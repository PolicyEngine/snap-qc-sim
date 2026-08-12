"""Generate committed null predictions for the OBBBA boundary design.

This module is a deterministic, NumPy-only mirror of the browser's observed-
resample and election engines.  It commits FY2026 no-response predictions,
analysis windows, prospective test machinery, and simulation-based power
before the FY2026 outcomes are published.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = REPO_ROOT / "app" / "public" / "data.json"
MOVEMENT_JSON = REPO_ROOT / "analysis" / "fy2025_movement.json"
OUT_JSON = REPO_ROOT / "analysis" / "preregistration_obbba_boundary.json"

SCHEMA = "snap_qc_sim.preregistration_obbba_boundary.v1"
REGISTERED_DATE = "2026-08-12"
DRAWS = 4_000
SIMULATION_SEED = 11
DRIFT_SEED_BASE = 1_107
PRIMARY_NULL_SEED = 20_260_930
DELAY_NULL_SEED = 20_260_931
NULL_REPLICATIONS = 20_000
PRIMARY_POWER_SEED = 20_270_601
DELAY_POWER_SEED = 20_270_602
POWER_REPLICATIONS = 2_000
ALPHA = 0.05
POWER_DELTAS = (0.0, 0.25, 0.5, 1.0)
QUANTILE_LEVELS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.10,
    0.25,
    0.50,
    0.75,
    0.90,
    0.95,
    0.975,
    0.99,
    0.995,
    0.999,
)
TIER_CUTS = (6.0, 8.0, 10.0)
DELAY_THRESHOLD = 20.0 / 1.5
ALL_BOUNDARIES = (*TIER_CUTS, DELAY_THRESHOLD)
FIXED_WIDTHS = (0.75, 1.25)
EXTRA_SAMPLES = {
    "baseline": 0,
    "extra_sample_300": 300,
    "extra_sample_500": 500,
}

UINT32_MASK = 0xFFFFFFFF
MULBERRY_WEYL = 0x6D2B79F5
UINT32_DENOMINATOR = 4_294_967_296.0

PIT_DEFINITION = (
    "PIT: u_s = (#{null draws < r26} + 0.5 * #{null draws == r26}) / "
    "4000, against regenerated full-precision baseline draws."
)
PRIMARY_TEST_DEFINITION = (
    "PRIMARY: T = mean(u_s | above) - mean(u_s | below), pooled across the "
    "three tier windows (assigned partition). H1 one-sided: T < 0. alpha = "
    "0.05. Null: 20,000 MC replications, seed 20260930 — independently per "
    "window state draw u ~ discrete uniform {(k+0.5)/4000 : k=0..3999}; "
    "p = fraction of null T <= realized T."
)
DELAY_TEST_DEFINITION = (
    "DELAY SECONDARY: U = mean(u_s) over the delay window; H1 one-sided: "
    "U > 1/2; alpha 0.05; same MC machinery, same seed stream discipline "
    "(separate seed 20260931)."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _round4(value: float) -> float:
    """Round a rate, percentage-point quantity, or probability to four places."""
    return round(float(value), 4)


def _whole_dollars(value: float) -> int:
    """Round dollar expectations to whole dollars using Python's ties-to-even."""
    return round(float(value))


def _number_key(value: float) -> str:
    return f"{value:g}"


def _delta_key(value: float) -> str:
    return str(float(value))


def mulberry32_stream_loop(seed: int, count: int) -> np.ndarray:
    """Return the browser's Mulberry32 stream using a scalar reference loop."""
    if count < 0:
        raise ValueError("count must be nonnegative")
    out = np.empty(count, dtype=np.float64)
    a = seed & UINT32_MASK
    for i in range(count):
        a = (a + MULBERRY_WEYL) & UINT32_MASK
        t = ((a ^ (a >> 15)) * (1 | a)) & UINT32_MASK
        mix = ((t ^ (t >> 7)) * (61 | t)) & UINT32_MASK
        t = ((t + mix) ^ t) & UINT32_MASK
        out[i] = (t ^ (t >> 14)) / UINT32_DENOMINATOR
    return out


def mulberry32_stream(seed: int, count: int) -> np.ndarray:
    """Return a vectorized, bit-faithful Mulberry32 stream.

    Mulberry32's state is a Weyl sequence, so all states can be formed at once:
    ``a_k = seed + k * 0x6D2B79F5 (mod 2**32)`` for ``k=1..count``.
    Every integer operation below is performed in uint64 and masked to the low
    32 bits at the same boundaries as the scalar/browser implementation.
    """
    if count < 0:
        raise ValueError("count must be nonnegative")
    if count == 0:
        return np.empty(0, dtype=np.float64)

    mask = np.uint64(UINT32_MASK)
    a = np.arange(1, count + 1, dtype=np.uint64)
    a *= np.uint64(MULBERRY_WEYL)
    a += np.uint64(seed & UINT32_MASK)
    a &= mask

    t = (a ^ (a >> np.uint64(15))) * (np.uint64(1) | a)
    t &= mask
    mix = (t ^ (t >> np.uint64(7))) * (np.uint64(61) | t)
    mix &= mask
    t = (t + mix) ^ t
    t &= mask
    t ^= t >> np.uint64(14)
    return t.astype(np.float64) / UINT32_DENOMINATOR


def simulate(
    state_data: Mapping[str, Any],
    *,
    extra: int = 0,
    seed: int = SIMULATION_SEED,
    anchor: float | None = None,
) -> np.ndarray:
    """Vectorized mirror of ``app.js simulate()`` for one state."""
    w = np.asarray(state_data["w"], dtype=np.float64)
    err = np.asarray(state_data["err"], dtype=np.float64)
    iss = np.asarray(state_data["iss"], dtype=np.float64)
    n = len(err)
    if len(w) != n or len(iss) != n:
        raise ValueError("w, err, and iss arrays must have equal lengths")
    if extra < 0:
        raise ValueError("extra must be nonnegative")

    we = w * err
    wi = w * iss
    point = 100.0 * np.sum(we) / np.sum(wi)
    center = float(state_data["official_fy2025"] if anchor is None else anchor)
    m = n + extra

    stream = mulberry32_stream(seed, DRAWS * m)
    indices = np.floor(stream * n).astype(np.int64).reshape(DRAWS, m)
    del stream
    sampled_we = np.sum(we[indices], axis=1, dtype=np.float64)
    sampled_wi = np.sum(wi[indices], axis=1, dtype=np.float64)
    return center + 100.0 * sampled_we / sampled_wi - point


def drift_draws(tau: float, seed: int = DRIFT_SEED_BASE) -> np.ndarray:
    """Mirror ``app.js driftDraws()`` with its two-uniform cosine transform."""
    uniforms = mulberry32_stream(seed, 2 * DRAWS).reshape(DRAWS, 2)
    u1 = np.maximum(uniforms[:, 0], 1e-12)
    u2 = uniforms[:, 1]
    return (
        float(tau)
        * np.sqrt(-2.0 * np.log(u1))
        * np.cos(2.0 * np.pi * u2)
    )


def tier_of(rate: float) -> int:
    """Return the statutory 0/5/10/15 cost-share tier for a scalar rate."""
    if rate < 6.0:
        return 0
    if rate < 8.0:
        return 5
    if rate < 10.0:
        return 10
    return 15


def _tier_shares(rates: np.ndarray) -> np.ndarray:
    return np.select(
        (rates < 6.0, rates < 8.0, rates < 10.0),
        (0, 5, 10),
        default=15,
    )


def delay_met(rate: float) -> bool:
    return bool(rate * 1.5 >= 20.0)


def election_stats(state_data: Mapping[str, Any], draws: np.ndarray) -> dict[str, Any]:
    """Full vectorized mirror of ``app.js electionStats()``."""
    fy25 = float(state_data["official_fy2025"])
    issuance = float(state_data["issuance"])
    lock_share = tier_of(fy25)
    delay25 = delay_met(fy25)
    crossed = draws * 1.5 >= 20.0
    zero28 = delay25 | crossed

    lock_tier_cost = lock_share / 100.0 * issuance
    lock28_values = np.where(zero28, 0.0, lock_tier_cost)
    elected_shares = _tier_shares(np.minimum(draws, fy25))
    elect28_values = np.where(zero28, 0.0, elected_shares / 100.0 * issuance)
    bill29_values = np.where(
        crossed,
        0.0,
        _tier_shares(draws) / 100.0 * issuance,
    )
    elect28 = float(np.mean(elect28_values))
    elect28_sq = float(np.mean(np.square(elect28_values)))

    return {
        "fy25": fy25,
        "lockShare": lock_share,
        "delay25": delay25,
        "lockTierCost": lock_tier_cost,
        "lock28": float(np.mean(lock28_values)),
        "elect28": elect28,
        "sd28": math.sqrt(max(0.0, elect28_sq - elect28 * elect28)),
        "bill29": float(np.mean(bill29_values)),
        "pWin": float(np.mean(draws < fy25)),
        "pDelay26": float(np.mean(crossed)),
    }


def _serialize_election(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fy25": _round4(raw["fy25"]),
        "lockShare": int(raw["lockShare"]),
        "delay25": bool(raw["delay25"]),
        "lockTierCost": _whole_dollars(raw["lockTierCost"]),
        "lock28": _whole_dollars(raw["lock28"]),
        "elect28": _whole_dollars(raw["elect28"]),
        "sd28": _whole_dollars(raw["sd28"]),
        "bill29": _whole_dollars(raw["bill29"]),
        "pWin": _round4(raw["pWin"]),
        "pDelay26": _round4(raw["pDelay26"]),
    }


def _variant_prediction(
    state_data: Mapping[str, Any], draws: np.ndarray
) -> tuple[dict[str, Any], dict[str, Any]]:
    shares = _tier_shares(draws)
    quantiles = np.quantile(draws, QUANTILE_LEVELS, method="linear")
    raw_election = election_stats(state_data, draws)
    fy25 = float(state_data["official_fy2025"])
    prediction = {
        "mean": _round4(np.mean(draws)),
        "sd": _round4(np.std(draws)),
        "counts_of_4000": {
            "win": int(np.sum(draws < fy25)),
            "delay26": int(np.sum(draws * 1.5 >= 20.0)),
            "below_6": int(np.sum(draws < 6.0)),
            "below_8": int(np.sum(draws < 8.0)),
            "below_10": int(np.sum(draws < 10.0)),
            "tier_0": int(np.sum(shares == 0)),
            "tier_5": int(np.sum(shares == 5)),
            "tier_10": int(np.sum(shares == 10)),
            "tier_15": int(np.sum(shares == 15)),
        },
        "quantiles": {
            _number_key(level): _round4(value)
            for level, value in zip(QUANTILE_LEVELS, quantiles, strict=True)
        },
        "p_below_6": _round4(np.mean(draws < 6.0)),
        "p_below_8": _round4(np.mean(draws < 8.0)),
        "p_below_10": _round4(np.mean(draws < 10.0)),
        "p_delay26": _round4(np.mean(draws * 1.5 >= 20.0)),
        "tier_probabilities": {
            "p0": _round4(np.mean(shares == 0)),
            "p5": _round4(np.mean(shares == 5)),
            "p10": _round4(np.mean(shares == 10)),
            "p15": _round4(np.mean(shares == 15)),
        },
        "p_win": _round4(np.mean(draws < state_data["official_fy2025"])),
        "election": _serialize_election(raw_election),
    }
    return prediction, raw_election


def _load_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    movement = json.loads(MOVEMENT_JSON.read_text(encoding="utf-8"))
    return data, movement


def _generate_baseline_draws(
    data: Mapping[str, Any], state_codes: list[str] | None = None
) -> dict[str, np.ndarray]:
    codes = sorted(data["states"]) if state_codes is None else sorted(state_codes)
    return {code: simulate(data["states"][code]) for code in codes}


def _build_rosters(
    data: Mapping[str, Any], baseline_draws: Mapping[str, np.ndarray]
) -> dict[str, Any]:
    codes = sorted(baseline_draws)
    raw: dict[str, Any] = {}
    qualifying_cuts: dict[str, list[float]] = {code: [] for code in codes}

    for cut in TIER_CUTS:
        key = _number_key(cut)
        qualifiers = [
            code
            for code in codes
            if 0.10 <= float(np.mean(baseline_draws[code] < cut)) <= 0.90
        ]
        for code in qualifiers:
            qualifying_cuts[code].append(cut)
        raw[key] = {
            "qualifiers": qualifiers,
            "above": [
                code
                for code in qualifiers
                if data["states"][code]["official_fy2025"] >= cut
            ],
            "below": [
                code
                for code in qualifiers
                if data["states"][code]["official_fy2025"] < cut
            ],
        }

    assigned_codes: dict[float, list[str]] = {cut: [] for cut in TIER_CUTS}
    multi_window_reassignments = []
    for code in codes:
        cuts = qualifying_cuts[code]
        if not cuts:
            continue
        fy25 = float(data["states"][code]["official_fy2025"])
        assigned_cut = min(cuts, key=lambda cut: (abs(fy25 - cut), cut))
        assigned_codes[assigned_cut].append(code)
        if len(cuts) > 1:
            multi_window_reassignments.append(
                {
                    "state": code,
                    "raw_qualifying_cuts_pp": [_round4(cut) for cut in cuts],
                    "assigned_cut_pp": _round4(assigned_cut),
                    "reassigned_from_cuts_pp": [
                        _round4(cut) for cut in cuts if cut != assigned_cut
                    ],
                    "distances_pp": {
                        _number_key(cut): _round4(abs(fy25 - cut)) for cut in cuts
                    },
                }
            )

    assigned: dict[str, Any] = {}
    for cut in TIER_CUTS:
        key = _number_key(cut)
        qualifiers = assigned_codes[cut]
        assigned[key] = {
            "qualifiers": qualifiers,
            "above": [
                code
                for code in qualifiers
                if data["states"][code]["official_fy2025"] >= cut
            ],
            "below": [
                code
                for code in qualifiers
                if data["states"][code]["official_fy2025"] < cut
            ],
        }

    delay_qualifiers = [
        code
        for code in codes
        if 0.10 <= float(np.mean(baseline_draws[code] * 1.5 >= 20.0)) <= 0.90
    ]
    delay_window = {
        "qualifiers": delay_qualifiers,
        "above": [
            code
            for code in delay_qualifiers
            if delay_met(data["states"][code]["official_fy2025"])
        ],
        "below": [
            code
            for code in delay_qualifiers
            if not delay_met(data["states"][code]["official_fy2025"])
        ],
    }

    fixed: dict[str, Any] = {}
    for width in FIXED_WIDTHS:
        fixed[_number_key(width)] = {
            _number_key(boundary): [
                code
                for code in codes
                if abs(data["states"][code]["official_fy2025"] - boundary)
                <= width
            ]
            for boundary in ALL_BOUNDARIES
        }

    return {
        "tier_probability_windows": {
            "raw": raw,
            "assigned": assigned,
            "multi_window_reassignments": multi_window_reassignments,
        },
        "delay_probability_window": delay_window,
        "fixed_width_windows": fixed,
    }


def _assigned_groups(rosters: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    assigned = rosters["tier_probability_windows"]["assigned"]
    above = sorted(
        code for cut in map(_number_key, TIER_CUTS) for code in assigned[cut]["above"]
    )
    below = sorted(
        code for cut in map(_number_key, TIER_CUTS) for code in assigned[cut]["below"]
    )
    return above, below


def _pit_from_draws(realized_rate: float, null_draws: np.ndarray) -> float:
    ordered = np.sort(null_draws)
    left = int(np.searchsorted(ordered, realized_rate, side="left"))
    right = int(np.searchsorted(ordered, realized_rate, side="right"))
    return (left + right) / (2.0 * DRAWS)


def _validate_realized_rates(
    realized_rates: Mapping[str, float], required_states: list[str]
) -> None:
    missing = sorted(set(required_states) - set(realized_rates))
    if missing:
        raise ValueError(f"realized-rate mapping is missing states: {missing}")
    invalid = [
        code
        for code in required_states
        if not math.isfinite(float(realized_rates[code]))
    ]
    if invalid:
        raise ValueError(f"realized rates must be finite: {invalid}")


def pit_values(realized_rates: Mapping[str, float]) -> dict[str, float]:
    """Compute preregistered empirical midrank PITs for the supplied states."""
    data, _ = _load_inputs()
    codes = sorted(realized_rates)
    unknown = sorted(set(codes) - set(data["states"]))
    if unknown:
        raise ValueError(f"unknown states: {unknown}")
    _validate_realized_rates(realized_rates, codes)
    draws = _generate_baseline_draws(data, codes)
    return {
        code: _pit_from_draws(float(realized_rates[code]), draws[code])
        for code in codes
    }


def _primary_null_statistics(above: list[str], below: list[str]) -> np.ndarray:
    codes = sorted(above + below)
    above_set = set(above)
    above_mask = np.array([code in above_set for code in codes], dtype=bool)
    rng = np.random.Generator(np.random.PCG64(PRIMARY_NULL_SEED))
    ranks = rng.integers(
        0,
        DRAWS,
        size=(NULL_REPLICATIONS, len(codes)),
        dtype=np.int64,
    )
    uniforms = (ranks + 0.5) / DRAWS
    return np.mean(uniforms[:, above_mask], axis=1) - np.mean(
        uniforms[:, ~above_mask], axis=1
    )


def _delay_null_statistics(state_count: int) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(DELAY_NULL_SEED))
    ranks = rng.integers(
        0,
        DRAWS,
        size=(NULL_REPLICATIONS, state_count),
        dtype=np.int64,
    )
    return np.mean((ranks + 0.5) / DRAWS, axis=1)


def primary_test(realized_rates: Mapping[str, float]) -> dict[str, Any]:
    """Run the preregistered pooled tier-window test on realized FY2026 rates."""
    data, _ = _load_inputs()
    draws = _generate_baseline_draws(data)
    rosters = _build_rosters(data, draws)
    above, below = _assigned_groups(rosters)
    required = sorted(above + below)
    _validate_realized_rates(realized_rates, required)
    pits = {
        code: _pit_from_draws(float(realized_rates[code]), draws[code])
        for code in required
    }
    statistic = float(np.mean([pits[c] for c in above])) - float(
        np.mean([pits[c] for c in below])
    )
    null_statistics = _primary_null_statistics(above, below)
    p_value = float(np.mean(null_statistics <= statistic))
    return {
        "statistic": statistic,
        "p_value": p_value,
        "reject": p_value <= ALPHA,
        "alpha": ALPHA,
        "alternative": "T < 0",
        "above": above,
        "below": below,
        "pit": pits,
    }


def delay_secondary_test(realized_rates: Mapping[str, float]) -> dict[str, Any]:
    """Run the preregistered upper-tail mean-PIT delay-window test."""
    data, _ = _load_inputs()
    draws = _generate_baseline_draws(data)
    rosters = _build_rosters(data, draws)
    codes = sorted(rosters["delay_probability_window"]["qualifiers"])
    _validate_realized_rates(realized_rates, codes)
    pits = {
        code: _pit_from_draws(float(realized_rates[code]), draws[code])
        for code in codes
    }
    statistic = float(np.mean([pits[code] for code in codes]))
    null_statistics = _delay_null_statistics(len(codes))
    p_value = float(np.mean(null_statistics >= statistic))
    return {
        "statistic": statistic,
        "p_value": p_value,
        "reject": p_value <= ALPHA,
        "alpha": ALPHA,
        "alternative": "U > 0.5",
        "states": codes,
        "pit": pits,
    }


def _pit_matrix(
    realized_rates: np.ndarray,
    codes: list[str],
    baseline_draws: Mapping[str, np.ndarray],
    shifts: Mapping[str, float],
) -> np.ndarray:
    pits = np.empty_like(realized_rates, dtype=np.float64)
    for column, code in enumerate(codes):
        ordered = np.sort(baseline_draws[code])
        shifted = realized_rates[:, column] + shifts.get(code, 0.0)
        left = np.searchsorted(ordered, shifted, side="left")
        right = np.searchsorted(ordered, shifted, side="right")
        pits[:, column] = (left + right) / (2.0 * DRAWS)
    return pits


def _sample_realized_rates(
    codes: list[str],
    baseline_draws: Mapping[str, np.ndarray],
    seed: int,
) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(seed))
    indices = rng.integers(
        0,
        DRAWS,
        size=(POWER_REPLICATIONS, len(codes)),
        dtype=np.int64,
    )
    rates = np.empty(indices.shape, dtype=np.float64)
    for column, code in enumerate(codes):
        rates[:, column] = baseline_draws[code][indices[:, column]]
    return rates


def _power_table(
    baseline_draws: Mapping[str, np.ndarray], rosters: Mapping[str, Any]
) -> dict[str, Any]:
    above, below = _assigned_groups(rosters)
    primary_codes = sorted(above + below)
    above_set = set(above)
    above_mask = np.array([code in above_set for code in primary_codes], dtype=bool)
    primary_rates = _sample_realized_rates(
        primary_codes, baseline_draws, PRIMARY_POWER_SEED
    )
    primary_null = np.sort(_primary_null_statistics(above, below))
    primary_power: dict[str, float] = {}
    for delta in POWER_DELTAS:
        shifts = {code: -delta for code in above}
        pits = _pit_matrix(primary_rates, primary_codes, baseline_draws, shifts)
        statistics = np.mean(pits[:, above_mask], axis=1) - np.mean(
            pits[:, ~above_mask], axis=1
        )
        p_values = np.searchsorted(
            primary_null, statistics, side="right"
        ) / NULL_REPLICATIONS
        primary_power[_delta_key(delta)] = _round4(np.mean(p_values <= ALPHA))

    delay_codes = sorted(rosters["delay_probability_window"]["qualifiers"])
    delay_rates = _sample_realized_rates(
        delay_codes, baseline_draws, DELAY_POWER_SEED
    )
    delay_null = np.sort(_delay_null_statistics(len(delay_codes)))
    delay_power: dict[str, float] = {}
    for delta in POWER_DELTAS:
        shifts = {code: delta for code in delay_codes}
        pits = _pit_matrix(delay_rates, delay_codes, baseline_draws, shifts)
        statistics = np.mean(pits, axis=1)
        p_values = (
            NULL_REPLICATIONS
            - np.searchsorted(delay_null, statistics, side="left")
        ) / NULL_REPLICATIONS
        delay_power[_delta_key(delta)] = _round4(np.mean(p_values <= ALPHA))

    common = {
        "alpha": ALPHA,
        "replications": POWER_REPLICATIONS,
        "deltas_pp": list(POWER_DELTAS),
        "null_replications": NULL_REPLICATIONS,
        "null_p_value_rule": "inclusive empirical tail; reject when p <= alpha",
        "common_random_numbers_across_deltas": True,
    }
    return {
        "primary": {
            **common,
            "seed": PRIMARY_POWER_SEED,
            "null_seed": PRIMARY_NULL_SEED,
            "shift_direction": "downward",
            "shifted_states": "assigned above-group states only",
            "rejection_rates_by_delta_pp": primary_power,
        },
        "delay": {
            **common,
            "seed": DELAY_POWER_SEED,
            "null_seed": DELAY_NULL_SEED,
            "shift_direction": "upward",
            "shifted_states": "every state in the delay probability window",
            "rejection_rates_by_delta_pp": delay_power,
        },
    }


def _definitions(movement: Mapping[str, Any]) -> dict[str, Any]:
    drift = movement["drift_estimate"]
    estimates = drift["point_estimates"]
    return {
        "simulation": (
            "For each state and variant, sample case indices row-major with a "
            "fresh seed-11 Mulberry32 stream; m=n, n+300, or n+500; compute "
            "official_fy2025 + resampled weighted rate - file point rate. "
            "All reported draw SDs use the population denominator (ddof=0)."
        ),
        "random_streams": {
            "algorithm": (
                "bit-faithful Mulberry32; vectorized Weyl state a_k = "
                "(seed + k * 0x6D2B79F5) mod 2^32 for k=1..N"
            ),
            "simulation_seed_each_state_and_variant": SIMULATION_SEED,
            "simulation_draw_order": "C-order (row-major), draw then sample slot",
            "mc_generator": "numpy.random.Generator(PCG64(seed))",
            "mc_matrix_order": "sorted state-code columns, C-order rows",
        },
        "variants": {
            "baseline": "observed resample with m=n",
            "extra_sample_300": "observed resample with m=n+300",
            "extra_sample_500": "observed resample with m=n+500",
            "drift_robust_median_mad": (
                "baseline draw plus independent-across-state N(0, tau^2) drift using "
                "the robust median/MAD tau"
            ),
            "drift_classical_method_of_moments": (
                "baseline draw plus independent-across-state N(0, tau^2) drift using "
                "the classical method-of-moments tau"
            ),
        },
        "quantiles": {
            "levels": list(QUANTILE_LEVELS),
            "convention": (
                "numpy.quantile method='linear' (the NumPy default linear "
                "interpolation convention), computed before rounding"
            ),
        },
        "rounding": (
            "Before hashing and serialization: rates, quantiles, percentage-"
            "point quantities, and probabilities are rounded to 4 decimal "
            "places with Python round (ties to even); dollar expectations are "
            "rounded to whole dollars with the same rule. National totals are "
            "summed at full precision before rounding."
        ),
        "counts": (
            "counts_of_4000 records exact integer draw counts (strict "
            "comparisons identical to the corresponding probabilities), so "
            "the committed crossing and tier predictions are exact "
            "commitments, not rounded summaries."
        ),
        "tiers": (
            "Strict upper cuts: rate <6 -> 0%, <8 -> 5%, <10 -> 10%, "
            "otherwise 15%; a draw exactly at a cut is in the upper tier."
        ),
        "delay": (
            "delay is rate * 1.5 >= 20 evaluated on full-precision floats; "
            "the exact boundary is 20/1.5, not its displayed 13.3333 value"
        ),
        "election": (
            "FY2028 is zero if FY2025 or FY2026 meets delay; otherwise it uses "
            "the tier of min(FY2025,FY2026). FY2029 is zero only if FY2026 "
            "meets delay and otherwise uses the FY2026 tier. sd28 is a "
            "population SD. pWin uses the strict FY2026 < FY2025 comparison."
        ),
        "windows": (
            "Probability windows include endpoints 0.10 and 0.90. Published "
            "two-decimal FY2025 rates define sides; equality is above. A state "
            "qualifying at multiple tier cuts is assigned to minimum "
            "(|FY2025-cut|, cut), so an exact distance tie goes to the lower cut. "
            "nearest_boundary uses the four exact statutory boundaries and the "
            "same lower-boundary tie rule."
        ),
        "drift": {
            "tau_source": (
                "analysis/fy2025_movement.json drift_estimate.point_estimates"
            ),
            "tau_pp": {
                "robust_median_mad": _round4(
                    estimates["robust_median_mad"]["tau_pp"]
                ),
                "classical_method_of_moments": _round4(
                    estimates["classical_method_of_moments"]["tau_pp"]
                ),
            },
            "box_muller": (
                "state k in sorted state-code order uses Mulberry32 seed "
                "1107+k; each draw consumes u1 then u2, clamps u1 at 1e-12, "
                "and uses the cosine form"
            ),
            "independence_note": (
                "This deliberately departs from the app toggle's shared-stream "
                "display convention: drift streams are independent across "
                "states, following the drift artifact's decomposition assumptions."
            ),
            "assumptions_source_key": "drift_estimate.assumptions",
            "assumptions": drift["assumptions"],
        },
        "inference": {
            "pit": PIT_DEFINITION,
            "primary": PRIMARY_TEST_DEFINITION,
            "delay_secondary": DELAY_TEST_DEFINITION,
            "implementation_pins": (
                "PCG64; sorted state-code columns; row-major replication "
                "matrices; no Monte Carlo +1 correction; inclusive empirical "
                "tails; reject when p <= alpha. Extra realized-rate mapping "
                "keys are ignored by each roster-specific callable."
            ),
        },
        "serialization": (
            "Wrapper is {payload, payload_sha256}; the self-pin hashes compact "
            "json.dumps(payload, sort_keys=True, separators=(',', ':')) bytes. "
            "The file uses indent=1, sort_keys=True, ensure_ascii=True, and a "
            "trailing newline."
        ),
    }


def build_payload() -> dict[str, Any]:
    """Build the rounded preregistration payload without reading a clock."""
    data, movement = _load_inputs()
    states = data["states"]
    codes = sorted(states)
    if len(codes) != 53:
        raise ValueError(f"expected 53 jurisdictions, found {len(codes)}")

    estimates = movement["drift_estimate"]["point_estimates"]
    drift_taus = {
        "drift_robust_median_mad": float(
            estimates["robust_median_mad"]["tau_pp"]
        ),
        "drift_classical_method_of_moments": float(
            estimates["classical_method_of_moments"]["tau_pp"]
        ),
    }

    baseline_draws: dict[str, np.ndarray] = {}
    state_predictions: dict[str, Any] = {}
    national_raw = {variant: 0.0 for variant in EXTRA_SAMPLES}
    tier_counts = {str(share): 0 for share in (0, 5, 10, 15)}

    for state_index, code in enumerate(codes):
        state = states[code]
        n = len(state["err"])
        if n != len(state["w"]) or n != len(state["iss"]):
            raise ValueError(f"case-array length mismatch for {code}")
        variants: dict[str, Any] = {}

        for variant, extra in EXTRA_SAMPLES.items():
            draws = simulate(state, extra=extra)
            prediction, raw_election = _variant_prediction(state, draws)
            variants[variant] = prediction
            national_raw[variant] += raw_election["elect28"]
            if variant == "baseline":
                baseline_draws[code] = draws

        for variant, tau in drift_taus.items():
            drifted = baseline_draws[code] + drift_draws(
                tau, seed=DRIFT_SEED_BASE + state_index
            )
            variants[variant], _ = _variant_prediction(state, drifted)

        fy25 = float(state["official_fy2025"])
        nearest = min(ALL_BOUNDARIES, key=lambda cut: (abs(fy25 - cut), cut))
        tier = tier_of(fy25)
        tier_counts[str(tier)] += 1
        state_predictions[code] = {
            "official_fy2025": _round4(fy25),
            "official_fy2024": _round4(state["official"]),
            "n": n,
            "issuance": _whole_dollars(state["issuance"]),
            "tier_fy2025": tier,
            "delay_fy2025": delay_met(fy25),
            "nearest_boundary": _round4(nearest),
            "signed_distance_pp": _round4(fy25 - nearest),
            "sampling_sd": _round4(np.std(baseline_draws[code])),
            "variants": variants,
        }

    rosters = _build_rosters(data, baseline_draws)
    power = _power_table(baseline_draws, rosters)
    national = {
        "state_count": len(codes),
        "sum_elect28_baseline": _whole_dollars(national_raw["baseline"]),
        "sum_elect28_extra300": _whole_dollars(
            national_raw["extra_sample_300"]
        ),
        "sum_elect28_extra500": _whole_dollars(
            national_raw["extra_sample_500"]
        ),
        "tier_counts_fy2025": tier_counts,
    }

    return {
        "schema": SCHEMA,
        "registered": {
            "date": REGISTERED_DATE,
            "registration_record": (
                "The public GitHub commit history is the registration record; "
                "this committed artifact precedes publication of FY2026 outcomes."
            ),
        },
        "provenance": {
            "repository_base": "PolicyEngine/snap-qc-sim origin/main c205e53",
            "generator": "analysis/preregister_obbba_boundary.py",
            "inputs": {
                "app/public/data.json": {
                    "sha256": _sha256(DATA_JSON),
                    "role": "FY2024 cases, FY2024/FY2025 official rates, issuance",
                },
                "analysis/fy2025_movement.json": {
                    "sha256": _sha256(MOVEMENT_JSON),
                    "role": "process-drift tau estimates and assumptions",
                },
            },
            "engine_description": (
                "NumPy-only vectorized port of app/public/app.js simulate(), "
                "driftDraws(), and full electionStats(), using full-precision "
                "draws until the declared serialization boundary."
            ),
            "browser_reference": "app/public/app.js lines 1-260",
            "mirror_reference": (
                "tests/test_adoption_numbers.py bit-faithful Python mirror and "
                "paper/FACTS.md M2/M3/J8 committed goldens"
            ),
        },
        "definitions": _definitions(movement),
        "design": {
            "question": (
                "Does OBBBA cost-sharing exposure causally change FY2026 "
                "measurement and program behavior at the locked FY2025 boundaries?"
            ),
            "no_response_null": (
                "Every FY2026 state measured rate follows its FY2025-centered "
                "observed-resample distribution, with declared sensitivity variants."
            ),
            "boundaries_pp": {
                "tier": list(TIER_CUTS),
                "delay": {
                    "expression": "20/1.5",
                    "display_value": _round4(DELAY_THRESHOLD),
                },
            },
            "windows": {
                "probability": "0.10 <= crossing probability <= 0.90",
                "fixed_widths_pp": list(FIXED_WIDTHS),
            },
            "rosters": rosters,
            "tests": {
                "primary": {
                    "definition": PRIMARY_TEST_DEFINITION,
                    "alpha": ALPHA,
                    "alternative": "T < 0",
                    "null_replications": NULL_REPLICATIONS,
                    "seed": PRIMARY_NULL_SEED,
                    "p_value_tail": "fraction(null T <= realized T)",
                },
                "delay_secondary": {
                    "definition": DELAY_TEST_DEFINITION,
                    "alpha": ALPHA,
                    "alternative": "U > 0.5",
                    "null_replications": NULL_REPLICATIONS,
                    "seed": DELAY_NULL_SEED,
                    "p_value_tail": "fraction(null U >= realized U)",
                },
            },
        },
        "predictions": {
            "states": state_predictions,
            "national": national,
        },
        "power": power,
    }


def main(out_path: str | Path = OUT_JSON) -> dict[str, Any]:
    """Build, self-pin, and write the deterministic preregistration artifact."""
    destination = Path(out_path)
    payload = build_payload()
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    payload_sha256 = hashlib.sha256(canonical).hexdigest()
    artifact = {"payload": payload, "payload_sha256": payload_sha256}
    serialized = json.dumps(
        artifact, indent=1, sort_keys=True, ensure_ascii=True
    ).encode() + b"\n"
    destination.write_bytes(serialized)
    file_sha256 = hashlib.sha256(serialized).hexdigest()
    print(f"artifact path: {destination}")
    print(f"payload_sha256: {payload_sha256}")
    print(f"full-file sha256: {file_sha256}")
    return artifact


if __name__ == "__main__":
    main()
