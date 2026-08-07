"""Signed per-case deviation distributions and FY2024 validation.

The model predicts the FY2024 SNAP QC error process from FY2017-19 and
FY2022-23 records.  It is predictive, not causal.  Conditional on a benefit
deviation (``abs(RAWBEN - BENFIX) > 0.5``), it estimates the sign and nine
quantiles of ``log(abs(D))``.  A log-scale exponential excess distribution
extends the quantile function beyond q99.

The direct comparison route retains the corrected v2 stage-2 classifier.
State-factor validation follows the same temporally frozen design as v2:
models fit through FY2022, factors fit on FY2023, and evaluation on FY2024.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

import scripts_build_model_data
from snap_qc_sim import QcCase, simulate

if __package__:
    from .hurdle_deviation_model import (
        MODEL_PARAMS,
        N_FOLDS,
        RANDOM_STATE,
        ProbabilityStage,
        _apply_state_factors,
        _calibration_summary,
        _evaluate_probability_stage,
        _feature_columns,
        _fit_probability_stage,
        _package_versions,
        _shrink_state_factors,
        _state_rates,
        _weighted_cross_val_predict,
        _weighted_mean,
        assemble,
        effective_sample_size,
    )
    from .hurdle_deviation_model import _provenance as hurdle_provenance
    from .predictive_process import (
        MAX_TAIL_SCALE,
        QUANTILE_LEVELS,
        TAIL_SCALE_MARGIN,
        conditional_survival,
        enforce_monotone_quantiles,
        expected_error_dollars,
    )
    from .train_error_model import THRESHOLD, YEAR_TEST, YEARS_TRAIN
else:
    from hurdle_deviation_model import (
        MODEL_PARAMS,
        N_FOLDS,
        RANDOM_STATE,
        ProbabilityStage,
        _apply_state_factors,
        _calibration_summary,
        _evaluate_probability_stage,
        _feature_columns,
        _fit_probability_stage,
        _package_versions,
        _shrink_state_factors,
        _state_rates,
        _weighted_cross_val_predict,
        _weighted_mean,
        assemble,
        effective_sample_size,
    )
    from hurdle_deviation_model import _provenance as hurdle_provenance
    from predictive_process import (
        MAX_TAIL_SCALE,
        QUANTILE_LEVELS,
        TAIL_SCALE_MARGIN,
        conditional_survival,
        enforce_monotone_quantiles,
        expected_error_dollars,
    )
    from train_error_model import THRESHOLD, YEAR_TEST, YEARS_TRAIN


OUT = Path(__file__).with_name("distributional_results.json")
APP_METADATA = Path(__file__).resolve().parents[1] / "app" / "public" / "data.json"
SIGN_SEED = RANDOM_STATE + 30
TAIL_SEED = RANDOM_STATE + 40
SIMULATION_SEED = 202_408
SIMULATION_DRAWS = 4_000
SIMULATION_SEEDS = tuple(SIMULATION_SEED + 10_000 * index for index in range(8))
SIMULATION_BATCH_SIZE = 128
DEVIATION_TOLERANCE = 0.5
TAIL_CUTOFFS = (0.85, 0.90, 0.95, 0.975, 0.99, 0.995)
TAIL_ATTACHMENT_QUANTILE = 0.99
LEVEL_RATIO_BOUNDS = (0.7, 1.4)
QUANTILE_COLUMNS = (
    "log_abs_deviation_q05",
    "log_abs_deviation_q10",
    "log_abs_deviation_q25",
    "log_abs_deviation_q50",
    "log_abs_deviation_q75",
    "log_abs_deviation_q90",
    "log_abs_deviation_q95",
    "log_abs_deviation_q975",
    "log_abs_deviation_q99",
)


@dataclass(frozen=True)
class TailFit:
    """Training-only diagnostics for the global q99 log-tail extension."""

    scale: float
    scale_se: float
    residual_cutoff: float
    cutoff_quantile: float
    n: int
    effective_n: float
    oof_folds: int
    mean_excess_by_cutoff: tuple[dict[str, float | int], ...]


@dataclass
class DistributionalBundle:
    """Deployable deviation, sign, quantile, and tail components."""

    deviation_stage: ProbabilityStage
    sign_stage: ProbabilityStage
    quantile_models: tuple[HistGradientBoostingRegressor, ...]
    tail: TailFit


@dataclass
class ProcessBundle:
    """Distributional process plus the direct crossing comparator."""

    distributional: DistributionalBundle
    direct_crossing_stage: ProbabilityStage


@dataclass
class DistributionalArtifacts:
    """JSON result and aligned FY2024 predictions for the app exporter."""

    result: dict[str, Any]
    predictions: pd.DataFrame
    bundle: DistributionalBundle
    state_factors: pd.DataFrame
    state_diagnostics: pd.DataFrame
    model_data_payload: dict[str, Any]


def _quantile_regressor(level: float) -> HistGradientBoostingRegressor:
    """Return the native sklearn 1.8 weighted quantile estimator."""
    return HistGradientBoostingRegressor(
        loss="quantile",
        quantile=float(level),
        **MODEL_PARAMS,
    )


def _weighted_quantile(
    values: np.ndarray | pd.Series,
    weights: np.ndarray | pd.Series,
    probability: float,
) -> float:
    """Return a deterministic inverse-CDF weighted quantile."""
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if not 0 <= probability <= 1:
        raise ValueError("weighted quantile probability must be in [0, 1]")
    valid = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not valid.any():
        raise ValueError("weighted quantile has no finite positive-weight rows")
    x = x[valid]
    w = w[valid]
    order = np.argsort(x, kind="mergesort")
    x = x[order]
    cumulative = np.cumsum(w[order])
    index = int(np.searchsorted(cumulative, probability * cumulative[-1], side="left"))
    return float(x[min(index, len(x) - 1)])


def _mean_excess_by_cutoff(
    residual: np.ndarray | pd.Series,
    weights: np.ndarray | pd.Series,
) -> list[dict[str, float | int]]:
    """Return weighted mean-excess diagnostics at fixed residual quantiles."""
    values = np.asarray(residual, dtype=float)
    weight = np.asarray(weights, dtype=float)
    valid = np.isfinite(values) & np.isfinite(weight) & (weight > 0)
    values = values[valid]
    weight = weight[valid]
    if not len(values):
        raise ValueError("mean-excess diagnostics have no positive-weight rows")

    rows: list[dict[str, float | int]] = []
    for probability in TAIL_CUTOFFS:
        cutoff = _weighted_quantile(values, weight, probability)
        selected = values > cutoff
        if not selected.any():
            raise ValueError(
                f"q{100 * probability:g} tail diagnostic has no strict exceedances"
            )
        excess = values[selected] - cutoff
        selected_weight = weight[selected]
        mean_excess = _weighted_mean(excess, selected_weight)
        n_eff = effective_sample_size(selected_weight)
        centered_variance = _weighted_mean(
            np.square(excess - mean_excess), selected_weight
        )
        if n_eff > 1:
            centered_variance *= n_eff / (n_eff - 1)
        standard_error = float(
            np.sqrt(centered_variance / n_eff) if n_eff > 0 else np.nan
        )
        rows.append(
            {
                "cutoff_quantile": float(probability),
                "residual_cutoff_log": cutoff,
                "mean_excess_log": mean_excess,
                "mean_excess_se_log": standard_error,
                "n": int(selected.sum()),
                "effective_n": n_eff,
                "weighted_exceedance_share": float(
                    selected_weight.sum() / weight.sum()
                ),
            }
        )
    return rows


def _fit_tail(
    deviators: pd.DataFrame,
    features: list[str],
) -> TailFit:
    """Fit the q99 log-exponential mean excess from OOF median residuals."""
    target = np.log(deviators["D"].abs()).astype(float)
    folds = min(N_FOLDS, len(deviators))
    if folds < 2:
        raise ValueError("too few deviators for OOF tail fitting")
    cv = KFold(n_splits=folds, shuffle=True, random_state=TAIL_SEED)
    oof_median = _weighted_cross_val_predict(
        _quantile_regressor(0.5),
        deviators[features],
        target,
        deviators["w"],
        cv,
        "predict",
    )
    residual = target.to_numpy(dtype=float) - oof_median
    weights = deviators["w"].to_numpy(dtype=float)
    diagnostics = _mean_excess_by_cutoff(residual, weights)
    selected = next(
        row for row in diagnostics if row["cutoff_quantile"] == TAIL_ATTACHMENT_QUANTILE
    )
    scale = float(selected["mean_excess_log"])
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("log-tail scale must be finite and positive")
    if scale >= MAX_TAIL_SCALE:
        raise ValueError(
            f"log-tail scale must be below {MAX_TAIL_SCALE:.2f}; finite dollar "
            "variance requires scale < 0.5 and the configured regression "
            f"margin is {TAIL_SCALE_MARGIN:.2f}"
        )
    upper_95 = scale + 1.96 * float(selected["mean_excess_se_log"])
    if upper_95 >= 0.5:
        raise ValueError(
            "log-tail scale uncertainty reaches the finite-variance boundary: "
            f"scale + 1.96 * SE = {upper_95:.6f} >= 0.5"
        )
    return TailFit(
        scale=scale,
        scale_se=float(selected["mean_excess_se_log"]),
        residual_cutoff=float(selected["residual_cutoff_log"]),
        cutoff_quantile=TAIL_ATTACHMENT_QUANTILE,
        n=int(selected["n"]),
        effective_n=float(selected["effective_n"]),
        oof_folds=folds,
        mean_excess_by_cutoff=tuple(diagnostics),
    )


def fit_distributional(
    train: pd.DataFrame,
    features: list[str],
) -> DistributionalBundle:
    """Fit deviation, sign, conditional quantiles, and the residual tail."""
    required = set(features) | {"D", "deviates", "w"}
    missing = sorted(required - set(train.columns))
    if missing:
        raise KeyError(f"distributional training frame is missing columns: {missing}")

    deviation_stage = _fit_probability_stage(
        train,
        features,
        "deviates",
        RANDOM_STATE,
    )
    deviators = train.loc[train["deviates"].eq(1)].copy()
    deviators["positive_deviation"] = deviators["D"].gt(0).astype(np.int8)
    sign_stage = _fit_probability_stage(
        deviators,
        features,
        "positive_deviation",
        SIGN_SEED,
    )
    log_magnitude = np.log(deviators["D"].abs()).astype(float)
    models: list[HistGradientBoostingRegressor] = []
    for level in QUANTILE_LEVELS:
        model = _quantile_regressor(float(level))
        model.fit(
            deviators[features],
            log_magnitude,
            sample_weight=deviators["w"],
        )
        models.append(model)
    tail = _fit_tail(deviators, features)
    return DistributionalBundle(
        deviation_stage=deviation_stage,
        sign_stage=sign_stage,
        quantile_models=tuple(models),
        tail=tail,
    )


def fit_process(train: pd.DataFrame, features: list[str]) -> ProcessBundle:
    """Fit the signed distribution and corrected direct crossing comparator."""
    distributional = fit_distributional(train, features)
    deviators = train.loc[train["deviates"].eq(1)]
    direct = _fit_probability_stage(
        deviators,
        features,
        "crosses",
        RANDOM_STATE + 10,
    )
    return ProcessBundle(distributional, direct)


def predict_export_parameters(
    bundle: DistributionalBundle,
    data: pd.DataFrame,
    features: list[str],
) -> pd.DataFrame:
    """Predict the calibrated deviation probability and exported quantiles.

    This is the shared model-primary surface for baseline and policy-scenario
    exports. It deliberately returns only the parameters consumed by the
    browser's absolute-deviation process.
    """
    result = pd.DataFrame(index=data.index)
    result["p_dev"] = bundle.deviation_stage.predict(data[features])
    raw_quantiles = np.column_stack(
        [model.predict(data[features]) for model in bundle.quantile_models]
    )
    quantiles = enforce_monotone_quantiles(
        raw_quantiles,
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    for index, column in enumerate(QUANTILE_COLUMNS):
        result[column] = quantiles[:, index]
    return result


def predict_process(
    bundle: ProcessBundle,
    data: pd.DataFrame,
    features: list[str],
) -> pd.DataFrame:
    """Add aligned component, quantile, and crossing predictions."""
    missing = sorted({"deviation_cap", "thr"} - set(data.columns))
    if missing:
        raise KeyError(f"distributional prediction frame is missing: {missing}")
    result = data.copy()
    distributional = bundle.distributional
    result["p_dev_raw"] = distributional.deviation_stage.predict_raw(result[features])
    export_parameters = predict_export_parameters(
        distributional,
        result,
        features,
    )
    result["p_dev"] = export_parameters["p_dev"]
    result["p_pos_raw"] = distributional.sign_stage.predict_raw(result[features])
    result["p_pos"] = distributional.sign_stage.predict(result[features])
    for column in QUANTILE_COLUMNS:
        result[column] = export_parameters[column]
    quantiles = export_parameters.loc[:, QUANTILE_COLUMNS].to_numpy(dtype=float)
    survival = conditional_survival(
        result["thr"].to_numpy(dtype=float),
        quantiles,
        distributional.tail.scale,
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    result["p_cross_distributional"] = result["p_dev"] * survival
    result["p_cross_direct_conditional"] = bundle.direct_crossing_stage.predict(
        result[features]
    )
    result["p_cross_direct_raw_conditional"] = bundle.direct_crossing_stage.predict_raw(
        result[features]
    )
    result["p_cross_direct"] = result["p_dev"] * result["p_cross_direct_conditional"]
    result["pred_err_dollars_uncapped"] = expected_error_dollars(
        result["p_dev"].to_numpy(dtype=float),
        quantiles,
        distributional.tail.scale,
        result["thr"].to_numpy(dtype=float),
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    result["pred_err_dollars"] = expected_error_dollars(
        result["p_dev"].to_numpy(dtype=float),
        quantiles,
        distributional.tail.scale,
        result["thr"].to_numpy(dtype=float),
        minimum_magnitude=DEVIATION_TOLERANCE,
        magnitude_cap=result["deviation_cap"].to_numpy(dtype=float),
    )
    return result


def weighted_quantile_coverage(
    data: pd.DataFrame,
    quantile_columns: tuple[str, ...] = QUANTILE_COLUMNS,
) -> list[dict[str, float | bool | int]]:
    """Return the nine-cell weighted FY2024 deviator coverage table."""
    deviators = data.loc[data["deviates"].eq(1)]
    if len(quantile_columns) != len(QUANTILE_LEVELS):
        raise ValueError("coverage requires one column per configured quantile")
    missing = sorted(set(quantile_columns) - set(deviators.columns))
    if missing:
        raise KeyError(f"coverage frame is missing quantile columns: {missing}")
    observed = np.log(deviators["D"].abs()).to_numpy(dtype=float)
    weights = deviators["w"].to_numpy(dtype=float)
    rows: list[dict[str, float | bool | int]] = []
    for level, column in zip(QUANTILE_LEVELS, quantile_columns, strict=True):
        predicted = deviators[column].to_numpy(dtype=float)
        coverage = _weighted_mean((observed <= predicted).astype(float), weights)
        gap_pp = 100 * (coverage - float(level))
        rows.append(
            {
                "quantile": float(level),
                "n": len(deviators),
                "effective_n": effective_sample_size(weights),
                "weighted_coverage": coverage,
                "gap_pp": gap_pp,
                "flag_over_3pp": bool(abs(gap_pp) > 3),
            }
        )
    return rows


def _heldout_mean_excess_by_cutoff(
    train: pd.DataFrame,
    predicted: pd.DataFrame,
    features: list[str],
    bundle: DistributionalBundle,
) -> list[dict[str, float | int]]:
    """Evaluate excesses over direct held-out conditional tail quantiles."""
    train_deviators = train.loc[train["deviates"].eq(1)]
    heldout = predicted.loc[predicted["deviates"].eq(1)]
    observed = np.log(heldout["D"].abs()).to_numpy(dtype=float)
    weights = heldout["w"].to_numpy(dtype=float)
    exported_columns = {
        float(level): column
        for level, column in zip(QUANTILE_LEVELS, QUANTILE_COLUMNS, strict=True)
    }
    predicted_by_cutoff: dict[float, np.ndarray] = {}
    source_by_cutoff: dict[float, str] = {}
    for probability in TAIL_CUTOFFS:
        if probability in exported_columns:
            predicted_quantile = heldout[exported_columns[probability]].to_numpy(
                dtype=float
            )
            source = "exported_monotone_quantile"
        else:
            diagnostic_model = _quantile_regressor(probability)
            diagnostic_model.fit(
                train_deviators[features],
                np.log(train_deviators["D"].abs()),
                sample_weight=train_deviators["w"],
            )
            predicted_quantile = diagnostic_model.predict(heldout[features])
            predicted_quantile = np.maximum(
                predicted_quantile, np.log(DEVIATION_TOLERANCE)
            )
            source = "diagnostic_direct_quantile"
        predicted_by_cutoff[probability] = predicted_quantile
        source_by_cutoff[probability] = source

    # Keep the four shipped q90-q99 cutoffs unchanged. Bound the two diagnostic
    # additions to their adjacent shipped cutoffs so q85 and q99.5 are actually
    # ordered within the shipped body/tail grid rather than crossed independent
    # fits.
    q85_raw = predicted_by_cutoff[0.85].copy()
    q995_raw = predicted_by_cutoff[0.995].copy()
    predicted_by_cutoff[0.85] = np.clip(
        q85_raw,
        heldout[exported_columns[0.75]].to_numpy(dtype=float),
        predicted_by_cutoff[0.90],
    )
    predicted_by_cutoff[0.995] = np.maximum(q995_raw, predicted_by_cutoff[0.99])
    source_by_cutoff[0.85] = "diagnostic_direct_quantile_bounded_between_q75_q90"
    source_by_cutoff[0.995] = "diagnostic_direct_quantile_bounded_above_q99"
    adjustment_by_cutoff = {
        0.85: q85_raw != predicted_by_cutoff[0.85],
        0.995: q995_raw != predicted_by_cutoff[0.995],
    }

    conditional_grid = np.column_stack(
        [predicted_by_cutoff[probability] for probability in TAIL_CUTOFFS]
    )
    if (np.diff(conditional_grid, axis=1) < 0).any():
        raise AssertionError("held-out tail diagnostic cutoffs are not monotone")

    rows: list[dict[str, float | int]] = []
    for probability in TAIL_CUTOFFS:
        predicted_quantile = predicted_by_cutoff[probability]
        source = source_by_cutoff[probability]
        excess = observed - predicted_quantile
        selected = excess > 0
        if not selected.any():
            raise ValueError(f"FY2024 q{100 * probability:g} has no strict exceedances")
        selected_excess = excess[selected]
        selected_weight = weights[selected]
        mean_excess = _weighted_mean(selected_excess, selected_weight)
        n_eff = effective_sample_size(selected_weight)
        variance = _weighted_mean(
            np.square(selected_excess - mean_excess), selected_weight
        )
        if n_eff > 1:
            variance *= n_eff / (n_eff - 1)
        row: dict[str, float | int] = {
            "cutoff_quantile": float(probability),
            "mean_excess_log": mean_excess,
            "mean_excess_se_log": float(np.sqrt(variance / n_eff)),
            "n": int(selected.sum()),
            "effective_n": n_eff,
            "weighted_exceedance_share": float(selected_weight.sum() / weights.sum()),
            "prediction_source": source,
        }
        adjusted = adjustment_by_cutoff.get(probability)
        if adjusted is not None:
            row["monotone_adjustment_n"] = int(adjusted.sum())
            row["monotone_adjustment_weighted_share"] = _weighted_mean(
                adjusted.astype(float), weights
            )
        rows.append(row)
    return rows


def _combined_mean_excess_table(
    tail: TailFit,
    heldout: list[dict[str, float | int]],
) -> list[dict[str, Any]]:
    """Align training-residual and held-out conditional diagnostics by cutoff."""
    heldout_by_cutoff = {row["cutoff_quantile"]: row for row in heldout}
    rows: list[dict[str, Any]] = []
    for training in tail.mean_excess_by_cutoff:
        probability = training["cutoff_quantile"]
        test = heldout_by_cutoff[probability]
        rows.append(
            {
                "cutoff_quantile": probability,
                "train_oof_residual_cutoff_log": training["residual_cutoff_log"],
                "train_oof_mean_excess_log": training["mean_excess_log"],
                "train_oof_mean_excess_se_log": training["mean_excess_se_log"],
                "train_oof_n": training["n"],
                "train_oof_effective_n": training["effective_n"],
                "train_oof_weighted_exceedance_share": training[
                    "weighted_exceedance_share"
                ],
                "fy2024_conditional_mean_excess_log": test["mean_excess_log"],
                "fy2024_conditional_mean_excess_se_log": test["mean_excess_se_log"],
                "fy2024_exceedance_n": test["n"],
                "fy2024_exceedance_effective_n": test["effective_n"],
                "fy2024_weighted_exceedance_share": test["weighted_exceedance_share"],
                "fy2024_prediction_source": test["prediction_source"],
                "fy2024_monotone_adjustment_n": test.get("monotone_adjustment_n", 0),
                "fy2024_monotone_adjustment_weighted_share": test.get(
                    "monotone_adjustment_weighted_share", 0.0
                ),
            }
        )
    return rows


def weighted_pit_summary(
    data: pd.DataFrame,
    tail_scale: float,
) -> dict[str, float | int]:
    """Return weighted PIT mean and an effective-n-scaled CvM statistic."""
    deviators = data.loc[data["deviates"].eq(1)]
    weights = deviators["w"].to_numpy(dtype=float)
    quantiles = deviators[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
    observed = deviators["D"].abs().to_numpy(dtype=float)
    pit = 1 - conditional_survival(
        observed,
        quantiles,
        tail_scale,
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    weighted_mean = _weighted_mean(pit, weights)
    n_eff = effective_sample_size(weights)

    order = np.argsort(pit, kind="mergesort")
    ordered_pit = pit[order]
    normalized_weight = weights[order] / weights.sum()
    cumulative_before = 0.0
    previous = 0.0
    integral = 0.0
    for value, probability_weight in zip(ordered_pit, normalized_weight, strict=True):
        integral += (
            (value - cumulative_before) ** 3 - (previous - cumulative_before) ** 3
        ) / 3
        cumulative_before += probability_weight
        previous = float(value)
    integral += ((1 - cumulative_before) ** 3 - (previous - cumulative_before) ** 3) / 3
    null_se = float(np.sqrt(1 / (12 * n_eff)))
    return {
        "n": len(deviators),
        "effective_n": n_eff,
        "weighted_mean": weighted_mean,
        "uniform_target_mean": 0.5,
        "mean_gap": weighted_mean - 0.5,
        "uniform_null_mean_se": null_se,
        "kish_iid_uniform_reference_z": (weighted_mean - 0.5) / null_se,
        "weighted_cvm_integral": integral,
        "effective_n_scaled_cvm": n_eff * integral,
        "reference_note": (
            "The z score and scaled CvM use an iid Uniform(0,1) reference with "
            "Kish effective n. They are descriptive diagnostics, not design-based "
            "tests; they omit QC survey dependence and fitted-CDF uncertainty."
        ),
    }


def _crossing_state_rates(data: pd.DataFrame, prediction: str) -> pd.DataFrame:
    """Aggregate HWGT crossing prevalence for state calibration."""
    required = {"state", "w", "issuance", "crosses", prediction}
    missing = sorted(required - set(data.columns))
    if missing:
        raise KeyError(f"crossing state frame is missing columns: {missing}")
    rows: list[dict[str, float | int | str]] = []
    for state, group in data.groupby("state", sort=True):
        weights = group["w"].to_numpy(dtype=float)
        observed = group["crosses"].to_numpy(dtype=float)
        predicted = group[prediction].to_numpy(dtype=float)
        observed_mean = _weighted_mean(observed, weights)
        predicted_mean = _weighted_mean(predicted, weights)
        if predicted_mean <= 0:
            raise ValueError(f"{state}: crossing prediction mean must be positive")
        ratio = observed_mean / predicted_mean
        n_eff = effective_sample_size(weights)
        contribution = (observed - ratio * predicted) / predicted_mean
        ratio_variance = _weighted_mean(np.square(contribution), weights)
        if n_eff > 1:
            ratio_variance *= n_eff / (n_eff - 1)
        factor_variance = max(
            ratio_variance / max(n_eff, 1),
            1 / max(n_eff, 1) ** 2,
        )
        rows.append(
            {
                "state": str(state),
                "n": len(group),
                "effective_n": n_eff,
                "population_weight_total": float(weights.sum()),
                "issuance_total": float(
                    np.sum(weights * group["issuance"].to_numpy(dtype=float))
                ),
                "pred_rate": 100 * predicted_mean,
                "obs_rate": 100 * observed_mean,
                "observed_to_predicted_ratio": ratio,
                "factor_sampling_variance": factor_variance,
            }
        )
    return pd.DataFrame(rows).sort_values("state").reset_index(drop=True)


def _factor_adjusted_rates(
    rates: pd.DataFrame,
    factors: pd.DataFrame,
) -> pd.DataFrame:
    """Multiply state aggregate prevalence by its frozen route factor."""
    factor_map = factors.set_index("state")["state_factor"]
    result = rates.copy()
    result["applied_state_factor"] = result["state"].map(factor_map)
    if result["applied_state_factor"].isna().any():
        missing = sorted(
            result.loc[result["applied_state_factor"].isna(), "state"].unique()
        )
        raise ValueError(f"missing crossing factors for states: {missing}")
    result["pred_rate"] *= result["applied_state_factor"]
    if (result["pred_rate"] > 100).any():
        raise ValueError("factor-adjusted state crossing prevalence exceeds 100%")
    result["observed_to_predicted_ratio"] = result["obs_rate"] / result["pred_rate"]
    return result


def _national_prevalence(data: pd.DataFrame, column: str) -> float:
    return 100 * _weighted_mean(data[column], data["w"].to_numpy(dtype=float))


def _national_from_state_rates(rates: pd.DataFrame) -> float:
    return _weighted_mean(
        rates["pred_rate"],
        rates["population_weight_total"].to_numpy(dtype=float),
    )


def _comparison_row(
    route: str,
    specification: str,
    rates: pd.DataFrame,
    national_prevalence: float,
) -> dict[str, Any]:
    calibration = _calibration_summary(rates)
    return {
        "route": route,
        "specification": specification,
        "national_predicted_prevalence_pct": national_prevalence,
        "equal_state_mae_pp": calibration["equal_jurisdiction"]["mae_pp"],
        "issuance_weighted_mae_pp": calibration["issuance_weighted"]["mae_pp"],
        "calibration": calibration,
    }


def _route_factor_validation(
    frozen_2023: pd.DataFrame,
    frozen_2024: pd.DataFrame,
    prediction: str,
    route: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fit_rates = _crossing_state_rates(frozen_2023, prediction)
    factors, shrinkage = _shrink_state_factors(fit_rates)
    raw_rates = _crossing_state_rates(frozen_2024, prediction)
    adjusted_rates = _factor_adjusted_rates(raw_rates, factors)
    rows = [
        _comparison_row(
            route,
            "frozen model through FY2022, unfactored",
            raw_rates,
            _national_prevalence(frozen_2024, prediction),
        ),
        _comparison_row(
            route,
            "frozen model through FY2022, FY2023-fit factor adjusted",
            adjusted_rates,
            _national_from_state_rates(adjusted_rates),
        ),
    ]
    details = {
        "factor_fit_year": 2023,
        "validation_year": 2024,
        "model_training_years": [year for year in YEARS_TRAIN if year < 2023],
        "shrinkage": shrinkage,
        "fy2023_unfactored": _calibration_summary(fit_rates),
        "factors": factors.to_dict("records"),
        "fy2024_unfactored_states": raw_rates.to_dict("records"),
        "fy2024_factor_adjusted_states": adjusted_rates.to_dict("records"),
    }
    return rows, details


def _dollar_factor_validation(
    frozen_2023: pd.DataFrame,
    frozen_2024: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Fit FY2023 dollar factors and validate the matched frozen FY2024 pair."""
    fit_rates = _state_rates(frozen_2023)
    factors, shrinkage = _shrink_state_factors(fit_rates)
    raw_rates = _state_rates(frozen_2024)
    adjusted_data = _apply_state_factors(frozen_2024, factors)
    adjusted_rates = _state_rates(adjusted_data)
    states = set(raw_rates["state"])
    if len(states) != 53 or states != set(adjusted_rates["state"]):
        raise ValueError(
            "dollar-factor validation requires the same 53 FY2024 jurisdictions"
        )

    factor_columns = factors[["state", "state_factor"]]
    adjusted_columns = adjusted_rates[["state", "pred_rate"]].rename(
        columns={"pred_rate": "adjusted_pred_rate"}
    )
    combined = raw_rates.merge(factor_columns, on="state", validate="one_to_one").merge(
        adjusted_columns, on="state", validate="one_to_one"
    )
    if (combined["obs_rate"] <= 0).any():
        states_without_observed_dollars = sorted(
            combined.loc[combined["obs_rate"] <= 0, "state"]
        )
        raise ValueError(
            "model/observed dollar ratios require positive observed rates: "
            f"{states_without_observed_dollars}"
        )
    combined["raw_model_to_observed_ratio"] = (
        combined["pred_rate"] / combined["obs_rate"]
    )
    combined["adjusted_model_to_observed_ratio"] = (
        combined["adjusted_pred_rate"] / combined["obs_rate"]
    )
    lower, upper = LEVEL_RATIO_BOUNDS
    combined["adjusted_ratio_outside_0_7_to_1_4"] = ~combined[
        "adjusted_model_to_observed_ratio"
    ].between(lower, upper, inclusive="both")
    combined = combined.sort_values("state").reset_index(drop=True)

    state_rows = [
        {
            "state": str(row.state),
            "n": int(row.n),
            "effective_n": float(row.effective_n),
            "issuance_total": float(row.issuance_total),
            "observed_dollar_rate_pct": float(row.obs_rate),
            "analytic_raw_dollar_rate_pct": float(row.pred_rate),
            "state_factor": float(row.state_factor),
            "analytic_factor_adjusted_dollar_rate_pct": float(row.adjusted_pred_rate),
            "raw_model_to_observed_ratio": float(row.raw_model_to_observed_ratio),
            "adjusted_model_to_observed_ratio": float(
                row.adjusted_model_to_observed_ratio
            ),
            "adjusted_ratio_outside_0_7_to_1_4": bool(
                row.adjusted_ratio_outside_0_7_to_1_4
            ),
        }
        for row in combined.itertuples(index=False)
    ]
    raw_level_gap = [
        {
            "state": row["state"],
            "observed_dollar_rate_pct": row["observed_dollar_rate_pct"],
            "analytic_raw_dollar_rate_pct": row["analytic_raw_dollar_rate_pct"],
            "raw_model_to_observed_ratio": row["raw_model_to_observed_ratio"],
        }
        for row in state_rows
    ]
    raw_summary = _calibration_summary(raw_rates)
    adjusted_summary = _calibration_summary(adjusted_rates)
    issuance_weights = raw_rates["issuance_total"].to_numpy(dtype=float)
    national_observed = _weighted_mean(raw_rates["obs_rate"], issuance_weights)
    national_raw = _weighted_mean(raw_rates["pred_rate"], issuance_weights)
    national_adjusted = _weighted_mean(adjusted_rates["pred_rate"], issuance_weights)
    result = {
        "route": "capped distributional expected error dollars",
        "model_training_years": [year for year in YEARS_TRAIN if year < 2023],
        "factor_fit_year": 2023,
        "validation_year": 2024,
        "matched_model_pair": True,
        "factor_application": (
            "multiply physically capped, strictly thresholded per-case error "
            "dollars; the factor does not alter the latent signed D draw"
        ),
        "shrinkage": {
            **shrinkage,
            "prior_mean_choice": (
                "fixed at 1 so noisy states shrink toward no multiplicative "
                "adjustment rather than toward a data-estimated level"
            ),
            "factor_uncertainty_propagated": False,
        },
        "fy2023_factor_fit_states": factors.to_dict("records"),
        "metrics": {
            "raw_frozen_model": raw_summary,
            "factor_adjusted_frozen_model": adjusted_summary,
        },
        "national_dollar_rates_pct": {
            "observed": national_observed,
            "analytic_raw": national_raw,
            "analytic_factor_adjusted": national_adjusted,
        },
        "level_ratio_gate": {
            "inclusive_bounds": [lower, upper],
            "ratio": "factor-adjusted analytic model / observed FY2024 sample",
            "flagged_state_count": int(
                combined["adjusted_ratio_outside_0_7_to_1_4"].sum()
            ),
            "flagged_states": combined.loc[
                combined["adjusted_ratio_outside_0_7_to_1_4"], "state"
            ].tolist(),
        },
        "states": state_rows,
        "raw_level_gap_table": raw_level_gap,
    }
    diagnostics = combined[
        [
            "state",
            "state_factor",
            "raw_model_to_observed_ratio",
            "adjusted_model_to_observed_ratio",
            "adjusted_ratio_outside_0_7_to_1_4",
        ]
    ].copy()
    return result, factors, diagnostics


def _physical_cap_diagnostics(
    predicted: pd.DataFrame,
    tail_scale: float,
    factors: pd.DataFrame,
) -> dict[str, Any]:
    """Quantify probability and expected-dollar mass winsorized by the cap."""
    weights = predicted["w"].to_numpy(dtype=float)
    p_dev = predicted["p_dev"].to_numpy(dtype=float)
    cap = predicted["deviation_cap"].to_numpy(dtype=float)
    quantiles = predicted[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
    probability_clipped = p_dev * conditional_survival(
        cap,
        quantiles,
        tail_scale,
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    uncapped = predicted["pred_err_dollars_uncapped"].to_numpy(dtype=float)
    capped = predicted["pred_err_dollars"].to_numpy(dtype=float)
    factor_map = factors.set_index("state")["state_factor"]
    factor = predicted["state"].map(factor_map).to_numpy(dtype=float)
    if not np.isfinite(factor).all() or (factor <= 0).any():
        raise ValueError("cap diagnostics require finite positive state factors")
    issuance_total = float(
        np.sum(weights * predicted["issuance"].to_numpy(dtype=float))
    )
    expected_deviation_probability = _weighted_mean(p_dev, weights)

    def dollar_summary(multiplier: np.ndarray) -> dict[str, float]:
        uncapped_total = float(np.sum(weights * multiplier * uncapped))
        capped_total = float(np.sum(weights * multiplier * capped))
        removed = uncapped_total - capped_total
        return {
            "uncapped_expected_error_dollars_total": uncapped_total,
            "capped_expected_error_dollars_total": capped_total,
            "expected_error_dollars_removed": removed,
            "expected_error_dollars_removed_fraction": removed / uncapped_total,
            "uncapped_expected_dollar_rate_pct": (
                100 * uncapped_total / issuance_total
            ),
            "capped_expected_dollar_rate_pct": 100 * capped_total / issuance_total,
            "expected_dollar_rate_reduction_pp": 100 * removed / issuance_total,
        }

    return {
        "rule": "max(BENMAX, abs(RAWBEN - BENFIX)) per case-year",
        "source_field": "BENMAX (maximum benefit amount)",
        "derivation": (
            "BENMAX supplies the case's maximum-monthly-allotment-scale ceiling; "
            "taking the maximum with observed abs(D) preserves the realized "
            "support for records whose adjudicated deviation exceeds BENMAX"
        ),
        "units": "dollars",
        "application": (
            "clip the final absolute D draw before the strict fiscal-year "
            "threshold; apply the state dollar factor after thresholding"
        ),
        "fy2024_cap_min": float(cap.min()),
        "fy2024_cap_max": float(cap.max()),
        "cases_with_observed_abs_D_above_BENMAX": int(
            (predicted["D"].abs() > predicted["benmax"]).sum()
        ),
        "cases_with_predicted_q99_above_cap": int(
            (np.exp(quantiles[:, -1]) > cap).sum()
        ),
        "weighted_unconditional_draw_probability_clipped": _weighted_mean(
            probability_clipped, weights
        ),
        "weighted_probability_clipped_conditional_on_expected_deviation": (
            _weighted_mean(probability_clipped, weights)
            / expected_deviation_probability
        ),
        "unfactored_frozen_model": dollar_summary(np.ones(len(predicted))),
        "factor_adjusted_frozen_model": dollar_summary(factor),
    }


def _load_app_metadata(path: Path = APP_METADATA) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict) or not isinstance(payload.get("states"), dict):
        raise TypeError("app data metadata must contain a states object")
    return payload


def _observed_bootstrap(
    group: pd.DataFrame,
    official_rate: float,
    seed: int,
) -> np.ndarray:
    cases = [
        QcCase(
            weight=float(row.w),
            issuance=float(row.issuance),
            error=float(row.obs_error_dollars),
            elements=frozenset(),
        )
        for row in group[["w", "issuance", "obs_error_dollars"]].itertuples(index=False)
    ]
    rates = simulate(
        cases,
        official_rate,
        draws=SIMULATION_DRAWS,
        rng=np.random.default_rng(seed),
    )
    return np.maximum(rates, 0.0)


def _model_bootstrap_draws(
    group: pd.DataFrame,
    tail_scale: float,
    state_factor: float,
    seed: int,
) -> np.ndarray:
    """Mirror the shipped case-bootstrap plus per-occurrence redraw process."""
    weights = group["w"].to_numpy(dtype=float)
    issuance = group["issuance"].to_numpy(dtype=float)
    p_dev = group["p_dev"].to_numpy(dtype=float)
    quantiles = group[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
    cap = group["deviation_cap"].to_numpy(dtype=float)
    if not np.isfinite(state_factor) or state_factor <= 0:
        raise ValueError("simulation state_factor must be finite and positive")

    rng = np.random.default_rng(seed)
    rates = np.empty(SIMULATION_DRAWS, dtype=float)
    n = len(group)
    weighted_issuance = weights * issuance
    minimum_log = float(np.log(DEVIATION_TOLERANCE))
    q99 = float(QUANTILE_LEVELS[-1])
    for start in range(0, SIMULATION_DRAWS, SIMULATION_BATCH_SIZE):
        stop = min(start + SIMULATION_BATCH_SIZE, SIMULATION_DRAWS)
        batch = stop - start
        indices = rng.integers(0, n, size=(batch, n))
        deviates = rng.random(size=(batch, n)) < p_dev[indices]
        uniform = rng.random(size=(batch, n))
        interval = np.searchsorted(QUANTILE_LEVELS, uniform, side="right")
        flat_indices = indices.reshape(-1)
        flat_interval = interval.reshape(-1)
        flat_uniform = uniform.reshape(-1)
        log_magnitude = np.empty(flat_uniform.shape, dtype=float)

        body = flat_interval < len(QUANTILE_LEVELS)
        if np.any(body):
            rows = np.flatnonzero(body)
            right_index = flat_interval[rows]
            left_index = np.maximum(right_index - 1, 0)
            left_level = np.where(right_index == 0, 0.0, QUANTILE_LEVELS[left_index])
            right_level = QUANTILE_LEVELS[right_index]
            left_log = quantiles[flat_indices[rows], left_index]
            left_log = np.where(right_index == 0, minimum_log, left_log)
            right_log = quantiles[flat_indices[rows], right_index]
            fraction = (flat_uniform[rows] - left_level) / (right_level - left_level)
            log_magnitude[rows] = left_log + fraction * (right_log - left_log)

        in_tail = ~body
        if np.any(in_tail):
            rows = np.flatnonzero(in_tail)
            relative_survival = (1 - flat_uniform[rows]) / (1 - q99)
            log_magnitude[rows] = quantiles[
                flat_indices[rows], -1
            ] - tail_scale * np.log(relative_survival)

        selected_cap = cap[indices]
        magnitude = np.exp(
            np.minimum(log_magnitude.reshape(batch, n), np.log(selected_cap))
        )
        error = np.where(
            deviates & (magnitude > THRESHOLD[YEAR_TEST]),
            state_factor * magnitude,
            0.0,
        )
        numerator = np.sum(weights[indices] * error, axis=1)
        denominator = np.sum(weighted_issuance[indices], axis=1)
        if np.any(denominator <= 0):
            raise ValueError("bootstrap issuance denominator must be positive")
        rates[start:stop] = 100 * numerator / denominator
    return rates


def _tier_probabilities(rates: np.ndarray) -> dict[str, float]:
    shares = np.select(
        [rates < 6, rates < 8, rates < 10],
        [0, 5, 10],
        default=15,
    )
    return {str(tier): float(np.mean(shares == tier)) for tier in (0, 5, 10, 15)}


def _seed_statistics(rates: np.ndarray) -> dict[str, Any]:
    return {
        "mean_pct": float(rates.mean()),
        "sd_pp": float(rates.std()),
        "tier_probabilities": _tier_probabilities(rates),
    }


def _mean_and_mc_se(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "estimate": float(array.mean()),
        "mc_se": float(array.std(ddof=1) / np.sqrt(len(array))),
    }


def _aggregate_seed_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mean = _mean_and_mc_se([float(row["mean_pct"]) for row in rows])
    sd = _mean_and_mc_se([float(row["sd_pp"]) for row in rows])
    tiers = {
        tier: _mean_and_mc_se([float(row["tier_probabilities"][tier]) for row in rows])
        for tier in ("0", "5", "10", "15")
    }
    return {
        "mean_pct": mean["estimate"],
        "mean_mc_se_pp": mean["mc_se"],
        "sd_pp": sd["estimate"],
        "sd_mc_se_pp": sd["mc_se"],
        "tier_probabilities": {
            tier: {
                "probability": values["estimate"],
                "mc_se": values["mc_se"],
            }
            for tier, values in tiers.items()
        },
    }


def _encoded_model_group(state: str, payload: dict[str, Any]) -> pd.DataFrame:
    """Reconstruct one state's model inputs from the serialized export payload."""
    required = {"n", "w", "iss", "p_dev", "cap", "q", "factor", "official"}
    missing = sorted(required - set(payload))
    if missing:
        raise KeyError(f"encoded model state {state} is missing: {missing}")
    n = int(payload["n"])
    arrays = {
        "w": np.asarray(payload["w"], dtype=float),
        "issuance": np.asarray(payload["iss"], dtype=float),
        "p_dev": np.asarray(payload["p_dev"], dtype=float),
        "deviation_cap": np.asarray(payload["cap"], dtype=float),
    }
    quantiles = np.asarray(payload["q"], dtype=float)
    if quantiles.shape != (n, len(QUANTILE_COLUMNS)):
        raise ValueError(
            f"encoded model state {state} has q shape {quantiles.shape}, "
            f"expected {(n, len(QUANTILE_COLUMNS))}"
        )
    if any(values.shape != (n,) for values in arrays.values()):
        raise ValueError(f"encoded model state {state} has unequal array lengths")
    if not all(np.isfinite(values).all() for values in (*arrays.values(), quantiles)):
        raise ValueError(f"encoded model state {state} contains nonfinite values")
    frame = pd.DataFrame(arrays)
    for index, column in enumerate(QUANTILE_COLUMNS):
        frame[column] = quantiles[:, index]
    return frame


def _simulation_validation(
    predicted_2024: pd.DataFrame,
    model_payload: dict[str, Any],
) -> dict[str, Any]:
    if model_payload.get("schema_version") != 2:
        raise ValueError("shipped simulation validation requires export schema 2")
    levels = np.asarray(model_payload.get("quantile_levels"), dtype=float)
    if levels.shape != QUANTILE_LEVELS.shape or not np.array_equal(
        levels, QUANTILE_LEVELS
    ):
        raise ValueError("encoded quantile levels do not match the fitted process")
    tail_scale = float(model_payload["tail_scale_log"])
    encoded_states = model_payload.get("states")
    if not isinstance(encoded_states, dict):
        raise TypeError("encoded model payload must contain a states object")
    states = sorted(predicted_2024["state"].unique())
    if len(states) != 53 or set(states) != set(encoded_states):
        raise ValueError("shipped simulation validation requires 53 jurisdictions")
    rows: list[dict[str, Any]] = []
    for state in states:
        observed_group = predicted_2024.loc[predicted_2024["state"].eq(state)]
        encoded_state = encoded_states[state]
        model_group = _encoded_model_group(state, encoded_state)
        if len(model_group) != len(observed_group):
            raise ValueError(
                f"encoded and observed FY2024 row counts differ for {state}"
            )
        official = float(encoded_state["official"])
        state_factor = float(encoded_state["factor"])
        model_seed_rows: list[dict[str, Any]] = []
        observed_seed_rows: list[dict[str, Any]] = []
        for seed in SIMULATION_SEEDS:
            raw_model = _model_bootstrap_draws(
                model_group,
                tail_scale,
                state_factor,
                seed,
            )
            model_shift = official - float(raw_model.mean())
            model_seed_rows.append(
                _seed_statistics(np.maximum(raw_model + model_shift, 0.0))
            )
            observed_seed_rows.append(
                _seed_statistics(
                    _observed_bootstrap(observed_group, official, seed + 1)
                )
            )
        rows.append(
            {
                "state": state,
                "n": len(model_group),
                "official_rate_pct": official,
                "state_factor": state_factor,
                "raw_model_to_observed_ratio": float(encoded_state["raw_level_ratio"]),
                "adjusted_model_to_observed_ratio": float(encoded_state["level_ratio"]),
                "adjusted_ratio_outside_0_7_to_1_4": bool(encoded_state["level_flag"]),
                "model": _aggregate_seed_statistics(model_seed_rows),
                "observed_bootstrap": _aggregate_seed_statistics(observed_seed_rows),
            }
        )
    return {
        "draws_per_seed": SIMULATION_DRAWS,
        "seed_count": len(SIMULATION_SEEDS),
        "seeds": list(SIMULATION_SEEDS),
        "total_draws_per_state": SIMULATION_DRAWS * len(SIMULATION_SEEDS),
        "state_count": len(states),
        "states": states,
        "model_input": {
            "source": "serialized model_data payload",
            "schema_version": int(model_payload["schema_version"]),
            "q_encoding": model_payload["q_encoding"],
            "uses_encoded_arrays_and_state_factors": True,
        },
        "model_process": (
            "read the serialized model_data arrays and scalar state factor; "
            "uniform CASE==1 row bootstrap; retain sampled HWGT in numerator and "
            "issuance denominator; redraw deviation occurrence and magnitude per "
            "sampled occurrence; cap |D|; apply the frozen state factor after the "
            "strict threshold; anchor each seed at its own model baseline mean"
        ),
        "observed_process": (
            "uniform corrected-error row bootstrap retaining HWGT inside the "
            "ratio and centered at the official rate"
        ),
        "downstream_rate_floor_pct": 0.0,
        "sd_estimands": {
            "model": "case-composition plus conditional error-process variation",
            "observed_bootstrap": "case-composition variation in observed errors",
        },
        "mc_error_method": (
            "standard error across independent seed-specific estimates: sample "
            "SD divided by sqrt(seed count)"
        ),
        "rows": rows,
    }


def _provenance(tail: TailFit, training_years: list[int]) -> dict[str, Any]:
    provenance = hurdle_provenance()
    with APP_METADATA.open("rb") as source:
        provenance["input_sha256"]["app/public/data.json"] = hashlib.file_digest(
            source, "sha256"
        ).hexdigest()
    provenance.update(
        {
            "package_versions": _package_versions(),
            "distributional_training_years": training_years,
            "distributional_validation_year": YEAR_TEST,
            "quantile_levels": QUANTILE_LEVELS.tolist(),
            "quantile_estimator": (
                "sklearn HistGradientBoostingRegressor with native quantile loss"
            ),
            "sign_seed": SIGN_SEED,
            "tail_seed": TAIL_SEED,
            "simulation_seeds": list(SIMULATION_SEEDS),
            "simulation_draws_per_seed": SIMULATION_DRAWS,
            "physical_cap_rule": ("max(BENMAX, abs(RAWBEN - BENFIX)) per case-year"),
            "tail": {
                "scale_log": tail.scale,
                "scale_se_log": tail.scale_se,
                "implied_pareto_tail_index": 1 / tail.scale,
                "residual_cutoff_log": tail.residual_cutoff,
                "fit_residual_cutoff_quantile": tail.cutoff_quantile,
                "fit_n": tail.n,
                "fit_effective_n": tail.effective_n,
                "oof_folds": tail.oof_folds,
                "method": (
                    "weighted mean exponential excess on log-magnitude beyond "
                    "q99 of OOF median residuals; attached above conditional q99"
                ),
                "finite_variance_gate": (
                    f"point scale < {MAX_TAIL_SCALE:.2f} and scale + 1.96 * "
                    "empirical weighted SE < 0.5"
                ),
            },
        }
    )
    return provenance


def analyze() -> DistributionalArtifacts:
    """Fit all distributional components and return deterministic artifacts."""
    data = assemble()
    data["case"] = 1
    features = _feature_columns(data)
    primary_train = data.loc[data["year"].isin(YEARS_TRAIN)]
    fy2024 = data.loc[data["year"].eq(YEAR_TEST)].copy()

    print("fitting primary signed distribution through FY2023")
    primary = fit_process(primary_train, features)
    primary_2024 = predict_process(primary, fy2024, features)

    comparison_rows: list[dict[str, Any]] = []
    for route, column in (
        ("direct stage-2", "p_cross_direct"),
        ("distributional implied crossing", "p_cross_distributional"),
    ):
        rates = _crossing_state_rates(primary_2024, column)
        comparison_rows.append(
            _comparison_row(
                route,
                "primary model through FY2023, unfactored",
                rates,
                _national_prevalence(primary_2024, column),
            )
        )

    print("fitting frozen signed distribution through FY2022")
    factor_years = [year for year in YEARS_TRAIN if year < 2023]
    frozen_train = data.loc[data["year"].isin(factor_years)]
    frozen = fit_process(frozen_train, features)
    frozen_2023 = predict_process(
        frozen,
        data.loc[data["year"].eq(2023)].copy(),
        features,
    )
    frozen_2024 = predict_process(frozen, fy2024, features)
    for route, column in (
        ("direct stage-2", "p_cross_direct"),
        ("distributional implied crossing", "p_cross_distributional"),
    ):
        rates = _crossing_state_rates(frozen_2024, column)
        comparison_rows.append(
            _comparison_row(
                route,
                "frozen model through FY2022, unfactored",
                rates,
                _national_prevalence(frozen_2024, column),
            )
        )

    dollar_validation, factors, state_diagnostics = _dollar_factor_validation(
        frozen_2023, frozen_2024
    )
    coverage = weighted_quantile_coverage(frozen_2024)
    coverage_gaps = np.asarray([row["gap_pp"] for row in coverage], dtype=float)
    pit = weighted_pit_summary(frozen_2024, frozen.distributional.tail.scale)
    heldout_mean_excess = _heldout_mean_excess_by_cutoff(
        frozen_train,
        frozen_2024,
        features,
        frozen.distributional,
    )
    mean_excess_table = _combined_mean_excess_table(
        frozen.distributional.tail, heldout_mean_excess
    )
    cap_diagnostics = _physical_cap_diagnostics(
        frozen_2024, frozen.distributional.tail.scale, factors
    )
    deviators_2024 = frozen_2024.loc[frozen_2024["deviates"].eq(1)].copy()
    deviators_2024["positive_deviation"] = deviators_2024["D"].gt(0).astype(np.int8)
    sign_2024 = _evaluate_probability_stage(
        frozen.distributional.sign_stage,
        deviators_2024,
        features,
        "positive_deviation",
    )

    official_prevalence = _national_prevalence(frozen_2024, "crosses")
    literal_crossing = 100 * _weighted_mean(
        (frozen_2024["D"].abs().to_numpy(dtype=float) > THRESHOLD[YEAR_TEST]).astype(
            float
        ),
        frozen_2024["w"].to_numpy(dtype=float),
    )
    discordant = frozen_2024["crosses"].ne(
        frozen_2024["D"].abs().gt(THRESHOLD[YEAR_TEST])
    )
    export_report = scripts_build_model_data.prepare_model_data(
        frozen_2024,
        tail_scale=frozen.distributional.tail.scale,
        tail_scale_se=frozen.distributional.tail.scale_se,
        state_factors=factors,
        state_diagnostics=state_diagnostics,
        metadata_path=APP_METADATA,
        threshold=THRESHOLD[YEAR_TEST],
        deviation_tolerance=DEVIATION_TOLERANCE,
        quantile_levels=QUANTILE_LEVELS,
        quantile_columns=QUANTILE_COLUMNS,
    )
    model_data_payload = export_report["data"]
    simulation = _simulation_validation(frozen_2024, model_data_payload)

    primary_rows = {
        row["route"]: row
        for row in comparison_rows
        if row["specification"] == "primary model through FY2023, unfactored"
    }
    direct_primary = primary_rows["direct stage-2"]
    distributional_primary = primary_rows["distributional implied crossing"]
    differences_by_specification: dict[str, dict[str, float]] = {}
    for specification in dict.fromkeys(
        str(row["specification"]) for row in comparison_rows
    ):
        route_rows = {
            str(row["route"]): row
            for row in comparison_rows
            if row["specification"] == specification
        }
        direct = route_rows["direct stage-2"]
        distributional = route_rows["distributional implied crossing"]
        differences_by_specification[specification] = {
            "equal_state": (
                distributional["equal_state_mae_pp"] - direct["equal_state_mae_pp"]
            ),
            "issuance_weighted": (
                distributional["issuance_weighted_mae_pp"]
                - direct["issuance_weighted_mae_pp"]
            ),
        }
    tail = frozen.distributional.tail
    upper_95 = tail.scale + 1.96 * tail.scale_se
    result: dict[str, Any] = {
        "schema_version": 2,
        "definitions": {
            "prediction_scope": (
                "the shipped distributional model is frozen after FY2017-19 and "
                "FY2022; FY2023 fits state dollar factors and FY2024 validates "
                "the frozen configuration; no causal interpretation"
            ),
            "signed_deviation_D": "RAWBEN - BENFIX",
            "deviates": "abs(D) > 0.5 dollars",
            "positive_sign": "D > 0 among deviators",
            "quantile_target": "log(abs(D)) among deviators",
            "conditional_independence": (
                "sign and magnitude draws are conditionally independent given features"
            ),
            "tail": (
                "log-scale exponential excess beyond conditional q99, with scale "
                "fit as the weighted mean excess beyond q99 of OOF median residuals"
            ),
            "physical_cap": (
                "abs(D) is winsorized at max(BENMAX, observed abs(D)) for each "
                "case-year before thresholding"
            ),
            "state_factor": (
                "FY2023 out-of-sample empirical-Bayes scalar applied after the "
                "strict threshold to capped error dollars"
            ),
            "crossing": (
                "error dollars equal abs(D) only when abs(D) is strictly greater "
                "than the fiscal-year threshold"
            ),
            "anchored_rate_floor": (
                "official-anchored model and observed-bootstrap rate draws are "
                "clipped at zero by downstream validation/presentation consumers"
            ),
        },
        "provenance": _provenance(tail, factor_years),
        "features": features,
        "quantile_levels": QUANTILE_LEVELS.tolist(),
        "quantile_columns": list(QUANTILE_COLUMNS),
        "sign": {
            "training_oof_cross_fitted": (frozen.distributional.sign_stage.oof_metrics),
            "fy2024_among_deviators": sign_2024,
            "exported": False,
            "export_note": (
                "p_pos is retained for sign analysis but omitted from model_data.json "
                "because measured error-rate outputs consume only abs(D)"
            ),
        },
        "magnitude_distribution": {
            "training_deviators_n": int(frozen_train["deviates"].sum()),
            "fy2024_deviators_n": int(frozen_2024["deviates"].sum()),
            "tail_fit": {
                "family": "exponential log excess",
                "attachment_quantile": TAIL_ATTACHMENT_QUANTILE,
                "fit_residual_cutoff_quantile": tail.cutoff_quantile,
                "scale_log": tail.scale,
                "scale_se_log": tail.scale_se,
                "scale_se_method": (
                    "empirical weighted mean-excess SE using Kish effective n; "
                    "conditional on the estimated threshold and OOF predictions"
                ),
                "implied_pareto_tail_index": 1 / tail.scale,
                "residual_cutoff_log": tail.residual_cutoff,
                "n": tail.n,
                "effective_n": tail.effective_n,
                "oof_folds": tail.oof_folds,
                "finite_variance_gate": {
                    "point_scale_upper_bound_exclusive": MAX_TAIL_SCALE,
                    "mathematical_limit_exclusive": 0.5,
                    "fixed_regression_margin": TAIL_SCALE_MARGIN,
                    "upper_95_log_scale": upper_95,
                    "uncertainty_margin_to_limit": 0.5 - upper_95,
                    "passed": bool(tail.scale < MAX_TAIL_SCALE and upper_95 < 0.5),
                },
                "mean_excess_by_cutoff": mean_excess_table,
                "threshold_stability_note": (
                    "Training OOF mean excess declines through q97.5 and "
                    "stabilizes at q99-q99.5. q99 matches the attachment depth "
                    "while retaining more effective sample than q99.5. The "
                    "FY2024 diagnostic q85 is bounded between the adjacent shipped "
                    "q75 and q90 cutoffs, and q99.5 is bounded above q99, so the "
                    "diagnostic thresholds remain ordered with the shipped grid; "
                    "conditional excess is lower at both deepest cutoffs."
                ),
            },
            "physical_cap": cap_diagnostics,
            "fy2024_weighted_coverage": coverage,
            "coverage_flags_over_3pp": int(
                sum(bool(row["flag_over_3pp"]) for row in coverage)
            ),
            "coverage_signed_gap_pattern": {
                "negative_gap_count": int((coverage_gaps < 0).sum()),
                "positive_gap_count": int((coverage_gaps > 0).sum()),
                "all_nine_negative": bool((coverage_gaps < 0).all()),
                "interpretation": (
                    "negative gaps are undercoverage: observed FY2024 magnitudes "
                    "stochastically exceed the fitted quantiles"
                ),
            },
            "fy2024_weighted_pit": pit,
        },
        "crossing_validation": {
            "observed_official_national_prevalence_pct": official_prevalence,
            "observed_literal_D_crossing_national_prevalence_pct": literal_crossing,
            "official_vs_literal_discordant_n": int(discordant.sum()),
            "official_vs_literal_discordance_weighted_pp": (
                100
                * _weighted_mean(
                    discordant.astype(float),
                    frozen_2024["w"].to_numpy(dtype=float),
                )
            ),
            "comparison_rows": comparison_rows,
            "distributional_minus_direct_mae_pp_by_specification": (
                differences_by_specification
            ),
            "primary_distributional_minus_direct_mae_pp": {
                "equal_state": (
                    distributional_primary["equal_state_mae_pp"]
                    - direct_primary["equal_state_mae_pp"]
                ),
                "issuance_weighted": (
                    distributional_primary["issuance_weighted_mae_pp"]
                    - direct_primary["issuance_weighted_mae_pp"]
                ),
            },
        },
        "dollar_rate_validation": dollar_validation,
        "measured_rate_simulation": simulation,
        "export": {
            "case_filter": "CASE == 1",
            "configuration": (
                "frozen-through-FY2022 distributional predictions, FY2023-fit "
                "dollar factors, per-case physical caps"
            ),
            "fy2024_cases": len(frozen_2024),
            "state_count": int(frozen_2024["state"].nunique()),
            "quantiles_are_log_dollars": True,
            "p_pos_exported": False,
            "model_data_raw_bytes": export_report["raw_bytes"],
            "model_data_gzip_bytes": export_report["gzip_bytes"],
            "q_decimal_quantization": export_report["q_decimal_quantization"],
            "browser_consumer_status": (
                "model mode remains disabled; model_data contains factor/cap/gate "
                "metadata and run_all pairs it with the SMD-only model_scenarios "
                "export, but app.js is unchanged"
            ),
        },
    }
    return DistributionalArtifacts(
        result=result,
        predictions=frozen_2024,
        bundle=frozen.distributional,
        state_factors=factors[["state", "state_factor"]].copy(),
        state_diagnostics=state_diagnostics,
        model_data_payload=model_data_payload,
    )


def _write_result(result: dict[str, Any], output_path: str | Path) -> None:
    destination = Path(output_path)
    with destination.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def main(output_path: str | Path = OUT) -> DistributionalArtifacts:
    """Run the analysis, write its JSON, and retain predictions for export."""
    artifacts = analyze()
    _write_result(artifacts.result, output_path)
    print(f"wrote {output_path}")
    return artifacts


def predictions_for_export() -> tuple[
    pd.DataFrame,
    TailFit,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Return the matched frozen predictions and metadata used by the export."""
    artifacts = analyze()
    return (
        artifacts.predictions,
        artifacts.bundle.tail,
        artifacts.state_factors,
        artifacts.state_diagnostics,
    )


if __name__ == "__main__":
    main()
