"""Fast contract and optional raw-data tests for the RI/KY event study."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from analysis import event_study


def _fixture_panel() -> pd.DataFrame:
    """Return a fixture suitable for tolerance, not platform hash, assertions.

    The optimizer can differ in last-bit floats across BLAS implementations.
    Tests therefore require same-process byte determinism and recover planted
    effects within tolerance; they do not hash optimizer output across systems.
    """
    rows = []
    states = ["AL", "CA", "FL", "GA", "KY", "NM", "OR", "RI", "TX"]
    for state_index, state in enumerate(states):
        for year in event_study.RIKY_YEARS:
            trend = year - 2012
            treatment_shift = 0.0
            if year >= 2017:
                treatment_shift = {"RI": 2.0, "KY": 4.0}.get(state, 0.0)
            rows.append(
                {
                    "state": state,
                    "year": year,
                    "strict_computing_dollars_per_case_month": (
                        1.0 + state_index * 0.2 + trend * 0.1 + treatment_shift
                    ),
                    "total_error_rate": (
                        4.0 + state_index * 0.3 + trend * 0.2 + treatment_shift
                    ),
                    "client_dollars_per_case_month": (
                        2.0 + state_index * 0.1 + trend * 0.05
                    ),
                }
            )
    return pd.DataFrame(rows)


def test_riky_fixture_schema_paths_and_donor_exclusions() -> None:
    result = event_study.build_riky_results(_fixture_panel())
    assert result["schema"] == "snap_qc_sim.riky_event_study.v1"
    assert result["scope"]["treated_states"] == ["RI", "KY"]
    assert result["scope"]["donor_pool"] == ["AL", "CA", "TX"]
    assert set(result["units"]) == {"RI", "KY"}
    for state in ("RI", "KY"):
        path = result["units"][state]["specifications"][
            "primary_exclude_fy2016_drop_fy2021"
        ]["outcomes"]["strict_computing_dollars_per_case_month"]["path"]
        assert len(path) == 13
        assert [row["event_time"] for row in path] == list(range(-4, 9))


def test_riky_fixture_is_deterministic_and_recovers_planted_effects() -> None:
    first = event_study.serialize_results(
        event_study.build_riky_results(_fixture_panel())
    )
    second = event_study.serialize_results(
        event_study.build_riky_results(_fixture_panel())
    )
    assert first == second
    result = json.loads(first)
    for state, planted in (("RI", 2.0), ("KY", 4.0)):
        outcome = result["units"][state]["specifications"][
            "primary_exclude_fy2016_drop_fy2021"
        ]["outcomes"]["strict_computing_dollars_per_case_month"]
        assert abs(outcome["effect"] - planted) < 0.05
        pre_gaps = [
            row["gap"] for row in outcome["path"] if row["year"] in range(2012, 2016)
        ]
        assert all(abs(gap) < 0.05 for gap in pre_gaps)
    pooled = result["pooled"]["statistics"]["strict_computing_dollars_per_case_month"][
        "effect"
    ]
    assert abs(pooled - 3.0) < 0.05


def test_committed_riky_artifact_contract() -> None:
    result = json.loads(event_study.RIKY_OUT.read_bytes())
    assert result["schema"] == "snap_qc_sim.riky_event_study.v1"
    assert result["scope"]["panel_years"] == list(range(2012, 2025))
    assert set(result["units"]) == {"RI", "KY"}
    assert set(result["pooled"]["statistics"]) == set(event_study.OUTCOMES)
    assert result["outcome_definitions"]["strict_codes"] == [17, 19, 20]
    assert result["units"]["RI"]["decision"]["verdict"] == "signal"
    assert result["units"]["KY"]["decision"]["verdict"] == "no_protocol_defined_signal"
    assert result["pooled"]["decision"]["verdict"] == "signal"
    assert (
        result["units"]["RI"]["permutation_inference"][
            "strict_computing_dollars_per_case_month"
        ]["absolute_rank"]
        == 1
    )
    assert (
        result["units"]["KY"]["permutation_inference"][
            "strict_computing_dollars_per_case_month"
        ]["absolute_rank"]
        == 13
    )
    assert (
        result["pooled"]["permutation_inference"][
            "strict_computing_dollars_per_case_month"
        ]["absolute_rank"]
        == 4
    )
    assert result["units"]["RI"]["specifications"][
        "primary_exclude_fy2016_drop_fy2021"
    ]["outcomes"]["strict_computing_dollars_per_case_month"]["effect"] == pytest.approx(
        2.89676409242692
    )
    assert result["units"]["KY"]["specifications"][
        "primary_exclude_fy2016_drop_fy2021"
    ]["outcomes"]["strict_computing_dollars_per_case_month"]["effect"] == pytest.approx(
        -0.5843029139007678
    )


@pytest.mark.skipif(
    not event_study.riky_raw_inputs_available(),
    reason="complete hash-audited mixed-format cache unavailable",
)
def test_raw_riky_regeneration_matches_committed_artifact() -> None:
    regenerated = event_study.serialize_results(
        event_study.build_riky_results(event_study.build_riky_panel())
    )
    assert regenerated == event_study.RIKY_OUT.read_bytes()
