"""Procedural targeting scenarios for measured SNAP QC error dollars.

Every result is an accounting construction: what happens to the measured rate
if counted error dollars in a selected group fall by X, however achieved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis import event_study, model_capture, persistence, train_error_model
from snap_qc_sim.data import QcCase
from snap_qc_sim.simulate import simulate, tier_of

OUT = Path(__file__).with_name("interventions_results.json")
MEMO_OUT = Path(__file__).with_name("INTERVENTIONS.md")
RANKING_RULES = ("oracle", "model", "self_employment", "random")
COVERAGE_PCT = (1, 5, 10)
EFFECTIVENESS_PCT = (25, 50)
SINGLE_DRAWS = 10_000
SEED = 20260820


def raw_inputs_available() -> bool:
    return model_capture.raw_inputs_available() and persistence.raw_inputs_available()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weighted_membership(
    weights: np.ndarray, score: np.ndarray, coverage: float, tie: np.ndarray
) -> np.ndarray:
    """Exact HWGT-budget membership, fractionally assigning one boundary case."""
    order = np.lexsort((tie, -score))
    ordered_weight = weights[order]
    before = np.r_[0.0, np.cumsum(ordered_weight)[:-1]]
    fraction = np.clip((coverage * weights.sum() - before) / ordered_weight, 0, 1)
    membership = np.zeros(len(weights))
    membership[order] = fraction
    return membership


def _single_summary(rates: np.ndarray) -> dict[str, Any]:
    rates = np.clip(rates, 0.0, None)
    shares = np.array([tier_of(rate) for rate in rates], dtype=float)
    return {
        "mean_rate": round(float(rates.mean()), 4),
        "p_tier": {
            str(share): round(float((shares == share).mean()), 4)
            for share in (0, 5, 10, 15)
        },
        "expected_share_pct": round(float(shares.mean()), 4),
    }


def _case_inputs() -> tuple[dict[str, list[QcCase]], pd.DataFrame]:
    scored = model_capture.load_scored_fy2024()
    raw = train_error_model.load_year(
        train_error_model.YEAR_TEST, include_source_row_index=True
    )
    # Match snap_qc_sim.data.load_cases after its CASE == 1 and state filters.
    raw = raw.loc[raw["RAWBEN"].notna() & raw["HWGT"].gt(0)].copy()
    joined = raw.merge(
        scored[["source_row_index", "model_score", "official_error"]],
        on="source_row_index",
        how="inner",
        validate="one_to_one",
    )
    se_cols = train_error_model._self_employment_columns(joined.columns)
    joined["self_employment"] = joined[se_cols].fillna(0).gt(0).any(axis=1) | joined[
        "FSSLFEMP"
    ].gt(0)
    joined["counted_error_dollars"] = joined["AMTERR"] * joined["official_error"]
    by_state: dict[str, list[QcCase]] = {}
    for state, group in joined.groupby("state", sort=True):
        cases = []
        for _, row in group.iterrows():
            elements = frozenset(
                int(row[f"ELEMENT{i}"])
                for i in train_error_model.FINDING_SLOTS
                if pd.notna(row[f"ELEMENT{i}"])
            )
            cases.append(
                QcCase(
                    float(row["HWGT"]),
                    float(row["RAWBEN"]),
                    float(row["counted_error_dollars"]),
                    elements,
                )
            )
        by_state[state] = cases
    return by_state, joined


def _persistence_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    rng = np.random.default_rng(persistence.SEED)
    wide = persistence.build_rate_panel()
    variances = persistence.cell_sampling_variances(rng).reindex(
        index=wide.index, columns=wide.columns
    )
    x = persistence.demean_by_year(wide)
    moments, counts, mean_variance = persistence.autocovariances(x, variances)
    fit = persistence.fit_components(moments, counts, mean_variance)
    return x, variances, fit


def compute_artifact() -> dict[str, Any]:
    cases_by_state, rows = _case_inputs()
    movement = json.loads(persistence.MOVEMENT_PATH.read_text())
    official = {row["state"]: row["fy2025"] for row in movement["states"]}
    state_frames = {
        state: group.reset_index(drop=True)
        for state, group in rows.groupby("state", sort=True)
    }
    rng = np.random.default_rng(SEED)
    memberships: dict[tuple[str, str, int], np.ndarray] = {}
    for state in sorted(set(cases_by_state) & set(official)):
        frame = state_frames[state]
        weights = frame["HWGT"].to_numpy(float)
        tie = frame["source_row_index"].to_numpy(float)
        random_score = rng.random(len(frame))
        scores = {
            "oracle": frame["counted_error_dollars"].to_numpy(float),
            "model": frame["model_score"].to_numpy(float),
            "self_employment": frame["self_employment"].to_numpy(float),
            "random": random_score,
        }
        for rule in RANKING_RULES:
            for coverage_pct in COVERAGE_PCT:
                memberships[(state, rule, coverage_pct)] = weighted_membership(
                    weights, scores[rule], coverage_pct / 100, tie
                )

    scenarios = []
    deltas_by_scenario: list[dict[str, float]] = []
    for rule in RANKING_RULES:
        for coverage_pct in COVERAGE_PCT:
            for effectiveness_pct in EFFECTIVENESS_PCT:
                state_results: dict[str, Any] = {}
                deltas: dict[str, float] = {}
                for state in sorted(set(cases_by_state) & set(official)):
                    cases = cases_by_state[state]
                    membership = memberships[(state, rule, coverage_pct)]
                    base = (
                        100
                        * sum(c.weight * c.error for c in cases)
                        / sum(c.weight * c.issuance for c in cases)
                    )
                    shifted = (
                        100
                        * sum(
                            c.weight
                            * c.error
                            * (1 - effectiveness_pct / 100 * membership[i])
                            for i, c in enumerate(cases)
                        )
                        / sum(c.weight * c.issuance for c in cases)
                    )
                    delta = shifted - base
                    deltas[state] = float(delta)
                    rates = simulate(
                        cases,
                        official[state],
                        effectiveness=effectiveness_pct / 100,
                        targeted_memberships=membership,
                        draws=SINGLE_DRAWS,
                        rng=np.random.default_rng(
                            SEED
                            + RANKING_RULES.index(rule) * 10_000
                            + coverage_pct * 100
                            + effectiveness_pct
                            + sum(map(ord, state))
                        ),
                    )
                    state_results[state] = {
                        "weighted_coverage_pct": round(
                            100
                            * float(
                                np.dot(
                                    state_frames[state]["HWGT"].to_numpy(float),
                                    membership,
                                )
                                / state_frames[state]["HWGT"].sum()
                            ),
                            8,
                        ),
                        "single_measurement_delta_pp": round(delta, 6),
                        "single_measurement": _single_summary(rates),
                    }
                scenarios.append(
                    {
                        "ranking_rule": rule,
                        "coverage_pct": coverage_pct,
                        "effectiveness_pct": effectiveness_pct,
                        "states": state_results,
                    }
                )
                deltas_by_scenario.append(deltas)

    x, variances, fit = _persistence_inputs()
    for scenario, deltas in zip(scenarios, deltas_by_scenario, strict=True):
        exposure = persistence.exposure(
            x,
            variances,
            fit,
            np.random.default_rng(SEED),
            state_level_shift_pp=deltas,
        )
        for state, result in scenario["states"].items():
            result["sustained_intervention_fy2028_30"] = exposure[state]["years"]

    persistence_path = Path(persistence.__file__).with_name("persistence_results.json")
    return {
        "schema_version": 1,
        "interpretation": (
            "accounting construction: what happens to the measured rate if "
            "counted error dollars in this group fall by X, however achieved"
        ),
        "sustained_intervention_assumption": (
            "the single-measurement rate delta is subtracted from the anchored "
            "FY2028-30 path in every horizon year because the procedure persists"
        ),
        "cost_share_unit": "percent of issuance",
        "coverage_unit": "percent of HWGT-weighted caseload",
        "self_employment_definition": (
            "any available SLFEMP1-18 > 0 or FSSLFEMP > 0, after CASE == 1 "
            "and valid-state filtering shared with train_error_model.load_year"
        ),
        "boundary_case_rule": (
            "one ranked boundary case is fractionally assigned so each HWGT budget is exact"
        ),
        "scenario_grid": scenarios,
        "input_hashes": {
            "coding_consistency": _sha256(event_study.AUDIT_PATH),
            "fy2025_movement": _sha256(persistence.MOVEMENT_PATH),
            "persistence_results": _sha256(persistence_path),
            "model_capture_results": _sha256(model_capture.OUT),
            "fy2024_sav": train_error_model._provenance()["input_sha256"][
                "qc_pub_fy2024.sav"
            ],
        },
        "environment": {
            "seed": SEED,
            "single_draws": SINGLE_DRAWS,
            "persistence_draws": persistence.EXPOSURE_DRAWS,
        },
        "runtime": "measured externally and reported in INTERVENTIONS_REPORT.md to keep regeneration byte-identical",
    }


def _memo(artifact: dict[str, Any]) -> str:
    return "\n".join(
        [
            "<!-- Generated by analysis/interventions.py; do not edit manually. -->",
            "",
            "# Targeted-intervention accounting scenarios",
            "",
            artifact["interpretation"].capitalize() + ".",
            "",
            "## Scenario grid",
            "",
            (
                "The artifact prices oracle, model, self-employment, and seeded-random "
                "rankings at 1%, 5%, and 10% of HWGT-weighted caseload, with counted "
                "error dollars reduced by 25% or 50% inside the selected group. A "
                "fractional boundary assignment makes each weighted budget exact."
            ),
            "",
            "## Single-measurement construction",
            "",
            (
                "FY2024 QC cases are resampled through the existing simulator and "
                "location-anchored on each jurisdiction's FY2025 official rate. Outputs "
                "are mean measured rates, statutory-tier probabilities, and expected "
                "cost share as a percent of issuance. No issuance dollars are used."
            ),
            "",
            "## Sustained intervention construction",
            "",
            artifact["sustained_intervention_assumption"].capitalize() + ".",
            "The persistence layer otherwise retains its anchored path, process dispersion, sampling proxy, clipping, and 7 USC 2013(a)(2) tiers.",
            "",
            "## Data definitions and limits",
            "",
            (
                "Self-employment means any available SLFEMP1-18 value above zero or "
                "FSSLFEMP above zero. The shared loader enforces CASE == 1 and valid "
                "state codes; the intervention lane also applies load_cases' nonmissing "
                "RAWBEN and positive-HWGT filters. Full state-scenario results and "
                "audited input hashes are in `analysis/interventions_results.json`."
            ),
            "",
        ]
    )


def main() -> None:
    artifact = compute_artifact()
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    MEMO_OUT.write_text(_memo(artifact))
    print(f"wrote {OUT} and {MEMO_OUT}")


if __name__ == "__main__":
    main()
