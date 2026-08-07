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

from snap_qc_sim import QcCase, simulate

if __package__:
    from .hurdle_deviation_model import (
        MODEL_PARAMS,
        N_FOLDS,
        RANDOM_STATE,
        ProbabilityStage,
        _calibration_summary,
        _evaluate_probability_stage,
        _feature_columns,
        _fit_probability_stage,
        _package_versions,
        _shrink_state_factors,
        _weighted_cross_val_predict,
        _weighted_mean,
        assemble,
        effective_sample_size,
    )
    from .hurdle_deviation_model import _provenance as hurdle_provenance
    from .predictive_process import (
        QUANTILE_LEVELS,
        conditional_survival,
        draw_deviations,
        enforce_monotone_quantiles,
        error_dollars,
        expected_error_dollars,
    )
    from .train_error_model import THRESHOLD, YEAR_TEST, YEARS_TRAIN
else:
    from hurdle_deviation_model import (
        MODEL_PARAMS,
        N_FOLDS,
        RANDOM_STATE,
        ProbabilityStage,
        _calibration_summary,
        _evaluate_probability_stage,
        _feature_columns,
        _fit_probability_stage,
        _package_versions,
        _shrink_state_factors,
        _weighted_cross_val_predict,
        _weighted_mean,
        assemble,
        effective_sample_size,
    )
    from hurdle_deviation_model import _provenance as hurdle_provenance
    from predictive_process import (
        QUANTILE_LEVELS,
        conditional_survival,
        draw_deviations,
        enforce_monotone_quantiles,
        error_dollars,
        expected_error_dollars,
    )
    from train_error_model import THRESHOLD, YEAR_TEST, YEARS_TRAIN


OUT = Path(__file__).with_name("distributional_results.json")
APP_METADATA = Path(__file__).resolve().parents[1] / "app" / "public" / "data.json"
SIGN_SEED = RANDOM_STATE + 30
TAIL_SEED = RANDOM_STATE + 40
SIMULATION_SEED = 202_408
SIMULATION_DRAWS = 4_000
DEVIATION_TOLERANCE = 0.5
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
    residual_cutoff: float
    n: int
    effective_n: float
    oof_folds: int


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


def _fit_tail(
    deviators: pd.DataFrame,
    features: list[str],
) -> TailFit:
    """Fit a log-exponential excess scale from top-decile OOF residuals."""
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
    cutoff = _weighted_quantile(residual, weights, 0.9)
    top = residual > cutoff
    if not top.any():
        raise ValueError("top-decile tail fit has no strict exceedances")
    excess = residual[top] - cutoff
    scale = _weighted_mean(excess, weights[top])
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("log-tail scale must be finite and positive")
    if scale >= 1:
        raise ValueError(
            "log-tail scale must be below one for finite expected error dollars"
        )
    return TailFit(
        scale=scale,
        residual_cutoff=cutoff,
        n=int(top.sum()),
        effective_n=effective_sample_size(weights[top]),
        oof_folds=folds,
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


def predict_process(
    bundle: ProcessBundle,
    data: pd.DataFrame,
    features: list[str],
) -> pd.DataFrame:
    """Add aligned component, quantile, and crossing predictions."""
    result = data.copy()
    distributional = bundle.distributional
    result["p_dev_raw"] = distributional.deviation_stage.predict_raw(result[features])
    result["p_dev"] = distributional.deviation_stage.predict(result[features])
    result["p_pos_raw"] = distributional.sign_stage.predict_raw(result[features])
    result["p_pos"] = distributional.sign_stage.predict(result[features])
    raw_quantiles = np.column_stack(
        [model.predict(result[features]) for model in distributional.quantile_models]
    )
    quantiles = enforce_monotone_quantiles(
        raw_quantiles,
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    for index, column in enumerate(QUANTILE_COLUMNS):
        result[column] = quantiles[:, index]
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
    return simulate(
        cases,
        official_rate,
        draws=SIMULATION_DRAWS,
        rng=np.random.default_rng(seed),
    )


def _model_full_state_draws(
    group: pd.DataFrame,
    official_rate: float,
    tail_scale: float,
    seed: int,
) -> tuple[np.ndarray, float, float]:
    """Draw every fixed FY2024 case, then apply v1's official level shift."""
    weights = group["w"].to_numpy(dtype=float)
    issuance = group["issuance"].to_numpy(dtype=float)
    observed_error = group["obs_error_dollars"].to_numpy(dtype=float)
    p_dev = group["p_dev"].to_numpy(dtype=float)
    p_pos = group["p_pos"].to_numpy(dtype=float)
    quantiles = group[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
    denominator = float(np.sum(weights * issuance))
    observed_point = 100 * float(np.sum(weights * observed_error)) / denominator
    analytic = expected_error_dollars(
        p_dev,
        quantiles,
        tail_scale,
        THRESHOLD[YEAR_TEST],
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    analytic_point = 100 * float(np.sum(weights * analytic)) / denominator

    rng = np.random.default_rng(seed)
    rates = np.empty(SIMULATION_DRAWS, dtype=float)
    batch_size = 100
    for start in range(0, SIMULATION_DRAWS, batch_size):
        stop = min(start + batch_size, SIMULATION_DRAWS)
        batch = stop - start
        deviations = draw_deviations(
            np.broadcast_to(p_dev, (batch, len(group))),
            np.broadcast_to(p_pos, (batch, len(group))),
            np.broadcast_to(quantiles, (batch, len(group), len(QUANTILE_LEVELS))),
            tail_scale,
            rng,
            minimum_magnitude=DEVIATION_TOLERANCE,
        )
        errors = error_dollars(deviations, THRESHOLD[YEAR_TEST])
        raw = 100 * np.sum(errors * weights, axis=1) / denominator
        # simulate.py simplifies to official - observed sample point + scenario draw.
        rates[start:stop] = official_rate - observed_point + raw
    return rates, observed_point, analytic_point


def _simulation_validation(
    predicted_2024: pd.DataFrame,
    tail_scale: float,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    issuance = (
        predicted_2024.assign(
            weighted_issuance=lambda frame: frame["w"] * frame["issuance"]
        )
        .groupby("state", sort=True)["weighted_issuance"]
        .sum()
        .sort_values(ascending=False)
    )
    comparison_states = ["CO"] + [
        str(state) for state in issuance.index if state != "CO"
    ][:3]
    rows: list[dict[str, Any]] = []
    for index, state in enumerate(comparison_states):
        group = predicted_2024.loc[predicted_2024["state"].eq(state)]
        official = float(metadata["states"][state]["official"])
        observed = _observed_bootstrap(
            group,
            official,
            SIMULATION_SEED + 2 * index,
        )
        model, observed_point, analytic_point = _model_full_state_draws(
            group,
            official,
            tail_scale,
            SIMULATION_SEED + 2 * index + 1,
        )
        rows.append(
            {
                "state": state,
                "n": len(group),
                "official_rate_pct": official,
                "observed_sample_point_pct": observed_point,
                "model_analytic_point_pct": analytic_point,
                "model": {
                    "mean_pct": float(model.mean()),
                    "sd_pp": float(model.std()),
                },
                "observed_bootstrap": {
                    "mean_pct": float(observed.mean()),
                    "sd_pp": float(observed.std()),
                },
            }
        )
    return {
        "draws": SIMULATION_DRAWS,
        "states": comparison_states,
        "model_process": (
            "fixed FY2024 CASE==1 roster; independently draw D for every case; "
            "rate = official - corrected observed sample point + model draw rate"
        ),
        "observed_process": (
            "uniform row bootstrap retaining HWGT inside the ratio; rate = "
            "official - corrected observed sample point + bootstrap rate"
        ),
        "rows": rows,
    }


def _provenance(tail: TailFit) -> dict[str, Any]:
    provenance = hurdle_provenance()
    with APP_METADATA.open("rb") as source:
        provenance["input_sha256"]["app/public/data.json"] = hashlib.file_digest(
            source, "sha256"
        ).hexdigest()
    provenance.update(
        {
            "package_versions": _package_versions(),
            "distributional_training_years": YEARS_TRAIN,
            "distributional_validation_year": YEAR_TEST,
            "quantile_levels": QUANTILE_LEVELS.tolist(),
            "quantile_estimator": (
                "sklearn HistGradientBoostingRegressor with native quantile loss"
            ),
            "sign_seed": SIGN_SEED,
            "tail_seed": TAIL_SEED,
            "simulation_seed": SIMULATION_SEED,
            "simulation_draws": SIMULATION_DRAWS,
            "tail": {
                "scale_log": tail.scale,
                "residual_cutoff_log": tail.residual_cutoff,
                "fit_n": tail.n,
                "fit_effective_n": tail.effective_n,
                "oof_folds": tail.oof_folds,
                "method": (
                    "exponential excess on log-magnitude beyond the weighted "
                    "90th percentile of OOF median residuals; attached above q99"
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
    predicted_2024 = predict_process(primary, fy2024, features)
    coverage = weighted_quantile_coverage(predicted_2024)
    deviators_2024 = predicted_2024.loc[predicted_2024["deviates"].eq(1)].copy()
    deviators_2024["positive_deviation"] = deviators_2024["D"].gt(0).astype(np.int8)
    sign_2024 = _evaluate_probability_stage(
        primary.distributional.sign_stage,
        deviators_2024,
        features,
        "positive_deviation",
    )

    comparison_rows: list[dict[str, Any]] = []
    for route, column in (
        ("direct stage-2", "p_cross_direct"),
        ("distributional implied crossing", "p_cross_distributional"),
    ):
        rates = _crossing_state_rates(predicted_2024, column)
        comparison_rows.append(
            _comparison_row(
                route,
                "primary model through FY2023, unfactored",
                rates,
                _national_prevalence(predicted_2024, column),
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
    factor_details: dict[str, Any] = {}
    for route, column in (
        ("direct stage-2", "p_cross_direct"),
        ("distributional implied crossing", "p_cross_distributional"),
    ):
        rows, details = _route_factor_validation(
            frozen_2023,
            frozen_2024,
            column,
            route,
        )
        comparison_rows.extend(rows)
        factor_details[route] = details

    official_prevalence = _national_prevalence(predicted_2024, "crosses")
    literal_crossing = 100 * _weighted_mean(
        (predicted_2024["D"].abs().to_numpy(dtype=float) > THRESHOLD[YEAR_TEST]).astype(
            float
        ),
        predicted_2024["w"].to_numpy(dtype=float),
    )
    discordant = predicted_2024["crosses"].ne(
        predicted_2024["D"].abs().gt(THRESHOLD[YEAR_TEST])
    )
    metadata = _load_app_metadata()
    simulation = _simulation_validation(
        predicted_2024,
        primary.distributional.tail.scale,
        metadata,
    )

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
    result: dict[str, Any] = {
        "schema_version": 1,
        "definitions": {
            "prediction_scope": (
                "predicts the FY2024 SNAP QC error process from FY2017-19 and "
                "FY2022-23 training records; no causal interpretation"
            ),
            "signed_deviation_D": "RAWBEN - BENFIX",
            "deviates": "abs(D) > 0.5 dollars",
            "positive_sign": "D > 0 among deviators",
            "quantile_target": "log(abs(D)) among deviators",
            "conditional_independence": (
                "sign and magnitude draws are conditionally independent given features"
            ),
            "tail": (
                "log-scale exponential excess beyond q99, with scale fit from "
                "the top decile of weighted OOF median residuals"
            ),
            "crossing": (
                "error dollars equal abs(D) only when abs(D) is strictly greater "
                "than the fiscal-year threshold"
            ),
        },
        "provenance": _provenance(primary.distributional.tail),
        "features": features,
        "quantile_levels": QUANTILE_LEVELS.tolist(),
        "quantile_columns": list(QUANTILE_COLUMNS),
        "sign": {
            "training_oof_cross_fitted": (
                primary.distributional.sign_stage.oof_metrics
            ),
            "fy2024_among_deviators": sign_2024,
        },
        "magnitude_distribution": {
            "training_deviators_n": int(primary_train["deviates"].sum()),
            "fy2024_deviators_n": int(predicted_2024["deviates"].sum()),
            "tail_fit": {
                "scale_log": primary.distributional.tail.scale,
                "residual_cutoff_log": (primary.distributional.tail.residual_cutoff),
                "n": primary.distributional.tail.n,
                "effective_n": primary.distributional.tail.effective_n,
                "oof_folds": primary.distributional.tail.oof_folds,
            },
            "fy2024_weighted_coverage": coverage,
            "coverage_flags_over_3pp": int(
                sum(bool(row["flag_over_3pp"]) for row in coverage)
            ),
        },
        "crossing_validation": {
            "observed_official_national_prevalence_pct": official_prevalence,
            "observed_literal_D_crossing_national_prevalence_pct": literal_crossing,
            "official_vs_literal_discordant_n": int(discordant.sum()),
            "official_vs_literal_discordance_weighted_pp": (
                100
                * _weighted_mean(
                    discordant.astype(float),
                    predicted_2024["w"].to_numpy(dtype=float),
                )
            ),
            "comparison_rows": comparison_rows,
            "fy2023_fit_factor_details": factor_details,
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
        "measured_rate_simulation": simulation,
        "export": {
            "case_filter": "CASE == 1",
            "fy2024_cases": len(predicted_2024),
            "state_count": int(predicted_2024["state"].nunique()),
            "quantiles_are_log_dollars": True,
        },
    }
    return DistributionalArtifacts(
        result=result,
        predictions=predicted_2024,
        bundle=primary.distributional,
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


def predictions_for_export() -> tuple[pd.DataFrame, float]:
    """Standalone builder hook returning validated primary FY2024 predictions."""
    artifacts = analyze()
    return artifacts.predictions, artifacts.bundle.tail.scale


if __name__ == "__main__":
    main()
