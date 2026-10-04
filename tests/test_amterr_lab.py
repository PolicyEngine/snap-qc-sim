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
    # 26 cases carry a computational finding: 13 reproduce, 10 do not, 3 were
    # not replayed.
    assert (
        CASES["layer2_computational_findings"]["cases"]
        - len(CASES["reproduced_with_computational_finding_keys"])
        - len(CASES["not_reproduced_with_computational_finding_keys"])
        == 3
    )

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


def test_moved_misses_partition_by_what_the_solver_did():
    outcomes = CASES["solver_outcomes"]
    moved = outcomes["not_reproduced_solver_moved_input"]
    kinds = ("steps_stopped_short", "reset_off_after_step_match", "household_size")
    lists = [set(moved[f"{kind}_keys"]) for kind in kinds]
    assert sum(len(keys) for keys in lists) == len(set().union(*lists))
    assert moved["n"] == len(set().union(*lists))
    assert moved["n"] == CASES["replay"]["not_reproduced_solver_moved_input_n"]
    rows = {row["key"]: row for row in CASES["not_reproduced_cases"]}
    for kind, keys in zip(kinds, lists):
        for key in keys:
            assert rows[key]["solver_moved_input"], key
            assert rows[key]["moved_miss_kind"] == kind, key
    unmoved = [row for row in rows.values() if not row["solver_moved_input"]]
    assert all(row["moved_miss_kind"] is None for row in unmoved)
    for key in moved["reset_off_after_step_match_keys"]:
        assert rows[key]["correctednotes"] in audit.UTILITY_RESET_NOTES
    for key in moved["household_size_keys"]:
        assert rows[key]["correctednotes"].startswith("hhsize")
    assert (
        moved["reset_off_after_step_match_keys"]
        == outcomes["utility_reset"]["reset_off_after_step_match_keys"]
    )


def test_solver_outcome_counts_are_consistent():
    outcomes = CASES["solver_outcomes"]
    assert (
        outcomes["solver_benefit_reproduces_rawben_recreated_n"]
        == (CASES["replay"]["n"])
    )
    household = outcomes["household_size"]
    assert len(household["away_from_rawben_keys"]) <= household["n"]
    assert household["reproduced_n"] <= household["n"]
    missed = {row["key"] for row in CASES["not_reproduced_cases"]}
    # A move away from RAWBEN cannot reproduce it.
    assert set(household["away_from_rawben_keys"]) <= missed

    utility = outcomes["utility_reset"]
    reset_off = utility["reset_off_after_step_match_keys"]
    assert len(reset_off) <= utility["steps_within_3_of_rawben_n"] <= utility["n"]
    assert utility["reproduced_n"] <= utility["n"]
    assert set(reset_off) <= missed

    rule = CASES["utility_reset_rule"]
    assert rule["rows_n"] == utility["n"]
    assert rule["rule_reproduces_final_amount_n"] == rule["rows_n"]
    assert rule["rows_n"] - rule[
        "nearest_to_file_util_reproduces_final_amount_n"
    ] == len(rule["nearest_to_file_util_misses_keys"])
    for amounts in rule["candidates_by_calendar_year"].values():
        assert amounts == sorted(set(amounts))

    at_maximum = outcomes["income_lowered_rawben_at_maximum"]
    matched = set(at_maximum["reproduced_keys"])
    assert len(matched) == at_maximum["reproduced_n"] <= at_maximum["n"]
    assert matched.isdisjoint(missed)
    assert matched.isdisjoint(CASES["replay_inputs_unchanged_keys"])
    assert (
        at_maximum["reproduced_ended_at_zero_income_n"]
        + at_maximum["reproduced_ended_at_step_limit_n"]
        == at_maximum["reproduced_n"]
    )
    assert at_maximum["reproduced_above_threshold_n"] <= at_maximum["reproduced_n"]
    # The solver's own at_max flag marks every one of them, and more.
    flagged = outcomes["reproduced_at_max_flag"]
    assert at_maximum["reproduced_at_max_flag_n"] == at_maximum["reproduced_n"]
    assert at_maximum["reproduced_n"] <= flagged["n"] <= CASES["replay"]["reproduced_n"]
    assert sum(flagged["by_correctednotes"].values()) == flagged["n"]

    weak = outcomes["weakly_identified"]
    by_stretch = weak["by_flat_stretch"]
    assert sum(by_stretch.values()) == weak["n"] <= CASES["replay"]["n"]
    assert weak["above_threshold_n"] <= weak["n"]
    keys = {name: set(listed) for name, listed in weak["keys"].items()}
    assert {name: len(listed) for name, listed in keys.items()} == by_stretch
    assert sum(len(listed) for listed in keys.values()) == len(
        set().union(*keys.values())
    )
    weak_keys = set().union(*keys.values())
    # Weakly identified matches are moved matches.
    assert weak_keys.isdisjoint(missed)
    assert weak_keys.isdisjoint(CASES["replay_inputs_unchanged_keys"])
    assert len(weak_keys) <= CASES["replay"]["reproduced_solver_moved_input_n"]
    # The 34 income-lowered matches at the maximum sit on the cap stretch.
    assert matched <= keys["maximum_allotment"]
    assert (
        sum(weak["maximum_allotment_by_correctednotes"].values())
        == by_stretch["maximum_allotment"]
    )
    # The solver's at_max flag overlaps only the cap stretch; the rest of it
    # is listed.
    assert (
        weak["maximum_allotment_at_max_flag_n"]
        + len(flagged["outside_weakly_identified_keys"])
        == (flagged["n"])
    )
    assert set(flagged["outside_weakly_identified_keys"]).isdisjoint(weak_keys)
    # "one household-size match and one match where nothing moved"
    replay = audit.load_replay().set_index("key")
    outside = flagged["outside_weakly_identified_keys"]
    unchanged = set(CASES["replay_inputs_unchanged_keys"])
    kinds = sorted(
        "unmoved" if key in unchanged else replay.loc[key, "correctednotes"][:6]
        for key in outside
    )
    assert kinds == ["hhsize", "unmoved"]
    # Bounded on neither side, and pushes that hold without a flat stretch.
    assert set(weak["bounded_on_neither_side_keys"]) <= weak_keys
    for key in weak["bounded_on_neither_side_keys"]:
        assert replay.loc[key, "correctednotes"] in audit.UTILITY_RESET_NOTES
    unnamed = set().union(*map(set, weak["unnamed_push_holds_keys"].values()))
    assert unnamed.isdisjoint(weak_keys) and unnamed.isdisjoint(missed)
    assert len(weak["minimum_benefit_rawben_values"]) == 1
    assert 0 < weak["shelter_cap_largest_gap_dollars"] <= audit.SHELTER_CAP_FY2024

    farther = set(outcomes["moved_benefit_farther_from_rawben_than_fsben_keys"])
    assert set(household["away_from_rawben_keys"]) <= farther <= missed
    assert outcomes["household_size_correctedamount_zero_n"] == household["n"]
    assert utility["correctedamount_differs_from_final_change_n"] <= utility["n"]


def _millions(value: float, digits: int) -> str:
    return f"${value / 1e6:.{digits}f}M"


def _percent(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f}%"


def _keys(keys: list[str]) -> str:
    """Case keys as ANALYSIS.md lists them: "a, b and c"."""
    return keys[0] if len(keys) == 1 else f"{', '.join(keys[:-1])} and {keys[-1]}"


def test_analysis_quotes_the_audit():
    """Whole sentences and table rows, so a figure cannot match elsewhere."""
    text = " ".join((LAB / "ANALYSIS.md").read_text(encoding="utf-8").split())
    may = AUDIT["by_posting"]["may2026"]
    aug = AUDIT["by_posting"]["aug2026"]
    counts = CASES["replay"]
    replay = may["replay"]
    misses = replay["broad_coded_misses"]
    outcomes = CASES["solver_outcomes"]
    moved = outcomes["not_reproduced_solver_moved_input"]
    reset_off = moved["reset_off_after_step_match_keys"]
    household = outcomes["household_size"]
    at_maximum = outcomes["income_lowered_rawben_at_maximum"]
    rule = CASES["utility_reset_rule"]
    utility = outcomes["utility_reset"]
    weak = outcomes["weakly_identified"]
    stretches = weak["by_flat_stretch"]
    at_cap = weak["maximum_allotment_by_correctednotes"]
    cap_rent = sum(v for k, v in at_cap.items() if k.startswith("rent"))
    cap_util = sum(v for k, v in at_cap.items() if k.startswith("util"))
    cap_med = sum(v for k, v in at_cap.items() if k.startswith("med"))
    cap_other = stretches["maximum_allotment"] - at_maximum["reproduced_n"]
    assert cap_rent + cap_util + cap_med == cap_other
    flagged = outcomes["reproduced_at_max_flag"]
    neither = weak["bounded_on_neither_side_keys"]
    unnamed = weak["unnamed_push_holds_keys"]
    (minimum,) = weak["minimum_benefit_rawben_values"]
    farther = outcomes["moved_benefit_farther_from_rawben_than_fsben_keys"]
    reset_away = sorted(set(farther) - set(household["away_from_rawben_keys"]))
    computational_reset_off = sorted(
        set(CASES["not_reproduced_with_computational_finding_keys"]) & set(reset_off)
    )
    broad_reset_off = [
        row["key"]
        for row in CASES["broad_coded_misses"]["cases"]
        if row["moved_miss_kind"] == "reset_off_after_step_match"
    ]
    software_reset_off = [
        row["key"]
        for row in CASES["software_coded_replayed"]["cases"]
        if not row["reproduced"] and row["key"] in reset_off
    ]
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
            f"In {moved['n']} the solver moved an input: in "
            f"{len(moved['steps_stopped_short_keys'])} its $3 steps stopped short of "
            f"RAWBEN; in {len(reset_off)} they reached within $3 of it and the utility "
            f"reset then moved the input off that match ({_keys(reset_off)}); and in "
            f"{len(moved['household_size_keys'])} the one-person household-size move "
            "missed."
        ),
        (
            f"{weak['n']} of the {counts['reproduced_solver_moved_input_n']} are "
            "weakly identified. In each, the issued benefit lies within $5 of a "
            "stretch where the solver's benefit formula is flat in the moved input: "
            "the maximum allotment, the minimum benefit, or the benefit past the "
            "shelter-deduction cap. By the solver's formula, every amount of the "
            "input on that stretch reproduces the issued benefit, so the match "
            f"bounds the input on one side at most. {len(neither)} of the "
            f"{weak['n']}, {_keys(neither)}, reproduce at every utility amount and "
            f"bound it on neither side. {weak['above_threshold_n']} of the "
            f"{weak['n']} are above the ${audit.THRESHOLD_FY2024} threshold."
        ),
        (
            f"{stretches['maximum_allotment']} are at or within $5 of the maximum "
            f"allotment, which caps the benefit. In {at_maximum['reproduced_n']} of them RAWBEN is the "
            "maximum and the solver lowered an income."
        ),
        (
            "The steps, which cannot pass RAWBEN, ran that income down to $0 in "
            f"{at_maximum['reproduced_ended_at_zero_income_n']} and to the "
            f"{audit.SOLVER_MAX_STEPS:,}-step limit in "
            f"{at_maximum['reproduced_ended_at_step_limit_n']}. "
            f"In the other {cap_other} the solver moved rent ({cap_rent}), the "
            f"utility allowance ({cap_util}) or the medical deduction ({cap_med}), "
            "and every further amount in the same direction keeps the benefit within "
            f"${audit.REPLAY_TOLERANCE} of RAWBEN."
        ),
        (
            f"{stretches['minimum_benefit']} are at the ${minimum:.0f} minimum benefit "
            "of a one- or two-person unit."
        ),
        (
            f"{stretches['shelter_cap']} are rent increases that stop within "
            f"${weak['shelter_cap_largest_gap_dollars']:.0f} of the shelter-deduction "
            "cap. Past the cap, rent no longer changes the benefit, which stays "
            f"within ${audit.REPLAY_TOLERANCE} of RAWBEN."
        ),
        (
            f"Not counted: {sum(len(v) for v in unnamed.values())} matches whose "
            "lowered input reaches no flat stretch, because the steps took it to $0 "
            f"({len(unnamed['input_already_zero'])}) or its band of matching amounts "
            f"runs down to $0 ({len(unnamed['band_reaches_zero'])})."
        ),
        (
            f"It is set for {flagged['n']} of the {counts['reproduced_n']} matches: "
            f"{weak['maximum_allotment_at_max_flag_n']} of the "
            f"{stretches['maximum_allotment']}, one household-size match and one "
            "match where nothing moved."
        ),
        (
            f"It does in {len(household['away_from_rawben_keys'])} of the "
            f"{household['n']} Colorado household-size moves, "
            f"{_keys(household['away_from_rawben_keys'])}."
        ),
        (
            "checks two parts of this account against the solver's output: its port "
            "of the solver's benefit formula reproduces all "
            f"{outcomes['solver_benefit_reproduces_rawben_recreated_n']} recreated "
            "benefits, and the reset rule above, applied to each row's stepped "
            f"amount, reproduces all {rule['rule_reproduces_final_amount_n']} final "
            "utility amounts."
        ),
        (
            "household-size moves never write it, so it is 0 in all "
            f"{outcomes['household_size_correctedamount_zero_n']}, and it is recorded "
            "before the utility reset, so it differs from the final change in all "
            f"{utility['correctedamount_differs_from_final_change_n']} utility rows "
            f"and is 0 in {len(CASES['moved_with_zero_correctedamount_keys'])} of them, "
            f"{_keys(CASES['moved_with_zero_correctedamount_keys'])}, which only the "
            "reset moved."
        ),
        (
            f"in {_keys(reset_away)} it leaves the benefit farther from RAWBEN than "
            f"FSBEN. With the {len(household['away_from_rawben_keys'])} "
            "household-size moves above, these are the only "
            f"{len(farther)} moved cases that end farther from RAWBEN than FSBEN."
        ),
        (
            f"{len(computational_reset_off)} of the "
            f"{replay['not_reproduced_with_computational_finding']['n']}, "
            f"{_keys(computational_reset_off)}, are among the {len(reset_off)} cases "
            "the utility reset moved off a match."
        ),
        (
            f"as do the {len(reset_off)} cases the utility reset moved off a match "
            "their steps had reached."
        ),
        (
            f"In {len(broad_reset_off)} of them, {_keys(broad_reset_off)}, the utility "
            "steps had reached within $3 of RAWBEN before the reset moved the input "
            "off that match."
        ),
        (
            f"In {_keys(software_reset_off)} its utility steps had reached within $3 "
            "of RAWBEN before the reset moved the input off that match."
        ),
        (
            "The 2026-10-03 text said the candidate above (or below) the file's UTIL "
            "nearest that UTIL; that rule gives the final amount in "
            f"{rule['nearest_to_file_util_reproduces_final_amount_n']} of the "
            f"{rule['rows_n']} utility rows."
        ),
        (
            "The move takes the benefit away from RAWBEN in "
            f"{len(household['away_from_rawben_keys'])} of the {household['n']} "
            "Colorado cases."
        ),
        (
            f'"In {moved["n"]} the solver moved an input and stopped short" was true '
            f"of {len(moved['steps_stopped_short_keys'])} of the {moved['n']}. In "
            f"{len(reset_off)} the steps reached within $3 of RAWBEN and the utility "
            "reset moved the input off that match; in "
            f"{len(moved['household_size_keys'])} the household-size move missed."
        ),
        (
            f"Added: {weak['n']} of the {counts['reproduced_solver_moved_input_n']} "
            f"moved matches are weakly identified, {at_maximum['reproduced_n']} of "
            "them because RAWBEN is the maximum allotment"
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


def test_retired_solver_wording_is_gone():
    """The 2026-10-03 solver wording survives only in the revision history."""
    text = " ".join((LAB / "ANALYSIS.md").read_text(encoding="utf-8").split())
    body = text.split("## Revision history")[0]
    for phrase in (
        "moved an input and stopped short",
        "every step stops",
        "value above (or below) the file's UTIL",
        "utility snap",
        "break-even",
        "ran on to zero income",
    ):
        assert phrase not in body, phrase
    assert "value above (or below) the file's UTIL" not in text


# ---------------------------------------------------------------------------
# properties of the ported solver benefit, which the weak-identification
# caveat relies on: the benefit stays between the minimum benefit and the
# maximum allotment, falls as income rises and rises with shelter costs and
# deductions, so each bound is reached on a flat stretch.


@st.composite
def solver_units(draw):
    """One unit's solver inputs; incomes and costs in whole dollars."""
    dollars = st.integers(min_value=0, max_value=6000)
    size = draw(st.integers(min_value=1, max_value=20))
    return {
        "rawearn": float(draw(dollars)),
        "rawunearn": float(draw(dollars)),
        "rawrent": float(draw(dollars)),
        "rawutil": float(draw(st.sampled_from((0, 91, 356, 560)))),
        "rawmedded": float(draw(st.integers(min_value=0, max_value=1500))),
        "rawdepded": float(draw(st.integers(min_value=0, max_value=1500))),
        "rawcsded": float(draw(st.integers(min_value=0, max_value=1500))),
        "rawstdded": float(draw(st.sampled_from((198, 208, 244, 279)))),
        "rawhomeless_ded": float(draw(st.sampled_from((0, 179)))),
        "rawbenmax": float(audit.MAX_ALLOTMENT_FY2024[size]),
        "rawminimum_ben": 23.0 if size < 3 else 0.0,
        "shelter_cap": draw(
            st.sampled_from((float(audit.SHELTER_CAP_FY2024), float("inf")))
        ),
    }


def _benefits(unit: dict, column: str, values: list[float]) -> np.ndarray:
    frame = pd.DataFrame([{**unit, column: value} for value in values])
    return audit.solver_benefit(frame).to_numpy()


def _terms(unit: dict, column: str, values: list[float]) -> pd.DataFrame:
    frame = pd.DataFrame([{**unit, column: value} for value in values])
    return audit.solver_terms(frame)


@settings(max_examples=300, deadline=None)
@given(
    solver_units(),
    st.sampled_from(("rawearn", "rawunearn")),
    st.lists(st.integers(min_value=0, max_value=9000), min_size=2, max_size=30),
)
def test_benefit_is_the_maximum_exactly_while_net_income_is_not_positive(
    unit, column, incomes
):
    """The mechanism behind the 34: net income never falls as income rises,
    and the benefit is the maximum allotment exactly when net income is zero
    or less, so the incomes that yield the maximum run from $0 up to one point."""
    values = sorted(float(v) for v in incomes)
    terms = _terms(unit, column, values)
    benefits, net = terms["benefit"].to_numpy(), terms["net"].to_numpy()
    assert np.all(np.diff(net) >= 0)
    assert np.all(np.diff(benefits) <= 0)
    assert np.all(benefits <= unit["rawbenmax"])
    assert np.all(benefits >= min(unit["rawminimum_ben"], unit["rawbenmax"]))
    assert np.array_equal(benefits == unit["rawbenmax"], net <= 0)
    at_maximum = benefits == unit["rawbenmax"]
    if at_maximum.any():
        last = np.flatnonzero(at_maximum).max()
        assert at_maximum[: last + 1].all()


@settings(max_examples=300, deadline=None)
@given(
    solver_units(),
    st.sampled_from(("rawrent", "rawutil", "rawmedded", "rawdepded", "rawcsded")),
    st.lists(st.integers(min_value=0, max_value=6000), min_size=2, max_size=30),
)
def test_benefit_rises_with_shelter_costs_and_deductions(unit, column, amounts):
    values = sorted(float(v) for v in amounts)
    benefits = _benefits(unit, column, values)
    assert np.all(np.diff(benefits) >= 0)
    assert np.all(benefits <= unit["rawbenmax"])
