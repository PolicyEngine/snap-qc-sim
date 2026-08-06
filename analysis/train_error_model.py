"""Official-error classifier and descriptive medical-error contrasts.

The analysis uses FY2017-19 and FY2022-23 for training and FY2024 for
evaluation. Pandemic-distorted FY2020-21 records remain excluded. The
diagnostic outcome is the adjudicated QC definition, not a difference between
two benefit fields. ``FSBEN`` is retained only as the engine-computable formula
benefit feature; the signed hurdle target is ``RAWBEN - BENFIX`` because
``BENFIX`` includes legitimate allotment adjustments such as proration.

Standard-medical-deduction (SMD) exposure comes from the state-year amount
registry. Adoption comparisons below are descriptive weighted contrasts, not
causal estimates. They deliberately report both the claimant-conditioned
population and the stable population of all elderly/disabled households.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyreadstat
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score

QC_DIR = Path("~/.cache/axiom-oracles/snap_qc_repo/qc_data").expanduser()
ADDITIONAL_DATA_DIR = Path(
    "~/.cache/axiom-oracles/snap_qc_repo/additional_data"
).expanduser()
SMD_PATH = ADDITIONAL_DATA_DIR / "standard_medical_deductions.csv"
OUT = Path(__file__).parent
YEARS_TRAIN = [2017, 2018, 2019, 2022, 2023]
YEAR_TEST = 2024
YEARS = YEARS_TRAIN + [YEAR_TEST]
THRESHOLD = {2017: 38, 2018: 37, 2019: 37, 2022: 48, 2023: 54, 2024: 56}
RANDOM_STATE = 7
PERSON_SLOTS_BY_YEAR = {
    2017: 16,
    2018: 16,
    2019: 16,
    2022: 16,
    2023: 17,
    2024: 18,
}

FIPS = {
    1: "AL",
    2: "AK",
    4: "AZ",
    5: "AR",
    6: "CA",
    8: "CO",
    9: "CT",
    10: "DE",
    11: "DC",
    12: "FL",
    13: "GA",
    15: "HI",
    16: "ID",
    17: "IL",
    18: "IN",
    19: "IA",
    20: "KS",
    21: "KY",
    22: "LA",
    23: "ME",
    24: "MD",
    25: "MA",
    26: "MI",
    27: "MN",
    28: "MS",
    29: "MO",
    30: "MT",
    31: "NE",
    32: "NV",
    33: "NH",
    34: "NJ",
    35: "NM",
    36: "NY",
    37: "NC",
    38: "ND",
    39: "OH",
    40: "OK",
    41: "OR",
    42: "PA",
    44: "RI",
    45: "SC",
    46: "SD",
    47: "TN",
    48: "TX",
    49: "UT",
    50: "VT",
    51: "VA",
    53: "WA",
    54: "WV",
    55: "WI",
    56: "WY",
    66: "GU",
    78: "VI",
}

STATE_NAME_TO_ABBR = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Guam": "GU",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virgin Islands": "VI",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}

FINDING_SLOTS = range(1, 10)
MEDICAL_ELEMENT = 365
IMPACT_FINDINGS = {2, 3, 4}  # overissuance, underissuance, ineligible

# Every name here is used by this module. Person-level self-employment fields
# are discovered separately because the published maximum slot grows from 16
# (FY2017-22), to 17 (FY2023), to 18 (FY2024).
REQUIRED_COLS = [
    "FSNKID",
    "EXPEDSER",
    "FSERNDED",
    "STATE",
    "YRMONTH",
    "HWGT",
    "STATUS",
    "AMTERR",
    "RAWBEN",
    "BENFIX",
    "FSBEN",
    "FSUSIZE",
    "CERTHHSZ",
    "FSNELDER",
    "FSNDIS",
    "FSEARN",
    "FSUNEARN",
    "FSGRINC",
    "FSNETINC",
    "FSMEDEXP",
    "FSMEDDED",
    "FSDEPDED",
    "FSCSDED",
    "FSSLTDED",
    "FSSLFEMP",
    "SUA1",
    "BENMAX",
    "MINIMUM_BEN",
    "CASE",
    *[f"ELEMENT{i}" for i in FINDING_SLOTS],
    *[f"E_FINDG{i}" for i in FINDING_SLOTS],
    *[f"AMOUNT{i}" for i in FINDING_SLOTS],
]
# Backward-compatible public name used by early analysis code.
COLS = REQUIRED_COLS


def assert_required_columns(
    df: pd.DataFrame, columns: list[str], *, context: str = "data"
) -> None:
    """Raise on an absent requested field instead of silently dropping it."""
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise ValueError(f"{context} is missing required columns: {', '.join(missing)}")


def _self_employment_columns(
    columns: pd.Index | list[str], *, expected_count: int | None = None
) -> list[str]:
    found = sorted(
        (c for c in columns if re.fullmatch(r"SLFEMP(?:[1-9]|1[0-8])", c)),
        key=lambda c: int(c.removeprefix("SLFEMP")),
    )
    if not found:
        raise ValueError("data is missing required SLFEMP person columns")
    count = len(found) if expected_count is None else expected_count
    expected = [f"SLFEMP{i}" for i in range(1, count + 1)]
    if found != expected:
        raise ValueError(
            "SLFEMP person columns are not contiguous: "
            f"expected {expected}, found {found}"
        )
    return found


def load_year(year: int) -> pd.DataFrame:
    """Load and enforce the official ``CASE == 1`` QC universe for one year."""
    if year not in THRESHOLD:
        raise ValueError(f"No official payment-error threshold configured for FY{year}")
    path = QC_DIR / f"qc_pub_fy{year}.sav"
    df, _ = pyreadstat.read_sav(str(path))
    df.columns = [c.upper() for c in df.columns]
    assert_required_columns(df, REQUIRED_COLS, context=f"FY{year} SAV")
    se_cols = _self_employment_columns(
        df.columns, expected_count=PERSON_SLOTS_BY_YEAR[year]
    )
    df = df[REQUIRED_COLS + se_cols].copy()
    df = filter_case_universe(df)
    df["year"] = year
    df["state"] = df["STATE"].map(FIPS)
    return df.loc[df["state"].notna()].reset_index(drop=True)


def filter_case_universe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy restricted to cases included in the official error rate."""
    assert_required_columns(df, ["CASE"], context="QC universe input")
    return df.loc[df["CASE"].eq(1)].copy()


def load_smd_amounts(path: Path = SMD_PATH) -> pd.DataFrame:
    """Return the authoritative state-year SMD amount registry in long form."""
    wide = pd.read_csv(path, encoding="utf-8-sig")
    assert_required_columns(
        wide,
        ["state_name", *[str(y) for y in range(2017, 2025)]],
        context="SMD registry",
    )
    if wide["state_name"].duplicated().any():
        duplicates = sorted(
            wide.loc[wide["state_name"].duplicated(), "state_name"].astype(str)
        )
        raise ValueError(f"Duplicate states in SMD registry: {', '.join(duplicates)}")
    wide["state"] = wide["state_name"].map(STATE_NAME_TO_ABBR)
    if wide["state"].isna().any():
        names = sorted(wide.loc[wide["state"].isna(), "state_name"].astype(str))
        raise ValueError(f"Unrecognized states in SMD registry: {', '.join(names)}")
    expected_states = set(FIPS.values())
    actual_states = set(wide["state"])
    if actual_states != expected_states:
        missing = sorted(expected_states - actual_states)
        extra = sorted(actual_states - expected_states)
        raise ValueError(
            f"SMD registry state coverage mismatch: missing={missing}, extra={extra}"
        )
    long = wide.melt(
        id_vars=["state_name", "state"],
        value_vars=[str(y) for y in range(2017, 2025)],
        var_name="year",
        value_name="amount",
    )
    long["year"] = long["year"].astype(int)
    long["amount"] = pd.to_numeric(long["amount"], errors="raise")
    if long["amount"].isna().any() or long["amount"].lt(0).any():
        raise ValueError("SMD amounts must be nonmissing and nonnegative")
    return long.sort_values(["state", "year"]).reset_index(drop=True)


def load_smd_registry(path: Path = SMD_PATH) -> dict[int, set[str]]:
    """Derive each year's treated states from positive registered amounts."""
    amounts = load_smd_amounts(path)
    return {
        year: set(
            amounts.loc[(amounts["year"] == year) & (amounts["amount"] > 0), "state"]
        )
        for year in range(2017, 2025)
    }


class _LazySmdRegistry(Mapping[int, set[str]]):
    """Compatibility mapping that avoids reading external data at import time."""

    _data: dict[int, set[str]] | None = None

    def _load(self) -> dict[int, set[str]]:
        if self._data is None:
            self._data = load_smd_registry()
        return self._data

    def __getitem__(self, key: int) -> set[str]:
        return self._load()[key]

    def __iter__(self) -> Iterator[int]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())


# Retained for imports from the hurdle script; unlike the old constant, every
# value is derived from the amount CSV (for example, CA is untreated in 2017).
SMD_DOC: Mapping[int, set[str]] = _LazySmdRegistry()


def official_error_label(
    df: pd.DataFrame, threshold_map: Mapping[int, float] = THRESHOLD
) -> pd.Series:
    """Return the adjudicated above-threshold payment-error indicator."""
    assert_required_columns(
        df, ["STATUS", "AMTERR", "year"], context="official-error input"
    )
    thresholds = df["year"].map(threshold_map)
    if thresholds.isna().any():
        missing_years = sorted(df.loc[thresholds.isna(), "year"].unique())
        raise ValueError(f"Missing thresholds for fiscal years: {missing_years}")
    status = pd.to_numeric(df["STATUS"], errors="coerce")
    amount = pd.to_numeric(df["AMTERR"], errors="coerce")
    if status.isna().any() or amount.isna().any():
        raise ValueError("Official-error fields STATUS and AMTERR must be nonmissing")
    return (status.isin([2, 3]) & amount.gt(thresholds)).astype(int)


def _missing_indicator(f: pd.DataFrame, name: str, values: pd.Series) -> None:
    f[f"{name}_missing"] = values.isna().astype(int)


def _medical_payment_impact(df: pd.DataFrame) -> pd.Series:
    """Identify a medical variance with impact in the same detailed slot."""
    paired_columns = [
        name
        for i in FINDING_SLOTS
        for name in (f"ELEMENT{i}", f"E_FINDG{i}", f"AMOUNT{i}")
    ]
    assert_required_columns(df, paired_columns, context="medical finding input")
    paired = []
    for i in FINDING_SLOTS:
        paired.append(
            df[f"ELEMENT{i}"].eq(MEDICAL_ELEMENT)
            & df[f"E_FINDG{i}"].isin(IMPACT_FINDINGS)
            & df[f"AMOUNT{i}"].gt(0)
        )
    return pd.concat(paired, axis=1).any(axis=1)


def build_features(df: pd.DataFrame, smd_states: set[str]) -> pd.DataFrame:
    """Build outcomes, covariates, and recomputable burden intermediates."""
    assert_required_columns(df, REQUIRED_COLS + ["year", "state"])
    if not df["CASE"].eq(1).all():
        raise ValueError("build_features requires the CASE == 1 analysis universe")
    se_cols = _self_employment_columns(df.columns)
    f = pd.DataFrame(index=df.index)

    f["official_error"] = official_error_label(df)
    f["error"] = f["official_error"]  # compatibility with the original script
    f["signed_deviation"] = df["RAWBEN"] - df["BENFIX"]
    f["formula_benefit"] = df["FSBEN"]
    has_medical_impact = _medical_payment_impact(df)
    f["error_medical"] = (f["official_error"].astype(bool) & has_medical_impact).astype(
        int
    )
    f["w"] = df["HWGT"]
    f["year"] = df["year"]
    f["state"] = df["state"]

    # Household covariates. Continuous missing values remain NaN because the
    # histogram GBM handles them directly; explicit flags prevent missingness
    # from being silently treated as a substantive zero.
    size = df["CERTHHSZ"].combine_first(df["FSUSIZE"])
    f["size"] = size
    _missing_indicator(f, "size", size)
    ed_missing = df[["FSNELDER", "FSNDIS"]].isna().any(axis=1)
    f["elderly_disabled_missing"] = ed_missing.astype(int)
    # These two fields are counts. Zero after a missing value is used only for
    # the binary indicator and is paired with the missingness flag above.
    f["elderly_or_disabled"] = (
        df[["FSNELDER", "FSNDIS"]].fillna(0).sum(axis=1) > 0
    ).astype(int)
    for output, source in [
        ("earned", "FSEARN"),
        ("unearned", "FSUNEARN"),
        ("gross", "FSGRINC"),
    ]:
        f[output] = df[source]
        _missing_indicator(f, output, df[source])
    f["has_earnings"] = df["FSEARN"].gt(0).astype(int)
    f["children"] = df["FSNKID"].gt(0).astype(int)
    _missing_indicator(f, "children", df["FSNKID"])
    f["expedited"] = df["EXPEDSER"].lt(3).astype(int)
    _missing_indicator(f, "expedited", df["EXPEDSER"])
    _missing_indicator(f, "formula_benefit", df["FSBEN"])

    # Intermediates (documentation / verification / computation burden).
    medical_expense = df["FSMEDEXP"]
    claims_medical = medical_expense.gt(0)
    above_excess_floor = medical_expense.gt(35)
    f["claims_medical"] = claims_medical.astype(int)
    _missing_indicator(f, "claims_medical", medical_expense)
    f["medical_expense_above_floor"] = above_excess_floor.astype(int)
    smd = df["state"].isin(smd_states)
    f["med_doc_required"] = (
        above_excess_floor & f["elderly_or_disabled"].astype(bool) & ~smd
    ).astype(int)
    # Known limitation: this binary proxy does not incorporate the state's
    # standard amount, whether the standard binds for this household, or whether
    # actual expenses above the standard still require documents.

    se_values = df[se_cols]
    f["se_records_missing"] = se_values.isna().all(axis=1).astype(int)
    # Empty/nonmember person slots are structural zeroes in the public file;
    # after flagging an entirely missing row, zero-fill is appropriate here.
    f["se_records"] = se_values.fillna(0).gt(0).sum(axis=1).astype(int)
    f["se_aggregate_has_income"] = df["FSSLFEMP"].gt(0).astype(int)
    f["se_aggregate_mismatch"] = (
        f["se_records"].gt(0).ne(f["se_aggregate_has_income"].astype(bool))
    ).astype(int)

    f["utility_actuals_missing"] = df["SUA1"].isna().astype(int)
    f["utility_actuals"] = df["SUA1"].eq(2).astype(int)
    deduction_cols = ["FSMEDDED", "FSDEPDED", "FSCSDED", "FSSLTDED"]
    f["deduction_components_missing"] = (
        df[deduction_cols].isna().any(axis=1).astype(int)
    )
    # Missing components are treated as absent only for this count, alongside
    # the explicit flag above; observed positive components remain informative.
    f["deduction_count"] = df[deduction_cols].fillna(0).gt(0).sum(axis=1)

    benefit_position_missing = df[["FSBEN", "BENMAX", "MINIMUM_BEN"]].isna().any(axis=1)
    f["benefit_position_missing"] = benefit_position_missing.astype(int)
    ben_rel_max = df["FSBEN"] / df["BENMAX"].replace(0, np.nan)
    f["at_max"] = ben_rel_max.ge(0.999).astype(int)
    f["at_min"] = df["FSBEN"].le(df["MINIMUM_BEN"] + 0.5).astype(int)
    f["ben_rel_max"] = ben_rel_max.clip(0, 1.5)

    f["net_share_undefined"] = (
        df["FSNETINC"].isna() | df["FSGRINC"].isna() | df["FSGRINC"].le(0)
    ).astype(int)
    f["net_share_of_gross"] = (df["FSNETINC"] / df["FSGRINC"].replace(0, np.nan)).clip(
        0, 2
    )

    total_ded_cols = ["FSDEPDED", "FSCSDED", "FSSLTDED", "FSMEDDED", "FSERNDED"]
    f["deductions_missing"] = (
        df[total_ded_cols].isna().any(axis=1) | size.isna()
    ).astype(int)
    # Deduction fields are additive amounts, so missing components are excluded
    # only after recording that the constructed total is incomplete.
    total_ded = df[total_ded_cols].sum(axis=1, min_count=1)
    f["deductions_per_member"] = total_ded / size.clip(lower=1)
    return f


COVARIATES = [
    "size",
    "size_missing",
    "elderly_or_disabled",
    "elderly_disabled_missing",
    "has_earnings",
    "earned",
    "earned_missing",
    "unearned",
    "unearned_missing",
    "gross",
    "gross_missing",
    "year",
    "children",
    "children_missing",
    "expedited",
    "expedited_missing",
    "formula_benefit",
    "formula_benefit_missing",
]
INTERMEDIATES = [
    "claims_medical",
    "claims_medical_missing",
    "medical_expense_above_floor",
    "med_doc_required",
    "se_records",
    "se_records_missing",
    "utility_actuals",
    "utility_actuals_missing",
    "deduction_count",
    "deduction_components_missing",
    "at_max",
    "at_min",
    "ben_rel_max",
    "benefit_position_missing",
    "net_share_of_gross",
    "net_share_undefined",
    "deductions_per_member",
    "deductions_missing",
]


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    """Return a weighted mean after rejecting missing/nonpositive weights."""
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return float("nan")
    return float(np.average(values.loc[valid], weights=weights.loc[valid]))


def weighted_rate(values: pd.Series, weights: pd.Series) -> float:
    """Semantic alias for a weighted mean of an indicator."""
    return weighted_mean(values, weights)


def _prevalence(frame: pd.DataFrame, label: str = "error") -> dict[str, float | int]:
    return {
        "n": len(frame),
        "weighted": weighted_rate(frame[label], frame["w"]),
        "unweighted": float(frame[label].mean()),
        "weighted_population": float(frame["w"].sum()),
    }


def fit_score(
    train: pd.DataFrame,
    test: pd.DataFrame,
    cols: list[str],
    label: str,
) -> tuple[HistGradientBoostingClassifier, np.ndarray, dict[str, float]]:
    model = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.08,
        max_leaf_nodes=63,
        random_state=RANDOM_STATE,
    )
    model.fit(train[cols], train["error"], sample_weight=train["w"])
    probability = model.predict_proba(test[cols])[:, 1]
    auc = roc_auc_score(test["error"], probability, sample_weight=test["w"])
    average_precision = average_precision_score(
        test["error"], probability, sample_weight=test["w"]
    )
    order = np.argsort(-probability)
    sorted_weights = test["w"].to_numpy()[order]
    sorted_errors = test["error"].to_numpy()[order]
    cutoff = (
        int(np.searchsorted(np.cumsum(sorted_weights), 0.05 * sorted_weights.sum())) + 1
    )
    precision_at_budget = float(
        np.average(sorted_errors[:cutoff], weights=sorted_weights[:cutoff])
    )
    metrics = {
        "roc_auc": float(auc),
        "pr_auc": float(average_precision),
        "precision_at_5pct_weight_budget": precision_at_budget,
    }
    print(
        f"{label:<28} AUC {auc:.4f}  PR-AUC {average_precision:.4f}  "
        f"P@5%budget {precision_at_budget:.3f}"
    )
    return model, probability, metrics


def _medical_cell(frame: pd.DataFrame) -> dict[str, float | int]:
    return {
        "rate": weighted_rate(frame["error_medical"], frame["w"]),
        "event_count": int(frame["error_medical"].sum()),
        "weighted_event_count": float((frame["error_medical"] * frame["w"]).sum()),
        "n": len(frame),
        "weighted_population": float(frame["w"].sum()),
    }


def _change_pp(post: Mapping[str, float], pre: Mapping[str, float]) -> float:
    return 100 * (float(post["rate"]) - float(pre["rate"]))


def medical_descriptive_contrasts(
    data: pd.DataFrame, smd_amounts: pd.DataFrame
) -> dict[str, Any]:
    """Calculate calendar-aligned, non-causal SMD adoption contrasts."""
    assert_required_columns(
        data,
        [
            "year",
            "state",
            "elderly_or_disabled",
            "claims_medical",
            "error_medical",
            "w",
        ],
        context="medical contrast data",
    )
    assert_required_columns(
        smd_amounts, ["state", "year", "amount"], context="SMD contrast registry"
    )
    available_years = sorted(set(data["year"]))
    never = sorted(
        set(smd_amounts.loc[smd_amounts["amount"].le(0), "state"])
        - set(smd_amounts.loc[smd_amounts["amount"].gt(0), "state"])
        - {"GU", "VI"}
    )
    adoption_years = (
        smd_amounts.loc[smd_amounts["amount"].gt(0)]
        .groupby("state")["year"]
        .min()
        .astype(int)
    )
    adopters = {
        state: int(year)
        for state, year in adoption_years.items()
        if min(available_years) < year <= max(available_years)
    }
    adopters_without_pre_period = {
        state: int(year)
        for state, year in adoption_years.items()
        if year <= min(available_years)
    }

    populations = {
        "claimant_conditioned": data.loc[
            data["elderly_or_disabled"].eq(1) & data["claims_medical"].eq(1)
        ],
        "all_elderly_disabled": data.loc[data["elderly_or_disabled"].eq(1)],
    }
    population_labels = {
        "claimant_conditioned": (
            "post-treatment-conditioned elderly/disabled medical claimants"
        ),
        "all_elderly_disabled": (
            "stable denominator: all elderly/disabled households, claiming or not"
        ),
    }
    result: dict[str, Any] = {
        "interpretation": "descriptive weighted contrasts; not causal estimates",
        "population_labels": population_labels,
        "claimant_conditioning_note": (
            "This is explicitly post-treatment-conditioned: observed medical "
            "claiming may itself respond to SMD adoption."
        ),
        "calendar_window_rule": (
            "pre uses every available pre-adoption training year in "
            "{2017,2018,2019,2022,2023}; post uses every available year on or "
            "after adoption; controls use the identical calendar cells"
        ),
        "eligible_adopters": dict(sorted(adopters.items())),
        "adopters_without_pre_period": dict(
            sorted(adopters_without_pre_period.items())
        ),
        "never_treated_controls": never,
        "populations": {},
    }
    for population_name, population in populations.items():
        state_results: dict[str, Any] = {}
        for state, adoption_year in sorted(adopters.items()):
            pre_years = [
                y for y in available_years if y in YEARS_TRAIN and y < adoption_year
            ]
            post_years = [y for y in available_years if y >= adoption_year]
            if not pre_years or not post_years:
                continue
            state_rows = population.loc[population["state"].eq(state)]
            control_rows = population.loc[population["state"].isin(never)]
            state_pre = _medical_cell(
                state_rows.loc[state_rows["year"].isin(pre_years)]
            )
            state_post = _medical_cell(
                state_rows.loc[state_rows["year"].isin(post_years)]
            )
            control_pre = _medical_cell(
                control_rows.loc[control_rows["year"].isin(pre_years)]
            )
            control_post = _medical_cell(
                control_rows.loc[control_rows["year"].isin(post_years)]
            )
            state_change = _change_pp(state_post, state_pre)
            control_change = _change_pp(control_post, control_pre)
            state_results[state] = {
                "adoption_year": adoption_year,
                "pre_years": pre_years,
                "post_years": post_years,
                "state_pre": state_pre,
                "state_post": state_post,
                "control_pre": control_pre,
                "control_post": control_post,
                "state_change_pp": state_change,
                "control_change_pp": control_change,
                "descriptive_contrast_pp": state_change - control_change,
            }
        if set(state_results) != set(adopters):
            missing = sorted(set(adopters) - set(state_results))
            raise AssertionError(
                f"medical contrast output omitted eligible adopters: {missing}"
            )
        result["populations"][population_name] = state_results
    return result


def _cross_sectional_medical_rates(data: pd.DataFrame) -> dict[str, Any]:
    claimant = data.loc[
        data["claims_medical"].eq(1) & data["elderly_or_disabled"].eq(1)
    ]
    stable = data.loc[data["elderly_or_disabled"].eq(1)]
    return {
        "population_labels": {
            "claimant_conditioned": (
                "post-treatment-conditioned elderly/disabled medical claimants"
            ),
            "all_elderly_disabled": (
                "stable denominator: all elderly/disabled households, claiming or not"
            ),
        },
        "claimant_conditioned": {
            str(int(required)): _medical_cell(group)
            for required, group in claimant.groupby("med_doc_required")
        },
        "all_elderly_disabled": {
            str(int(required)): _medical_cell(group)
            for required, group in stable.groupby("med_doc_required")
        },
        "limitations": (
            "med_doc_required applies the $35 excess gate but does not incorporate "
            "the state standard amount, whether that standard binds, or whether "
            "actuals above the standard require documentation"
        ),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _provenance() -> dict[str, Any]:
    packages = {}
    for package in ["numpy", "pandas", "pyreadstat", "scikit-learn", "scipy"]:
        packages[package] = importlib.metadata.version(package)
    inputs = [QC_DIR / f"qc_pub_fy{year}.sav" for year in YEARS] + [SMD_PATH]
    return {
        "packages": packages,
        "input_sha256": {path.name: _sha256(path) for path in inputs},
        "threshold_map": {str(year): value for year, value in THRESHOLD.items()},
        "years_train": YEARS_TRAIN,
        "year_test": YEAR_TEST,
        "random_state": RANDOM_STATE,
        "case_filter": "CASE == 1",
        "official_error_label": "STATUS in {2,3} and AMTERR > fiscal-year threshold",
        "signed_deviation": "RAWBEN - BENFIX",
        "formula_benefit_feature": "FSBEN",
        "medical_outcome": (
            "official error and same-slot ELEMENTi == 365, "
            "E_FINDGi in {2,3,4}, AMOUNTi > 0, i=1..9"
        ),
        "person_self_employment_slots_by_year": {
            str(year): count for year, count in sorted(PERSON_SLOTS_BY_YEAR.items())
        },
        "smd_registry": str(SMD_PATH),
    }


def main() -> None:
    smd_amounts = load_smd_amounts()
    smd_registry = load_smd_registry()
    frames = []
    for year in YEARS:
        source = load_year(year)
        print(f"FY{year}: SMD registry {len(smd_registry[year])} states")
        frames.append(build_features(source, smd_registry[year]))
    data = pd.concat(frames, ignore_index=True)
    train = data.loc[data["year"].ne(YEAR_TEST)]
    test = data.loc[data["year"].eq(YEAR_TEST)]
    prevalence = {"train": _prevalence(train), "test": _prevalence(test)}
    print(
        f"\ntrain {len(train):,} cases "
        f"({prevalence['train']['unweighted']:.1%} unweighted / "
        f"{prevalence['train']['weighted']:.1%} weighted error), "
        f"test {len(test):,} "
        f"({prevalence['test']['unweighted']:.1%} / "
        f"{prevalence['test']['weighted']:.1%})"
    )

    print("\n== FY2024 evaluation ==")
    _, _, baseline = fit_score(
        train, test, COVARIATES, "covariates + formula anchor"
    )
    full_columns = COVARIATES + INTERMEDIATES
    full_model, _, full = fit_score(
        train, test, full_columns, "baseline + burden intermediates"
    )
    lift = {
        "roc_auc": full["roc_auc"] - baseline["roc_auc"],
        "pr_auc": full["pr_auc"] - baseline["pr_auc"],
        "precision_at_5pct_weight_budget": (
            full["precision_at_5pct_weight_budget"]
            - baseline["precision_at_5pct_weight_budget"]
        ),
    }
    print(f"lift: AUC {lift['roc_auc']:+.4f}, PR-AUC {lift['pr_auc']:+.4f}")

    importance = permutation_importance(
        full_model,
        test[full_columns],
        test["error"],
        scoring="roc_auc",
        n_repeats=5,
        random_state=RANDOM_STATE,
        sample_weight=test["w"],
    )
    importances = {
        column: {
            "mean_auc_decrease": float(importance.importances_mean[index]),
            "std": float(importance.importances_std[index]),
        }
        for index, column in enumerate(full_columns)
    }
    print("\ntop features (weighted AUC permutation importance on FY2024):")
    for column in sorted(
        importances,
        key=lambda name: importances[name]["mean_auc_decrease"],
        reverse=True,
    )[:8]:
        print(f"  {column:<28} {importances[column]['mean_auc_decrease']:+.4f}")

    cross_section = _cross_sectional_medical_rates(data)
    adoption_contrasts = medical_descriptive_contrasts(data, smd_amounts)
    se_cross_check = {
        "definition": (
            "positive income in any available SLFEMP1-18 slot compared with "
            "positive published FSSLFEMP aggregate"
        ),
        "mismatch_count": int(data["se_aggregate_mismatch"].sum()),
        "mismatch_weighted_rate": weighted_rate(
            data["se_aggregate_mismatch"], data["w"]
        ),
        "by_year": {
            str(int(year)): {
                "mismatch_count": int(group["se_aggregate_mismatch"].sum()),
                "mismatch_weighted_rate": weighted_rate(
                    group["se_aggregate_mismatch"], group["w"]
                ),
            }
            for year, group in data.groupby("year")
        },
    }
    print("\nmedical-error rates among elderly/disabled medical claimants:")
    for required, cell in cross_section["claimant_conditioned"].items():
        print(
            f"  med_doc_required={required}: {cell['rate']:.2%} "
            f"(events={cell['event_count']}, n={cell['n']:,})"
        )
    print("\n== SMD adoption descriptive weighted contrasts ==")
    for population_name, states in adoption_contrasts["populations"].items():
        print(adoption_contrasts["population_labels"][population_name])
        for state, result in states.items():
            print(
                f"  {state}: {result['state_pre']['rate']:.1%} "
                f"({result['state_pre']['event_count']} events) -> "
                f"{result['state_post']['rate']:.1%} "
                f"({result['state_post']['event_count']} events); "
                f"calendar-aligned contrast vs controls "
                f"{result['descriptive_contrast_pp']:+.1f}pp"
            )

    results = {
        "schema_version": 2,
        # Flat keys retained for consumers of the first committed schema.
        "auc_covariates": baseline["roc_auc"],
        "auc_with_intermediates": full["roc_auc"],
        "pr_covariates": baseline["pr_auc"],
        "pr_with_intermediates": full["pr_auc"],
        "p_at_5pct_budget_covariates": baseline["precision_at_5pct_weight_budget"],
        "p_at_5pct_budget_with_intermediates": full["precision_at_5pct_weight_budget"],
        "train_n": len(train),
        "test_n": len(test),
        "prevalence": prevalence,
        "models": {
            "covariates_only": baseline,
            "with_intermediates": full,
            "lift": lift,
        },
        "feature_sets": {
            "covariates": COVARIATES,
            "intermediates": INTERMEDIATES,
        },
        "smd_treatment_by_year": {
            str(year): {
                "treated_state_count": len(smd_registry[year]),
                "treated_states": sorted(smd_registry[year]),
            }
            for year in YEARS
        },
        "permutation_importance_weighted_roc_auc": importances,
        "self_employment_cross_check": se_cross_check,
        "medical_cross_section": cross_section,
        "smd_adoption_contrasts": adoption_contrasts,
        "provenance": _provenance(),
    }
    output_path = OUT / "model_results.json"
    with output_path.open("w") as output:
        json.dump(results, output, indent=2, allow_nan=False)
        output.write("\n")
    print(f"\nwrote {output_path}")


if __name__ == "__main__":
    main()
