"""Lock the persistence decomposition artifact and its regeneration.

Fast locks always run from the committed JSON. Raw regeneration is
value-locked through the shared conftest comparator and skips when the
hash-audited FY2012-24 cache is absent, matching the event-study tests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis import event_study, persistence

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "analysis" / "persistence_results.json"


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text())


def test_years_follow_the_audit_conventions(artifact) -> None:
    assert artifact["years_used"] == list(persistence.YEARS_USED)
    assert 2021 not in artifact["years_used"]
    assert "2021" in artifact["years_dropped"]


def test_fit_domains(artifact) -> None:
    fit = artifact["fit"]
    assert fit["sigma_alpha_sq_pp2"] >= 0
    assert fit["sigma_u_sq_pp2"] >= 0
    assert -0.5 <= fit["rho"] < 1.0
    share = fit["persistent_share_of_process_variance"]
    if share is not None:
        total = fit["sigma_alpha_sq_pp2"] + fit["sigma_u_sq_pp2"]
        assert 0.0 <= share <= 1.0
        assert share == pytest.approx(fit["sigma_alpha_sq_pp2"] / total, abs=5e-4)


def test_moments_shape(artifact) -> None:
    moments = artifact["moments"]
    assert moments["lags"] == list(range(persistence.MAX_LAG + 1))
    assert len(moments["mean_products_pp2"]) == persistence.MAX_LAG + 1
    assert all(n > 0 for n in moments["pair_counts"])
    assert moments["mean_sampling_variance_pp2"] > 0


def test_reliabilities_are_probabilities(artifact) -> None:
    rel = artifact["single_year_reliability"]
    assert len(rel) == artifact["n_states"]
    assert all(0.0 <= value <= 1.0 for value in rel.values())


def test_validation_reports_all_baselines(artifact) -> None:
    val = artifact["fy2025_validation"]
    assert "not a clean model comparison" in val["semantics"]
    for key in (
        "shrinkage_prediction",
        "naive_fy2024_carryforward",
        "official_fy2024_carryforward",
        "national_mean_only",
    ):
        scores = val[key]
        assert 0.0 <= scores["mae_pp"] <= scores["rmse_pp"], key
        assert -1.0 <= scores["corr"] <= 1.0, key
    assert val["n_states"] == len(val["per_state"])


def test_exposure_cells_are_internally_consistent(artifact) -> None:
    for state, block in artifact["exposure_fy2028_30"].items():
        assert block["sampling_sd_pp"] > 0
        for year, cell in block["years"].items():
            total = sum(cell["p_tier"].values())
            assert total == pytest.approx(1.0, abs=5e-3), (state, year)
            implied = sum(float(share) * prob for share, prob in cell["p_tier"].items())
            assert cell["expected_share_pct"] == pytest.approx(implied, abs=0.02), (
                state,
                year,
            )
            assert cell["mean_rate"] >= 0 and cell["sd_rate"] > 0
            assert 0.0 <= cell["p_clipped_at_zero"] <= 1.0


def test_input_hashes_match_live_files(artifact) -> None:
    """Guards the stale-hash failure mode found in the decomposition tests."""
    hashes = artifact["input_hashes"]
    audit = hashlib.sha256(event_study.AUDIT_PATH.read_bytes()).hexdigest()
    movement = hashlib.sha256(persistence.MOVEMENT_PATH.read_bytes()).hexdigest()
    assert hashes["coding_consistency"] == audit
    assert hashes["fy2025_movement"] == movement
    audit_years = json.loads(event_study.AUDIT_PATH.read_text())["years"]
    assert hashes["raw_by_fiscal_year"] == {
        str(y): audit_years[str(y)]["source"]["sha256"] for y in persistence.YEARS_USED
    }


def test_memo_is_generated_from_the_artifact(artifact) -> None:
    memo = (ROOT / "analysis" / "PERSISTENCE.md").read_text()
    assert memo == persistence._memo(artifact)


@pytest.mark.skipif(
    not persistence.raw_inputs_available(),
    reason="complete hash-audited mixed-format cache unavailable",
)
def test_raw_regeneration_matches_committed_artifact(
    artifact, assert_artifact_values_match
) -> None:
    regenerated = persistence.compute_artifact()
    committed = {k: v for k, v in artifact.items() if k != "environment"}
    fresh = {k: v for k, v in regenerated.items() if k != "environment"}
    # The committed artifact serializes with sort_keys=True; normalize the
    # fresh dict through the same serialization before the strict compare.
    fresh = json.loads(json.dumps(fresh, sort_keys=True))
    committed = json.loads(json.dumps(committed, sort_keys=True))
    assert_artifact_values_match(fresh, committed, path="persistence")
