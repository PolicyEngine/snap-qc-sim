"""Lock the replication-package export to the paper's cited inventory."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_export_module():
    spec = importlib.util.spec_from_file_location(
        "export_replication_package", ROOT / "scripts" / "export_replication_package.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_inventory_files_exist_in_repo() -> None:
    """Every inventoried path must exist — a rename upstream breaks the export."""
    module = _load_export_module()
    missing = [name for name in module.INVENTORY if not (ROOT / name).is_file()]
    assert not missing, missing


def test_export_builds_complete_manifest_and_zip(tmp_path) -> None:
    module = _load_export_module()
    pkg = module.build_package("HEAD", tmp_path)

    manifest = json.loads((pkg / "MANIFEST.json").read_text())
    listed = set(manifest["files"])
    assert set(module.INVENTORY) <= listed
    assert "REPLICATION_README.md" in listed

    for name, meta in manifest["files"].items():
        data = (pkg / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name
        assert len(data) == meta["bytes"], name

    readme = (pkg / "REPLICATION_README.md").read_text()
    assert manifest["commit"] in readme
    assert "snapqcdata.net" in readme

    zip_path = Path(f"{pkg}.zip")
    with zipfile.ZipFile(zip_path) as zf:
        zipped = {name.split("/", 1)[1] for name in zf.namelist()}
    assert zipped == listed | {"MANIFEST.json"}


def test_export_is_deterministic_for_a_ref(tmp_path) -> None:
    module = _load_export_module()
    a = module.build_package("HEAD", tmp_path / "a")
    b = module.build_package("HEAD", tmp_path / "b")
    assert Path(f"{a}.zip").read_bytes() == Path(f"{b}.zip").read_bytes()
