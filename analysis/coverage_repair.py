"""Deterministic post-hoc dispersion repair for the frozen GBM distribution."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__:
    from .distributional_deviation_model import (
        DEVIATION_TOLERANCE,
        QUANTILE_COLUMNS,
        _dollar_factor_validation,
        weighted_pit_summary,
        weighted_quantile_coverage,
    )
    from .hurdle_deviation_model import (
        RANDOM_STATE,
        _feature_columns,
        _fit_probability_stage,
        assemble,
    )
    from .predictive_process import (
        QUANTILE_LEVELS,
        enforce_monotone_quantiles,
        expected_error_dollars,
    )
    from .qrf_benchmark import _fit_gbm_magnitude, _predict_gbm_quantiles
    from .train_error_model import (
        BBCE_PATH,
        MEDICARE_PART_B_PATH,
        QC_DIR,
        SMD_PATH,
        YEAR_TEST,
        YEARS_TRAIN,
    )
else:
    from distributional_deviation_model import (
        DEVIATION_TOLERANCE,
        QUANTILE_COLUMNS,
        _dollar_factor_validation,
        weighted_pit_summary,
        weighted_quantile_coverage,
    )
    from hurdle_deviation_model import (
        RANDOM_STATE,
        _feature_columns,
        _fit_probability_stage,
        assemble,
    )
    from predictive_process import (
        QUANTILE_LEVELS,
        enforce_monotone_quantiles,
        expected_error_dollars,
    )
    from qrf_benchmark import _fit_gbm_magnitude, _predict_gbm_quantiles
    from train_error_model import (
        BBCE_PATH,
        MEDICARE_PART_B_PATH,
        QC_DIR,
        SMD_PATH,
        YEAR_TEST,
        YEARS_TRAIN,
    )


OUT = Path(__file__).with_name("coverage_repair_results.json")
BASELINE_RESULTS = Path(__file__).with_name("distributional_results.json")
PROTOCOL = Path(__file__).with_name("COVERAGE_REPAIR_PROTOCOL.md")
TRAINING_YEARS = tuple(int(year) for year in YEARS_TRAIN)
MECHANISMS = ("conformal_remap", "spread_inflation", "both")
TIE_ORDER = {name: index for index, name in enumerate(MECHANISMS)}
SPREAD_GRID = np.round(np.arange(0.5, 3.0001, 0.001), 3)
TIE_TOLERANCE = 1e-12
MATERIAL_IMPROVEMENT_PP = 0.25
MAE_GUARD_ALLOWANCE_PP = 0.05
BASELINE_MAE_PP = 0.9311800033868244
BASELINE_SIGN_AUC_RAW = 0.6993960587007345
BASELINE_SIGN_AUC_CALIBRATED = 0.6997568121541028
MODULE_FILES = (
    "coverage_repair.py",
    "distributional_deviation_model.py",
    "hurdle_deviation_model.py",
    "predictive_process.py",
    "qrf_benchmark.py",
    "train_error_model.py",
)


def _jsonable(value: Any) -> Any:
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
        raise ValueError("coverage-repair result contains a nonfinite float")
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _interpolate_levels(
    matrix: np.ndarray, levels: np.ndarray, tail_scale: float
) -> np.ndarray:
    """Evaluate row-wise log quantiles at arbitrary monotone levels."""
    quantiles = np.asarray(matrix, dtype=float)
    requested = np.asarray(levels, dtype=float)
    if quantiles.ndim != 2 or quantiles.shape[1] != len(QUANTILE_LEVELS):
        raise ValueError("quantile matrix has the wrong shape")
    if requested.shape != QUANTILE_LEVELS.shape:
        raise ValueError("requested levels have the wrong shape")
    if (
        (np.diff(requested) < 0).any()
        or (requested < 0).any()
        or (requested >= 1).any()
    ):
        raise ValueError("requested levels must be monotone in [0, 1)")

    result = np.empty((len(quantiles), len(requested)), dtype=float)
    floor = math.log(DEVIATION_TOLERANCE)
    for index, level in enumerate(requested):
        if level <= QUANTILE_LEVELS[0]:
            fraction = float(level / QUANTILE_LEVELS[0])
            result[:, index] = floor + fraction * (quantiles[:, 0] - floor)
        elif level <= QUANTILE_LEVELS[-1]:
            upper = int(np.searchsorted(QUANTILE_LEVELS, level, side="left"))
            if QUANTILE_LEVELS[upper] == level:
                result[:, index] = quantiles[:, upper]
            else:
                lower = upper - 1
                fraction = float(
                    (level - QUANTILE_LEVELS[lower])
                    / (QUANTILE_LEVELS[upper] - QUANTILE_LEVELS[lower])
                )
                result[:, index] = quantiles[:, lower] + fraction * (
                    quantiles[:, upper] - quantiles[:, lower]
                )
        else:
            result[:, index] = quantiles[:, -1] - tail_scale * math.log(
                (1 - float(level)) / (1 - float(QUANTILE_LEVELS[-1]))
            )
    return enforce_monotone_quantiles(result, minimum_magnitude=DEVIATION_TOLERANCE)


def _fit_remap(oof: pd.DataFrame) -> dict[str, Any]:
    coverage = weighted_quantile_coverage(oof)
    empirical = np.asarray([row["weighted_coverage"] for row in coverage])
    empirical = np.maximum.accumulate(np.r_[0.0, empirical, 1.0])
    source = np.r_[0.0, QUANTILE_LEVELS, 1.0]
    unique_coverage: list[float] = []
    largest_source: list[float] = []
    for coverage_value, source_value in zip(empirical, source, strict=True):
        if unique_coverage and coverage_value == unique_coverage[-1]:
            largest_source[-1] = float(source_value)
        else:
            unique_coverage.append(float(coverage_value))
            largest_source.append(float(source_value))
    remapped = np.interp(QUANTILE_LEVELS, unique_coverage, largest_source)
    remapped = np.minimum(remapped, 1 - 1e-12)
    return {
        "source_levels": remapped.tolist(),
        "oof_source_level_coverage": coverage,
        "inverse_curve_coverage": unique_coverage,
        "inverse_curve_source_levels": largest_source,
    }


def _coverage_by_spread(
    observed: np.ndarray,
    median: np.ndarray,
    quantile: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    delta = quantile - median
    centered = observed - median
    total = float(weights.sum())
    result = np.zeros(len(SPREAD_GRID), dtype=float)
    zero = np.isclose(delta, 0.0, rtol=0.0, atol=1e-14)
    result += float(weights[zero & (centered <= 0)].sum())
    for positive in (True, False):
        selected = (delta > 0) if positive else (delta < 0)
        if not selected.any():
            continue
        threshold = centered[selected] / delta[selected]
        selected_weights = weights[selected]
        order = np.argsort(threshold, kind="mergesort")
        threshold = threshold[order]
        cumulative = np.cumsum(selected_weights[order])
        if positive:
            positions = np.searchsorted(threshold, SPREAD_GRID, side="right") - 1
            valid = positions >= 0
            result[valid] += cumulative[positions[valid]]
        else:
            positions = np.searchsorted(threshold, SPREAD_GRID, side="left")
            before = np.zeros(len(SPREAD_GRID), dtype=float)
            valid = positions > 0
            before[valid] = cumulative[positions[valid] - 1]
            result += cumulative[-1] - before
    return result / total


def _fit_spread_factor(frame: pd.DataFrame) -> tuple[float, float]:
    observed = np.log(frame["D"].abs()).to_numpy(dtype=float)
    weights = frame["w"].to_numpy(dtype=float)
    matrix = frame[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
    median = matrix[:, 3]
    gaps = []
    for index, level in enumerate(QUANTILE_LEVELS):
        coverage = _coverage_by_spread(observed, median, matrix[:, index], weights)
        gaps.append(np.abs(100 * (coverage - float(level))))
    loss = np.mean(np.column_stack(gaps), axis=1)
    best = float(loss.min())
    index = int(np.flatnonzero(loss <= best + TIE_TOLERANCE)[0])
    return float(SPREAD_GRID[index]), float(loss[index])


def _fit_spreads(oof: pd.DataFrame) -> dict[str, Any]:
    global_factor, global_loss = _fit_spread_factor(oof)
    states: dict[str, Any] = {}
    for state, group in oof.groupby("state", sort=True):
        factor, loss = _fit_spread_factor(group)
        states[str(state)] = {"factor": factor, "oof_mean_absolute_gap_pp": loss}
    return {
        "grid": {"minimum": 0.5, "maximum": 3.0, "step": 0.001},
        "global_fallback": {
            "factor": global_factor,
            "oof_mean_absolute_gap_pp": global_loss,
        },
        "states": states,
    }


def _apply_spreads(
    matrix: np.ndarray, states: pd.Series, fit: Mapping[str, Any]
) -> np.ndarray:
    fallback = float(fit["global_fallback"]["factor"])
    factors = np.asarray(
        [
            float(fit["states"].get(str(state), {"factor": fallback})["factor"])
            for state in states
        ]
    )
    median = matrix[:, [3]]
    return enforce_monotone_quantiles(
        median + factors[:, None] * (matrix - median),
        minimum_magnitude=DEVIATION_TOLERANCE,
    )


def _attach_quantiles(
    base: pd.DataFrame, matrix: np.ndarray, tail_scale: float
) -> pd.DataFrame:
    result = base.copy()
    for index, column in enumerate(QUANTILE_COLUMNS):
        result[column] = matrix[:, index]
    common = (
        result["p_dev"].to_numpy(dtype=float),
        matrix,
        tail_scale,
        result["thr"].to_numpy(dtype=float),
    )
    result["pred_err_dollars_uncapped"] = expected_error_dollars(
        *common, minimum_magnitude=DEVIATION_TOLERANCE
    )
    result["pred_err_dollars"] = expected_error_dollars(
        *common,
        minimum_magnitude=DEVIATION_TOLERANCE,
        magnitude_cap=result["deviation_cap"].to_numpy(dtype=float),
    )
    return result


def _coverage_summary(frame: pd.DataFrame) -> dict[str, Any]:
    levels = weighted_quantile_coverage(frame)
    gaps = np.asarray([row["gap_pp"] for row in levels])
    by_state = {}
    for state, group in frame.groupby("state", sort=True):
        by_state[str(state)] = weighted_quantile_coverage(group)
    return {
        "levels": levels,
        "by_state": by_state,
        "mean_absolute_gap_pp": float(np.mean(np.abs(gaps))),
        "max_absolute_gap_pp": float(np.max(np.abs(gaps))),
        "negative_gap_count": int((gaps < 0).sum()),
        "positive_gap_count": int((gaps > 0).sum()),
        "zero_gap_count": int((gaps == 0).sum()),
    }


def _metrics(
    predicted_2023: pd.DataFrame,
    predicted_2024: pd.DataFrame,
    tail_scale: float,
    baseline_sign: Mapping[str, float],
) -> dict[str, Any]:
    dollar, factors, _ = _dollar_factor_validation(predicted_2023, predicted_2024)
    mae = float(
        dollar["metrics"]["factor_adjusted_frozen_model"]["equal_jurisdiction"][
            "mae_pp"
        ]
    )
    return {
        "coverage": _coverage_summary(predicted_2024),
        "pit": weighted_pit_summary(predicted_2024, tail_scale),
        "guards": {
            "factored_equal_state_dollar_rate_mae_pp": mae,
            "mae_delta_from_committed_pp": mae - BASELINE_MAE_PP,
            "mae_within_plus_0_05pp": bool(
                mae <= BASELINE_MAE_PP + MAE_GUARD_ALLOWANCE_PP + TIE_TOLERANCE
            ),
            "sign_auc_raw": float(baseline_sign["raw"]),
            "sign_auc_calibrated": float(baseline_sign["calibrated"]),
            "sign_auc_unchanged": bool(
                baseline_sign["raw"] == BASELINE_SIGN_AUC_RAW
                and baseline_sign["calibrated"] == BASELINE_SIGN_AUC_CALIBRATED
            ),
        },
        "dollar_factor_fit": {
            "fit_year": 2023,
            "validation_year": 2024,
            "states": factors[["state", "state_factor"]].to_dict("records"),
        },
    }


def _fit_base_predictions(
    data: pd.DataFrame, features: list[str], train: pd.DataFrame, *targets: pd.DataFrame
) -> tuple[Any, list[pd.DataFrame]]:
    magnitude = _fit_gbm_magnitude(train, features)
    probability = _fit_probability_stage(train, features, "deviates", RANDOM_STATE)
    predictions = []
    for target in targets:
        matrix, _ = _predict_gbm_quantiles(magnitude, target, features)
        base = target.copy()
        base["p_dev"] = probability.predict(target[features])
        predictions.append(_attach_quantiles(base, matrix, magnitude.tail.scale))
    return magnitude, predictions


def _cross_fitted_predictions(data: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    rows = []
    for held_year in TRAINING_YEARS:
        print(f"fitting leave-one-year-out magnitude fold FY{held_year}")
        train = data.loc[data["year"].isin(TRAINING_YEARS) & data["year"].ne(held_year)]
        held = data.loc[data["year"].eq(held_year)].copy()
        magnitude = _fit_gbm_magnitude(train, features)
        matrix, _ = _predict_gbm_quantiles(magnitude, held, features)
        for index, column in enumerate(QUANTILE_COLUMNS):
            held[column] = matrix[:, index]
        held["repair_tail_scale"] = float(magnitude.tail.scale)
        rows.append(held.loc[held["deviates"].eq(1)])
    return pd.concat(rows, ignore_index=True)


def _transform_pair(
    name: str,
    train_fit: Mapping[str, Any],
    frame: pd.DataFrame,
    tail_scale: float,
) -> pd.DataFrame:
    matrix = frame[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
    if name in ("conformal_remap", "both"):
        matrix = _interpolate_levels(
            matrix, np.asarray(train_fit["remap"]["source_levels"]), tail_scale
        )
    if name in ("spread_inflation", "both"):
        matrix = _apply_spreads(matrix, frame["state"], train_fit["spread"])
    return _attach_quantiles(frame, matrix, tail_scale)


def _input_hashes() -> dict[str, str]:
    paths = [QC_DIR / f"qc_pub_fy{year}.sav" for year in (*TRAINING_YEARS, YEAR_TEST)]
    paths.extend([SMD_PATH, BBCE_PATH, MEDICARE_PART_B_PATH])
    hashes = {path.name: _file_sha256(path) for path in paths}
    analysis_dir = Path(__file__).parent
    hashes.update(
        {f"analysis/{name}": _file_sha256(analysis_dir / name) for name in MODULE_FILES}
    )
    hashes["analysis/COVERAGE_REPAIR_PROTOCOL.md"] = _file_sha256(PROTOCOL)
    hashes["analysis/distributional_results.json"] = _file_sha256(BASELINE_RESULTS)
    return dict(sorted(hashes.items()))


def _decision_rule() -> dict[str, Any]:
    return {
        "name": "minimum_guarded_primary_with_materiality",
        "primary": "FY2024 mean absolute coverage gap across nine levels (pp)",
        "lower_is_better": True,
        "guards": {
            "factored_equal_state_dollar_rate_mae": {
                "committed_baseline_pp": BASELINE_MAE_PP,
                "maximum_increase_pp": MAE_GUARD_ALLOWANCE_PP,
                "maximum_allowed_pp": BASELINE_MAE_PP + MAE_GUARD_ALLOWANCE_PP,
            },
            "sign_auc": "raw and calibrated values must be exactly unchanged",
        },
        "material_improvement_required_pp": MATERIAL_IMPROVEMENT_PP,
        "tie_tolerance": TIE_TOLERANCE,
        "tie_order": list(MECHANISMS),
        "failure_verdict": "RETAIN BASELINE",
    }


def derive_verdict(result: Mapping[str, Any]) -> dict[str, Any]:
    baseline_primary = float(result["baseline"]["coverage"]["mean_absolute_gap_pp"])
    eligible = []
    for name in MECHANISMS:
        candidate = result["mechanisms"][name]
        guards = candidate["guards"]
        if guards["mae_within_plus_0_05pp"] and guards["sign_auc_unchanged"]:
            eligible.append(name)
    if eligible:
        minimum = min(
            float(result["mechanisms"][name]["coverage"]["mean_absolute_gap_pp"])
            for name in eligible
        )
        tied = [
            name
            for name in eligible
            if float(result["mechanisms"][name]["coverage"]["mean_absolute_gap_pp"])
            <= minimum + TIE_TOLERANCE
        ]
        winner = min(tied, key=TIE_ORDER.__getitem__)
        eligible.sort(
            key=lambda name: (
                float(result["mechanisms"][name]["coverage"]["mean_absolute_gap_pp"]),
                TIE_ORDER[name],
            )
        )
    else:
        winner = None
    improvement = (
        baseline_primary
        - float(result["mechanisms"][winner]["coverage"]["mean_absolute_gap_pp"])
        if winner
        else None
    )
    selected = (
        winner
        if improvement is not None
        and improvement + TIE_TOLERANCE >= MATERIAL_IMPROVEMENT_PP
        else None
    )
    return {
        "eligible_mechanisms": eligible,
        "best_guard_passing_mechanism": winner,
        "best_improvement_pp": improvement,
        "selected_mechanism": selected,
        "verdict": f"USE {selected}" if selected else "RETAIN BASELINE",
    }


def _run_core() -> dict[str, Any]:
    data = assemble()
    data["case"] = 1
    features = _feature_columns(data)
    committed = json.loads(BASELINE_RESULTS.read_text())
    sign = {
        "raw": committed["sign"]["fy2024_among_deviators"]["auc_raw"],
        "calibrated": committed["sign"]["fy2024_among_deviators"]["auc_calibrated"],
    }
    if sign != {
        "raw": BASELINE_SIGN_AUC_RAW,
        "calibrated": BASELINE_SIGN_AUC_CALIBRATED,
    }:
        raise RuntimeError(
            "committed sign AUC no longer matches preregistered baseline"
        )

    oof = _cross_fitted_predictions(data, features)
    remap = _fit_remap(oof)
    remapped_oof = oof.copy()
    remapped_matrix = np.empty((len(oof), len(QUANTILE_LEVELS)))
    for tail_scale, indexes in oof.groupby(
        "repair_tail_scale", sort=True
    ).groups.items():
        remapped_matrix[indexes] = _interpolate_levels(
            oof.loc[indexes, list(QUANTILE_COLUMNS)].to_numpy(),
            np.asarray(remap["source_levels"]),
            float(tail_scale),
        )
    for index, column in enumerate(QUANTILE_COLUMNS):
        remapped_oof[column] = remapped_matrix[:, index]
    fits = {
        "conformal_remap": {"remap": remap},
        "spread_inflation": {"spread": _fit_spreads(oof)},
        "both": {"remap": remap, "spread": _fit_spreads(remapped_oof)},
    }

    frozen_years = tuple(year for year in TRAINING_YEARS if year < 2023)
    frozen_train = data.loc[data["year"].isin(frozen_years)]
    fy2023 = data.loc[data["year"].eq(2023)].copy()
    fy2024 = data.loc[data["year"].eq(YEAR_TEST)].copy()
    magnitude, (base_2023, base_2024) = _fit_base_predictions(
        data, features, frozen_train, fy2023, fy2024
    )
    tail_scale = float(magnitude.tail.scale)
    baseline = _metrics(base_2023, base_2024, tail_scale, sign)
    if (
        abs(
            baseline["guards"]["factored_equal_state_dollar_rate_mae_pp"]
            - BASELINE_MAE_PP
        )
        > 1e-10
    ):
        raise RuntimeError(
            "regenerated baseline dollar MAE does not match committed value"
        )

    mechanisms = {}
    for name in MECHANISMS:
        repaired_2023 = _transform_pair(name, fits[name], base_2023, tail_scale)
        repaired_2024 = _transform_pair(name, fits[name], base_2024, tail_scale)
        mechanisms[name] = {
            "fit": fits[name],
            **_metrics(repaired_2023, repaired_2024, tail_scale, sign),
        }
    result = {
        "schema_version": 1,
        "protocol": {
            "path": "analysis/COVERAGE_REPAIR_PROTOCOL.md",
            "training_years": list(TRAINING_YEARS),
            "base_model_training_years": list(frozen_years),
            "factor_fit_year": 2023,
            "validation_year": YEAR_TEST,
            "mechanisms": list(MECHANISMS),
            "decision_rule": _decision_rule(),
        },
        "provenance": {
            "input_sha256": _input_hashes(),
            "random_state": RANDOM_STATE,
            "quantile_levels": QUANTILE_LEVELS.tolist(),
            "spread_grid_points": len(SPREAD_GRID),
        },
        "baseline": baseline,
        "mechanisms": mechanisms,
    }
    result["verdict"] = derive_verdict(result)
    return _jsonable(result)


def run_experiment(repetitions: int = 2) -> dict[str, Any]:
    if repetitions < 2:
        raise ValueError("repetitions must be at least two")
    cores = []
    hashes = []
    for repetition in range(repetitions):
        print(f"coverage-repair repetition {repetition + 1}/{repetitions}")
        core = _run_core()
        cores.append(core)
        hashes.append(_sha256_json(core))
    if len(set(hashes)) != 1:
        raise RuntimeError("coverage-repair repetitions were not byte-identical")
    result = cores[0]
    result["determinism"] = {
        "repetitions": repetitions,
        "canonical_core_sha256_by_repetition": hashes,
        "exact_match": True,
        "hash_definition": "SHA-256 of sorted compact strict JSON core",
    }
    return result


def write_result(result: Mapping[str, Any], path: Path = OUT) -> None:
    destination = Path(path)
    app_root = Path(__file__).resolve().parents[1] / "app"
    if destination.resolve() == app_root or app_root in destination.resolve().parents:
        raise ValueError("coverage-repair output must not be written under app/")
    destination.write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--repetitions", type=int, default=2)
    return parser


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    result = run_experiment(args.repetitions)
    write_result(result, args.output)
    print(f"wrote {args.output}")
    return result


if __name__ == "__main__":
    main()
