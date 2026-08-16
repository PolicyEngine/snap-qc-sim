"""Fast contracts for the rung-3 Colorado deduction-composition artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from analysis.rung3 import cluster1_imputation as cluster1

MODEL = Path("analysis/rung3/cluster1_models.json")
FRAME = Path("analysis/rung3/cluster1_co_frame.parquet")


def _fixture() -> pd.DataFrame:
    """Tiny joint-outcome fixture covering both structural-medical domains.

    This fixture tests scientific determinism by value, not model JSON bytes:
    JSON float rendering and dictionary serialization are not the contract.
    Its donors deliberately pair claim indicators with positive amounts so a
    regression to independent sampling is visible as an invariant failure.
    """
    rows = []
    for index in range(12):
        medical_domain = index >= 6
        positive = index % 3 == 0
        rows.append(
            {
                "unit_id": f"fixture-{index}",
                "weight": float(index + 1),
                "household_size": 1 + index % 4,
                "earned_income": float(index * 100),
                "unearned_income": float(index * 20),
                "gross_income": float(index * 120),
                "has_elderly_or_disabled": medical_domain,
                "has_children": index % 2 == 0,
                "rent": float((index % 4) * 400),
                "utility_treatment": 2 if positive else 4,
                "utility_claims_actual_expenses": positive,
                "utility_allowance": 100.0 if positive else 560.0,
                "medical_deduction_claimed": medical_domain and positive,
                "medical_expense_above_floor": (
                    165.0 if medical_domain and positive else 0.0
                ),
                "dependent_care_deduction_claimed": positive,
                "dependent_care_deduction": 75.0 if positive else 0.0,
                "child_support_deduction_claimed": positive,
                "child_support_deduction": 50.0 if positive else 0.0,
                "homeless_deduction_claimed": False,
            }
        )
    return pd.DataFrame(rows)


def test_small_seeded_refit_is_value_deterministic() -> None:
    fixture = _fixture()
    first = cluster1.apply_hot_deck(cluster1.fit_hot_deck(fixture, seed=19), fixture)
    second = cluster1.apply_hot_deck(cluster1.fit_hot_deck(fixture, seed=19), fixture)
    pd.testing.assert_frame_equal(first, second)
    assert not first.loc[
        ~first["has_elderly_or_disabled"], "medical_deduction_claimed"
    ].any()
    for claimed, amount in [
        ("medical_deduction_claimed", "medical_expense_above_floor"),
        ("dependent_care_deduction_claimed", "dependent_care_deduction"),
        ("child_support_deduction_claimed", "child_support_deduction"),
    ]:
        assert first[claimed].eq(first[amount].gt(0)).all()


def test_model_schema_and_recorded_application_bands() -> None:
    model = json.loads(MODEL.read_text())
    assert model["schema"] == "snap_qc_sim.cluster1_model.v1"
    assert model["training"]["case_count"] == 856
    assert model["application"]["unit_count"] == 1281
    assert model["artifacts"]["dense_to_sparse_join"]["matched_dense_units"] == 1281
    for column, rate in model["application"]["frame_claim_rates"].items():
        lower, upper = model["application"]["artifact_test_bands"][column]
        assert lower <= rate <= upper


def test_frame_schema_and_claim_rates() -> None:
    pytest.importorskip("pyarrow")
    frame = pd.read_parquet(FRAME)
    required = {
        "spm_unit_id",
        "takes_up_snap_if_eligible",
        "utility_treatment",
        "utility_allowance",
        "utility_claims_actual_expenses",
        "medical_deduction_claimed",
        "medical_expense_above_floor",
        "dependent_care_deduction",
        "child_support_deduction",
        "homeless_deduction_claimed",
        "source_frame_sha256",
        "qc_source_sha256",
        "imputation_model_schema",
    }
    assert required <= set(frame)
    assert len(frame) == 1281
    model = json.loads(MODEL.read_text())
    for column, (lower, upper) in model["application"]["artifact_test_bands"].items():
        rate = float((frame[column] * frame["weight"]).sum() / frame["weight"].sum())
        assert lower <= rate <= upper
