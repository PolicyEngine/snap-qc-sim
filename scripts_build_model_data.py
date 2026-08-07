"""Build the self-contained FY2024 distributional model export for the app."""

from __future__ import annotations

import copy
import gzip
import json
import math
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis.predictive_process import MAX_TAIL_SCALE, TAIL_SCALE_MARGIN

QUANTILE_LEVELS = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975, 0.99)
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

MAX_RAW_BYTES = 2_500_000
TAIL_METHOD = (
    "weighted_exponential_above_q99_fitted_to_q99_oof_median_log_residual_excess"
)
REQUIRED_COLUMNS = (
    "case",
    "state",
    "w",
    "issuance",
    "p_dev",
    "D",
    "benmax",
    "deviation_cap",
)
# p_pos is intentionally absent: browser rate outputs consume |D|, not sign.
ARRAY_KEYS = ("w", "iss", "p_dev", "cap", "q")
LEVEL_RATIO_BOUNDS = (0.7, 1.4)


def _round_significant(value: float, digits: int = 4) -> float:
    rounded = float(f"{float(value):.{digits}g}")
    return 0.0 if rounded == 0 else rounded


def _round_decimal(value: float, decimals: int) -> float:
    rounded = round(float(value), decimals)
    return 0.0 if rounded == 0 else rounded


def _quantize_log_quantiles(
    states: dict[str, dict[str, Any]], *, decimals: int
) -> dict[str, dict[str, Any]]:
    """Return a deep copy with only log-dollar quantiles decimal-quantized."""
    quantized = copy.deepcopy(states)
    for state in quantized.values():
        state["q"] = [
            [_round_decimal(value, decimals) for value in row] for row in state["q"]
        ]
    return quantized


def _load_metadata(path: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read metadata from {path}: {error}") from error

    states = payload.get("states")
    if not isinstance(states, dict) or not states:
        raise ValueError(f"Metadata {path} must contain a nonempty states object")
    for state, metadata in states.items():
        if not isinstance(metadata, dict):
            raise TypeError(f"Metadata for {state} must be an object")
        missing = {"official", "verified"} - metadata.keys()
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"Metadata for {state} is missing: {names}")
    return states


def _validated_state_metadata(
    state_factors: pd.DataFrame,
    state_diagnostics: pd.DataFrame,
    metadata_states: set[str],
) -> pd.DataFrame:
    """Validate one factor and FY2024 level diagnostic per jurisdiction."""
    if not isinstance(state_factors, pd.DataFrame):
        raise TypeError("state_factors must be a pandas DataFrame")
    if not isinstance(state_diagnostics, pd.DataFrame):
        raise TypeError("state_diagnostics must be a pandas DataFrame")
    factor_required = {"state", "state_factor"}
    diagnostic_required = {
        "state",
        "raw_model_to_observed_ratio",
        "adjusted_model_to_observed_ratio",
        "adjusted_ratio_outside_0_7_to_1_4",
    }
    missing_factors = factor_required - set(state_factors.columns)
    missing_diagnostics = diagnostic_required - set(state_diagnostics.columns)
    if missing_factors:
        raise ValueError(
            f"state_factors is missing: {', '.join(sorted(missing_factors))}"
        )
    if missing_diagnostics:
        raise ValueError(
            f"state_diagnostics is missing: {', '.join(sorted(missing_diagnostics))}"
        )
    for name, frame in (
        ("state_factors", state_factors),
        ("state_diagnostics", state_diagnostics),
    ):
        if frame["state"].duplicated().any():
            duplicates = sorted(frame.loc[frame["state"].duplicated(), "state"])
            raise ValueError(f"{name} contains duplicate states: {duplicates}")
        states = set(frame["state"])
        if states != metadata_states:
            raise ValueError(
                f"{name} state set does not match metadata; "
                f"missing={sorted(metadata_states - states)}, "
                f"extra={sorted(states - metadata_states)}"
            )

    factors = state_factors[["state", "state_factor"]].copy()
    diagnostics = state_diagnostics[list(diagnostic_required)].copy()
    combined = factors.merge(diagnostics, on="state", validate="one_to_one")
    for column in (
        "state_factor",
        "raw_model_to_observed_ratio",
        "adjusted_model_to_observed_ratio",
    ):
        combined[column] = pd.to_numeric(combined[column], errors="coerce")
        if not np.isfinite(combined[column]).all() or (combined[column] <= 0).any():
            raise ValueError(f"{column} must contain finite positive values")
    lower, upper = LEVEL_RATIO_BOUNDS
    expected_flag = ~combined["adjusted_model_to_observed_ratio"].between(
        lower, upper, inclusive="both"
    )
    supplied_flag = combined["adjusted_ratio_outside_0_7_to_1_4"]
    if not supplied_flag.map(lambda value: isinstance(value, (bool, np.bool_))).all():
        raise TypeError("state level flags must contain only boolean values")
    actual_flag = supplied_flag.astype(bool)
    if not actual_flag.equals(expected_flag):
        raise ValueError("state level flags do not match the configured ratio gate")
    combined["adjusted_ratio_outside_0_7_to_1_4"] = actual_flag
    return combined.sort_values("state").reset_index(drop=True)


def _validate_quantile_schema(
    quantile_levels: Sequence[float], quantile_columns: Sequence[str]
) -> tuple[tuple[float, ...], tuple[str, ...]]:
    levels = tuple(float(level) for level in quantile_levels)
    columns = tuple(quantile_columns)
    if len(levels) != len(columns):
        raise ValueError(
            "quantile_levels and quantile_columns must have the same length"
        )
    if len(levels) != 9:
        raise ValueError("The model export requires exactly nine quantiles")
    if len(set(columns)) != len(columns):
        raise ValueError("quantile_columns must be unique")
    if any(not math.isfinite(level) or not 0 < level < 1 for level in levels):
        raise ValueError(
            "quantile_levels must be finite probabilities between zero and one"
        )
    if any(right <= left for left, right in pairwise(levels)):
        raise ValueError("quantile_levels must be strictly increasing")
    return levels, columns


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce").astype(float)
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError(f"{column} must contain only finite numeric values")
    return values


def _validated_predictions(
    predictions: pd.DataFrame,
    *,
    quantile_columns: tuple[str, ...],
    metadata_states: set[str],
) -> pd.DataFrame:
    if not isinstance(predictions, pd.DataFrame):
        raise TypeError("predictions must be a pandas DataFrame")

    required = set(REQUIRED_COLUMNS) | set(quantile_columns)
    missing = required - set(predictions.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"predictions is missing required columns: {names}")

    validated = predictions.copy()
    validated["case"] = _numeric_column(validated, "case")
    if not validated["case"].eq(1).all():
        raise ValueError("Model-data predictions must contain only case == 1 rows")

    if (
        validated["state"].isna().any()
        or not validated["state"]
        .map(lambda value: isinstance(value, str) and bool(value))
        .all()
    ):
        raise ValueError("state must contain nonempty strings")
    prediction_states = set(validated["state"])
    if prediction_states != metadata_states:
        missing_states = sorted(metadata_states - prediction_states)
        extra_states = sorted(prediction_states - metadata_states)
        raise ValueError(
            "Prediction state set does not match metadata; "
            f"missing={missing_states}, extra={extra_states}"
        )

    numeric_columns = (
        "w",
        "issuance",
        "p_dev",
        "D",
        "benmax",
        "deviation_cap",
        *quantile_columns,
    )
    for column in numeric_columns:
        validated[column] = _numeric_column(validated, column)
    if not validated["w"].gt(0).all():
        raise ValueError("w must contain only positive weights")
    if not validated["issuance"].ge(0).all():
        raise ValueError("issuance must contain only nonnegative values")
    if not validated["p_dev"].between(0, 1, inclusive="both").all():
        raise ValueError("p_dev must contain probabilities in [0, 1]")
    if not validated["deviation_cap"].gt(0).all():
        raise ValueError("deviation_cap must contain positive dollar values")
    if not validated["benmax"].gt(0).all():
        raise ValueError("benmax must contain positive dollar values")
    caps = validated["deviation_cap"].to_numpy(dtype=float)
    if not np.allclose(caps, np.round(caps), rtol=0, atol=1e-9):
        raise ValueError("deviation_cap must contain whole-dollar source values")
    expected_caps = np.maximum(
        validated["benmax"].to_numpy(dtype=float),
        validated["D"].abs().to_numpy(dtype=float),
    )
    if not np.allclose(caps, expected_caps, rtol=0, atol=1e-9):
        raise ValueError("deviation_cap must equal max(benmax, abs(D)) per case-year")

    quantiles = validated.loc[:, quantile_columns].to_numpy(dtype=float)
    if (np.diff(quantiles, axis=1) < 0).any():
        raise ValueError("Predicted log quantiles must be monotone within every case")
    return validated


def _build_states(
    predictions: pd.DataFrame,
    metadata: dict[str, dict[str, Any]],
    state_metadata: pd.DataFrame,
    quantile_columns: tuple[str, ...],
    *,
    q_decimals: int | None = None,
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    state_metadata = state_metadata.set_index("state")
    for state in sorted(metadata):
        rows = predictions.loc[predictions["state"].eq(state)]
        weights = rows["w"].to_numpy(dtype=float)
        issuance = rows["issuance"].to_numpy(dtype=float)
        caps = rows["deviation_cap"].to_numpy(dtype=float)
        quantiles = rows.loc[:, quantile_columns].to_numpy(dtype=float)
        diagnostics = state_metadata.loc[state]
        state_data = {
            "official": metadata[state]["official"],
            "issuance": round(float(np.dot(weights, issuance))),
            "n": len(rows),
            "verified": metadata[state]["verified"],
            "factor": _round_significant(diagnostics["state_factor"], digits=6),
            "raw_level_ratio": _round_significant(
                diagnostics["raw_model_to_observed_ratio"], digits=6
            ),
            "level_ratio": _round_significant(
                diagnostics["adjusted_model_to_observed_ratio"], digits=6
            ),
            "level_flag": bool(diagnostics["adjusted_ratio_outside_0_7_to_1_4"]),
            "w": [_round_significant(value) for value in weights],
            "iss": [_round_significant(value) for value in issuance],
            "p_dev": [_round_significant(value) for value in rows["p_dev"]],
            "cap": [round(value) for value in caps],
            "q": [
                [
                    _round_significant(value)
                    if q_decimals is None
                    else _round_decimal(value, q_decimals)
                    for value in quantile_row
                ]
                for quantile_row in quantiles
            ],
        }
        lengths = {len(state_data[key]) for key in ARRAY_KEYS}
        if lengths != {state_data["n"]}:
            raise ValueError(f"Unequal per-case array lengths for {state}")
        states[state] = state_data
    return states


def _payload(
    *,
    threshold: float,
    quantile_levels: tuple[float, ...],
    tail_scale: float,
    tail_scale_se: float,
    deviation_tolerance: float,
    states: dict[str, dict[str, Any]],
    q_encoding: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "threshold": float(threshold),
        "quantile_levels": list(quantile_levels),
        "tail_scale_log": float(tail_scale),
        "tail_scale_se_log": float(tail_scale_se),
        "implied_pareto_tail_index": 1 / float(tail_scale),
        "tail_method": TAIL_METHOD,
        "finite_variance_gate": {
            "point_scale_upper_bound_exclusive": MAX_TAIL_SCALE,
            "mathematical_limit_exclusive": 0.5,
            "fixed_regression_margin": TAIL_SCALE_MARGIN,
            "upper_95_log_scale": float(tail_scale + 1.96 * tail_scale_se),
        },
        "deviation_tolerance": float(deviation_tolerance),
        "deviation_cap": {
            "array_key": "cap",
            "units": "dollars",
            "rule": "max(BENMAX, abs(RAWBEN - BENFIX)) per case-year",
            "application": "clip final abs(D) before strict thresholding",
        },
        "state_factor": {
            "scalar_key": "factor",
            "model_training_years": [2017, 2018, 2019, 2022],
            "fit_year": 2023,
            "validation_year": 2024,
            "eb_prior_mean": 1.0,
            "application": "multiply capped error dollars after strict threshold",
        },
        "level_ratio_gate": {
            "scalar_key": "level_ratio",
            "flag_key": "level_flag",
            "inclusive_bounds": list(LEVEL_RATIO_BOUNDS),
            "ratio": "factor-adjusted analytic model / observed FY2024 sample",
        },
        "operation_order": [
            "draw_abs_D",
            "cap_abs_D",
            "strict_threshold",
            "multiply_state_factor",
            "anchor_at_model_baseline_mean",
            "clip_rate_at_zero",
        ],
        "anchored_rate_floor_pct": 0.0,
        "p_pos_exported": False,
        "p_pos_omission_reason": (
            "measured error-rate outputs consume abs(D); sign is retained only "
            "in analysis"
        ),
        "q_units": "natural_log_dollars",
        "q_encoding": q_encoding,
        "states": states,
    }


def _encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def prepare_model_data(
    predictions: pd.DataFrame,
    *,
    tail_scale: float,
    tail_scale_se: float,
    state_factors: pd.DataFrame,
    state_diagnostics: pd.DataFrame,
    metadata_path: Path = Path("app/public/data.json"),
    threshold: float = 56,
    deviation_tolerance: float = 0.5,
    quantile_levels: Sequence[float] = QUANTILE_LEVELS,
    quantile_columns: Sequence[str] = QUANTILE_COLUMNS,
) -> dict[str, Any]:
    """Validate predictions and prepare deterministic browser-ready JSON bytes.

    Quantiles encode natural-log dollars. All numeric arrays initially use four
    significant figures. If that compact JSON exceeds 2.5 MB, only the quantile
    arrays switch to two decimal places in log dollars, and ``q_encoding`` records
    the fallback.
    """
    levels, columns = _validate_quantile_schema(quantile_levels, quantile_columns)
    if (
        not math.isfinite(float(tail_scale))
        or not 0 < float(tail_scale) < MAX_TAIL_SCALE
    ):
        raise ValueError(
            f"tail_scale must be finite, positive, and below {MAX_TAIL_SCALE:.2f}"
        )
    if not math.isfinite(float(tail_scale_se)) or float(tail_scale_se) <= 0:
        raise ValueError("tail_scale_se must be finite and positive")
    if float(tail_scale) + 1.96 * float(tail_scale_se) >= 0.5:
        raise ValueError("tail scale uncertainty reaches the finite-variance boundary")
    if not math.isfinite(float(threshold)) or float(threshold) <= 0:
        raise ValueError("threshold must be finite and positive")
    if not math.isfinite(float(deviation_tolerance)) or float(deviation_tolerance) < 0:
        raise ValueError("deviation_tolerance must be finite and nonnegative")

    metadata_path = Path(metadata_path)
    metadata = _load_metadata(metadata_path)
    state_metadata = _validated_state_metadata(
        state_factors,
        state_diagnostics,
        set(metadata),
    )
    validated = _validated_predictions(
        predictions,
        quantile_columns=columns,
        metadata_states=set(metadata),
    )
    if (validated["deviation_cap"] < deviation_tolerance).any():
        raise ValueError("deviation_cap must be at least deviation_tolerance")
    states = _build_states(validated, metadata, state_metadata, columns)
    payload = _payload(
        threshold=threshold,
        quantile_levels=levels,
        tail_scale=tail_scale,
        tail_scale_se=tail_scale_se,
        deviation_tolerance=deviation_tolerance,
        states=states,
        q_encoding={"rounding": "significant_figures", "digits": 4},
    )
    encoded = _encode(payload)
    used_decimal_quantization = False
    if len(encoded) > MAX_RAW_BYTES:
        payload = _payload(
            threshold=threshold,
            quantile_levels=levels,
            tail_scale=tail_scale,
            deviation_tolerance=deviation_tolerance,
            states=_build_states(
                validated,
                metadata,
                state_metadata,
                columns,
                q_decimals=2,
            ),
            tail_scale_se=tail_scale_se,
            q_encoding={"rounding": "decimal_places", "digits": 2},
        )
        encoded = _encode(payload)
        used_decimal_quantization = True

    gzip_bytes = len(gzip.compress(encoded, mtime=0))
    return {
        "data": payload,
        "encoded": encoded,
        "raw_bytes": len(encoded),
        "gzip_bytes": gzip_bytes,
        "q_decimal_quantization": 2 if used_decimal_quantization else None,
    }


def build_model_data(
    predictions: pd.DataFrame,
    *,
    tail_scale: float,
    tail_scale_se: float,
    state_factors: pd.DataFrame,
    state_diagnostics: pd.DataFrame,
    output_path: Path,
    metadata_path: Path = Path("app/public/data.json"),
    threshold: float = 56,
    deviation_tolerance: float = 0.5,
    quantile_levels: Sequence[float] = QUANTILE_LEVELS,
    quantile_columns: Sequence[str] = QUANTILE_COLUMNS,
) -> dict[str, Any]:
    """Prepare and write a deterministic browser-ready JSON export."""
    prepared = prepare_model_data(
        predictions,
        tail_scale=tail_scale,
        tail_scale_se=tail_scale_se,
        state_factors=state_factors,
        state_diagnostics=state_diagnostics,
        metadata_path=metadata_path,
        threshold=threshold,
        deviation_tolerance=deviation_tolerance,
        quantile_levels=quantile_levels,
        quantile_columns=quantile_columns,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(prepared["encoded"])
    return {key: value for key, value in prepared.items() if key != "encoded"} | {
        "output_path": str(output_path)
    }


def main() -> None:
    """Fit/load FY2024 predictions and write app/public/model_data.json."""
    from analysis import distributional_deviation_model

    (
        predictions,
        tail,
        state_factors,
        state_diagnostics,
    ) = distributional_deviation_model.predictions_for_export()
    path = Path("app/public/model_data.json")
    report = build_model_data(
        predictions,
        tail_scale=tail.scale,
        tail_scale_se=tail.scale_se,
        state_factors=state_factors,
        state_diagnostics=state_diagnostics,
        output_path=path,
        threshold=distributional_deviation_model.THRESHOLD[
            distributional_deviation_model.YEAR_TEST
        ],
        deviation_tolerance=(distributional_deviation_model.DEVIATION_TOLERANCE),
        quantile_levels=distributional_deviation_model.QUANTILE_LEVELS,
        quantile_columns=distributional_deviation_model.QUANTILE_COLUMNS,
    )
    quantization = report["q_decimal_quantization"]
    quantization_note = (
        f", q rounded to {quantization} log-dollar decimals"
        if quantization is not None
        else ""
    )
    print(
        f"{path}: {report['raw_bytes'] / 1e6:.3f} MB raw, "
        f"{report['gzip_bytes'] / 1e6:.3f} MB gzip, "
        f"{len(report['data']['states'])} states{quantization_note}"
    )


if __name__ == "__main__":
    main()
