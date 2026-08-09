"""Unit tests for the FY2025 movement analysis pure functions."""

import math

import pytest

from analysis.fy2025_movement import (
    TWO_YEAR_Z,
    delay_applies,
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
