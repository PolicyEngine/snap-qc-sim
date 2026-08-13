"""Fast contract and optional raw-data tests for the event study."""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from analysis import event_study


def _fixture_panel() -> pd.DataFrame:
    rows = []
    states = ["AL", "CA", "GA", "OR", "TX"]
    for state_index, state in enumerate(states):
        for year in event_study.YEARS:
            trend = year - 2017
            treatment_shift = 2.0 if state == "OR" and year >= 2022 else 0.0
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


def test_result_schema_and_paths() -> None:
    result = event_study.build_results(_fixture_panel())
    assert result["schema"] == "snap_qc_sim.event_study.v1"
    assert result["scope"]["primary_treated_state"] == "OR"
    assert result["scope"]["donor_pool"] == ["AL", "CA", "TX"]
    assert set(result["specifications"]) == set(event_study.SPECIFICATIONS)
    assert set(result["permutation_inference"]) == set(event_study.OUTCOMES)
    for outcome in event_study.OUTCOMES:
        path = result["specifications"]["primary_drop_fy2021"]["outcomes"][outcome][
            "path"
        ]
        assert len(path) == 8
        assert [row["event_time"] for row in path] == list(range(-4, 4))


def test_verdict_follows_frozen_rule() -> None:
    decision = event_study.build_results(_fixture_panel())["decision"]
    expected = (
        "signal"
        if decision["strict_p_value"] < 0.10
        and decision["client_placebo_p_value"] >= 0.10
        else "no_protocol_defined_signal"
    )
    assert decision["verdict"] == expected
    assert decision["adoption_gate"] is False


def test_fixture_is_byte_deterministic() -> None:
    first = event_study.serialize_results(event_study.build_results(_fixture_panel()))
    second = event_study.serialize_results(event_study.build_results(_fixture_panel()))
    assert first == second
    assert (
        hashlib.sha256(first).hexdigest()
        == "34b9a386255826595511636a08bc140427b173379dc0a99af3e45beeb1d534ff"
    )


def test_committed_result_schema_and_sha() -> None:
    raw = event_study.OUT.read_bytes()
    result = json.loads(raw)
    assert result["schema"] == "snap_qc_sim.event_study.v1"
    assert result["decision"]["verdict"] == "no_protocol_defined_signal"
    assert (
        hashlib.sha256(raw).hexdigest()
        == "2ad9107b6633ffb55e969d07c11f5b7602e857d4b691e0e9498d4c82debcc37f"
    )


@pytest.mark.skipif(
    not event_study.raw_inputs_available(), reason="audited raw SAV cache unavailable"
)
def test_raw_sav_regeneration_matches_committed_artifact() -> None:
    regenerated = event_study.serialize_results(
        event_study.build_results(event_study.build_panel())
    )
    assert regenerated == event_study.OUT.read_bytes()
