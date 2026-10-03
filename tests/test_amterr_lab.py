"""Guards for the amterr lab's claims audit (paper/snapshot/labs/amterr).

The committed ``claims_audit.json`` recomputes every figure in the lab's
ANALYSIS.md. Most tests here need only committed files. The regeneration test
also needs both FY2024 QC postings and skips without them.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

LAB = Path(__file__).parents[1] / "paper/snapshot/labs/amterr"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "amterr_audit_claims", LAB / "audit_claims.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()
AUDIT = json.loads((LAB / "claims_audit.json").read_text(encoding="utf-8"))
POSTINGS = tuple(AUDIT["by_posting"])
CASES = AUDIT["case_level"]


# ---------------------------------------------------------------------------
# committed-file checks (no QC data needed)


def test_replay_partition_recomputes_from_committed_replay():
    replay = audit.load_replay()
    moved = audit.moved_from_keys(replay, CASES["replay_inputs_unchanged_keys"])
    assert audit.replay_partition(replay, moved) == CASES["replay"]


def test_unchanged_inputs_cover_every_no_change_row():
    replay = audit.load_replay()
    no_change = set(replay.loc[replay["solver_no_change"], "key"])
    unchanged = set(CASES["replay_inputs_unchanged_keys"])
    assert no_change <= unchanged
    assert unchanged.isdisjoint(CASES["moved_with_zero_correctedamount_keys"])


def test_replay_partition_is_exhaustive():
    replay = CASES["replay"]
    assert replay["reproduced_n"] + replay["not_reproduced_n"] == replay["n"]
    assert (
        replay["reproduced_solver_moved_input_n"] + replay["reproduced_without_move_n"]
        == replay["reproduced_n"]
    )
    unmoved = (
        replay["not_reproduced_solver_no_change_n"]
        + replay["not_reproduced_eligible_but_unmoved_n"]
    )
    assert (
        replay["not_reproduced_solver_moved_input_n"] + unmoved
        == (replay["not_reproduced_n"])
    )
    # An unmoved row replays the file's own inputs, so the engine returns FSBEN.
    assert replay["not_reproduced_unmoved_engine_equals_fsben_n"] == unmoved
    assert (
        sum(replay["not_reproduced_by_correctednotes"].values())
        == (replay["not_reproduced_n"])
    )


def test_case_lists_nest():
    missed = {row["key"] for row in CASES["not_reproduced_cases"]}
    broad = CASES["broad_coded_misses"]
    broad_keys = {row["key"] for row in broad["cases"]}
    candidates = set(broad["computation_candidate_keys"])
    assert candidates <= broad_keys <= missed
    assert candidates.isdisjoint(broad["other_keys"])
    assert candidates | set(broad["other_keys"]) == broad_keys
    assert len(missed) == CASES["replay"]["not_reproduced_n"]
    for row in broad["cases"]:
        assert row["broad_coded_findings"], row["key"]
        assert all(f[2] in audit.BROAD_CODES for f in row["broad_coded_findings"])


def test_audit_case_rows_agree_with_committed_replay():
    replay = audit.load_replay().set_index("key")
    for row in CASES["not_reproduced_cases"]:
        source = replay.loc[row["key"]]
        assert not source["reproduced"]
        assert row["rawben"] == source["rawben"]
        assert row["fsben"] == source["fsben"]
        assert row["engine_on_original"] == source["engine_on_original"]
        assert row["correctednotes"] == source["correctednotes"]


def test_analysis_example_is_outside_the_broad_class():
    example = CASES["analysis_example_202312_40441"]
    assert example["agency_codes"] == [15]
    assert not example["in_broad_coded_misses"]
    assert example["engine_on_original"] == example["fsben"]


def test_regenerated_layer_one_and_two_artifacts_match_committed_copies():
    for name, record in AUDIT["regenerated_artifacts"].items():
        assert record["matches_committed"], name
        # The audit compared against this exact file; an edit to it must fail.
        assert record["sha256"] == audit.sha256(audit.REPO / record["path"]), name


def test_audit_was_built_from_the_committed_replay_and_solver_output():
    for path, digest in AUDIT["inputs"]["committed"].items():
        assert audit.sha256(audit.REPO / path) == digest, path


def test_postings_differ_only_in_weight_columns():
    assert set(AUDIT["posting_diff"]["changed_columns"]) <= audit.WEIGHT_COLUMNS
    assert AUDIT["posting_diff"]["rows_in_same_order"]


@pytest.mark.parametrize("posting", POSTINGS)
def test_weighted_partitions_conserve_dollars(posting):
    result = AUDIT["by_posting"][posting]
    replay = result["replay"]
    assert replay["reproduced"]["n"] + replay["not_reproduced"]["n"] == 283
    assert replay["reproduced"]["dollars"] + replay["not_reproduced"]["dollars"] == (
        pytest.approx(replay["replayed"]["dollars"], abs=0.02)
    )
    assert (
        replay["computation_candidates"]["dollars"]
        <= replay["broad_coded_misses"]["dollars"]
        <= replay["not_reproduced"]["dollars"]
    )
    rate = audit.OFFICIAL_RATES["fy2024"]["CO"]
    for metric in replay.values():
        assert 0 <= metric["share_of_colorado_error_dollars"] <= 1
        assert metric["points_of_official_fy2024_rate"] == pytest.approx(
            metric["share_of_colorado_error_dollars"] * rate, abs=1e-6
        )
        assert metric["above_threshold_n"] <= metric["n"]
    candidates = set(CASES["broad_coded_misses"]["computation_candidate_keys"])
    assert candidates <= set(CASES["not_reproduced_with_computational_finding_keys"])

    for classes in result["class_by_replay_outcome"].values():
        for parts in classes.values():
            pieces = ("reproduced", "not_reproduced", "not_replayed")
            assert sum(parts[p]["n"] for p in pieces) == parts["all"]["n"]
            assert sum(parts[p]["dollars"] for p in pieces) == pytest.approx(
                parts["all"]["dollars"], abs=0.03
            )

    software = result["software_coded_replayed"]
    kinds = ("software_coded_element", "same_input_other_element", "other_input")
    parts = [software[f"reproduced_solver_moved_{kind}"] for kind in kinds]
    assert sum(p["n"] for p in parts) == software["reproduced"]["n"]
    assert sum(p["dollars"] for p in parts) == pytest.approx(
        software["reproduced"]["dollars"], abs=0.02
    )

    colorado = result["totals"]["CO"]
    layer2 = result["layer2"]
    assert sum(v["n"] for v in layer2.values()) == colorado["error_cases"]
    assert sum(v["dollars"] for v in layer2.values()) == pytest.approx(
        colorado["error_dollars"], abs=0.05
    )


def test_case_counts_do_not_depend_on_posting():
    first, *rest = (AUDIT["by_posting"][p] for p in POSTINGS)
    for other in rest:
        for state in ("CO", "US"):
            for block in ("layer1", "axis1"):
                for name, metric in first["totals"][state][block].items():
                    assert other["totals"][state][block][name]["n"] == metric["n"]
        for name, metric in first["layer2"].items():
            assert other["layer2"][name]["n"] == metric["n"]


def _millions(value: float, digits: int) -> str:
    return f"${value / 1e6:.{digits}f}M"


def _percent(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f}%"


def test_analysis_quotes_the_audit():
    """Whole sentences and table rows, so a figure cannot match elsewhere."""
    text = " ".join((LAB / "ANALYSIS.md").read_text(encoding="utf-8").split())
    may = AUDIT["by_posting"]["may2026"]
    aug = AUDIT["by_posting"]["aug2026"]
    counts = CASES["replay"]
    replay = may["replay"]
    misses = replay["broad_coded_misses"]
    quoted = [
        (
            f"{counts['reproduced_n']} of {counts['n']} "
            f"({_percent(counts['reproduced_n'] / counts['n'])} of cases, "
            f"{_percent(replay['reproduced']['share_of_replayed'])} of the "
            f"{_millions(replay['replayed']['dollars'], 1)} replayed error dollars)"
        ),
        (
            f"In {counts['reproduced_solver_moved_input_n']} the solver moved an input; "
            f"in {counts['reproduced_without_move_n']} nothing moved"
        ),
        (
            f"In {counts['not_reproduced_solver_moved_input_n']} the solver moved an "
            "input and stopped short"
        ),
        (
            f"They carry {_millions(misses['dollars'], 2)}/yr: "
            f"{_percent(misses['share_of_replayed'])} of replayed error dollars and "
            f"{_percent(misses['share_of_colorado_error_dollars'])} of Colorado"
        ),
        f"gives {_millions(misses['engine_gap_dollars'], 2)}.",
        (
            f"{replay['reproduced_with_computational_finding']['n']} reproduce "
            f"({_millions(replay['reproduced_with_computational_finding']['dollars'], 1)}"
            f"/yr, "
            f"{_percent(replay['reproduced_with_computational_finding']['share_of_colorado_error_dollars'])}"
            " of Colorado error dollars), "
            f"{replay['not_reproduced_with_computational_finding']['n']} do not "
            f"({_millions(replay['not_reproduced_with_computational_finding']['dollars'], 1)}"
            f", "
            f"{_percent(replay['not_reproduced_with_computational_finding']['share_of_colorado_error_dollars'])})"
        ),
        (
            f"The {CASES['layer2_computational_findings']['cases']} pure_math and mixed "
            f"cases carry {CASES['layer2_computational_findings']['findings']} "
            "computational findings"
        ),
        f"on ${may['totals']['US']['issuance_rawben_dollars'] / 1e9:.1f}B of issuance",
        f"{CASES['reconstruction']['national_rows']:,} national error rows",
    ]

    # Software-cause table rows (Colorado and national).
    labels = {
        "software_17_19": "Software (17, 19)",
        "worker_computation_20_21": "Worker computation (20, 21)",
        "data_entry_18": "Data entry (18)",
        "policy_or_budgeted_10_22": "Policy misapplied or budgeted wrong (10, 22)",
    }
    for name, label in labels.items():
        colorado = may["totals"]["CO"]["axis1"][name]
        national = may["totals"]["US"]["axis1"][name]
        national_dollars = national["dollars"] / 1e6
        shown = (
            f"${national_dollars:,.0f}M"
            if national_dollars >= 1000
            else f"${national_dollars:.1f}M"
        )
        quoted.append(
            f"| {label} | {_millions(colorado['dollars'], 1)}/yr "
            f"({colorado['n']} cases) | {_percent(colorado['share'])} | "
            f"{shown}/yr | {_percent(national['share'])} |"
        )

    # Cost-share table rows: all error dollars, then above the $56 threshold.
    split = may["class_by_replay_outcome"]["broad_10_17_19_20_21_22"]
    rows = {
        "All": "all",
        "Replay reproduces the issued benefit": "reproduced",
        "Replay does not reproduce": "not_reproduced",
        "Not replayed (solver filters)": "not_replayed",
    }
    for label, part in rows.items():
        every, above = split["all_errors"][part], split["above_threshold"][part]
        quoted.append(
            f"| {label} | {every['n']} ({above['n']}) | {_percent(every['share'])} | "
            f"{every['points_of_official_fy2024_rate']:.2f} | "
            f"{_percent(above['share'])} | "
            f"{above['points_of_official_fy2024_rate']:.2f} |"
        )
    candidates = replay["computation_candidates"]
    quoted.append(
        f"| The 7 computation candidates | {candidates['n']} "
        f"({candidates['above_threshold_n']}) | "
        f"{_percent(candidates['share_of_colorado_error_dollars'])} | "
        f"{candidates['points_of_official_fy2024_rate']:.2f} | "
        f"{_percent(candidates['share_of_colorado_above_threshold_error_dollars'])} | "
        f"{candidates['above_threshold_points_of_official_fy2024_rate']:.2f} |"
    )

    # August-weights table rows that carry both postings.
    def both(label, path, digits=2):
        left, right = may, aug
        for key in path:
            left, right = left[key], right[key]
        return (
            f"| {label} | {_millions(left['dollars'], digits)} "
            f"({_percent(left['share'])}) | {_millions(right['dollars'], digits)} "
            f"({_percent(right['share'])}) |"
        )

    quoted += [
        both("Layer 1 strict, Colorado", ("totals", "CO", "layer1", "strict_17_19_20")),
        both(
            "Layer 1 broad, Colorado",
            ("totals", "CO", "layer1", "broad_10_17_19_20_21_22"),
        ),
        both("Data entry (18), Colorado", ("totals", "CO", "axis1", "data_entry_18")),
        both(
            "Software (17, 19), Colorado", ("totals", "CO", "axis1", "software_17_19")
        ),
        (
            f"| One cost-share tier (5% of issuance) | "
            f"{_millions(may['totals']['CO']['cost_share_step_dollars'], 1)} | "
            f"{_millions(aug['totals']['CO']['cost_share_step_dollars'], 1)} |"
        ),
    ]
    missing = [q for q in quoted if q not in text]
    assert not missing, missing


# ---------------------------------------------------------------------------
# regeneration from the raw postings (skips without the data)


def _postings_available() -> bool:
    for label, spec in audit.POSTINGS.items():
        path = audit.posting_path(label)
        if not path.exists() or audit.sha256(path) != spec["csv_sha256"]:
            return False
    return True


@pytest.mark.skipif(not _postings_available(), reason="FY2024 QC postings absent")
def test_audit_regenerates_from_postings(assert_artifact_values_match):
    assert_artifact_values_match(json.loads(audit.render(audit.build())), AUDIT)


# ---------------------------------------------------------------------------
# property tests on the classification and partition logic

ELEMENTS = (150, 311, 331, 350, 362, 364, 366, 520)
NATURES = (6, 37, 38, 44, 52, 53, 54, 56, 57, 75, 80, 97, 98, 123)
AGENCIES = (1, 2, 10, 12, 15, 17, 18, 19, 20, 21, 22, 26)


@st.composite
def colorado_errors(draw):
    n = draw(st.integers(min_value=1, max_value=25))
    rows = []
    for index in range(n):
        row = {
            "STATE": 8,
            "YRMONTH": 202310 + index // 10,
            "HHLDNO": 40000 + index,
            "STATUS": draw(st.sampled_from((2, 3))),
            "AMTERR": float(draw(st.integers(min_value=1, max_value=900))),
            "HWGT": draw(st.floats(min_value=1.0, max_value=6000.0)),
        }
        populated = draw(st.integers(min_value=0, max_value=4))
        for slot in audit.SLOTS:
            if slot <= populated:
                row[f"ELEMENT{slot}"] = float(draw(st.sampled_from(ELEMENTS)))
                row[f"NATURE{slot}"] = float(draw(st.sampled_from(NATURES)))
                agency = draw(st.one_of(st.none(), st.sampled_from(AGENCIES)))
                row[f"AGENCY{slot}"] = np.nan if agency is None else float(agency)
            else:
                row[f"ELEMENT{slot}"] = np.nan
                row[f"NATURE{slot}"] = np.nan
                row[f"AGENCY{slot}"] = np.nan
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame["key"] = [audit.case_key(y, h) for y, h in zip(frame.YRMONTH, frame.HHLDNO)]
    return frame


@given(
    st.sampled_from(ELEMENTS),
    st.sampled_from(NATURES),
    st.one_of(st.none(), st.sampled_from(AGENCIES)),
)
def test_is_computational_rule(element, nature, agency):
    result = audit.is_computational((element, nature, agency))
    if (
        element == audit.ARITHMETIC_ELEMENT
        or nature in audit.INHERENT_COMPUTATION_NATURES
    ):
        assert result
    elif nature in audit.DEDUCTION_NATURES:
        assert result == (agency in audit.BROAD_CODES)
    else:
        assert not result


@settings(max_examples=150, deadline=None)
@given(colorado_errors())
def test_layer2_classes_partition_cases_and_dollars(frame):
    result = audit.phase_a_classification(frame)
    totals = result["classes"]
    assert sum(v[0] for v in totals.values()) == len(frame)
    dollars = float((frame.HWGT * frame.AMTERR).sum())
    assert sum(v[2] for v in totals.values()) == pytest.approx(dollars, rel=1e-12)
    assert len(result["pure_math"]) == totals["pure_math"][0]
    assert len(result["input_system_caused"]) == totals["input_system_caused"][0]
    for case in result["pure_math"]:
        assert case["findings"]
        assert all(audit.is_computational(tuple(f)) for f in case["findings"])
    for case in result["input_system_caused"]:
        assert not any(audit.is_computational(tuple(f)) for f in case["findings"])
        assert any(f[2] in audit.BROAD_CODES for f in case["findings"])


@settings(max_examples=150, deadline=None)
@given(colorado_errors(), st.data())
def test_replay_split_partitions_each_class(frame, data):
    errors = audit.error_cases(frame)
    replayed = data.draw(
        st.lists(st.booleans(), min_size=len(frame), max_size=len(frame))
    )
    reproduced = data.draw(
        st.lists(st.booleans(), min_size=len(frame), max_size=len(frame))
    )
    joined = pd.DataFrame(
        {
            "key": frame.key[np.array(replayed)],
            "reproduced": np.array(reproduced)[np.array(replayed)],
        }
    )
    split = audit.broad_split(joined, errors)
    for classes in split.values():
        for parts in classes.values():
            pieces = ("reproduced", "not_reproduced", "not_replayed")
            assert sum(parts[p]["n"] for p in pieces) == parts["all"]["n"]
            assert sum(parts[p]["share"] for p in pieces) == pytest.approx(
                parts["all"]["share"], abs=1e-9
            )


@settings(max_examples=100, deadline=None)
@given(colorado_errors(), st.floats(min_value=0.01, max_value=100.0))
def test_shares_are_invariant_to_rescaling_weights(frame, factor):
    scaled = frame.assign(HWGT=frame.HWGT * factor)
    for codes in (audit.STRICT_CODES, audit.BROAD_CODES, audit.SOFTWARE_CODES):
        base, other = audit.error_cases(frame), audit.error_cases(scaled)
        total, total_scaled = base.error_dollars.sum(), other.error_dollars.sum()
        left = audit.class_metric(base, audit.any_code(base, codes), total)
        right = audit.class_metric(other, audit.any_code(other, codes), total_scaled)
        assert left["n"] == right["n"]
        assert left["share"] == pytest.approx(right["share"], abs=1e-9)


@settings(max_examples=100, deadline=None)
@given(colorado_errors())
def test_any_presence_is_monotone_in_the_code_set(frame):
    errors = audit.error_cases(frame)
    total = errors.error_dollars.sum()
    strict = audit.class_metric(
        errors, audit.any_code(errors, audit.STRICT_CODES), total
    )
    broad = audit.class_metric(errors, audit.any_code(errors, audit.BROAD_CODES), total)
    assert strict["n"] <= broad["n"]
    assert strict["dollars"] <= broad["dollars"] + 0.01
