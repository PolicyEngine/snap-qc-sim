#!/usr/bin/env python3
"""Deterministic Colorado rung-3 accounting prototype.

Run with the pinned rung3 environment; engine and model imports stay runtime-only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import pickle
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FRAME = ROOT / "analysis/rung3/cluster1_co_frame.parquet"
SPARSE = Path(
    "/private/tmp/claude-501/-Users-maxghenis/51a1b6bb-c8a6-466b-bd9b-2620f722d19d/scratchpad/populace_us_2024_current.h5"
)
RESULT = ROOT / "analysis/rung3/prototype_results.json"
CASELOAD_TARGET = 305_279.584
ISSUANCE_TARGET = 1_267_963_387.75
RATES = {"over": 0.0791, "under": 0.0206}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_people(units: pd.DataFrame) -> pd.DataFrame:
    people = pd.read_hdf(SPARSE, "person")
    people = people.loc[people.person_spm_unit_id.isin(units.spm_unit_id)].copy()
    if people.person_spm_unit_id.nunique() != len(units):
        raise ValueError("person/SPM-unit linkage is incomplete")
    return people


def engine(frame: pd.DataFrame, people: pd.DataFrame, year: int) -> pd.DataFrame:
    from policyengine_core.simulations.simulation_builder import SimulationBuilder
    from policyengine_us import Microsimulation

    # Preserve real people. Other entities are intentionally one-per-SPM-unit;
    # they are structural containers for this SNAP-only calculation.
    unit_ids = frame.spm_unit_id.to_numpy()
    unit_pos = {value: index for index, value in enumerate(unit_ids)}
    person_unit = people.person_spm_unit_id.map(unit_pos).to_numpy()
    count = len(people)
    builder = SimulationBuilder()
    sim = Microsimulation()
    builder.populations = sim.tax_benefit_system.instantiate_entities()
    builder.declare_person_entity("person", np.arange(count))
    for entity in ("household", "spm_unit", "family", "tax_unit", "marital_unit"):
        builder.declare_entity(entity, np.arange(len(frame)))
        builder.join_with_persons(
            builder.populations[entity], person_unit, np.array(["member"] * count)
        )
    sim.build_from_populations(builder.populations)
    period = f"{year}-01"
    annual = str(year)
    monthly = {
        "snap_unit_size": frame.household_size,
        "snap_earned_income": frame.earned_income,
        "snap_unearned_income": frame.unearned_income,
        "snap_gross_income": frame.gross_income,
        "snap_excess_medical_expense_deduction": frame.medical_expense_above_floor,
        "snap_dependent_care_deduction": frame.dependent_care_deduction,
        "snap_child_support_deduction": frame.child_support_deduction,
        "snap_utility_allowance": frame.utility_allowance,
    }
    for variable, values in monthly.items():
        sim.set_input(variable, period, values.to_numpy())
    sim.set_input("housing_cost", annual, frame.rent.to_numpy() * 12)
    sim.set_input("has_usda_elderly_disabled", annual, frame.has_elderly_or_disabled)
    sim.set_input("is_homeless", annual, frame.homeless_deduction_claimed)
    sim.set_input("state_code", annual, np.full(len(frame), 8))
    person_inputs = {
        "age": people.A_AGE.fillna(0),
        "is_disabled": people.is_disabled.fillna(False),
        "is_full_time_college_student": people.is_full_time_college_student.fillna(
            False
        ),
        "weekly_hours_worked_before_lsr": people.weekly_hours_worked_before_lsr.fillna(
            0
        ),
        "is_pregnant": people.is_pregnant.fillna(False),
        "is_incapable_of_self_care": people.is_incapable_of_self_care.fillna(False),
        "is_snap_abawd_discretionary_exempt": people.is_snap_abawd_discretionary_exempt.fillna(
            False
        ),
        "immigration_status_str": people.immigration_status_str.fillna("CITIZEN"),
    }
    for variable, values in person_inputs.items():
        sim.set_input(variable, annual, values.to_numpy())
    outputs = {}
    for name, variable in {
        "eligible": "is_snap_eligible",
        "benefit": "snap_normal_allotment",
        "maximum_allotment": "snap_max_allotment",
        "net_income": "snap_net_income",
    }.items():
        outputs[name] = np.asarray(sim.calculate(variable, period=period))
    return pd.DataFrame(outputs, index=frame.index)


def model_features(
    frame: pd.DataFrame, engine_result: pd.DataFrame
) -> tuple[pd.DataFrame, list[str]]:
    """Map available prototype concepts onto the committed scorer surface."""
    from analysis.hurdle_deviation_model import _feature_columns, assemble

    training = assemble()
    features = _feature_columns(training)
    x = pd.DataFrame(np.nan, index=frame.index, columns=features)
    known = {
        "size": frame.household_size,
        "size_missing": 0,
        "elderly_or_disabled": frame.has_elderly_or_disabled.astype(int),
        "elderly_disabled_missing": 0,
        "has_earnings": frame.earned_income.gt(0).astype(int),
        "earned": frame.earned_income,
        "earned_missing": 0,
        "unearned": frame.unearned_income,
        "unearned_missing": 0,
        "gross": frame.gross_income,
        "gross_missing": 0,
        "year": 2024,
        "children": frame.has_children.astype(int),
        "children_missing": 0,
        "formula_benefit": engine_result.benefit,
        "formula_benefit_missing": 0,
        "claims_medical": frame.medical_deduction_claimed.astype(int),
        "claims_medical_missing": 0,
        "medical_expense_above_floor": frame.medical_expense_above_floor,
        "utility_actuals": frame.utility_claims_actual_expenses.astype(int),
        "utility_actuals_missing": 0,
        "deduction_count": frame[
            [
                "medical_deduction_claimed",
                "dependent_care_deduction_claimed",
                "child_support_deduction_claimed",
            ]
        ].sum(axis=1),
        "deduction_components_missing": 0,
        "at_max": np.isclose(
            engine_result.benefit, engine_result.maximum_allotment
        ).astype(int),
        "at_min": engine_result.benefit.le(23).astype(int),
        "ben_rel_max": engine_result.benefit
        / engine_result.maximum_allotment.replace(0, np.nan),
        "benefit_position_missing": 0,
        "net_share_of_gross": engine_result.net_income
        / frame.gross_income.replace(0, np.nan),
        "net_share_undefined": frame.gross_income.eq(0).astype(int),
        "deductions_per_member": (
            frame.medical_expense_above_floor
            + frame.dependent_care_deduction
            + frame.child_support_deduction
        )
        / frame.household_size,
        "deductions_missing": 0,
        "state_bbce": 1,
        "state_bbce_missing": 0,
        "state_bbce_elderly_or_disabled": frame.has_elderly_or_disabled.astype(int),
        "state_bbce_has_earnings": frame.earned_income.gt(0).astype(int),
        "state_bbce_children": frame.has_children.astype(int),
    }
    for column, value in known.items():
        if column in x:
            x[column] = value
    x["w"] = frame.weight
    x["deviation_cap"] = engine_result.maximum_allotment.clip(lower=57)
    x["thr"] = 56.0
    return pd.concat([x, training.iloc[0:0]], axis=0), features


def score(
    frame: pd.DataFrame, engine_result: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, int]]:
    try:
        import sklearn  # noqa: F401
    except ImportError:
        with tempfile.TemporaryDirectory(prefix="rung3-prototype-") as directory:
            exchange = Path(directory) / "exchange.pkl"
            output = Path(directory) / "prediction.pkl"
            frame_data = {
                column: frame[column].astype(object).to_numpy()
                if str(frame[column].dtype).startswith("string")
                else frame[column].to_numpy()
                for column in frame
            }
            engine_data = {
                column: engine_result[column].to_numpy() for column in engine_result
            }
            with exchange.open("wb") as stream:
                pickle.dump((frame_data, engine_data), stream)
            subprocess.run(
                [
                    str(ROOT / ".venv/bin/python"),
                    str(Path(__file__)),
                    "--score-worker",
                    str(exchange),
                    str(output),
                ],
                cwd=ROOT,
                check=True,
            )
            with output.open("rb") as stream:
                prediction_data, missing = pickle.load(stream)
            return pd.DataFrame(prediction_data), missing
    from analysis.distributional_deviation_model import fit_process, predict_process
    from analysis.hurdle_deviation_model import _feature_columns, assemble

    all_data = assemble()
    features = _feature_columns(all_data)
    training = all_data.loc[all_data.year.isin([2017, 2018, 2019, 2022, 2023])]
    bundle = fit_process(training, features)
    x, _ = model_features(frame, engine_result)
    x = x.iloc[: len(frame)].copy()
    prediction = predict_process(bundle, x, features)
    prediction["over_dollars"] = prediction.pred_err_dollars * prediction.p_pos
    prediction["under_dollars"] = prediction.pred_err_dollars * (1 - prediction.p_pos)
    missing = {
        column: int(x[column].isna().sum())
        for column in features
        if x[column].isna().any()
    }
    return prediction, missing


def score_worker(exchange: Path, output: Path) -> None:
    with exchange.open("rb") as stream:
        frame_data, engine_data = pickle.load(stream)
    prediction, missing = score(pd.DataFrame(frame_data), pd.DataFrame(engine_data))
    prediction_data = {column: prediction[column].to_numpy() for column in prediction}
    with output.open("wb") as stream:
        pickle.dump((prediction_data, missing), stream)


def rake(
    base_weight: np.ndarray, margins: np.ndarray, targets: np.ndarray
) -> tuple[np.ndarray, dict[str, float]]:
    """Exponential calibration to four dollar/count sums."""
    scaled = margins / np.maximum(np.abs(targets), 1)
    desired = targets / np.maximum(np.abs(targets), 1)
    beta = np.zeros(margins.shape[1])
    converged = False
    residual = np.full(margins.shape[1], np.inf)
    for _ in range(200):
        ratio = np.exp(np.clip(scaled @ beta, -30, 30))
        weighted = base_weight * ratio
        residual = scaled.T @ weighted - desired
        if np.max(np.abs(residual)) < 1e-8:
            converged = True
            break
        jacobian = scaled.T @ (weighted[:, None] * scaled)
        beta -= np.linalg.lstsq(jacobian, residual, rcond=None)[0]
    ratio = np.exp(np.clip(scaled @ beta, -30, 30))
    weights = base_weight * ratio
    ess = weights.sum() ** 2 / np.square(weights).sum()
    return weights, {
        "effective_sample_size": float(ess),
        "max_weight_ratio": float(ratio.max()),
        "converged": converged,
        "max_relative_residual": float(np.max(np.abs(residual))),
    }


def summarize(
    frame: pd.DataFrame, eng: pd.DataFrame, pred: pd.DataFrame, weights: np.ndarray
) -> dict[str, float]:
    baseline = frame.takes_up_snap_if_eligible.to_numpy() & eng.eligible.to_numpy()
    annual = 12.0
    issuance = float(
        np.sum(weights[baseline] * eng.benefit.to_numpy()[baseline]) * annual
    )
    over = float(
        np.sum(weights[baseline] * pred.over_dollars.to_numpy()[baseline]) * annual
    )
    under = float(
        np.sum(weights[baseline] * pred.under_dollars.to_numpy()[baseline]) * annual
    )
    return {
        "caseload": float(weights[baseline].sum()),
        "issuance": issuance,
        "overpayment_dollars": over,
        "underpayment_dollars": under,
        "overpayment_rate": over / issuance,
        "underpayment_rate": under / issuance,
        "total_rate": (over + under) / issuance,
    }


def main() -> dict[str, object]:
    started = time.perf_counter()
    frame = pd.read_parquet(FRAME)
    people = load_people(frame)
    eng24 = engine(frame, people, 2024)
    eng25 = engine(frame, people, 2025)
    doubled_frame = pd.concat([frame, frame], ignore_index=True)
    doubled_engine = pd.concat([eng24, eng25], ignore_index=True)
    doubled_prediction, missing = score(doubled_frame, doubled_engine)
    pred24 = doubled_prediction.iloc[: len(frame)].reset_index(drop=True)
    pred25 = doubled_prediction.iloc[len(frame) :].reset_index(drop=True)
    initial = frame.weight.to_numpy()
    uncal = summarize(frame, eng24, pred24, initial)
    baseline = frame.takes_up_snap_if_eligible.to_numpy() & eng24.eligible.to_numpy()
    margins = np.column_stack(
        [
            baseline,
            baseline * eng24.benefit * 12,
            baseline * pred24.over_dollars * 12,
            baseline * pred24.under_dollars * 12,
        ]
    ).astype(float)
    targets = np.array(
        [
            CASELOAD_TARGET,
            ISSUANCE_TARGET,
            ISSUANCE_TARGET * RATES["over"],
            ISSUANCE_TARGET * RATES["under"],
        ]
    )
    calibrated, diagnostics = rake(initial, margins, targets)
    post = summarize(frame, eng24, pred24, calibrated)
    pred25["thr"] = 57.0
    movement = summarize(frame, eng25, pred25, calibrated)
    payload = {
        "schema": "snap_qc_sim.rung3_prototype.v1",
        "eligibility": {
            "convention": "build-consistent engine is_snap_eligible",
            "eligible_units": int(eng24.eligible.sum()),
            "baseline_units": int(baseline.sum()),
            "flag_only_units": int(frame.takes_up_snap_if_eligible.sum()),
            "baseline_weighted_caseload": uncal["caseload"],
            "flag_only_weighted_caseload": float(
                initial[frame.takes_up_snap_if_eligible].sum()
            ),
        },
        "uncalibrated": {
            **uncal,
            "overpayment_model_target_ratio": uncal["overpayment_rate"] / RATES["over"],
            "underpayment_model_target_ratio": uncal["underpayment_rate"]
            / RATES["under"],
        },
        "calibration": {
            "targets": {
                "caseload": CASELOAD_TARGET,
                "issuance": ISSUANCE_TARGET,
                "overpayment_dollars": ISSUANCE_TARGET * RATES["over"],
                "underpayment_dollars": ISSUANCE_TARGET * RATES["under"],
            },
            "diagnostics": {
                **diagnostics,
                "degenerate": diagnostics["effective_sample_size"] < 0.1 * len(frame),
            },
            "post": post,
        },
        "fy2025": {
            "prototype": movement,
            "official_total_rate": 0.1009,
            "official_change_pp": 0.12,
            "prototype_change_pp": 100 * (movement["total_rate"] - post["total_rate"]),
        },
        "error_model": {
            "missing_value_counts": missing,
            "coverage_failure_disclosed": True,
        },
        "inputs": {
            "frame": {"path": str(FRAME), "sha256": sha256(FRAME)},
            "sparse_build": {"path": str(SPARSE), "sha256": sha256(SPARSE)},
        },
        "environment": {
            "python": platform.python_version(),
            "policyengine_us": importlib.metadata.version("policyengine-us"),
            "runtime_seconds": time.perf_counter() - started,
        },
        "task_b": {
            "status": "not_run_wall_time_stub",
            "deployed_statistical_flip": {
                "crossing_rate_delta_pp": -0.060,
                "expected_fy2028_bill_delta_dollars": -2_000_000,
            },
            "causal_claim": False,
        },
    }
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-worker", nargs=2, metavar=("INPUT", "OUTPUT"))
    arguments = parser.parse_args()
    if arguments.score_worker:
        score_worker(Path(arguments.score_worker[0]), Path(arguments.score_worker[1]))
    else:
        main()
