"""Locks for the prospective FY2025 frozen-pipeline harness."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from analysis import fy2025_confirmation as confirmation

RAW_FY2024 = Path.home() / ".cache/axiom-oracles/snap_qc_repo/qc_data/qc_pub_fy2024.sav"


def _analysis_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("analysis"):
                module = node.module.split(".")[-1]
                imports.add(f"analysis/{module}.py")
            elif node.level and node.module:
                imports.add(f"analysis/{node.module}.py")
    return imports


def test_manifest_hashes_complete_analysis_import_closure() -> None:
    manifest = json.loads(confirmation.MANIFEST_PATH.read_text(encoding="utf-8"))
    frozen = set(manifest["frozen_modules_sha256"])
    discovered = {
        "analysis/train_error_model.py",
        "analysis/hurdle_deviation_model.py",
        "analysis/distributional_deviation_model.py",
    }
    pending = list(discovered)
    while pending:
        module = pending.pop()
        for imported in _analysis_imports(confirmation.ROOT / module):
            if (confirmation.ROOT / imported).is_file() and imported not in discovered:
                discovered.add(imported)
                pending.append(imported)
    assert frozen == discovered


def test_manifest_and_result_schema_locks() -> None:
    manifest = json.loads(confirmation.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert set(manifest) == {
        "feature_registry_sha256",
        "freeze_name",
        "frozen_modules_sha256",
        "fy2024_reference_values",
        "fy2025_schema",
        "input_files",
        "metric_definitions",
        "model_hyperparameters",
        "schema_version",
        "train_years",
    }
    assert manifest["schema_version"] == 1
    assert manifest["fy2025_schema"] == {
        "person_self_employment_slots": 18,
        "smd_and_bbce_policy": "carry forward frozen FY2024 registry cells",
        "threshold_dollars": 57,
    }
    references = manifest["fy2024_reference_values"]
    assert set(references) == {
        "classifier",
        "coverage_gaps_pp",
        "factored_equal_state_dollar_rate_mae_pp",
        "hurdle",
        "sign_roc_auc",
    }
    assert len(references["coverage_gaps_pp"]) == 9


def test_drift_refusal_lists_tampered_module(tmp_path: Path) -> None:
    manifest = json.loads(confirmation.MANIFEST_PATH.read_text(encoding="utf-8"))
    relative = "analysis/train_error_model.py"
    manifest["frozen_modules_sha256"] = {
        relative: manifest["frozen_modules_sha256"][relative]
    }
    target = tmp_path / relative
    target.parent.mkdir()
    target.write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(confirmation.FreezeDriftError, match=relative):
        confirmation.verify_freeze(manifest, root=tmp_path)


@pytest.mark.skipif(not RAW_FY2024.is_file(), reason="raw FY2024 QC file unavailable")
def test_dry_run_agrees_byte_for_byte(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(confirmation.MANIFEST_PATH.read_bytes())
    confirmation.dry_run(
        RAW_FY2024,
        manifest_path=manifest_path,
        results_path=tmp_path / "dry-run.json",
    )
