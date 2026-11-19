"""Render the real app.js in node (tests/render_harness.mjs) and check what a
reader sees: the answer agrees with the all-states row, the delay wording
follows the simulated delay odds, nothing renders as NaN or undefined, every
claim that the Axiom engine reproduces a QC file says eligibility is
untested, analyst settings leave the answer alone, the analyst artifacts
load only when the tools open, date-dependent copy switches on its dates,
and the delay wording switches at its thresholds.

The default run covers states chosen to reach every branch of the answer
(tier 0 near and far from 6%, each tier, a zero-noise state, the verified
states with and without exclusions, near the delay line, and delayed with
partial and certain odds, and a delay chance under 0.5% that still moves
the keep-FY-2025 bill). SNAPQC_RENDER_ALL=1 renders all 53 jurisdictions,
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
BASELINE_STATES = "SD,NE,NV,LA,CO,HI,GU,MD,NY,OR,GA,AK,OK"
ANALYST_STATES = "LA,CO,NY,GA"
# Every analyst setting a shared link can carry, on states with and without
# an ungated model scenario (SD and HI are gated).
LEVERS = "?engine=1&drift=1&audits=500&smd=1"
LEVER_STATES = "LA,CO,NY,GA,SD,HI"
# Tier 15%, tier 10%, tier 0, and delayed, for the clock and odds runs.
SWITCH_STATES = "CO,LA,SD,GA"
# Each side of the 0.5% and 5% delay-wording thresholds.
SYNTHETIC_ODDS = "0.0049,0.005,0.049,0.05"
# Today, after USDA's FY 2026 deadline, after FY 2027 ends.
CLOCK = ("2026-11-18", "2027-07-15", "2027-10-02")
# The large artifacts only the analyst tools use.
ANALYST_FILES = {"interventions_data.json", "model_data.json", "model_scenarios.json"}
# "reproduces", not "reproducibility" (the toolchain probe's name).
CLAIM = re.compile(r"\breproduc(?:e|es|ed|ing)\b")
UNTESTED = re.compile(r"\beligibility (?:is )?untested\b")
# The FY 2026 status the answer gives on every date (7 U.S.C. 2025(c)(8)(C)).
FY26_STATUS = (
    "FY 2026's sample period ended September 30, 2026, and the law gives USDA until "
    "June 30, 2027 to determine FY 2026 error rates (7 U.S.C. 2025(c)(8)(C)). This page "
    "simulates that rate rather than using a published figure; once USDA publishes it, "
    "the published rate settles what these odds estimate."
)
# The answer's chance wording and the table's short form of it.
CHANCE = re.compile(r"different tier (less than 1%|more than 99%|\d+%) of the time")
SHORT = {"less than 1%": "<1%", "more than 99%": ">99%"}


@cache
def _render(
    width: int,
    analyst: bool,
    search: str | None = None,
    toggle: bool = False,
    states: str | None = None,
    today: str | None = None,
    pdelay: str | None = None,
    stall: str | None = None,
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
    if today:
        args.append(f"--today={today}")
    if pdelay:
        args.append(f"--pdelay={pdelay}")
    if stall:
        args.append(f"--stall={stall}")
    out = subprocess.run(
        args, capture_output=True, text=True, timeout=1800, check=False
    )
    if out.returncode:
        pytest.fail(f"render harness failed ({args[3:]}): {out.stderr[-3000:]}")
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
    """The rendered table cell and the answer give the same chance of a
    different tier, delayed states included, in the same rounding."""
    for code, s in _states().items():
        words = CHANCE.findall(s["points"])
        assert len(words) == 1, code
        assert s["cells"][4] == SHORT.get(words[0], words[0]), (code, s["cells"])
        assert s["cells"][4] not in ("0%", "100%"), code
        if s["tier"] > 0:
            assert f"in the {s['tier']}% cost-share tier" in s["lead"], code


def _words_value(s: str) -> tuple[float, float]:
    """A fmtWords figure as (value, rounding half-width)."""
    if s == "$0":
        return 0.0, 0.0
    if s == "under $1 million":
        return 0.25e6, 0.25e6
    m = re.fullmatch(r"\$(\d+(?:\.\d+)?) (million|billion)", s)
    assert m, s
    unit = 1e6 if m.group(2) == "million" else 1e9
    half = 0.5e6 if unit == 1e6 else 0.005e9
    return float(m.group(1)) * unit, half


def _cell_value(s: str) -> tuple[float, float]:
    """A table bill cell (fmtM) as (value, rounding half-width)."""
    m = re.fullmatch(r"\$(\d+(?:\.\d+)?)(M|B)", s)
    assert m, s
    if m.group(2) == "M":
        return float(m.group(1)) * 1e6, 0.5e6
    return float(m.group(1)) * 1e9, 0.005e9


def _agree(words: str, cell: str, value: float) -> None:
    """The answer's words and the table's cell both round the row's value."""
    for v, half in (_words_value(words), _cell_value(cell)):
        assert abs(v - value) <= half + 1e-6 * max(value, 1), (words, cell, value)


def test_answer_bill_matches_the_table_row() -> None:
    for code, s in _states().items():
        row, cells, expect = s["row"], s["cells"], s["expect"]
        if s["delay25"]:
            # Delayed states owe nothing for FY 2028; the row shows FY 2029.
            assert row["bill"] == row["bill29"] and row["eShare"] == 0, code
            assert "owes nothing for FY 2028" in s["lead"], code
            assert (
                f"expected FY 2029 bill is {expect['bill29']} a year" in s["points"]
            ), code
            assert cells[5].endswith(" FY29") and cells[6].endswith(" FY29"), code
            _agree(expect["bill29"], cells[5].removesuffix(" FY29"), row["bill"])
        elif s["tier"] == 0:
            assert row["bill"] == 0 and cells[5] == "$0M", code
            assert (
                "owes nothing for FY 2028, since it can use its FY 2025 rate"
                in s["points"]
            ), code
        else:
            assert row["bill"] == row["eShare"], code
            # The lead gives the bill the table shows, not only the tier cost.
            words = expect["elect28"]
            assert f"its expected FY 2028 bill is {words} a year" in s["lead"], code
            assert f"expected FY 2028 bill is {words} a year" in s["points"], code
            _agree(words, cells[5], row["bill"])


def test_bill_spread_is_bounded() -> None:
    """Each draw bills 0, 5, 10 or 15% of the base, so the spread is at most
    7.5% of the base, and at least that of the two tier costs either side
    of the mean (h = 5% of the base, theta the mean's fraction of a step:
    sd >= h * sqrt(theta * (1 - theta))). None when the FY 2026 delay is
    certain (every draw bills $0 for FY 2029)."""
    for code, s in _states().items():
        sd, bill, base = s["row"]["billSd"], s["row"]["bill"], s["issuance"]
        assert 0 <= sd <= 0.075 * base + 1e-6, code
        h = 0.05 * base
        theta = (bill / h) % 1
        assert sd >= h * (theta * (1 - theta)) ** 0.5 * (1 - 1e-6) - 1e-6, code
        if s["delay25"] and s["expect"]["pDelay26Raw"] == 1:
            assert sd == 0 and bill == 0, code


def test_delay_wording_follows_the_simulated_delay_odds() -> None:
    for code, s in _states().items():
        p, words = s["expect"]["pDelay26Raw"], s["expect"]["pDelay26"]
        if s["delay25"]:
            assert (
                f"A fresh FY 2026 sample reaches the delay line {words} of the time"
                in s["lead"]
            ), code
            assert "unless that rate also tops 13.33%" in s["lead"], code
            assert "points above that line" in s["points"], code
            continue
        assert "points below that line" in s["points"], code
        if p >= 0.005:
            assert (
                f"reaches it {words} of the time, which would move its first bill to FY 2030"
                in s["points"]
            ), code
            if s["tier"] > 0:
                assert (
                    f"the {words} chance that rate reaches the delay line" in s["lead"]
                ), code
        else:
            assert "reaches it less than 1% of the time" in s["points"], code
            assert "chance that rate reaches the delay line" not in s["lead"], code
        # Simulated rates are continuous: the copy names the line, not 13.33%.
        assert "tops 13.33%" not in s["points"], code
        # Near the line the "How sure" point raises the delay too.
        assert ("of such samples reach the delay line" in s["points"]) == (p >= 0.05), (
            code
        )
        # The keep-FY-2025 bill nets the delay chance; when that moves it off
        # the lead's tier cost, the point says why.
        if s["tier"] > 0:
            moved = s["expect"]["lock28"] != s["expect"]["lockTierCost"]
            labelled = (
                ", counting the same delay chance" in s["points"]
                or ", counting its small chance of a delay" in s["points"]
            )
            assert labelled == (p >= 0.005 or moved), code


def test_delay_rule_names_the_two_years_it_covers() -> None:
    for code, s in _states().items():
        assert (
            "An FY 2025 or FY 2026 rate delays the first bill if 1.5 times it reaches "
            "20% (7 U.S.C. 2013(a)(2)(B)(iii)): at the two decimals USDA publishes, any "
            "rate above 13.33%." in s["points"]
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


def test_fy2026_status_states_the_deadline() -> None:
    """The page cannot know whether USDA has published, so every answer
    gives the statutory deadline instead of a guess from the date."""
    for code, s in _states().items():
        assert FY26_STATUS in s["points"], code
        assert "not yet published" not in s["points"], code
        assert "being measured through" not in _reader_text(s), code


@pytest.mark.parametrize("today", CLOCK)
def test_date_switches_render_on_both_sides(today: str) -> None:
    """Render with the app's clock fixed on each side of October 1, 2027,
    the end of FY 2027; the FY 2026 status reads the same on every date."""
    day = datetime.date.fromisoformat(today)
    fy27_ended = day >= datetime.date(2027, 10, 1)
    for code, s in _render(390, False, states=SWITCH_STATES, today=today)[
        "states"
    ].items():
        text = _reader_text(s)
        for bad in ("NaN", "undefined", "Infinity", "[object"):
            assert bad not in text, (today, code, bad)
        assert FY26_STATUS in s["points"], (today, code)
        # Delayed states' "How sure" point never calls FY 2026 unsettled.
        assert "The FY 2026 rate is not" not in s["points"], (today, code)
        if s["delay25"]:
            assert "For FY 2026 this page simulates the rate" in s["points"], code
        assert s["fy27Heading"] == (
            "FY 2027 and the FY 2030 bill"
            if fy27_ended
            else "FY 2027, the year still open"
        ), (today, code)
        assert (
            "FY 2027's sample period ended September 30, 2027" in s["points"]
        ) == fy27_ended, (today, code)
        assert ("FY 2027, open now" in s["points"]) == (not fy27_ended), (today, code)


def test_delay_wording_switches_at_its_thresholds() -> None:
    """No jurisdiction's simulated FY 2026 delay chance falls between 0.5%
    and 5% today, so render every answer with the chance set on each side
    of both thresholds."""
    out = _render(390, False, states=SWITCH_STATES, pdelay=SYNTHETIC_ODDS)
    tiers = set()
    for key, run in out["synthetic"].items():
        p, words = float(key), run["words"]
        for code, s in run["states"].items():
            if s["delay25"]:
                continue
            tiers.add(s["tier"])
            pts, lead = s["points"], s["lead"]
            crosses = p >= 0.005
            assert (
                f"reaches it {words} of the time, which would move its first bill to FY 2030"
                in pts
            ) == crosses, (p, code)
            assert ("reaches it less than 1% of the time." in pts) == (not crosses), (
                p,
                code,
            )
            assert ("of such samples reach the delay line" in pts) == (p >= 0.05), (
                p,
                code,
            )
            if s["tier"] > 0:
                assert (
                    f"the {words} chance that rate reaches the delay line and delays "
                    "its first bill" in lead
                ) == crosses, (p, code)
                assert ("Counting that option and the chance of a delay" in pts) == (
                    crosses
                ), (p, code)
                assert (", counting the same delay chance" in pts) == crosses, (p, code)
    assert 0 in tiers and len(tiers) >= 3


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


def test_sustained_grid_prices_delayed_states_from_fy_2029() -> None:
    out = _states(920, analyst=True)
    assert any(s["delay25"] for s in out.values())
    for code, s in out.items():
        sus = s["sustained"]
        assert "Not shown for" not in sus, code
        assert "statutory share" not in sus, code
        assert "before the FY 2026 election and the delay clause" in sus, code
        if s["delay25"]:
            assert "FY 2028: $0 (delayed by statute)" in sus, code
            assert "FY 2029:" in sus and "FY 2029–30 cost" in sus, code
            assert "three-year cost" not in sus, code
            # The tile says when the first bill moves, never a bare
            # "first bill FY 2029".
            assert "first bill FY 2029" not in s["tiles"][1], code
            assert "expected FY 2029 bill" in s["tiles"][1], code
        else:
            assert "FY 2028:" in sus and "three-year cost" in sus, code


def test_adoption_note_counts_the_replayed_cases() -> None:
    data = json.loads((PUBLIC / "data.json").read_bytes())["states"]
    checked = set()
    for code, s in _states(920, analyst=True).items():
        st = data[code]
        if not st["verified"]:
            assert "has not yet been replayed" in s["adoption"], code
            continue
        checked.add(bool(st["n"] - st["verified"]))
        assert f"for all {st['verified']} replayable reviews" in s["adoption"], code
        if st["n"] > st["verified"]:
            assert (
                f"{st['verified']} of the file's {st['n']}; the other "
                f"{st['n'] - st['verified']} are SSI-CAP standardized-benefit cases"
            ) in s["adoption"], code
        else:
            assert "every case in its file" in s["adoption"], code
        assert "eligibility is untested" in s["adoption"], code
    # States with and without SSI-CAP exclusions.
    assert checked == {True, False}


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
    run = _render(920, True, LEVERS, states=LEVER_STATES)
    levered = run["states"]
    # The link's SMD setting survives the scenario load: the box comes back
    # checked and every URL the app wrote while loading keeps smd=1.
    assert run["smdRestored"]
    assert run["urlsAtLoad"] and all("smd=1" in u for u in run["urlsAtLoad"])
    # Clearing the scenario frees the cause-coded cut on the next render.
    assert run["cutFreedOnRender"]
    scenarios = json.loads((PUBLIC / "model_scenarios.json").read_bytes())["states"]
    assert set(levered) <= set(plain)
    for code, s in levered.items():
        # The FY 2027 chart labels follow the width, so fy27 is not compared.
        for key in ("lead", "points", "cta", "row", "cells"):
            assert s[key] == plain[code][key], (code, key)
        # The other levers took effect too, and drift restates the FY 2026
        # election at the published-rate baseline.
        assert "Drift on" in s["mechanism"], code
        assert "With drift, at the published-rate baseline" in s["mechanism"], code
        assert "reach the delay line" in s["mechanism"], code
        if not s["delay25"] and s["tier"] > 0:
            assert re.search(
                r"is \$[\d.]+[MB]/yr, against \$[\d.]+[MB]/yr keeping its FY 2025 rate "
                r"\(an expected saving of \$[\d.]+[MB]/yr\)",
                s["mechanism"],
            ), code
        assert s["auditsVal"] == "+500", code
        # The scenario runs wherever the state has an ungated SMD lever.
        sc = scenarios.get(code) or {}
        ungated = bool((sc.get("levers") or {}).get("smd")) and not sc.get("level_flag")
        assert s["smdOn"] == ungated, code
        # The cut and the scenario do not compose: one disables the other.
        assert s["cutDisabled"] == s["smdOn"], code
        if s["smdOn"]:
            assert "turn off the standard medical deduction scenario" in s["live"], code
            assert s["sustained"] == "", code
        else:
            assert s["live"].startswith("One measurement with the cut"), code
    assert any(s["smdOn"] for s in levered.values())
    assert not all(s["smdOn"] for s in levered.values())


@pytest.mark.parametrize("stall", ["engine_scenario_data.json", "fy2027_data.json"])
def test_answer_and_table_render_before_the_side_artifacts(stall: str) -> None:
    """Neither the adoption nor the FY 2027 artifact holds up the answer or
    the table; each panel says it is loading until its file arrives."""
    out = _render(920, True, states="CO,GA", stall=stall)
    for code, s in out["states"].items():
        assert not s["lead"].startswith("Loading"), code
        assert len(s["cells"]) == 7, code
        if stall == "engine_scenario_data.json":
            assert s["adoption"] == "Loading the adoption scenario artifact…", code
            assert out["adoptNational"] == "", code
        else:
            assert s["fy27"] == "Loading the FY 2027 projections…", code
            assert "Loading" not in s["adoption"], code


def test_a_prototype_key_in_the_link_falls_back_to_colorado() -> None:
    out = _render(390, False, "?state=constructor", states="CO,GA")
    assert out["urlsAtLoad"]
    assert all("state=CO" in u for u in out["urlsAtLoad"])
    assert not any("constructor" in u for u in out["urlsAtLoad"])


def test_analyst_artifacts_load_only_when_the_tools_open() -> None:
    baseline = _render(390, False)
    assert not ANALYST_FILES & set(baseline["fetched"])
    opened = _render(920, False, toggle=True, states="CO")
    assert not ANALYST_FILES & set(opened["fetchedBeforeToggle"])
    assert ANALYST_FILES <= set(opened["fetched"])
    assert opened["states"]["CO"]["live"].startswith("One measurement with the cut")


def test_adoption_total_renders_beside_its_caveat_not_in_the_takeaway() -> None:
    out = _render(390, False)
    assert "rules engine" not in out["takeaway"]
    assert "adopt" not in out["takeaway"]
    assert "at baseline, with no drift" in out["adoptNational"]
    assert (
        "not estimates of what adopting a rules engine would cause"
        in out["adoptNational"]
    )


def test_every_element_the_app_reads_is_in_the_page() -> None:
    """The harness makes up any element the app asks for, so a missing id
    would render here and throw in a browser; every id must exist in
    index.html or in markup app.js writes."""
    known = set(re.findall(r'\bid="([^"$]+)"', (PUBLIC / "index.html").read_text()))
    js = (PUBLIC / "app.js").read_text()
    known |= set(re.findall(r'\bid="([^"$]+)"', js))
    ids = set(_render(390, False)["ids"]) | set(_render(920, True)["ids"])
    ids |= set(_render(920, True, LEVERS, states=LEVER_STATES)["ids"])
    # Ids read only inside event handlers, which the harness never fires,
    # and ids the app selects with querySelector.
    static = set(re.findall(r'\$\("([^"]+)"\)', js))
    static |= set(re.findall(r'querySelector(?:All)?\("#([\w-]+)', js))
    assert len(static) > 30
    assert (ids | static) - known == set()
