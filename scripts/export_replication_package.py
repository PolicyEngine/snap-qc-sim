"""Export the migrations paper's replication package from a pinned git ref.

The development repo is the paper's home; journals want a scoped citation
object. This script cuts one: exactly the files the paper's "Artifacts and
reproduction" section names — manuscript, figures and their generator, the
estimation scripts and protocols, the committed result artifacts, the
registry and audit files, and the tests that lock every quoted value —
extracted from a single git ref via ``git archive`` so nothing from the
working tree can leak in.

Output is deterministic for a given ref: file bytes come from the ref, the
generated README and MANIFEST carry the commit hash rather than wall-clock
time, and zip entries use the commit's own timestamp, so re-exporting the
same ref yields a byte-identical zip.

Usage:
    uv run python scripts/export_replication_package.py --ref v20260817
    uv run python scripts/export_replication_package.py --ref HEAD --verify
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Every file the paper's reproduction section relies on. The export FAILS if
# any entry is missing at the ref — a rename upstream must update this list.
INVENTORY = [
    # Manuscript, bibliography, figures, and the figure generator.
    "paper-causal/index.qmd",
    "paper-causal/references.bib",
    "paper-causal/generate_figures.py",
    "paper-causal/FIGURES_CAPTIONS.md",
    "paper-causal/figures/fig-paths.png",
    "paper-causal/figures/fig-placebo.png",
    "paper-causal/figures/fig-window.png",
    "paper-causal/figures/fig-channels.png",
    # Estimation code, frozen protocols, memos, and committed artifacts.
    "analysis/event_study.py",
    "analysis/uhip_decomposition.py",
    "analysis/fixed_donor_decomposition.py",
    "analysis/riky_event_study_results.json",
    "analysis/event_study_results.json",
    "analysis/uhip_decomposition_results.json",
    "analysis/fixed_donor_decomposition_results.json",
    "analysis/system_migrations.json",
    "analysis/coding_consistency.json",
    "analysis/cause_shares.json",
    "analysis/RIKY_EVENT_STUDY_PROTOCOL.md",
    "analysis/EVENT_STUDY_PROTOCOL.md",
    "analysis/UHIP_DECOMPOSITION_PROTOCOL.md",
    "analysis/UHIP_DECOMPOSITION.md",
    "analysis/UHIP_DECOMPOSITION_DEVIATIONS.md",
    "analysis/FIXED_DONOR_PROTOCOL.md",
    "analysis/FIXED_DONOR.md",
    "analysis/EVENT_FAMILY_ADDENDUM.md",
    "analysis/EVENT_FAMILY_ADDENDUM_CORRECTION.md",
    # The value locks: every number quoted in the paper has a test here.
    "tests/conftest.py",
    "tests/test_riky_event_study.py",
    "tests/test_event_study.py",
    "tests/test_uhip_decomposition.py",
    "tests/test_fixed_donor_decomposition.py",
    "tests/test_system_migrations.py",
    "tests/test_migrations_figures.py",
    # Pinned environment; snap_qc_sim ships so `uv run --frozen` can build
    # the project's editable install exactly as in the source repo.
    "pyproject.toml",
    "uv.lock",
    "snap_qc_sim/__init__.py",
    "snap_qc_sim/data.py",
    "snap_qc_sim/simulate.py",
]

README_TEMPLATE = """\
# Replication package — three SNAP eligibility-system migrations

Scoped replication package for "What a system replacement does to measured
error: three SNAP eligibility-system migrations in the quality-control
record" (Max Ghenis, PolicyEngine). Exported from the development
repository at a pinned commit; the live manuscript is at
https://policyengine.org/us/snap-payment-error-simulator/paper-migrations/

- Source repository: https://github.com/PolicyEngine/snap-qc-sim
- Pinned ref: `{ref}`
- Commit: `{commit}`
- License: Apache-2.0 (per the repository's pyproject.toml)

## Verify every quoted value

Each number quoted in the paper reads from a committed artifact in
`analysis/`, and a fast test locks each quoted value to its artifact:

    uv run --frozen --extra dev --extra analysis pytest tests/ -q

The locks run from the committed JSON artifacts alone — no external data
needed. `MANIFEST.json` lists the SHA-256 of every file here; compare
against the source repository at the pinned commit to confirm byte
identity.

## Full regeneration (optional, needs the raw QC files)

Regenerating the artifacts from raw data needs the FY2012-24 SNAP
quality-control public-use files, which USDA FNS distributes at
https://snapqcdata.net/datafiles (documentation at
https://www.fns.usda.gov/snap/qc/per). This package does not redistribute
them. The loaders in `analysis/event_study.py` verify the SHA-256 of every
raw file they read; the regeneration tests skip when the hash-audited
local cache is absent and compare values, not bytes, when it is present.

`analysis/cause_shares.json` ships as a committed artifact; its generator
depends on the source repository's error-model stack, which sits outside
this paper's scope.

## Figures

`paper-causal/generate_figures.py` regenerates all four figures from the
committed artifacts (requires matplotlib):

    uv run --frozen --extra dev --extra analysis \\
        python paper-causal/generate_figures.py \\
        --output-dir paper-causal/figures
"""


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, cwd=ROOT, **kwargs)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_package(ref: str, output_dir: Path) -> Path:
    """Extract the inventory at ``ref`` into ``output_dir``; return the package dir."""
    commit = _run(["git", "rev-parse", ref]).stdout.decode().strip()
    commit_epoch = int(
        _run(["git", "show", "-s", "--format=%ct", commit]).stdout.decode().strip()
    )

    archive = _run(["git", "archive", "--format=tar", commit, "--", *INVENTORY]).stdout
    extracted: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                extracted[member.name] = tar.extractfile(member).read()

    missing = sorted(set(INVENTORY) - set(extracted))
    if missing:
        raise SystemExit(
            f"inventory files missing at {ref}: {missing} — "
            "update INVENTORY if the paper's files moved"
        )

    pkg = output_dir / f"snap-migrations-replication-{commit[:12]}"
    for name, data in extracted.items():
        dest = pkg / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    readme = README_TEMPLATE.format(ref=ref, commit=commit)
    (pkg / "REPLICATION_README.md").write_text(readme)

    files = {name: extracted[name] for name in sorted(extracted)}
    files["REPLICATION_README.md"] = readme.encode()
    manifest = {
        "paper": "three SNAP eligibility-system migrations in the quality-control record",
        "source_repository": "https://github.com/PolicyEngine/snap-qc-sim",
        "ref": ref,
        "commit": commit,
        "files": {
            name: {"sha256": _sha256(data), "bytes": len(data)}
            for name, data in sorted(files.items())
        },
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    (pkg / "MANIFEST.json").write_bytes(manifest_bytes)
    files["MANIFEST.json"] = manifest_bytes

    zip_path = output_dir / f"{pkg.name}.zip"
    date_time = _zip_datetime(commit_epoch)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(f"{pkg.name}/{name}", date_time=date_time)
            info.external_attr = 0o644 << 16
            zf.writestr(info, files[name])
    return pkg


def _zip_datetime(epoch: int) -> tuple[int, int, int, int, int, int]:
    import time

    t = time.gmtime(max(epoch, 315532800))  # zip epoch floor: 1980-01-01
    return (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)


def verify_package(pkg: Path) -> None:
    """Run the value-lock tests inside the exported package."""
    env = dict(os.environ, PYTHONPATH=str(pkg))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q"],
        cwd=pkg,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"package verification failed (pytest rc={result.returncode})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="git ref to export (tag, sha, HEAD)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist",
        help="directory for the package dir and zip (default: dist/)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="run the value-lock tests inside the exported package",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pkg = build_package(args.ref, args.output_dir)
    print(f"exported {pkg}")
    print(f"zip: {pkg}.zip")
    if args.verify:
        verify_package(pkg)
        print("package verification: value-lock tests pass inside the package")


if __name__ == "__main__":
    main()
