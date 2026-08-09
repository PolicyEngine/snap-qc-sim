"""Unit tests for the FY2025 movement analysis pure functions."""

import math

import numpy as np
import pytest

from analysis.fy2025_movement import (
    NORMAL_MAD_SCALE,
    TWO_YEAR_Z,
    delay_applies,
    estimate_process_drift,
    movement_row,
    tier_share,
)


def test_tier_share_boundaries():
    assert tier_share(0.0) == 0
    assert tier_share(5.99) == 0
    assert tier_share(6.0) == 5
    assert tier_share(7.99) == 5
    assert tier_share(8.0) == 10
    assert tier_share(9.99) == 10
    assert tier_share(10.0) == 15
    assert tier_share(24.66) == 15


def test_tier_share_rejects_bad_rates():
    with pytest.raises(ValueError):
        tier_share(-0.01)
    with pytest.raises(ValueError):
        tier_share(math.nan)


def test_delay_applies_published_precision_boundary():
    # 13.33 x 1.5 = 19.995 < 20; 13.34 x 1.5 = 20.01 >= 20.
    assert not delay_applies(13.33)
    assert delay_applies(13.34)
    assert delay_applies(23.15)
    assert not delay_applies(0.0)


def test_movement_row_z_and_flags():
    row = movement_row("XX", 9.97, 10.09, 0.9)
    assert row["delta_pp"] == pytest.approx(0.12)
    assert row["z_vs_fy2024_sampling_sd"] == pytest.approx(0.12 / 0.9, abs=1e-4)
    assert row["tier_fy2024"] == 10
    assert row["tier_fy2025"] == 15
    assert row["tier_changed"] is True
    assert row["beyond_two_year_noise_95"] is False
    assert row["delay_fy2024"] is False and row["delay_fy2025"] is False


def test_movement_row_beyond_noise_uses_two_year_band():
    sd = 0.5
    just_inside = movement_row("XX", 8.0, 8.0 + sd * (TWO_YEAR_Z - 0.01), sd)
    just_beyond = movement_row("XX", 8.0, 8.0 + sd * (TWO_YEAR_Z + 0.01), sd)
    assert just_inside["beyond_two_year_noise_95"] is False
    assert just_beyond["beyond_two_year_noise_95"] is True


def test_movement_row_zero_sd_is_signed_infinite_z():
    up = movement_row("XX", 5.0, 6.0, 0.0)
    assert math.isinf(up["z_vs_fy2024_sampling_sd"])
    assert up["z_vs_fy2024_sampling_sd"] > 0


def test_classical_drift_estimator_matches_method_of_moments():
    deltas = np.array([-3.0, -1.0, 1.0, 3.0])
    sampling_sds = np.ones(4)

    estimate = estimate_process_drift(deltas, sampling_sds, bootstrap_draws=32, seed=1)
    point = estimate["point_estimates"]["classical_method_of_moments"]

    observed_variance = np.var(deltas, ddof=1)
    expected_drift_variance = observed_variance - 2.0
    assert point["observed_movement_variance_pp2"] == pytest.approx(
        observed_variance, abs=1e-4
    )
    assert point["two_year_sampling_variance_pp2"] == pytest.approx(2.0)
    assert point["untruncated_drift_variance_pp2"] == pytest.approx(
        expected_drift_variance, abs=1e-4
    )
    assert point["tau_pp"] == pytest.approx(
        math.sqrt(expected_drift_variance), abs=1e-4
    )


def test_drift_estimator_truncates_negative_variance_component_at_zero():
    estimate = estimate_process_drift(
        [-0.1, 0.0, 0.1], [1.0, 1.0, 1.0], bootstrap_draws=16
    )

    for name in ("classical_method_of_moments", "robust_median_mad"):
        point = estimate["point_estimates"][name]
        assert point["untruncated_drift_variance_pp2"] < 0
        assert point["tau_pp"] == 0


def test_robust_drift_estimator_uses_normal_consistent_mad():
    deltas = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    sampling_sds = np.full(5, 0.2)

    estimate = estimate_process_drift(deltas, sampling_sds, bootstrap_draws=32, seed=2)
    robust = estimate["point_estimates"]["robust_median_mad"]
    expected_observed_variance = (1.0 / NORMAL_MAD_SCALE) ** 2
    expected_sampling_variance = 2 * 0.2**2

    assert robust["median_delta_pp"] == 0
    assert robust["movement_mad_pp"] == 1
    assert robust["normal_consistent_observed_variance_pp2"] == pytest.approx(
        expected_observed_variance, abs=1e-4
    )
    assert robust["two_year_median_sampling_variance_pp2"] == pytest.approx(
        expected_sampling_variance
    )
    assert robust["tau_pp"] == pytest.approx(
        math.sqrt(expected_observed_variance - expected_sampling_variance),
        abs=1e-4,
    )


def test_robust_drift_estimator_resists_one_extreme_movement():
    estimate = estimate_process_drift(
        [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 100.0],
        [0.0] * 7,
        bootstrap_draws=32,
    )

    points = estimate["point_estimates"]
    assert (
        points["robust_median_mad"]["tau_pp"]
        < points["classical_method_of_moments"]["tau_pp"]
    )


def test_drift_bootstrap_is_deterministic_and_reports_uncertainty():
    kwargs = {"bootstrap_draws": 256, "seed": 8675309}
    first = estimate_process_drift([-2, -1, 0, 1, 3], [0.4] * 5, **kwargs)
    second = estimate_process_drift([-2, -1, 0, 1, 3], [0.4] * 5, **kwargs)

    assert first == second
    assert first["bootstrap"]["draws"] == 256
    assert first["bootstrap"]["seed"] == 8675309
    for name in ("classical_tau", "robust_tau"):
        summary = first["bootstrap"][name]
        assert summary["standard_error_pp"] >= 0
        assert (
            summary["confidence_interval_95_pp"][0]
            <= summary["confidence_interval_95_pp"][1]
        )
        assert 0 <= summary["zero_estimate_share"] <= 1


@pytest.mark.parametrize(
    ("deltas", "sampling_sds", "message"),
    [
        ([1.0], [0.1], "at least two"),
        ([1.0, 2.0], [0.1], "same length"),
        ([1.0, math.nan], [0.1, 0.1], "deltas must be finite"),
        ([1.0, 2.0], [0.1, -0.1], "finite and nonnegative"),
    ],
)
def test_drift_estimator_rejects_invalid_inputs(deltas, sampling_sds, message):
    with pytest.raises(ValueError, match=message):
        estimate_process_drift(deltas, sampling_sds, bootstrap_draws=8)
