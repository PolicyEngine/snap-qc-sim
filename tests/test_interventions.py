"""Locks for procedural-intervention accounting scenarios."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis import event_study, interventions, model_capture, persistence
from snap_qc_sim.simulate import targeted_error

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "analysis" / "interventions_results.json"


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text())


def test_targeted_error_is_pure_and_bounded() -> None:
    assert targeted_error(100, 1, 0.25) == 75
    assert targeted_error(100, 0, 0.50) == 100
    assert targeted_error(100, 0.5, 0.50) == 75
    with pytest.raises(ValueError):
        targeted_error(100, 1.1, 0.5)


def test_schema_and_grid(artifact) -> None:
    assert artifact["schema_version"] == 1
    assert artifact["cost_share_unit"] == "percent of issuance"
    grid = artifact["scenario_grid"]
    assert len(grid) == 4 * 3 * 2
    assert {
        (x["ranking_rule"], x["coverage_pct"], x["effectiveness_pct"]) for x in grid
    } == {
        (rule, coverage, effectiveness)
        for rule in interventions.RANKING_RULES
        for coverage in interventions.COVERAGE_PCT
        for effectiveness in interventions.EFFECTIVENESS_PCT
    }


def test_state_cells_and_tier_probabilities(artifact) -> None:
    expected_states = {
        row["state"]
        for row in json.loads(persistence.MOVEMENT_PATH.read_text())["states"]
    }
    for scenario in artifact["scenario_grid"]:
        assert set(scenario["states"]) == expected_states
        for state, result in scenario["states"].items():
            assert result["weighted_coverage_pct"] == pytest.approx(
                scenario["coverage_pct"], abs=1e-7
            )
            single = result["single_measurement"]
            assert single["mean_rate"] >= 0
            assert sum(single["p_tier"].values()) == pytest.approx(1, abs=5e-4)
            assert 0 <= single["expected_share_pct"] <= 15
            sustained = result["sustained_intervention_fy2028_30"]
            assert set(sustained) == {"2028", "2029", "2030"}
            for year, cell in sustained.items():
                assert sum(cell["p_tier"].values()) == pytest.approx(1, abs=5e-3), (
                    state,
                    year,
                )
                assert 0 <= cell["expected_share_pct"] <= 15


def test_live_input_hash_guards(artifact) -> None:
    hashes = artifact["input_hashes"]
    persistence_results = ROOT / "analysis" / "persistence_results.json"
    assert (
        hashes["coding_consistency"]
        == hashlib.sha256(event_study.AUDIT_PATH.read_bytes()).hexdigest()
    )
    assert (
        hashes["fy2025_movement"]
        == hashlib.sha256(persistence.MOVEMENT_PATH.read_bytes()).hexdigest()
    )
    assert (
        hashes["persistence_results"]
        == hashlib.sha256(persistence_results.read_bytes()).hexdigest()
    )
    assert (
        hashes["model_capture_results"]
        == hashlib.sha256(model_capture.OUT.read_bytes()).hexdigest()
    )


def test_memo_is_generated_from_artifact(artifact) -> None:
    assert (ROOT / "analysis" / "INTERVENTIONS.md").read_text() == interventions._memo(
        artifact
    )


@pytest.mark.skipif(
    not interventions.raw_inputs_available(),
    reason="complete model and persistence raw caches unavailable",
)
def test_raw_regeneration_matches_committed_artifact(
    artifact, assert_artifact_values_match
) -> None:
    fresh = json.loads(json.dumps(interventions.compute_artifact(), sort_keys=True))
    committed = json.loads(json.dumps(artifact, sort_keys=True))
    assert_artifact_values_match(fresh, committed, path="interventions")


def test_issuance_dollars_are_consistent(artifact) -> None:
    """Dollar fields equal share times the hash-guarded issuance file."""
    import hashlib as _hashlib

    issuance = json.loads((ROOT / "analysis" / "issuance_fy2024.json").read_text())
    live = _hashlib.sha256(
        (ROOT / "analysis" / "issuance_fy2024.json").read_bytes()
    ).hexdigest()
    assert artifact["input_hashes"]["issuance_fy2024"] == live
    assert artifact["issuance_source"]["sha256"] == issuance["source"]["sha256"]
    checked = 0
    for scenario in artifact["scenario_grid"]:
        for state, result in scenario["states"].items():
            dollars = issuance["states"].get(state)
            if dollars is None:
                assert "issuance_fy2024_dollars" not in result
                continue
            assert result["issuance_fy2024_dollars"] == dollars
            single = result["single_measurement"]
            assert single["expected_cost_share_dollars"] == round(
                single["expected_share_pct"] / 100 * dollars
            )
            implied = round(
                sum(
                    year["expected_share_pct"] / 100 * dollars
                    for year in result["sustained_intervention_fy2028_30"].values()
                )
            )
            assert result["sustained_expected_cost_share_dollars_3yr"] == implied
            checked += 1
    assert checked > 0


def test_disclosures_present(artifact) -> None:
    assert "not modeled" in artifact["delay_clause_not_modeled"]
    assert "official nominal threshold" in artifact["threshold_convention"]
    assert "unverified" in artifact["issuance_source"]["caveat"]
