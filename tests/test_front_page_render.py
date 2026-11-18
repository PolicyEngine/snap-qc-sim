"""Render the real app.js in node (tests/render_harness.mjs) and check what a
reader sees: the answer agrees with the all-states row, the delay wording
follows the simulated delay odds, nothing renders as NaN or undefined, and
every claim that the Axiom engine reproduces a QC file says eligibility is
untested.

The default run covers states chosen to reach every branch of the answer
(tier 0 near and far from 6%, each tier, a zero-noise state, the verified
states with and without exclusions, near the delay line, and delayed with
partial and certain odds). SNAPQC_RENDER_ALL=1 renders all 53 jurisdictions,
which takes several minutes in node.
"""

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
# "reproduces", not "reproducibility" (the toolchain probe's name).
CLAIM = re.compile(r"\breproduc(?:e|es|ed|ing)\b")


@cache
def _render(width: int, analyst: bool) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    args = [node, str(HARNESS), str(PUBLIC), str(width)]
    if analyst:
        args.append("--analyst")
    if not ALL:
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
            assert "owes nothing for FY 2028 whichever year it uses" in s["points"], (
                code
            )
        else:
            assert row["bill"] == row["eShare"], code
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
        else:
            assert "crosses it less than 1% of the time" in s["points"], code
        # Near the line the "How sure" point raises the delay too.
        assert ("of such samples top 13.33%" in s["points"]) == (p >= 0.05), code


def test_lead_names_the_benefit_base() -> None:
    for code, s in _states().items():
        if not s["delay25"] and s["tier"] > 0:
            assert "in FY 2024 benefits that its QC sample represents" in s["lead"], (
                code
            )


@pytest.mark.parametrize("analyst", [False, True])
def test_every_reproduction_claim_says_eligibility_is_untested(analyst: bool) -> None:
    engine = re.compile(r"Axiom|engine|RuleSpec|encoded", re.IGNORECASE)
    checked = 0
    for code, s in _states(920 if analyst else 390, analyst).items():
        for para in s["paragraphs"]:
            if CLAIM.search(para) and engine.search(para):
                checked += 1
                assert "eligibility" in para, (code, para[:200])
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
            assert "have not yet been replayed against its QC file" in s["cta"], code
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
        else:
            assert "excluded" not in s["cta"], code
