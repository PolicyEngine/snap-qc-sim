"""Hurdle deviation model and temporally honest state calibration.

The diagnostic payment-error outcome is adjudicated, not reconstructed:
``STATUS in {2, 3} and AMTERR > the fiscal-year threshold``.  The hurdle's
signed deviation is ``D = RAWBEN - BENFIX``.  BENFIX is the allotment after
identified errors and legitimate allotment adjustments have been resolved;
using RAWBEN - FSBEN would therefore misclassify legitimate adjustments as
errors.  FSBEN remains an intentional predictor, named ``formula_benefit``,
because it is the closest public-file analogue to the formula anchor a rules
engine can recompute under a counterfactual.

This module implements only the current three-part expected-dollar model:

1. P(any adjudicated benefit deviation),
2. P(official above-threshold error | deviation), and
3. E[|D| | official error] using a log model and OOF Duan smearing.

It does not implement a signed conditional distribution, benefit draws, an
input-noise model, or a computation-failure mixture.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict

if __package__:  # Package import (tests and ``python -m analysis...``).
    from .train_error_model import (
        BBCE_PATH,
        COVARIATES,
        INTERMEDIATES,
        MEDICARE_PART_B_PATH,
        QC_DIR,
        SMD_PATH,
        THRESHOLD,
        YEAR_TEST,
        YEARS_TRAIN,
        build_features,
        load_bbce_registry,
        load_medicare_part_b_premiums,
        load_smd_registry,
        load_year,
    )
else:  # Direct script execution from the analysis directory.
    from train_error_model import (
        BBCE_PATH,
        COVARIATES,
        INTERMEDIATES,
        MEDICARE_PART_B_PATH,
        QC_DIR,
        SMD_PATH,
        THRESHOLD,
        YEAR_TEST,
        YEARS_TRAIN,
        build_features,
        load_bbce_registry,
        load_medicare_part_b_premiums,
        load_smd_registry,
        load_year,
    )

OUT = Path(__file__).with_name("hurdle_results.json")
RANDOM_STATE = 7
N_FOLDS = 5
DEVIATION_TOLERANCE = 0.5
MODEL_PARAMS = {
    "max_iter": 300,
    "learning_rate": 0.08,
    "max_leaf_nodes": 63,
    "random_state": RANDOM_STATE,
}


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], context: str) -> None:
    """Raise instead of silently dropping a requested schema field."""
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise KeyError(f"{context} is missing required columns: {missing}")


def add_hurdle_targets(
    frame: pd.DataFrame, deviation_tolerance: float = DEVIATION_TOLERANCE
) -> pd.DataFrame:
    """Return a copy with nested ``deviates`` and ``crosses`` targets.

    ``crosses`` is the official-error label supplied by adjudication fields,
    never a benefit-difference proxy. Stage 1 is strictly ``|D| > 0.5``.
    Stage 2 is fit only on stage-1-positive rows; the handful of official
    errors whose BENFIX deviation does not clear the tolerance are reported as
    reconciliation anomalies rather than promoted into the stage-1 target.
    """
    _require_columns(frame, ["D", "official_error"], "hurdle target frame")
    if deviation_tolerance < 0:
        raise ValueError("deviation_tolerance must be non-negative")

    result = frame.copy()
    deviation = pd.to_numeric(result["D"], errors="coerce")
    official = pd.to_numeric(result["official_error"], errors="coerce")
    if deviation.isna().any():
        raise ValueError("D must be numeric and nonmissing before targets are added")
    if official.isna().any() or not official.isin([0, 1]).all():
        raise ValueError("official_error must be a nonmissing binary indicator")

    result["crosses"] = official.astype(np.int8)
    result["deviates"] = (deviation.abs() > deviation_tolerance).astype(np.int8)
    return result


def _feature_columns(data: pd.DataFrame) -> list[str]:
    """Build the nested full feature set and enforce feature discipline."""
    prohibited = {"cat_elig", "cat_elig_code", "CAT_ELIG"}
    covariates = [c for c in COVARIATES if c not in prohibited]
    intermediates = [c for c in INTERMEDIATES if c not in prohibited]

    # This is a burden/computation intermediate, not a static household
    # covariate.  Keep this guard until all downstream imports have migrated.
    covariates = [c for c in covariates if c != "deductions_per_member"]
    if "deductions_per_member" not in intermediates:
        intermediates.append("deductions_per_member")

    features = list(
        dict.fromkeys(
            covariates + intermediates + ["formula_benefit", "formula_benefit_missing"]
        )
    )
    _require_columns(data, features, "assembled hurdle features")
    if set(features) & prohibited:
        raise AssertionError("static categorical-eligibility fields cannot be features")

    numeric = data[features].apply(pd.to_numeric, errors="coerce")
    infinite = np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan))
    if infinite.any():
        bad = [features[i] for i in np.flatnonzero(infinite.any(axis=0))]
        raise ValueError(f"model features contain infinite values: {bad}")
    # HistGradientBoosting natively routes NaN values.  Missingness indicators
    # are created by build_features for informative source fields; the formula
    # anchor indicator is added explicitly in assemble().
    return features


def assemble() -> pd.DataFrame:
    """Load the official CASE==1 universe and assemble hurdle inputs."""
    registry = load_smd_registry()
    bbce_registry = load_bbce_registry()
    part_b_premiums = load_medicare_part_b_premiums()
    frames: list[pd.DataFrame] = []
    dropped: dict[str, int] = {}
    raw_required = [
        "CASE",
        "STATUS",
        "AMTERR",
        "RAWBEN",
        "BENFIX",
        "FSBEN",
        "BENMAX",
        "HWGT",
    ]

    for year in YEARS_TRAIN + [YEAR_TEST]:
        df = load_year(year)
        _require_columns(df, raw_required, f"FY{year} QC file")
        if not (pd.to_numeric(df["CASE"], errors="coerce") == 1).all():
            raise ValueError(f"FY{year}: load_year did not enforce CASE == 1")
        if year not in registry:
            raise KeyError(f"SMD registry has no FY{year} entry")

        threshold = THRESHOLD[year]
        status = pd.to_numeric(df["STATUS"], errors="coerce")
        amterr = pd.to_numeric(df["AMTERR"], errors="coerce")
        assigned = pd.to_numeric(df["RAWBEN"], errors="coerce")
        corrected = pd.to_numeric(df["BENFIX"], errors="coerce")
        formula = pd.to_numeric(df["FSBEN"], errors="coerce")
        benmax = pd.to_numeric(df["BENMAX"], errors="coerce")
        weight = pd.to_numeric(df["HWGT"], errors="coerce")
        if benmax.isna().any() or (benmax <= 0).any():
            raise ValueError(f"FY{year}: BENMAX must be finite and positive")

        # Missing target/weight values cannot be assigned a label or loss and
        # are excluded explicitly.  Formula-benefit NaNs remain modelable and
        # receive a missingness indicator rather than a blind zero fill.
        valid = (
            status.notna()
            & amterr.notna()
            & assigned.notna()
            & corrected.notna()
            & weight.notna()
            & (weight > 0)
        )
        dropped[str(year)] = int((~valid).sum())

        # Feature construction also derives diagnostic outcomes, so filter
        # records whose targets/losses cannot be defined before calling it.
        # Informative missing predictors (including FSBEN) remain in the data.
        valid_df = df.loc[valid].copy()
        features = build_features(
            valid_df,
            registry[year],
            bbce_registry[year],
            part_b_premiums,
        ).copy()
        if not features.index.equals(valid_df.index):
            raise ValueError(f"FY{year}: build_features changed row alignment")

        features["D"] = assigned.loc[valid] - corrected.loc[valid]
        features["benmax"] = benmax.loc[valid]
        features["deviation_cap"] = np.maximum(features["benmax"], features["D"].abs())
        features["official_error"] = (
            status.loc[valid].isin([2, 3]) & (amterr.loc[valid] > threshold)
        ).astype(np.int8)
        features["formula_benefit"] = formula.loc[valid]
        features["formula_benefit_missing"] = formula.loc[valid].isna().astype(np.int8)
        features["formula_deviation_abs"] = (
            assigned.loc[valid] - formula.loc[valid]
        ).abs()
        features["amterr"] = amterr.loc[valid]
        features["issuance"] = assigned.loc[valid]
        features["thr"] = threshold
        features["w"] = weight.loc[valid]
        features = add_hurdle_targets(features)
        features["obs_error_dollars"] = features["amterr"] * features["official_error"]
        frames.append(features)

    data = pd.concat(frames, ignore_index=True)
    data.attrs["dropped_missing_target_or_weight_by_year"] = dropped
    _feature_columns(data)
    return data


def effective_sample_size(weights: np.ndarray | pd.Series) -> float:
    """Kish effective sample size for non-negative analysis weights."""
    w = np.asarray(weights, dtype=float)
    w = w[np.isfinite(w) & (w > 0)]
    if not len(w):
        return 0.0
    return float(w.sum() ** 2 / np.square(w).sum())


def _weighted_mean(values: np.ndarray | pd.Series, weights: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    valid = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not valid.any():
        raise ValueError("weighted mean has no finite positive-weight observations")
    return float(np.average(x[valid], weights=w[valid]))


def _safe_auc(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    if np.unique(y).size < 2:
        raise ValueError("ROC AUC requires both outcome classes")
    return float(roc_auc_score(y, p, sample_weight=w))


def _calibration_in_the_large(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    """Weighted logit-intercept recalibration; positive means underprediction."""
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-8, 1 - 1e-8)
    w = np.asarray(w, dtype=float)
    observed = _weighted_mean(y, w)
    if observed <= 0 or observed >= 1:
        return float("nan")
    logit = np.log(p / (1 - p))
    lo, hi = -30.0, 30.0
    for _ in range(100):
        mid = (lo + hi) / 2
        fitted = 1 / (1 + np.exp(-np.clip(logit + mid, -50, 50)))
        if _weighted_mean(fitted, w) < observed:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2)


def _probability_metrics(
    y: np.ndarray, raw_probability: np.ndarray, probability: np.ndarray, w: np.ndarray
) -> dict[str, float | int]:
    y = np.asarray(y, dtype=int)
    raw = np.asarray(raw_probability, dtype=float)
    calibrated = np.asarray(probability, dtype=float)
    weights = np.asarray(w, dtype=float)
    prevalence = _weighted_mean(y, weights)
    mean_raw = _weighted_mean(raw, weights)
    mean_calibrated = _weighted_mean(calibrated, weights)
    return {
        "n": len(y),
        "effective_n": effective_sample_size(weights),
        "weighted_prevalence": prevalence,
        "unweighted_prevalence": float(y.mean()),
        "auc_raw": _safe_auc(y, raw, weights),
        "auc_calibrated": _safe_auc(y, calibrated, weights),
        "pr_auc_raw": float(average_precision_score(y, raw, sample_weight=weights)),
        "pr_auc_calibrated": float(
            average_precision_score(y, calibrated, sample_weight=weights)
        ),
        "weighted_brier_raw": _weighted_mean(np.square(raw - y), weights),
        "weighted_brier_calibrated": _weighted_mean(np.square(calibrated - y), weights),
        "mean_probability_raw": mean_raw,
        "mean_probability_calibrated": mean_calibrated,
        "mean_calibration_error_raw": mean_raw - prevalence,
        "mean_calibration_error_calibrated": mean_calibrated - prevalence,
        "calibration_in_the_large_raw": _calibration_in_the_large(y, raw, weights),
        "calibration_in_the_large_calibrated": _calibration_in_the_large(
            y, calibrated, weights
        ),
    }


def _weighted_cross_val_predict(
    estimator: Any,
    x: pd.DataFrame,
    y: pd.Series,
    weights: pd.Series,
    cv: Any,
    method: str,
) -> np.ndarray:
    """Call cross_val_predict across supported sklearn sample-weight APIs."""
    kwargs: dict[str, Any] = {
        "estimator": estimator,
        "X": x,
        "y": y,
        "cv": cv,
        "method": method,
    }
    fit_argument = {"sample_weight": weights.to_numpy(dtype=float)}
    if "params" in inspect.signature(cross_val_predict).parameters:
        kwargs["params"] = fit_argument
    else:  # scikit-learn < 1.4
        kwargs["fit_params"] = fit_argument
    return np.asarray(cross_val_predict(**kwargs))


def _classifier() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(**MODEL_PARAMS)


def _regressor() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(**MODEL_PARAMS)


@dataclass
class ProbabilityStage:
    model: HistGradientBoostingClassifier
    calibrator: IsotonicRegression
    oof_metrics: dict[str, Any]

    def predict_raw(self, x: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(x)[:, 1]

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return np.clip(self.calibrator.predict(self.predict_raw(x)), 0, 1)


@dataclass
class HurdleBundle:
    stage1: ProbabilityStage
    stage2: ProbabilityStage
    magnitude_model: HistGradientBoostingRegressor
    smear: float
    stage3_oof_n: int
    stage3_zero_magnitude_excluded: int
    stage3_oof_observed_mean_weighted: float
    stage3_oof_predicted_mean_weighted: float
    stage3_oof_mae_weighted: float
    stage3_nested_oof_fold_smears: list[float]
    stage3_nested_oof_inner_folds: list[int]


def _nested_probability_oof_predictions(
    x: pd.DataFrame,
    y: pd.Series,
    weights: pd.Series,
    n_splits: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Return leakage-free raw and isotonic-calibrated outer-fold scores.

    Within each outer training set, inner OOF base-model scores train that
    fold's isotonic calibrator. The base model is then refit on the full outer
    training set before scoring the untouched outer test set. Consequently no
    outer-test outcome can affect either its base prediction or calibrator.
    """
    raw_oof = np.full(len(y), np.nan, dtype=float)
    calibrated_oof = np.full(len(y), np.nan, dtype=float)
    inner_folds: list[int] = []
    outer_cv = StratifiedKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=seed,
    )

    for fold, (fit_idx, score_idx) in enumerate(outer_cv.split(x, y)):
        x_fit = x.iloc[fit_idx]
        y_fit = y.iloc[fit_idx]
        w_fit = weights.iloc[fit_idx]
        inner_class_counts = y_fit.value_counts()
        inner_n_splits = min(N_FOLDS, int(inner_class_counts.min()))
        if inner_n_splits < 2:
            raise ValueError("outer training fold has too few cases for inner OOF")
        inner_folds.append(inner_n_splits)
        inner_cv = StratifiedKFold(
            n_splits=inner_n_splits,
            shuffle=True,
            random_state=seed + 10_000 + fold,
        )
        inner_raw = _weighted_cross_val_predict(
            _classifier(),
            x_fit,
            y_fit,
            w_fit,
            inner_cv,
            "predict_proba",
        )[:, 1]
        fold_calibrator = IsotonicRegression(
            out_of_bounds="clip",
            y_min=0,
            y_max=1,
        )
        fold_calibrator.fit(
            inner_raw,
            y_fit.to_numpy(dtype=int),
            sample_weight=w_fit.to_numpy(dtype=float),
        )

        fold_model = _classifier()
        fold_model.fit(x_fit, y_fit, sample_weight=w_fit)
        fold_raw = fold_model.predict_proba(x.iloc[score_idx])[:, 1]
        raw_oof[score_idx] = fold_raw
        calibrated_oof[score_idx] = fold_calibrator.predict(fold_raw)

    if not np.isfinite(raw_oof).all() or not np.isfinite(calibrated_oof).all():
        raise ValueError("nested probability cross-fitting produced invalid scores")
    return raw_oof, np.clip(calibrated_oof, 0, 1), inner_folds


def _nested_magnitude_oof_predictions(
    x: pd.DataFrame,
    log_magnitude: pd.Series,
    weights: pd.Series,
    n_splits: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, list[float], list[int]]:
    """Return outer-fold log scores and independently smeared diagnostics.

    Each outer-fold smear is learned from inner OOF residuals within that
    outer training set. Thus an outer-test row affects neither its log-score
    model nor the smearing factor used for its diagnostic magnitude.
    """
    oof_log_prediction = np.full(len(log_magnitude), np.nan, dtype=float)
    oof_magnitude = np.full(len(log_magnitude), np.nan, dtype=float)
    fold_smears: list[float] = []
    inner_folds: list[int] = []
    outer_cv = KFold(n_splits=n_splits, shuffle=True, random_state=seed)

    for fold, (fit_idx, score_idx) in enumerate(outer_cv.split(x)):
        x_fit = x.iloc[fit_idx]
        y_fit = log_magnitude.iloc[fit_idx]
        w_fit = weights.iloc[fit_idx]
        inner_n_splits = min(N_FOLDS, len(fit_idx))
        if inner_n_splits < 2:
            raise ValueError("outer training fold has too few cases for inner OOF")
        inner_folds.append(inner_n_splits)
        inner_cv = KFold(
            n_splits=inner_n_splits,
            shuffle=True,
            random_state=seed + 10_000 + fold,
        )
        inner_oof_log = _weighted_cross_val_predict(
            _regressor(),
            x_fit,
            y_fit,
            w_fit,
            inner_cv,
            "predict",
        )
        inner_residual = y_fit.to_numpy(dtype=float) - inner_oof_log
        fold_smear = _weighted_mean(
            np.exp(inner_residual),
            w_fit.to_numpy(dtype=float),
        )
        if not np.isfinite(fold_smear) or fold_smear <= 0:
            raise ValueError("nested OOF Duan smear must be finite and positive")
        fold_smears.append(fold_smear)

        fold_model = _regressor()
        fold_model.fit(x_fit, y_fit, sample_weight=w_fit)
        fold_log_prediction = fold_model.predict(x.iloc[score_idx])
        oof_log_prediction[score_idx] = fold_log_prediction
        oof_magnitude[score_idx] = np.exp(fold_log_prediction) * fold_smear

    if (
        not np.isfinite(oof_log_prediction).all()
        or not np.isfinite(oof_magnitude).all()
    ):
        raise ValueError("nested magnitude cross-fitting produced invalid scores")
    return oof_log_prediction, oof_magnitude, fold_smears, inner_folds


def _fit_probability_stage(
    train: pd.DataFrame, features: list[str], target: str, seed: int
) -> ProbabilityStage:
    y = train[target].astype(int)
    class_counts = y.value_counts()
    if set(class_counts.index) != {0, 1}:
        raise ValueError(f"{target} must contain both classes")
    n_splits = min(N_FOLDS, int(class_counts.min()))
    if n_splits < 2:
        raise ValueError(f"{target} has too few observations for OOF calibration")

    raw_oof, calibrated_oof, inner_folds = _nested_probability_oof_predictions(
        train[features],
        y,
        train["w"],
        n_splits,
        seed,
    )
    # Deployment uses the model refit on all training rows and an isotonic
    # calibrator fit to their full-training OOF base scores. The nested scores
    # above are reserved for leakage-free training diagnostics.
    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
    calibrator.fit(raw_oof, y, sample_weight=train["w"])
    model = _classifier()
    model.fit(train[features], y, sample_weight=train["w"])
    metrics = _probability_metrics(
        y.to_numpy(), raw_oof, calibrated_oof, train["w"].to_numpy()
    )
    metrics["oof_method"] = "nested_outer_inner"
    metrics["outer_folds"] = n_splits
    metrics["inner_folds_by_outer_fold"] = inner_folds
    return ProbabilityStage(model, calibrator, metrics)


def fit_hurdle(train: pd.DataFrame, features: list[str]) -> HurdleBundle:
    """Fit both calibrated probabilities and the OOF-smeared magnitude."""
    _require_columns(
        train,
        features + ["deviates", "crosses", "D", "w"],
        "hurdle training frame",
    )
    stage1 = _fit_probability_stage(train, features, "deviates", RANDOM_STATE)

    stage2_train = train.loc[train["deviates"] == 1]
    if not stage2_train["deviates"].eq(1).all():
        raise AssertionError("stage-2 training population is not nested")
    stage2 = _fit_probability_stage(
        stage2_train, features, "crosses", RANDOM_STATE + 10
    )

    official = stage2_train.loc[stage2_train["crosses"] == 1]
    positive = official.loc[official["D"].abs() > 0]
    excluded = int(len(official) - len(positive))
    if len(positive) < N_FOLDS:
        raise ValueError("too few positive magnitudes for OOF Duan smearing")
    log_magnitude = np.log(positive["D"].abs())
    (
        oof_log_prediction,
        nested_oof_magnitude,
        nested_fold_smears,
        nested_inner_folds,
    ) = _nested_magnitude_oof_predictions(
        positive[features],
        log_magnitude,
        positive["w"],
        N_FOLDS,
        RANDOM_STATE + 20,
    )
    # The deployable smear uses every full-training OOF residual. Nested fold
    # smears above are used only to score leakage-free training diagnostics.
    residual = log_magnitude.to_numpy() - oof_log_prediction
    smear = _weighted_mean(np.exp(residual), positive["w"].to_numpy())
    observed_magnitude = positive["D"].abs().to_numpy(dtype=float)
    magnitude_weights = positive["w"].to_numpy(dtype=float)
    if not np.isfinite(smear) or smear <= 0:
        raise ValueError("OOF Duan smearing factor must be finite and positive")
    magnitude_model = _regressor()
    magnitude_model.fit(positive[features], log_magnitude, sample_weight=positive["w"])
    return HurdleBundle(
        stage1=stage1,
        stage2=stage2,
        magnitude_model=magnitude_model,
        smear=smear,
        stage3_oof_n=len(positive),
        stage3_zero_magnitude_excluded=excluded,
        stage3_oof_observed_mean_weighted=_weighted_mean(
            observed_magnitude, magnitude_weights
        ),
        stage3_oof_predicted_mean_weighted=_weighted_mean(
            nested_oof_magnitude, magnitude_weights
        ),
        stage3_oof_mae_weighted=_weighted_mean(
            np.abs(nested_oof_magnitude - observed_magnitude), magnitude_weights
        ),
        stage3_nested_oof_fold_smears=nested_fold_smears,
        stage3_nested_oof_inner_folds=nested_inner_folds,
    )


def predict_hurdle(
    bundle: HurdleBundle, data: pd.DataFrame, features: list[str]
) -> pd.DataFrame:
    """Add raw/calibrated component predictions and expected error dollars."""
    result = data.copy()
    result["p1_raw"] = bundle.stage1.predict_raw(result[features])
    result["p1"] = bundle.stage1.predict(result[features])
    result["p2_raw"] = bundle.stage2.predict_raw(result[features])
    result["p2"] = bundle.stage2.predict(result[features])
    result["pred_magnitude"] = (
        np.exp(bundle.magnitude_model.predict(result[features])) * bundle.smear
    )
    result["pred_err_dollars"] = result["p1"] * result["p2"] * result["pred_magnitude"]
    return result


def _evaluate_probability_stage(
    stage: ProbabilityStage,
    data: pd.DataFrame,
    features: list[str],
    target: str,
) -> dict[str, float | int]:
    y = data[target].to_numpy(dtype=int)
    raw = stage.predict_raw(data[features])
    calibrated = stage.predict(data[features])
    return _probability_metrics(y, raw, calibrated, data["w"].to_numpy())


def _importance(
    model: HistGradientBoostingClassifier,
    data: pd.DataFrame,
    features: list[str],
    target: str,
) -> list[dict[str, float | str]]:
    """Weighted holdout permutation importance on the ROC-AUC scale."""
    result = permutation_importance(
        model,
        data[features],
        data[target],
        scoring="roc_auc",
        n_repeats=3,
        random_state=RANDOM_STATE,
        sample_weight=data["w"],
    )
    order = np.argsort(-result.importances_mean)
    return [
        {
            "feature": features[i],
            "roc_auc_decrease_mean": float(result.importances_mean[i]),
            "roc_auc_decrease_std": float(result.importances_std[i]),
        }
        for i in order
    ]


def _prevalence(data: pd.DataFrame, column: str) -> dict[str, float | int]:
    return {
        "n": len(data),
        "unweighted": float(data[column].mean()),
        "weighted": _weighted_mean(data[column], data["w"].to_numpy()),
    }


def _state_rates(data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate expected and official error dollars over observed issuance."""
    rows: list[dict[str, float | int | str]] = []
    for state, group in data.groupby("state", sort=True):
        w = group["w"].to_numpy(dtype=float)
        issuance = group["issuance"].to_numpy(dtype=float)
        observed = group["obs_error_dollars"].to_numpy(dtype=float)
        predicted = group["pred_err_dollars"].to_numpy(dtype=float)
        issuance_total = float(np.sum(w * issuance))
        if not np.isfinite(issuance_total) or issuance_total <= 0:
            raise ValueError(f"{state}: issuance total must be finite and positive")
        observed_total = float(np.sum(w * observed))
        predicted_total = float(np.sum(w * predicted))
        if not np.isfinite(predicted_total) or predicted_total <= 0:
            raise ValueError(
                f"{state}: predicted error-dollar total must be finite and positive"
            )

        observed_mean = _weighted_mean(observed, w)
        predicted_mean = _weighted_mean(predicted, w)
        ratio = observed_mean / predicted_mean
        n_eff = effective_sample_size(w)
        # Delta-method influence values for the ratio of two weighted means.
        # This accounts for case-level variation in both observed and predicted
        # dollars; dividing their weighted variance by Kish effective n avoids
        # treating large raw samples with highly uneven QC weights as precise.
        ratio_contribution = (observed - ratio * predicted) / predicted_mean
        ratio_variance = _weighted_mean(np.square(ratio_contribution), w)
        if n_eff > 1:
            ratio_variance *= n_eff / (n_eff - 1)
        # A small effective-n floor prevents an all-identical state's sample
        # variance from implying infinite precision.
        factor_sampling_variance = max(
            ratio_variance / max(n_eff, 1.0), 1.0 / max(n_eff, 1.0) ** 2
        )
        rows.append(
            {
                "state": str(state),
                "n": len(group),
                "effective_n": n_eff,
                "issuance_total": issuance_total,
                "pred_rate": 100 * predicted_total / issuance_total,
                "obs_rate": 100 * observed_total / issuance_total,
                "observed_to_predicted_ratio": ratio,
                "factor_sampling_variance": factor_sampling_variance,
            }
        )
        if "applied_state_factor" in group:
            applied = group["applied_state_factor"].dropna().unique()
            if len(applied) != 1:
                raise ValueError(f"{state}: adjusted rows have inconsistent factors")
            rows[-1]["applied_state_factor"] = float(applied[0])
    if not rows:
        raise ValueError("no states have positive issuance and predictions")
    return pd.DataFrame(rows).sort_values("state").reset_index(drop=True)


def weighted_calibration_metrics(
    state_rates: pd.DataFrame, weights: str | np.ndarray | pd.Series | None = None
) -> dict[str, float | int]:
    """Slope/intercept/error/correlation across state rate pairs.

    Pass ``weights=None`` for equal-jurisdiction metrics or
    ``weights='issuance_total'`` for issuance-weighted metrics.
    """
    _require_columns(state_rates, ["pred_rate", "obs_rate"], "state rates")
    x = state_rates["pred_rate"].to_numpy(dtype=float)
    y = state_rates["obs_rate"].to_numpy(dtype=float)
    if weights is None:
        w = np.ones(len(state_rates), dtype=float)
    elif isinstance(weights, str):
        _require_columns(state_rates, [weights], "state-rate weights")
        w = state_rates[weights].to_numpy(dtype=float)
    else:
        w = np.asarray(weights, dtype=float)
    if len(w) != len(x):
        raise ValueError("calibration weights must match state-rate rows")
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(w) & (w > 0)
    x, y, w = x[valid], y[valid], w[valid]
    if len(x) < 2:
        raise ValueError("calibration metrics require at least two jurisdictions")

    x_mean = _weighted_mean(x, w)
    y_mean = _weighted_mean(y, w)
    covariance = _weighted_mean((x - x_mean) * (y - y_mean), w)
    x_variance = _weighted_mean(np.square(x - x_mean), w)
    y_variance = _weighted_mean(np.square(y - y_mean), w)
    if x_variance <= 0 or y_variance <= 0:
        raise ValueError("calibration rates have zero cross-state variance")
    slope = covariance / x_variance
    return {
        "states": len(x),
        "slope": slope,
        "intercept_pp": y_mean - slope * x_mean,
        "mae_pp": _weighted_mean(np.abs(x - y), w),
        "rmse_pp": float(np.sqrt(_weighted_mean(np.square(x - y), w))),
        "corr": float(covariance / np.sqrt(x_variance * y_variance)),
    }


def _calibration_summary(state_rates: pd.DataFrame) -> dict[str, Any]:
    return {
        "equal_jurisdiction": weighted_calibration_metrics(state_rates),
        "issuance_weighted": weighted_calibration_metrics(
            state_rates, "issuance_total"
        ),
    }


def _shrink_state_factors(
    fy2023_rates: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float | str]]:
    """Empirical-Bayes factors centered at one with effective-n precision."""
    _require_columns(
        fy2023_rates,
        [
            "observed_to_predicted_ratio",
            "factor_sampling_variance",
            "effective_n",
        ],
        "FY2023 factor rates",
    )
    factors = fy2023_rates.copy()
    raw = factors["observed_to_predicted_ratio"].to_numpy(dtype=float)
    sampling_variance = factors["factor_sampling_variance"].to_numpy(dtype=float)
    n_eff = factors["effective_n"].to_numpy(dtype=float)

    # Method-of-moments between-state variance around the fixed prior mean 1.
    # State contributions are weighted by Kish effective sample size.
    prior_variance = max(
        0.0,
        _weighted_mean(np.square(raw - 1) - sampling_variance, n_eff),
    )
    if prior_variance == 0:
        shrinkage_weight = np.zeros(len(factors), dtype=float)
    else:
        data_precision = 1 / sampling_variance
        prior_precision = 1 / prior_variance
        shrinkage_weight = data_precision / (data_precision + prior_precision)
    factors["raw_factor"] = raw
    factors["shrinkage_weight"] = shrinkage_weight
    factors["state_factor"] = 1 + shrinkage_weight * (raw - 1)
    return factors, {
        "method": (
            "empirical-Bayes precision weighting around factor 1; observation "
            "variance uses a ratio influence function and the Kish effective "
            "sample size"
        ),
        "prior_mean": 1.0,
        "estimated_between_state_variance": prior_variance,
    }


def _apply_state_factors(data: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    _require_columns(data, ["state", "pred_err_dollars"], "factor application data")
    _require_columns(factors, ["state", "state_factor"], "state factors")
    if factors["state"].duplicated().any():
        duplicates = sorted(
            factors.loc[factors["state"].duplicated(), "state"].unique()
        )
        raise ValueError(f"state factors contain duplicate jurisdictions: {duplicates}")
    factor_values = pd.to_numeric(factors["state_factor"], errors="coerce")
    if factor_values.isna().any() or not np.isfinite(factor_values).all():
        raise ValueError("state factors must be finite numeric values")
    if (factor_values <= 0).any():
        raise ValueError("state factors must be positive")

    factor_map = factors.set_index("state")["state_factor"]
    result = data.copy()
    result["applied_state_factor"] = result["state"].map(factor_map)
    if result["applied_state_factor"].isna().any():
        missing = sorted(
            result.loc[result["applied_state_factor"].isna(), "state"].unique()
        )
        raise ValueError(f"no frozen FY2023 factor is available for states: {missing}")
    result["pred_err_dollars"] = (
        result["pred_err_dollars"] * result["applied_state_factor"]
    )
    return result


def _magnitude_summary(data: pd.DataFrame) -> dict[str, float | int]:
    official = data.loc[(data["deviates"] == 1) & (data["crosses"] == 1)]
    w = official["w"].to_numpy(dtype=float)
    return {
        "n": len(official),
        "effective_n": effective_sample_size(w),
        "observed_abs_D_mean_weighted": _weighted_mean(official["D"].abs(), w),
        "observed_abs_D_mean_unweighted": float(official["D"].abs().mean()),
        "observed_AMTERR_mean_weighted": _weighted_mean(official["amterr"], w),
        "predicted_abs_D_mean_weighted": _weighted_mean(official["pred_magnitude"], w),
        "predicted_abs_D_mean_unweighted": float(official["pred_magnitude"].mean()),
        "observed_signed_D_mean_weighted": _weighted_mean(official["D"], w),
    }


def _hurdle_population_summary(data: pd.DataFrame) -> dict[str, float | int]:
    """Describe the nested stage-2 population and reconciliation anomalies."""
    stage1 = data["deviates"].eq(1)
    official = data["crosses"].eq(1)
    outside = official & ~stage1
    official_dollars = np.sum(
        data.loc[official, "w"].to_numpy(dtype=float)
        * data.loc[official, "obs_error_dollars"].to_numpy(dtype=float)
    )
    outside_dollars = np.sum(
        data.loc[outside, "w"].to_numpy(dtype=float)
        * data.loc[outside, "obs_error_dollars"].to_numpy(dtype=float)
    )
    return {
        "stage1_positive_n": int(stage1.sum()),
        "stage2_population_n": int(stage1.sum()),
        "official_error_n": int(official.sum()),
        "official_errors_inside_stage2_n": int((official & stage1).sum()),
        "official_errors_outside_stage2_n": int(outside.sum()),
        "official_error_dollars_outside_stage2_weighted_share": (
            float(outside_dollars / official_dollars) if official_dollars > 0 else 0.0
        ),
    }


def _concordance(data: pd.DataFrame) -> dict[str, float | int]:
    w = data["w"].to_numpy(dtype=float)
    d_match = np.isclose(
        data["D"].abs().to_numpy(dtype=float),
        data["amterr"].to_numpy(dtype=float),
        rtol=0,
        atol=1e-9,
    )
    formula_valid = data["formula_deviation_abs"].notna().to_numpy()
    formula_match = np.isclose(
        data.loc[formula_valid, "formula_deviation_abs"].to_numpy(dtype=float),
        data.loc[formula_valid, "amterr"].to_numpy(dtype=float),
        rtol=0,
        atol=1e-9,
    )
    return {
        "n": len(data),
        "abs_RAWBEN_minus_BENFIX_equals_AMTERR_weighted": _weighted_mean(
            d_match.astype(float), w
        ),
        "abs_RAWBEN_minus_BENFIX_equals_AMTERR_unweighted": float(d_match.mean()),
        "formula_valid_n": int(formula_valid.sum()),
        "abs_RAWBEN_minus_FSBEN_equals_AMTERR_weighted": _weighted_mean(
            formula_match.astype(float), w[formula_valid]
        ),
        "abs_RAWBEN_minus_FSBEN_equals_AMTERR_unweighted": float(formula_match.mean()),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_versions() -> dict[str, str]:
    packages = ["numpy", "pandas", "scikit-learn", "pyreadstat", "scipy"]
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _provenance() -> dict[str, Any]:
    inputs: dict[str, str] = {}
    for year in YEARS_TRAIN + [YEAR_TEST]:
        path = QC_DIR / f"qc_pub_fy{year}.sav"
        if not path.is_file():
            raise FileNotFoundError(f"missing pipeline input: {path}")
        inputs[path.name] = _sha256(path)
    registry = SMD_PATH
    if not registry.is_file():
        raise FileNotFoundError(f"missing pipeline input: {registry}")
    inputs[registry.name] = _sha256(registry)
    for feature_registry in (BBCE_PATH, MEDICARE_PART_B_PATH):
        if not feature_registry.is_file():
            raise FileNotFoundError(f"missing pipeline input: {feature_registry}")
        inputs[feature_registry.name] = _sha256(feature_registry)
    return {
        "package_versions": _package_versions(),
        "input_sha256": inputs,
        "threshold_dollars_by_fiscal_year": {
            str(year): int(amount) for year, amount in sorted(THRESHOLD.items())
        },
        "random_state": RANDOM_STATE,
        "oof_folds": N_FOLDS,
        "oof_design": {
            "probability_training_metrics": (
                "nested outer/inner cross-fitting; each outer calibrator is fit "
                "on inner OOF base scores from its outer training set"
            ),
            "deployable_probability_calibrator": (
                "weighted isotonic fit on all full-training OOF base scores"
            ),
            "magnitude_training_metrics": (
                "outer-fold log predictions multiplied by Duan smears fit on "
                "inner OOF residuals from the corresponding outer training set"
            ),
            "deployable_duan_smear": (
                "weighted mean exp(residual) over all full-training OOF residuals"
            ),
        },
        "deviation_tolerance_dollars": DEVIATION_TOLERANCE,
        "model_parameters": MODEL_PARAMS,
    }


def _state_records(
    rates: pd.DataFrame, factor_label: str | None = None
) -> list[dict[str, Any]]:
    output = rates.copy()
    if factor_label is not None:
        output = output.rename(columns={"observed_to_predicted_ratio": factor_label})
    return output.to_dict("records")


def main(output_path: str | Path = OUT) -> dict[str, Any]:
    data = assemble()
    features = _feature_columns(data)
    primary_train = data.loc[data["year"].isin(YEARS_TRAIN)]
    fy2024 = data.loc[data["year"] == YEAR_TEST].copy()

    print(
        f"primary train {len(primary_train):,} cases through FY{max(YEARS_TRAIN)}; "
        f"FY{YEAR_TEST} validation {len(fy2024):,} cases"
    )
    primary = fit_hurdle(primary_train, features)
    predicted_2024 = predict_hurdle(primary, fy2024, features)
    stage2_2024 = predicted_2024.loc[predicted_2024["deviates"] == 1]

    stage1_test = _evaluate_probability_stage(
        primary.stage1, predicted_2024, features, "deviates"
    )
    stage2_test = _evaluate_probability_stage(
        primary.stage2, stage2_2024, features, "crosses"
    )
    stage1_importance = _importance(
        primary.stage1.model, predicted_2024, features, "deviates"
    )
    stage2_importance = _importance(
        primary.stage2.model, stage2_2024, features, "crosses"
    )
    headline_rates = _state_rates(predicted_2024)
    headline_calibration = _calibration_summary(headline_rates)

    # Entire factor-validation path is temporally frozen.  The same hurdle
    # trained only through FY2022 predicts both factor-fit FY2023 and FY2024.
    factor_training_years = [year for year in YEARS_TRAIN if year < 2023]
    factor_train = data.loc[data["year"].isin(factor_training_years)]
    fy2023 = data.loc[data["year"] == 2023].copy()
    frozen = fit_hurdle(factor_train, features)
    frozen_2023 = predict_hurdle(frozen, fy2023, features)
    frozen_2024 = predict_hurdle(frozen, fy2024, features)
    fy2023_rates = _state_rates(frozen_2023)
    factors, shrinkage = _shrink_state_factors(fy2023_rates)
    adjusted_2024 = _apply_state_factors(frozen_2024, factors)
    frozen_2024_rates = _state_rates(frozen_2024)
    adjusted_2024_rates = _state_rates(adjusted_2024)

    magnitude = _magnitude_summary(predicted_2024)
    result: dict[str, Any] = {
        "schema_version": 2,
        "definitions": {
            "official_error": (
                "STATUS in {2,3} and AMTERR greater than the fiscal-year threshold"
            ),
            "signed_deviation_D": "RAWBEN - BENFIX",
            "stage1_deviates": (
                "abs(D) > 0.5 dollars; reconciliation anomalies are not promoted"
            ),
            "stage2_crosses": (
                "official_error, modeled only in the stage1-positive population"
            ),
            "probability_calibration": (
                "weighted isotonic regression; reported training metrics use "
                "nested outer/inner cross-fitting, while deployment fits the "
                "calibrator on all full-training OOF classifier predictions"
            ),
            "formula_benefit": (
                "FSBEN; intentional engine-computable formula anchor feature, not target"
            ),
            "observed_rate": (
                "weighted official AMTERR dollars divided by weighted RAWBEN issuance"
            ),
        },
        "provenance": _provenance(),
        "features": features,
        "prevalence": {
            "training_through_fy2023": {
                "deviates": _prevalence(primary_train, "deviates"),
                "official_error": _prevalence(primary_train, "crosses"),
            },
            "fy2024": {
                "deviates": _prevalence(fy2024, "deviates"),
                "official_error": _prevalence(fy2024, "crosses"),
            },
        },
        "target_concordance": {
            "all_years": _concordance(data),
            "fy2024": _concordance(fy2024),
        },
        "stage1": {
            "training_oof_cross_fitted": primary.stage1.oof_metrics,
            "fy2024": stage1_test,
            "permutation_importance_fy2024_scoring_roc_auc": stage1_importance,
        },
        "stage2": {
            "population": "rows with abs(D) > 0.5 dollars only",
            "training_oof_cross_fitted": primary.stage2.oof_metrics,
            "fy2024_among_stage1_positives": stage2_test,
            "permutation_importance_fy2024_scoring_roc_auc": stage2_importance,
        },
        "stage3": {
            "target": (
                "abs(RAWBEN - BENFIX) among official errors in the "
                "stage1-positive population"
            ),
            "smear_method": (
                "deployable weighted mean exp(full-training OOF log-magnitude residual)"
            ),
            "smear": primary.smear,
            "oof_n": primary.stage3_oof_n,
            "zero_magnitude_official_errors_excluded": (
                primary.stage3_zero_magnitude_excluded
            ),
            "training_oof": {
                "method": (
                    "nested outer/inner cross-fitting; each outer-fold log "
                    "prediction uses a Duan smear fit on inner OOF residuals "
                    "from that outer training set"
                ),
                "outer_folds": N_FOLDS,
                "inner_folds_by_outer_fold": (primary.stage3_nested_oof_inner_folds),
                "fold_smears": primary.stage3_nested_oof_fold_smears,
                "observed_abs_D_mean_weighted": (
                    primary.stage3_oof_observed_mean_weighted
                ),
                "predicted_abs_D_mean_weighted": (
                    primary.stage3_oof_predicted_mean_weighted
                ),
                "mae_weighted": primary.stage3_oof_mae_weighted,
            },
            "fy2024": magnitude,
        },
        "calibration": {
            "headline_fy2024_unfactored": {
                "label": "unfactored FY2024 validation; equal and issuance weighted",
                **headline_calibration,
                "states": _state_records(
                    headline_rates, "descriptive_anchor_factor_fy2024"
                ),
            },
            "fy2023_fit_factor_validation": {
                "label": (
                    "model and smear trained through FY2022; factors fit on OOS "
                    "FY2023 and frozen for FY2024"
                ),
                "model_training_years": factor_training_years,
                "factor_fit_year": 2023,
                "validation_year": 2024,
                "frozen_model_smear": frozen.smear,
                "shrinkage": shrinkage,
                "fy2023_unfactored": _calibration_summary(fy2023_rates),
                "factors": _state_records(factors),
                "fy2024_unfactored_frozen_model": _calibration_summary(
                    frozen_2024_rates
                ),
                "fy2024_factor_adjusted": {
                    **_calibration_summary(adjusted_2024_rates),
                    "states": _state_records(
                        adjusted_2024_rates,
                        "descriptive_residual_factor_fy2024_after_adjustment",
                    ),
                },
            },
        },
        "data_quality": {
            "dropped_missing_target_or_weight_by_year": data.attrs.get(
                "dropped_missing_target_or_weight_by_year", {}
            ),
            "hurdle_population_nesting": {
                "training_through_fy2023": _hurdle_population_summary(primary_train),
                "fy2024": _hurdle_population_summary(fy2024),
            },
        },
    }

    # Stable aliases ease comparison with the contaminated checked-in result;
    # the nested records above are authoritative and fully labeled.
    equal = headline_calibration["equal_jurisdiction"]
    issuance = headline_calibration["issuance_weighted"]
    adjusted_equal = weighted_calibration_metrics(adjusted_2024_rates)
    result.update(
        {
            "stage1_auc": stage1_test["auc_raw"],
            "stage2_auc_among_deviators": stage2_test["auc_raw"],
            "smear": primary.smear,
            "stage3_observed_mean": magnitude["observed_abs_D_mean_weighted"],
            "stage3_predicted_mean": magnitude["predicted_abs_D_mean_weighted"],
            "calibration_corr": equal["corr"],
            "calibration_mae_pp": equal["mae_pp"],
            "calibration_rmse_pp": equal["rmse_pp"],
            "calibration_slope": equal["slope"],
            "calibration_intercept_pp": equal["intercept_pp"],
            "calibration_issuance_weighted": issuance,
            "fy2023_fit_factor_adjusted_fy2024_mae_pp": adjusted_equal["mae_pp"],
        }
    )

    print(
        "stage 1 FY2024 AUC "
        f"{stage1_test['auc_raw']:.4f}; stage 2 AUC "
        f"{stage2_test['auc_raw']:.4f}; OOF smear {primary.smear:.3f}"
    )
    print(
        "FY2024 unfactored equal-state: "
        f"slope {equal['slope']:.3f}, intercept {equal['intercept_pp']:.3f}pp, "
        f"MAE {equal['mae_pp']:.3f}pp, RMSE {equal['rmse_pp']:.3f}pp, "
        f"corr {equal['corr']:.3f}"
    )
    print(
        "FY2024 unfactored issuance-weighted: "
        f"slope {issuance['slope']:.3f}, "
        f"intercept {issuance['intercept_pp']:.3f}pp, "
        f"MAE {issuance['mae_pp']:.3f}pp, RMSE {issuance['rmse_pp']:.3f}pp, "
        f"corr {issuance['corr']:.3f}"
    )
    print(
        "FY2023-fit frozen factor-adjusted FY2024 equal-state MAE "
        f"{adjusted_equal['mae_pp']:.3f}pp"
    )

    destination = Path(output_path)
    with destination.open("w") as file:
        json.dump(result, file, indent=2, sort_keys=True, allow_nan=False)
        file.write("\n")
    print(f"wrote {destination}")
    return result


if __name__ == "__main__":
    main()
