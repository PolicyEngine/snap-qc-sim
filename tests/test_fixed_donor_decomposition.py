"""Fast locks and optional raw regeneration for the fixed-donor estimator."""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from analysis import event_study, fixed_donor_decomposition, uhip_decomposition


def _fixture_panel() -> pd.DataFrame:
    rows = []
    states = ["AL", "CA", "FL", "GA", "KY", "NM", "OR", "RI", "TX"]
    for state_index, state in enumerate(states):
        for year in event_study.RIKY_YEARS:
            trend = year - 2012
            shift = 2.0 if state == "RI" and year >= 2017 else 0.0
            row = {"state": state, "year": year}
            for outcome_index, outcome in enumerate(event_study.OUTCOMES):
                row[outcome] = 2.0 + state_index * 0.2 + trend * 0.1
            for outcome_index, outcome in enumerate(
                fixed_donor_decomposition.ANALYSIS_OUTCOMES
            ):
                row[outcome] = 1.0 + state_index * 0.2 + trend * 0.1
                if outcome == "mass_change":
                    row[outcome] += shift
                elif outcome == "defect_or_mass_change":
                    row[outcome] += 0.75 * shift
            rows.append(row)
    return pd.DataFrame(rows)


def test_fixture_determinism_and_planted_effect_tolerance() -> None:
    first = fixed_donor_decomposition.serialize_results(
        fixed_donor_decomposition.build_results(_fixture_panel())
    )
    second = fixed_donor_decomposition.serialize_results(
        fixed_donor_decomposition.build_results(_fixture_panel())
    )
    assert first == second
    result = json.loads(first)
    fixed = result["side_by_side"]["fixed_donor"]
    assert fixed["mass_change"]["effect"] == pytest.approx(2.0, abs=0.05)
    assert fixed["defect_or_mass_change"]["effect"] == pytest.approx(1.5, abs=0.05)


def test_committed_artifact_contract_and_protocol_pins() -> None:
    result = json.loads(fixed_donor_decomposition.OUT.read_bytes())
    assert result["schema"] == fixed_donor_decomposition.SCHEMA
    assert result["schema_version"] == 1
    assert result["reproduction_check"]["passed"] is True
    assert result["protocol_sha256"] == fixed_donor_decomposition.PROTOCOL_SHA256
    assert (
        result["decomposition_protocol_sha256"]
        == fixed_donor_decomposition.DECOMPOSITION_PROTOCOL_SHA256
    )
    assert (
        hashlib.sha256(fixed_donor_decomposition.PROTOCOL_PATH.read_bytes()).hexdigest()
        == fixed_donor_decomposition.PROTOCOL_SHA256
    )
    assert (
        hashlib.sha256(
            fixed_donor_decomposition.DECOMPOSITION_PROTOCOL_PATH.read_bytes()
        ).hexdigest()
        == fixed_donor_decomposition.DECOMPOSITION_PROTOCOL_SHA256
    )
    assert set(result["scope"]["inferential_channels"]) == set(
        uhip_decomposition.INFERENTIAL_CHANNELS
    )
    assert set(result["scope"]["descriptive_channels"]) == set(
        uhip_decomposition.DESCRIPTIVE_CHANNELS
    )


def test_reproduction_values_verdicts_and_serializer() -> None:
    raw = fixed_donor_decomposition.OUT.read_bytes()
    result = json.loads(raw)
    observed = result["reproduction_check"]["observed"]
    assert observed["effect"] == pytest.approx(3.9642021849522484, rel=1e-9)
    assert observed["p_value"] == 0.23255813953488372
    assert observed["absolute_rank"] == 10
    assert observed["rank_denominator"] == 43
    client_p = result["client_placebo"]["p_value"]
    for channel in uhip_decomposition.INFERENTIAL_CHANNELS:
        value = result["side_by_side"]["fixed_donor"][channel]
        expected = (
            "signal"
            if value["p_value"] < 0.10 and client_p >= 0.10
            else "no_protocol_defined_signal"
        )
        family = (
            "signal_family_adjusted"
            if value["p_value"] < 0.10 / 3
            else "no_family_adjusted_signal"
        )
        assert value["verdict"] == expected
        assert value["verdict_family_adjusted"] == family
        assert value["profile"]["changes_verdict"] is False
    assert fixed_donor_decomposition.serialize_results(result) == raw


@pytest.mark.skipif(
    not fixed_donor_decomposition.raw_inputs_available(),
    reason="complete hash-audited mixed-format cache unavailable",
)
def test_raw_regeneration_matches_committed_artifact(
    assert_artifact_values_match,
) -> None:
    panel, descriptive = fixed_donor_decomposition.build_panel()
    regenerated = fixed_donor_decomposition.build_results(panel, descriptive)
    assert regenerated["reproduction_check"]["passed"] is True
    assert_artifact_values_match(
        json.loads(fixed_donor_decomposition.serialize_results(regenerated)),
        json.loads(fixed_donor_decomposition.OUT.read_bytes()),
    )
