"""Render the real app.js in node (tests/render_harness.mjs) and check what a
reader sees: the answer agrees with the all-states row, the delay wording
follows the simulated delay odds, nothing renders as NaN or undefined, every
claim that the Axiom engine reproduces a QC file says eligibility is
untested, analyst settings leave the answer alone, and the analyst artifacts
load only when the tools open.

The default run covers states chosen to reach every branch of the answer
(tier 0 near and far from 6%, each tier, a zero-noise state, the verified
states with and without exclusions, near the delay line, and delayed with
partial and certain odds). SNAPQC_RENDER_ALL=1 renders all 53 jurisdictions,
which takes several minutes in node.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "app" / "public"
HARNESS = ROOT / "tests" / "render_harness.mjs"
ALL = os.environ.get("SNAPQC_RENDER_ALL") == "1"
BASELINE_STATES = "SD,NE,NV,LA,CO,HI,GU,MD,NY,OR,GA,AK"
ANALYST_STATES = "LA,CO,NY,GA"
# Every analyst setting a shared link can carry.
LEVERS = "?engine=1&drift=1&audits=500&smd=1"
# The large artifacts only the analyst tools use.
ANALYST_FILES = {"interventions_data.json", "model_data.json", "model_scenarios.json"}
# "reproduces", not "reproducibility" (the toolchain probe's name).
CLAIM = re.compile(r"\breproduc(?:e|es|ed|ing)\b")
UNTESTED = re.compile(r"\beligibility (?:is )?untested\b")


@cache
def _render(
    width: int,
    analyst: bool,
    search: str | None = None,
    toggle: bool = False,
    states: str | None = None,
) -> dict:
    node = shutil.which("node")
    if not node:
        if os.environ.get("CI"):
            pytest.fail("node is required in CI")
        pytest.skip("node not available")
    args = [node, str(HARNESS), str(PUBLIC), str(width)]
    if analyst:
        args.append("--analyst")
    if toggle:
        args.append("--toggle")
    if search is not None:
        args.append(f"--search={search}")
    if states:
        args.append(f"--states={states}")
    elif not ALL:
        args.append(f"--states={ANALYST_STATES if analyst else BASELINE_STATES}")
    out = subprocess.run(args, capture_output=True, text=True, check=True, timeout=1800)
    return json.loads(out.stdout)


def _states(width: int = 390, analyst: bool = False) -> dict:
    return _render(width, analyst)["states"]


def _reader_text(s: dict) -> str:
    return " ".join([s["lead"], s["points"], s["fy27"], s["cta"], *s["paragraphs"]])


@pytest.mark.parametrize("analyst", [False, True])
def test_nothing_renders_as_nan_or_undefined(analyst: bool) -> None:
    for code, s in _states(920 if analyst else 390, analyst).items():
        text = _reader_text(s) + " " + s["strip"]
        for bad in ("NaN", "undefined", "Infinity", "[object"):
            assert bad not in text, (code, bad)


def test_answer_tier_chance_matches_the_table_row() -> None:
    for code, s in _states().items():
        if s["delay25"]:
            continue
        assert f"different tier {s['row']['pmisWords']} of the time" in s["points"], (
            code
        )


def test_answer_bill_matches_the_table_row() -> None:
    for code, s in _states().items():
        row = s["row"]
        if s["delay25"]:
            # Delayed states owe nothing for FY 2028; the row shows FY 2029.
            assert row["bill"] == row["bill29"] and row["eShare"] == 0, code
            assert "owes nothing for FY 2028" in s["lead"], code
            assert (
                f"expected FY 2029 bill is {row['billWords']} a year" in s["points"]
            ), code
        elif s["tier"] == 0:
            assert row["bill"] == 0, code
            assert (
                "owes nothing for FY 2028, since it can use its FY 2025 rate"
                in s["points"]
            ), code
        else:
            assert row["bill"] == row["eShare"], code
            # The lead gives the bill the table shows, not only the tier cost.
            assert (
                f"its expected FY 2028 bill is {row['billWords']} a year" in s["lead"]
            ), code
            assert (
                f"expected FY 2028 bill is {row['billWords']} a year" in s["points"]
            ), code


def test_bill_spread_is_bounded() -> None:
    """A bill that is 0 or a tier share (at most 15%) of the base has a
    standard deviation of at most 7.5% of the base, and none when the
    FY 2026 delay is certain (every draw bills $0 for FY 2029)."""
    for code, s in _states().items():
        sd, base = s["row"]["billSd"], s["issuance"]
        assert 0 <= sd <= 0.075 * base + 1e-6, code
        if s["delay25"] and s["expect"]["pDelay26Raw"] == 1:
            assert sd == 0 and s["row"]["bill"] == 0, code


def test_delay_wording_follows_the_simulated_delay_odds() -> None:
    for code, s in _states().items():
        p, words = s["expect"]["pDelay26Raw"], s["expect"]["pDelay26"]
        if s["delay25"]:
            assert (
                f"A fresh FY 2026 sample tops 13.33% {words} of the time" in s["lead"]
            ), code
            assert "unless that rate also tops 13.33%" in s["lead"], code
            assert "points above that line" in s["points"], code
            continue
        assert "points below that line" in s["points"], code
        if p >= 0.005:
            assert (
                f"crosses it {words} of the time, which would move its first bill to FY 2030"
                in s["points"]
            ), code
            if s["tier"] > 0:
                assert f"the {words} chance that rate tops 13.33%" in s["lead"], code
        else:
            assert "crosses it less than 1% of the time" in s["points"], code
            assert "chance that rate tops 13.33%" not in s["lead"], code
        # Near the line the "How sure" point raises the delay too.
        assert ("of such samples top 13.33%" in s["points"]) == (p >= 0.05), code


def test_delay_rule_names_the_two_years_it_covers() -> None:
    for code, s in _states().items():
        assert (
            "An FY 2025 or FY 2026 rate above 13.33% delays the first bill"
            in s["points"]
        ), code


def test_lead_names_the_benefit_base() -> None:
    for code, s in _states().items():
        if not s["delay25"] and s["tier"] > 0:
            assert "in FY 2024 benefits that its QC sample represents" in s["lead"], (
                code
            )


def test_fy2027_heading_follows_the_calendar() -> None:
    # Local time, as the app's new Date() uses.
    ended = datetime.datetime.now().astimezone().date() >= datetime.date(2027, 10, 1)
    for code, s in _states().items():
        assert s["fy27Heading"] == (
            "FY 2027 and the FY 2030 bill" if ended else "FY 2027, the year still open"
        ), code


@pytest.mark.parametrize("analyst", [False, True])
def test_every_reproduction_claim_says_eligibility_is_untested(analyst: bool) -> None:
    engine = re.compile(r"Axiom|engine|RuleSpec|encod", re.IGNORECASE)
    checked = 0
    for code, s in _states(920 if analyst else 390, analyst).items():
        for para in s["paragraphs"]:
            if CLAIM.search(para) and engine.search(para):
                checked += 1
                assert UNTESTED.search(para), (code, para[:200])
    assert checked > 0


def test_sustained_grid_is_withheld_for_delayed_states() -> None:
    for code, s in _states(920, analyst=True).items():
        if s["delay25"]:
            assert s["sustained"].startswith("Not shown for"), code
        else:
            assert "FY 2028:" in s["sustained"], code


def test_unreplayed_states_are_not_called_verified() -> None:
    for code, s in _states().items():
        if not s["row"]["verified"]:
            assert "has not yet been replayed against its QC file" in s["cta"], code
            assert "independently" not in _reader_text(s), code


def test_verified_note_counts_every_exclusion() -> None:
    data = json.loads((PUBLIC / "data.json").read_bytes())["states"]
    engine = json.loads((PUBLIC / "engine_data.json").read_bytes())["states"]
    for code, s in _states().items():
        st = data[code]
        if not st["verified"]:
            continue
        excluded = st["n"] - st["verified"]
        assert st["verified"] == engine[code]["compared"], code
        assert excluded == engine[code]["excluded"], code
        assert f"for all {st['verified']} replayable reviews" in s["cta"], code
        if excluded:
            assert (
                f"{excluded} SSI-CAP standardized-benefit cases are excluded"
                in s["cta"]
            ), code
            assert (
                "Supplemental Security Income Combined Application Project"
                in (s["cta"])
            ), code
        else:
            assert "excluded" not in s["cta"], code


def test_fy2027_repricing_is_provisional_while_its_artifact_is_projected() -> None:
    fy27 = json.loads((PUBLIC / "fy2027_data.json").read_bytes())
    projected = (
        fy27["fy2027_max_allotment_4p_48dc"]["dollars"] != 1023
        or fy27["thresholds"]["2027"]["threshold_dollars_strictly_greater_than"] != 59
    )
    checked = 0
    for code, s in _states().items():
        if code not in fy27["states"]:
            continue
        checked += 1
        shown = "provisional until it is rerun on the published values" in s["fy27"]
        assert shown == projected, code
    assert checked > 0


def test_analyst_settings_leave_the_answer_unchanged() -> None:
    """The analyst intro promises that the answer above stays as published:
    a link carrying every analyst setting renders the same answer, and the
    model scenario clears the targeted-review panels it does not compose
    with."""
    plain = _states()
    levered = _render(920, True, LEVERS)["states"]
    scenarios = json.loads((PUBLIC / "model_scenarios.json").read_bytes())["states"]
    for code, s in levered.items():
        if code in plain:
            for key in ("lead", "points", "cta"):
                assert s[key] == plain[code][key], (code, key)
        # The scenario runs wherever the state has an ungated SMD lever.
        sc = scenarios.get(code) or {}
        ungated = bool((sc.get("levers") or {}).get("smd")) and not sc.get("level_flag")
        assert s["smdOn"] == ungated, code
        if s["smdOn"]:
            assert "turn off the standard medical deduction scenario" in s["live"], code
            assert s["sustained"] == "", code
        else:
            assert s["live"].startswith("One measurement with the cut"), code
    assert any(s["smdOn"] for s in levered.values())


def test_analyst_artifacts_load_only_when_the_tools_open() -> None:
    baseline = _render(390, False)
    assert not ANALYST_FILES & set(baseline["fetched"])
    opened = _render(920, False, toggle=True, states="CO")
    assert not ANALYST_FILES & set(opened["fetchedBeforeToggle"])
    assert ANALYST_FILES <= set(opened["fetched"])
    assert opened["states"]["CO"]["live"].startswith("One measurement with the cut")


def test_every_element_the_app_reads_is_in_the_page() -> None:
    """The harness makes up any element the app asks for, so a missing id
    would render here and throw in a browser; every id must exist in
    index.html or in markup app.js writes."""
    known = set(re.findall(r'\bid="([^"$]+)"', (PUBLIC / "index.html").read_text()))
    known |= set(re.findall(r'\bid="([^"$]+)"', (PUBLIC / "app.js").read_text()))
    ids = set(_render(390, False)["ids"]) | set(_render(920, True)["ids"])
    ids |= set(_render(920, True, LEVERS)["ids"])
    assert ids - known == set()
