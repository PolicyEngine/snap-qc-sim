"""Fast integrity locks for the committed rung-3 parity artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULTS = Path(__file__).resolve().parents[1] / "analysis/rung3/parity_results.json"
ROUND2_RESULTS = (
    Path(__file__).resolve().parents[1] / "analysis/rung3/parity_round2_results.json"
)
if not RESULTS.exists():
    pytest.skip("rung-3 parity artifact is not present", allow_module_level=True)

EXPECTED_SCOPE = {
    "AZ": 922,
    "CA": 883,
    "CO": 856,
    "GA": 945,
    "MD": 722,
    "NY": 847,
    "TX": 906,
}


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(RESULTS.read_text())


@pytest.fixture(scope="module")
def round2_artifact() -> dict:
    if not ROUND2_RESULTS.exists():
        pytest.skip("rung-3 round-2 parity artifact is not present")
    return json.loads(ROUND2_RESULTS.read_text())


def test_schema(artifact: dict) -> None:
    assert artifact["schema_version"] == "1.0.0"
    assert set(artifact) >= {
        "environment",
        "input_hashes",
        "comparator_variable",
        "mapping_decisions",
        "states",
    }
    assert artifact["comparator_variable"] == "snap_normal_allotment"
    assert set(artifact["states"]) == set(EXPECTED_SCOPE)


def test_scope_counts_match_replay(artifact: dict) -> None:
    assert {
        state: result["in_scope_n"] for state, result in artifact["states"].items()
    } == EXPECTED_SCOPE


@pytest.mark.parametrize("state", sorted(EXPECTED_SCOPE))
def test_state_arithmetic(artifact: dict, state: str) -> None:
    result = artifact["states"][state]
    total = result["in_scope_n"]
    exact = result["exact_match_n"]
    nonmatch = total - exact
    assert 0 <= exact <= total
    assert result["exact_match_rate"] == pytest.approx(exact / total)
    assert sum(result["divergence_histogram_dollars"].values()) == nonmatch
    assert sum(entry["n"] for entry in result["divergence_causes"]) == nonmatch


def test_round2_schema_and_scope(round2_artifact: dict) -> None:
    assert round2_artifact["schema_version"] == "2.0.0"
    assert set(round2_artifact["modes"]) == {
        "baseline_round1",
        "mapping_fixed_pe_us",
        "admin_rounding",
    }
    for states in round2_artifact["modes"].values():
        assert {state: value["in_scope_n"] for state, value in states.items()} == (
            EXPECTED_SCOPE
        )


def test_round2_locked_parity_counts(round2_artifact: dict) -> None:
    expected = {
        "baseline_round1": 2_872,
        "mapping_fixed_pe_us": 4_403,
        "admin_rounding": 6_081,
    }
    for mode, exact in expected.items():
        assert (
            sum(
                state["exact_match_n"]
                for state in round2_artifact["modes"][mode].values()
            )
            == exact
        )


def test_round2_deduction_decomposition(round2_artifact: dict) -> None:
    assert round2_artifact["deduction_concept_cohort_n"] == 2_393
    assert sum(entry["n"] for entry in round2_artifact["sub_cause_histogram"]) == 2_393
    assert len(round2_artifact["case_localizations"]) == 2_393
    conversions = {
        item["round1_cause"]: item
        for item in round2_artifact["admin_conversion_by_round1_cause"]
    }
    assert conversions["rounding_convention"]["round1_divergent_n"] == 814
    assert conversions["rounding_convention"]["admin_rounding_exact_n"] == 814
    assert conversions["deduction_concept"]["round1_divergent_n"] == 2_393
    assert conversions["deduction_concept"]["admin_rounding_exact_n"] == 2_393
