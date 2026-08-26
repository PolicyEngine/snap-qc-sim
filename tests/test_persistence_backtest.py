"""Lock the distributional-backtest artifact and its regeneration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis import event_study, persistence, persistence_backtest

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "analysis" / "persistence_backtest_results.json"


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text())


def test_summary_domains_and_ordering(artifact) -> None:
    s = artifact["summary"]
    assert set(s) == set(persistence_backtest.APPROACHES)
    for row in s.values():
        assert row["n_state_years"] > 300
        assert 0.0 <= row["coverage_50"] <= row["coverage_90"] <= 1.0
        assert row["mean_crps"] > 0 and row["mean_pinball"] > 0
        assert row["mean_predictive_sd_pp"] > 0
    assert s["widened"]["mean_predictive_sd_pp"] > s["static"]["mean_predictive_sd_pp"]
    assert s["rao_yu"]["coverage_90"] >= s["static"]["coverage_90"]


def test_per_year_winners_consistent(artifact) -> None:
    for year, row in artifact["per_year_mean_crps"].items():
        vals = {k: row[k] for k in persistence_backtest.APPROACHES}
        assert row["winner"] == min(vals, key=vals.get), year


def test_input_hashes_match_live_files(artifact) -> None:
    hashes = artifact["input_hashes"]
    audit = hashlib.sha256(event_study.AUDIT_PATH.read_bytes()).hexdigest()
    assert hashes["coding_consistency"] == audit
    audit_years = json.loads(event_study.AUDIT_PATH.read_text())["years"]
    assert hashes["raw_by_fiscal_year"] == {
        str(y): audit_years[str(y)]["source"]["sha256"] for y in persistence.YEARS_USED
    }


def test_penalty_translation_is_internally_consistent(artifact) -> None:
    pt = artifact["penalty_translation"]
    assert pt["innovation_variance_pp2"] > 0
    for code, row in pt["states"].items():
        for name in ("static", "widened"):
            cell = row[name]
            p29 = cell["fy2029"]["p_bucket"]
            assert sum(p29.values()) == pytest.approx(1.0, abs=5e-3), code
            assert cell["fy2029"]["modal_bucket_probability"] == pytest.approx(
                max(p29.values()), abs=1e-6
            )
            for year in ("fy2028", "fy2029"):
                assert cell[year]["sd_bill_dollars"] >= 0
        assert row["widened"]["predictive_sd_pp"] > row["static"]["predictive_sd_pp"], (
            code
        )
    m = pt["median_modal_bucket_probability_fy2029"]
    assert m["widened"] <= m["static"]
    for name in ("static", "widened"):
        for year in ("fy2028", "fy2029"):
            nat = pt["national"][name][year]
            assert nat["expected_total_dollars"] >= 0
            assert nat["sd_total_dollars_no_correlation"] > 0


def test_statutory_fy2028_semantics(artifact) -> None:
    """A state whose locked FY2025 crosses the delay test owes exactly zero
    in FY2028 with zero variance under every construction (7 USC
    2013(a)(2)(B); the Illinois case from the sol review)."""
    pt = artifact["penalty_translation"]
    checked = 0
    for code, row in pt["states"].items():
        if not row["fy2025_delay"]:
            continue
        for name in ("static", "widened"):
            assert row[name]["fy2028"]["expected_bill_dollars"] == 0, code
            assert row[name]["fy2028"]["sd_bill_dollars"] == 0, code
        checked += 1
    assert checked >= 1
    assert pt["states"]["IL"]["fy2025_delay"] is True


def test_sensitivity_rows_present_and_ordered(artifact) -> None:
    sens = artifact["sensitivity_official_se_scale"]
    assert set(sens) == set(persistence_backtest.SENSITIVITY)
    s = artifact["summary"]
    assert (
        s["static"]["mean_predictive_sd_pp"]
        < s["static_fair"]["mean_predictive_sd_pp"]
        < sens["static_fair_official_1p1"]["mean_predictive_sd_pp"]
    )
    for row in sens.values():
        assert 0.0 <= row["coverage_50"] <= row["coverage_90"] <= 1.0


def test_penalty_hashes_match_live_files(artifact) -> None:
    hashes = artifact["input_hashes"]
    for key, path in (
        ("fy2025_movement", "fy2025_movement.json"),
        ("issuance_fy2024", "issuance_fy2024.json"),
        ("persistence_results", "persistence_results.json"),
    ):
        live = hashlib.sha256((ROOT / "analysis" / path).read_bytes()).hexdigest()
        assert hashes[key] == live, key


def test_memo_is_generated_from_the_artifact(artifact) -> None:
    memo = (ROOT / "analysis" / "PERSISTENCE_BACKTEST.md").read_text()
    assert memo == persistence_backtest._memo(artifact)


@pytest.mark.skipif(
    not persistence_backtest.raw_inputs_available(),
    reason="complete hash-audited mixed-format cache unavailable",
)
def test_raw_regeneration_matches_committed_artifact(
    artifact, assert_artifact_values_match
) -> None:
    regenerated = persistence_backtest.compute_artifact()
    committed = {k: v for k, v in artifact.items() if k != "environment"}
    fresh = {k: v for k, v in regenerated.items() if k != "environment"}
    fresh = json.loads(json.dumps(fresh, sort_keys=True))
    committed = json.loads(json.dumps(committed, sort_keys=True))
    assert_artifact_values_match(fresh, committed, path="persistence_backtest")
