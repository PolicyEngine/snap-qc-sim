"""Locks for the committed location-repair experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis import location_repair as repair

RESULT_PATH = Path(repair.__file__).with_name("location_repair_results.json")
COMMITTED_SHA256 = "31a055f4be1d0988d74307a9f2a54804fabf49e1f1e40ca90d84681e55b60070"
RAW_SOURCES = [
    *(
        repair.QC_DIR / f"qc_pub_fy{year}.sav"
        for year in (*repair.TRAINING_YEARS, repair.YEAR_TEST)
    ),
    repair.SMD_PATH,
    repair.BBCE_PATH,
    repair.MEDICARE_PART_B_PATH,
]


def _result() -> dict:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def test_committed_artifact_schema_rule_and_sha_are_locked():
    payload = _result()

    assert payload["schema_version"] == 1
    assert set(payload) == {
        "baseline",
        "determinism",
        "mechanisms",
        "protocol",
        "provenance",
        "schema_version",
        "verdict",
    }
    assert set(payload["mechanisms"]) == set(repair.MECHANISMS)
    assert payload["protocol"]["decision_rule"] == repair._decision_rule()
    determinism = payload["determinism"]
    assert determinism["exact_match"] is True
    assert len(set(determinism["canonical_core_sha256_by_repetition"])) == 1
    assert hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest() == COMMITTED_SHA256


def test_artifact_has_every_state_and_level_and_profile_repair_counts():
    payload = _result()
    estimators = {"baseline": payload["baseline"], **payload["mechanisms"]}

    for estimator in estimators.values():
        coverage = estimator["coverage"]
        assert [row["quantile"] for row in coverage["levels"]] == pytest.approx(
            repair.QUANTILE_LEVELS
        )
        assert len(coverage["by_state"]) == 53
        for rows in coverage["by_state"].values():
            assert len(rows) == len(repair.QUANTILE_LEVELS)
    for name, candidate in payload["mechanisms"].items():
        per_level = candidate["guards"]["per_level"]["levels"]
        assert len(per_level) == len(repair.QUANTILE_LEVELS)
        assert [row["quantile"] for row in per_level] == pytest.approx(
            repair.QUANTILE_LEVELS
        )
        counts = candidate["isotonic_repairs"]
        if name == "level_profile":
            assert counts["pooled_oof_rows"] > 0
            assert counts["fy2024_rows"] > 0
        else:
            assert set(counts.values()) == {0}


def test_verdict_follows_rule_and_winner_satisfies_every_guard():
    payload = _result()

    assert payload["verdict"] == repair.derive_verdict(payload)
    winner = payload["verdict"]["selected_mechanism"]
    assert winner is not None
    candidate = payload["mechanisms"][winner]
    assert repair._passes_all_guards(candidate)
    guards = candidate["guards"]
    assert guards["mae_within_plus_0_05pp"] is True
    assert guards["hurdle_probabilities_unchanged"] is True
    assert guards["sign_auc_unchanged"] is True
    assert guards["all_grid_fits_bracketed"] is True
    assert all(
        row["absolute_gap_worsening_within_0_5pp"] and row["no_new_over_3pp_flag"]
        for row in guards["per_level"]["levels"]
    )
    assert guards["per_level"]["q05_at_least_half_baseline"] is True
    improvement = (
        payload["baseline"]["coverage"]["mean_absolute_gap_pp"]
        - candidate["coverage"]["mean_absolute_gap_pp"]
    )
    assert improvement >= repair.MATERIAL_IMPROVEMENT_PP


def _candidate(primary: float, passes: bool = True) -> dict:
    return {
        "coverage": {"mean_absolute_gap_pp": primary},
        "guards": {
            "mae_within_plus_0_05pp": passes,
            "hurdle_probabilities_unchanged": passes,
            "sign_auc_unchanged": passes,
            "all_grid_fits_bracketed": passes,
            "per_level": {
                "all_absolute_gap_worsening_within_0_5pp": passes,
                "no_new_over_3pp_flags": passes,
                "q05_at_least_half_baseline": passes,
            },
        },
    }


@pytest.mark.parametrize(
    ("best_primary", "passes", "expected"),
    [(3.0, True, "global_shift"), (4.6, True, None), (3.0, False, None)],
)
def test_derive_verdict_enforces_materiality_and_all_guards(
    best_primary, passes, expected
):
    payload = {
        "baseline": {"coverage": {"mean_absolute_gap_pp": 4.7}},
        "mechanisms": {
            name: _candidate(best_primary + index, passes)
            for index, name in enumerate(repair.MECHANISMS)
        },
    }

    assert repair.derive_verdict(payload)["selected_mechanism"] == expected


def test_repairs_leave_hurdle_and_sign_metrics_exactly_unchanged():
    payload = _result()

    for candidate in payload["mechanisms"].values():
        guards = candidate["guards"]
        assert guards["hurdle_probabilities_unchanged"] is True
        assert guards["sign_auc_raw"] == repair.BASELINE_SIGN_AUC_RAW
        assert guards["sign_auc_calibrated"] == repair.BASELINE_SIGN_AUC_CALIBRATED


@pytest.mark.skipif(
    not all(path.is_file() for path in RAW_SOURCES),
    reason="private SNAP QC raw sources are unavailable",
)
def test_raw_source_regeneration_matches_committed_artifact():
    assert repair.run_experiment(repetitions=2) == _result()
