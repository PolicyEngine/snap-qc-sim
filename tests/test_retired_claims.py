"""Locks for the October 2026 claim corrections in the working paper.

The manuscript, README, fact catalog and simulator once described FSBEN as
"the agency's own computational canon", read the error-case replay as
explaining errors "as correct arithmetic on wrong facts" with a
"computation-side upper bound", claimed technical-documentation errata no
source records, and gave Colorado's 0.03-point FY2024 margin without its
FY2025 rate. These tests tie every corrected figure to a committed artifact
(``claims_audit.json``, ``cause_shares.json``, the per-case replay rows) and
keep the retired wording out of the living files. The parity-target figures
(797 of 856) also need the FY2024 QC file and skip without it.
"""

from __future__ import annotations

import html
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "paper/snapshot/labs/amterr"
MANUSCRIPT = ROOT / "paper/index.qmd"
RENDERED = ROOT / "app/public/paper/web/index.html"
RENDERED_PDF = ROOT / "app/public/paper/web/index.pdf"
README = ROOT / "README.md"
FACTS = ROOT / "paper/FACTS.md"
SIMULATOR = ROOT / "app/public/index.html"
SIMULATOR_JS = ROOT / "app/public/app.js"

AUDIT = json.loads((LAB / "claims_audit.json").read_text(encoding="utf-8"))
SLICES = json.loads((ROOT / "analysis/cause_shares.json").read_text(encoding="utf-8"))[
    "colorado_replay_reconciliation"
]["slices"]
REPLAY_ROWS = json.loads(
    (LAB / "amterr_replay_results.json").read_text(encoding="utf-8")
)
FY2024_THRESHOLD = 56  # official error threshold, FY2024 (FACTS A6)

# Lowercased, whitespace-collapsed fragments of the retired claims.
RETIRED = (
    "agency's own",
    "government's own",
    "agency's own computational canon",
    "the agency's own canon",
    "agency's own benefit-calculation software",
    "agency's own computed outputs",
    "a closed model",
    "minimodel-canon",
    "as correct arithmetic on wrong facts",
    "explained as correct arithmetic",
    "the agency's arithmetic was correct",
    "disclosure-protection perturbation",
    "computation-side upper bound",
    "residual class is an upper bound",
    "bounded above by the replay",
    "errata in the federal technical documentation",
    "errata in the technical documentation",
    "explained cases have deviations",
    "minimodel's full-formula recomputation",
    "minimodel-recomputed",
    "fna qc minimodel",
)


def _normalize(text: str, *, is_html: bool = False, is_js: bool = False) -> str:
    """Collapse whitespace and typographic apostrophes.

    For HTML, drop tags. For JavaScript, rejoin string and template-literal
    concatenations broken across source lines, so a phrase split over two
    lines still reads as one.
    """
    if is_html:
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    if is_js:
        text = re.sub(r"[`\"']\s*\+\s*[`\"']", "", text)
    return " ".join(text.replace("’", "'").split())


def _read(path: Path) -> str:
    return _normalize(
        path.read_text(encoding="utf-8"),
        is_html=path.suffix == ".html",
        is_js=path.suffix == ".js",
    )


def _percent(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%"


# ---------------------------------------------------------------------------
# retired wording


@pytest.mark.parametrize(
    "path", [MANUSCRIPT, RENDERED, README, SIMULATOR, SIMULATOR_JS]
)
def test_retired_wording_is_gone(path):
    text = _read(path).lower()
    found = [phrase for phrase in RETIRED if phrase in text]
    assert not found, f"{path.relative_to(ROOT)} still carries {found}"


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext absent")
def test_retired_wording_is_gone_from_the_pdf():
    text = subprocess.run(
        ["pdftotext", str(RENDERED_PDF), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # pdftotext breaks hyphenated words across lines; rejoin them first.
    text = _normalize(re.sub(r"-\n", "-", text)).lower()
    found = [phrase for phrase in RETIRED if phrase in text]
    assert not found, f"index.pdf still carries {found}"


def test_js_scan_sees_phrases_split_across_concatenated_lines():
    """The retired app.js sentence was split over a template-literal join."""
    retired_js = (
        "`the allotment corrected for the reviewer's findings (BENFIX), and the "
        "Minimodel's full-formula ` +\n    `recomputation (FSBEN). |RAWBEN - "
        "BENFIX| equals`"
    )
    text = _normalize(retired_js, is_js=True).lower()
    assert "minimodel's full-formula recomputation" in text
    assert "minimodel's full-formula recomputation" in RETIRED


def test_lab_readme_quotes_the_replay_printout():
    """The lab README quotes amterr_replay.py's summary line verbatim."""
    readme = (LAB / "README.md").read_text(encoding="utf-8")
    script = (LAB / "amterr_replay.py").read_text(encoding="utf-8")
    replay = AUDIT["case_level"]["replay"]
    n, k = replay["n"], replay["reproduced_n"]
    assert 'print(f"engine(solver inputs) vs RAWBEN {tol}:' in script
    assert (
        f"`engine(solver inputs) vs RAWBEN <=$5: {k}/{n} ({100 * k / n:.1f}%)`"
        in readme
    )
    assert "engine(original)" not in readme


def test_facts_records_each_withdrawal():
    """The catalog keeps the retired wording only as a superseded record."""
    facts = _read(FACTS)
    assert "| C4 | WITHDRAWN 2026-10-03" in facts
    assert 'SUPERSEDES the revision-9 wording "explains 246/283' in facts
    assert 'SUPERSEDES "33 of 246 explained cases' in facts


# ---------------------------------------------------------------------------
# replay figures: manuscript prose against claims_audit.json and the slices


def _key(row: dict) -> str:
    return f"{row['yrmonth']}-{row['hhldno']}"


def _near_fsben_rows() -> list[dict]:
    """Replay rows whose issued benefit was within $5 of FSBEN before any step."""
    return [r for r in REPLAY_ROWS if abs(r["rawben"] - r["fsben"]) <= 5]


def _moved_near_matches() -> int:
    """Reproduced cases the solver moved although RAWBEN was already near FSBEN."""
    unchanged = set(AUDIT["case_level"]["replay_inputs_unchanged_keys"])
    return sum(
        1 for r in _near_fsben_rows() if r["within5"] and _key(r) not in unchanged
    )


def _unmoved_computational_misses() -> int:
    """Non-reproduced cases that both moved nothing and carry a computational finding."""
    cases = AUDIT["case_level"]
    unmoved = {
        c["key"] for c in cases["not_reproduced_cases"] if not c["solver_moved_input"]
    }
    return len(unmoved & set(cases["not_reproduced_with_computational_finding_keys"]))


def _replay_counts() -> dict[str, int]:
    replay = AUDIT["case_level"]["replay"]
    co = AUDIT["by_posting"]["may2026"]["totals"]["CO"]
    by_posting = AUDIT["by_posting"]["may2026"]["replay"]
    layer2 = AUDIT["case_level"]["layer2_computational_findings"]["cases"]
    above = SLICES["official_above_threshold_97"]
    sub = SLICES["subthreshold_186"]
    outcomes = AUDIT["case_level"]["solver_outcomes"]
    at_maximum = outcomes["income_lowered_rawben_at_maximum"]
    weak = outcomes["weakly_identified"]
    moved_misses = outcomes["not_reproduced_solver_moved_input"]
    return {
        "error_cases": co["error_cases"],
        "n": replay["n"],
        "reproduced": replay["reproduced_n"],
        "not_reproduced": replay["not_reproduced_n"],
        "moved": replay["reproduced_solver_moved_input_n"],
        "unmoved": replay["reproduced_without_move_n"],
        "miss_no_change": replay["not_reproduced_solver_no_change_n"],
        "miss_stopped": replay["not_reproduced_eligible_but_unmoved_n"],
        "agree": replay["solver_and_engine_agree_n"],
        "layer2": layer2,
        "layer2_reproduced": by_posting["reproduced_with_computational_finding"]["n"],
        "layer2_not_reproduced": by_posting[
            "not_reproduced_with_computational_finding"
        ]["n"],
        "miss_overlap": _unmoved_computational_misses(),
        "moved_near": _moved_near_matches(),
        "above_n": above["total"]["n"],
        "above_reproduced": above["outcomes"]["reproduced"]["n"],
        "sub_n": sub["total"]["n"],
        "sub_reproduced": sub["outcomes"]["reproduced"]["n"],
        "weak": weak["n"],
        "weak_above": weak["above_threshold_n"],
        "weak_cap": weak["by_flat_stretch"]["maximum_allotment"],
        "weak_minimum": weak["by_flat_stretch"]["minimum_benefit"],
        "weak_shelter": weak["by_flat_stretch"]["shelter_cap"],
        "weak_income": at_maximum["reproduced_n"],
        "reset_off": len(moved_misses["reset_off_after_step_match_keys"]),
        "stopped_short": len(moved_misses["steps_stopped_short_keys"]),
        "household_miss": len(moved_misses["household_size_keys"]),
        "layer2_reset_off": len(
            set(moved_misses["reset_off_after_step_match_keys"])
            & set(AUDIT["case_level"]["not_reproduced_with_computational_finding_keys"])
        ),
    }


def replay_quotes(c: dict[str, int]) -> list[str]:
    """Whole sentences the manuscript must carry, built from the counts."""
    above = _percent(c["above_reproduced"], c["above_n"])
    sub = _percent(c["sub_reproduced"], c["sub_n"])
    blended = _percent(c["reproduced"], c["n"])
    unmoved_misses = c["miss_no_change"] + c["miss_stopped"]
    not_replayed = c["layer2"] - c["layer2_reproduced"] - c["layer2_not_reproduced"]
    return [
        # abstract
        (
            f"For {c['n']} of the {c['error_cases']} Colorado cases with a recorded "
            "payment deviation, a public solver"
        ),
        (
            f"reproduces the issued benefit within $5 for {above} of the "
            f"above-threshold official error cases and {sub} of the sub-threshold "
            "deviations, which is consistent with correct arithmetic on a wrong input."
        ),
        # decomposition table, layer 3
        (
            f"Not identified. {above} of above-threshold official errors and {sub} "
            f"of sub-threshold deviations ({blended} blended) reproduce the issued "
            "benefit within $5, consistent with a wrong input; of the "
            f"{c['not_reproduced']} that do not, the solver moved nothing in "
            f"{unmoved_misses} and {c['layer2_not_reproduced']} carry a computational "
            f"finding ({c['miss_overlap']} are both)"
        ),
        # replay paragraph
        (
            f"Of {c['n']} deviation cases surviving the solver's consistency filters "
            f"({c['error_cases'] - c['n']} of {c['error_cases']} are excluded), "
            f"{c['reproduced']} reproduce the issued amount within the file's $5 "
            "editing tolerance, which is consistent with correct arithmetic applied "
            "to a wrong input."
        ),
        (
            f"In {c['moved']} of the {c['reproduced']} the solver moved an input; in "
            f"the other {c['unmoved']} it took no step, and the issued benefit was "
            "already within $5 of `FSBEN`, so the match restates the parity result."
        ),
        (
            f"In {c['moved_near']} of the {c['moved']} the issued benefit was also "
            "within $5 of `FSBEN` before the solver moved, so those matches did not "
            "need the move."
        ),
        (
            f"among the {c['above_n']} above-threshold official error cases "
            f"{c['above_reproduced']} reproduce ({above}, binomial standard error"
        ),
        (
            f"among the {c['sub_n']} sub-threshold deviations {c['sub_reproduced']} "
            f"do ({sub})."
        ),
        (
            f"In {c['weak']} of the {c['moved']} moved matches, {c['weak_above']} of "
            "them above the threshold, the issued benefit lies within $5 of a "
            "stretch where the solver's benefit formula is flat in the moved input "
            f"(the maximum allotment in {c['weak_cap']}, the minimum benefit in "
            f"{c['weak_minimum']} and rent past the shelter-deduction cap in "
            f"{c['weak_shelter']}). By that formula every amount of the input on the "
            "stretch reproduces the issued benefit, so the match bounds the input "
            f"on one side at most and is weakly identified. In {c['weak_income']} of "
            f"the {c['weak_cap']} the issued benefit is the maximum allotment and "
            "the solver lowered an income;"
        ),
        (f"agree on the within-$5 classification for all {c['agree']} cases"),
        (
            f"in {unmoved_misses} of the {c['not_reproduced']} it moved nothing "
            f"({c['miss_no_change']} cases whose first finding falls outside those "
            f"codes, and {c['miss_stopped']} where it stopped before moving)"
        ),
        (
            f"In {c['reset_off']} more, its $3 steps reached within $3 of the issued "
            "benefit before the utility reset moved the input off that match; in "
            f"{c['stopped_short']} a stop rule ended the steps short of it, and in "
            f"{c['household_miss']} the one-person household-size move missed."
        ),
        (
            f"Of the {c['layer2_not_reproduced']}, {c['layer2_reset_off']} are among "
            f"the {c['reset_off']} the utility reset moved off a match."
        ),
        (
            f"Of the {c['layer2']} cases that carry a layer-2 computational finding, "
            f"{c['layer2_reproduced']} reproduce, {c['layer2_not_reproduced']} do not "
            f"and {not_replayed} were not replayed."
        ),
    ]


def test_manuscript_quotes_the_replay_audit():
    text = _read(MANUSCRIPT)
    missing = [quote for quote in replay_quotes(_replay_counts()) if quote not in text]
    assert not missing, missing


def test_facts_quotes_the_solver_outcomes():
    """FACTS D5 and D6 carry the lab audit's solver-outcome counts."""
    facts = _read(FACTS)
    outcomes = AUDIT["case_level"]["solver_outcomes"]
    weak = outcomes["weakly_identified"]
    stretches = weak["by_flat_stretch"]
    at_maximum = outcomes["income_lowered_rawben_at_maximum"]
    at_cap = weak["maximum_allotment_by_correctednotes"]
    moved = outcomes["not_reproduced_solver_moved_input"]
    replay = AUDIT["case_level"]["replay"]
    household = outcomes["household_size"]
    flagged = outcomes["reproduced_at_max_flag"]
    rule = AUDIT["case_level"]["utility_reset_rule"]
    farther = outcomes["moved_benefit_farther_from_rawben_than_fsben_keys"]
    reset_away = sorted(set(farther) - set(household["away_from_rawben_keys"]))
    computational = AUDIT["case_level"][
        "not_reproduced_with_computational_finding_keys"
    ]
    layer2 = sorted(set(moved["reset_off_after_step_match_keys"]) & set(computational))

    def by_prefix(prefix):
        return sum(v for k, v in at_cap.items() if k.startswith(prefix))

    quotes = [
        (
            f"in {weak['n']} of the {replay['reproduced_solver_moved_input_n']} moved "
            f"matches ({weak['above_threshold_n']} above the $56 threshold)"
        ),
        (
            f"{stretches['maximum_allotment']} are at or within $5 of the maximum "
            f"allotment, {stretches['minimum_benefit']} at the "
            f"${weak['minimum_benefit_rawben_values'][0]:.0f} minimum benefit of a "
            f"one- or two-person unit, and {stretches['shelter_cap']} are rent "
            "increases that stop within "
            f"${weak['shelter_cap_largest_gap_dollars']:.0f} of the shelter-deduction "
            "cap"
        ),
        (
            f"{len(weak['bounded_on_neither_side_keys'])} of the {weak['n']} ("
            + ", ".join(weak["bounded_on_neither_side_keys"])
            + ") reproduce at every utility amount and bound it on neither side"
        ),
        (
            "Not counted: "
            f"{sum(len(v) for v in weak['unnamed_push_holds_keys'].values())} "
            "matches whose lowered input reaches no flat stretch ("
            f"{len(weak['unnamed_push_holds_keys']['input_already_zero'])} already at "
            f"$0, {len(weak['unnamed_push_holds_keys']['band_reaches_zero'])} whose "
            "band of matching amounts runs down to $0)"
        ),
        f"In {at_maximum['reproduced_n']} of the {stretches['maximum_allotment']},",
        (
            "ran that income down to $0 in "
            f"{at_maximum['reproduced_ended_at_zero_income_n']} and to the "
            f"1,000-step limit in {at_maximum['reproduced_ended_at_step_limit_n']}"
        ),
        (
            f"In the other {stretches['maximum_allotment'] - at_maximum['reproduced_n']}"
            f" the solver moved rent ({by_prefix('rent')}), the utility allowance "
            f"({by_prefix('util')}) or the medical deduction ({by_prefix('med')})"
        ),
        (
            f"marks {flagged['n']} of the {replay['reproduced_n']} matches: "
            f"{weak['maximum_allotment_at_max_flag_n']} of the "
            f"{stretches['maximum_allotment']}, one household-size match and one "
            "match with nothing moved"
        ),
        (
            f"in the {moved['n']} moved cases that do not reproduce: in "
            f"{len(moved['steps_stopped_short_keys'])} its $3 steps stopped short of "
            f"RAWBEN; in {len(moved['reset_off_after_step_match_keys'])} ("
            + ", ".join(moved["reset_off_after_step_match_keys"])
            + ")"
        ),
        (
            f"in {len(moved['household_size_keys'])} the one-person household-size "
            "move missed"
        ),
        (
            f"{len(household['away_from_rawben_keys'])} of the {household['n']} "
            "household-size moves ("
            + ", ".join(household["away_from_rawben_keys"])
            + ") take the benefit away from RAWBEN, and the reset does in "
            + ", ".join(reset_away)
            + f"; these {len(farther)} are the only moved cases"
        ),
        (
            f"{len(layer2)} of the {len(computational)} non-reproduced cases with a "
            "layer-2 computational finding (" + ", ".join(layer2) + ")"
        ),
        (
            "reproduces all "
            f"{outcomes['solver_benefit_reproduces_rawben_recreated_n']} recreated "
            "benefits, and the reset rule D4 states reproduces all "
            f"{rule['rule_reproduces_final_amount_n']} final utility amounts"
        ),
    ]
    missing = [quote for quote in quotes if quote not in facts]
    assert not missing, missing
    assert rule["rule_reproduces_final_amount_n"] == rule["rows_n"]


def test_replay_counts_partition():
    """The identities the replay paragraph's arithmetic relies on."""
    c = _replay_counts()
    assert c["reproduced"] + c["not_reproduced"] == c["n"] == c["agree"]
    assert c["moved"] + c["unmoved"] == c["reproduced"]
    assert c["above_n"] + c["sub_n"] == c["n"]
    assert c["above_reproduced"] + c["sub_reproduced"] == c["reproduced"]
    assert c["layer2_reproduced"] + c["layer2_not_reproduced"] <= c["layer2"]
    assert c["n"] <= c["error_cases"]
    # The weakly identified and reset-off cases sit inside the classes the
    # paragraph quotes them against.
    assert c["weak_above"] <= min(c["weak"], c["above_reproduced"])
    assert c["weak"] <= c["moved"]
    assert c["weak_cap"] + c["weak_minimum"] + c["weak_shelter"] == c["weak"]
    assert c["weak_income"] <= c["weak_cap"]
    # The paragraph accounts for every non-reproduced case exactly once.
    assert (
        c["miss_no_change"]
        + c["miss_stopped"]
        + c["reset_off"]
        + c["stopped_short"]
        + c["household_miss"]
        == c["not_reproduced"]
    )
    assert c["layer2_reset_off"] <= min(c["reset_off"], c["layer2_not_reproduced"])
    # "nothing moved and the match restates the parity result" needs every
    # unmoved match to sit within $5 of FSBEN already.
    replay = AUDIT["case_level"]["replay"]
    assert replay["reproduced_without_move_rawben_within_5_of_fsben_n"] == c["unmoved"]


def test_threshold_split_differential():
    """cause_shares.json's slices against the per-case replay rows."""
    above = [r for r in REPLAY_ROWS if r["amterr"] > FY2024_THRESHOLD]
    below = [r for r in REPLAY_ROWS if r["amterr"] <= FY2024_THRESHOLD]
    c = _replay_counts()
    assert (len(above), sum(r["within5"] for r in above)) == (
        c["above_n"],
        c["above_reproduced"],
    )
    assert (len(below), sum(r["within5"] for r in below)) == (
        c["sub_n"],
        c["sub_reproduced"],
    )


def test_unmoved_matches_restate_parity():
    """The 16 unmoved matches replay the file's inputs, so the engine gives FSBEN."""
    unchanged = set(AUDIT["case_level"]["replay_inputs_unchanged_keys"])
    rows = [
        r
        for r in REPLAY_ROWS
        if f"{r['yrmonth']}-{r['hhldno']}" in unchanged and r["within5"]
    ]
    assert len(rows) == _replay_counts()["unmoved"]
    for r in rows:
        assert r["engine_on_original"] == r["fsben"]
        assert abs(r["rawben"] - r["fsben"]) <= 5


def test_superseded_33_reconciles_with_the_near_fsben_matches():
    """FACTS H8: every match that started within $5 of FSBEN needed no move.

    The old "33 within comparison tolerance mechanically" counted AMTERR <= $5.
    All 33 started with RAWBEN within $5 of FSBEN, as did 2 more, and on the
    file's own inputs the engine returns FSBEN, so all 35 match without a move.
    The solver took no step in 16 and moved an input anyway in the other 19.
    """
    unchanged = set(AUDIT["case_level"]["replay_inputs_unchanged_keys"])
    small = [r for r in REPLAY_ROWS if r["within5"] and r["amterr"] <= 5]
    near = _near_fsben_rows()
    assert all(abs(r["rawben"] - r["fsben"]) <= 5 for r in small)
    assert all(r["within5"] for r in near)
    unmoved = [r for r in near if _key(r) in unchanged]
    moved = [r for r in near if _key(r) not in unchanged]
    assert (len(small), len(near), len(unmoved), len(moved)) == (33, 35, 16, 19)
    assert len(unmoved) == _replay_counts()["unmoved"]
    assert len(moved) == _replay_counts()["moved_near"]
    extra = sorted({r["amterr"] for r in near if r["amterr"] > 5})
    facts = _read(FACTS)
    assert f"{len(small)} of the 246 have AMTERR ≤ $5" in facts
    assert (
        f"in {len(near) - len(small)} more with AMTERR of ${extra[0]:.0f}" in facts
        and len(extra) == 1
    )
    assert f"none of these {len(near)} matches needed a move" in facts
    assert f"moved an input anyway in {len(moved)}" in facts


# ---------------------------------------------------------------------------
# Colorado's margin always carries the FY2025 rate


def test_colorado_margin_carries_both_years():
    rates = AUDIT["inputs"]["official_rates_percent"]
    fy24, fy25 = rates["fy2024"]["CO"], rates["fy2025"]["CO"]
    margin = round(10 - fy24, 2)
    # The sentences say "below" for FY2024 and "above" for FY2025.
    assert fy24 < 10 <= fy25
    assert (
        f"official fiscal 2024 rate sits {margin:.2f} points below the 15%-share "
        f"boundary, and its fiscal 2025 rate, {fy25:.2f}%, sits above it"
    ) in _read(MANUSCRIPT)
    assert (
        f"official FY 2024 rate {fy24:.2f}%, {margin:.2f} points below the 10% "
        "rate where the 15% cost share begins, with a ±0.9-point sampling SD; its "
        f"FY 2025 rate, {fy25:.2f}%, is above it"
    ) in _read(README)
    assert (
        f"official FY2024 {fy24:.2f}% ({margin:.2f}pp below the 10% rate where the "
        f"15% share begins; the FY2025 rate, {fy25:.2f}%, is above it, J3)"
    ) in _read(FACTS)


def test_every_margin_mention_names_fy2025():
    for path in (MANUSCRIPT, README, FACTS):
        text = _read(path)
        for match in re.finditer(r"(?<![\d.])0\.03(?!\d)[- ]?(points?|pp)", text):
            window = text[match.start() : match.start() + 200]
            assert "10.09%" in window, (path.name, window)


# ---------------------------------------------------------------------------
# the parity target: FSBEN's description and the 797-of-856 figure


def test_simulator_describes_fsben_as_mathematicas_computation():
    text = _read(SIMULATOR)
    assert (
        "Mathematica computes the QC file's formula benefit (FSBEN) for USDA from "
        "each edited case record with the benefit formula of the QC Minimodel"
    ) in text


def _load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "amterr_audit_claims_for_retired_claims", LAB / "audit_claims.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_audit_module()


def _available_postings() -> list[str]:
    out = []
    for label, spec in audit.POSTINGS.items():
        path = audit.posting_path(label)
        if path.exists() and audit.sha256(path) == spec["csv_sha256"]:
            out.append(label)
    return out


@pytest.mark.skipif(not _available_postings(), reason="FY2024 QC posting absent")
@pytest.mark.parametrize("posting", _available_postings() or ["none"])
def test_fsben_within_five_of_benfix_in_colorado(posting):
    frame = pd.read_csv(
        audit.posting_path(posting),
        usecols=["STATE", "FSBEN", "BENFIX", "ALLADJ"],
        low_memory=False,
    )
    co = frame[frame["STATE"] == 8]
    within = int(((co["FSBEN"] - co["BENFIX"]).abs() <= 5).sum())
    exact = int((co["FSBEN"] == co["BENFIX"]).sum())
    off = co[(co["FSBEN"] - co["BENFIX"]).abs() > 5]
    prorated = int((off["ALLADJ"] == 2).sum())  # ALLADJ 2 = prorated benefit
    assert (within, len(co), exact, prorated) == (797, 856, 743, 21)
    assert (
        f"`FSBEN` ends within $5 of `BENFIX` in {within} of {len(co)} cases; "
        f"{prorated} of the other {len(off)} are prorated allotments"
    ) in _read(MANUSCRIPT)
    facts = _read(FACTS)
    assert (
        f"within $5 of `BENFIX` in {within} of {len(co)} cases ({exact} exactly "
        f"equal; {prorated} of the other {len(off)} are prorated allotments"
    ) in facts


# ---------------------------------------------------------------------------
# property tests on the lock itself


@st.composite
def replay_counts(draw):
    above_n = draw(st.integers(1, 400))
    sub_n = draw(st.integers(1, 400))
    above_reproduced = draw(st.integers(0, above_n))
    sub_reproduced = draw(st.integers(0, sub_n))
    n = above_n + sub_n
    reproduced = above_reproduced + sub_reproduced
    not_reproduced = n - reproduced
    unmoved = draw(st.integers(0, reproduced))
    miss_no_change = draw(st.integers(0, not_reproduced))
    miss_stopped = draw(st.integers(0, not_reproduced - miss_no_change))
    layer2_reproduced = draw(st.integers(0, 50))
    layer2_not_reproduced = draw(st.integers(0, 50))
    layer2 = layer2_reproduced + layer2_not_reproduced + draw(st.integers(0, 20))
    miss_overlap = draw(
        st.integers(0, min(miss_no_change + miss_stopped, layer2_not_reproduced))
    )
    weak_cap = draw(st.integers(0, reproduced - unmoved))
    weak_minimum = draw(st.integers(0, reproduced - unmoved - weak_cap))
    weak_shelter = draw(st.integers(0, reproduced - unmoved - weak_cap - weak_minimum))
    weak = weak_cap + weak_minimum + weak_shelter
    misses_left = not_reproduced - miss_no_change - miss_stopped
    reset_off = draw(st.integers(0, misses_left))
    stopped_short = draw(st.integers(0, misses_left - reset_off))
    return {
        "error_cases": n + draw(st.integers(0, 100)),
        "n": n,
        "reproduced": reproduced,
        "not_reproduced": not_reproduced,
        "moved": reproduced - unmoved,
        "unmoved": unmoved,
        "miss_no_change": miss_no_change,
        "miss_stopped": miss_stopped,
        "agree": n,
        "layer2": layer2,
        "layer2_reproduced": layer2_reproduced,
        "layer2_not_reproduced": layer2_not_reproduced,
        "miss_overlap": miss_overlap,
        "moved_near": draw(st.integers(0, reproduced - unmoved)),
        "above_n": above_n,
        "above_reproduced": above_reproduced,
        "sub_n": sub_n,
        "sub_reproduced": sub_reproduced,
        "weak": weak,
        "weak_above": draw(st.integers(0, min(weak, above_reproduced))),
        "weak_cap": weak_cap,
        "weak_minimum": weak_minimum,
        "weak_shelter": weak_shelter,
        "weak_income": draw(st.integers(0, weak_cap)),
        "reset_off": reset_off,
        "stopped_short": stopped_short,
        "household_miss": misses_left - reset_off - stopped_short,
        "layer2_reset_off": draw(st.integers(0, min(reset_off, layer2_not_reproduced))),
    }


@settings(deadline=None)
@given(replay_counts(), st.data())
def test_lock_detects_any_changed_count(counts, data):
    """Every count is load-bearing: changing one changes the required prose."""
    key = data.draw(st.sampled_from(sorted(counts)))
    changed = dict(counts, **{key: counts[key] + 1})
    assert replay_quotes(changed) != replay_quotes(counts)


@settings(deadline=None)
@given(replay_counts())
def test_lock_is_deterministic_and_counts_render_verbatim(counts):
    quotes = replay_quotes(counts)
    assert quotes == replay_quotes(counts)
    joined = " ".join(quotes)
    for key in ("n", "reproduced", "moved", "unmoved", "above_n", "sub_n"):
        assert re.search(rf"(?<![\d.]){counts[key]}(?![\d.])", joined), key


@settings(deadline=None)
@given(st.integers(1, 10_000), st.data())
def test_complementary_shares_sum_to_100(denominator, data):
    numerator = data.draw(st.integers(0, denominator))
    total = float(_percent(numerator, denominator)[:-1]) + float(
        _percent(denominator - numerator, denominator)[:-1]
    )
    assert abs(total - 100.0) <= 0.1 + 1e-9
