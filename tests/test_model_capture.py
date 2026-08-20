"""Locks for the out-of-sample FY2024 model capture artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis import model_capture, train_error_model

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "analysis" / "model_capture_results.json"


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text())


def test_schema_and_out_of_sample_provenance(artifact) -> None:
    assert artifact["schema_version"] == 1
    assert artifact["coverage_pct"] == list(model_capture.COVERAGE_PCT)
    provenance = artifact["provenance"]
    assert provenance["evaluation_year"] == train_error_model.YEAR_TEST == 2024
    assert provenance["training_years"] == train_error_model.YEARS_TRAIN
    assert 2024 not in provenance["training_years"]
    assert provenance["out_of_sample_by_construction"] is True


def test_capture_domains_and_ordering(artifact) -> None:
    scopes = {"national": artifact["national"], **artifact["states"]}
    exceptions = []
    for scope, curve in scopes.items():
        for pct, cell in curve.items():
            for key in ("model", "oracle", "random_expectation", "random_seeded_draw"):
                assert 0 <= cell[key] <= 1, (scope, pct, key)
            assert cell["oracle"] >= cell["model"], (scope, pct)
            if cell["model"] < cell["random_expectation"]:
                exceptions.append((scope, int(pct)))
    assert all(
        cell["model"] >= cell["random_expectation"]
        for cell in artifact["national"].values()
    )
    # Sparse state samples do not guarantee realized model capture above an
    # expectation. Lock the observed exceptions instead of rewriting data.
    assert exceptions == [
        ("AK", 1),
        ("GU", 1),
        ("GU", 2),
        ("MT", 1),
        ("SD", 1),
        ("VT", 1),
        ("VT", 2),
        ("WY", 1),
        ("WY", 2),
    ]


def test_auc_lock(artifact) -> None:
    check = artifact["roc_auc_cross_check"]
    assert check["recomputed"] == pytest.approx(check["committed"], abs=5e-12)
    assert check["recomputed"] == pytest.approx(0.7666, abs=5e-5)


def test_live_input_hashes(artifact) -> None:
    hashes = artifact["input_hashes"]
    model_results = ROOT / "analysis" / "model_results.json"
    training_script = ROOT / "analysis" / "train_error_model.py"
    assert (
        hashes["model_results"]
        == hashlib.sha256(model_results.read_bytes()).hexdigest()
    )
    assert (
        hashes["train_error_model"]
        == hashlib.sha256(training_script.read_bytes()).hexdigest()
    )
    assert hashes["inputs"] == train_error_model._provenance()["input_sha256"]


@pytest.mark.skipif(
    not model_capture.raw_inputs_available(),
    reason="complete FY2017-24 SAV cache unavailable",
)
def test_raw_regeneration_matches_committed_artifact(
    artifact, assert_artifact_values_match
) -> None:
    fresh = json.loads(json.dumps(model_capture.compute_artifact(), sort_keys=True))
    committed = json.loads(json.dumps(artifact, sort_keys=True))
    assert_artifact_values_match(fresh, committed, path="model_capture")
