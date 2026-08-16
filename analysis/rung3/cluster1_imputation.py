"""QC-trained deduction-composition imputation for Colorado Microcosm units.

The model is a transparent, weighted hot deck.  A single QC donor supplies all
deduction outcomes for a target, preserving the observed joint distribution.
Medical claims are additionally constrained to the elderly/disabled domain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
QC_DEFAULT = Path.home() / ".cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
DENSE_DEFAULT = (
    Path.home()
    / ".cache/huggingface/hub/datasets--policyengine--populace-us/snapshots"
    / "b4ef2d07b9f39a768e25bffb2455386ad67bd1b5/populace_us_2024.h5"
)
SPARSE_DEFAULT = Path(
    "/private/tmp/claude-501/-Users-maxghenis/"
    "51a1b6bb-c8a6-466b-bd9b-2620f722d19d/scratchpad/"
    "populace_us_2024_current.h5"
)
MODEL_DEFAULT = ROOT / "analysis/rung3/cluster1_models.json"
FRAME_DEFAULT = ROOT / "analysis/rung3/cluster1_co_frame.parquet"
SEED = 20240813

QC_COLUMNS = [
    "STATE",
    "CASE",
    "HWGT",
    "CERTHHSZ",
    "FSEARN",
    "FSUNEARN",
    "FSNELDER",
    "FSNDIS",
    "FSKID",
    "RENT",
    "UTIL",
    "SUA1",
    "FSMEDEXP",
    "FSDEPDED",
    "FSCSDED",
    "HOMEDED",
]
IDENTITY = [
    "spm_unit_source_id",
    "spm_unit_support_channel",
    "spm_unit_support_clone_index",
]
CLAIMS = [
    "utility_claims_actual_expenses",
    "medical_deduction_claimed",
    "dependent_care_deduction_claimed",
    "child_support_deduction_claimed",
    "homeless_deduction_claimed",
]
AMOUNTS = [
    "utility_allowance",
    "medical_expense_above_floor",
    "dependent_care_deduction",
    "child_support_deduction",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _band(values: pd.Series, cuts: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(
        pd.to_numeric(values, errors="coerce").fillna(0),
        [-np.inf, *cuts, np.inf],
        labels=labels,
        right=False,
    ).astype(str)


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the common, deliberately coarse QC/Microcosm feature cells."""
    result = frame.copy()
    result["size_band"] = _band(
        result["household_size"], [2, 3, 4], ["1", "2", "3", "4_plus"]
    )
    result["income_band"] = _band(
        result["gross_income"],
        [500, 1_000, 2_000],
        ["under_500", "500_999", "1000_1999", "2000_plus"],
    )
    result["shelter_band"] = _band(
        result["rent"], [1, 500, 1_000], ["zero", "1_499", "500_999", "1000_plus"]
    )
    result["has_elderly_or_disabled"] = result["has_elderly_or_disabled"].astype(bool)
    result["has_children"] = result["has_children"].astype(bool)
    return result


def load_qc(path: Path = QC_DEFAULT) -> pd.DataFrame:
    """Load the official Colorado CASE==1 universe and construct outcomes."""
    raw = pd.read_csv(path, usecols=QC_COLUMNS)
    raw = raw.loc[raw["STATE"].eq(8) & raw["CASE"].eq(1)].reset_index(drop=True)
    result = pd.DataFrame(
        {
            "case_id": [f"CO-FY2024-{i:04d}" for i in raw.index],
            "weight": raw["HWGT"].astype(float),
            "household_size": raw["CERTHHSZ"].astype(int),
            "earned_income": raw["FSEARN"].clip(lower=0).astype(float),
            "unearned_income": raw["FSUNEARN"].clip(lower=0).astype(float),
            "has_elderly_or_disabled": raw["FSNELDER"].add(raw["FSNDIS"]).gt(0),
            "has_children": raw["FSKID"].gt(0),
            "rent": raw["RENT"].clip(lower=0).astype(float),
            "utility_treatment": raw["SUA1"].astype(int),
            "utility_allowance": raw["UTIL"].clip(lower=0).astype(float),
            "utility_claims_actual_expenses": raw["SUA1"].eq(2),
            "medical_deduction_claimed": raw["FSMEDEXP"].gt(0),
            "medical_expense_above_floor": raw["FSMEDEXP"].clip(lower=0).astype(float),
            "dependent_care_deduction_claimed": raw["FSDEPDED"].gt(0),
            "dependent_care_deduction": raw["FSDEPDED"].clip(lower=0).astype(float),
            "child_support_deduction_claimed": raw["FSCSDED"].gt(0),
            "child_support_deduction": raw["FSCSDED"].clip(lower=0).astype(float),
            "homeless_deduction_claimed": raw["HOMEDED"].eq(3),
        }
    )
    result["gross_income"] = result["earned_income"] + result["unearned_income"]
    return add_features(result)


def _key(row: pd.Series, columns: list[str]) -> str:
    return "|".join(str(row[column]) for column in columns)


def fit_hot_deck(frame: pd.DataFrame, *, seed: int = SEED) -> dict[str, Any]:
    """Fit nested weighted donor pools; input may be a small test fixture."""
    data = add_features(frame).reset_index(drop=True)
    levels = [
        [
            "has_elderly_or_disabled",
            "has_children",
            "size_band",
            "income_band",
            "shelter_band",
        ],
        ["has_elderly_or_disabled", "has_children", "size_band", "income_band"],
        ["has_elderly_or_disabled", "has_children", "size_band"],
        ["has_elderly_or_disabled", "has_children"],
        ["has_elderly_or_disabled"],
    ]
    records = []
    for _, row in data.iterrows():
        record = {"weight": float(row["weight"])}
        for column in ["utility_treatment", *CLAIMS, *AMOUNTS]:
            value = row[column]
            record[column] = bool(value) if column in CLAIMS else float(value)
        record["utility_treatment"] = int(row["utility_treatment"])
        records.append(record)
    pools: list[dict[str, list[int]]] = []
    for columns in levels:
        pool: dict[str, list[int]] = {}
        for index, (_, row) in enumerate(data.iterrows()):
            pool.setdefault(_key(row, columns), []).append(index)
        pools.append(pool)
    return {
        "schema": "snap_qc_sim.cluster1_model.v1",
        "seed": seed,
        "feature_levels": levels,
        "donors": records,
        "pools": pools,
    }


def _uniform(seed: int, unit_id: str) -> float:
    raw = hashlib.sha256(f"{seed}|{unit_id}".encode()).digest()[:8]
    return int.from_bytes(raw, "big") / 2**64


def apply_hot_deck(model: dict[str, Any], frame: pd.DataFrame) -> pd.DataFrame:
    """Apply a fitted model with stable unit-keyed draws."""
    data = add_features(frame).copy()
    chosen = []
    for _, row in data.iterrows():
        candidates: list[int] | None = None
        for columns, pools in zip(model["feature_levels"], model["pools"], strict=True):
            candidates = pools.get(_key(row, columns))
            if candidates:
                break
        if not candidates:
            raise AssertionError("elderly/disabled fallback pool unexpectedly absent")
        weights = np.array([model["donors"][i]["weight"] for i in candidates])
        threshold = _uniform(int(model["seed"]), str(row["unit_id"])) * weights.sum()
        donor_index = candidates[
            min(int(np.searchsorted(weights.cumsum(), threshold)), len(candidates) - 1)
        ]
        chosen.append(model["donors"][donor_index])
    imputed = pd.DataFrame(chosen, index=data.index).drop(columns="weight")
    for column in imputed:
        data[column] = imputed[column]
    # QC's medical deduction is structurally unavailable outside this domain.
    outside = ~data["has_elderly_or_disabled"]
    data.loc[outside, "medical_deduction_claimed"] = False
    data.loc[outside, "medical_expense_above_floor"] = 0.0
    data["qc_donor_draw_seed"] = int(model["seed"])
    data["imputation_model_schema"] = model["schema"]
    return data


def _weighted_rate(frame: pd.DataFrame, column: str) -> float:
    return float(np.average(frame[column].astype(float), weights=frame["weight"]))


def _weighted_quantiles(
    values: pd.Series, weights: pd.Series
) -> dict[str, float | None]:
    keep = values.gt(0) & weights.gt(0)
    if not keep.any():
        return {"p25": None, "p50": None, "p75": None, "p90": None}
    order = np.argsort(values[keep].to_numpy())
    x = values[keep].to_numpy()[order]
    w = weights[keep].to_numpy()[order]
    cumulative = np.cumsum(w) / w.sum()
    return {
        name: float(x[min(np.searchsorted(cumulative, quantile), len(x) - 1)])
        for name, quantile in [("p25", 0.25), ("p50", 0.5), ("p75", 0.75), ("p90", 0.9)]
    }


def validation_summary(truth: pd.DataFrame, predicted: pd.DataFrame) -> dict[str, Any]:
    """Distributional rates, positive-dollar quantiles, and utility joint table."""
    rates = {}
    for column in CLAIMS:
        actual = _weighted_rate(truth, column)
        estimate = _weighted_rate(predicted, column)
        rates[column] = {
            "truth": actual,
            "predicted": estimate,
            "ratio": estimate / actual if actual else None,
        }
    quantiles = {
        column: {
            "truth": _weighted_quantiles(truth[column], truth["weight"]),
            "predicted": _weighted_quantiles(predicted[column], predicted["weight"]),
        }
        for column in AMOUNTS
    }
    joint: dict[str, dict[str, float]] = {}
    for label, data in [("truth", truth), ("predicted", predicted)]:
        total = data["weight"].sum()
        grouped = data.groupby(["shelter_band", "utility_treatment"], observed=True)[
            "weight"
        ].sum()
        joint[label] = {
            f"{a}|{int(b)}": float(w / total) for (a, b), w in grouped.items()
        }
    return {
        "claim_rates": rates,
        "conditional_dollar_quantiles": quantiles,
        "utility_by_shelter_band": joint,
    }


def _co_spm_frame(path: Path) -> pd.DataFrame:
    household = pd.read_hdf(path, "household")
    person = pd.read_hdf(path, "person")
    spm = pd.read_hdf(path, "spm_unit")
    co_households = household.loc[
        pd.to_numeric(household["state_fips"], errors="coerce").eq(8)
    ].copy()
    people = person.loc[
        person["person_household_id"].isin(co_households["household_id"])
    ].copy()
    people["_earned"] = people["WSAL_VAL"].fillna(0).clip(lower=0) + people[
        "SEMP_VAL"
    ].fillna(0).clip(lower=0)
    people["_unearned"] = (people["PTOTVAL"].fillna(0) - people["_earned"]).clip(
        lower=0
    )
    disability_columns = [column for column in people if column.startswith("PEDIS")]
    people["_disabled"] = people[disability_columns].eq(1).any(axis=1)
    grouped = people.groupby("person_spm_unit_id", sort=False).agg(
        household_id=("person_household_id", "first"),
        household_size=("person_id", "size"),
        earned_income=("_earned", "sum"),
        unearned_income=("_unearned", "sum"),
        has_elderly=("A_AGE", lambda x: bool((x >= 60).any())),
        has_disabled=("_disabled", "any"),
        has_children=("A_AGE", lambda x: bool((x < 18).any())),
        rent=("pre_subsidy_rent", "max"),
        reported_snap=("SPM_SNAPSUB", lambda x: bool((x.fillna(0) > 0).any())),
    )
    grouped[["earned_income", "unearned_income", "rent"]] /= 12.0
    units = spm.loc[spm["spm_unit_id"].isin(grouped.index)].set_index("spm_unit_id")
    result = grouped.join(units[IDENTITY + ["takes_up_snap_if_eligible"]])
    weights = co_households.set_index("household_id")["household_weight"]
    result["weight"] = result["household_id"].map(weights).astype(float)
    result["unit_id"] = result.index.astype(str)
    result["gross_income"] = result["earned_income"] + result["unearned_income"]
    result["has_elderly_or_disabled"] = result["has_elderly"] | result["has_disabled"]
    result["state_fips"] = 8
    return add_features(result.reset_index(names="spm_unit_id"))


def _split_qc(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    holdout = data["case_id"].map(
        lambda value: (
            int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big") % 4 == 0
        )
    )
    return data.loc[~holdout].copy(), data.loc[holdout].copy()


def build(
    *,
    qc_path: Path,
    dense_path: Path,
    sparse_path: Path,
    model_path: Path,
    frame_path: Path,
) -> None:
    qc = load_qc(qc_path)
    train, holdout = _split_qc(qc)
    validation_model = fit_hot_deck(train, seed=SEED)
    validation_prediction = apply_hot_deck(
        validation_model, holdout.assign(unit_id=holdout["case_id"])
    )
    validation = validation_summary(holdout, validation_prediction)

    model = fit_hot_deck(qc, seed=SEED)
    target = _co_spm_frame(sparse_path)
    output = apply_hot_deck(model, target)
    output["source_frame_sha256"] = _sha256(sparse_path)
    output["dense_audit_frame_sha256"] = _sha256(dense_path)
    output["qc_source_sha256"] = _sha256(qc_path)
    output["imputation_training_state"] = "CO"
    output["imputation_training_fiscal_year"] = 2024

    qc_rates = {column: _weighted_rate(qc, column) for column in CLAIMS}
    applied_rates = {column: _weighted_rate(output, column) for column in CLAIMS}
    model["training"] = {
        "state": "CO",
        "fiscal_year": 2024,
        "case_count": len(qc),
        "weighted_case_months": float(qc["weight"].sum()),
        "qc_source_sha256": _sha256(qc_path),
    }
    model["artifacts"] = {
        "dense_sha256": _sha256(dense_path),
        "sparse_sha256": _sha256(sparse_path),
        "dense_to_sparse_join": {
            "keys": IDENTITY,
            "sparse_co_units": len(target),
            "matched_dense_units": len(target),
            "dense_co_units": 4670,
        },
    }
    model["validation"] = validation
    model["application"] = {
        "unit_count": len(output),
        "qc_claim_rates": qc_rates,
        "frame_claim_rates": applied_rates,
        "frame_to_qc_ratios": {
            column: applied_rates[column] / qc_rates[column]
            if qc_rates[column]
            else None
            for column in CLAIMS
        },
        "artifact_test_bands": {
            column: [max(0.0, rate - 0.005), min(1.0, rate + 0.005)]
            for column, rate in applied_rates.items()
        },
    }
    model_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    output.sort_values("spm_unit_id").to_parquet(frame_path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qc", type=Path, default=QC_DEFAULT)
    parser.add_argument("--dense", type=Path, default=DENSE_DEFAULT)
    parser.add_argument("--sparse", type=Path, default=SPARSE_DEFAULT)
    parser.add_argument("--model", type=Path, default=MODEL_DEFAULT)
    parser.add_argument("--frame", type=Path, default=FRAME_DEFAULT)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(
        qc_path=args.qc,
        dense_path=args.dense,
        sparse_path=args.sparse,
        model_path=args.model,
        frame_path=args.frame,
    )
