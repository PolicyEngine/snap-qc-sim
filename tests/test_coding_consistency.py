"""Contract tests for the historical coding-consistency audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis import build_coding_consistency as builder

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "analysis/coding_consistency.json"
REFERENCE = ROOT / "analysis/cause_shares.json"
PAYLOAD = json.loads(ARTIFACT.read_text())
CAUSE_SHARES = json.loads(REFERENCE.read_text())
needs_raw_sources = pytest.mark.skipif(
    not all(builder.source_path(year).exists() for year in builder.YEARS)
    or not all(
        (builder.SOURCE_ROOT / f"qc_pub_fy2020_per{period}.sav").exists()
        for period in (1, 2)
    )
    or not (builder.HISTORICAL_ROOT / "qcfy2017_csv" / "qc_pub_fy2017.csv").exists()
    or not builder.HISTORICAL_HASHES.exists(),
    reason="local historical QC raw sources are not all present",
)


def test_committed_artifact_schema_and_years() -> None:
    """Lock the top-level schema and complete ordered fiscal-year panel."""
    assert PAYLOAD["schema"] == builder.SCHEMA
    assert PAYLOAD["schema_version"] == builder.SCHEMA_VERSION == 2
    assert list(PAYLOAD["years"]) == [str(year) for year in builder.YEARS]
    assert PAYLOAD["scope_note"] == "Inventory/accounting only; no causal claims."
    assert set(PAYLOAD["panel_recommendation"]) == {
        "strict_class_outcomes",
        "status",
        "total_rate_fixed_real_threshold",
    }


@pytest.mark.parametrize("year", builder.YEARS)
def test_per_year_presence_flags(year: int) -> None:
    """All supplied years retain the fields and nine finding slots audited."""
    block = PAYLOAD["years"][str(year)]
    fields = block["row_universe"]["fields"]
    assert all(fields[field]["present"] for field in builder.CORE_FIELDS)
    assert block["cause_slots"]["all_nine_present"]
    assert all(
        block["findings"][root]["all_nine_present"]
        for root in ("nature", "e_findg", "element")
    )
    assert (
        block["row_universe"]["active_case_count"]
        == block["row_universe"]["case_distribution"]["1"]
    )
    assert block["source"]["sha256"]


def test_threshold_acquisition_boundary_is_explicit() -> None:
    """Unavailable earlier documentation must never silently become a value."""
    assert [
        PAYLOAD["years"][str(year)]["threshold"]["dollars"]
        for year in range(2012, 2018)
    ] == [50, 50, 37, 38, 38, 38]
    assert all(
        PAYLOAD["years"][str(year)]["threshold"]["status"] == "verified_local_techdoc"
        for year in range(2012, 2018)
    )
    for year, cite in (
        (2018, "FY2018_Tech_Doc.pdf p. 14 ($37, a decrease of $1 from FY2017)"),
        (2019, "FY2019_Tech_Doc.pdf p. 10 ($37, unchanged from FY2018)"),
    ):
        threshold = PAYLOAD["years"][str(year)]["threshold"]
        assert threshold == {
            "citation": cite,
            "dollars": 37,
            "status": "verified_local_techdoc",
        }
    assert [
        PAYLOAD["years"][str(year)]["threshold"]["dollars"]
        for year in range(2020, 2025)
    ] == [37, 39, 48, 54, 56]


def test_preperiod_strict_class_and_fy2017_cross_check_are_locked() -> None:
    """Lock the RI/KY pre-period evidence and independent FY2017 reconciliation."""
    for year in range(2012, 2017):
        cause_slots = PAYLOAD["years"][str(year)]["cause_slots"]
        strict = cause_slots["strict_computing_apparatus"]
        assert builder.STRICT_CODES <= set(cause_slots["observed_codes"])
        assert strict["present"] is True
        assert strict["active_cases_any"] > 0
    cross_check = PAYLOAD["source_cross_checks"]["fy2017_csv_vs_sav"]
    assert cross_check["row_count_difference_csv_minus_sav"] == 0
    assert cross_check["reconciles"] is True
    assert all(
        inventory["exact_match"]
        for inventory in cross_check["cause_slot_inventories"].values()
    )
    assert PAYLOAD["years"]["2014"]["findings"]["e_findg"]["observed_codes"] == [
        2,
        3,
        4,
        "A",
    ]


def test_fy2024_reconciles_with_cause_shares_inventories() -> None:
    """Lock every overlapping FY2024 convention to cause_shares.json."""
    conventions = PAYLOAD["reference_conventions"]
    assert conventions["cause_codes"] == sorted(
        int(code) for code in CAUSE_SHARES["cause_codes"]
    )
    fy2024 = PAYLOAD["years"]["2024"]
    assert fy2024["cause_slots"]["codes_absent_from_fy2024_map"] == []
    assert conventions["strict_computing_apparatus"] == sorted(builder.STRICT_CODES)
    assert conventions["broad_computing_apparatus"] == sorted(builder.BROAD_CODES)
    semantics = CAUSE_SHARES["finding_nature_semantics"]
    expected_natures = sorted(
        semantics["inherent_computation"]["nature_codes"]
        + semantics["conditional_deduction"]["nature_codes"]
    )
    assert conventions["facts_k3_nature_codes"] == expected_natures
    assert (
        conventions["facts_k3_element_codes"]
        == semantics["inherent_computation"]["element_codes"]
    )


def test_pandemic_files_and_recommendation_are_locked() -> None:
    """Prevent the partial pandemic samples from being normalized away."""
    pandemic = PAYLOAD["pandemic_file_handling"]
    assert pandemic["fy2020"]["row_count_reconciles"] is True
    assert pandemic["fy2020"]["period_row_sum"] == 27_112
    assert pandemic["fy2021"]["rows"] == 9_832
    assert "pandemic-partial" in pandemic["fy2021"]["recommendation"]
    assert PAYLOAD["panel_recommendation"]["status"].endswith("not_a_design_decision")


@needs_raw_sources
def test_raw_sav_regeneration_is_byte_identical_and_committed() -> None:
    """Two independent builds serialize identically and match the artifact."""
    first = (
        json.dumps(builder.build(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    second = (
        json.dumps(builder.build(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    assert first == second == ARTIFACT.read_text()
