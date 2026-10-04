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
import sys
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "paper/snapshot/labs/amterr"
MANUSCRIPT = ROOT / "paper/index.qmd"
RENDERED = ROOT / "app/public/paper/web/index.html"
README = ROOT / "README.md"
FACTS = ROOT / "paper/FACTS.md"
SIMULATOR = ROOT / "app/public/index.html"

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
)


def _normalize(text: str, *, is_html: bool = False) -> str:
    """Collapse whitespace and typographic apostrophes; for HTML, drop tags."""
    if is_html:
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return " ".join(text.replace("’", "'").split())


def _read(path: Path) -> str:
    return _normalize(path.read_text(encoding="utf-8"), is_html=path.suffix == ".html")


def _percent(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%"


# ---------------------------------------------------------------------------
# retired wording


@pytest.mark.parametrize("path", [MANUSCRIPT, RENDERED, README, SIMULATOR])
def test_retired_wording_is_gone(path):
    text = _read(path).lower()
    found = [phrase for phrase in RETIRED if phrase in text]
    assert not found, f"{path.relative_to(ROOT)} still carries {found}"


def test_facts_records_each_withdrawal():
    """The catalog keeps the retired wording only as a superseded record."""
    facts = _read(FACTS)
    assert "| C4 | WITHDRAWN 2026-10-03" in facts
    assert 'SUPERSEDES the revision-9 wording "explains 246/283' in facts
    assert 'SUPERSEDES "33 of 246 explained cases' in facts


# ---------------------------------------------------------------------------
# replay figures: manuscript prose against claims_audit.json and the slices


def _replay_counts() -> dict[str, int]:
    replay = AUDIT["case_level"]["replay"]
    co = AUDIT["by_posting"]["may2026"]["totals"]["CO"]
    by_posting = AUDIT["by_posting"]["may2026"]["replay"]
    layer2 = AUDIT["case_level"]["layer2_computational_findings"]["cases"]
    above = SLICES["official_above_threshold_97"]
    sub = SLICES["subthreshold_186"]
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
        "above_n": above["total"]["n"],
        "above_reproduced": above["outcomes"]["reproduced"]["n"],
        "sub_n": sub["total"]["n"],
        "sub_reproduced": sub["outcomes"]["reproduced"]["n"],
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
        f"For {c['n']} of Colorado's {c['error_cases']} error cases, a public solver",
        (
            f"reproduces the issued benefit within $5 for {above} of the "
            f"above-threshold official error cases and {sub} of the sub-threshold "
            "deviations, which is consistent with correct arithmetic on a wrong input."
        ),
        # decomposition table, layer 3
        (
            f"Not identified. {above} of above-threshold official errors and {sub} "
            f"of sub-threshold deviations ({blended} blended) reproduce the issued "
            "benefit within $5, consistent with a wrong input"
        ),
        # replay paragraph
        (
            f"Of {c['n']} deviation cases surviving the solver's consistency filters "
            f"({c['error_cases'] - c['n']} of {c['error_cases']} are excluded), "
            f"{c['reproduced']} reproduce the issued amount within the file's $5 "
            "editing tolerance, which is consistent with correct arithmetic applied "
            "to wrong facts."
        ),
        (
            f"In {c['moved']} of the {c['reproduced']} the solver moved an input; in "
            f"the other {c['unmoved']} the issued benefit was already within $5 of "
            "`FSBEN`, so nothing moved and the match restates the parity result."
        ),
        (
            f"among the {c['above_n']} above-threshold official error cases "
            f"{c['above_reproduced']} reproduce ({above}, binomial standard error"
        ),
        (
            f"among the {c['sub_n']} sub-threshold deviations {c['sub_reproduced']} "
            f"do ({sub})."
        ),
        (f"agree on the within-$5 classification for all {c['agree']} cases"),
        (
            f"in {unmoved_misses} of the {c['not_reproduced']} it moved nothing "
            f"({c['miss_no_change']} cases whose first finding names an input it "
            f"does not adjust, and {c['miss_stopped']} where it stopped before moving)"
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


def test_replay_counts_partition():
    """The identities the replay paragraph's arithmetic relies on."""
    c = _replay_counts()
    assert c["reproduced"] + c["not_reproduced"] == c["n"] == c["agree"]
    assert c["moved"] + c["unmoved"] == c["reproduced"]
    assert c["above_n"] + c["sub_n"] == c["n"]
    assert c["above_reproduced"] + c["sub_reproduced"] == c["reproduced"]
    assert c["layer2_reproduced"] + c["layer2_not_reproduced"] <= c["layer2"]
    assert c["n"] <= c["error_cases"]
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


def test_superseded_33_reconciles_with_the_16():
    """FACTS H8: 33 reproduced cases have AMTERR <= $5; 16 of them moved nothing."""
    unchanged = set(AUDIT["case_level"]["replay_inputs_unchanged_keys"])
    small = [r for r in REPLAY_ROWS if r["within5"] and r["amterr"] <= 5]
    unmoved = [r for r in small if f"{r['yrmonth']}-{r['hhldno']}" in unchanged]
    assert (len(small), len(unmoved)) == (33, 16)
    assert len(unmoved) == _replay_counts()["unmoved"]
    facts = _read(FACTS)
    assert f"{len(small)} of the 246 have AMTERR ≤ $5" in facts
    assert f"the solver moved an input in {len(small) - len(unmoved)} of them" in facts


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
        f"official FY 2024 rate {fy24:.2f}%, {margin:.2f} points below the 15% "
        f"boundary, with a ±0.9-point sampling SD; its FY 2025 rate, {fy25:.2f}%, "
        "is above the boundary"
    ) in _read(README)
    assert (
        f"official FY2024 {fy24:.2f}% ({margin:.2f}pp below the 15% boundary; the "
        f"FY2025 rate, {fy25:.2f}%, is above it, J3)"
    ) in _read(FACTS)


def test_every_margin_mention_names_fy2025():
    for path in (MANUSCRIPT, README):
        text = _read(path)
        for match in re.finditer(r"0\.03 points", text):
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
        usecols=["STATE", "FSBEN", "BENFIX"],
        low_memory=False,
    )
    co = frame[frame["STATE"] == 8]
    within = int(((co["FSBEN"] - co["BENFIX"]).abs() <= 5).sum())
    exact = int((co["FSBEN"] == co["BENFIX"]).sum())
    assert (within, len(co), exact) == (797, 856, 743)
    assert (
        f"`FSBEN` ends within $5 of `BENFIX` in {within} of {len(co)} cases"
    ) in _read(MANUSCRIPT)
    facts = _read(FACTS)
    assert (
        f"within $5 of `BENFIX` in {within} of {len(co)} cases ({exact} exactly"
        in facts
    )


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
        "above_n": above_n,
        "above_reproduced": above_reproduced,
        "sub_n": sub_n,
        "sub_reproduced": sub_reproduced,
    }


@given(replay_counts(), st.data())
def test_lock_detects_any_changed_count(counts, data):
    """Every count is load-bearing: changing one changes the required prose."""
    key = data.draw(st.sampled_from(sorted(counts)))
    changed = dict(counts, **{key: counts[key] + 1})
    assert replay_quotes(changed) != replay_quotes(counts)


@given(replay_counts())
def test_lock_is_deterministic_and_counts_render_verbatim(counts):
    quotes = replay_quotes(counts)
    assert quotes == replay_quotes(counts)
    joined = " ".join(quotes)
    for key in ("n", "reproduced", "moved", "unmoved", "above_n", "sub_n"):
        assert re.search(rf"(?<![\d.]){counts[key]}(?![\d.])", joined), key


@given(st.integers(1, 10_000), st.data())
def test_complementary_shares_sum_to_100(denominator, data):
    numerator = data.draw(st.integers(0, denominator))
    total = float(_percent(numerator, denominator)[:-1]) + float(
        _percent(denominator - numerator, denominator)[:-1]
    )
    assert abs(total - 100.0) <= 0.1 + 1e-9
