"""Independent Python mirror of the browser adoption engine.

Re-derives the adoption panel's headline numbers (paper FACTS M2-M3
exemplars) from the committed artifacts alone: data.json case arrays,
engine_scenario_data.json flags and shares, and a bit-faithful mirror of
app.js's mulberry32 stream (analysis/adoption_mirror.py, shared with the
committed national-sums builder). Two implementations, one
classification — a drift in either the artifacts or the engine
convention trips this test. Committed artifacts only, so it runs in CI.
"""

from __future__ import annotations

import numpy as np
import pytest

from analysis.adoption_mirror import ADOPT, DATA, point_rate, run_state


def test_wedge_disclosure_stats_match_the_app_and_paper() -> None:
    """The official-minus-file wedge quoted in the app and FACTS row O.

    The wedge (federal re-review integration plus ineligible-case error the
    file never records) is what anchoring carries as a fixed layer; these
    stats lock the disclosed numbers to the committed arrays.
    """
    shares = {}
    for code, st in DATA["states"].items():
        point = point_rate(st, np.asarray(st["err"], dtype=float))
        shares[code] = (st["official"] - point) / st["official"]
    assert float(np.median(list(shares.values()))) == pytest.approx(0.31, abs=0.005)
    assert min(shares.values()) == pytest.approx(-0.034, abs=0.005)
    assert max(shares.values()) == pytest.approx(0.81, abs=0.005)
    assert shares["CO"] == pytest.approx(0.256, abs=0.005)
    assert shares["NY"] == pytest.approx(0.444, abs=0.005)
    negative = sorted(code for code, s in shares.items() if s < 0)
    assert negative == ["MN", "NV"]


def test_strict_flags_are_a_subset_of_broad_everywhere() -> None:
    """{17,19,20} ⊂ {10,17,19,20,21,22} must survive into every state's flags."""
    for code, ad in ADOPT["states"].items():
        s = np.asarray(ad["any_strict"], dtype=bool)
        b = np.asarray(ad["any_broad"], dtype=bool)
        assert not (s & ~b).any(), code
        assert ad["shares"]["any_strict"] <= ad["shares"]["any_broad"] + 1e-15, code


def test_colorado_exemplar_matches_facts_m3() -> None:
    """CO: the saving case — centers cross the 10% boundary."""
    r = run_state("CO")
    assert r["base"]["e28"] == pytest.approx(158.9e6, abs=0.05e6)
    assert r["strict"]["e28"] == pytest.approx(142.6e6, abs=0.05e6)
    assert r["broad"]["e28"] == pytest.approx(135.6e6, abs=0.05e6)
    assert r["base"]["pWin"] == pytest.approx(0.525, abs=0.002)
    assert r["strict"]["pWin"] == pytest.approx(0.743, abs=0.002)
    assert r["broad"]["pWin"] == pytest.approx(0.820, abs=0.002)


def test_new_york_nonmonotonicity_matches_facts_m3() -> None:
    """NY: zero strict share; broad RAISES the near-term bill via the delay clause."""
    ad = ADOPT["states"]["NY"]
    assert ad["shares"]["any_strict"] == 0.0
    r = run_state("NY")
    assert r["base"]["e28"] == pytest.approx(629.9e6, abs=0.1e6)
    assert r["strict"]["e28"] == pytest.approx(r["base"]["e28"], rel=1e-12)
    assert r["broad"]["e28"] == pytest.approx(1020.8e6, abs=0.1e6)
    assert r["broad"]["e28"] > r["base"]["e28"]
    assert r["base"]["pDelay26"] == pytest.approx(0.417, abs=0.002)
    assert r["broad"]["pDelay26"] == pytest.approx(0.051, abs=0.002)


def test_georgia_deferral_mechanics_match_facts_m3() -> None:
    """GA: delay25 met — FY2028 is $0 under every engine; FY2029 prices deferral."""
    r = run_state("GA")
    for k in ("base", "strict", "broad"):
        assert r[k]["e28"] == 0.0, k
    assert r["base"]["b29"] == pytest.approx(8.7e6, abs=0.1e6)
    assert r["strict"]["b29"] == pytest.approx(63.1e6, abs=0.1e6)
    assert r["broad"]["b29"] == pytest.approx(396.3e6, abs=0.1e6)
    assert r["base"]["pDelay26"] == pytest.approx(0.981, abs=0.002)
