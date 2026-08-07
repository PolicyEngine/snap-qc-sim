"""Head-to-head QRF benchmark against the shipped GBM quantile stack.

The benchmark is deliberately separate from :mod:`analysis.run_all`.  It reads
the existing QC inputs, prepares browser-schema payloads entirely in memory,
and writes only its requested JSON and Markdown reports.  It never writes
``app/``.

The deterministic benchmark core is fitted and evaluated at least twice.  Run
times are observational metadata and are excluded from the exact SHA-256
comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import scripts_build_model_data

if __package__:
    from .distributional_deviation_model import (
        APP_METADATA,
        DEVIATION_TOLERANCE,
        QUANTILE_COLUMNS,
        SIMULATION_DRAWS,
        SIMULATION_SEEDS,
        _aggregate_seed_statistics,
        _dollar_factor_validation,
        _encoded_model_group,
        _fit_tail,
        _model_bootstrap_draws,
        _observed_bootstrap,
        _quantile_regressor,
        _seed_statistics,
        weighted_pit_summary,
        weighted_quantile_coverage,
    )
    from .hurdle_deviation_model import (
        RANDOM_STATE,
        _feature_columns,
        _fit_probability_stage,
        _package_versions,
        assemble,
    )
    from .predictive_process import (
        MAX_TAIL_SCALE,
        QUANTILE_LEVELS,
        TAIL_SCALE_MARGIN,
        enforce_monotone_quantiles,
        expected_error_dollars,
    )
    from .quantile_forest_deviation_model import (
        QRF_PARAMS,
        QuantilePrediction,
        fit_quantile_forest,
        predict_quantiles,
        quantile_diagnostics,
    )
    from .train_error_model import THRESHOLD, YEAR_TEST, YEARS_TRAIN
else:
    from distributional_deviation_model import (
        APP_METADATA,
        DEVIATION_TOLERANCE,
        QUANTILE_COLUMNS,
        SIMULATION_DRAWS,
        SIMULATION_SEEDS,
        _aggregate_seed_statistics,
        _dollar_factor_validation,
        _encoded_model_group,
        _fit_tail,
        _model_bootstrap_draws,
        _observed_bootstrap,
        _quantile_regressor,
        _seed_statistics,
        weighted_pit_summary,
        weighted_quantile_coverage,
    )
    from hurdle_deviation_model import (
        RANDOM_STATE,
        _feature_columns,
        _fit_probability_stage,
        _package_versions,
        assemble,
    )
    from predictive_process import (
        MAX_TAIL_SCALE,
        QUANTILE_LEVELS,
        TAIL_SCALE_MARGIN,
        enforce_monotone_quantiles,
        expected_error_dollars,
    )
    from quantile_forest_deviation_model import (
        QRF_PARAMS,
        QuantilePrediction,
        fit_quantile_forest,
        predict_quantiles,
        quantile_diagnostics,
    )
    from train_error_model import THRESHOLD, YEAR_TEST, YEARS_TRAIN


DEFAULT_JSON = Path(__file__).with_name("qrf_benchmark_results.json")
DEFAULT_MARKDOWN = Path(__file__).with_name("QRF_BENCHMARK.md")
DEFAULT_SHIPPED_RESULTS = Path(__file__).with_name("distributional_results.json")
TARGET_STATES = ("CO", "CA", "NY", "TX")
TIE_TOLERANCE = 1e-12
RECOMMENDED_SHELL = (
    "OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 "
    "VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 "
    "uv run --frozen --extra analysis python -m analysis.qrf_benchmark"
)


@dataclass(frozen=True)
class GbmMagnitudeBundle:
    """The shipped independent GBM quantile fits and their OOF tail."""

    models: tuple[Any, ...]
    tail: Any


def _jsonable(value: Any) -> Any:
    """Convert analysis objects to strict, deterministic JSON primitives."""
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, pd.DataFrame):
        return _jsonable(value.to_dict("records"))
    if isinstance(value, pd.Series):
        return _jsonable(value.tolist())
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("benchmark result contains a nonfinite float")
    return value


def _canonical_json(value: Any) -> bytes:
    """Encode a strict canonical representation for exact repeat comparison."""
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _fit_gbm_magnitude(
    train: pd.DataFrame,
    features: list[str],
) -> GbmMagnitudeBundle:
    """Fit the exact shipped nine-GBM magnitude stack and GBM OOF tail."""
    deviators = train.loc[train["deviates"].eq(1)]
    target = np.log(deviators["D"].abs()).astype(float)
    models: list[Any] = []
    for level in QUANTILE_LEVELS:
        model = _quantile_regressor(float(level))
        model.fit(
            deviators[features],
            target,
            sample_weight=deviators["w"],
        )
        models.append(model)
    return GbmMagnitudeBundle(tuple(models), _fit_tail(deviators, features))


def _matrix_adjustment_diagnostics(raw: np.ndarray) -> dict[str, Any]:
    """Return GBM diagnostics in the QRF module's diagnostic vocabulary."""
    matrix = np.asarray(raw, dtype=float)
    crossing = np.diff(matrix, axis=1) < 0
    floored = np.maximum(matrix, np.log(DEVIATION_TOLERANCE))
    safeguarded = enforce_monotone_quantiles(
        matrix,
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    return {
        "raw_crossing_count": int(crossing.sum()),
        "raw_crossing_row_count": int(crossing.any(axis=1).sum()),
        "floor_adjustment_count": int((floored != matrix).sum()),
        "post_helper_adjustment_count": int((safeguarded != floored).sum()),
        "naturally_monotone": bool(not crossing.any()),
    }


def _predict_gbm_quantiles(
    bundle: GbmMagnitudeBundle,
    data: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, dict[str, Any]]:
    raw = np.column_stack([model.predict(data[features]) for model in bundle.models])
    diagnostics = _matrix_adjustment_diagnostics(raw)
    return (
        enforce_monotone_quantiles(
            raw,
            minimum_magnitude=DEVIATION_TOLERANCE,
        ),
        diagnostics,
    )


def _predict_qrf_quantiles(
    bundle: Any,
    data: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, dict[str, Any]]:
    prediction = predict_quantiles(
        bundle,
        data,
        features,
        return_diagnostics=True,
    )
    if not isinstance(prediction, QuantilePrediction):
        raise TypeError("QRF diagnostic prediction did not return QuantilePrediction")
    # Re-run the public diagnostic helper against the safeguarded matrix as a
    # defensive API/schema check.  The raw diagnostics remain the informative
    # values reported below.
    safeguarded = quantile_diagnostics(prediction.quantiles)
    if not safeguarded.naturally_monotone:
        raise AssertionError("safeguarded QRF quantiles are not monotone")
    return prediction.quantiles, _jsonable(prediction.diagnostics)


def _prediction_frame(
    data: pd.DataFrame,
    p_dev: np.ndarray,
    quantiles: np.ndarray,
    tail: Any,
) -> pd.DataFrame:
    """Attach the common hurdle and estimator-specific magnitude process."""
    matrix = enforce_monotone_quantiles(
        np.asarray(quantiles, dtype=float),
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    if matrix.shape != (len(data), len(QUANTILE_COLUMNS)):
        raise ValueError("predicted quantile matrix has the wrong shape")
    probability = np.asarray(p_dev, dtype=float)
    if probability.shape != (len(data),) or not np.isfinite(probability).all():
        raise ValueError("p_dev has the wrong shape or contains nonfinite values")
    if ((probability < 0) | (probability > 1)).any():
        raise ValueError("p_dev must lie in [0, 1]")

    result = data.copy()
    result["p_dev"] = probability
    for index, column in enumerate(QUANTILE_COLUMNS):
        result[column] = matrix[:, index]
    common_arguments = (
        result["p_dev"].to_numpy(dtype=float),
        matrix,
        float(tail.scale),
        result["thr"].to_numpy(dtype=float),
    )
    result["pred_err_dollars_uncapped"] = expected_error_dollars(
        *common_arguments,
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    result["pred_err_dollars"] = expected_error_dollars(
        *common_arguments,
        minimum_magnitude=DEVIATION_TOLERANCE,
        magnitude_cap=result["deviation_cap"].to_numpy(dtype=float),
    )
    return result


def _coverage_summary(predicted_2024: pd.DataFrame) -> dict[str, Any]:
    rows = weighted_quantile_coverage(predicted_2024)
    gaps = np.asarray([row["gap_pp"] for row in rows], dtype=float)
    return {
        "levels": rows,
        "mean_absolute_gap_pp": float(np.mean(np.abs(gaps))),
        "max_absolute_gap_pp": float(np.max(np.abs(gaps))),
        "one_sided_pattern": {
            "negative_gap_count": int((gaps < 0).sum()),
            "positive_gap_count": int((gaps > 0).sum()),
            "zero_gap_count": int((gaps == 0).sum()),
            "all_nine_negative": bool((gaps < 0).all()),
            "all_nine_positive": bool((gaps > 0).all()),
            "all_nine_same_nonzero_sign": bool((gaps < 0).all() or (gaps > 0).all()),
            "interpretation": (
                "negative gaps indicate undercoverage; positive gaps indicate "
                "overcoverage"
            ),
        },
    }


def _tail_summary(tail: Any) -> dict[str, Any]:
    scale = float(tail.scale)
    scale_se = float(tail.scale_se)
    upper_95 = scale + 1.96 * scale_se
    return {
        "family": "exponential log excess",
        "attachment_quantile": float(tail.cutoff_quantile),
        "scale_log": scale,
        "scale_se_log": scale_se,
        "upper_95_log_scale": upper_95,
        "residual_cutoff_log": float(tail.residual_cutoff),
        "n": int(tail.n),
        "effective_n": float(tail.effective_n),
        "oof_folds": int(tail.oof_folds),
        "mean_excess_by_cutoff": _jsonable(tail.mean_excess_by_cutoff),
        "finite_variance_gate": {
            "point_scale_upper_bound_exclusive": MAX_TAIL_SCALE,
            "mathematical_limit_exclusive": 0.5,
            "fixed_regression_margin": TAIL_SCALE_MARGIN,
            "passed": bool(scale < MAX_TAIL_SCALE and upper_95 < 0.5),
        },
    }


def _export_summary(prepared: dict[str, Any]) -> dict[str, Any]:
    payload = prepared["data"]
    states = payload["states"]
    cases = sum(int(state["n"]) for state in states.values())
    levels = payload["quantile_levels"]
    return {
        "schema_version": int(payload["schema_version"]),
        "raw_bytes": int(prepared["raw_bytes"]),
        "gzip_bytes": int(prepared["gzip_bytes"]),
        "encoded_sha256": hashlib.sha256(prepared["encoded"]).hexdigest(),
        "q_encoding": payload["q_encoding"],
        "q_decimal_quantization": prepared["q_decimal_quantization"],
        "cases": cases,
        "states": len(states),
        "quantile_vector_shape": [cases, len(levels)],
        "per_case_quantile_vector_shape": [len(levels)],
        "model_object_size_excluded": True,
        "comparison_scope": "serialized per-case vectors only",
    }


def _load_json_object(path: Path, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read {context} from {path}: {error}") from error
    if not isinstance(payload, dict):
        raise TypeError(f"{context} must be a JSON object: {path}")
    return payload


def _shipped_gbm_equivalence(
    gbm: dict[str, Any],
    simulation_reference: dict[str, Any],
    shipped: dict[str, Any],
    shipped_path: Path,
) -> dict[str, Any]:
    """Report numeric deltas from the checked-in shipped GBM result."""
    comparisons: list[dict[str, Any]] = []

    def add(metric: str, current: float, reference: float) -> None:
        comparisons.append(
            {
                "metric": metric,
                "benchmark_gbm": float(current),
                "shipped_reference": float(reference),
                "delta_benchmark_minus_shipped": float(current - reference),
            }
        )

    shipped_magnitude = shipped["magnitude_distribution"]
    shipped_coverage = shipped_magnitude["fy2024_weighted_coverage"]
    for index, level in enumerate(QUANTILE_LEVELS):
        current_row = gbm["coverage"]["levels"][index]
        reference_row = shipped_coverage[index]
        if float(reference_row["quantile"]) != float(level):
            raise ValueError("shipped GBM coverage levels do not match benchmark")
        add(
            f"coverage_q{100 * float(level):g}_weighted",
            current_row["weighted_coverage"],
            reference_row["weighted_coverage"],
        )
        add(
            f"coverage_q{100 * float(level):g}_gap_pp",
            current_row["gap_pp"],
            reference_row["gap_pp"],
        )
    add(
        "coverage_mean_absolute_gap_pp",
        gbm["coverage"]["mean_absolute_gap_pp"],
        float(np.mean([abs(float(row["gap_pp"])) for row in shipped_coverage])),
    )
    add(
        "coverage_max_absolute_gap_pp",
        gbm["coverage"]["max_absolute_gap_pp"],
        float(max(abs(float(row["gap_pp"])) for row in shipped_coverage)),
    )

    shipped_pit = shipped_magnitude["fy2024_weighted_pit"]
    for field in (
        "weighted_mean",
        "mean_gap",
        "weighted_cvm_integral",
        "effective_n_scaled_cvm",
    ):
        add(f"pit_{field}", gbm["pit"][field], shipped_pit[field])

    for specification in ("raw_frozen_model", "factor_adjusted_frozen_model"):
        for weighting in ("equal_jurisdiction", "issuance_weighted"):
            add(
                f"dollar_{specification}_{weighting}_mae_pp",
                gbm["dollar_rate_validation"]["metrics"][specification][weighting][
                    "mae_pp"
                ],
                shipped["dollar_rate_validation"]["metrics"][specification][weighting][
                    "mae_pp"
                ],
            )

    shipped_tail = shipped_magnitude["tail_fit"]
    for current_field, reference_field in (
        ("scale_log", "scale_log"),
        ("scale_se_log", "scale_se_log"),
        ("residual_cutoff_log", "residual_cutoff_log"),
    ):
        add(
            f"tail_{current_field}",
            gbm["tail"][current_field],
            shipped_tail[reference_field],
        )

    add(
        "export_raw_bytes",
        gbm["export"]["raw_bytes"],
        shipped["export"]["model_data_raw_bytes"],
    )
    add(
        "export_gzip_bytes",
        gbm["export"]["gzip_bytes"],
        shipped["export"]["model_data_gzip_bytes"],
    )

    shipped_simulation = {
        str(row["state"]): row for row in shipped["measured_rate_simulation"]["rows"]
    }
    for state in TARGET_STATES:
        if state not in shipped_simulation:
            raise ValueError(f"shipped GBM simulation is missing {state}")
        reference_row = shipped_simulation[state]
        add(
            f"simulation_{state}_model_sd_pp",
            gbm["simulation"]["states"][state]["sd_pp"],
            reference_row["model"]["sd_pp"],
        )
        add(
            f"simulation_{state}_observed_bootstrap_sd_pp",
            simulation_reference["observed_bootstrap"][state]["sd_pp"],
            reference_row["observed_bootstrap"]["sd_pp"],
        )
    absolute_deltas = [
        abs(float(row["delta_benchmark_minus_shipped"])) for row in comparisons
    ]
    tolerance = 1e-10
    return {
        "reference_path": str(shipped_path.resolve()),
        "reference_sha256": _file_sha256(shipped_path),
        "tolerance": tolerance,
        "passed": bool(max(absolute_deltas, default=0.0) <= tolerance),
        "exact_numeric_match": bool(not any(absolute_deltas)),
        "max_absolute_delta": max(absolute_deltas, default=0.0),
        "comparisons": comparisons,
    }


def _estimator_validation(
    predicted_2023: pd.DataFrame,
    predicted_2024: pd.DataFrame,
    tail: Any,
    metadata_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    dollar_validation, factors, state_diagnostics = _dollar_factor_validation(
        predicted_2023,
        predicted_2024,
    )
    prepared = scripts_build_model_data.prepare_model_data(
        predicted_2024,
        tail_scale=float(tail.scale),
        tail_scale_se=float(tail.scale_se),
        state_factors=factors,
        state_diagnostics=state_diagnostics,
        metadata_path=metadata_path,
        threshold=THRESHOLD[YEAR_TEST],
        deviation_tolerance=DEVIATION_TOLERANCE,
        quantile_levels=QUANTILE_LEVELS,
        quantile_columns=QUANTILE_COLUMNS,
    )
    result = {
        "coverage": _coverage_summary(predicted_2024),
        "pit": weighted_pit_summary(predicted_2024, float(tail.scale)),
        "dollar_rate_validation": dollar_validation,
        "tail": _tail_summary(tail),
        "export": _export_summary(prepared),
    }
    return result, prepared["data"]


def _simulation_comparison(
    predicted_2024: pd.DataFrame,
    payloads: Mapping[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Run the shipped centered/floored validation with common random numbers."""
    observed: dict[str, Any] = {}
    estimator_rows: dict[str, dict[str, Any]] = {
        estimator: {} for estimator in payloads
    }
    for state in TARGET_STATES:
        observed_group = predicted_2024.loc[predicted_2024["state"].eq(state)]
        if observed_group.empty:
            raise ValueError(f"FY2024 validation is missing requested state {state}")
        encoded_by_estimator = {
            estimator: payload["states"][state]
            for estimator, payload in payloads.items()
        }
        officials = {
            float(encoded["official"]) for encoded in encoded_by_estimator.values()
        }
        if len(officials) != 1:
            raise ValueError(f"{state}: estimator exports disagree on official rate")
        official = officials.pop()

        observed_seed_rows = [
            _seed_statistics(_observed_bootstrap(observed_group, official, seed + 1))
            for seed in SIMULATION_SEEDS
        ]
        observed[state] = _aggregate_seed_statistics(observed_seed_rows)

        for estimator, encoded in encoded_by_estimator.items():
            model_group = _encoded_model_group(state, encoded)
            if len(model_group) != len(observed_group):
                raise ValueError(
                    f"{state}: encoded {estimator} and observed row counts differ"
                )
            tail_scale = float(payloads[estimator]["tail_scale_log"])
            state_factor = float(encoded["factor"])
            seed_rows: list[dict[str, Any]] = []
            for seed in SIMULATION_SEEDS:
                raw = _model_bootstrap_draws(
                    model_group,
                    tail_scale,
                    state_factor,
                    seed,
                )
                centered = np.maximum(raw + official - float(raw.mean()), 0.0)
                seed_rows.append(_seed_statistics(centered))
            aggregate = _aggregate_seed_statistics(seed_rows)
            aggregate["absolute_sd_gap_to_observed_pp"] = abs(
                float(aggregate["sd_pp"]) - float(observed[state]["sd_pp"])
            )
            estimator_rows[estimator][state] = aggregate
    reference = {
        "states": list(TARGET_STATES),
        "draws_per_seed": SIMULATION_DRAWS,
        "seeds": list(SIMULATION_SEEDS),
        "seed_count": len(SIMULATION_SEEDS),
        "total_draws_per_state": SIMULATION_DRAWS * len(SIMULATION_SEEDS),
        "common_random_numbers_between_estimators": True,
        "model_center": (
            "within each seed, add official rate minus the raw model-draw mean"
        ),
        "model_and_observed_floor_pct": 0.0,
        "observed_bootstrap": observed,
    }
    return reference, estimator_rows


def _runtime_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    def summarize(values: list[float]) -> dict[str, Any]:
        return {
            "seconds_by_repetition": values,
            "mean_seconds": float(statistics.fmean(values)),
            "median_seconds": float(statistics.median(values)),
            "min_seconds": float(min(values)),
            "max_seconds": float(max(values)),
        }

    estimators: dict[str, Any] = {}
    for estimator in ("gbm", "qrf"):
        fit = [float(row[estimator]["fit_seconds"]) for row in records]
        predict = [float(row[estimator]["prediction_seconds"]) for row in records]
        total = [left + right for left, right in zip(fit, predict, strict=True)]
        estimators[estimator] = {
            "magnitude_fit": summarize(fit),
            "fy2023_and_fy2024_prediction": summarize(predict),
            "magnitude_fit_plus_prediction": summarize(total),
        }
    return {
        "observational_only": True,
        "excluded_from_deterministic_core_sha256": True,
        "scope": "estimator-specific magnitude fit plus FY2023/FY2024 prediction",
        "shared_probability_stage_excluded": True,
        "fit_order_by_repetition": [row["fit_order"] for row in records],
        "estimators": estimators,
    }


def _estimator_run(
    estimator: str,
    train: pd.DataFrame,
    fy2023: pd.DataFrame,
    fy2024: pd.DataFrame,
    features: list[str],
    p_dev_2023: np.ndarray,
    p_dev_2024: np.ndarray,
    metadata_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    fit_start = time.perf_counter()
    if estimator == "gbm":
        bundle = _fit_gbm_magnitude(train, features)
    elif estimator == "qrf":
        bundle = fit_quantile_forest(train, features)
    else:
        raise ValueError(f"unknown estimator: {estimator}")
    fit_seconds = time.perf_counter() - fit_start

    prediction_start = time.perf_counter()
    if estimator == "gbm":
        quantiles_2023, diagnostics_2023 = _predict_gbm_quantiles(
            bundle, fy2023, features
        )
        quantiles_2024, diagnostics_2024 = _predict_gbm_quantiles(
            bundle, fy2024, features
        )
    else:
        quantiles_2023, diagnostics_2023 = _predict_qrf_quantiles(
            bundle, fy2023, features
        )
        quantiles_2024, diagnostics_2024 = _predict_qrf_quantiles(
            bundle, fy2024, features
        )
    predicted_2023 = _prediction_frame(fy2023, p_dev_2023, quantiles_2023, bundle.tail)
    predicted_2024 = _prediction_frame(fy2024, p_dev_2024, quantiles_2024, bundle.tail)
    prediction_seconds = time.perf_counter() - prediction_start

    result, payload = _estimator_validation(
        predicted_2023,
        predicted_2024,
        bundle.tail,
        metadata_path,
    )
    result["quantile_adjustments"] = {
        "fy2023": diagnostics_2023,
        "fy2024": diagnostics_2024,
    }
    return (
        result,
        payload,
        {
            "fit_seconds": fit_seconds,
            "prediction_seconds": prediction_seconds,
        },
    )


def _provenance(
    features: list[str],
    metadata_path: Path,
    shipped_results_path: Path,
    train: pd.DataFrame,
    fy2023: pd.DataFrame,
    fy2024: pd.DataFrame,
) -> dict[str, Any]:
    packages = _package_versions()
    try:
        packages["quantile-forest"] = version("quantile-forest")
    except PackageNotFoundError:
        packages["quantile-forest"] = "not-installed"
    return {
        "package_versions": packages,
        "metadata_path": str(metadata_path.resolve()),
        "metadata_sha256": _file_sha256(metadata_path),
        "shipped_gbm_results_path": str(shipped_results_path.resolve()),
        "shipped_gbm_results_sha256": _file_sha256(shipped_results_path),
        "recommended_shell": RECOMMENDED_SHELL,
        "parallelism": (
            "QRF n_jobs=1; set numerical-library thread variables before Python "
            "starts using the recommended shell command"
        ),
        "random_state": RANDOM_STATE,
        "training_years": [year for year in YEARS_TRAIN if year < 2023],
        "factor_fit_year": 2023,
        "validation_year": YEAR_TEST,
        "training_cases": len(train),
        "training_deviators": int(train["deviates"].sum()),
        "fy2023_cases": len(fy2023),
        "fy2024_cases": len(fy2024),
        "features": features,
        "quantile_levels": QUANTILE_LEVELS.tolist(),
        "quantile_columns": list(QUANTILE_COLUMNS),
        "qrf_parameters": QRF_PARAMS,
    }


def _run_once(
    train: pd.DataFrame,
    fy2023: pd.DataFrame,
    fy2024: pd.DataFrame,
    features: list[str],
    p_dev_2023: np.ndarray,
    p_dev_2024: np.ndarray,
    probability_metrics: dict[str, Any],
    metadata_path: Path,
    shipped_results_path: Path,
    shipped_results: dict[str, Any],
    repetition: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Alternate order so the observational timing comparison is not tied to a
    # permanently warm or cold second position.
    order = ("gbm", "qrf") if repetition % 2 == 0 else ("qrf", "gbm")
    estimator_results: dict[str, Any] = {}
    payloads: dict[str, dict[str, Any]] = {}
    estimator_timing: dict[str, Any] = {}
    for estimator in order:
        result, payload, timing = _estimator_run(
            estimator,
            train,
            fy2023,
            fy2024,
            features,
            p_dev_2023,
            p_dev_2024,
            metadata_path,
        )
        estimator_results[estimator] = result
        payloads[estimator] = payload
        estimator_timing[estimator] = timing

    identical_export_fields = (
        "schema_version",
        "cases",
        "states",
        "quantile_vector_shape",
        "per_case_quantile_vector_shape",
    )
    for field in identical_export_fields:
        values = {
            _canonical_json(estimator_results[name]["export"][field])
            for name in ("gbm", "qrf")
        }
        if len(values) != 1:
            raise ValueError(f"estimator exports disagree on {field}")

    simulation_reference, simulation_rows = _simulation_comparison(
        fy2024,
        payloads,
    )
    for estimator, rows in simulation_rows.items():
        estimator_results[estimator]["simulation"] = {"states": rows}

    shipped_gbm_equivalence = _shipped_gbm_equivalence(
        estimator_results["gbm"],
        simulation_reference,
        shipped_results,
        shipped_results_path,
    )
    if not shipped_gbm_equivalence["passed"]:
        raise RuntimeError(
            "benchmark GBM does not reproduce the shipped comparator within "
            f"{shipped_gbm_equivalence['tolerance']}: maximum absolute delta "
            f"{shipped_gbm_equivalence['max_absolute_delta']}"
        )

    core = {
        "schema_version": 1,
        "protocol": {
            "comparison": ("QRF versus shipped independent gradient-boosted quantiles"),
            "common_probability_stage_fit_once": True,
            "features_targets_years_weights_caps_identical": True,
            "magnitude_target": "log(abs(D)) among abs(D) > 0.5 deviators",
            "state_factor_protocol": (
                "frozen magnitude model through FY2022; separately refit each "
                "estimator's factors on FY2023; validate FY2024"
            ),
            "tail_protocol": (
                "estimator-specific q99 OOF-median residual mean excess, attached "
                "above each estimator's conditional q99"
            ),
            "caps": "max(BENMAX, abs(RAWBEN - BENFIX)) before strict threshold",
            "qrf_weight_caveat": (
                "HWGT is passed as fit(sample_weight), affecting tree splits and "
                "impurity. quantile-forest's final leaf-frequency quantile "
                "aggregation does not directly reuse HWGT magnitudes."
            ),
            "gbm_weight_caveat": (
                "HWGT weights each estimator's quantile loss during fit."
            ),
            "missing_features": {
                "gbm": "native HistGradientBoosting missing-value routing",
                "qrf": (
                    "unweighted training-deviator median imputation; OOF tail "
                    "fits learn their unweighted imputer within each training fold"
                ),
            },
            "monotonicity": {
                "gbm": (
                    "independent fits are passed through the shipped row-wise "
                    "sorting and 0.5-dollar floor"
                ),
                "qrf": (
                    "all levels are predicted jointly and monotone by "
                    "construction; the same shipped floor/helper is defensive"
                ),
            },
            "export_scope": (
                "in-memory schema-2 per-case vectors; fitted model object size "
                "is irrelevant and excluded"
            ),
            "export_schema_and_vector_shapes_identical": True,
        },
        "provenance": _provenance(
            features,
            metadata_path,
            shipped_results_path,
            train,
            fy2023,
            fy2024,
        ),
        "common_probability_stage": {
            "fit_count_across_benchmark": 1,
            "training_oof_metrics": probability_metrics,
            "shared_predictions_between_estimators": True,
        },
        "shipped_gbm_equivalence": shipped_gbm_equivalence,
        "validity_gates": {
            "shipped_gbm_equivalence": {
                "passed": True,
                "tolerance": shipped_gbm_equivalence["tolerance"],
                "max_absolute_delta": shipped_gbm_equivalence["max_absolute_delta"],
            }
        },
        "simulation_reference": simulation_reference,
        "estimators": estimator_results,
    }
    timing = {
        "fit_order": list(order),
        **estimator_timing,
    }
    return _jsonable(core), timing


def _lower_is_better_gate(
    gate_id: str,
    category: str,
    gbm: float,
    qrf: float,
    *,
    primary: bool = False,
    unit: str,
) -> dict[str, Any]:
    delta = float(qrf - gbm)
    if abs(delta) <= TIE_TOLERANCE:
        winner = "tie"
    elif delta < 0:
        winner = "qrf"
    else:
        winner = "gbm"
    return {
        "id": gate_id,
        "category": category,
        "primary": primary,
        "direction": "lower_is_better",
        "unit": unit,
        "gbm": float(gbm),
        "qrf": float(qrf),
        "delta_qrf_minus_gbm": delta,
        "winner": winner,
    }


def _pass_gate(
    gate_id: str,
    category: str,
    gbm: bool,
    qrf: bool,
) -> dict[str, Any]:
    winner = "tie" if gbm == qrf else ("qrf" if qrf else "gbm")
    return {
        "id": gate_id,
        "category": category,
        "primary": False,
        "direction": "pass_is_better",
        "unit": "boolean",
        "gbm": bool(gbm),
        "qrf": bool(qrf),
        "delta_qrf_minus_gbm": int(qrf) - int(gbm),
        "winner": winner,
    }


def _metric(core: dict[str, Any], estimator: str) -> dict[str, Any]:
    return core["estimators"][estimator]


def _build_verdict(
    core: dict[str, Any],
    runtime: dict[str, Any],
    determinism: dict[str, Any],
) -> dict[str, Any]:
    gbm = _metric(core, "gbm")
    qrf = _metric(core, "qrf")
    gates: list[dict[str, Any]] = []

    for index, level in enumerate(QUANTILE_LEVELS):
        gbm_row = gbm["coverage"]["levels"][index]
        qrf_row = qrf["coverage"]["levels"][index]
        label = str(float(level)).replace("0.", "q").replace(".", "")
        gate = _lower_is_better_gate(
            f"coverage_{label}",
            "coverage",
            abs(float(gbm_row["gap_pp"])),
            abs(float(qrf_row["gap_pp"])),
            unit="percentage_points_absolute_gap",
        )
        gate["gbm_signed_gap_pp"] = float(gbm_row["gap_pp"])
        gate["qrf_signed_gap_pp"] = float(qrf_row["gap_pp"])
        gates.append(gate)

    gates.append(
        _lower_is_better_gate(
            "coverage_mean_absolute_gap",
            "coverage",
            gbm["coverage"]["mean_absolute_gap_pp"],
            qrf["coverage"]["mean_absolute_gap_pp"],
            primary=True,
            unit="percentage_points",
        )
    )
    gates.extend(
        [
            _lower_is_better_gate(
                "pit_absolute_mean_gap",
                "pit",
                abs(gbm["pit"]["mean_gap"]),
                abs(qrf["pit"]["mean_gap"]),
                unit="probability",
            ),
            _lower_is_better_gate(
                "pit_effective_n_scaled_cvm",
                "pit",
                gbm["pit"]["effective_n_scaled_cvm"],
                qrf["pit"]["effective_n_scaled_cvm"],
                unit="statistic",
            ),
        ]
    )

    for specification, label in (
        ("raw_frozen_model", "raw"),
        ("factor_adjusted_frozen_model", "factored"),
    ):
        for weighting, weighting_label in (
            ("equal_jurisdiction", "equal_state"),
            ("issuance_weighted", "issuance_weighted"),
        ):
            gates.append(
                _lower_is_better_gate(
                    f"dollar_{label}_{weighting_label}_mae",
                    "dollar_rate_calibration",
                    gbm["dollar_rate_validation"]["metrics"][specification][weighting][
                        "mae_pp"
                    ],
                    qrf["dollar_rate_validation"]["metrics"][specification][weighting][
                        "mae_pp"
                    ],
                    primary=(
                        specification == "factor_adjusted_frozen_model"
                        and weighting == "equal_jurisdiction"
                    ),
                    unit="percentage_points",
                )
            )

    for state in TARGET_STATES:
        gates.append(
            _lower_is_better_gate(
                f"simulation_{state.lower()}_absolute_sd_gap",
                "simulation_sd",
                gbm["simulation"]["states"][state]["absolute_sd_gap_to_observed_pp"],
                qrf["simulation"]["states"][state]["absolute_sd_gap_to_observed_pp"],
                unit="percentage_points",
            )
        )

    gates.append(
        _lower_is_better_gate(
            "magnitude_runtime",
            "runtime",
            runtime["estimators"]["gbm"]["magnitude_fit_plus_prediction"][
                "median_seconds"
            ],
            runtime["estimators"]["qrf"]["magnitude_fit_plus_prediction"][
                "median_seconds"
            ],
            unit="seconds_median",
        )
    )
    for encoding in ("raw", "gzip"):
        gates.append(
            _lower_is_better_gate(
                f"export_{encoding}_bytes",
                "export",
                gbm["export"][f"{encoding}_bytes"],
                qrf["export"][f"{encoding}_bytes"],
                unit="bytes",
            )
        )
    gates.append(
        _pass_gate(
            "tail_finite_variance",
            "tail",
            gbm["tail"]["finite_variance_gate"]["passed"],
            qrf["tail"]["finite_variance_gate"]["passed"],
        )
    )
    gates.append(
        _pass_gate(
            "determinism_exact_repetition",
            "determinism",
            determinism["estimator_exact_match"]["gbm"],
            determinism["estimator_exact_match"]["qrf"],
        )
    )

    coverage_gate = next(
        gate for gate in gates if gate["id"] == "coverage_mean_absolute_gap"
    )
    calibration_gate = next(
        gate for gate in gates if gate["id"] == "dollar_factored_equal_state_mae"
    )
    coverage_ok = coverage_gate["delta_qrf_minus_gbm"] <= TIE_TOLERANCE
    calibration_ok = calibration_gate["delta_qrf_minus_gbm"] <= TIE_TOLERANCE
    switch = bool(coverage_ok and calibration_ok)
    if switch:
        recommendation = "switch_to_qrf"
        statement = (
            "Switch to QRF: it wins or ties both primary gates—FY2024 mean "
            "absolute coverage gap and FY2023-factor-adjusted FY2024 equal-state "
            "dollar-rate MAE."
        )
    else:
        recommendation = "retain_gbm"
        losses: list[str] = []
        if not coverage_ok:
            losses.append(
                "mean absolute coverage gap by "
                f"{coverage_gate['delta_qrf_minus_gbm']:.6f} pp"
            )
        if not calibration_ok:
            losses.append(
                "factor-adjusted equal-state dollar-rate MAE by "
                f"{calibration_gate['delta_qrf_minus_gbm']:.6f} pp"
            )
        statement = "Retain the shipped GBM: QRF loses " + " and ".join(losses) + "."
    return {
        "tie_tolerance": TIE_TOLERANCE,
        "gates": gates,
        "primary_rule": (
            "recommend switching only when QRF ties or wins both primary "
            "coverage mean-absolute-gap and factor-adjusted equal-state MAE"
        ),
        "primary_gate_results": {
            "coverage_qrf_ties_or_wins": coverage_ok,
            "calibration_qrf_ties_or_wins": calibration_ok,
        },
        "recommendation": recommendation,
        "statement": statement,
    }


def _format_number(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}"


def _winner_label(value: str) -> str:
    return {"gbm": "GBM", "qrf": "QRF", "tie": "Tie"}[value]


def render_markdown(result: dict[str, Any]) -> str:
    """Render the checked-in report deterministically from a result mapping."""
    gbm = result["estimators"]["gbm"]
    qrf = result["estimators"]["qrf"]
    gates = {gate["id"]: gate for gate in result["verdict"]["gates"]}
    lines = [
        "# QRF benchmark against the shipped GBM quantiles",
        "",
        result["verdict"]["statement"],
        "",
        "## Headline head-to-head",
        "",
        "Lower is better for every numeric row.",
        "",
        "| Gate | GBM | QRF | QRF − GBM | Winner |",
        "|---|---:|---:|---:|:---|",
    ]
    headline = (
        ("Mean absolute coverage gap (pp)", "coverage_mean_absolute_gap"),
        ("Absolute PIT mean gap", "pit_absolute_mean_gap"),
        ("PIT effective-n-scaled CvM", "pit_effective_n_scaled_cvm"),
        ("Raw equal-state dollar MAE (pp)", "dollar_raw_equal_state_mae"),
        (
            "FY2023-factored equal-state dollar MAE (pp)",
            "dollar_factored_equal_state_mae",
        ),
        (
            "FY2023-factored issuance-weighted dollar MAE (pp)",
            "dollar_factored_issuance_weighted_mae",
        ),
    )
    for label, gate_id in headline:
        gate = gates[gate_id]
        lines.append(
            f"| {label} | {_format_number(gate['gbm'])} | "
            f"{_format_number(gate['qrf'])} | "
            f"{_format_number(gate['delta_qrf_minus_gbm'])} | "
            f"{_winner_label(gate['winner'])} |"
        )

    equivalence = result["shipped_gbm_equivalence"]
    lines.extend(
        [
            "",
            "## Shipped-GBM equivalence check",
            "",
            (
                "The benchmark's GBM path is compared numerically with the "
                "checked-in `analysis/distributional_results.json` baseline. "
                f"Passed: **{str(equivalence['passed']).lower()}**; maximum "
                f"absolute delta across {len(equivalence['comparisons'])} "
                f"checked metrics: {equivalence['max_absolute_delta']:.3g}."
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## FY2024 weighted conditional-quantile coverage",
            "",
            (
                "Coverage uses HWGT among deviators. Signed gaps are observed "
                "coverage minus the nominal level, in percentage points."
            ),
            "",
            (
                "| Quantile | GBM coverage | GBM gap (pp) | QRF coverage | "
                "QRF gap (pp) | Winner by absolute gap |"
            ),
            "|---:|---:|---:|---:|---:|:---|",
        ]
    )
    for index, level in enumerate(QUANTILE_LEVELS):
        gbm_row = gbm["coverage"]["levels"][index]
        qrf_row = qrf["coverage"]["levels"][index]
        label = str(float(level)).replace("0.", "q").replace(".", "")
        winner = _winner_label(gates[f"coverage_{label}"]["winner"])
        lines.append(
            f"| {float(level):.3f} | "
            f"{100 * float(gbm_row['weighted_coverage']):.2f}% | "
            f"{float(gbm_row['gap_pp']):+.3f} | "
            f"{100 * float(qrf_row['weighted_coverage']):.2f}% | "
            f"{float(qrf_row['gap_pp']):+.3f} | {winner} |"
        )
    for estimator, label in ((gbm, "GBM"), (qrf, "QRF")):
        pattern = estimator["coverage"]["one_sided_pattern"]
        lines.append(
            f"\n{label}: mean absolute gap "
            f"{estimator['coverage']['mean_absolute_gap_pp']:.3f} pp; max "
            f"{estimator['coverage']['max_absolute_gap_pp']:.3f} pp; "
            f"{pattern['negative_gap_count']} negative and "
            f"{pattern['positive_gap_count']} positive signed gaps."
        )

    observed = result["simulation_reference"]["observed_bootstrap"]
    lines.extend(
        [
            "",
            "## Seed-averaged simulated standard deviations",
            "",
            (
                f"Each entry averages {len(SIMULATION_SEEDS)} seeds × "
                f"{SIMULATION_DRAWS:,} draws. Both estimators use the same random "
                "streams; each seed is centered at the official rate and floored "
                "at zero."
            ),
            "",
            (
                "| State | Observed bootstrap SD (pp) | GBM SD (pp) | "
                "GBM abs gap | QRF SD (pp) | QRF abs gap | Winner |"
            ),
            "|:---|---:|---:|---:|---:|---:|:---|",
        ]
    )
    for state in TARGET_STATES:
        gbm_state = gbm["simulation"]["states"][state]
        qrf_state = qrf["simulation"]["states"][state]
        gate = gates[f"simulation_{state.lower()}_absolute_sd_gap"]
        lines.append(
            f"| {state} | {observed[state]['sd_pp']:.4f} | "
            f"{gbm_state['sd_pp']:.4f} | "
            f"{gbm_state['absolute_sd_gap_to_observed_pp']:.4f} | "
            f"{qrf_state['sd_pp']:.4f} | "
            f"{qrf_state['absolute_sd_gap_to_observed_pp']:.4f} | "
            f"{_winner_label(gate['winner'])} |"
        )

    runtime = result["runtime"]["estimators"]
    lines.extend(
        [
            "",
            "## Runtime and export implications",
            "",
            (
                "Run time is observational, alternates estimator order across "
                "repetitions, and is excluded from the deterministic core hash. "
                "Model-object size is excluded: only the identically shaped "
                "exported per-case vectors matter to the shipped consumer."
            ),
            "",
            "| Metric | GBM | QRF | QRF − GBM | Winner |",
            "|---|---:|---:|---:|:---|",
        ]
    )
    runtime_gate = gates["magnitude_runtime"]
    lines.append(
        "| Median magnitude fit + FY2023/FY2024 prediction (s) | "
        f"{runtime_gate['gbm']:.3f} | {runtime_gate['qrf']:.3f} | "
        f"{runtime_gate['delta_qrf_minus_gbm']:+.3f} | "
        f"{_winner_label(runtime_gate['winner'])} |"
    )
    for encoding in ("raw", "gzip"):
        gate = gates[f"export_{encoding}_bytes"]
        lines.append(
            f"| Export {encoding} bytes | {int(gate['gbm']):,} | "
            f"{int(gate['qrf']):,} | {int(gate['delta_qrf_minus_gbm']):+,} | "
            f"{_winner_label(gate['winner'])} |"
        )
    lines.append(
        "\nBoth exports use schema "
        f"{gbm['export']['schema_version']} with vector shape "
        f"{gbm['export']['quantile_vector_shape']}."
    )

    lines.extend(
        [
            "",
            "## Method caveats",
            "",
            (
                "- **Weights:** Both estimators receive HWGT at fit. GBM weights "
                "its quantile losses. QRF sample weights affect split/impurity "
                "fitting, but quantile-forest's final leaf-frequency aggregation "
                "does not directly reuse the HWGT magnitudes."
            ),
            "",
            (
                "- **Missing features:** GBM uses native missing-value routing. "
                "QRF uses unweighted training-deviator median imputation; every "
                "OOF tail fold learns its unweighted imputer only on that fold's "
                "training rows."
            ),
            "",
            (
                "- **Monotonicity:** QRF predicts all nine levels jointly and is "
                "monotone by construction. GBM fits levels independently. Both "
                "pass through the shipped 0.5-dollar floor and row-wise sorting "
                "safeguard."
            ),
            "",
            (
                "- **Tail:** Each estimator separately fits the same q99 "
                "OOF-median log-residual mean-excess tail and attaches it above "
                f"its own q99. GBM scale is {gbm['tail']['scale_log']:.4f}; QRF "
                f"scale is {qrf['tail']['scale_log']:.4f}. Both must pass the "
                f"point-scale <{MAX_TAIL_SCALE:.2f} and upper-95 <0.5 "
                "finite-variance gate."
            ),
            "",
            (
                "- **Caps and calibration:** Both use the same per-case physical "
                "cap. FY2023 state factors are refit separately for each frozen "
                "estimator before FY2024 evaluation."
            ),
            "",
            "## Determinism",
            "",
            (
                "Exact deterministic-core SHA-256 match across "
                f"{result['determinism']['repetitions']} repetitions: "
                f"**{str(result['determinism']['exact_match']).lower()}**. Hash: "
                f"`{result['determinism']['core_sha256_by_repetition'][0]}`. "
                "Timings are not part of this hash."
            ),
            "",
            "## Recommendation",
            "",
            result["verdict"]["statement"],
            "",
            (
                "The decision rule is fixed in advance: switch only if QRF ties "
                "or wins both mean absolute FY2024 coverage gap and "
                "factor-adjusted equal-state FY2024 dollar-rate MAE."
            ),
            "",
        ]
    )
    # Reference this so a malformed runtime structure is caught by rendering.
    if not runtime:
        raise ValueError("runtime estimator summary must not be empty")
    return "\n".join(lines)


def run_benchmark(
    *,
    metadata_path: str | Path = APP_METADATA,
    shipped_results_path: str | Path = DEFAULT_SHIPPED_RESULTS,
    repetitions: int = 2,
) -> dict[str, Any]:
    """Run repeated deterministic cores and return a strict result mapping."""
    if repetitions < 2:
        raise ValueError("repetitions must be at least 2")
    metadata = Path(metadata_path)
    if not metadata.is_file():
        raise FileNotFoundError(f"metadata file does not exist: {metadata}")
    shipped_path = Path(shipped_results_path)
    if not shipped_path.is_file():
        raise FileNotFoundError(
            f"shipped GBM result file does not exist: {shipped_path}"
        )
    shipped_results = _load_json_object(shipped_path, "shipped GBM results")
    data = assemble()
    data["case"] = 1
    features = _feature_columns(data)
    training_years = [year for year in YEARS_TRAIN if year < 2023]
    train = data.loc[data["year"].isin(training_years)].copy()
    fy2023 = data.loc[data["year"].eq(2023)].copy()
    fy2024 = data.loc[data["year"].eq(YEAR_TEST)].copy()

    # The hurdle is deliberately fit only once, then held byte-for-byte common
    # across both estimators and every repeated magnitude benchmark core.
    probability = _fit_probability_stage(
        train,
        features,
        "deviates",
        RANDOM_STATE,
    )
    p_dev_2023 = probability.predict(fy2023[features])
    p_dev_2024 = probability.predict(fy2024[features])

    cores: list[dict[str, Any]] = []
    timing_records: list[dict[str, Any]] = []
    for repetition in range(repetitions):
        print(f"benchmark repetition {repetition + 1}/{repetitions}")
        core, timing = _run_once(
            train,
            fy2023,
            fy2024,
            features,
            p_dev_2023,
            p_dev_2024,
            probability.oof_metrics,
            metadata,
            shipped_path,
            shipped_results,
            repetition,
        )
        cores.append(core)
        timing_records.append(timing)

    core_hashes = [_sha256(core) for core in cores]
    estimator_hashes = {
        estimator: [_sha256(core["estimators"][estimator]) for core in cores]
        for estimator in ("gbm", "qrf")
    }
    determinism = {
        "repetitions": repetitions,
        "hash_algorithm": "sha256 over sorted compact strict JSON",
        "timing_excluded": True,
        "core_sha256_by_repetition": core_hashes,
        "exact_match": len(set(core_hashes)) == 1,
        "estimator_sha256_by_repetition": estimator_hashes,
        "estimator_exact_match": {
            estimator: len(set(hashes)) == 1
            for estimator, hashes in estimator_hashes.items()
        },
    }
    runtime = _runtime_summary(timing_records)
    result = dict(cores[0])
    result["runtime"] = runtime
    result["determinism"] = determinism
    result["verdict"] = _build_verdict(result, runtime, determinism)
    return _jsonable(result)


def _ensure_not_app_output(path: Path) -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    destination = path.resolve()
    if destination == app_root or app_root in destination.parents:
        raise ValueError(f"benchmark reports must not be written under app/: {path}")


def write_reports(
    result: dict[str, Any],
    *,
    json_path: str | Path = DEFAULT_JSON,
    markdown_path: str | Path = DEFAULT_MARKDOWN,
) -> None:
    """Write strict JSON and its deterministic Markdown rendering."""
    json_destination = Path(json_path)
    markdown_destination = Path(markdown_path)
    for destination in (json_destination, markdown_destination):
        _ensure_not_app_output(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
    with json_destination.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
    markdown_destination.write_text(
        render_markdown(result),
        encoding="utf-8",
        newline="\n",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON,
        help=f"strict JSON result path (default: {DEFAULT_JSON})",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=DEFAULT_MARKDOWN,
        help=f"Markdown report path (default: {DEFAULT_MARKDOWN})",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        default=APP_METADATA,
        help="read-only state official-rate metadata path",
    )
    parser.add_argument(
        "--shipped-results-path",
        type=Path,
        default=DEFAULT_SHIPPED_RESULTS,
        help="checked-in shipped GBM result used for equivalence deltas",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=2,
        help="full deterministic repetitions; must be at least 2",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    result = run_benchmark(
        metadata_path=args.metadata_path,
        shipped_results_path=args.shipped_results_path,
        repetitions=args.repetitions,
    )
    write_reports(
        result,
        json_path=args.json_output,
        markdown_path=args.markdown_output,
    )
    print(f"wrote {args.json_output}")
    print(f"wrote {args.markdown_output}")
    return result


if __name__ == "__main__":
    main()
