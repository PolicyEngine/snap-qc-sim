"""Tests for the deterministic Colorado SMD counterfactual join."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analysis import counterfactual_join, train_error_model

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "analysis" / "counterfactual_co_smd.json"
DOCUMENT = REPO_ROOT / "analysis" / "COUNTERFACTUAL.md"


def test_smd_off_flips_only_the_existing_documentation_predicate():
    """The counterfactual uses the exact gate and E/D predicate from training."""
    index = pd.Index(["gate-and-ed", "gate-only", "ed-only", "second-target"])
    above_floor = pd.Series([1, 1, 0, 1], index=index)
    elderly_disabled = pd.Series([1, 0, 1, 1], index=index)
    smd_applies = pd.Series([True, True, True, True], index=index)

    baseline_required = train_error_model.medical_documentation_required(
        above_floor,
        elderly_disabled,
        smd_applies,
    )
    counterfactual_required = train_error_model.medical_documentation_required(
        above_floor,
        elderly_disabled,
        pd.Series(False, index=index),
    )

    assert baseline_required.tolist() == [0, 0, 0, 0]
    assert counterfactual_required.tolist() == [1, 0, 0, 1]


def test_counterfactual_reprices_all_engine_computable_features():
    """Engine deltas update every corresponding model feature from the QC anchor."""
    index = pd.Index(["changed", "unchanged"])
    raw = pd.DataFrame(
        {
            "FSBEN": [100.0, 23.0],
            "BENMAX": [100.0, 291.0],
            "MINIMUM_BEN": [23.0, 23.0],
            "FSMEDDED": [165.0, 0.0],
            "FSDEPDED": [10.0, 0.0],
            "FSCSDED": [0.0, 0.0],
            "FSSLTDED": [0.0, 0.0],
            "FSERNDED": [0.0, 0.0],
            "FSNETINC": [50.0, 0.0],
            "FSGRINC": [100.0, 0.0],
            "CERTHHSZ": [2.0, 1.0],
            "FSUSIZE": [2.0, 1.0],
        },
        index=index,
    )
    baseline = pd.DataFrame(
        {
            "medical_expense_above_floor": [1, 0],
            "elderly_or_disabled": [1, 1],
            "med_doc_required": [0, 0],
            "formula_benefit": [100.0, 23.0],
            "formula_benefit_missing": [0, 0],
            "benefit_position_missing": [0, 0],
            "at_max": [1, 0],
            "at_min": [0, 1],
            "ben_rel_max": [1.0, 23 / 291],
            "deduction_count": [2, 0],
            "deduction_components_missing": [0, 0],
            "deductions_per_member": [87.5, 0.0],
            "deductions_missing": [0, 0],
            "net_share_of_gross": [0.5, float("nan")],
            "net_share_undefined": [0, 1],
        },
        index=index,
    )
    engine_deltas = pd.DataFrame(
        {
            "benefit_delta": [-10.0, 0.0],
            "medical_deduction_delta": [-100.0, 0.0],
            "shelter_deduction_delta": [20.0, 0.0],
            "net_income_delta": [20.0, 0.0],
        },
        index=index,
    )

    result = counterfactual_join.apply_smd_off_features(
        raw,
        baseline,
        engine_deltas,
    )

    assert result["med_doc_required"].tolist() == [1, 0]
    assert result["formula_benefit"].tolist() == [90.0, 23.0]
    assert result["at_max"].tolist() == [0, 0]
    assert result["at_min"].tolist() == [0, 1]
    assert result["ben_rel_max"].tolist() == [0.9, 23 / 291]
    assert result["deduction_count"].tolist() == [3, 0]
    assert result["deductions_per_member"].tolist() == [47.5, 0.0]
    assert result["net_share_of_gross"].iloc[0] == 0.7
    assert result["net_share_undefined"].tolist() == [0, 1]


def test_committed_counterfactual_artifact_schema():
    """The checked-in artifact carries every scenario and honesty disclosure."""
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    counterfactual_join.validate_artifact(payload)

    assert payload["schema"] == "snap_qc_sim.counterfactual_co_smd.v1"
    assert list(payload["scenarios"]) == ["floor", "point", "ceiling"]
    assert payload["interpretation"]["causal"] is False
    assert payload["uncertainty"]["conditional_on_fitted_models"] is True
    assert len(payload["provenance"]["round_1b_input_sha256"]) == 9


def test_counterfactual_serialization_is_deterministic(tmp_path):
    """Repeated output writes match each other and the committed artifacts."""
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    first_json = tmp_path / "first.json"
    first_document = tmp_path / "first.md"
    second_json = tmp_path / "second.json"
    second_document = tmp_path / "second.md"

    counterfactual_join.write_outputs(payload, first_json, first_document)
    counterfactual_join.write_outputs(payload, second_json, second_document)

    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_document.read_bytes() == second_document.read_bytes()
    assert first_json.read_bytes() == ARTIFACT.read_bytes()
    assert first_document.read_bytes() == DOCUMENT.read_bytes()
