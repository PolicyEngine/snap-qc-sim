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
TAIL_METHOD = "weighted_exponential_above_q99_fitted_to_top_decile_oof_log_residuals"
REQUIRED_COLUMNS = ("case", "state", "w", "issuance", "p_dev", "p_pos")
ARRAY_KEYS = ("w", "iss", "p_dev", "p_pos", "q")


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

    numeric_columns = ("w", "issuance", "p_dev", "p_pos", *quantile_columns)
    for column in numeric_columns:
        validated[column] = _numeric_column(validated, column)
    if not validated["w"].gt(0).all():
        raise ValueError("w must contain only positive weights")
    if not validated["issuance"].ge(0).all():
        raise ValueError("issuance must contain only nonnegative values")
    for column in ("p_dev", "p_pos"):
        if not validated[column].between(0, 1, inclusive="both").all():
            raise ValueError(f"{column} must contain probabilities in [0, 1]")

    quantiles = validated.loc[:, quantile_columns].to_numpy(dtype=float)
    if (np.diff(quantiles, axis=1) < 0).any():
        raise ValueError("Predicted log quantiles must be monotone within every case")
    return validated


def _build_states(
    predictions: pd.DataFrame,
    metadata: dict[str, dict[str, Any]],
    quantile_columns: tuple[str, ...],
    *,
    q_decimals: int | None = None,
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for state in sorted(metadata):
        rows = predictions.loc[predictions["state"].eq(state)]
        weights = rows["w"].to_numpy(dtype=float)
        issuance = rows["issuance"].to_numpy(dtype=float)
        quantiles = rows.loc[:, quantile_columns].to_numpy(dtype=float)
        state_data = {
            "official": metadata[state]["official"],
            "issuance": round(float(np.dot(weights, issuance))),
            "n": len(rows),
            "verified": metadata[state]["verified"],
            "w": [_round_significant(value) for value in weights],
            "iss": [_round_significant(value) for value in issuance],
            "p_dev": [_round_significant(value) for value in rows["p_dev"]],
            "p_pos": [_round_significant(value) for value in rows["p_pos"]],
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
    deviation_tolerance: float,
    states: dict[str, dict[str, Any]],
    q_encoding: dict[str, Any],
) -> dict[str, Any]:
    return {
        "threshold": float(threshold),
        "quantile_levels": list(quantile_levels),
        "tail_scale_log": float(tail_scale),
        "tail_method": TAIL_METHOD,
        "deviation_tolerance": float(deviation_tolerance),
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


def build_model_data(
    predictions: pd.DataFrame,
    *,
    tail_scale: float,
    output_path: Path,
    metadata_path: Path = Path("app/public/data.json"),
    threshold: float = 56,
    deviation_tolerance: float = 0.5,
    quantile_levels: Sequence[float] = QUANTILE_LEVELS,
    quantile_columns: Sequence[str] = QUANTILE_COLUMNS,
) -> dict[str, Any]:
    """Validate predictions and write a deterministic browser-ready JSON export.

    Quantiles encode natural-log dollars. All numeric arrays initially use four
    significant figures. If that compact JSON exceeds 2.5 MB, only the quantile
    arrays switch to two decimal places in log dollars, and ``q_encoding`` records
    the fallback.
    """
    levels, columns = _validate_quantile_schema(quantile_levels, quantile_columns)
    if not math.isfinite(float(tail_scale)) or not 0 < float(tail_scale) < 1:
        raise ValueError("tail_scale must be finite and strictly between zero and one")
    if not math.isfinite(float(threshold)) or float(threshold) <= 0:
        raise ValueError("threshold must be finite and positive")
    if not math.isfinite(float(deviation_tolerance)) or float(deviation_tolerance) < 0:
        raise ValueError("deviation_tolerance must be finite and nonnegative")

    metadata_path = Path(metadata_path)
    metadata = _load_metadata(metadata_path)
    validated = _validated_predictions(
        predictions,
        quantile_columns=columns,
        metadata_states=set(metadata),
    )
    states = _build_states(validated, metadata, columns)
    payload = _payload(
        threshold=threshold,
        quantile_levels=levels,
        tail_scale=tail_scale,
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
                columns,
                q_decimals=2,
            ),
            q_encoding={"rounding": "decimal_places", "digits": 2},
        )
        encoded = _encode(payload)
        used_decimal_quantization = True

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encoded)
    gzip_bytes = len(gzip.compress(encoded, mtime=0))
    return {
        "data": payload,
        "raw_bytes": len(encoded),
        "gzip_bytes": gzip_bytes,
        "q_decimal_quantization": 2 if used_decimal_quantization else None,
        "output_path": str(output_path),
    }


def main() -> None:
    """Fit/load FY2024 predictions and write app/public/model_data.json."""
    from analysis import distributional_deviation_model

    predictions, tail_scale = distributional_deviation_model.predictions_for_export()
    path = Path("app/public/model_data.json")
    report = build_model_data(
        predictions,
        tail_scale=tail_scale,
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
