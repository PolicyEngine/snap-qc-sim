"""Out-of-sample FY2024 capture curves for the committed error model.

This is an accounting construction: it asks what share of measured counted
error dollars lies in a fixed HWGT-weighted review budget. It is not a causal
estimate and does not predict what targeting would cause.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from analysis import train_error_model as model

OUT = Path(__file__).with_name("model_capture_results.json")
COVERAGE_PCT = (1, 2, 5, 10, 20)
SEED = 20260820
AUC_TOLERANCE = 5e-12


def raw_inputs_available() -> bool:
    return all(
        (model.QC_DIR / f"qc_pub_fy{year}.sav").is_file() for year in model.YEARS
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_scored_fy2024() -> pd.DataFrame:
    """Refit through the training script's own path and return FY2024 scores."""
    if model.YEAR_TEST in model.YEARS_TRAIN or model.YEARS != [
        *model.YEARS_TRAIN,
        model.YEAR_TEST,
    ]:
        raise AssertionError("training-script year constants no longer isolate FY2024")
    smd = model.load_smd_registry()
    bbce = model.load_bbce_registry()
    premiums = model.load_medicare_part_b_premiums()
    frames = []
    sources = []
    for year in model.YEARS:
        source = model.load_year(year, include_source_row_index=True)
        features = model.build_features(source, smd[year], bbce[year], premiums)
        features["source_row_index"] = source["source_row_index"].to_numpy()
        frames.append(features)
        sources.append(source)
    data = pd.concat(frames, ignore_index=True)
    raw = pd.concat(sources, ignore_index=True)
    train = data.loc[data["year"].isin(model.YEARS_TRAIN)]
    test_mask = data["year"].eq(model.YEAR_TEST)
    test = data.loc[test_mask].copy()
    committed_columns = model.COVARIATES + model.BURDEN_INTERMEDIATES
    _, scores, _ = model.fit_score(
        train, test, committed_columns, "committed burden model"
    )
    test["model_score"] = scores
    test["counted_error_dollars"] = (
        raw.loc[test_mask, "AMTERR"].to_numpy() * test["official_error"].to_numpy()
    )
    return test.reset_index(drop=True)


def weighted_budget_capture(
    frame: pd.DataFrame, score: np.ndarray, coverage: float
) -> float:
    """Counted-error-dollar capture at an exact weighted-caseload budget."""
    order = np.lexsort((frame["source_row_index"].to_numpy(), -np.asarray(score)))
    weights = frame["w"].to_numpy(dtype=float)[order]
    dollars = (
        frame["w"].to_numpy(dtype=float)
        * frame["counted_error_dollars"].to_numpy(dtype=float)
    )[order]
    budget = coverage * weights.sum()
    before = np.r_[0.0, np.cumsum(weights)[:-1]]
    fraction = np.clip((budget - before) / weights, 0.0, 1.0)
    denominator = dollars.sum()
    return float((fraction * dollars).sum() / denominator) if denominator else 0.0


def _curve(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, Any]:
    random_score = rng.random(len(frame))
    result: dict[str, Any] = {}
    for pct in COVERAGE_PCT:
        coverage = pct / 100
        result[str(pct)] = {
            "model": round(
                weighted_budget_capture(
                    frame, frame["model_score"].to_numpy(), coverage
                ),
                8,
            ),
            "oracle": round(
                weighted_budget_capture(
                    frame, frame["counted_error_dollars"].to_numpy(), coverage
                ),
                8,
            ),
            "random_expectation": coverage,
            "random_seeded_draw": round(
                weighted_budget_capture(frame, random_score, coverage), 8
            ),
        }
    return result


def compute_artifact() -> dict[str, Any]:
    scored = load_scored_fy2024()
    auc = float(
        roc_auc_score(
            scored["official_error"], scored["model_score"], sample_weight=scored["w"]
        )
    )
    locked = float(model.COMMITTED_BURDEN_BASELINE["roc_auc"])
    if abs(auc - locked) > AUC_TOLERANCE:
        raise AssertionError(
            f"FY2024 ROC-AUC drifted: recomputed {auc}, committed {locked}"
        )
    if abs(auc - 0.7666) > 0.00005:
        raise AssertionError(f"FY2024 ROC-AUC no longer rounds to locked 0.7666: {auc}")
    rng = np.random.default_rng(SEED)
    return {
        "schema_version": 1,
        "interpretation": (
            "accounting construction: share of FY2024 measured counted error dollars "
            "within an HWGT-weighted review budget; not a causal estimate"
        ),
        "provenance": {
            "evaluation_year": model.YEAR_TEST,
            "training_years": model.YEARS_TRAIN,
            "out_of_sample_by_construction": True,
            "verification": "YEAR_TEST is absent from YEARS_TRAIN in analysis/train_error_model.py",
            "training_path_reused": "load_year + build_features + fit_score",
            "feature_set": "COVARIATES + BURDEN_INTERMEDIATES",
        },
        "coverage_pct": list(COVERAGE_PCT),
        "roc_auc_cross_check": {
            "recomputed": auc,
            "committed": locked,
            "display_lock": 0.7666,
        },
        "national": _curve(scored, rng),
        "states": {
            state: _curve(group.reset_index(drop=True), rng)
            for state, group in scored.groupby("state", sort=True)
        },
        "input_hashes": {
            "model_results": _sha256(model.OUT / "model_results.json"),
            "train_error_model": _sha256(Path(model.__file__)),
            "inputs": model._provenance()["input_sha256"],
        },
        "environment": {"seed": SEED},
        "runtime": "measured externally and reported in INTERVENTIONS_REPORT.md to keep regeneration byte-identical",
    }


def main() -> None:
    OUT.write_text(json.dumps(compute_artifact(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
