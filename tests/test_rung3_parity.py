"""Fast integrity locks for the committed rung-3 parity artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("policyengine")

RESULTS = Path(__file__).resolve().parents[1] / "analysis/rung3/parity_results.json"
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
