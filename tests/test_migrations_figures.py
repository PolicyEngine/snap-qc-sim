"""Fast contract tests for committed migrations-paper figures."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper-causal" / "generate_figures.py"
FIGURES = {
    "fig-paths.png",
    "fig-placebo.png",
    "fig-channels.png",
    "fig-window.png",
}
ARTIFACT_HASHES = {
    # Values are hashes of committed inputs, never rendered matplotlib files.
    "event_study_results.json": (
        "2ad9107b6633ffb55e969d07c11f5b7602e857d4b691e0e9498d4c82debcc37f"
    ),
    "fixed_donor_decomposition_results.json": (
        "dd806a54892b2b3d4520ddab54c0e4e893008f8e6e0d309cd615c7d38cabbc22"
    ),
    "riky_event_study_results.json": (
        "6b8b927033058c550ba9b17c9d249ff6b64a16bb905470511f69a92825df743e"
    ),
    "uhip_decomposition_results.json": (
        "76f1cdee721a7801c54e3d256df56a42b33747dc39aa7bdf5da7e159005e98ba"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_script_and_committed_figures_exist() -> None:
    assert SCRIPT.is_file()
    assert {
        path.name for path in (ROOT / "paper-causal" / "figures").glob("*.png")
    } == FIGURES


def test_regeneration_file_set_and_inputs(tmp_path: Path) -> None:
    output = tmp_path / "figures"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(output)],
        cwd=ROOT,
        check=True,
    )
    assert {path.name for path in output.iterdir()} == FIGURES
    actual_hashes = {
        name: _sha256(ROOT / "analysis" / name) for name in ARTIFACT_HASHES
    }
    assert actual_hashes == ARTIFACT_HASHES


def test_generator_declares_the_same_value_inputs() -> None:
    spec = importlib.util.spec_from_file_location("migrations_figures", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.ARTIFACT_FILES.values()) == set(ARTIFACT_HASHES)
