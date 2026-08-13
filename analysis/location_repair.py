"""Deterministic post-hoc location repair for the frozen GBM distribution."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

if __package__:
    from . import coverage_repair as common
    from .distributional_deviation_model import (
        _dollar_factor_validation,
        weighted_pit_summary,
        weighted_quantile_coverage,
    )
    from .hurdle_deviation_model import (
        RANDOM_STATE,
        _feature_columns,
        assemble,
        effective_sample_size,
    )
    from .predictive_process import QUANTILE_LEVELS, enforce_monotone_quantiles
    from .train_error_model import (
        BBCE_PATH,
        MEDICARE_PART_B_PATH,
        QC_DIR,
        SMD_PATH,
        YEAR_TEST,
    )
else:
    import coverage_repair as common
    from distributional_deviation_model import (
        _dollar_factor_validation,
        weighted_pit_summary,
        weighted_quantile_coverage,
    )
    from hurdle_deviation_model import (
        RANDOM_STATE,
        _feature_columns,
        assemble,
        effective_sample_size,
    )
    from predictive_process import QUANTILE_LEVELS, enforce_monotone_quantiles
    from train_error_model import (
        BBCE_PATH,
        MEDICARE_PART_B_PATH,
        QC_DIR,
        SMD_PATH,
        YEAR_TEST,
    )

OUT = Path(__file__).with_name("location_repair_results.json")
PROTOCOL = Path(__file__).with_name("LOCATION_REPAIR_PROTOCOL.md")
BASELINE_RESULTS = Path(__file__).with_name("distributional_results.json")
TRAINING_YEARS = common.TRAINING_YEARS
QUANTILE_COLUMNS = common.QUANTILE_COLUMNS
MECHANISMS = ("global_shift", "state_shift", "level_profile")
TIE_ORDER = {name: index for index, name in enumerate(MECHANISMS)}
SHIFT_GRID = np.round(np.arange(-2.0, 2.0001, 0.001), 3)
SHIFT_GRID_STEP = 0.001
MIN_STATE_DEVIATORS = 100
MIN_STATE_EFFECTIVE_N = 100.0
TIE_TOLERANCE = 1e-12
MATERIAL_IMPROVEMENT_PP = 0.25
MAX_LEVEL_WORSENING_PP = 0.5
MAE_GUARD_ALLOWANCE_PP = common.MAE_GUARD_ALLOWANCE_PP
BASELINE_MAE_PP = common.BASELINE_MAE_PP
BASELINE_SIGN_AUC_RAW = common.BASELINE_SIGN_AUC_RAW
BASELINE_SIGN_AUC_CALIBRATED = common.BASELINE_SIGN_AUC_CALIBRATED
MODULE_FILES = (
    "location_repair.py",
    "coverage_repair.py",
    "distributional_deviation_model.py",
    "hurdle_deviation_model.py",
    "predictive_process.py",
    "qrf_benchmark.py",
    "train_error_model.py",
)


def _shift_loss(frame: pd.DataFrame) -> tuple[float, float, bool]:
    """Fit the pre-registered common shift grid to nine coverage gaps."""
    observed = np.log(frame["D"].abs()).to_numpy(dtype=float)
    weights = frame["w"].to_numpy(dtype=float)
    total = float(weights.sum())
    losses = []
    for level, column in zip(QUANTILE_LEVELS, QUANTILE_COLUMNS, strict=True):
        residual = observed - frame[column].to_numpy(dtype=float)
        order = np.argsort(residual, kind="mergesort")
        sorted_residual = residual[order]
        cumulative = np.cumsum(weights[order])
        positions = np.searchsorted(sorted_residual, SHIFT_GRID, side="right") - 1
        covered = np.zeros(len(SHIFT_GRID), dtype=float)
        valid = positions >= 0
        covered[valid] = cumulative[positions[valid]] / total
        losses.append(np.abs(100 * (covered - float(level))))
    loss = np.mean(np.column_stack(losses), axis=1)
    best = float(loss.min())
    tied = np.flatnonzero(loss <= best + TIE_TOLERANCE)
    index = min(tied, key=lambda item: (abs(SHIFT_GRID[item]), SHIFT_GRID[item]))
    endpoint = index in (0, len(SHIFT_GRID) - 1)
    return float(SHIFT_GRID[index]), float(loss[index]), endpoint


def _fit_global(oof: pd.DataFrame) -> dict[str, Any]:
    shift, loss, endpoint = _shift_loss(oof)
    return {
        "shift_log_dollars": shift,
        "oof_mean_absolute_gap_pp": loss,
        "at_grid_endpoint": endpoint,
    }


def _fit_states(oof: pd.DataFrame) -> dict[str, Any]:
    fallback = _fit_global(oof)
    states = {}
    for state, group in oof.groupby("state", sort=True):
        n = len(group)
        n_eff = effective_sample_size(group["w"].to_numpy(dtype=float))
        thin = n < MIN_STATE_DEVIATORS or n_eff < MIN_STATE_EFFECTIVE_N
        if thin:
            fit = {
                "shift_log_dollars": fallback["shift_log_dollars"],
                "oof_mean_absolute_gap_pp": None,
                "at_grid_endpoint": False,
            }
        else:
            shift, loss, endpoint = _shift_loss(group)
            fit = {
                "shift_log_dollars": shift,
                "oof_mean_absolute_gap_pp": loss,
                "at_grid_endpoint": endpoint,
            }
        states[str(state)] = {
            "n": n,
            "effective_n": n_eff,
            "uses_global_fallback": thin,
            **fit,
        }
    fitted_endpoints = [
        row["at_grid_endpoint"]
        for row in states.values()
        if not row["uses_global_fallback"]
    ]
    return {
        "thinness_rule": {
            "minimum_unweighted_deviators": MIN_STATE_DEVIATORS,
            "minimum_kish_effective_n": MIN_STATE_EFFECTIVE_N,
            "requires_both": True,
        },
        "global_fallback": fallback,
        "states": states,
        "all_grid_fits_bracketed": not fallback["at_grid_endpoint"]
        and not any(fitted_endpoints),
    }


def _weighted_empirical_quantile(values: np.ndarray, weights: np.ndarray, u: float):
    order = np.argsort(values, kind="mergesort")
    ordered = values[order]
    cumulative = np.cumsum(weights[order])
    index = int(np.searchsorted(cumulative, u * cumulative[-1], side="left"))
    return float(ordered[index])


def _fit_level_profile(oof: pd.DataFrame) -> dict[str, Any]:
    observed = np.log(oof["D"].abs()).to_numpy(dtype=float)
    weights = oof["w"].to_numpy(dtype=float)
    offsets = []
    for level, column in zip(QUANTILE_LEVELS, QUANTILE_COLUMNS, strict=True):
        residual = observed - oof[column].to_numpy(dtype=float)
        offsets.append(_weighted_empirical_quantile(residual, weights, float(level)))
    return {
        "offsets_log_dollars": offsets,
        "weighted_empirical_quantile_convention": (
            "smallest sorted residual with cumulative positive HWGT >= level"
        ),
    }


def _isotonic_project(matrix: np.ndarray) -> tuple[np.ndarray, int]:
    raw = np.asarray(matrix, dtype=float)
    violating = np.any(np.diff(raw, axis=1) < 0, axis=1)
    projected = raw.copy()
    x = np.arange(raw.shape[1], dtype=float)
    for row in np.flatnonzero(violating):
        projected[row] = IsotonicRegression(increasing=True).fit_transform(x, raw[row])
    projected = enforce_monotone_quantiles(
        projected, minimum_magnitude=common.DEVIATION_TOLERANCE
    )
    return projected, int(violating.sum())


def _apply(
    name: str, fit: Mapping[str, Any], frame: pd.DataFrame, tail_scale: float
) -> tuple[pd.DataFrame, int]:
    matrix = frame[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
    repairs = 0
    if name == "global_shift":
        matrix = matrix + float(fit["shift_log_dollars"])
        matrix = enforce_monotone_quantiles(
            matrix, minimum_magnitude=common.DEVIATION_TOLERANCE
        )
    elif name == "state_shift":
        fallback = float(fit["global_fallback"]["shift_log_dollars"])
        shifts = np.asarray(
            [
                float(
                    fit["states"].get(str(state), {}).get("shift_log_dollars", fallback)
                )
                for state in frame["state"]
            ]
        )
        matrix = enforce_monotone_quantiles(
            matrix + shifts[:, None], minimum_magnitude=common.DEVIATION_TOLERANCE
        )
    elif name == "level_profile":
        matrix, repairs = _isotonic_project(
            matrix + np.asarray(fit["offsets_log_dollars"])[None, :]
        )
    else:
        raise ValueError(f"unknown location-repair mechanism: {name}")
    result = common._attach_quantiles(frame, matrix, tail_scale)
    if not np.array_equal(
        result["p_dev"].to_numpy(), frame["p_dev"].to_numpy(), equal_nan=True
    ):
        raise AssertionError("location repair changed frozen hurdle probabilities")
    return result, repairs


def _coverage_summary(frame: pd.DataFrame) -> dict[str, Any]:
    levels = weighted_quantile_coverage(frame)
    gaps = np.asarray([row["gap_pp"] for row in levels])
    return {
        "levels": levels,
        "by_state": {
            str(state): weighted_quantile_coverage(group)
            for state, group in frame.groupby("state", sort=True)
        },
        "mean_absolute_gap_pp": float(np.mean(np.abs(gaps))),
        "max_absolute_gap_pp": float(np.max(np.abs(gaps))),
        "negative_gap_count": int((gaps < 0).sum()),
        "positive_gap_count": int((gaps > 0).sum()),
        "zero_gap_count": int((gaps == 0).sum()),
    }


def _level_guards(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    rows = []
    for base, repaired in zip(baseline["levels"], candidate["levels"], strict=True):
        worsening = abs(float(repaired["gap_pp"])) - abs(float(base["gap_pp"]))
        no_worsening = worsening <= MAX_LEVEL_WORSENING_PP + TIE_TOLERANCE
        baseline_clean = not bool(base["flag_over_3pp"])
        no_new_flag = (not baseline_clean) or not bool(repaired["flag_over_3pp"])
        rows.append(
            {
                "quantile": float(base["quantile"]),
                "baseline_gap_pp": float(base["gap_pp"]),
                "candidate_gap_pp": float(repaired["gap_pp"]),
                "absolute_gap_worsening_pp": worsening,
                "absolute_gap_worsening_within_0_5pp": no_worsening,
                "baseline_under_or_equal_3pp": baseline_clean,
                "no_new_over_3pp_flag": no_new_flag,
            }
        )
    q05_floor = 0.5 * float(baseline["levels"][0]["weighted_coverage"])
    q05_coverage = float(candidate["levels"][0]["weighted_coverage"])
    return {
        "levels": rows,
        "all_absolute_gap_worsening_within_0_5pp": all(
            row["absolute_gap_worsening_within_0_5pp"] for row in rows
        ),
        "no_new_over_3pp_flags": all(row["no_new_over_3pp_flag"] for row in rows),
        "q05_baseline_coverage": float(baseline["levels"][0]["weighted_coverage"]),
        "q05_minimum_coverage": q05_floor,
        "q05_candidate_coverage": q05_coverage,
        "q05_at_least_half_baseline": q05_coverage + TIE_TOLERANCE >= q05_floor,
    }


def _metrics(
    predicted_2023: pd.DataFrame,
    predicted_2024: pd.DataFrame,
    tail_scale: float,
    sign: Mapping[str, float],
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
            "mae_within_plus_0_05pp": mae
            <= BASELINE_MAE_PP + MAE_GUARD_ALLOWANCE_PP + TIE_TOLERANCE,
            "hurdle_probabilities_unchanged": True,
            "sign_auc_raw": float(sign["raw"]),
            "sign_auc_calibrated": float(sign["calibrated"]),
            "sign_auc_unchanged": sign["raw"] == BASELINE_SIGN_AUC_RAW
            and sign["calibrated"] == BASELINE_SIGN_AUC_CALIBRATED,
        },
        "dollar_factor_fit": {
            "fit_year": 2023,
            "validation_year": YEAR_TEST,
            "states": factors[["state", "state_factor"]].to_dict("records"),
        },
    }


def _decision_rule() -> dict[str, Any]:
    return {
        "name": "minimum_guarded_primary_with_materiality_and_level_guards",
        "primary": "FY2024 mean absolute coverage gap across nine levels (pp)",
        "lower_is_better": True,
        "guards": {
            "per_level_absolute_gap_maximum_worsening_pp": MAX_LEVEL_WORSENING_PP,
            "no_new_strict_over_3pp_flags": True,
            "q05_minimum_fraction_of_baseline_coverage": 0.5,
            "factored_equal_state_dollar_rate_mae": {
                "committed_baseline_pp": BASELINE_MAE_PP,
                "maximum_increase_pp": MAE_GUARD_ALLOWANCE_PP,
                "maximum_allowed_pp": BASELINE_MAE_PP + MAE_GUARD_ALLOWANCE_PP,
            },
            "hurdle_probabilities": "must be exactly unchanged",
            "sign_auc": "raw and calibrated values must be exactly unchanged",
            "shift_grid": "every fitted shift must be strictly inside the grid",
        },
        "material_improvement_required_pp": MATERIAL_IMPROVEMENT_PP,
        "tie_tolerance": TIE_TOLERANCE,
        "tie_order": list(MECHANISMS),
        "failure_verdict": "RETAIN BASELINE",
    }


def _passes_all_guards(candidate: Mapping[str, Any]) -> bool:
    guards = candidate["guards"]
    level = guards["per_level"]
    return bool(
        guards["mae_within_plus_0_05pp"]
        and guards["hurdle_probabilities_unchanged"]
        and guards["sign_auc_unchanged"]
        and guards["all_grid_fits_bracketed"]
        and level["all_absolute_gap_worsening_within_0_5pp"]
        and level["no_new_over_3pp_flags"]
        and level["q05_at_least_half_baseline"]
    )


def derive_verdict(result: Mapping[str, Any]) -> dict[str, Any]:
    baseline = float(result["baseline"]["coverage"]["mean_absolute_gap_pp"])
    eligible = [
        name for name in MECHANISMS if _passes_all_guards(result["mechanisms"][name])
    ]
    eligible.sort(
        key=lambda name: (
            float(result["mechanisms"][name]["coverage"]["mean_absolute_gap_pp"]),
            TIE_ORDER[name],
        )
    )
    winner = eligible[0] if eligible else None
    improvement = (
        baseline
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


def _input_hashes() -> dict[str, str]:
    paths = [QC_DIR / f"qc_pub_fy{year}.sav" for year in (*TRAINING_YEARS, YEAR_TEST)]
    paths.extend([SMD_PATH, BBCE_PATH, MEDICARE_PART_B_PATH])
    hashes = {path.name: common._file_sha256(path) for path in paths}
    analysis_dir = Path(__file__).parent
    hashes.update(
        {
            f"analysis/{name}": common._file_sha256(analysis_dir / name)
            for name in MODULE_FILES
        }
    )
    hashes["analysis/LOCATION_REPAIR_PROTOCOL.md"] = common._file_sha256(PROTOCOL)
    hashes["analysis/distributional_results.json"] = common._file_sha256(
        BASELINE_RESULTS
    )
    return dict(sorted(hashes.items()))


def _run_core() -> dict[str, Any]:
    data = assemble()
    data["case"] = 1
    features = _feature_columns(data)
    committed = json.loads(BASELINE_RESULTS.read_text(encoding="utf-8"))
    sign = {
        "raw": committed["sign"]["fy2024_among_deviators"]["auc_raw"],
        "calibrated": committed["sign"]["fy2024_among_deviators"]["auc_calibrated"],
    }
    if sign != {
        "raw": BASELINE_SIGN_AUC_RAW,
        "calibrated": BASELINE_SIGN_AUC_CALIBRATED,
    }:
        raise RuntimeError("committed sign AUC no longer matches protocol")

    oof = common._cross_fitted_predictions(data, features)
    fits = {
        "global_shift": _fit_global(oof),
        "state_shift": _fit_states(oof),
        "level_profile": _fit_level_profile(oof),
    }
    _, oof_profile_repairs = _isotonic_project(
        oof[list(QUANTILE_COLUMNS)].to_numpy(dtype=float)
        + np.asarray(fits["level_profile"]["offsets_log_dollars"])[None, :]
    )

    frozen_years = tuple(year for year in TRAINING_YEARS if year < 2023)
    frozen_train = data.loc[data["year"].isin(frozen_years)]
    fy2023 = data.loc[data["year"].eq(2023)].copy()
    fy2024 = data.loc[data["year"].eq(YEAR_TEST)].copy()
    magnitude, (base_2023, base_2024) = common._fit_base_predictions(
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
        repaired_2023, repairs_2023 = _apply(name, fits[name], base_2023, tail_scale)
        repaired_2024, repairs_2024 = _apply(name, fits[name], base_2024, tail_scale)
        candidate = {
            "fit": fits[name],
            "isotonic_repairs": {
                "pooled_oof_rows": oof_profile_repairs
                if name == "level_profile"
                else 0,
                "fy2023_rows": repairs_2023,
                "fy2024_rows": repairs_2024,
            },
            **_metrics(repaired_2023, repaired_2024, tail_scale, sign),
        }
        candidate["guards"]["per_level"] = _level_guards(
            baseline["coverage"], candidate["coverage"]
        )
        candidate["guards"]["all_grid_fits_bracketed"] = (
            not fits[name]["at_grid_endpoint"]
            if name == "global_shift"
            else fits[name].get("all_grid_fits_bracketed", True)
        )
        mechanisms[name] = candidate

    result = {
        "schema_version": 1,
        "protocol": {
            "path": "analysis/LOCATION_REPAIR_PROTOCOL.md",
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
            "shift_grid": {"minimum": -2.0, "maximum": 2.0, "step": SHIFT_GRID_STEP},
            "shift_grid_points": len(SHIFT_GRID),
        },
        "baseline": baseline,
        "mechanisms": mechanisms,
    }
    result["verdict"] = derive_verdict(result)
    return common._jsonable(result)


def run_experiment(repetitions: int = 2) -> dict[str, Any]:
    if repetitions < 2:
        raise ValueError("repetitions must be at least two")
    cores = []
    hashes = []
    for repetition in range(repetitions):
        print(f"location-repair repetition {repetition + 1}/{repetitions}")
        core = _run_core()
        cores.append(core)
        hashes.append(common._sha256_json(core))
    if len(set(hashes)) != 1:
        raise RuntimeError("location-repair repetitions were not byte-identical")
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
        raise ValueError("location-repair output must not be written under app/")
    destination.write_text(
        json.dumps(common._jsonable(result), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
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
