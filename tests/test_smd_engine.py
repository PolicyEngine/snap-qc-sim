"""Fast locks for the engine-grounded SMD accounting artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pandas")

from analysis import smd_engine_counterfactual as smd

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "analysis/smd_engine_counterfactual.json"


@pytest.fixture(scope="module")
def payload():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_schema_and_state_scope(payload):
    assert payload["schema"] == "snap_qc_sim.smd_engine_counterfactual.v1"
    assert payload["construction"] == "accounting"
    assert payload["causal"] is False
    assert payload["verified_states"] == ["AZ", "CA", "CO", "GA", "MD", "NY", "TX"]
    assert payload["smd_verified_states"] == ["AZ", "CA", "CO", "GA", "TX"]


def test_case_counts_and_bracket_ordering(payload):
    for state in payload["smd_verified_states"]:
        item = payload["states"][state]
        assert item["claimant_cases"] == len(item["cases"])
        assert item["claimant_cases"] == item["standardized_unrecoverable_cases"] + item["actual_excess_recoverable_cases"]
        for case in item["cases"]:
            assert case["convention_a_delta"] == 0
            assert case["convention_b_delta"] <= case["convention_a_delta"] <= 0
            assert abs(case["convention_a_delta"]) <= abs(case["convention_b_delta"])
        a = item["results"]["convention_a"]
        b = item["results"]["convention_b"]
        assert a["issuance_change_dollars"] == 0
        assert b["issuance_change_dollars"] <= a["issuance_change_dollars"]


def test_non_smd_verified_states_are_reported(payload):
    for state in ("MD", "NY"):
        assert payload["states"][state]["recoverability_verdict"] == "not_computed_no_smd_in_registry"


def test_all_citations_are_nonempty(payload):
    citations = payload["recoverability"]["citations"]
    assert citations
    assert all(smd.citation_fields_nonempty(citation) for citation in citations)
    for state in payload["states"].values():
        assert state["citations"]
        assert all(smd.citation_fields_nonempty(citation) for citation in state["citations"])


def test_disclosures_and_hashes(payload):
    assert payload["data_forced_choices"]
    assert payload["environment"]["runtime_seconds"] > 0
    assert len(payload["input_hashes"]) == 5
    assert all(len(value) == 64 for value in payload["input_hashes"].values())
    assert "Neither is causal" in payload["deployed_model_comparison"]["warning"]
