"""Unit tests for the pure NumPy predictive deviation process."""

import numpy as np
import pytest

from analysis.predictive_process import (
    QUANTILE_LEVELS,
    conditional_survival,
    draw_deviations,
    enforce_monotone_quantiles,
    error_dollars,
    expected_error_dollars,
)


def test_enforce_monotone_quantiles_sorts_and_clips_each_case():
    predicted = np.array(
        [
            [np.log(4.0), np.log(0.1), np.log(2.0)],
            [np.log(3.0), np.log(1.0), np.log(2.0)],
        ]
    )

    result = enforce_monotone_quantiles(predicted, minimum_magnitude=0.5)

    assert np.allclose(
        np.exp(result),
        [[0.5, 2.0, 4.0], [1.0, 2.0, 3.0]],
    )


def test_error_dollars_uses_a_strict_threshold_crossing():
    deviation = np.array([-57.0, -56.0, 0.0, 56.0, 57.0])

    assert error_dollars(deviation, 56.0).tolist() == [57.0, 0.0, 0.0, 0.0, 57.0]


def test_conditional_survival_matches_quantile_knots_and_tail():
    magnitudes = np.arange(2.0, 11.0)
    log_quantiles = np.log(magnitudes)
    scale = 0.25

    at_knots = conditional_survival(magnitudes, log_quantiles, scale)
    tail_threshold = magnitudes[-1] * 2**scale
    in_tail = conditional_survival(tail_threshold, log_quantiles, scale)

    assert np.allclose(at_knots, 1.0 - QUANTILE_LEVELS)
    assert in_tail == pytest.approx((1.0 - QUANTILE_LEVELS[-1]) / 2.0)
    assert conditional_survival(0.49, log_quantiles, scale) == pytest.approx(1.0)


def test_conditional_survival_counts_flat_body_mass_at_strict_threshold():
    log_quantiles = np.full(QUANTILE_LEVELS.size, np.log(10.0))

    survival = conditional_survival(10.0, log_quantiles, tail_scale=0.25)

    assert survival == pytest.approx(1.0 - QUANTILE_LEVELS[-1])


def test_draw_deviations_respects_deviation_and_sign_probabilities():
    log_quantiles = np.broadcast_to(np.log(np.arange(2.0, 11.0)), (3, 9))
    draws = draw_deviations(
        p_dev=np.array([0.0, 1.0, 1.0]),
        p_pos=np.array([0.5, 0.0, 1.0]),
        log_quantiles=log_quantiles,
        tail_scale=0.2,
        rng=np.random.default_rng(42),
        magnitude_cap=100.0,
    )

    assert draws[0] == 0.0
    assert draws[1] < 0.0
    assert draws[2] > 0.0


def test_monte_carlo_mean_matches_closed_form_expectation():
    sample_size = 500_000
    deviation_probability = 0.4
    magnitude = 10.0
    scale = 0.25
    threshold = 5.0
    log_quantiles = np.full((1, QUANTILE_LEVELS.size), np.log(magnitude))

    analytic = expected_error_dollars(
        deviation_probability,
        log_quantiles,
        scale,
        threshold,
        minimum_magnitude=magnitude,
    )
    draws = draw_deviations(
        p_dev=np.full(sample_size, deviation_probability),
        p_pos=0.5,
        log_quantiles=log_quantiles,
        tail_scale=scale,
        rng=np.random.default_rng(20240806),
        magnitude_cap=1e12,
        minimum_magnitude=magnitude,
    )
    simulated = error_dollars(draws, threshold).mean()

    # Here 99% of deviators have magnitude 10 and the final 1% follows a
    # Pareto tail with mean 10 / (1 - scale), giving a closed-form benchmark.
    closed_form = deviation_probability * (
        QUANTILE_LEVELS[-1] * magnitude
        + (1.0 - QUANTILE_LEVELS[-1]) * magnitude / (1.0 - scale)
    )
    assert analytic.item() == pytest.approx(closed_form)
    assert simulated == pytest.approx(closed_form, abs=0.025)


@pytest.mark.parametrize("probability", [-0.01, 1.01, np.nan])
def test_draw_deviations_rejects_invalid_probabilities(probability):
    with pytest.raises(ValueError):
        draw_deviations(
            p_dev=probability,
            p_pos=0.5,
            log_quantiles=np.zeros(QUANTILE_LEVELS.size),
            tail_scale=0.2,
            rng=np.random.default_rng(1),
            magnitude_cap=100.0,
        )


@pytest.mark.parametrize("scale", [0.45, 0.5, 1.0])
def test_predictive_process_requires_finite_variance_margin(scale):
    with pytest.raises(ValueError, match="below 0.45"):
        expected_error_dollars(
            0.5,
            np.zeros(QUANTILE_LEVELS.size),
            scale,
            56.0,
        )


def test_expected_error_matches_closed_form_for_a_truncated_tail():
    probability = 0.4
    magnitude = 10.0
    scale = 0.25
    threshold = magnitude * 2**scale
    log_quantiles = np.full(QUANTILE_LEVELS.size, np.log(magnitude))

    actual = expected_error_dollars(
        probability,
        log_quantiles,
        scale,
        threshold,
        minimum_magnitude=magnitude,
    )
    expected_tail = (
        probability
        * (1.0 - QUANTILE_LEVELS[-1])
        * magnitude
        / (1.0 - scale)
        * 2 ** (-(1.0 - scale))
    )

    assert actual.item() == pytest.approx(expected_tail)


def test_draw_deviations_enforces_per_case_caps_on_body_and_tail():
    log_quantiles = np.full((2, QUANTILE_LEVELS.size), np.log(1_000.0))

    draws = draw_deviations(
        p_dev=np.ones(2),
        p_pos=np.ones(2),
        log_quantiles=log_quantiles,
        tail_scale=0.25,
        rng=np.random.default_rng(9),
        magnitude_cap=np.array([20.0, 30.0]),
    )

    assert draws.tolist() == pytest.approx([20.0, 30.0])


@pytest.mark.parametrize("cap", [0.49, 0.0, np.nan, np.inf])
def test_draw_deviations_rejects_invalid_caps(cap):
    with pytest.raises(ValueError, match="magnitude_cap"):
        draw_deviations(
            p_dev=1.0,
            p_pos=1.0,
            log_quantiles=np.zeros(QUANTILE_LEVELS.size),
            tail_scale=0.25,
            rng=np.random.default_rng(1),
            magnitude_cap=cap,
        )


def test_capped_expected_error_matches_tail_identity_and_strict_threshold():
    probability = 0.4
    magnitude = 10.0
    scale = 0.25
    cap = 20.0
    threshold = 5.0
    log_quantiles = np.full(QUANTILE_LEVELS.size, np.log(magnitude))

    above_threshold = expected_error_dollars(
        probability,
        log_quantiles,
        scale,
        threshold,
        minimum_magnitude=magnitude,
    )
    above_cap = expected_error_dollars(
        probability,
        log_quantiles,
        scale,
        cap,
        minimum_magnitude=magnitude,
    )
    survival_at_cap = conditional_survival(
        cap,
        log_quantiles,
        scale,
        minimum_magnitude=magnitude,
    )
    capped = expected_error_dollars(
        probability,
        log_quantiles,
        scale,
        threshold,
        minimum_magnitude=magnitude,
        magnitude_cap=cap,
    )

    assert capped.item() == pytest.approx(
        above_threshold.item()
        - above_cap.item()
        + probability * cap * survival_at_cap.item()
    )
    assert (
        expected_error_dollars(
            probability,
            log_quantiles,
            scale,
            cap,
            minimum_magnitude=magnitude,
            magnitude_cap=cap,
        ).item()
        == 0.0
    )
