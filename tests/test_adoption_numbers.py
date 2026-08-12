"""Independent Python mirror of the browser adoption engine.

Re-derives the adoption panel's headline numbers (paper FACTS M2-M3
exemplars) from the committed artifacts alone: data.json case arrays,
engine_scenario_data.json flags and shares, and a bit-faithful mirror of
app.js's mulberry32 stream. Two implementations, one classification — a
drift in either the artifacts or the engine convention trips this test.
Committed artifacts only; no source CSV required, so it runs in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "app/public/data.json").read_text())
ADOPT = json.loads((ROOT / "app/public/engine_scenario_data.json").read_text())

DRAWS = 4000
SEED = 11


def delay_met(rate: float) -> bool:
    return rate * 1.5 >= 20


def tier_of(rate: float) -> int:
    for cut, share in ((6, 0), (8, 5), (10, 10)):
        if rate < cut:
            return share
    return 15


def mulberry32_stream(seed: int, count: int) -> np.ndarray:
    """The exact rng stream app.js draws (mulberry32, uint32 arithmetic)."""
    out = np.empty(count)
    a = seed & 0xFFFFFFFF
    for i in range(count):
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((a ^ (a >> 15)) * (1 | a)) & 0xFFFFFFFF
        t = (t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) ^ t
        t &= 0xFFFFFFFF
        out[i] = (t ^ (t >> 14)) / 4294967296
    return out


def simulate(st: dict, err: np.ndarray, anchor: float, stream: np.ndarray):
    """Mirror of app.js simulate(): resample, center on the anchor."""
    w = np.asarray(st["w"])
    iss = np.asarray(st["iss"])
    n = len(err)
    we, wi = w * err, w * iss
    point = 100 * we.sum() / wi.sum()
    idx = (stream * n).astype(np.int64).reshape(DRAWS, n)
    return anchor + 100 * we[idx].sum(axis=1) / wi[idx].sum(axis=1) - point


def election(st: dict, draws: np.ndarray) -> dict:
    fy25 = st["official_fy2025"]
    lock = tier_of(fy25)
    delay25 = delay_met(fy25)
    crossed = draws * 1.5 >= 20
    zero28 = delay25 | crossed
    elected = np.array([tier_of(min(d, fy25)) for d in draws], dtype=float)
    e28 = np.where(zero28, 0.0, elected / 100 * st["issuance"]).mean()
    b29 = np.where(
        crossed, 0.0, np.array([tier_of(d) for d in draws]) / 100 * st["issuance"]
    ).mean()
    return {
        "e28": e28,
        "b29": b29,
        "pWin": float((draws < fy25).mean()),
        "pDelay26": float(crossed.mean()),
        "lock": lock,
    }


def point_rate(st: dict, err: np.ndarray) -> float:
    w = np.asarray(st["w"])
    return float(100 * (w * err).sum() / (w * np.asarray(st["iss"])).sum())


def run_state(code: str) -> dict:
    st = DATA["states"][code]
    ad = ADOPT["states"][code]
    n = len(st["err"])
    stream = mulberry32_stream(SEED, DRAWS * n)
    err0 = np.asarray(st["err"], dtype=float)
    out = {"base": election(st, simulate(st, err0, st["official_fy2025"], stream))}
    for key in ("strict", "broad"):
        flags = np.asarray(ad[f"any_{key}"], dtype=bool)
        err = np.where(flags, 0.0, err0)
        # Additive anchor: the official-minus-file offset is a fixed layer,
        # so the anchor shifts by the file-rate reduction alone (app.js
        # adoptDraws convention).
        anchor = st["official_fy2025"] - (point_rate(st, err0) - point_rate(st, err))
        out[key] = election(st, simulate(st, err, anchor, stream))
    return out


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
