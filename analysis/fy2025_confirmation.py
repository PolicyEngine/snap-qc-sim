"""Run the frozen SNAP QC pipeline once against the FY2025 public-use file."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd

from analysis import distributional_deviation_model as distributional
from analysis import hurdle_deviation_model as hurdle
from analysis import train_error_model as classifier

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
MANIFEST_PATH = ANALYSIS / "fy2025_confirmation_manifest.json"
RESULTS_PATH = ANALYSIS / "fy2025_confirmation_results.json"
REFERENCE_PATHS = {
    "classifier": ANALYSIS / "model_results.json",
    "hurdle": ANALYSIS / "hurdle_results.json",
    "distributional": ANALYSIS / "distributional_results.json",
}
FROZEN_MODULES = (
    "analysis/train_error_model.py",
    "analysis/hurdle_deviation_model.py",
    "analysis/distributional_deviation_model.py",
    "analysis/predictive_process.py",
)
FY2025_THRESHOLD = 57
FY2025_PERSON_SLOTS = 18


class FreezeDriftError(RuntimeError):
    """Raised when a frozen scoring dependency no longer matches the manifest."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _metric_references() -> dict[str, Any]:
    model = _read_json(REFERENCE_PATHS["classifier"])
    hurdle_result = _read_json(REFERENCE_PATHS["hurdle"])
    dist = _read_json(REFERENCE_PATHS["distributional"])
    return {
        "classifier": {
            "roc_auc": model["models"]["with_burden_intermediates"]["roc_auc"],
            "pr_auc": model["models"]["with_burden_intermediates"]["pr_auc"],
        },
        "hurdle": {
            "stage1_roc_auc": hurdle_result["stage1"]["fy2024"]["auc_calibrated"],
            "stage1_pr_auc": hurdle_result["stage1"]["fy2024"]["pr_auc_calibrated"],
            "stage2_roc_auc": hurdle_result["stage2"]["fy2024_among_stage1_positives"][
                "auc_calibrated"
            ],
            "stage2_pr_auc": hurdle_result["stage2"]["fy2024_among_stage1_positives"][
                "pr_auc_calibrated"
            ],
            "stage3_observed_mean": hurdle_result["stage3"]["fy2024"][
                "observed_abs_D_mean_weighted"
            ],
            "stage3_predicted_mean": hurdle_result["stage3"]["fy2024"][
                "predicted_abs_D_mean_weighted"
            ],
        },
        "factored_equal_state_dollar_rate_mae_pp": dist["dollar_rate_validation"][
            "metrics"
        ]["factor_adjusted_frozen_model"]["equal_jurisdiction"]["mae_pp"],
        "coverage_gaps_pp": [
            row["gap_pp"]
            for row in dist["magnitude_distribution"]["fy2024_weighted_coverage"]
        ],
        "sign_roc_auc": dist["sign"]["fy2024_among_deviators"]["auc_calibrated"],
    }


def build_manifest() -> dict[str, Any]:
    """Build the immutable portion of the freeze manifest."""
    registries = {
        "standard_medical_deductions.csv": classifier.SMD_PATH,
        "state_bbce.csv": classifier.BBCE_PATH,
        "medicare_part_b_premiums.csv": classifier.MEDICARE_PART_B_PATH,
    }
    return {
        "schema_version": 1,
        "freeze_name": "FY2025 frozen-pipeline confirmation",
        "frozen_modules_sha256": {
            name: _sha256(ROOT / name) for name in FROZEN_MODULES
        },
        "feature_registry_sha256": {
            name: _sha256(path) for name, path in registries.items()
        },
        "model_hyperparameters": {
            "classifier": {
                "max_iter": 300,
                "learning_rate": 0.08,
                "max_leaf_nodes": 63,
                "random_state": classifier.RANDOM_STATE,
            },
            "hurdle_and_distributional": hurdle.MODEL_PARAMS,
            "folds": hurdle.N_FOLDS,
            "distributional_quantiles": list(distributional.QUANTILE_LEVELS),
            "distributional_sign_seed": distributional.SIGN_SEED,
            "distributional_tail_seed": distributional.TAIL_SEED,
        },
        "train_years": {
            "classifier_and_primary_hurdle": classifier.YEARS_TRAIN,
            "frozen_factored_distributional": [2017, 2018, 2019, 2022],
            "state_factor_fit": [2023],
        },
        "fy2025_schema": {
            "threshold_dollars": FY2025_THRESHOLD,
            "person_self_employment_slots": FY2025_PERSON_SLOTS,
            "smd_and_bbce_policy": "carry forward frozen FY2024 registry cells",
        },
        "metric_definitions": {
            "classifier_auc_pr_auc": "analysis/train_error_model.py:938",
            "hurdle_probability_metrics": "analysis/hurdle_deviation_model.py:259",
            "equal_state_mae": "analysis/hurdle_deviation_model.py:734",
            "quantile_coverage_gaps": (
                "analysis/distributional_deviation_model.py:426"
            ),
            "sign_auc": "analysis/hurdle_deviation_model.py:259",
        },
        "fy2024_reference_values": _metric_references(),
        "input_files": {},
    }


def manifest_hash(manifest: dict[str, Any]) -> str:
    """Hash the full manifest, including the recorded evaluation input."""
    return hashlib.sha256(_canonical_bytes(manifest)).hexdigest()


def write_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Write a newly frozen manifest; intended only during harness creation."""
    manifest = build_manifest()
    path.write_bytes(json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")
    return manifest


def verify_freeze(manifest: dict[str, Any], root: Path = ROOT) -> None:
    """Fail closed and enumerate every frozen module or registry that drifted."""
    drifted = []
    for name, expected in manifest["frozen_modules_sha256"].items():
        path = root / name
        actual = _sha256(path) if path.is_file() else "missing"
        if actual != expected:
            drifted.append(name)
    registry_paths = {
        "standard_medical_deductions.csv": classifier.SMD_PATH,
        "state_bbce.csv": classifier.BBCE_PATH,
        "medicare_part_b_premiums.csv": classifier.MEDICARE_PART_B_PATH,
    }
    for name, expected in manifest["feature_registry_sha256"].items():
        path = registry_paths[name]
        actual = _sha256(path) if path.is_file() else "missing"
        if actual != expected:
            drifted.append(str(path))
    if drifted:
        files = "\n".join(f"  - {name}" for name in drifted)
        raise FreezeDriftError(f"frozen pipeline drift detected:\n{files}")


def record_input(path: Path, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Record the QC file hash before any scoring is permitted."""
    manifest = _read_json(manifest_path)
    digest = _sha256(path)
    inputs = manifest.setdefault("input_files", {})
    key = path.name
    if key in inputs and inputs[key]["sha256"] != digest:
        raise ValueError(f"{key} is already recorded with a different sha256")
    inputs[key] = {"sha256": digest, "size_bytes": path.stat().st_size}
    manifest_path.write_bytes(
        json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    )
    return manifest


@contextmanager
def _evaluation_year(year: int, qc_path: Path) -> Iterator[None]:
    """Point all three frozen modules at one explicitly supplied test file."""
    modules = (classifier, hurdle, distributional)
    saved = [(module, module.YEAR_TEST) for module in modules]
    saved_threshold = dict(classifier.THRESHOLD)
    saved_slots = dict(classifier.PERSON_SLOTS_BY_YEAR)
    saved_dir = classifier.QC_DIR
    saved_hurdle_dir = hurdle.QC_DIR
    smd_loader = hurdle.load_smd_registry
    bbce_loader = hurdle.load_bbce_registry

    def smd_with_frozen_test_year() -> dict[int, set[str]]:
        registry = smd_loader()
        registry[year] = set(registry[2024])
        return registry

    def bbce_with_frozen_test_year() -> dict[int, set[str]]:
        old_years = classifier.YEARS
        classifier.YEARS = classifier.YEARS_TRAIN + [2024]
        try:
            registry = bbce_loader()
        finally:
            classifier.YEARS = old_years
        registry[year] = set(registry[2024])
        return registry

    if qc_path.name != f"qc_pub_fy{year}.sav":
        raise ValueError(f"expected filename qc_pub_fy{year}.sav, got {qc_path.name}")
    try:
        classifier.QC_DIR = qc_path.parent
        hurdle.QC_DIR = qc_path.parent
        classifier.THRESHOLD[year] = FY2025_THRESHOLD if year == 2025 else 56
        classifier.PERSON_SLOTS_BY_YEAR[year] = FY2025_PERSON_SLOTS
        classifier.YEAR_TEST = year
        classifier.YEARS = classifier.YEARS_TRAIN + [year]
        hurdle.YEAR_TEST = year
        hurdle.THRESHOLD = classifier.THRESHOLD
        hurdle.load_smd_registry = smd_with_frozen_test_year
        hurdle.load_bbce_registry = bbce_with_frozen_test_year
        distributional.YEAR_TEST = year
        distributional.THRESHOLD = classifier.THRESHOLD
        yield
    finally:
        classifier.QC_DIR = saved_dir
        hurdle.QC_DIR = saved_hurdle_dir
        classifier.THRESHOLD.clear()
        classifier.THRESHOLD.update(saved_threshold)
        classifier.PERSON_SLOTS_BY_YEAR.clear()
        classifier.PERSON_SLOTS_BY_YEAR.update(saved_slots)
        classifier.YEARS = classifier.YEARS_TRAIN + [saved[0][1]]
        for module, value in saved:
            module.YEAR_TEST = value
        hurdle.load_smd_registry = smd_loader
        hurdle.load_bbce_registry = bbce_loader


def _classifier_metrics(year: int) -> dict[str, float]:
    smd = hurdle.load_smd_registry()
    bbce = hurdle.load_bbce_registry()
    premiums = classifier.load_medicare_part_b_premiums()
    frames = []
    for current_year in classifier.YEARS_TRAIN + [year]:
        frames.append(
            classifier.build_features(
                classifier.load_year(current_year),
                smd[current_year],
                bbce[current_year],
                premiums,
            )
        )
    data = pd.concat(frames, ignore_index=True)
    train = data.loc[data["year"].isin(classifier.YEARS_TRAIN)]
    test = data.loc[data["year"].eq(year)]
    columns = classifier.COVARIATES + classifier.BURDEN_INTERMEDIATES
    _, _, metrics = classifier.fit_score(train, test, columns, "frozen classifier")
    return {"roc_auc": metrics["roc_auc"], "pr_auc": metrics["pr_auc"]}


def _extract_metrics(
    classifier_metrics: dict[str, float],
    hurdle_result: dict[str, Any],
    distributional_result: dict[str, Any],
    year: int,
) -> dict[str, Any]:
    # These legacy result keys name the original validation year literally;
    # their values are computed from the currently patched evaluation year.
    year_key = "fy2024"
    return {
        "classifier": classifier_metrics,
        "hurdle": {
            "stage1_roc_auc": hurdle_result["stage1"][year_key]["auc_calibrated"],
            "stage1_pr_auc": hurdle_result["stage1"][year_key]["pr_auc_calibrated"],
            "stage2_roc_auc": hurdle_result["stage2"][
                f"{year_key}_among_stage1_positives"
            ]["auc_calibrated"],
            "stage2_pr_auc": hurdle_result["stage2"][
                f"{year_key}_among_stage1_positives"
            ]["pr_auc_calibrated"],
            "stage3_observed_mean": hurdle_result["stage3"][year_key][
                "observed_abs_D_mean_weighted"
            ],
            "stage3_predicted_mean": hurdle_result["stage3"][year_key][
                "predicted_abs_D_mean_weighted"
            ],
        },
        "factored_equal_state_dollar_rate_mae_pp": distributional_result[
            "dollar_rate_validation"
        ]["metrics"]["factor_adjusted_frozen_model"]["equal_jurisdiction"]["mae_pp"],
        "coverage_gaps_pp": [
            row["gap_pp"]
            for row in distributional_result["magnitude_distribution"][
                "fy2024_weighted_coverage"
            ]
        ],
        "sign_roc_auc": distributional_result["sign"]["fy2024_among_deviators"][
            "auc_calibrated"
        ],
    }


def run(
    qc_path: Path,
    *,
    year: int = 2025,
    manifest_path: Path = MANIFEST_PATH,
    results_path: Path = RESULTS_PATH,
) -> dict[str, Any]:
    """Record an input, verify the freeze, score it, and write confirmation JSON."""
    manifest = record_input(qc_path, manifest_path)
    verify_freeze(manifest)
    with _evaluation_year(year, qc_path):
        classifier_metrics = _classifier_metrics(year)
        hurdle_result = hurdle.main(results_path.with_suffix(".hurdle.tmp"))
        distributional_artifacts = distributional.main(
            results_path.with_suffix(".distributional.tmp")
        )
    metrics = _extract_metrics(
        classifier_metrics, hurdle_result, distributional_artifacts.result, year
    )
    references = manifest["fy2024_reference_values"]
    result = {
        "schema_version": 1,
        "evaluation_year": year,
        "input": manifest["input_files"][qc_path.name],
        "freeze_manifest_sha256": manifest_hash(manifest),
        "metrics": {
            name: {"value": value, "fy2024_reference": references[name]}
            for name, value in metrics.items()
        },
    }
    results_path.write_bytes(
        json.dumps(result, indent=2, sort_keys=True).encode() + b"\n"
    )
    results_path.with_suffix(".hurdle.tmp").unlink(missing_ok=True)
    results_path.with_suffix(".distributional.tmp").unlink(missing_ok=True)
    return result


def dry_run(
    qc_path: Path,
    manifest_path: Path = MANIFEST_PATH,
    results_path: Path | None = None,
) -> None:
    """Run FY2024 through the harness and require byte-identical metric JSON."""
    manifest = _read_json(manifest_path)
    verify_freeze(manifest)
    temporary = results_path or RESULTS_PATH.with_suffix(".dry-run.json")
    original_manifest = manifest_path.read_bytes()
    try:
        result = run(
            qc_path,
            year=2024,
            manifest_path=manifest_path,
            results_path=temporary,
        )
    finally:
        manifest_path.write_bytes(original_manifest)
    actual = {name: cell["value"] for name, cell in result["metrics"].items()}
    expected = manifest["fy2024_reference_values"]
    if _canonical_bytes(actual) != _canonical_bytes(expected):
        raise AssertionError("FY2024 dry-run metrics differ from committed references")
    temporary.unlink(missing_ok=True)
    print("FY2024 dry run reproduced all committed references byte-for-byte")


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qc_file", type=Path, nargs="?")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-manifest", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.write_manifest:
        write_manifest()
        return 0
    if args.qc_file is None:
        parser.error("qc_file is required")
    try:
        if args.dry_run:
            dry_run(args.qc_file)
        else:
            run(args.qc_file)
    except (FreezeDriftError, ValueError, AssertionError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
