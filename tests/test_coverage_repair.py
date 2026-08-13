"""Locks for the committed coverage-repair experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis import coverage_repair as repair

RESULT_PATH = Path(repair.__file__).with_name("coverage_repair_results.json")
COMMITTED_SHA256 = "e784971f37d4e229c5a6f60fc8c88b53ac35e37ec5758febaae6422790d85893"
RAW_SOURCES = [
    *(
        repair.QC_DIR / f"qc_pub_fy{year}.sav"
        for year in (*repair.TRAINING_YEARS, 2024)
    ),
    repair.SMD_PATH,
    repair.BBCE_PATH,
    repair.MEDICARE_PART_B_PATH,
]


def _result() -> dict:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def test_committed_artifact_schema_and_sha_are_locked():
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
    assert payload["determinism"]["exact_match"] is True
    assert len(set(payload["determinism"]["canonical_core_sha256_by_repetition"])) == 1
    assert hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest() == COMMITTED_SHA256


def test_artifact_has_every_state_and_level_for_every_candidate():
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
            assert [row["quantile"] for row in rows] == pytest.approx(
                repair.QUANTILE_LEVELS
            )


def test_verdict_follows_embedded_rule_and_winner_satisfies_guards():
    payload = _result()

    assert payload["verdict"] == repair.derive_verdict(payload)
    winner = payload["verdict"]["selected_mechanism"]
    assert winner is not None
    guards = payload["mechanisms"][winner]["guards"]
    assert guards["mae_within_plus_0_05pp"] is True
    assert guards["sign_auc_unchanged"] is True
    assert guards["factored_equal_state_dollar_rate_mae_pp"] <= (
        repair.BASELINE_MAE_PP + repair.MAE_GUARD_ALLOWANCE_PP
    )
    improvement = (
        payload["baseline"]["coverage"]["mean_absolute_gap_pp"]
        - payload["mechanisms"][winner]["coverage"]["mean_absolute_gap_pp"]
    )
    assert improvement >= repair.MATERIAL_IMPROVEMENT_PP


def test_repairs_leave_sign_auc_exactly_unchanged():
    payload = _result()

    for candidate in payload["mechanisms"].values():
        assert candidate["guards"]["sign_auc_raw"] == repair.BASELINE_SIGN_AUC_RAW
        assert (
            candidate["guards"]["sign_auc_calibrated"]
            == repair.BASELINE_SIGN_AUC_CALIBRATED
        )


@pytest.mark.parametrize(
    ("primary", "mae_ok", "auc_ok", "expected"),
    [
        (1.0, True, True, "conformal_remap"),
        (4.5, True, True, None),
        (1.0, False, True, None),
        (1.0, True, False, None),
    ],
)
def test_derive_verdict_enforces_materiality_and_guards(
    primary, mae_ok, auc_ok, expected
):
    payload = {
        "baseline": {"coverage": {"mean_absolute_gap_pp": 4.7}},
        "mechanisms": {},
    }
    for index, name in enumerate(repair.MECHANISMS):
        payload["mechanisms"][name] = {
            "coverage": {"mean_absolute_gap_pp": primary + index},
            "guards": {
                "mae_within_plus_0_05pp": mae_ok,
                "sign_auc_unchanged": auc_ok,
            },
        }

    assert repair.derive_verdict(payload)["selected_mechanism"] == expected


@pytest.mark.skipif(
    not all(path.is_file() for path in RAW_SOURCES),
    reason="private SNAP QC raw sources are unavailable",
)
def test_raw_source_regeneration_matches_committed_artifact():
    regenerated = repair.run_experiment(repetitions=2)

    assert regenerated == _result()
