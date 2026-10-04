"""Recompute every quantitative claim in ANALYSIS.md from committed artifacts.

Inputs:

* ``amterr_replay_results.json`` and ``co_fy2024_reconstruction.csv`` (this
  directory): the July 2026 replay and solver outputs, committed as-is;
* the FY2024 SNAP QC public-use CSV, in one or both of its two postings.

Outputs ``claims_audit.json`` (this directory). The audit also regenerates
``native_decomposition.json`` and ``../phase_a_classification.json`` from the
May 2026 posting and records whether they match the committed copies. To check
ANALYSIS.md's account of the solver, it ports the solver's benefit formula and
utility reset from ``reconstruct_co_fy2024.R`` and fails unless the port
reproduces every benefit the solver recorded.

The two postings differ only in the weight columns (HWGT, FYWGT, HWGT_OLD,
FYWGT_OLD); the audit re-verifies that, so every case-level result (which
cases the solver moved, which the engine reproduces) is posting-invariant and
only weighted dollars move.

Usage, from the repository root::

    uv run --extra analysis python paper/snapshot/labs/amterr/audit_claims.py
    uv run --extra analysis python paper/snapshot/labs/amterr/audit_claims.py --check

Environment (defaults in ``POSTINGS``):

    SNAP_QC_CSV_MAY2026  qc_pub_fy2024.csv from the May 2026 posting
    SNAP_QC_CSV_AUG2026  qc_pub_fy2024.csv from the August 2026 posting
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LAB = Path(__file__).resolve().parent
REPO = LAB.parents[3]
REPLAY_PATH = LAB / "amterr_replay_results.json"
RECONSTRUCTION_PATH = LAB / "co_fy2024_reconstruction.csv"
NATIVE_PATH = LAB / "native_decomposition.json"
PHASE_A_PATH = LAB.parent / "phase_a_classification.json"
OUTPUT_PATH = LAB / "claims_audit.json"

# USDA replaces postings rather than editing them. Each entry pins the zip and
# the CSV member so a mislabeled local file fails loudly.
POSTINGS: dict[str, dict[str, str]] = {
    "may2026": {
        "env": "SNAP_QC_CSV_MAY2026",
        "default": "~/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv",
        "zip_url": (
            "https://snapqcdata.net/sites/default/files/2026-05/qcfy2024_csv.zip"
        ),
        "zip_sha256": (
            "0f3230a4318307d3088382546095eebfde03e781da6f65c9eac7f077bd4263f4"
        ),
        "csv_sha256": (
            "45193eb7370463ab3067d71da23a580fec34a5460341e4e750dda0be061e1aa9"
        ),
        "last_modified": "2026-05-21",
        "role": "weights used by the July 2026 lab run",
    },
    "aug2026": {
        "env": "SNAP_QC_CSV_AUG2026",
        "default": "~/.cache/axiom-oracles/snap-qc/aug2026/qc_pub_fy2024.csv",
        "zip_url": (
            "https://snapqcdata.net/sites/default/files/2026-08/qcfy2024_csv.zip"
        ),
        "zip_sha256": (
            "b8b29b8593f78aa51c48332c47d2d92fa5bbecf5346570acb45e26f2d9ebd2b5"
        ),
        "csv_sha256": (
            "e871a8e9caca0be72e2003b09bdf71e1d020984b52289d2b74c4c6b88c4f793b"
        ),
        "last_modified": "2026-08-18",
        "role": "current posting; corrects HWGT and FYWGT",
    },
}
LEGACY_POSTING = "may2026"

# FNS payment error rate tables (percent): FY2024 dated 2025-06-30, FY2025
# dated 2026-06-24.
OFFICIAL_RATES = {
    "fy2024": {"CO": 9.97, "US": 10.93, "dated": "2025-06-30"},
    "fy2025": {"CO": 10.09, "US": 10.62, "dated": "2026-06-24"},
}
THRESHOLD_FY2024 = 56
COLORADO_FIPS = 8
REPLAY_TOLERANCE = 5
COST_SHARE_STEP = 0.05

SLOTS = tuple(range(1, 10))
STRICT_CODES = frozenset({17, 19, 20})
BROAD_CODES = frozenset({10, 17, 19, 20, 21, 22})
SOFTWARE_CODES = frozenset({17, 19})
AXIS1_CLASSES = {
    "software_17_19": frozenset({17, 19}),
    "worker_computation_20_21": frozenset({20, 21}),
    "data_entry_18": frozenset({18}),
    "policy_or_budgeted_10_22": frozenset({10, 22}),
}
INHERENT_COMPUTATION_NATURES = frozenset({36, 42, 43, 54, 64, 65, 75, 79, 80, 98, 123})
DEDUCTION_NATURES = frozenset({52, 53, 56, 57})
# native_decomposition.json's "nc" field: the inherent natures plus 28
# (incorrect income limit applied) and 127 (pass-through not considered or
# incorrectly applied). Neither occurs in a Colorado error case.
NC_NATURES = INHERENT_COMPUTATION_NATURES | {28, 127}
ARITHMETIC_ELEMENT = 520
PHASE_A_CLASSES = ("input_other", "mixed", "pure_math", "input_system_caused")

# The eight inputs amterr_replay.py feeds the engine, and the file fields the
# solver initializes them from (missing values become 0).
REPLAY_INPUTS = {
    "rawusize": "FSUSIZE",
    "rawearn": "FSEARN",
    "rawunearn": "FSUNEARN",
    "rawrent": "RENT",
    "rawutil": "UTIL",
    "rawmedded": "FSMEDDED",
    "rawdepded": "FSDEPDED",
    "rawcsded": "FSCSDED",
}
# The input the solver moves for each ELEMENT1 it handles
# (reconstruct_co_fy2024.R, adjust_* calls and the element-150 step).
SOLVER_ELEMENT_INPUTS = {
    **dict.fromkeys(
        (331, 332, 333, 334, 335, 336, 342, 343, 344, 345, 346, 350), "rawunearn"
    ),
    **dict.fromkeys((311, 312, 314, 321), "rawearn"),
    363: "rawrent",
    364: "rawutil",
    365: "rawmedded",
    323: "rawdepded",
    366: "rawcsded",
    150: "rawusize",
}
# The solver's step size, step limit and within-$3 stop (income_shift,
# max_iterations and diff_matches in reconstruct_co_fy2024.R).
SOLVER_STEP = 3
SOLVER_MAX_STEPS = 1000
SOLVER_MATCH = 3
# FY2024 excess shelter deduction cap (48 states and DC; snap_qc
# additional_data/year_data.csv). The solver lifts it for units with an
# elderly or disabled member (FSNELDER + FSNDIS > 0).
SHELTER_CAP_FY2024 = 672
# FY2024 maximum allotments by household size, 48 states and DC (snap_qc
# additional_data/max_allotments.csv). The solver keeps only rows whose BENMAX
# matches this table, which also bounds the utility reset's candidate pool.
MAX_ALLOTMENT_FY2024 = {
    **dict(enumerate((291, 535, 766, 973, 1155, 1386, 1532, 1751), start=1)),
    **{size: 1751 + 219 * (size - 8) for size in range(9, 21)},
}
# The reset's candidates: amounts more than this many filtered cases report.
UTILITY_CANDIDATE_MIN_CASES = 5
UTILITY_RESET_NOTES = ("util_up", "util_down")
# The input each stepped label moves (adjust_* calls in the R script).
SOLVER_NOTE_INPUTS = {
    "earn": "rawearn",
    "unearn": "rawunearn",
    "rent": "rawrent",
    "util": "rawutil",
    "med": "rawmedded",
    "dep": "rawdepded",
    "cs": "rawcsded",
}
# Stands in for "without limit" when an input is pushed past the solver's
# value: far beyond every Colorado income, cost and the shelter cap.
SOLVER_PUSH = 100_000
# Labels adjust_income gives a moved income when RAWBEN exceeds the file-side
# uncapped benefit, so its steps lower the income (_error: it reached zero).
INCOME_LOWERING_NOTES = ("earn_down", "earn_error", "unearn_down", "unearn_error")
# The solver's benefit inputs, as written to co_fy2024_reconstruction.csv.
SOLVER_BENEFIT_INPUTS = (
    "rawearn",
    "rawunearn",
    "rawrent",
    "rawutil",
    "rawmedded",
    "rawdepded",
    "rawcsded",
    "rawstdded",
    "rawhomeless_ded",
    "rawbenmax",
    "rawminimum_ben",
)

FINDING_COLUMNS = tuple(
    f"{root}{slot}"
    for root in ("AGENCY", "ELEMENT", "NATURE", "AMOUNT")
    for slot in SLOTS
)
QC_COLUMNS = (
    "STATE",
    "YRMONTH",
    "HHLDNO",
    "STATUS",
    "AMTERR",
    "RAWBEN",
    "FSBEN",
    "HWGT",
    "BENMAX",
    "FSNELDER",
    "FSNDIS",
    *REPLAY_INPUTS.values(),
    *FINDING_COLUMNS,
)
WEIGHT_COLUMNS = frozenset({"HWGT", "FYWGT", "HWGT_OLD", "FYWGT_OLD"})


# --------------------------------------------------------------------------
# small helpers


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dollars(value: float) -> float:
    return round(float(value), 2)


def share(numerator: float, denominator: float) -> float:
    return round(float(numerator) / float(denominator), 12) if denominator else 0.0


def points(value: float) -> float:
    return round(float(value), 6)


def case_key(yrmonth: object, hhldno: object) -> str:
    return f"{int(float(yrmonth))}-{int(float(hhldno))}"


def code(value: object) -> int | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    number = float(value)
    if not number.is_integer():
        raise ValueError(f"fractional code {value!r}")
    return int(number)


def posting_path(label: str) -> Path:
    spec = POSTINGS[label]
    return Path(os.environ.get(spec["env"], spec["default"])).expanduser()


def load_posting(label: str, *, verify: bool = True) -> pd.DataFrame:
    path = posting_path(label)
    if not path.exists():
        raise FileNotFoundError(
            f"{label} posting not found at {path}; set {POSTINGS[label]['env']} "
            f"(download {POSTINGS[label]['zip_url']})"
        )
    if verify and sha256(path) != POSTINGS[label]["csv_sha256"]:
        raise ValueError(f"{path} is not the {label} posting (sha256 mismatch)")
    frame = pd.read_csv(path, usecols=list(QC_COLUMNS), low_memory=False)
    frame["key"] = [case_key(y, h) for y, h in zip(frame["YRMONTH"], frame["HHLDNO"])]
    return frame


def any_code(frame: pd.DataFrame, codes: Iterable[int]) -> pd.Series:
    agencies = frame[[f"AGENCY{slot}" for slot in SLOTS]]
    return agencies.isin(list(codes)).any(axis=1)


def findings(row: pd.Series) -> list[tuple[int, int | None, int | None]]:
    """Populated (ELEMENT, NATURE, AGENCY) triples, in slot order."""
    out = []
    for slot in SLOTS:
        element = code(row[f"ELEMENT{slot}"])
        if element is None:
            continue
        out.append((element, code(row[f"NATURE{slot}"]), code(row[f"AGENCY{slot}"])))
    return out


def is_computational(
    finding: tuple[int, int | None, int | None],
    system_codes: frozenset[int] = BROAD_CODES,
) -> bool:
    """Layer-2 rule: inherent computation nature or the arithmetic element;
    deduction natures only when the same slot's cause is system-side."""
    element, nature, agency = finding
    return (
        element == ARITHMETIC_ELEMENT
        or nature in INHERENT_COMPUTATION_NATURES
        or (nature in DEDUCTION_NATURES and agency in system_codes)
    )


def error_cases(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[frame["STATUS"].isin([2, 3])].copy()
    out["error_dollars"] = out["HWGT"] * out["AMTERR"]
    return out


def class_metric(cases: pd.DataFrame, mask: pd.Series, total: float) -> dict:
    selected = cases.loc[mask.fillna(False).astype(bool)]
    value = float(selected["error_dollars"].sum())
    return {
        "n": len(selected),
        "dollars": dollars(value),
        "share": share(value, total),
    }


# --------------------------------------------------------------------------
# posting comparison


def posting_diff() -> dict[str, Any]:
    """Columns that differ between the postings, over every column."""
    may_path, aug_path = posting_path("may2026"), posting_path("aug2026")
    full_may = pd.read_csv(may_path, low_memory=False)
    full_aug = pd.read_csv(aug_path, low_memory=False)
    if list(full_may.columns) != list(full_aug.columns):
        raise AssertionError("postings have different columns")
    if len(full_may) != len(full_aug):
        raise AssertionError("postings have different row counts")
    colorado = full_may["STATE"].eq(COLORADO_FIPS)
    changed = {}
    for column in full_may.columns:
        left, right = full_may[column], full_aug[column]
        differs = ~((left == right) | (left.isna() & right.isna()))
        if differs.any():
            changed[column] = {
                "rows": int(differs.sum()),
                "colorado_rows": int(differs[colorado].sum()),
            }
    if set(changed) - WEIGHT_COLUMNS:
        raise AssertionError(f"non-weight columns changed: {sorted(changed)}")
    return {
        "rows": len(full_may),
        "columns": len(full_may.columns),
        "rows_in_same_order": bool(
            full_may["YRMONTH"].equals(full_aug["YRMONTH"])
            and full_may["HHLDNO"].equals(full_aug["HHLDNO"])
        ),
        "changed_columns": changed,
    }


# --------------------------------------------------------------------------
# layers 1 and 2: regenerate the archived artifacts


def native_decomposition(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Rebuild native_decomposition.json (field meanings in ANALYSIS.md)."""
    out = {}
    for label, part in (("US", frame), ("CO", frame[frame["STATE"] == 8])):
        errors = error_cases(part)
        weights = errors["HWGT"].to_numpy()[:, None]
        agencies = errors[[f"AGENCY{slot}" for slot in SLOTS]]
        natures = errors[[f"NATURE{slot}" for slot in SLOTS]]
        amounts = errors[[f"AMOUNT{slot}" for slot in SLOTS]].fillna(0).to_numpy()
        row: dict[str, float] = {
            "benefit_dollars": float((part["FSBEN"] * part["HWGT"]).sum()),
            "cases": float(len(part)),
            "err_cases": float(len(errors)),
            "err_cases_w": float(errors["HWGT"].sum()),
            "err_dollars": float(errors["error_dollars"].sum()),
            "err_dollars_raw": float(errors["AMTERR"].sum()),
            "under_dollars": float(
                errors.loc[errors["STATUS"] == 3, "error_dollars"].sum()
            ),
            "finding_dollars": float((amounts * weights).sum()),
            "over_dollars": float(
                errors.loc[errors["STATUS"] == 2, "error_dollars"].sum()
            ),
        }
        groups = (
            ("t1", agencies.isin(list(STRICT_CODES))),
            ("t2", agencies.isin(list(BROAD_CODES))),
            ("nc", natures.isin(list(NC_NATURES))),
        )
        for prefix, slot_mask in groups:
            case_mask = slot_mask.any(axis=1)
            row[f"{prefix}_cases_w"] = float(errors.loc[case_mask, "HWGT"].sum())
            row[f"{prefix}_case_dollars"] = float(
                errors.loc[case_mask, "error_dollars"].sum()
            )
            row[f"{prefix}_finding_dollars"] = float(
                (np.where(slot_mask.to_numpy(), amounts, 0.0) * weights).sum()
            )
        out[label] = row
    return out


def phase_a_classification(frame: pd.DataFrame) -> dict[str, Any]:
    """Rebuild ../phase_a_classification.json (Colorado, layer 2)."""
    errors = error_cases(frame[frame["STATE"] == COLORADO_FIPS])
    totals = {name: [0, 0.0, 0.0] for name in PHASE_A_CLASSES}
    listed: dict[str, list[dict[str, Any]]] = {
        "pure_math": [],
        "input_system_caused": [],
    }
    for _, row in errors.sort_values(["YRMONTH", "HHLDNO"]).iterrows():
        found = findings(row)
        flags = [is_computational(f) for f in found]
        if flags and all(flags):
            name = "pure_math"
        elif any(flags):
            name = "mixed"
        elif any(agency in BROAD_CODES for _, _, agency in found):
            name = "input_system_caused"
        else:
            name = "input_other"
        totals[name][0] += 1
        totals[name][1] += float(row["HWGT"])
        totals[name][2] += float(row["error_dollars"])
        if name in listed:
            listed[name].append(
                {
                    "case": f"2024-{case_key(row['YRMONTH'], row['HHLDNO'])}",
                    "status": str(int(row["STATUS"])),
                    "amterr": float(row["AMTERR"]),
                    "w": float(row["HWGT"]),
                    "findings": [list(f) for f in found],
                }
            )
    return {"classes": totals, **listed}


def _max_relative_difference(actual: Any, expected: Any) -> float:
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            return float("inf")
        return max(
            (_max_relative_difference(actual[k], expected[k]) for k in expected),
            default=0.0,
        )
    if isinstance(expected, list):
        if len(actual) != len(expected):
            return float("inf")
        return max(
            (_max_relative_difference(a, e) for a, e in zip(actual, expected)),
            default=0.0,
        )
    if isinstance(expected, float) or isinstance(actual, float):
        scale = max(abs(float(expected)), 1.0)
        return abs(float(actual) - float(expected)) / scale
    return 0.0 if actual == expected else float("inf")


def compare_to_committed(actual: Any, path: Path) -> dict[str, Any]:
    expected = json.loads(path.read_text(encoding="utf-8"))
    difference = _max_relative_difference(actual, expected)
    return {
        "path": path.relative_to(REPO).as_posix(),
        "sha256": sha256(path),
        "regenerated_from_posting": LEGACY_POSTING,
        "matches_committed": bool(difference <= 1e-9),
        "max_relative_difference": float(f"{difference:.3e}"),
    }


# --------------------------------------------------------------------------
# layer 3: the replay


def load_replay() -> pd.DataFrame:
    replay = pd.DataFrame(json.loads(REPLAY_PATH.read_text(encoding="utf-8")))
    replay["key"] = [
        case_key(y, h) for y, h in zip(replay["yrmonth"], replay["hhldno"])
    ]
    reconstruction = pd.read_csv(RECONSTRUCTION_PATH)
    reconstruction["key"] = [
        case_key(y, h)
        for y, h in zip(reconstruction["YRMONTH"], reconstruction["HHLDNO"])
    ]
    solver_columns = [c for c in SOLVER_BENEFIT_INPUTS if c not in REPLAY_INPUTS]
    keep = reconstruction[
        [
            "key",
            "correctedamount",
            "ELEMENT1",
            *REPLAY_INPUTS,
            *solver_columns,
            "at_max",
        ]
    ].rename(columns={"ELEMENT1": "solver_element", "at_max": "solver_at_max"})
    merged = replay.merge(keep, on="key", how="left", validate="1:1")
    if merged["correctedamount"].isna().any():
        raise AssertionError("replay rows missing from the reconstruction")
    merged["reproduced"] = merged["within5"].astype(bool)
    # The solver moves only the input named by ELEMENT1; "no_change" means the
    # element is outside its lists.
    merged["solver_no_change"] = merged["correctednotes"].eq("no_change")
    return merged


def moved_from_keys(replay: pd.DataFrame, unchanged: Iterable[str]) -> pd.Series:
    """Rebuild the moved flag from the committed list of unchanged cases."""
    return ~replay["key"].isin(set(unchanged))


def join_replay(replay: pd.DataFrame, posting: pd.DataFrame) -> pd.DataFrame:
    colorado = posting[posting["STATE"] == COLORADO_FIPS]
    if not colorado["key"].is_unique:
        raise AssertionError("Colorado YRMONTH-HHLDNO keys are not unique")
    joined = replay.merge(colorado, on="key", how="left", validate="1:1")
    if joined["STATE"].isna().any():
        raise AssertionError("replay rows missing from the posting")
    for left, right in (("amterr", "AMTERR"), ("rawben", "RAWBEN"), ("fsben", "FSBEN")):
        if not np.array_equal(joined[left].astype(float), joined[right].astype(float)):
            raise AssertionError(f"replay {left} disagrees with posting {right}")
    joined["error_dollars"] = joined["HWGT"] * joined["AMTERR"]
    joined["engine_equals_fsben"] = joined["engine_on_original"].eq(joined["FSBEN"])
    # An input moved when any replayed input differs from the file value it
    # was initialized from. correctedamount understates this: it is recorded
    # before the utility allowance is snapped to a common state value.
    changed = pd.concat(
        [
            joined[raw].astype(float).ne(joined[field].fillna(0).astype(float))
            for raw, field in REPLAY_INPUTS.items()
        ],
        axis=1,
    )
    joined["solver_moved_input"] = changed.any(axis=1)
    if (joined["solver_moved_input"] & joined["solver_no_change"]).any():
        raise AssertionError("a no_change row has a changed input")
    return classify_solver_moves(joined)


def solver_terms(inputs: pd.DataFrame) -> pd.DataFrame:
    """The solver's benefit and its parts: calculate_raw_benefits in
    reconstruct_co_fy2024.R.

    ``inputs`` carries ``SOLVER_BENEFIT_INPUTS`` and ``shelter_cap`` (infinite
    for a unit with an elderly or disabled member). The operations and their
    order follow the R function, so the floors land on the same doubles.
    Returns the shelter deduction, net income (which may be negative) and the
    benefit.
    """
    earn = inputs["rawearn"]
    net_before_shelter = (earn + inputs["rawunearn"]) - (
        earn * 0.2
        + inputs["rawdepded"]
        + inputs["rawmedded"]
        + inputs["rawcsded"]
        + inputs["rawstdded"]
    )
    half = np.maximum(net_before_shelter * 0.5, 0)
    uncapped_shelter = np.floor((inputs["rawrent"] + inputs["rawutil"]) - half)
    shelter = np.floor(
        np.minimum(np.maximum(uncapped_shelter, 0), inputs["shelter_cap"])
    )
    net = np.floor(net_before_shelter - (shelter + inputs["rawhomeless_ded"]))
    uncapped = np.floor(inputs["rawbenmax"] - 0.3 * net)
    benefit = np.minimum(
        np.maximum(uncapped, inputs["rawminimum_ben"]), inputs["rawbenmax"]
    )
    return pd.DataFrame({"shelter": shelter, "net": net, "benefit": benefit})


def solver_benefit(inputs: pd.DataFrame) -> pd.Series:
    """The solver's benefit (see ``solver_terms``)."""
    return solver_terms(inputs)["benefit"]


def classify_solver_moves(joined: pd.DataFrame) -> pd.DataFrame:
    """Recompute what each move did, with the solver's own benefit formula.

    * ``benefit_after_steps``: the benefit on the inputs the $3 steps reached,
      before the utility reset (the stepped utility amount is the file's UTIL
      plus ``correctedamount``, which the solver records before the reset).
    * ``moved_miss_kind``, for a moved input that does not reproduce:
      ``household_size`` (the one-person move), ``reset_off_after_step_match``
      (the steps reached within $3 of RAWBEN and the reset moved the input off
      that match) or ``steps_stopped_short`` (a stop rule ended the steps on
      the starting side of RAWBEN, more than $3 from it).
    """
    out = joined.copy()
    inputs = out[list(SOLVER_BENEFIT_INPUTS)].astype(float)
    elderly_or_disabled = (out["FSNELDER"] + out["FSNDIS"]) > 0
    inputs["shelter_cap"] = np.where(elderly_or_disabled, np.inf, SHELTER_CAP_FY2024)
    final = solver_benefit(inputs)
    if not final.eq(out["rawben_recreated"].astype(float)).all():
        raise AssertionError("solver_benefit does not reproduce rawben_recreated")

    notes = out["correctednotes"]
    utility = notes.isin(UTILITY_RESET_NOTES)
    stepped = inputs.assign(rawutil=out["UTIL"] + out["correctedamount"])
    out["benefit_after_steps"] = final.where(~utility, solver_benefit(stepped))
    rawben, fsben = out["RAWBEN"].astype(float), out["FSBEN"].astype(float)
    steps_matched = (rawben - out["benefit_after_steps"]).abs() <= SOLVER_MATCH
    household = notes.str.startswith("hhsize")
    moved_miss = out["solver_moved_input"] & ~out["reproduced"]
    kind = pd.Series(
        np.select(
            [
                moved_miss & household,
                moved_miss & ~household & steps_matched,
                moved_miss & ~household & ~steps_matched,
            ],
            [
                "household_size",
                "reset_off_after_step_match",
                "steps_stopped_short",
            ],
            default=None,
        ),
        index=out.index,
        dtype=object,
    )
    if (kind.eq("reset_off_after_step_match") & ~utility).any():
        raise AssertionError("a stepped non-utility miss ended within $3")
    short = kind.eq("steps_stopped_short")
    starting_side = np.sign(rawben - out["benefit_after_steps"]) == np.sign(
        rawben - fsben
    )
    if not starting_side[short].all():
        raise AssertionError("a miss counted as stopped short passed RAWBEN")
    out["moved_miss_kind"] = kind
    # The household-size move's direction comes from the nature code alone.
    out["household_size_move_away_from_rawben"] = household & (
        (final - fsben) * (rawben - fsben) < 0
    )
    out["income_lowered_rawben_at_maximum"] = notes.isin(
        INCOME_LOWERING_NOTES
    ) & rawben.eq(out["rawbenmax"].astype(float))
    out["flat_stretch"] = flat_stretch(out, inputs, final)
    lowered_at_maximum = out["income_lowered_rawben_at_maximum"] & out["reproduced"]
    if not out.loc[lowered_at_maximum, "flat_stretch"].eq("maximum_allotment").all():
        raise AssertionError("an at-maximum income match is not on the cap")
    return out


def flat_stretch(
    joined: pd.DataFrame, inputs: pd.DataFrame, final: pd.Series
) -> pd.Series:
    """Where a reproduced match sits on a flat stretch of the benefit formula.

    The moved input is pushed without limit in the solver's direction (to $0
    when the solver lowered it, up by ``SOLVER_PUSH`` when it raised it). The
    benefit is monotone in each input, so if the pushed benefit still lies
    within $5 of RAWBEN, every amount between the solver's and the limit
    reproduces RAWBEN too, and the match bounds the input on one side only.
    The stretch is named by what makes the formula flat there: the maximum
    allotment, the minimum benefit, or (for a raised rent or utility amount)
    the shelter-deduction cap. A lowered input whose band merely reaches $0
    is left unnamed. Household-size moves are not stepped and are left out.
    """
    notes = joined["correctednotes"]
    column = notes.str.split("_").str[0].map(SOLVER_NOTE_INPUTS)
    candidate = joined["reproduced"] & joined["solver_moved_input"] & column.notna()
    pushed = inputs.copy()
    raised = pd.Series(False, index=joined.index)
    for name in set(column.dropna()):
        rows = candidate & column.eq(name)
        start = joined[REPLAY_INPUTS[name]].fillna(0).astype(float)
        up = rows & (inputs[name] > start)
        raised |= up
        pushed.loc[rows, name] = np.where(
            up[rows], inputs.loc[rows, name] + SOLVER_PUSH, 0.0
        )
    terms = solver_terms(pushed)
    rawben = joined["RAWBEN"].astype(float)
    holds = candidate & (rawben - terms["benefit"]).abs().le(REPLAY_TOLERANCE)
    shelter_input = column.isin(["rawrent", "rawutil"])
    named = np.select(
        [
            holds & terms["benefit"].eq(inputs["rawbenmax"]),
            holds & terms["benefit"].eq(inputs["rawminimum_ben"]),
            holds & raised & shelter_input & terms["shelter"].eq(inputs["shelter_cap"]),
        ],
        ["maximum_allotment", "minimum_benefit", "shelter_cap"],
        default=None,
    )
    return pd.Series(named, index=joined.index, dtype=object)


def solver_outcomes(joined: pd.DataFrame) -> dict[str, Any]:
    """Counts behind ANALYSIS.md's account of what the solver's moves did."""
    reproduced = joined["reproduced"]
    keys = joined["key"]
    notes = joined["correctednotes"]

    household = notes.str.startswith("hhsize")
    away = joined["household_size_move_away_from_rawben"]

    utility = notes.isin(UTILITY_RESET_NOTES)
    steps_matched = (
        joined["RAWBEN"].astype(float) - joined["benefit_after_steps"]
    ).abs() <= SOLVER_MATCH
    reset_off = joined["moved_miss_kind"].eq("reset_off_after_step_match")

    kinds = ("steps_stopped_short", "reset_off_after_step_match", "household_size")
    moved_miss = joined["solver_moved_input"] & ~reproduced

    at_maximum = joined["income_lowered_rawben_at_maximum"]
    matched = at_maximum & reproduced
    lowered = joined["rawearn"].where(notes.str.startswith("earn"), joined["rawunearn"])
    at_zero = matched & lowered.eq(0)
    at_limit = matched & ~at_zero
    at_limit &= joined["correctedamount"].eq(-SOLVER_STEP * SOLVER_MAX_STEPS)
    if (at_zero | at_limit).sum() != matched.sum():
        raise AssertionError(
            "an at-maximum income match ended before zero or the limit"
        )
    flagged = joined["solver_at_max"].astype(bool) & reproduced
    above = joined["AMTERR"].gt(THRESHOLD_FY2024)
    stretch = joined["flat_stretch"]
    weak = stretch.notna()
    at_cap = stretch.eq("maximum_allotment")
    rawben = joined["RAWBEN"].astype(float)
    moved = joined["solver_moved_input"]
    farther = moved & (
        (rawben - joined["rawben_recreated"].astype(float)).abs()
        > (rawben - joined["FSBEN"].astype(float)).abs()
    )
    final_change = joined["rawutil"].astype(float) - joined["UTIL"].astype(float)

    return {
        "solver_benefit_reproduces_rawben_recreated_n": len(joined),
        "household_size": {
            "n": int(household.sum()),
            "reproduced_n": int((household & reproduced).sum()),
            "away_from_rawben_keys": sorted(keys[away]),
        },
        "moved_benefit_farther_from_rawben_than_fsben_keys": sorted(keys[farther]),
        "household_size_correctedamount_zero_n": int(
            (household & joined["correctedamount"].eq(0)).sum()
        ),
        "utility_reset": {
            "n": int(utility.sum()),
            "correctedamount_differs_from_final_change_n": int(
                (utility & joined["correctedamount"].ne(final_change)).sum()
            ),
            "steps_within_3_of_rawben_n": int((utility & steps_matched).sum()),
            "reproduced_n": int((utility & reproduced).sum()),
            "reset_off_after_step_match_keys": sorted(keys[reset_off]),
        },
        "not_reproduced_solver_moved_input": {
            "n": int(moved_miss.sum()),
            **{
                f"{kind}_keys": sorted(keys[joined["moved_miss_kind"].eq(kind)])
                for kind in kinds
            },
        },
        "income_lowered_rawben_at_maximum": {
            "n": int(at_maximum.sum()),
            "reproduced_n": int(matched.sum()),
            "reproduced_above_threshold_n": int(
                (matched & joined["AMTERR"].gt(THRESHOLD_FY2024)).sum()
            ),
            "reproduced_ended_at_zero_income_n": int(at_zero.sum()),
            "reproduced_ended_at_step_limit_n": int(at_limit.sum()),
            "reproduced_at_max_flag_n": int((matched & flagged).sum()),
            "reproduced_keys": sorted(keys[matched]),
        },
        "weakly_identified": {
            "n": int(weak.sum()),
            "above_threshold_n": int((weak & above).sum()),
            "by_flat_stretch": {
                name: int(count)
                for name, count in sorted(stretch[weak].value_counts().items())
            },
            "maximum_allotment_by_correctednotes": {
                note: int(count)
                for note, count in sorted(notes[at_cap].value_counts().items())
            },
            "maximum_allotment_at_max_flag_n": int((at_cap & flagged).sum()),
            "keys": {
                name: sorted(keys[stretch.eq(name)])
                for name in sorted(set(stretch.dropna()))
            },
        },
        "reproduced_at_max_flag": {
            "n": int(flagged.sum()),
            "outside_weakly_identified_keys": sorted(keys[flagged & ~weak]),
            "by_correctednotes": {
                note: int(count)
                for note, count in sorted(notes[flagged].value_counts().items())
            },
        },
    }


def utility_reset_check(frame: pd.DataFrame, joined: pd.DataFrame) -> dict[str, Any]:
    """Re-apply the utility reset that ANALYSIS.md describes.

    The candidate pool follows reconstruct_co_fy2024.R: Colorado cases of any
    review status that pass its consistency filters (|RAWBEN - FSBEN| within $5
    of AMTERR, RENT and UTIL present, BENMAX equal to the FY2024 table value),
    grouped by calendar year. A candidate is a UTIL amount that more than five
    of them report. Each util_up (util_down) row takes the candidate above
    (below) the file's UTIL nearest the amount its steps reached, keeps that
    amount when none lies above, and gets 0 when none lies below; ties go to
    the smaller amount, as R's which.min over the sorted counts does. The
    rule the 2026-10-03 text gave instead, the candidate nearest the file's
    UTIL, is scored alongside it.
    """
    pool = frame[frame["STATE"] == COLORADO_FIPS]
    consistent = ((pool["RAWBEN"] - pool["FSBEN"]).abs() - pool["AMTERR"]).abs() <= 5
    pool = pool[consistent & pool["RENT"].notna() & pool["UTIL"].notna()]
    table = pool["FSUSIZE"].fillna(0).map(MAX_ALLOTMENT_FY2024)
    pool = pool[pool["BENMAX"].eq(table)]
    counts = pool.groupby([pool["YRMONTH"] // 100, "UTIL"]).size()
    candidates: dict[int, list[float]] = {}
    for (year, amount), n in counts.items():
        if n > UTILITY_CANDIDATE_MIN_CASES:
            candidates.setdefault(int(year), []).append(float(amount))

    rows = joined[joined["correctednotes"].isin(UTILITY_RESET_NOTES)]
    by_rule, by_file_util = [], []
    for _, row in rows.iterrows():
        pool_year = np.array(sorted(candidates.get(int(row["YRMONTH"]) // 100, [])))
        raising = row["correctednotes"] == "util_up"
        file_util = float(row["UTIL"])
        side = (
            pool_year[pool_year > file_util]
            if raising
            else pool_year[pool_year < file_util]
        )
        stepped = file_util + float(row["correctedamount"])
        if len(side) == 0:
            rule = file_rule = stepped if raising else 0.0
        else:
            rule = float(side[np.argmin(np.abs(side - stepped))])
            file_rule = float(side.min() if raising else side.max())
        final = float(row["rawutil"])
        by_rule.append(rule == final)
        by_file_util.append(file_rule == final)
    keys = list(rows["key"])
    return {
        "candidate_pool_n": len(pool),
        "candidates_by_calendar_year": {
            str(year): amounts for year, amounts in sorted(candidates.items())
        },
        "rows_n": len(rows),
        "rule_reproduces_final_amount_n": int(sum(by_rule)),
        "nearest_to_file_util_reproduces_final_amount_n": int(sum(by_file_util)),
        "nearest_to_file_util_misses_keys": sorted(
            k for k, hit in zip(keys, by_file_util) if not hit
        ),
    }


def case_findings(joined: pd.DataFrame, mask: pd.Series) -> list[dict[str, Any]]:
    rows = []
    for _, row in joined.loc[mask].sort_values("key").iterrows():
        found = findings(row)
        broad = [f for f in found if f[2] in BROAD_CODES]
        rows.append(
            {
                "key": row["key"],
                "status": int(row["STATUS"]),
                "rawben": float(row["RAWBEN"]),
                "fsben": float(row["FSBEN"]),
                "engine_on_original": float(row["engine_on_original"]),
                "amterr": float(row["AMTERR"]),
                "reproduced": bool(row["reproduced"]),
                "correctednotes": row["correctednotes"],
                "solver_moved_input": bool(row["solver_moved_input"]),
                "moved_miss_kind": row["moved_miss_kind"],
                "solver_element": int(row["solver_element"]),
                "findings": [list(f) for f in found],
                "broad_coded_findings": [list(f) for f in broad],
                "broad_coded_finding_is_computational": any(
                    is_computational(f) for f in broad
                ),
            }
        )
    return rows


def replay_partition(replay: pd.DataFrame, moved: pd.Series) -> dict[str, Any]:
    """Case counts from the replay, the solver output and a moved flag."""
    reproduced = replay["reproduced"]
    miss = ~reproduced
    trivial = (replay["rawben"] - replay["fsben"]).abs() <= REPLAY_TOLERANCE
    engine_equals_fsben = replay["engine_on_original"].eq(replay["fsben"])
    misses = replay.loc[miss]
    return {
        "n": len(replay),
        "reproduced_n": int(reproduced.sum()),
        "not_reproduced_n": int(miss.sum()),
        "solver_and_engine_agree_n": int(
            (replay["within5"] == replay["solver_within5"]).sum()
        ),
        "reproduced_solver_moved_input_n": int((reproduced & moved).sum()),
        "reproduced_without_move_n": int((reproduced & ~moved).sum()),
        "reproduced_without_move_rawben_within_5_of_fsben_n": int(
            (reproduced & ~moved & trivial).sum()
        ),
        "not_reproduced_solver_moved_input_n": int((miss & moved).sum()),
        "not_reproduced_solver_no_change_n": int(misses["solver_no_change"].sum()),
        "not_reproduced_eligible_but_unmoved_n": int(
            (miss & ~moved & ~replay["solver_no_change"]).sum()
        ),
        "not_reproduced_engine_equals_fsben_n": int((miss & engine_equals_fsben).sum()),
        "not_reproduced_unmoved_engine_equals_fsben_n": int(
            (miss & ~moved & engine_equals_fsben).sum()
        ),
        "not_reproduced_by_correctednotes": {
            note: int(count)
            for note, count in sorted(misses["correctednotes"].value_counts().items())
        },
    }


def case_level(joined: pd.DataFrame) -> dict[str, Any]:
    """Posting-invariant facts: which cases, never how many dollars."""
    miss = ~joined["reproduced"]
    broad = any_code(joined, BROAD_CODES)
    software = any_code(joined, SOFTWARE_CODES)

    broad_misses = case_findings(joined, miss & broad)
    candidates = [
        r["key"] for r in broad_misses if r["broad_coded_finding_is_computational"]
    ]
    computational_misses = [
        r["key"]
        for r in case_findings(joined, miss)
        if any(is_computational(tuple(f)) for f in r["findings"])
    ]
    computational_matches = [
        r["key"]
        for r in case_findings(joined, ~miss)
        if any(is_computational(tuple(f)) for f in r["findings"])
    ]

    software_rows = []
    for _, row in joined.loc[software].sort_values("key").iterrows():
        found = findings(row)
        software_elements = sorted({f[0] for f in found if f[2] in SOFTWARE_CODES})
        software_inputs = {SOLVER_ELEMENT_INPUTS.get(e) for e in software_elements}
        element = int(row["solver_element"])
        if not row["solver_moved_input"]:
            what_moved = "nothing"
        elif element in software_elements:
            what_moved = "software_coded_element"
        elif SOLVER_ELEMENT_INPUTS.get(element) in software_inputs:
            what_moved = "same_input_other_element"
        else:
            what_moved = "other_input"
        software_rows.append(
            {
                "key": row["key"],
                "reproduced": bool(row["reproduced"]),
                "amterr": float(row["AMTERR"]),
                "correctednotes": row["correctednotes"],
                "solver_element": element,
                "solver_input": SOLVER_ELEMENT_INPUTS.get(element),
                "software_coded_elements": software_elements,
                "solver_moved": what_moved,
                "findings": [list(f) for f in found],
            }
        )

    example = joined.loc[joined["key"] == "202312-40441"].iloc[0]
    example_codes = sorted({f[2] for f in findings(example) if f[2] is not None})
    unchanged = sorted(joined.loc[~joined["solver_moved_input"], "key"])
    snapped = joined["solver_moved_input"] & joined["correctedamount"].eq(0)
    snapped &= ~joined["correctednotes"].str.startswith("hhsize")
    return {
        "replay": replay_partition(joined, joined["solver_moved_input"]),
        "solver_outcomes": solver_outcomes(joined),
        "replay_inputs_unchanged_keys": unchanged,
        "moved_with_zero_correctedamount_keys": sorted(joined.loc[snapped, "key"]),
        "broad_coded_misses": {
            "codes": sorted(BROAD_CODES),
            "n": len(broad_misses),
            "engine_equals_fsben_n": sum(
                r["engine_on_original"] == r["fsben"] for r in broad_misses
            ),
            "solver_no_change_n": sum(
                r["correctednotes"] == "no_change" for r in broad_misses
            ),
            "computation_candidate_keys": candidates,
            "other_keys": [
                r["key"] for r in broad_misses if r["key"] not in candidates
            ],
            "cases": broad_misses,
        },
        "software_coded_replayed": {
            "codes": sorted(SOFTWARE_CODES),
            "n": len(software_rows),
            "reproduced_n": sum(r["reproduced"] for r in software_rows),
            "reproduced_by_what_moved": {
                kind: sum(
                    r["reproduced"] and r["solver_moved"] == kind for r in software_rows
                )
                for kind in (
                    "software_coded_element",
                    "same_input_other_element",
                    "other_input",
                    "nothing",
                )
            },
            "cases": software_rows,
        },
        "analysis_example_202312_40441": {
            "agency_codes": example_codes,
            "in_broad_coded_misses": bool(set(example_codes) & BROAD_CODES),
            "correctednotes": example["correctednotes"],
            "rawben": float(example["RAWBEN"]),
            "fsben": float(example["FSBEN"]),
            "engine_on_original": float(example["engine_on_original"]),
        },
        "not_reproduced_with_computational_finding_keys": computational_misses,
        "reproduced_with_computational_finding_keys": computational_matches,
        "not_reproduced_cases": case_findings(joined, miss),
    }


# --------------------------------------------------------------------------
# weighted results for one posting


def colorado_and_national(frame: pd.DataFrame) -> dict[str, Any]:
    out = {}
    for label, part in (("CO", frame[frame["STATE"] == COLORADO_FIPS]), ("US", frame)):
        errors = error_cases(part)
        total = float(errors["error_dollars"].sum())
        issuance = float((part["RAWBEN"] * part["HWGT"]).sum())
        above = errors["AMTERR"] > THRESHOLD_FY2024
        amounts = errors[[f"AMOUNT{slot}" for slot in SLOTS]].fillna(0).to_numpy()
        out[label] = {
            "cases": len(part),
            "error_cases": len(errors),
            "finding_amount_dollars": dollars(
                (amounts * errors["HWGT"].to_numpy()[:, None]).sum()
            ),
            "error_dollars": dollars(total),
            "error_dollars_above_threshold": dollars(
                errors.loc[above, "error_dollars"].sum()
            ),
            "issuance_rawben_dollars": dollars(issuance),
            "calculated_fsben_dollars": dollars((part["FSBEN"] * part["HWGT"]).sum()),
            "file_error_rate": share(total, issuance),
            "cost_share_step_dollars": dollars(COST_SHARE_STEP * issuance),
            "layer1": {
                "strict_17_19_20": class_metric(
                    errors, any_code(errors, STRICT_CODES), total
                ),
                "broad_10_17_19_20_21_22": class_metric(
                    errors, any_code(errors, BROAD_CODES), total
                ),
            },
            "axis1": {
                name: class_metric(errors, any_code(errors, codes), total)
                for name, codes in AXIS1_CLASSES.items()
            },
            "broad_code_case_counts": {
                str(c): int(any_code(errors, {c}).sum()) for c in sorted(BROAD_CODES)
            },
            "no_cause_code": class_metric(
                errors,
                errors[[f"AGENCY{slot}" for slot in SLOTS]].isna().all(axis=1),
                total,
            ),
        }
    out["CO"]["axis1_ratio_to_national"] = {
        name: round(
            out["CO"]["axis1"][name]["share"] / out["US"]["axis1"][name]["share"], 6
        )
        for name in AXIS1_CLASSES
    }
    return out


def computational_findings(frame: pd.DataFrame) -> dict[str, Any]:
    """Tally the computational findings in layer-2 pure_math and mixed cases."""
    errors = error_cases(frame[frame["STATE"] == COLORADO_FIPS])
    tally: dict[tuple[int, int | None, int | None, str], int] = {}
    cases = 0
    for _, row in errors.iterrows():
        found = findings(row)
        flags = [is_computational(f) for f in found]
        if not any(flags):
            continue
        cases += 1
        name = "pure_math" if all(flags) else "mixed"
        for finding, flag in zip(found, flags):
            if flag:
                key = (*finding, name)
                tally[key] = tally.get(key, 0) + 1
    rows = [
        {"element": e, "nature": n, "agency": a, "class": c, "findings": k}
        for (e, n, a, c), k in sorted(tally.items(), key=lambda item: str(item[0]))
    ]
    return {
        "cases": cases,
        "findings": sum(r["findings"] for r in rows),
        "by_code": rows,
    }


def reconstruction_rows() -> dict[str, int]:
    national = LAB / "fy2024_reconstruction_national.csv"
    return {
        "colorado_rows": len(pd.read_csv(RECONSTRUCTION_PATH)),
        "national_rows": len(pd.read_csv(national, usecols=["STATE"])),
    }


def phase_a_summary(frame: pd.DataFrame) -> dict[str, Any]:
    regenerated = phase_a_classification(frame)
    total = sum(v[2] for v in regenerated["classes"].values())
    return {
        name: {
            "n": values[0],
            "dollars": dollars(values[2]),
            "share": share(values[2], total),
        }
        for name, values in regenerated["classes"].items()
    }


def replay_dollars(
    joined: pd.DataFrame, colorado_errors: pd.DataFrame
) -> dict[str, Any]:
    replayed_total = float(joined["error_dollars"].sum())
    colorado_total = float(colorado_errors["error_dollars"].sum())
    rate = OFFICIAL_RATES["fy2024"]["CO"]
    broad = any_code(joined, BROAD_CODES)
    miss = ~joined["reproduced"]
    level = case_level(joined)
    candidates = set(level["broad_coded_misses"]["computation_candidate_keys"])
    is_candidate = joined["key"].isin(candidates)
    computational = joined["key"].isin(
        set(level["not_reproduced_with_computational_finding_keys"])
    )

    above_total = float(
        colorado_errors.loc[
            colorado_errors["AMTERR"] > THRESHOLD_FY2024, "error_dollars"
        ].sum()
    )
    above = joined["AMTERR"] > THRESHOLD_FY2024

    def metric(mask: pd.Series) -> dict[str, Any]:
        value = float(joined.loc[mask, "error_dollars"].sum())
        above_value = float(joined.loc[mask & above, "error_dollars"].sum())
        colorado_share = share(value, colorado_total)
        above_share = share(above_value, above_total)
        return {
            "n": int(mask.sum()),
            "dollars": dollars(value),
            "share_of_replayed": share(value, replayed_total),
            "share_of_colorado_error_dollars": colorado_share,
            "points_of_official_fy2024_rate": points(colorado_share * rate),
            "above_threshold_n": int((mask & above).sum()),
            "share_of_colorado_above_threshold_error_dollars": above_share,
            "above_threshold_points_of_official_fy2024_rate": points(
                above_share * rate
            ),
        }

    gap = (joined["engine_on_original"] - joined["RAWBEN"]).abs() * joined["HWGT"]
    return {
        "replayed": metric(pd.Series(True, index=joined.index)),
        "reproduced": metric(joined["reproduced"]),
        "not_reproduced": metric(miss),
        "broad_coded_misses": {
            **metric(miss & broad),
            "engine_gap_dollars": dollars(gap[miss & broad].sum()),
        },
        "computation_candidates": metric(is_candidate),
        "not_reproduced_with_computational_finding": metric(computational),
        "reproduced_with_computational_finding": metric(
            joined["key"].isin(set(level["reproduced_with_computational_finding_keys"]))
        ),
    }


def broad_split(joined: pd.DataFrame, colorado_errors: pd.DataFrame) -> dict[str, Any]:
    """Where the any-presence broad and software classes land in the replay."""
    rate = OFFICIAL_RATES["fy2024"]["CO"]
    lookup = joined.set_index("key")["reproduced"]
    out = {}
    for name, codes in (
        ("broad_10_17_19_20_21_22", BROAD_CODES),
        ("software_17_19", SOFTWARE_CODES),
        ("other_10_20_21_22", frozenset({10, 20, 21, 22})),
    ):
        for convention, errors in (
            ("all_errors", colorado_errors),
            (
                "above_threshold",
                colorado_errors[colorado_errors["AMTERR"] > THRESHOLD_FY2024],
            ),
        ):
            total = float(errors["error_dollars"].sum())
            in_class = any_code(errors, codes)
            replay_status = errors["key"].map(lookup)
            parts = {
                "all": in_class,
                "reproduced": in_class & replay_status.eq(True),
                "not_reproduced": in_class & replay_status.eq(False),
                "not_replayed": in_class & replay_status.isna(),
            }
            out.setdefault(name, {})[convention] = {
                part: {
                    **class_metric(errors, mask, total),
                    "points_of_official_fy2024_rate": points(
                        share(errors.loc[mask, "error_dollars"].sum(), total) * rate
                    ),
                }
                for part, mask in parts.items()
            }
    return out


def software_dollars(joined: pd.DataFrame) -> dict[str, Any]:
    software = any_code(joined, SOFTWARE_CODES)
    cases = case_level(joined)["software_coded_replayed"]["cases"]
    moved = joined["key"].map({r["key"]: r["solver_moved"] for r in cases})
    parts = [
        ("reproduced", software & joined["reproduced"]),
        ("not_reproduced", software & ~joined["reproduced"]),
    ]
    for kind in ("software_coded_element", "same_input_other_element", "other_input"):
        parts.append(
            (
                f"reproduced_solver_moved_{kind}",
                software & joined["reproduced"] & moved.eq(kind),
            )
        )
    return {
        part: {
            "n": int(mask.sum()),
            "dollars": dollars(joined.loc[mask, "error_dollars"].sum()),
        }
        for part, mask in parts
    }


def weighted_results(frame: pd.DataFrame, replay: pd.DataFrame) -> dict[str, Any]:
    joined = join_replay(replay, frame)
    colorado_errors = error_cases(frame[frame["STATE"] == COLORADO_FIPS])
    return {
        "totals": colorado_and_national(frame),
        "layer2": phase_a_summary(frame),
        "replay": replay_dollars(joined, colorado_errors),
        "class_by_replay_outcome": broad_split(joined, colorado_errors),
        "software_coded_replayed": software_dollars(joined),
    }


# --------------------------------------------------------------------------
# artifact


def posting_case_level(frame: pd.DataFrame, replay: pd.DataFrame) -> dict[str, Any]:
    """Every case-level block; build() checks it is the same under each posting."""
    joined = join_replay(replay, frame)
    return {
        **case_level(joined),
        "utility_reset_rule": utility_reset_check(frame, joined),
        "layer2_computational_findings": computational_findings(frame),
        "reconstruction": reconstruction_rows(),
    }


def build(postings: Iterable[str] = tuple(POSTINGS)) -> dict[str, Any]:
    postings = tuple(postings)
    frames = {label: load_posting(label) for label in postings}
    replay = load_replay()
    legacy = frames[LEGACY_POSTING]
    artifact: dict[str, Any] = {
        "schema": "amterr-lab-claims-audit/1",
        "inputs": {
            "committed": {
                path.relative_to(REPO).as_posix(): sha256(path)
                for path in (REPLAY_PATH, RECONSTRUCTION_PATH)
            },
            "postings": {
                label: {
                    k: v
                    for k, v in POSTINGS[label].items()
                    if k not in ("env", "default")
                }
                for label in postings
            },
            "official_rates_percent": OFFICIAL_RATES,
        },
        "conventions": {
            "error_case": "STATUS in {2,3}",
            "error_dollars": "sum(HWGT * AMTERR); the FY file pools 12 monthly samples, so the sum is annual",
            "issuance": "sum(HWGT * RAWBEN) over all records",
            "code_class": "a case counts if any of AGENCY1-AGENCY9 is in the class (classes overlap)",
            "reproduced": f"abs(engine_on_original - RAWBEN) <= {REPLAY_TOLERANCE}",
            "solver_moved_input": (
                "any replayed input ("
                + ", ".join(REPLAY_INPUTS)
                + ") differs from its file field ("
                + ", ".join(REPLAY_INPUTS.values())
                + "; missing -> 0)"
            ),
            "benefit_after_steps": (
                "the solver's benefit formula (calculate_raw_benefits, ported as "
                "solver_benefit and checked against rawben_recreated for every "
                "row) on the inputs its $3 steps reached; for util_up and "
                "util_down rows the utility amount is UTIL + correctedamount, "
                "before the reset to a commonly reported amount"
            ),
            "moved_miss_kind": (
                "for a moved input that does not reproduce: household_size; "
                f"reset_off_after_step_match (benefit_after_steps within "
                f"${SOLVER_MATCH} of RAWBEN); otherwise steps_stopped_short"
            ),
            "income_lowered_rawben_at_maximum": (
                f"correctednotes in {list(INCOME_LOWERING_NOTES)} and RAWBEN "
                "equal to the solver's maximum allotment (rawbenmax)"
            ),
            "computation_candidate": (
                "not reproduced, and a finding carrying a code in "
                f"{sorted(BROAD_CODES)} is computational under the layer-2 rule"
            ),
            "points_of_official_fy2024_rate": (
                "share of file error dollars x 9.97; an approximation, since the "
                "official rate is regression-adjusted and counts only errors above "
                f"the ${THRESHOLD_FY2024} threshold"
            ),
        },
        "regenerated_artifacts": {
            "native_decomposition": compare_to_committed(
                native_decomposition(legacy), NATIVE_PATH
            ),
            "phase_a_classification": compare_to_committed(
                phase_a_classification(legacy), PHASE_A_PATH
            ),
        },
        "case_level": posting_case_level(legacy, replay),
        "by_posting": {
            label: weighted_results(frame, replay) for label, frame in frames.items()
        },
    }
    if {"may2026", "aug2026"} <= set(postings):
        artifact["posting_diff"] = posting_diff()
        for label in postings:
            level = posting_case_level(frames[label], replay)
            if level != artifact["case_level"]:
                raise AssertionError(f"case-level results differ under {label}")
    return artifact


def render(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, indent=1, sort_keys=False) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the regenerated audit differs from claims_audit.json",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    text = render(build())
    if args.check:
        current = (
            OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        )
        if current != text:
            print(f"{OUTPUT_PATH.relative_to(REPO)} is stale", file=sys.stderr)
            return 1
        print(f"{OUTPUT_PATH.relative_to(REPO)} is current")
        return 0
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
