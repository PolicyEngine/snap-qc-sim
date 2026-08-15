#!/usr/bin/env python3
"""Compare PolicyEngine-US's SNAP allotment with the FY2024 QC oracle.

This program intentionally imports the engine only inside runtime functions. It
must be run with the pre-provisioned rung-3 environment described in PARITY.md.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
QC_CSV = Path.home() / ".cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
RESULTS = ROOT / "analysis/rung3/parity_results.json"
ROUND2_RESULTS = ROOT / "analysis/rung3/parity_round2_results.json"
ROUND2_REPORT = ROOT / "PARITY_R2_REPORT.md"
MEMO = ROOT / "analysis/rung3/PARITY.md"

STATES = {4: "AZ", 6: "CA", 8: "CO", 13: "GA", 24: "MD", 36: "NY", 48: "TX"}
EXPECTED_SCOPE = {
    "AZ": 922,
    "CA": 883,
    "CO": 856,
    "GA": 945,
    "MD": 722,
    "NY": 847,
    "TX": 906,
}
CAUSE_ORDER = (
    "rounding_convention",
    "utility_policy",
    "bbce_config",
    "deduction_concept",
    "expedited_or_proration",
    "input_unavailable",
    "engine_rule_difference",
    "unclassified",
)
INTERMEDIATES = {
    "gross_income": "FSGRINC",
    "earned_income_deduction": "FSERNDED",
    "standard_deduction": "FSSTDDED",
    "excess_shelter": "FSSLTDED",
    "net_income": "FSNETINC",
}
ROUND2_INTERMEDIATES = {
    "gross_income": "FSGRINC",
    "earned_income_deduction": "FSERNDED",
    "standard_deduction": "FSSTDDED",
    "medical_deduction": "FSMEDDED",
    "dependent_care_deduction": "FSDEPDED",
    "child_support_deduction": "FSCSDED",
    "excess_shelter": "FSSLTDED",
    "net_income": "FSNETINC",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cases() -> pd.DataFrame:
    """Mirror build_reprice.py's already-certified scope, without re-deriving it."""
    frame = pd.read_csv(QC_CSV, low_memory=False)
    frame.columns = [column.upper() for column in frame.columns]
    frame["source_row_index"] = np.arange(len(frame))
    frame = frame.loc[frame.CASE.eq(1) & frame.STATE.isin(STATES)].copy()
    keep = (
        frame.MN_FIP.fillna(0).ne(1)
        & frame.SSI_CAP.fillna(0).isin([0, 4])
        & frame.FSBEN.notna()
        & frame.FSBEN.gt(0)
        & frame.CERTHHSZ.notna()
        & frame.CERTHHSZ.gt(0)
    )
    frame = frame.loc[keep].copy()
    frame["state"] = frame.STATE.map(STATES)
    frame["case_id"] = frame.apply(
        lambda row: f"FY2024-{int(row.YRMONTH):06d}-{int(row.source_row_index):05d}",
        axis=1,
    )
    counts = frame.groupby("state").size().astype(int).to_dict()
    if counts != EXPECTED_SCOPE:
        raise AssertionError(f"replay scope drifted: {counts}")
    return frame.sort_values(["YRMONTH", "state", "case_id"]).reset_index(drop=True)


def _values(frame: pd.DataFrame, column: str) -> np.ndarray:
    return frame[column].fillna(0).to_numpy()


def run_month_batch(
    frame: pd.DataFrame, period: str, *, annualize_housing_cost: bool = False
) -> dict[str, np.ndarray]:
    """Run one recorded month as a vectorized PolicyEngine-US simulation."""
    from policyengine_core.simulations.simulation_builder import SimulationBuilder
    from policyengine_us import Microsimulation

    size = len(frame)
    ids = np.arange(size)
    builder = SimulationBuilder()
    microsim = Microsimulation()
    builder.populations = microsim.tax_benefit_system.instantiate_entities()
    builder.declare_person_entity("person", ids)
    for entity in ("household", "spm_unit", "family", "tax_unit", "marital_unit"):
        builder.declare_entity(entity, ids)
        builder.join_with_persons(
            builder.populations[entity], ids, np.array(["member"] * size)
        )
    microsim.build_from_populations(builder.populations)

    # Formula inputs are recorded monthly amounts. Directly overriding the
    # congruent SNAP variables avoids reconstructing administrative concepts
    # (especially allowable medical expense) from unavailable person detail.
    monthly = {
        "snap_unit_size": _values(frame, "CERTHHSZ"),
        "snap_earned_income": _values(frame, "FSEARN"),
        "snap_unearned_income": _values(frame, "FSUNEARN"),
        # PE-US can apply state-specific child-support exclusions while forming
        # gross income. The QC comparator defines gross as earned + unearned,
        # so override that congruent intermediate uniformly as well.
        "snap_gross_income": _values(frame, "FSEARN") + _values(frame, "FSUNEARN"),
        "snap_excess_medical_expense_deduction": _values(frame, "FSMEDDED"),
        "snap_dependent_care_deduction": _values(frame, "FSDEPDED"),
        "snap_child_support_deduction": _values(frame, "FSCSDED"),
        "snap_utility_allowance": _values(frame, "UTIL"),
        # The QC scope contains certified positive-benefit cases. Eligibility
        # is held true so missing assets/immigration/work-status data and BBCE
        # do not turn the formula-amount comparison into a new eligibility test.
        "is_snap_eligible": np.ones(size, dtype=bool),
    }
    for variable, values in monthly.items():
        microsim.set_input(variable, period, values)
    year = period[:4]
    # housing_cost is a YEAR variable. Round 1 deliberately retains its
    # original monthly-period assignment in baseline mode; round 2 maps the
    # recorded monthly RENT amount to an annual flow before setting it.
    if annualize_housing_cost:
        microsim.set_input("housing_cost", year, _values(frame, "RENT") * 12)
    else:
        microsim.set_input("housing_cost", period, _values(frame, "RENT"))
    microsim.set_input(
        "has_usda_elderly_disabled",
        year,
        (_values(frame, "FSNELDER") + _values(frame, "FSNDIS")) > 0,
    )
    microsim.set_input("is_homeless", year, _values(frame, "HOMEDED") == 3)
    microsim.set_input("state_code", year, _values(frame, "STATE").astype(int))

    variables = {
        "formula_benefit": "snap_normal_allotment",
        "gross_income": "snap_gross_income",
        "earned_income_deduction": "snap_earned_income_deduction",
        "standard_deduction": "snap_standard_deduction",
        "medical_deduction": "snap_excess_medical_expense_deduction",
        "dependent_care_deduction": "snap_dependent_care_deduction",
        "child_support_deduction": "snap_child_support_deduction",
        "excess_shelter": "snap_excess_shelter_expense_deduction",
        "net_income": "snap_net_income",
        "maximum_allotment": "snap_max_allotment",
        "minimum_allotment": "snap_min_allotment",
        "housing_cost_monthly": "housing_cost",
        "utility_allowance": "snap_utility_allowance",
    }
    result = {
        output: np.asarray(microsim.calculate(variable, period=period))
        for output, variable in variables.items()
    }
    shelter = microsim.tax_benefit_system.parameters(
        period
    ).gov.usda.snap.income.deductions.excess_shelter_expense
    result["shelter_cap"] = np.full(size, float(shelter.cap["CONTIGUOUS_US"]))
    result["homeless_deduction"] = np.full(size, float(shelter.homeless.deduction))
    return result


def engine_results(
    frame: pd.DataFrame, *, annualize_housing_cost: bool = False
) -> pd.DataFrame:
    chunks = []
    for yrmonth, group in frame.groupby("YRMONTH", sort=True):
        period = f"{int(yrmonth) // 100:04d}-{int(yrmonth) % 100:02d}"
        calculated = run_month_batch(
            group, period, annualize_housing_cost=annualize_housing_cost
        )
        chunk = group[["case_id"]].copy()
        for name, values in calculated.items():
            chunk[name] = values
        chunks.append(chunk)
    calculated = pd.concat(chunks, ignore_index=True).set_index("case_id")
    return frame.join(calculated, on="case_id", validate="one_to_one")


def whole_dollars(values: pd.Series) -> pd.Series:
    """Convert engine currency output to monthly dollars, half away from zero."""
    array = values.to_numpy(dtype=float)
    return pd.Series(
        np.sign(array) * np.floor(np.abs(array) + 0.5), index=values.index
    ).astype(int)


def first_divergent_intermediate(row: pd.Series) -> str | None:
    for engine, recorded in INTERMEDIATES.items():
        value = float(row[engine])
        value_whole = int(np.sign(value) * np.floor(abs(value) + 0.5))
        if value_whole != int(row[recorded]):
            return engine
    return None


def cause_for(row: pd.Series) -> str:
    first = row["first_divergent_intermediate"]
    if first == "gross_income":
        return "deduction_concept"
    if first == "earned_income_deduction":
        return "rounding_convention"
    if first == "standard_deduction":
        return "engine_rule_difference"
    if first == "excess_shelter":
        if int(row.HOMEDED) == 3:
            return "engine_rule_difference"
        if abs(float(row.excess_shelter) - float(row.FSSLTDED)) <= 1:
            return "rounding_convention"
        return "deduction_concept"
    if first == "net_income":
        if abs(float(row.net_income) - float(row.FSNETINC)) <= 1:
            return "rounding_convention"
        return "deduction_concept"
    if first is None or pd.isna(first):
        return "rounding_convention"
    return "unclassified"


def policyengine_interface_spot_check(frame: pd.DataFrame) -> dict[str, object]:
    """Check 50 records through policyengine.py's public household route.

    The public one-household API is annual-only. Each record's monthly inputs
    are annualized, and its annual result is divided by 12. The check compares
    the public route with an annual batch calculation under identical semantics.
    """
    import policyengine as pe

    candidates = frame.loc[frame.YRMONTH.eq(202401)].head(50)
    annualized = candidates.copy()
    flow_columns = [
        "FSEARN",
        "FSUNEARN",
        "FSMEDDED",
        "FSDEPDED",
        "FSCSDED",
        "RENT",
        "UTIL",
    ]
    annualized[flow_columns] = annualized[flow_columns].fillna(0) * 12
    direct_annual = run_month_batch(annualized, "2024")["formula_benefit"] / 12
    differences = []
    for position, (_, row) in enumerate(candidates.iterrows()):
        annual = {
            name: (0 if pd.isna(row[name]) else float(row[name])) * 12
            for name in flow_columns
        }

        result = pe.us.calculate_household(
            people=[{"age": 40}],
            year=2024,
            household={"state_code": row.state, "is_homeless": int(row.HOMEDED) == 3},
            spm_unit={
                "snap_unit_size": float(row.CERTHHSZ),
                "snap_earned_income": annual["FSEARN"],
                "snap_unearned_income": annual["FSUNEARN"],
                "snap_gross_income": annual["FSEARN"] + annual["FSUNEARN"],
                "snap_excess_medical_expense_deduction": annual["FSMEDDED"],
                "snap_dependent_care_deduction": annual["FSDEPDED"],
                "snap_child_support_deduction": annual["FSCSDED"],
                "housing_cost": annual["RENT"],
                "snap_utility_allowance": annual["UTIL"],
                "has_usda_elderly_disabled": int(row.FSNELDER) + int(row.FSNDIS) > 0,
                "is_snap_eligible": True,
            },
            extra_variables=["snap_normal_allotment"],
        )
        interface_monthly = float(result.spm_unit.snap_normal_allotment) / 12
        differences.append(interface_monthly - float(direct_annual[position]))
    return {
        "n": len(differences),
        "route": "policyengine.us.calculate_household",
        "annualization": "monthly flow inputs multiplied by 12; stock/count inputs repeated; annual output divided by 12",
        "exact_n": sum(abs(value) < 5e-5 for value in differences),
        "max_abs_difference": max((abs(value) for value in differences), default=0),
    }


def build_payload(
    frame: pd.DataFrame, runtime_seconds: float, spot: dict[str, object]
) -> dict[str, object]:
    frame = frame.copy()
    frame["engine_whole_dollars"] = whole_dollars(frame.formula_benefit)
    frame["difference_dollars"] = frame.engine_whole_dollars - frame.FSBEN.astype(int)
    frame["first_divergent_intermediate"] = frame.apply(
        first_divergent_intermediate, axis=1
    )
    frame["cause"] = frame.apply(cause_for, axis=1)
    state_results = {}
    for state, group in frame.groupby("state", sort=True):
        divergent = group.loc[group.difference_dollars.ne(0)]
        causes = []
        for cause in CAUSE_ORDER:
            members = divergent.loc[divergent.cause.eq(cause)]
            if members.empty:
                continue
            firsts = members.first_divergent_intermediate.dropna()
            causes.append(
                {
                    "cause_class": cause,
                    "n": len(members),
                    "exemplar_case_ids": members.case_id.head(3).tolist(),
                    "first_divergent_intermediate": firsts.mode().iat[0]
                    if not firsts.empty
                    else None,
                }
            )
        histogram = Counter(str(int(value)) for value in divergent.difference_dollars)
        exact = int(group.difference_dollars.eq(0).sum())
        state_results[state] = {
            "in_scope_n": len(group),
            "exact_match_n": exact,
            "exact_match_rate": exact / len(group),
            "divergence_histogram_dollars": dict(
                sorted(histogram.items(), key=lambda item: int(item[0]))
            ),
            "divergence_causes": causes,
        }

    peus = Path(importlib.util.find_spec("policyengine_us").origin).parent
    citations = {
        "comparator": str(peus / "variables/gov/usda/snap/snap_normal_allotment.py")
        + ":4-23",
        "takeup": str(peus / "variables/gov/usda/snap/snap.py") + ":19-35",
        "expected_contribution": str(
            peus / "variables/gov/usda/snap/snap_expected_contribution.py"
        )
        + ":13-19",
        "utility": str(
            peus
            / "variables/gov/usda/snap/income/deductions/shelter/snap_utility_allowance.py"
        )
        + ":4-16",
        "shelter": str(
            peus
            / "variables/gov/usda/snap/income/deductions/shelter/snap_excess_shelter_expense_deduction.py"
        )
        + ":15-40",
        "categorical_eligibility": str(
            peus / "variables/gov/usda/snap/eligibility/is_snap_eligible.py"
        )
        + ":16-35",
    }
    return {
        "schema_version": "1.0.0",
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "policyengine": importlib.metadata.version("policyengine"),
            "policyengine_us": importlib.metadata.version("policyengine-us"),
            "runtime_seconds": runtime_seconds,
        },
        "input_hashes": {str(QC_CSV): sha256(QC_CSV)},
        "comparator_variable": "snap_normal_allotment",
        "mapping_decisions": {
            "period": "Each QC YRMONTH is evaluated as that exact monthly period.",
            "formula_benefit": "snap_normal_allotment; excludes take-up and emergency/local supplements.",
            "income": "FSEARN -> snap_earned_income; FSUNEARN -> snap_unearned_income.",
            "deductions": "Recorded FSMEDDED, FSDEPDED, and FSCSDED override the congruent SNAP deduction variables uniformly.",
            "rent": "RENT -> housing_cost.",
            "utility": "Recorded adjudicated UTIL directly overrides snap_utility_allowance; state SUA policy is not re-derived.",
            "elderly_disabled": "FSNELDER + FSNDIS > 0 -> has_usda_elderly_disabled.",
            "homeless": "HOMEDED == 3 -> is_homeless; engine homeless-choice logic remains active.",
            "eligibility_bbce": {
                state: "is_snap_eligible forced true; BBCE/categorical eligibility not re-adjudicated"
                for state in EXPECTED_SCOPE
            },
            "takeup_behavior_seed": "Not used: comparator is snap_normal_allotment, not snap.",
            "whole_dollars": "Engine monthly result rounded half away from zero before comparison to integer FSBEN.",
            "source_citations": citations,
        },
        "batch_route": "policyengine_us.Microsimulation grouped by exact QC month",
        "policyengine_interface_spot_check": spot,
        "states": state_results,
    }


def render_memo(payload: dict[str, object]) -> str:
    rows = []
    blockers = []
    for state, result in payload["states"].items():
        rows.append(
            f"| {state} | {result['in_scope_n']:,} | {result['exact_match_n']:,} | {result['exact_match_rate']:.2%} |"
        )
        if result["exact_match_n"] != result["in_scope_n"]:
            blockers.append(state)
    cause_totals = Counter()
    for result in payload["states"].values():
        cause_totals.update(
            {entry["cause_class"]: entry["n"] for entry in result["divergence_causes"]}
        )
    causes = "\n".join(
        f"- `{cause}`: {count:,} cases." for cause, count in cause_totals.most_common()
    )
    verdict = "EXACT PARITY" if not blockers else "NOT YET"
    blocker_text = (
        "None." if not blockers else ", ".join(blockers) + " have non-matching cases."
    )
    spot = payload["policyengine_interface_spot_check"]
    return f"""# PolicyEngine SNAP parity

## Promotion verdict

**{verdict}.** Blockers: {blocker_text}

## Parity results

| State | In scope | Exact matches | Match rate |
|---|---:|---:|---:|
{chr(10).join(rows)}

## Divergence diagnoses

{causes}

### Deduction concepts

The dominant class first diverges in gross, shelter, or net income despite the uniform direct overrides. It captures definition and arithmetic differences between PE-US's composed deduction tree and the recorded administrative intermediates; it is not state SUA re-derivation because recorded `UTIL` is forced.

### Rounding convention

These cases first differ only at the final allotment or at a whole-dollar intermediate. PolicyEngine-US retains fractional deductions and computes 30 percent of floored net income, while the QC replay floors the earned deduction and ceilings the benefit reduction.

### Engine rule difference

Two Colorado cases follow PE-US's conditional homeless maximum rather than the QC replay's claimed flat homeless deduction. This is a formula-encoding difference, not an unavailable-input classification.

## Execution and mapping

The full run used vectorized `policyengine_us.Microsimulation` batches grouped by exact `YRMONTH`; runtime was {payload["environment"]["runtime_seconds"]:.2f} seconds. The public policyengine.py route is annual-only, so its 50-case January spot check annualized monthly inputs and divided annual output by 12: {spot["exact_n"]}/{spot["n"]} exact, maximum absolute difference {spot["max_abs_difference"]:.6g}. The machine-readable artifact records every mapping decision and installed-source citation.

The formula comparator is `snap_normal_allotment`, not `snap`: the former is the ordinary allotment before take-up, emergency allotments, and DC supplements. Recorded `UTIL` directly overrides `snap_utility_allowance`; the harness does not re-derive state SUA rules. Eligibility is uniformly forced true for this positive-FSBEN certified-recipient scope, so BBCE, assets, immigration, and work requirements do not silently redefine the oracle population.

## Version skew

This run used policyengine {payload["environment"]["policyengine"]} and policyengine-us {payload["environment"]["policyengine_us"]}, the versions certified by policyengine.py's manifest in the provisioned environment. Installing policyengine-us 1.808.0 fails policyengine.py's provenance gate at import; that known skew was not bypassed.
"""


def administrative_results(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the certified administrative whole-dollar chain to PE-US values."""
    result = frame.copy()
    half_up = lambda values: np.floor(np.asarray(values, dtype=float) + 0.5)
    gross = half_up(result.gross_income)
    earned = np.floor(result.earned_income_deduction.to_numpy(dtype=float))
    standard = half_up(result.standard_deduction)
    medical = half_up(result.medical_deduction)
    dependent = half_up(result.dependent_care_deduction)
    child_support = half_up(result.child_support_deduction)
    homeless = result.HOMEDED.fillna(0).eq(3).to_numpy()
    homeless_deduction = half_up(result.homeless_deduction)
    adjusted = np.maximum(
        0,
        gross
        - earned
        - standard
        - medical
        - dependent
        - child_support
        - np.where(homeless, homeless_deduction, 0),
    )
    uncapped_shelter = np.maximum(
        0,
        result.housing_cost_monthly.to_numpy(dtype=float)
        + result.utility_allowance.to_numpy(dtype=float)
        - 0.5 * adjusted,
    )
    elderly_disabled = (_values(result, "FSNELDER") + _values(result, "FSNDIS")) > 0
    shelter = np.where(
        elderly_disabled,
        uncapped_shelter,
        np.minimum(uncapped_shelter, result.shelter_cap.to_numpy(dtype=float)),
    )
    shelter = np.where(homeless, 0, half_up(shelter))
    net = np.maximum(0, adjusted - shelter)
    reduction = np.ceil(0.30 * net)
    maximum = half_up(result.maximum_allotment)
    minimum = np.floor(result.minimum_allotment.to_numpy(dtype=float))
    benefit = np.maximum(minimum, np.maximum(0, maximum - reduction)).astype(int)
    result["admin_earned_income_deduction"] = earned.astype(int)
    result["admin_excess_shelter"] = shelter.astype(int)
    result["admin_net_income"] = net.astype(int)
    result["admin_formula_benefit"] = benefit
    return result


def _direction(delta: float) -> str:
    if delta > 0:
        return "pe_us_above_recorded"
    if delta < 0:
        return "pe_us_below_recorded"
    return "exact"


def _size_bin(delta: float) -> str:
    value = abs(delta)
    if value <= 1:
        return "$1"
    if value <= 5:
        return "$2-$5"
    if value <= 25:
        return "$6-$25"
    if value <= 100:
        return "$26-$100"
    return "$101+"


def round2_first_divergence(row: pd.Series) -> tuple[str | None, int]:
    for engine, recorded in ROUND2_INTERMEDIATES.items():
        value = int(np.floor(float(row[engine]) + 0.5))
        delta = value - int(row[recorded])
        if delta:
            return engine, delta
    return None, 0


def parity_table(frame: pd.DataFrame, benefit_column: str) -> dict[str, object]:
    tables = {}
    difference = frame[benefit_column].astype(int) - frame.FSBEN.astype(int)
    for state, group in frame.assign(_difference=difference).groupby(
        "state", sort=True
    ):
        exact = int(group._difference.eq(0).sum())
        tables[state] = {
            "in_scope_n": len(group),
            "exact_match_n": exact,
            "exact_match_rate": exact / len(group),
        }
    return tables


def build_round2_payload(
    legacy: pd.DataFrame, fixed: pd.DataFrame, runtime_seconds: float
) -> dict[str, object]:
    legacy = legacy.copy()
    fixed = administrative_results(fixed)
    legacy["engine_whole_dollars"] = whole_dollars(legacy.formula_benefit)
    legacy["difference_dollars"] = legacy.engine_whole_dollars - legacy.FSBEN.astype(
        int
    )
    legacy["first_divergent_intermediate"] = legacy.apply(
        first_divergent_intermediate, axis=1
    )
    legacy["cause"] = legacy.apply(cause_for, axis=1)
    cohort = legacy.loc[
        legacy.difference_dollars.ne(0) & legacy.cause.eq("deduction_concept")
    ].copy()
    details = []
    for _, old in cohort.iterrows():
        concept, delta = round2_first_divergence(old)
        details.append(
            {
                "case_id": old.case_id,
                "state": old.state,
                "concept": concept or "none_before_allotment",
                "direction": _direction(delta),
                "difference_dollars": int(delta),
                "size_bin": _size_bin(delta),
            }
        )
    detail = pd.DataFrame(details)
    by_concept = []
    for concept, group in detail.groupby("concept", sort=True):
        classification = (
            "pe_us_concept_or_formula_difference"
            if concept == "net_income"
            else "harness_mapping_gap"
        )
        by_concept.append(
            {
                "concept": concept,
                "n": len(group),
                "classification": classification,
                "direction": group.direction.value_counts().sort_index().to_dict(),
                "dollar_size_distribution": group.size_bin.value_counts()
                .sort_index()
                .to_dict(),
                "states": group.state.value_counts().sort_index().to_dict(),
                "exemplar_case_ids": group.case_id.head(3).tolist(),
            }
        )
    legacy_table = parity_table(legacy, "engine_whole_dollars")
    fixed["engine_whole_dollars"] = whole_dollars(fixed.formula_benefit)
    fixed_table = parity_table(fixed, "engine_whole_dollars")
    admin_table = parity_table(fixed, "admin_formula_benefit")
    admin_by_id = fixed.set_index("case_id").admin_formula_benefit
    conversions = []
    for cause, group in legacy.loc[legacy.difference_dollars.ne(0)].groupby(
        "cause", sort=True
    ):
        converted = sum(
            int(admin_by_id.loc[row.case_id]) == int(row.FSBEN)
            for _, row in group.iterrows()
        )
        conversions.append(
            {
                "round1_cause": cause,
                "round1_divergent_n": len(group),
                "admin_rounding_exact_n": converted,
                "admin_rounding_exact_rate": converted / len(group),
            }
        )
    peus = Path(importlib.util.find_spec("policyengine_us").origin).parent
    citations = {
        "housing_cost_period": str(
            peus / "variables/household/expense/housing/housing_cost.py"
        )
        + ":4-16",
        "earned_deduction_fractional": str(
            peus
            / "variables/gov/usda/snap/income/deductions/snap_earned_income_deduction.py"
        )
        + ":13-17",
        "pre_shelter_stack": str(
            peus
            / "variables/gov/usda/snap/income/deductions/shelter/snap_net_income_pre_shelter.py"
        )
        + ":22-30",
        "shelter_formula": str(
            peus
            / "variables/gov/usda/snap/income/deductions/shelter/snap_excess_shelter_expense_deduction.py"
        )
        + ":15-40",
        "net_income": str(peus / "variables/gov/usda/snap/income/snap_net_income.py")
        + ":13-16",
        "expected_contribution": str(
            peus / "variables/gov/usda/snap/snap_expected_contribution.py"
        )
        + ":13-19",
    }
    return {
        "schema_version": "2.0.0",
        "environment": {
            "policyengine": importlib.metadata.version("policyengine"),
            "policyengine_us": importlib.metadata.version("policyengine-us"),
            "runtime_seconds": runtime_seconds,
        },
        "input_hashes": {str(QC_CSV): sha256(QC_CSV)},
        "modes": {
            "baseline_round1": legacy_table,
            "mapping_fixed_pe_us": fixed_table,
            "admin_rounding": admin_table,
        },
        "mapping_decisions": [
            {
                "id": "annualize_monthly_rent_for_annual_housing_cost",
                "classification": "harness_mapping_gap",
                "recorded_column": "RENT",
                "pe_us_variable": "housing_cost",
                "legacy_mapping": "monthly RENT set at the monthly period",
                "round2_mapping": "monthly RENT multiplied by 12 and set at calendar year",
                "uniform": True,
                "source_citation": citations["housing_cost_period"],
            }
        ],
        "deduction_concept_cohort_n": len(cohort),
        "admin_conversion_by_round1_cause": conversions,
        "sub_cause_histogram": by_concept,
        "source_citations": citations,
        "case_localizations": details,
    }


def render_round2_report(payload: dict[str, object]) -> str:
    totals = {}
    for mode, states in payload["modes"].items():
        totals[mode] = (
            sum(item["exact_match_n"] for item in states.values()),
            sum(item["in_scope_n"] for item in states.values()),
        )
    rows = []
    for state in EXPECTED_SCOPE:
        baseline = payload["modes"]["baseline_round1"][state]
        admin = payload["modes"]["admin_rounding"][state]
        rows.append(
            f"| {state} | {baseline['exact_match_n']:,}/{baseline['in_scope_n']:,} "
            f"({baseline['exact_match_rate']:.2%}) | {admin['exact_match_n']:,}/"
            f"{admin['in_scope_n']:,} ({admin['exact_match_rate']:.2%}) |"
        )
    causes = "\n".join(
        f"- `{item['concept']}`: {item['n']:,} ({item['classification']})."
        for item in payload["sub_cause_histogram"]
    )
    return f"""# Parity round 2 report

The round-1 comparator remains {totals["baseline_round1"][0]:,}/{totals["baseline_round1"][1]:,} exact. Correcting the annual `housing_cost` mapping yields {totals["mapping_fixed_pe_us"][0]:,}/{totals["mapping_fixed_pe_us"][1]:,}; applying the uniform administrative whole-dollar sequence yields {totals["admin_rounding"][0]:,}/{totals["admin_rounding"][1]:,}.

| State | Round-1 baseline | Admin rounding after mapping fix |
|---|---:|---:|
{chr(10).join(rows)}

## Deduction-concept decomposition

{causes}

All mechanism citations and every case localization are recorded in `analysis/rung3/parity_round2_results.json`. Full harness runtime: {payload["environment"]["runtime_seconds"]:.2f} seconds.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "round2"), default="baseline")
    args = parser.parse_args()
    start = time.perf_counter()
    cases = load_cases()
    if args.mode == "round2":
        legacy = engine_results(cases)
        fixed = engine_results(cases, annualize_housing_cost=True)
        payload = build_round2_payload(legacy, fixed, time.perf_counter() - start)
        ROUND2_RESULTS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        report = render_round2_report(payload)
        ROUND2_REPORT.write_text(report)
        round1_memo = MEMO.read_text().split("\n## Round 2\n", maxsplit=1)[0]
        MEMO.write_text(
            round1_memo
            + "\n## Round 2\n\n"
            + report.removeprefix("# Parity round 2 report\n\n")
        )
        print(f"Wrote {ROUND2_RESULTS}, {ROUND2_REPORT}, and appended {MEMO}")
        return
    calculated = engine_results(cases)
    spot = policyengine_interface_spot_check(calculated)
    payload = build_payload(calculated, time.perf_counter() - start, spot)
    RESULTS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    existing = MEMO.read_text() if MEMO.exists() else ""
    round2_suffix = (
        "\n## Round 2\n" + existing.split("\n## Round 2\n", maxsplit=1)[1]
        if "\n## Round 2\n" in existing
        else ""
    )
    MEMO.write_text(render_memo(payload) + round2_suffix)
    total = sum(value["in_scope_n"] for value in payload["states"].values())
    exact = sum(value["exact_match_n"] for value in payload["states"].values())
    print(f"PolicyEngine-US parity: {exact:,}/{total:,}; wrote {RESULTS} and {MEMO}")


if __name__ == "__main__":
    main()
