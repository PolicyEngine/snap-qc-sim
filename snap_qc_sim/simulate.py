"""Monte Carlo of the measured error rate under audit-volume and policy levers.

Method: the state's QC sample supplies the error process (who has counted
errors, how large, which finding elements). Scenarios re-draw QC-style
samples of a chosen size and recompute the weighted measured rate, centered
on the official published rate (which carries FNS's regression adjustment).
Policy levers suppress the error contribution of the finding-element
categories they standardize away, at a chosen effectiveness — a scenario
dial, not a causal estimate.
"""

from __future__ import annotations

import numpy as np

from .data import QcCase

#: 7 USC 2013(a)(2) cost-share tiers: (rate upper bound, state share %).
TIERS: list[tuple[float, int]] = [(6.0, 0), (8.0, 5), (10.0, 10), (float("inf"), 15)]

#: Policy lever -> QC finding ELEMENT codes it suppresses.
LEVERS: dict[str, frozenset[int]] = {
    # Standard medical deduction, sized at or above the Medicare Part B
    # premium so it binds for nearly all claimants (element 365).
    "smd": frozenset({365}),
    # Standard self-employment expense deduction (element 312).
    "ssed": frozenset({312}),
    # Heat-and-eat: SUA entitlement removes utility-amount variances
    # (element 364). The elderly/disabled-only variant is a subset; this
    # v1 applies the full element as an upper bound.
    "heat_and_eat": frozenset({364}),
    # Broad-based categorical eligibility: removes resource-screen
    # variances (elements 211-225).
    "bbce_resources": frozenset({211, 212, 213, 221, 222, 224, 225}),
}


def tier_of(rate: float) -> int:
    """State share percentage for a payment error rate."""
    for cut, share in TIERS:
        if rate < cut:
            return share
    return 15


def lever_error(error: float, elements: frozenset[int], suppressed: frozenset[int],
                effectiveness: float) -> float:
    """Counted error dollars for a case after suppressing lever categories.

    Single-attribution approximation: the case's error is scaled by the share
    of its finding elements that survive, times the lever effectiveness. A
    case whose findings are all suppressed drops out at ``effectiveness``.
    """
    if error == 0 or not elements:
        return error
    hit = len(elements & suppressed) / len(elements)
    return error * (1 - effectiveness * hit)


def simulate(
    cases: list[QcCase],
    official_rate: float,
    *,
    extra_audits: int = 0,
    suppressed: frozenset[int] = frozenset(),
    effectiveness: float = 1.0,
    draws: int = 10_000,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Draws from the measured-rate distribution for one scenario.

    Resampling at the scenario's sample size carries the audit-volume
    variance effect (SD ~ 1/sqrt(n)); the distribution is centered at the
    official rate shifted by the lever's effect on the sample's own rate.
    """
    rng = rng or np.random.default_rng()
    w = np.array([c.weight for c in cases])
    iss = np.array([c.issuance for c in cases])
    err0 = np.array([c.error for c in cases])
    err = np.array(
        [lever_error(c.error, c.elements, suppressed, effectiveness) for c in cases]
    )
    n = len(cases)
    point0 = 100 * (w * err0).sum() / (w * iss).sum()
    point1 = 100 * (w * err).sum() / (w * iss).sum()
    level = official_rate + (point1 - point0)
    m = n + extra_audits
    idx = rng.integers(0, n, size=(draws, m))
    boots = 100 * (w * err)[idx].sum(axis=1) / (w * iss)[idx].sum(axis=1)
    return level + (boots - point1)


def summarize(rates: np.ndarray, issuance: float) -> dict:
    """Tier probabilities and cost-share dollars for a rate distribution."""
    shares = np.array([tier_of(r) for r in rates], dtype=float)
    dollars = shares / 100 * issuance
    return {
        "mean_rate": float(rates.mean()),
        "sd_rate": float(rates.std()),
        "p_tier": {str(s): float((shares == s).mean()) for s in (0, 5, 10, 15)},
        "expected_cost_share": float(dollars.mean()),
        "sd_cost_share": float(dollars.std()),
        "p95_cost_share": float(np.percentile(dollars, 95)),
    }
