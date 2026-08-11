"""Build FY2024 State cause-share accounting from public SNAP QC findings.

The public file supplies a primary-cause code for each of as many as nine
recorded variances.  It does not supply a case-level binary agency/client
flag, and the per-variance amounts do not reconcile to case ``AMTERR`` for
every record.  This module therefore emits both:

* a case-dollar partition that splits each case equally across the distinct
  documented cause classes present in its nine ``AGENCYi`` slots; and
* a same-slot element tabulation using positive ``AMOUNTi`` only when the
  paired ``E_FINDGi`` records overissuance, underissuance, or ineligibility.

Both are accounting conventions, not causal estimates of what a rules engine
would prevent.  Exact code-level and overlapping any-presence results remain
available so readers can substitute a different convention without returning
to the restricted execution environment.
"""

from __future__ import annotations

import importlib.metadata
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis import train_error_model as error_model

FISCAL_YEAR = 2024
OUTPUT_PATH = Path(__file__).with_name("cause_shares.json")
TECHDOC_PATH = Path("~/.cache/axiom-oracles/snap-qc/techdoc.txt").expanduser()
PUBLIC_CSV_PATH = Path(
    "~/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
).expanduser()
REPLAY_PATH = (
    Path(__file__).parents[1]
    / "paper/snapshot/labs/amterr/amterr_replay_results.json"
)

SLOTS = tuple(error_model.FINDING_SLOTS)
DETAIL_ROOTS = (
    "AGENCY",
    "AMOUNT",
    "DISCOV",
    "E_FINDG",
    "ELEMENT",
    "NATURE",
    "OCCDATE",
    "TIMEPER",
    "VERIF",
)
DETAIL_COLUMNS = tuple(f"{root}{slot}" for root in DETAIL_ROOTS for slot in SLOTS)
IMPACT_CODES = {2: "overissuance", 3: "underissuance", 4: "ineligible"}

# The labels below are transcribed from techdoc.txt:L11840-L11973.  The
# requested agency/client superclasses are analysis mappings; the public file
# itself records the individual codes, not a binary flag.
CAUSE_CODES: dict[int, dict[str, str]] = {
    1: {
        "label": "Information not reported",
        "class": "client_or_fact",
    },
    2: {
        "label": (
            "Incomplete or incorrect information provided; agency not required "
            "to verify"
        ),
        "class": "client_or_fact",
    },
    3: {
        "label": (
            "Information withheld by client (case referred for Intentional "
            "Program Violation investigation)"
        ),
        "class": "client_or_fact",
    },
    4: {
        "label": (
            "Incorrect information provided by client (case referred for "
            "Intentional Program Violation investigation)"
        ),
        "class": "client_or_fact",
    },
    7: {
        "label": "Inaccurate information reported by collateral contact",
        "class": "client_or_fact",
    },
    8: {
        "label": (
            "Acted on incorrect federal computer match information not requiring "
            "verification (variance excluded from error determination but recorded)"
        ),
        "class": "excluded_federal_match",
    },
    10: {"label": "Policy incorrectly applied", "class": "agency_or_system"},
    12: {
        "label": "Reported information disregarded or not applied",
        "class": "agency_or_system",
    },
    14: {
        "label": (
            "Agency failed to follow up on inconsistent or incomplete information"
        ),
        "class": "agency_or_system",
    },
    15: {
        "label": "Agency failed to follow up on impending changes",
        "class": "agency_or_system",
    },
    16: {
        "label": "Agency failed to verify required information",
        "class": "agency_or_system",
    },
    17: {"label": "Computer programming error", "class": "agency_or_system"},
    18: {
        "label": "Data entry and/or coding error",
        "class": "agency_or_system",
    },
    19: {
        "label": "Mass change (computer-generated mass-change error)",
        "class": "agency_or_system",
    },
    20: {
        "label": "Arithmetic computation error",
        "class": "agency_or_system",
    },
    21: {"label": "Computer user error", "class": "agency_or_system"},
    22: {
        "label": "Agency budgeted an incorrect amount",
        "class": "agency_or_system",
    },
    23: {
        "label": (
            "Agency failed to follow recertification procedure related to "
            "notices/forms"
        ),
        "class": "agency_or_system",
    },
    24: {
        "label": (
            "Agency failed to follow recertification procedure related to interviews"
        ),
        "class": "agency_or_system",
    },
    25: {
        "label": (
            "Agency failed to follow recertification procedure related to time frames"
        ),
        "class": "agency_or_system",
    },
    26: {
        "label": (
            "Change not required to be reported by client or acted upon by State "
            "agency under time frames and reporting requirements"
        ),
        "class": "no_required_action",
    },
    99: {"label": "Other", "class": "other"},
}

CAUSE_CLASSES = (
    "agency_or_system",
    "client_or_fact",
    "excluded_federal_match",
    "no_required_action",
    "other",
    "unclassified",
)
EXCLUSIVE_AXIS_CLASSES = (
    "agency_or_system",
    "client_or_fact",
    "mixed_agency_client",
    "residual_or_unclassified",
)
SCENARIO_CODE_SETS = {
    "strict_computation": {
        "codes": (17, 19, 20),
        "label": "Programming, computer-generated mass change, or arithmetic",
    },
    "broad_rules_engine": {
        "codes": (10, 17, 19, 20, 21, 22),
        "label": (
            "Strict set plus policy misapplication, computer-user error, and "
            "incorrect budgeting"
        ),
    },
    "software_only": {
        "codes": (17, 19),
        "label": "Computer programming or computer-generated mass change",
    },
}

STATE_NAME_BY_ABBR = {
    abbreviation: name
    for name, abbreviation in error_model.STATE_NAME_TO_ABBR.items()
}
STATE_FIPS_BY_ABBR = {abbreviation: fips for fips, abbreviation in error_model.FIPS.items()}

FIELD_SEMANTICS = {
    "sibling_inventory": {
        "fields": [f"{root}1-{root}9" for root in DETAIL_ROOTS],
        "meaning": (
            "Nine same-suffix variance records; R denotes a field from raw QC data."
        ),
        "techdoc_citations": ["techdoc.txt:L6179-L6234"],
    },
    "AGENCY1-AGENCY9": {
        "meaning": "Agency or client responsibility; primary cause of variance.",
        "range": [1, 99],
        "techdoc_citations": [
            "techdoc.txt:L6179-L6184",
            "techdoc.txt:L11816-L11973",
        ],
    },
    "AMOUNT1-AMOUNT9": {
        "meaning": "Dollar amount of the same-suffix variance.",
        "range": [0, 2377],
        "techdoc_citations": ["techdoc.txt:L11975-L11997"],
    },
    "DISCOV1-DISCOV9": {
        "meaning": "How the same-suffix variance was discovered; not a cause field.",
        "range": [1, 9],
        "techdoc_citations": ["techdoc.txt:L11999-L12088"],
    },
    "E_FINDG1-E_FINDG9": {
        "meaning": (
            "Impact of the same-suffix variance: 2 overissuance, 3 "
            "underissuance, 4 ineligible. It is not a nature or cause code."
        ),
        "codes": {str(code): label for code, label in IMPACT_CODES.items()},
        "techdoc_citations": ["techdoc.txt:L12090-L12130"],
    },
    "ELEMENT1-ELEMENT9": {
        "meaning": "Program element affected by the same-suffix variance.",
        "range": [111, 820],
        "techdoc_citations": ["techdoc.txt:L12132-L12484"],
    },
    "NATURE1-NATURE9": {
        "meaning": "Nature of the same-suffix variance; not responsibility.",
        "range": [6, 314],
        "techdoc_citations": ["techdoc.txt:L12486-L12900"],
    },
    "OCCDATE1-OCCDATE9": {
        "meaning": "Year and month in which the same-suffix variance occurred.",
        "range": [200304, 999999],
        "techdoc_citations": ["techdoc.txt:L12913-L12939"],
    },
    "TIMEPER1-TIMEPER9": {
        "meaning": "Timing of the variance relative to the agency's most recent action.",
        "range": [1, 9],
        "techdoc_citations": ["techdoc.txt:L12941-L12987"],
    },
    "VERIF1-VERIF9": {
        "meaning": "How the same-suffix variance was verified; not a cause field.",
        "range": [1, 9],
        "techdoc_citations": ["techdoc.txt:L12989-L13065"],
    },
    "CASE": {
        "meaning": "Case classification; code 1 is included in error-rate calculation.",
        "techdoc_citations": ["techdoc.txt:L6348-L6377"],
    },
    "STATUS": {
        "meaning": "1 correct, 2 overissuance, 3 underissuance.",
        "techdoc_citations": ["techdoc.txt:L6766-L6794"],
    },
    "AMTERR": {
        "meaning": (
            "Nonnegative dollar magnitude of any identified case benefit error: "
            "the difference between what the State authorized and should have "
            "authorized."
        ),
        "techdoc_citations": ["techdoc.txt:L9484-L9501"],
    },
    "HWGT": {
        "meaning": (
            "Monthly sample weight. For the 12 monthly FY samples, summing "
            "HWGT times a monthly dollar amount gives an annual flow; no extra "
            "factor of 12 is applied."
        ),
        "techdoc_citations": ["techdoc.txt:L7358-L7377"],
    },
    "STATE": {
        "meaning": "FIPS code for State or territory.",
        "techdoc_citations": ["techdoc.txt:L7534-L7550"],
    },
}


def _rounded(value: float, digits: int) -> float:
    """Return a stable finite rounded float, normalizing negative zero."""
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"Artifact contains a non-finite number: {number}")
    result = round(number, digits)
    return 0.0 if result == 0 else result


def _share(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else _rounded(numerator / denominator, 12)


def _cause_code(value: object) -> int | None:
    if pd.isna(value):
        return None
    number = float(value)
    if not number.is_integer():
        raise ValueError(f"Fractional AGENCY code: {value}")
    code = int(number)
    if code not in CAUSE_CODES:
        raise ValueError(f"Undocumented AGENCY code: {code}")
    return code


def _cause_class(value: object) -> str:
    code = _cause_code(value)
    return "unclassified" if code is None else CAUSE_CODES[code]["class"]


def _metric(
    mask: pd.Series,
    *,
    weights: pd.Series,
    dollars: pd.Series,
    denominator_dollars: float,
) -> dict[str, int | float]:
    selected = mask.fillna(False).astype(bool)
    total_dollars = float(dollars.loc[selected].sum())
    return {
        "n": int(selected.sum()),
        "weighted_n": _rounded(weights.loc[selected].sum(), 6),
        "dollars": _rounded(total_dollars, 2),
        "share_of_official_error_dollars": _share(
            total_dollars, denominator_dollars
        ),
    }


def _fractional_class_allocations(cases: pd.DataFrame) -> pd.DataFrame:
    """Split every case equally across its distinct documented cause classes."""
    records: list[dict[str, Any]] = []
    for index, row in cases.iterrows():
        classes = {
            _cause_class(row[f"AGENCY{slot}"])
            for slot in SLOTS
            if pd.notna(row[f"AGENCY{slot}"])
        }
        if not classes:
            classes = {"unclassified"}
        fraction = 1.0 / len(classes)
        for cause_class in sorted(classes):
            records.append(
                {
                    "case_index": index,
                    "class": cause_class,
                    "fraction": fraction,
                    "weight": float(row["HWGT"]),
                    "case_dollars": float(row["HWGT"] * row["AMTERR"]),
                    "allocated_dollars": float(
                        row["HWGT"] * row["AMTERR"] * fraction
                    ),
                }
            )
    return pd.DataFrame.from_records(records)


def _fractional_metrics(
    allocations: pd.DataFrame, denominator_dollars: float
) -> dict[str, dict[str, int | float]]:
    metrics: dict[str, dict[str, int | float]] = {}
    for cause_class in CAUSE_CLASSES:
        part = allocations.loc[allocations["class"].eq(cause_class)]
        allocated_dollars = float(part["allocated_dollars"].sum())
        metrics[cause_class] = {
            "n_cases": len(part),
            "weighted_n_cases": _rounded(part["weight"].sum(), 6),
            "fractional_n": _rounded(part["fraction"].sum(), 6),
            "fractional_weighted_n": _rounded(
                (part["weight"] * part["fraction"]).sum(), 6
            ),
            "dollars": _rounded(allocated_dollars, 2),
            "share_of_official_error_dollars": _share(
                allocated_dollars, denominator_dollars
            ),
        }
    return metrics


def _case_classes(cases: pd.DataFrame) -> pd.Series:
    """Collapse the agency/client axis while retaining mixed and residual cases."""
    result: dict[Any, str] = {}
    for index, row in cases.iterrows():
        classes = {
            _cause_class(row[f"AGENCY{slot}"])
            for slot in SLOTS
            if pd.notna(row[f"AGENCY{slot}"])
        }
        agency = "agency_or_system" in classes
        client = "client_or_fact" in classes
        if agency and client:
            result[index] = "mixed_agency_client"
        elif agency:
            result[index] = "agency_or_system"
        elif client:
            result[index] = "client_or_fact"
        else:
            result[index] = "residual_or_unclassified"
    return pd.Series(result, name="exclusive_axis_class")


def _long_elements(cases: pd.DataFrame) -> pd.DataFrame:
    records = []
    for slot in SLOTS:
        part = cases[
            [
                "HWGT",
                "AMTERR",
                f"AGENCY{slot}",
                f"AMOUNT{slot}",
                f"E_FINDG{slot}",
                f"ELEMENT{slot}",
            ]
        ].copy()
        part.columns = [
            "weight",
            "case_amterr",
            "agency",
            "amount",
            "finding",
            "element",
        ]
        part["case_index"] = part.index
        part["slot"] = slot
        records.append(part)
    long = pd.concat(records, ignore_index=True)
    long["amount"] = pd.to_numeric(long["amount"], errors="coerce")
    long["finding"] = pd.to_numeric(long["finding"], errors="coerce")
    if long["amount"].dropna().lt(0).any():
        raise ValueError("AMOUNTi contains a negative value")
    long = long.loc[
        long["finding"].isin(IMPACT_CODES) & long["amount"].gt(0)
    ].copy()
    long["class"] = long["agency"].map(_cause_class)
    long["impact"] = long["finding"].astype(int).map(IMPACT_CODES)
    long["dollars"] = long["weight"] * long["amount"]
    return long


def _element_metric(
    part: pd.DataFrame,
    *,
    official_dollars: float,
    attributed_dollars: float,
) -> dict[str, int | float]:
    dollars = float(part["dollars"].sum())
    return {
        "n": len(part),
        "weighted_n": _rounded(part["weight"].sum(), 6),
        "dollars": _rounded(dollars, 2),
        "share_of_attributed_element_dollars": _share(dollars, attributed_dollars),
        "share_of_official_error_dollars": _share(dollars, official_dollars),
    }


def _element_summary(
    elements: pd.DataFrame, official_dollars: float, cases: pd.DataFrame
) -> dict[str, Any]:
    attributed_dollars = float(elements["dollars"].sum())
    classes = {
        cause_class: _element_metric(
            elements.loc[elements["class"].eq(cause_class)],
            official_dollars=official_dollars,
            attributed_dollars=attributed_dollars,
        )
        for cause_class in CAUSE_CLASSES
    }
    impacts = {
        impact: _element_metric(
            elements.loc[elements["impact"].eq(impact)],
            official_dollars=official_dollars,
            attributed_dollars=attributed_dollars,
        )
        for impact in IMPACT_CODES.values()
    }
    slots: dict[str, Any] = {}
    for slot in SLOTS:
        slot_elements = elements.loc[elements["slot"].eq(slot)]
        slots[str(slot)] = {
            "total": _element_metric(
                slot_elements,
                official_dollars=official_dollars,
                attributed_dollars=attributed_dollars,
            ),
            "classes": {
                cause_class: _element_metric(
                    slot_elements.loc[slot_elements["class"].eq(cause_class)],
                    official_dollars=official_dollars,
                    attributed_dollars=attributed_dollars,
                )
                for cause_class in CAUSE_CLASSES
            },
        }

    case_element_sums = elements.groupby("case_index")["amount"].sum().reindex(
        cases.index, fill_value=0.0
    )
    return {
        "selection": "E_FINDGi in {2,3,4} and AMOUNTi > 0, paired at suffix i",
        "scope_warning": (
            "These are recorded variance amounts inside official-error cases, not "
            "a guaranteed decomposition of case AMTERR. In particular, code 8 is "
            "documented as excluded from error determination."
        ),
        "total": _element_metric(
            elements,
            official_dollars=official_dollars,
            attributed_dollars=attributed_dollars,
        ),
        "classes": classes,
        "by_impact": impacts,
        "by_slot": slots,
        "reconciliation": {
            "official_error_dollars": _rounded(official_dollars, 2),
            "attributed_element_dollars": _rounded(attributed_dollars, 2),
            "difference_element_minus_official_dollars": _rounded(
                attributed_dollars - official_dollars, 2
            ),
            "element_to_official_dollar_ratio": _share(
                attributed_dollars, official_dollars
            ),
            "n_cases_with_positive_paired_element": int(
                elements["case_index"].nunique()
            ),
            "n_cases_without_positive_paired_element": int(
                len(cases) - elements["case_index"].nunique()
            ),
            "n_cases_element_amount_sum_equals_amterr": int(
                np.isclose(case_element_sums, cases["AMTERR"], atol=0, rtol=0).sum()
            ),
        },
    }


def _case_summary(cases: pd.DataFrame, official_dollars: float) -> dict[str, Any]:
    weights = cases["HWGT"]
    dollars = weights * cases["AMTERR"]
    allocations = _fractional_class_allocations(cases)
    allocated_sum = float(allocations["allocated_dollars"].sum())
    if not np.isclose(allocated_sum, official_dollars, rtol=1e-12, atol=0.01):
        raise AssertionError("Fractional case attribution does not exhaust dollars")

    exclusive = _case_classes(cases)
    exclusive_metrics = {
        cause_class: _metric(
            exclusive.eq(cause_class),
            weights=weights,
            dollars=dollars,
            denominator_dollars=official_dollars,
        )
        for cause_class in EXCLUSIVE_AXIS_CLASSES
    }

    code_sets: dict[int, set[Any]] = {code: set() for code in CAUSE_CODES}
    class_sets: dict[str, set[Any]] = {cause_class: set() for cause_class in CAUSE_CLASSES}
    for index, row in cases.iterrows():
        observed_codes = {
            _cause_code(row[f"AGENCY{slot}"])
            for slot in SLOTS
            if pd.notna(row[f"AGENCY{slot}"])
        }
        if not observed_codes:
            class_sets["unclassified"].add(index)
        for code in observed_codes:
            if code is None:
                continue
            code_sets[code].add(index)
            class_sets[CAUSE_CODES[code]["class"]].add(index)

    by_code = {
        str(code): {
            "label": details["label"],
            **_metric(
                pd.Series(cases.index.isin(code_sets[code]), index=cases.index),
                weights=weights,
                dollars=dollars,
                denominator_dollars=official_dollars,
            ),
        }
        for code, details in sorted(CAUSE_CODES.items())
    }
    any_presence = {
        cause_class: _metric(
            pd.Series(cases.index.isin(class_sets[cause_class]), index=cases.index),
            weights=weights,
            dollars=dollars,
            denominator_dollars=official_dollars,
        )
        for cause_class in CAUSE_CLASSES
    }
    scenario_subsets = {}
    for name, definition in SCENARIO_CODE_SETS.items():
        indexes = set().union(*(code_sets[code] for code in definition["codes"]))
        scenario_subsets[name] = {
            "codes": list(definition["codes"]),
            "label": definition["label"],
            **_metric(
                pd.Series(cases.index.isin(indexes), index=cases.index),
                weights=weights,
                dollars=dollars,
                denominator_dollars=official_dollars,
            ),
        }

    agency_indexes = class_sets["agency_or_system"]
    client_indexes = class_sets["client_or_fact"]
    overlap = agency_indexes & client_indexes
    residual_indexes = (
        class_sets["excluded_federal_match"]
        | class_sets["no_required_action"]
        | class_sets["other"]
    )
    axis_indexes = agency_indexes | client_indexes
    return {
        "fractional_class_attribution": {
            "method": (
                "Split each case's HWGT*AMTERR equally across the distinct cause "
                "classes present in its nonmissing AGENCY1-9 slots; repeated slots "
                "within a class do not add weight; a case with no code is unclassified."
            ),
            "classes": _fractional_metrics(allocations, official_dollars),
            "allocated_dollars": _rounded(allocated_sum, 2),
        },
        "exclusive_axis": {
            "method": (
                "Agency only, client/fact only, both (mixed), or neither/residual, "
                "based on any nonmissing AGENCY1-9 code."
            ),
            "classes": exclusive_metrics,
        },
        "any_presence": {
            "method": (
                "Credit the full case AMTERR to every cause class present. Classes "
                "overlap and their dollars must not be summed."
            ),
            "classes": any_presence,
            "by_code": by_code,
        },
        "scenario_subsets_any_presence": {
            "method": (
                "Legacy case-attribution sensitivity: credit full AMTERR if any "
                "AGENCY slot contains a listed code. Sets are nested/overlapping."
            ),
            "classes": scenario_subsets,
        },
        "overlap_diagnostics": {
            "agency_client": _metric(
                pd.Series(cases.index.isin(overlap), index=cases.index),
                weights=weights,
                dollars=dollars,
                denominator_dollars=official_dollars,
            ),
            "axis_plus_residual": _metric(
                pd.Series(
                    cases.index.isin(axis_indexes & residual_indexes), index=cases.index
                ),
                weights=weights,
                dollars=dollars,
                denominator_dollars=official_dollars,
            ),
            "no_agency_code": _metric(
                pd.Series(
                    cases.index.isin(class_sets["unclassified"]), index=cases.index
                ),
                weights=weights,
                dollars=dollars,
                denominator_dollars=official_dollars,
            ),
        },
    }


def _state_row(
    state: str,
    universe: pd.DataFrame,
    official_cases: pd.DataFrame,
) -> dict[str, Any]:
    if state == "US":
        state_universe = universe
        cases = official_cases
        state_fips: int | None = None
        state_name = "United States"
    else:
        state_universe = universe.loc[universe["state"].eq(state)]
        cases = official_cases.loc[official_cases["state"].eq(state)]
        state_fips = STATE_FIPS_BY_ABBR[state]
        state_name = STATE_NAME_BY_ABBR[state]

    official_dollars = float((cases["HWGT"] * cases["AMTERR"]).sum())
    elements = _long_elements(cases)
    return {
        "state": state,
        "state_fips": state_fips,
        "state_name": state_name,
        "universe_n": len(state_universe),
        "universe_weighted_n": _rounded(state_universe["HWGT"].sum(), 6),
        "n": len(cases),
        "weighted_n": _rounded(cases["HWGT"].sum(), 6),
        "average_monthly_weighted_n": _rounded(cases["HWGT"].sum() / 12, 6),
        "official_error_dollars": _rounded(official_dollars, 2),
        "case_attributed": _case_summary(cases, official_dollars),
        "element_attributed": _element_summary(elements, official_dollars, cases),
    }


def compute_rows(universe: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute the 53 jurisdiction rows and a national row."""
    required = [
        "CASE",
        "STATE",
        "STATUS",
        "AMTERR",
        "HWGT",
        "year",
        "state",
        *DETAIL_COLUMNS,
    ]
    error_model.assert_required_columns(universe, required, context="cause-share input")
    if not universe["CASE"].eq(1).all():
        raise ValueError("cause-share input must already be restricted to CASE == 1")
    weights = pd.to_numeric(universe["HWGT"], errors="coerce")
    if weights.isna().any() or weights.le(0).any():
        raise ValueError("HWGT must be nonmissing and positive")

    official_mask = error_model.official_error_label(universe).eq(1)
    official_cases = universe.loc[official_mask].copy()
    expected_states = set(error_model.FIPS.values())
    observed_states = set(universe["state"])
    if observed_states != expected_states:
        raise ValueError(
            "FY2024 State coverage mismatch: "
            f"missing={sorted(expected_states - observed_states)}, "
            f"extra={sorted(observed_states - expected_states)}"
        )

    rows = [
        _state_row(state, universe, official_cases)
        for state in sorted(expected_states)
    ]
    rows.append(_state_row("US", universe, official_cases))
    return rows


def _class_sets_for_row(row: pd.Series) -> set[str]:
    classes = {
        _cause_class(row[f"AGENCY{slot}"])
        for slot in SLOTS
        if pd.notna(row[f"AGENCY{slot}"])
    }
    return classes or {"unclassified"}


def _replay_metric(
    frame: pd.DataFrame, denominator_dollars: float
) -> dict[str, int | float]:
    dollars = float(frame["case_dollars"].sum())
    return {
        "n": len(frame),
        "weighted_n": _rounded(frame["HWGT"].sum(), 6),
        "dollars": _rounded(dollars, 2),
        "share_of_slice_dollars": _share(dollars, denominator_dollars),
    }


def colorado_replay_reconciliation(universe: pd.DataFrame) -> dict[str, Any]:
    """Crosswalk the committed 283-case Colorado replay to all nine SAV slots."""
    replay = pd.DataFrame(json.loads(REPLAY_PATH.read_text(encoding="utf-8")))
    replay["source_row_index"] = replay["case_id"].str.rsplit("-", n=1).str[-1].astype(int)
    if replay["source_row_index"].duplicated().any():
        raise ValueError("Replay contains duplicate source-row identifiers")

    co = universe.loc[universe["state"].eq("CO")].set_index("source_row_index")
    missing = sorted(set(replay["source_row_index"]) - set(co.index))
    if missing:
        raise ValueError(f"Replay rows absent from FY2024 CO universe: {missing}")
    joined = co.loc[replay["source_row_index"]].copy().reset_index()
    replay = replay.reset_index(drop=True)
    if not np.allclose(joined["AMTERR"], replay["amterr"], atol=0, rtol=0):
        raise ValueError("Replay AMTERR does not match source SAV")
    if not np.allclose(joined["HWGT"], replay["weight"], atol=1e-6, rtol=0):
        raise ValueError("Replay HWGT does not match source SAV")
    if not joined["STATUS"].astype(int).eq(replay["status"].astype(int)).all():
        raise ValueError("Replay STATUS does not match source SAV")

    for column in replay.columns:
        if column not in joined:
            joined[column] = replay[column]
    joined["case_dollars"] = joined["HWGT"] * joined["AMTERR"]
    joined["engine_outcome"] = np.where(
        joined["within5"], "explained_input_facts", "computation_side_upper_bound"
    )
    joined["official_above_threshold"] = error_model.official_error_label(joined).eq(1)
    joined["cause_classes"] = joined.apply(_class_sets_for_row, axis=1)
    joined["qc_any_agency"] = joined["cause_classes"].map(
        lambda classes: "agency_or_system" in classes
    )
    joined["qc_broad_rules_engine"] = joined.apply(
        lambda row: any(
            _cause_code(row[f"AGENCY{slot}"])
            in SCENARIO_CODE_SETS["broad_rules_engine"]["codes"]
            for slot in SLOTS
            if pd.notna(row[f"AGENCY{slot}"])
        ),
        axis=1,
    )

    slices = {
        "all_283": joined,
        "official_above_threshold_97": joined.loc[
            joined["official_above_threshold"]
        ],
        "subthreshold_186": joined.loc[~joined["official_above_threshold"]],
    }
    slice_metrics: dict[str, Any] = {}
    for name, part in slices.items():
        denominator = float(part["case_dollars"].sum())
        slice_metrics[name] = {
            "total": _replay_metric(part, denominator),
            "outcomes": {
                outcome: _replay_metric(
                    part.loc[part["engine_outcome"].eq(outcome)], denominator
                )
                for outcome in (
                    "explained_input_facts",
                    "computation_side_upper_bound",
                )
            },
            "solver_engine_within5_concordant_n": int(
                part["solver_within5"].eq(part["within5"]).sum()
            ),
        }

    official = slices["official_above_threshold_97"].copy()
    official_denominator = float(official["case_dollars"].sum())
    fractional_records = []
    for index, row in official.iterrows():
        classes = row["cause_classes"]
        fraction = 1 / len(classes)
        for cause_class in sorted(classes):
            fractional_records.append(
                {
                    "class": cause_class,
                    "outcome": row["engine_outcome"],
                    "fraction": fraction,
                    "weight": row["HWGT"],
                    "dollars": row["case_dollars"] * fraction,
                    "source_index": index,
                }
            )
    crosswalk = pd.DataFrame(fractional_records)
    fractional_cross_tab: dict[str, Any] = {}
    for cause_class in CAUSE_CLASSES:
        fractional_cross_tab[cause_class] = {}
        for outcome in (
            "explained_input_facts",
            "computation_side_upper_bound",
        ):
            part = crosswalk.loc[
                crosswalk["class"].eq(cause_class)
                & crosswalk["outcome"].eq(outcome)
            ]
            dollars = float(part["dollars"].sum())
            fractional_cross_tab[cause_class][outcome] = {
                "fractional_n": _rounded(part["fraction"].sum(), 6),
                "fractional_weighted_n": _rounded(
                    (part["weight"] * part["fraction"]).sum(), 6
                ),
                "dollars": _rounded(dollars, 2),
                "share_of_replay_official_dollars": _share(
                    dollars, official_denominator
                ),
            }

    binary_cross_tab: dict[str, Any] = {}
    for qc_label, qc_value in (
        ("qc_any_agency", True),
        ("qc_no_agency", False),
    ):
        binary_cross_tab[qc_label] = {}
        for outcome in (
            "explained_input_facts",
            "computation_side_upper_bound",
        ):
            part = official.loc[
                official["qc_any_agency"].eq(qc_value)
                & official["engine_outcome"].eq(outcome)
            ]
            binary_cross_tab[qc_label][outcome] = _replay_metric(
                part, official_denominator
            )

    all_replay = slices["all_283"]
    all_replay_dollars = float(all_replay["case_dollars"].sum())
    broad_residual = all_replay.loc[
        all_replay["qc_broad_rules_engine"]
        & all_replay["engine_outcome"].eq("computation_side_upper_bound")
    ].copy()
    broad_residual["engine_gap_dollars"] = (
        (broad_residual["engine_on_original"] - broad_residual["rawben"]).abs()
        * broad_residual["HWGT"]
    )

    co_official_total = int(
        error_model.official_error_label(
            universe.loc[universe["state"].eq("CO")]
        ).sum()
    )
    return {
        "reference": {
            "path": str(REPLAY_PATH.relative_to(Path(__file__).parents[1])),
            "sha256": error_model._sha256(REPLAY_PATH),
            "classification": (
                "abs(engine_on_original - RAWBEN) <= 5; a miss is a "
                "computation-side upper bound, not a proven computation error"
            ),
        },
        "denominator_reconciliation": {
            "co_status_2_or_3_n": int(
                universe.loc[
                    universe["state"].eq("CO"), "STATUS"
                ].isin([2, 3]).sum()
            ),
            "co_official_above_threshold_n": co_official_total,
            "replay_all_n": len(joined),
            "replay_official_above_threshold_n": int(
                joined["official_above_threshold"].sum()
            ),
            "official_cases_excluded_by_replay_filter_n": int(
                co_official_total - joined["official_above_threshold"].sum()
            ),
        },
        "slices": slice_metrics,
        "official_replay_fractional_cause_by_engine_outcome": fractional_cross_tab,
        "official_replay_any_agency_by_engine_outcome": binary_cross_tab,
        "committed_prose_discrepancy": {
            "claim_location": (
                "paper/snapshot/labs/amterr/ANALYSIS.md:L62-L67"
            ),
            "claim": "10 cases, $3.28M, 3.3%",
            "recomputed_broad_residual_n": len(broad_residual),
            "recomputed_hwgt_times_amterr_dollars": _rounded(
                broad_residual["case_dollars"].sum(), 2
            ),
            "recomputed_share_of_283_replay_dollars": _share(
                broad_residual["case_dollars"].sum(), all_replay_dollars
            ),
            "recomputed_hwgt_times_engine_gap_dollars": _rounded(
                broad_residual["engine_gap_dollars"].sum(), 2
            ),
            "assessment": (
                "The 10-case count reproduces from all nine SAV AGENCY slots; "
                "neither available dollar definition reproduces $3.28M."
            ),
        },
    }


def _cause_code_metadata() -> dict[str, Any]:
    return {
        str(code): {
            **details,
            "classification_status": "analysis_mapping_from_published_label",
        }
        for code, details in sorted(CAUSE_CODES.items())
    }


def build_artifact() -> dict[str, Any]:
    """Load the pinned public SAV and return the complete artifact payload."""
    universe = error_model.load_year(
        FISCAL_YEAR,
        include_source_row_index=True,
        additional_columns=DETAIL_COLUMNS,
    )
    rows = compute_rows(universe)
    sav_path = error_model.QC_DIR / f"qc_pub_fy{FISCAL_YEAR}.sav"
    packages = {
        package: importlib.metadata.version(package)
        for package in ("numpy", "pandas", "pyreadstat")
    }
    public_csv = {
        "path": "~/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv",
        "role": "independent public-schema audit only; computations use SAV",
    }
    if PUBLIC_CSV_PATH.exists():
        public_csv.update(
            {
                "sha256": error_model._sha256(PUBLIC_CSV_PATH),
                "bytes": PUBLIC_CSV_PATH.stat().st_size,
            }
        )

    return {
        "schema": "snap_qc_sim.cause_shares.v1",
        "schema_version": 1,
        "fiscal_year": FISCAL_YEAR,
        "public_file_supports_element_primary_cause": True,
        "support_statement": (
            "The public SAV contains AGENCY1-9, documented as agency or client "
            "responsibility and primary cause of variance. It does not contain an "
            "exhaustive binary agency/client flag or a direct allocation of case "
            "AMTERR across findings, and cause attribution is not a causal estimate "
            "of errors preventable by a verified rules engine."
        ),
        "field_semantics": FIELD_SEMANTICS,
        "cause_codes": _cause_code_metadata(),
        "class_semantics": {
            "agency_or_system": (
                "Codes 10, 12, and 14-25. This includes agency process, data-entry, "
                "policy, programming, and computation causes; it is broader than "
                "rules-engine logic errors."
            ),
            "client_or_fact": (
                "Codes 1-4 and 7. Combining information-not-reported, explicit "
                "client codes, and collateral-contact inaccuracy is an analysis "
                "superclass, not a codebook-defined binary."
            ),
            "excluded_federal_match": (
                "Code 8, kept separate because the codebook says the variance is "
                "excluded from error determination even though such elements occur "
                "inside some official-error cases."
            ),
            "no_required_action": "Code 26; neither client reporting nor agency action required.",
            "other": "Code 99; no more specific public semantics.",
            "unclassified": "No nonmissing documented AGENCY code; never imputed.",
        },
        "attribution_conventions": {
            "primary_case_partition": (
                "Equal split across distinct cause classes in the case; exhaustive "
                "and nonoverlapping after fractional allocation. It scans all "
                "recorded variance causes, including findings that may not contribute "
                "to case AMTERR, because the public file supplies no exact linkage."
            ),
            "exclusive_axis": (
                "Whole-case agency-only/client-only/mixed/residual diagnostic."
            ),
            "any_presence": (
                "Whole AMTERR credited to every present class/code; intentionally "
                "overlapping and included for code-level regrouping and legacy comparison."
            ),
            "element": (
                "Positive AMOUNTi with same-slot E_FINDGi in {2,3,4}; no attempt "
                "to force element sums to equal AMTERR. These are recorded variance "
                "amounts inside official-error cases; code 8 is expressly excluded "
                "from error determination by the codebook."
            ),
        },
        "provenance": {
            "input_sav": {
                "path": "~/.cache/axiom-oracles/snap_qc_repo/qc_data/qc_pub_fy2024.sav",
                "sha256": error_model._sha256(sav_path),
                "bytes": sav_path.stat().st_size,
            },
            "public_csv": public_csv,
            "technical_documentation": {
                "path": "~/.cache/axiom-oracles/snap-qc/techdoc.txt",
                "sha256": error_model._sha256(TECHDOC_PATH),
                "bytes": TECHDOC_PATH.stat().st_size,
            },
            "generator": {
                "path": "analysis/cause_shares.py",
                "sha256": error_model._sha256(Path(__file__)),
            },
            "loader": {
                "path": "analysis/train_error_model.py",
                "function": "load_year",
                "universe_function": "filter_case_universe",
                "official_error_function": "official_error_label",
                "sha256": error_model._sha256(Path(error_model.__file__)),
            },
            "universe": "CASE == 1",
            "official_error": "STATUS in {2,3} and AMTERR > 56",
            "threshold_dollars": error_model.THRESHOLD[FISCAL_YEAR],
            "threshold_comparison": "strictly greater than",
            "dollar_formula": "sum(HWGT * AMTERR) over official-error cases",
            "element_dollar_formula": (
                "sum(HWGT * AMOUNTi) where E_FINDGi in {2,3,4} and AMOUNTi > 0"
            ),
            "annualization": (
                "The FY file pools 12 monthly samples. HWGT is monthly; pooling "
                "monthly dollar flows across all samples already yields annual "
                "dollars, so no additional factor of 12 is applied."
            ),
            "rounding": {
                "dollars": "nearest cent",
                "weighted_counts": "6 decimal places",
                "shares": "12 decimal places",
                "calculation_order": "aggregate unrounded binary64 values, then round",
            },
            "packages": packages,
            "python": sys.version.split()[0],
            "determinism": "No timestamps, randomness, locale formatting, or absolute paths.",
        },
        "rows": rows,
        "colorado_replay_reconciliation": colorado_replay_reconciliation(universe),
    }


def write_artifact(
    payload: Mapping[str, Any], path: Path = OUTPUT_PATH
) -> None:
    """Write canonical deterministic JSON with a terminal newline."""
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Iterable[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        raise SystemExit("cause_shares.py takes no arguments")
    write_artifact(build_artifact())


if __name__ == "__main__":
    main()
