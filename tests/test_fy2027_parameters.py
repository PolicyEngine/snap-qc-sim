"""Tests for the FY2027 SNAP QC tolerance derivation."""

from decimal import Decimal

import pytest

from analysis.fy2027_parameters import (
    apply_rounding,
    build,
    derive_threshold,
    evaluate_rounding_conventions,
    render_markdown,
    tfp_boundary_for_threshold,
    unrounded_threshold,
)


def test_statutory_scaling_uses_exact_decimal_inputs():
    assert unrounded_threshold("939.90") == Decimal(37) * Decimal("939.90") / Decimal(
        "632.30"
    )


def test_rounding_self_test_uniquely_reproduces_published_fy2022_to_fy2026():
    result = evaluate_rounding_conventions()

    assert result["years_tested"] == [2022, 2023, 2024, 2025, 2026]
    assert result["matching_conventions"] == ["floor"]
    assert result["unique_match"] is True
    assert [
        row["candidate_thresholds_dollars"]["floor"] for row in result["comparisons"]
    ] == [48, 54, 56, 57, 58]


def test_fy2023_near_integer_distinguishes_floor_from_nearest_and_ceiling():
    raw = unrounded_threshold("939.90")

    assert raw < 55
    assert apply_rounding(raw, "floor") == 54
    assert apply_rounding(raw, "nearest_half_up") == 55
    assert apply_rounding(raw, "ceiling") == 55


def test_fy2027_is_explicit_estimate_using_latest_official_month():
    result = build()
    estimate = result["fy2027_result"]
    series_row = result["threshold_series"][-1]

    assert derive_threshold("1018.20") == 59
    assert estimate["status"] == "ESTIMATE"
    assert estimate["missing_input"] is True
    assert estimate["required_input_month"] == "2026-06"
    assert estimate["latest_official_input_month"] == "2026-05"
    assert estimate["convention_ambiguity"].startswith("none")
    assert estimate["input_uncertainty_bounded_by_available_evidence"] is False
    assert "estimate_range_dollars" not in estimate
    assert series_row["status"] == "ESTIMATE"
    assert series_row["source_label"] == "fna"


def test_nearby_sensitivity_uses_exact_floor_decision_boundaries():
    estimate = build()["fy2027_result"]
    sensitivity = estimate["nearby_threshold_sensitivity"]

    assert [row["threshold_dollars"] for row in sensitivity] == [58, 59, 60, 61]
    assert Decimal(estimate["boundary_for_60_dollars_decimal"]) == (
        tfp_boundary_for_threshold(60)
    )
    assert estimate["boundary_for_60_dollars_exact_fraction"] == "37938/37"
    assert estimate["first_sufficient_published_tenth_for_60_dollars"] == 1025.4
    assert derive_threshold("1025.30") == 59
    assert derive_threshold("1025.40") == 60


def test_every_threshold_series_value_has_source_label_and_receipt_url():
    for row in build()["threshold_series"]:
        assert row["source_label"] in {"axiom", "pe", "fna"}
        assert row["source_url"].startswith("https://")


def test_source_precedence_audit_is_explicit_and_generator_is_offline():
    sources = build()["source_audit"]

    assert "No encoded June-30" in sources["axiom"]["result"]
    assert "not the required June-30" in sources["pe"]["result"]
    assert sources["fna"]["source_label"] == "fna"
    assert sources["network_fetches_by_generator"] == []
    for observation in sources["fna"]["observations"]:
        assert len(observation["observation_record_sha256"]) == 64
        assert observation["source_file_sha256"] is None


def test_generated_markdown_keeps_estimate_warning_prominent():
    markdown = render_markdown(build())

    assert "**ESTIMATE: $59 using the May 2026 proxy.**" in markdown
    assert "not an official FY2027 value" in markdown
    assert "not a forecast range" in markdown
    assert "Only **floor**" in markdown
    assert "FY2021 is $39" in markdown


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_invalid_tfp_values_are_rejected(value):
    with pytest.raises(ValueError):
        unrounded_threshold(value)


def test_unknown_rounding_convention_is_rejected():
    with pytest.raises(ValueError, match="unknown rounding convention"):
        apply_rounding("10.5", "bankers")
