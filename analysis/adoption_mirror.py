"""Python mirror of the browser adoption engine (app.js), bit-faithful RNG.

Shared by the contract tests and the committed national-sums builder.
The mirror reproduces app.js's mulberry32 stream exactly; summation uses
numpy, so agreement with the browser is within float-reduction noise
(tolerances live at the call sites).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

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
