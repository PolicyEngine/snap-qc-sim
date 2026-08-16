"""Fast artifact locks for the rung-3 Colorado prototype."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

pytest.importorskip("pandas")

RESULT = Path("analysis/rung3/prototype_results.json")


def test_prototype_schema_and_reconciliation_fields() -> None:
    result = json.loads(RESULT.read_text())
    assert result["schema"] == "snap_qc_sim.rung3_prototype.v1"
    assert (
        result["eligibility"]["baseline_units"]
        <= result["eligibility"]["flag_only_units"]
    )
    for name in ("uncalibrated",):
        assert math.isfinite(result[name]["overpayment_model_target_ratio"])
        assert math.isfinite(result[name]["underpayment_model_target_ratio"])
        assert "caseload" in result[name]
        assert "issuance" in result[name]
    calibration = result["calibration"]
    assert "effective_sample_size" in calibration["diagnostics"]
    assert "max_weight_ratio" in calibration["diagnostics"]
    assert {"caseload", "issuance"} <= calibration["post"].keys()


def test_prototype_disclosures_and_hashes() -> None:
    result = json.loads(RESULT.read_text())
    assert result["error_model"]["coverage_failure_disclosed"] is True
    assert result["task_b"]["causal_claim"] is False
    for artifact in result["inputs"].values():
        assert len(artifact["sha256"]) == 64
