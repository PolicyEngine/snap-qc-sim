"""Unit tests over synthetic cases (no data download required)."""

import numpy as np
import pytest

from snap_qc_sim import (
    LEVERS,
    QcCase,
    lever_error,
    simulate,
    summarize,
    tier_of,
)


def test_tier_boundaries():
    assert tier_of(5.99) == 0
    assert tier_of(6.0) == 5
    assert tier_of(7.99) == 5
    assert tier_of(8.0) == 10
    assert tier_of(9.99) == 10
    assert tier_of(10.0) == 15
    assert tier_of(24.66) == 15


def test_lever_error_scales_by_element_share():
    e = frozenset({365, 311})
    assert lever_error(100.0, e, LEVERS["smd"], 1.0) == pytest.approx(50.0)
    assert lever_error(100.0, e, LEVERS["smd"], 0.5) == pytest.approx(75.0)
    assert lever_error(100.0, frozenset({365}), LEVERS["smd"], 1.0) == 0.0
    assert lever_error(0.0, frozenset({365}), LEVERS["smd"], 1.0) == 0.0
    assert lever_error(100.0, frozenset({311}), LEVERS["smd"], 1.0) == 100.0


def _cases(n=400, error_rate=0.1, seed=3):
    rng = np.random.default_rng(seed)
    cases = []
    for _ in range(n):
        issued = float(rng.uniform(100, 900))
        has_err = rng.random() < 0.3
        err = issued * error_rate / 0.3 if has_err else 0.0
        cases.append(QcCase(1.0, issued, err, frozenset({365}) if has_err else frozenset()))
    return cases


def test_more_audits_shrink_spread():
    cases = _cases()
    base = simulate(cases, 10.0, rng=np.random.default_rng(1), draws=4000)
    more = simulate(cases, 10.0, extra_audits=1200, rng=np.random.default_rng(1), draws=4000)
    assert more.std() < base.std() * 0.7
    assert abs(more.mean() - base.mean()) < 0.2


def test_full_suppression_zeroes_the_rate_shift():
    cases = _cases()
    rates = simulate(
        cases, 10.0, suppressed=LEVERS["smd"], effectiveness=1.0,
        rng=np.random.default_rng(2), draws=2000,
    )
    # All error cases carry only element 365, so full suppression removes
    # the whole sample rate; the centered level drops by the sample rate.
    assert rates.mean() < 1.0


def test_summarize_prices_tiers():
    rates = np.array([9.5, 9.5, 10.5, 10.5])
    s = summarize(rates, 1_000_000_000)
    assert s["p_tier"]["10"] == 0.5 and s["p_tier"]["15"] == 0.5
    assert s["expected_cost_share"] == pytest.approx(0.125 * 1_000_000_000)
