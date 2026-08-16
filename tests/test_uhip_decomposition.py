"""Fast locks and optional raw regeneration for the UHIP decomposition.

Optimizer output is tested for same-process determinism and numeric tolerance,
never with a cross-platform fixture byte hash. Raw regeneration is value-locked
at rel=1e-9, following the event-study artifact contract and #62 pattern.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from analysis import event_study, uhip_decomposition


def _fixture_panel() -> pd.DataFrame:
    rows = []
    states = ["AL", "CA", "FL", "GA", "KY", "NM", "OR", "RI", "TX"]
    for state_index, state in enumerate(states):
        for year in event_study.RIKY_YEARS:
            trend = year - 2012
            shift = 2.0 if state == "RI" and year >= 2017 else 0.0
            row = {"state": state, "year": year}
            for outcome_index, outcome in enumerate(uhip_decomposition.FIT_OUTCOMES):
                row[outcome] = 1.0 + state_index * 0.2 + trend * 0.1
                if outcome == "mass_change":
                    row[outcome] += shift
                elif outcome == "defect_or_mass_change":
                    row[outcome] += 0.75 * shift
            rows.append(row)
    return pd.DataFrame(rows)


def test_fixture_determinism_and_planted_effect_tolerance() -> None:
    first = uhip_decomposition.serialize_results(
        uhip_decomposition.build_results(_fixture_panel())
    )
    second = uhip_decomposition.serialize_results(
        uhip_decomposition.build_results(_fixture_panel())
    )
    assert first == second
    result = json.loads(first)
    assert result["inferential_channels"]["mass_change"]["effect"] == pytest.approx(
        2.0, abs=0.05
    )
    assert result["inferential_channels"]["defect_or_mass_change"][
        "effect"
    ] == pytest.approx(1.5, abs=0.05)


def test_committed_artifact_contract_and_protocol_pin() -> None:
    raw = uhip_decomposition.OUT.read_bytes()
    result = json.loads(raw)
    assert result["schema"] == uhip_decomposition.SCHEMA
    assert result["schema_version"] == 1
    assert result["protocol_sha256"] == uhip_decomposition.PROTOCOL_SHA256
    assert hashlib.sha256(
        uhip_decomposition.PROTOCOL_PATH.read_bytes()
    ).hexdigest() == (uhip_decomposition.PROTOCOL_SHA256)
    assert set(result["scope"]["inferential_channels"]) == {
        "mass_change",
        "disregard",
        "defect_or_mass_change",
    }
    assert set(result["scope"]["descriptive_channels"]) == {
        "defect",
        "arithmetic",
        "user",
        "entry",
        "recert",
    }
    assert set(result["inferential_channels"]) == set(
        result["scope"]["inferential_channels"]
    )
    assert set(result["descriptive_channels"]) == set(
        result["scope"]["descriptive_channels"]
    )
    assert all(
        "p_value" not in channel and "verdict" not in channel
        for channel in result["descriptive_channels"].values()
    )


def test_verdicts_and_overlap_identity() -> None:
    result = json.loads(uhip_decomposition.OUT.read_bytes())
    client_p = result["client_placebo"]["p_value"]
    for channel in result["inferential_channels"].values():
        expected = (
            "signal"
            if channel["p_value"] < 0.10 and client_p >= 0.10
            else "no_protocol_defined_signal"
        )
        family = (
            "signal_family_adjusted"
            if channel["p_value"] < 0.10 / 3
            else "no_family_adjusted_signal"
        )
        assert channel["verdict"] == expected
        assert channel["verdict_family_adjusted"] == family
        assert channel["profile"]["changes_verdict"] is False
    for year in result["overlap_accounting"]:
        assert year["sum_channel_dollars"] == pytest.approx(
            year["strict_outcome_dollars"] + year["duplicate_credit_dollars"],
            rel=1e-12,
            abs=1e-8,
        )


def test_serializer_reproduces_committed_bytes() -> None:
    raw = uhip_decomposition.OUT.read_bytes()
    assert uhip_decomposition.serialize_results(json.loads(raw)) == raw


@pytest.mark.skipif(
    not uhip_decomposition.raw_inputs_available(),
    reason="complete hash-audited mixed-format cache unavailable",
)
def test_raw_regeneration_matches_committed_artifact(
    assert_artifact_values_match,
) -> None:
    panel, descriptive = uhip_decomposition.build_panel()
    regenerated = json.loads(
        uhip_decomposition.serialize_results(
            uhip_decomposition.build_results(panel, descriptive)
        )
    )
    assert_artifact_values_match(
        regenerated, json.loads(uhip_decomposition.OUT.read_bytes())
    )
