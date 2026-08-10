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
from collections.abc import Collection, Iterator, Mapping
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
FEATURE_DATA_DIR = OUT / "data"
BBCE_PATH = FEATURE_DATA_DIR / "state_bbce.csv"
MEDICARE_PART_B_PATH = FEATURE_DATA_DIR / "medicare_part_b_premiums.csv"
YEARS_TRAIN = [2017, 2018, 2019, 2022, 2023]
YEAR_TEST = 2024
YEARS = YEARS_TRAIN + [YEAR_TEST]
SAMPLE_CALENDAR_YEARS = (2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024)
THRESHOLD = {2017: 38, 2018: 37, 2019: 37, 2022: 48, 2023: 54, 2024: 56}
RANDOM_STATE = 7
MEDICAL_EXPENSE_FLOOR = 35.0
PREMIUM_ONLY_TOLERANCE = 5.0
JUST_ABOVE_PREMIUM_MAX = 50.0
BAND_COMPARISON_EPSILON = 1e-9
BBCE_SOURCE_PANEL_SHA256 = (
    "3f3f035c7ded13996e43b1a43e7ec0e4a742bb17522d1f730edb0990aafe08cb"
)
BBCE_REPORT_URL = (
    "https://fns-prod.azureedge.us/sites/default/files/resource-files/"
    "snap-16th-state-options-report-june24.pdf"
)
BBCE_YEAR_SOURCES = {
    2017: {
        "edition": 13,
        "as_of": "2016-10-01",
        "basis": "report_snapshot",
    },
    2018: {
        "edition": 14,
        "as_of": "2017-10-01",
        "basis": "report_snapshot",
    },
    2019: {
        "edition": 14,
        "as_of": "2017-10-01",
        "basis": "carried_forward_no_intervening_report",
    },
    2022: {
        "edition": 15,
        "as_of": "2022-10-01",
        "basis": "end_of_fiscal_year_proxy",
    },
    2023: {
        "edition": 15,
        "as_of": "2022-10-01",
        "basis": "report_snapshot",
    },
    2024: {
        "edition": 16,
        "as_of": "2023-10-01",
        "basis": "report_snapshot",
    },
}
COMMITTED_BURDEN_BASELINE = {
    "roc_auc": 0.7666262908275983,
    "pr_auc": 0.3553041682372305,
    "precision_at_5pct_weight_budget": 0.47760784361005676,
    "commit": "900199db293bf4120d0ed711d18f4bbec724e7ee",
}
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
    "CERTMTH",
    "LASTCERT",
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
    "MED_DED_DEMO",
    "FSMEDDED",
    "FSDEPDED",
    "FSCSDED",
    "FSSLTDED",
    "FSSLFEMP",
    "SUA1",
    "BENMAX",
    "MINIMUM_BEN",
    "CASE",
    "CAT_ELIG",
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


def load_year(year: int, *, include_source_row_index: bool = False) -> pd.DataFrame:
    """Load and enforce the official ``CASE == 1`` QC universe for one year.

    ``include_source_row_index`` preserves the zero-based SAV row number used
    by the certified engine artifacts' case identifiers. It is metadata only
    and never enters the predictive feature set.
    """
    if year not in THRESHOLD:
        raise ValueError(f"No official payment-error threshold configured for FY{year}")
    path = QC_DIR / f"qc_pub_fy{year}.sav"
    df, _ = pyreadstat.read_sav(str(path))
    df.columns = [c.upper() for c in df.columns]
    if include_source_row_index:
        df["source_row_index"] = np.arange(len(df), dtype=np.int64)
    assert_required_columns(df, REQUIRED_COLS, context=f"FY{year} SAV")
    se_cols = _self_employment_columns(
        df.columns, expected_count=PERSON_SLOTS_BY_YEAR[year]
    )
    selected = REQUIRED_COLS + se_cols
    if include_source_row_index:
        selected = selected + ["source_row_index"]
    df = df[selected].copy()
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


def load_bbce_registry(path: Path = BBCE_PATH) -> dict[int, set[str]]:
    """Return the documented state BBCE registry for each model fiscal year."""
    wide = pd.read_csv(path, encoding="utf-8-sig")
    year_columns = [str(year) for year in YEARS]
    assert_required_columns(
        wide,
        ["state_name", *year_columns],
        context="BBCE registry",
    )
    if wide["state_name"].duplicated().any():
        duplicates = sorted(
            wide.loc[wide["state_name"].duplicated(), "state_name"].astype(str)
        )
        raise ValueError(f"Duplicate states in BBCE registry: {', '.join(duplicates)}")
    wide["state"] = wide["state_name"].map(STATE_NAME_TO_ABBR)
    if wide["state"].isna().any():
        names = sorted(wide.loc[wide["state"].isna(), "state_name"].astype(str))
        raise ValueError(f"Unrecognized states in BBCE registry: {', '.join(names)}")
    expected_states = set(FIPS.values())
    actual_states = set(wide["state"])
    if actual_states != expected_states:
        missing = sorted(expected_states - actual_states)
        extra = sorted(actual_states - expected_states)
        raise ValueError(
            f"BBCE registry state coverage mismatch: missing={missing}, extra={extra}"
        )
    values = wide[year_columns].apply(pd.to_numeric, errors="coerce")
    if values.isna().any().any() or not values.isin([0, 1]).all().all():
        raise ValueError("BBCE registry values must be nonmissing binary indicators")
    return {year: set(wide.loc[values[str(year)].eq(1), "state"]) for year in YEARS}


def load_medicare_part_b_premiums(
    path: Path = MEDICARE_PART_B_PATH,
    required_calendar_years: Collection[int] = SAMPLE_CALENDAR_YEARS,
) -> dict[int, float]:
    """Return exact standard monthly Part B premiums by calendar year."""
    data = pd.read_csv(path, encoding="utf-8-sig")
    assert_required_columns(
        data,
        ["calendar_year", "standard_monthly_premium", "source_url"],
        context="Medicare Part B registry",
    )
    years = pd.to_numeric(data["calendar_year"], errors="coerce")
    premiums = pd.to_numeric(data["standard_monthly_premium"], errors="coerce")
    if years.isna().any() or premiums.isna().any():
        raise ValueError("Medicare Part B years and premiums must be numeric")
    if not years.eq(np.floor(years)).all():
        raise ValueError("Medicare Part B calendar years must be whole numbers")
    years = years.astype(int)
    if years.duplicated().any():
        duplicates = sorted(years.loc[years.duplicated()].unique())
        raise ValueError(f"Duplicate years in Medicare Part B registry: {duplicates}")
    if not np.isfinite(premiums).all() or premiums.le(MEDICAL_EXPENSE_FLOOR).any():
        raise ValueError("Medicare Part B premiums must be finite and above $35")
    if (
        data["source_url"].isna().any()
        or not data["source_url"].str.startswith("https://www.cms.gov/").all()
    ):
        raise ValueError("Every Medicare Part B premium needs an official CMS URL")
    missing_years = sorted(set(required_calendar_years) - set(years))
    if missing_years:
        raise ValueError(
            "Medicare Part B registry is missing sampled calendar years: "
            f"{missing_years}"
        )
    return dict(zip(years, premiums.astype(float), strict=True))


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


def medical_documentation_required(
    medical_expense_above_floor: pd.Series,
    elderly_or_disabled: pd.Series,
    smd_applies: pd.Series,
) -> pd.Series:
    """Return the model's medical-documentation burden proxy.

    The proxy is one only when reported medical expense clears the strict
    ``$35`` excess gate, the household contains an elderly or disabled member,
    and a standard medical deduction does not apply. Keeping this predicate in
    one function prevents counterfactual joins from broadening the flip to all
    medical claimants or only the censored subset.
    """
    if not (
        medical_expense_above_floor.index.equals(elderly_or_disabled.index)
        and medical_expense_above_floor.index.equals(smd_applies.index)
    ):
        raise ValueError("medical-documentation inputs must share an index")
    return (
        medical_expense_above_floor.astype(bool)
        & elderly_or_disabled.astype(bool)
        & ~smd_applies.astype(bool)
    ).astype(int)


def _nonnegative_qc_numeric(values: pd.Series) -> pd.Series:
    """Coerce a nonnegative QC field and collapse restricted missing sentinels."""
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.mask(numeric.lt(0))


def build_certification_features(
    df: pd.DataFrame,
    elderly_or_disabled: pd.Series,
) -> pd.DataFrame:
    """Build case-level certification cadence features from public QC fields."""
    assert_required_columns(
        df,
        ["CERTMTH", "LASTCERT"],
        context="certification feature input",
    )
    if not df.index.equals(elderly_or_disabled.index):
        raise ValueError("certification inputs must share an index")

    result = pd.DataFrame(index=df.index)
    cert_period = _nonnegative_qc_numeric(df["CERTMTH"])
    months_since = _nonnegative_qc_numeric(df["LASTCERT"])
    source_missing = cert_period.isna() | months_since.isna()
    structurally_valid = (
        ~source_missing
        & cert_period.gt(0)
        & months_since.ge(0)
        & months_since.lt(cert_period)
    )
    near_recert = structurally_valid & months_since.ge(cert_period - 2)

    result["months_since_cert"] = months_since
    result["months_since_cert_missing"] = months_since.isna().astype(int)
    result["cert_period_months"] = cert_period
    result["cert_period_months_missing"] = cert_period.isna().astype(int)
    result["cert_timing_inconsistent"] = (~source_missing & ~structurally_valid).astype(
        int
    )
    result["near_recert"] = near_recert.astype(int)
    result["near_recert_missing"] = source_missing.astype(int)
    result["near_recert_elderly_or_disabled"] = (
        near_recert & elderly_or_disabled.astype(bool)
    ).astype(int)
    return result


def build_bbce_features(
    df: pd.DataFrame,
    bbce_states: set[str],
    elderly_or_disabled: pd.Series,
    has_earnings: pd.Series,
    children: pd.Series,
) -> pd.DataFrame:
    """Build official state-BBCE status and supported household interactions."""
    assert_required_columns(df, ["state"], context="BBCE feature input")
    inputs = [elderly_or_disabled, has_earnings, children]
    if any(not df.index.equals(values.index) for values in inputs):
        raise ValueError("BBCE feature inputs must share an index")
    unknown_registry_states = sorted(set(bbce_states) - set(FIPS.values()))
    if unknown_registry_states:
        raise ValueError(
            f"BBCE feature registry has unknown states: {unknown_registry_states}"
        )

    result = pd.DataFrame(index=df.index)
    state_valid = df["state"].isin(FIPS.values())
    state_bbce = state_valid & df["state"].isin(bbce_states)
    result["state_bbce"] = state_bbce.astype(int)
    result["state_bbce_missing"] = (~state_valid).astype(int)
    result["state_bbce_elderly_or_disabled"] = (
        state_bbce & elderly_or_disabled.astype(bool)
    ).astype(int)
    result["state_bbce_has_earnings"] = (state_bbce & has_earnings.astype(bool)).astype(
        int
    )
    result["state_bbce_children"] = (state_bbce & children.astype(bool)).astype(int)
    return result


def build_medicare_premium_features(
    df: pd.DataFrame,
    elderly_household: pd.Series,
    premiums_by_calendar_year: Mapping[int, float],
) -> pd.DataFrame:
    """Build elderly-household Part B bands on the QC excess-expense scale."""
    assert_required_columns(
        df,
        ["YRMONTH", "FSMEDEXP"],
        context="Medicare premium feature input",
    )
    if not df.index.equals(elderly_household.index):
        raise ValueError("Medicare premium inputs must share an index")
    if not premiums_by_calendar_year:
        raise ValueError("Medicare Part B premium registry cannot be empty")

    result = pd.DataFrame(index=df.index)
    yrmonth = _nonnegative_qc_numeric(df["YRMONTH"])
    whole_yrmonth = yrmonth.eq(np.floor(yrmonth))
    calendar_year = np.floor(yrmonth / 100).where(whole_yrmonth)
    calendar_month = yrmonth.mod(100).where(whole_yrmonth)
    valid_month = calendar_month.between(1, 12)
    calendar_year = calendar_year.where(valid_month)
    premium = calendar_year.map(premiums_by_calendar_year)

    medical_excess = _nonnegative_qc_numeric(df["FSMEDEXP"])
    has_allowable_expense = medical_excess.gt(0)
    applicable = (
        elderly_household.astype(bool) & has_allowable_expense & premium.notna()
    )
    # FSMEDEXP is already the allowable amount above SNAP's $35 floor. Add the
    # floor back before comparing with the published gross Part B premium.
    reconstructed_expense = (medical_excess + MEDICAL_EXPENSE_FLOOR).where(
        has_allowable_expense
    )
    signed_distance = reconstructed_expense - premium
    absolute_distance = signed_distance.abs().where(applicable)

    result["premium_only"] = (
        applicable
        & absolute_distance.le(PREMIUM_ONLY_TOLERANCE + BAND_COMPARISON_EPSILON)
    ).astype(int)
    result["just_above_premium"] = (
        applicable
        & signed_distance.gt(PREMIUM_ONLY_TOLERANCE + BAND_COMPARISON_EPSILON)
        & signed_distance.le(JUST_ABOVE_PREMIUM_MAX + BAND_COMPARISON_EPSILON)
    ).astype(int)
    result["medical_expense_distance_to_premium"] = absolute_distance
    result["part_b_premium_missing"] = premium.isna().astype(int)

    # Diagnostics retained outside the model feature lists.
    result["part_b_premium_reference"] = premium
    result["reconstructed_medical_expense"] = reconstructed_expense
    result["part_b_band_applicable"] = applicable.astype(int)
    result["naive_literal_premium_only"] = (
        applicable
        & (medical_excess - premium)
        .abs()
        .le(PREMIUM_ONLY_TOLERANCE + BAND_COMPARISON_EPSILON)
    ).astype(int)
    return result


def build_features(
    df: pd.DataFrame,
    smd_states: set[str],
    bbce_states: set[str] | None = None,
    premiums_by_calendar_year: Mapping[int, float] | None = None,
) -> pd.DataFrame:
    """Build outcomes, covariates, and recomputable burden intermediates."""
    assert_required_columns(df, REQUIRED_COLS + ["year", "state"])
    if not df["CASE"].eq(1).all():
        raise ValueError("build_features requires the CASE == 1 analysis universe")
    se_cols = _self_employment_columns(df.columns)
    if bbce_states is None:
        years = pd.to_numeric(df["year"], errors="coerce").dropna().unique()
        if len(years) != 1 or int(years[0]) not in YEARS:
            raise ValueError(
                "build_features needs one supported fiscal year when BBCE states "
                "are not supplied"
            )
        bbce_states = load_bbce_registry()[int(years[0])]
    if premiums_by_calendar_year is None:
        premiums_by_calendar_year = load_medicare_part_b_premiums()
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
    elderly_count = _nonnegative_qc_numeric(df["FSNELDER"])
    disabled_count = _nonnegative_qc_numeric(df["FSNDIS"])
    ed_missing = elderly_count.isna() | disabled_count.isna()
    f["elderly_disabled_missing"] = ed_missing.astype(int)
    # These two fields are counts. Zero after a missing value is used only for
    # the binary indicator and is paired with the missingness flag above.
    elderly_household = elderly_count.fillna(0).gt(0)
    f["elderly_household_diagnostic"] = elderly_household.astype(int)
    f["elderly_or_disabled"] = (
        elderly_household | disabled_count.fillna(0).gt(0)
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

    certification = build_certification_features(df, f["elderly_or_disabled"])
    bbce = build_bbce_features(
        df,
        bbce_states,
        f["elderly_or_disabled"],
        f["has_earnings"],
        f["children"],
    )
    f = f.join(certification).join(bbce)
    cat_elig = _nonnegative_qc_numeric(df["CAT_ELIG"])
    # CAT_ELIG codes 2/3 are not unique BBCE identifiers. This diagnostic
    # supports a registry cross-check but is intentionally not a model feature.
    f["cat_elig_bbce_like_diagnostic"] = cat_elig.isin([2, 3]).astype(int)
    f["cat_elig_missing_diagnostic"] = cat_elig.isna().astype(int)

    # Intermediates (documentation / verification / computation burden).
    medical_expense = _nonnegative_qc_numeric(df["FSMEDEXP"])
    claims_medical = medical_expense.gt(0)
    above_excess_floor = medical_expense.gt(35)
    f["claims_medical"] = claims_medical.astype(int)
    _missing_indicator(f, "claims_medical", medical_expense)
    f["medical_expense_above_floor"] = above_excess_floor.astype(int)
    smd = df["state"].isin(smd_states)
    f["med_doc_required"] = medical_documentation_required(
        f["medical_expense_above_floor"],
        f["elderly_or_disabled"],
        smd,
    )
    premium = build_medicare_premium_features(
        df,
        elderly_household,
        premiums_by_calendar_year,
    )
    f = f.join(premium)
    medical_demo = _nonnegative_qc_numeric(df["MED_DED_DEMO"])
    f["medical_deduction_demo_diagnostic"] = medical_demo.eq(1).astype(int)
    f["co_smd_censored_165_diagnostic"] = (
        df["state"].eq("CO") & medical_demo.eq(1) & medical_expense.eq(165)
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
BURDEN_INTERMEDIATES = [
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
CERTIFICATION_FEATURES = [
    "months_since_cert",
    "months_since_cert_missing",
    "cert_period_months",
    "cert_period_months_missing",
    "cert_timing_inconsistent",
    "near_recert",
    "near_recert_missing",
    "near_recert_elderly_or_disabled",
]
BBCE_FEATURES = [
    "state_bbce",
    "state_bbce_missing",
    "state_bbce_elderly_or_disabled",
    "state_bbce_has_earnings",
    "state_bbce_children",
]
MEDICARE_PREMIUM_FEATURES = [
    "premium_only",
    "just_above_premium",
    "medical_expense_distance_to_premium",
    "part_b_premium_missing",
]
ADDITIVE_FEATURES = CERTIFICATION_FEATURES + BBCE_FEATURES + MEDICARE_PREMIUM_FEATURES
INTERMEDIATES = BURDEN_INTERMEDIATES + ADDITIVE_FEATURES


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


def certification_feature_summary(data: pd.DataFrame) -> dict[str, Any]:
    """Return coverage and cadence diagnostics for the certification family."""
    assert_required_columns(
        data,
        [
            "year",
            "w",
            "elderly_or_disabled",
            "months_since_cert_missing",
            "cert_period_months",
            "cert_period_months_missing",
            "cert_timing_inconsistent",
            "near_recert",
        ],
        context="certification summary input",
    )

    def summarize(frame: pd.DataFrame) -> dict[str, float | int]:
        valid_period = frame["cert_period_months"].gt(0)
        elderly_valid = valid_period & frame["elderly_or_disabled"].eq(1)
        return {
            "n": len(frame),
            "months_since_cert_missing_n": int(
                frame["months_since_cert_missing"].sum()
            ),
            "cert_period_months_missing_n": int(
                frame["cert_period_months_missing"].sum()
            ),
            "cert_timing_inconsistent_n": int(frame["cert_timing_inconsistent"].sum()),
            "near_recert_n": int(frame["near_recert"].sum()),
            "near_recert_weighted_rate": weighted_rate(
                frame["near_recert"], frame["w"]
            ),
            "valid_period_n": int(valid_period.sum()),
            "period_24_plus_rate_valid": float(
                frame.loc[valid_period, "cert_period_months"].ge(24).mean()
            ),
            "elderly_disabled_period_24_plus_rate_valid": float(
                frame.loc[elderly_valid, "cert_period_months"].ge(24).mean()
            ),
        }

    return {
        "definition": (
            "near_recert is CERTMTH - 2 <= LASTCERT < CERTMTH, with "
            "CERTMTH > 0 and both fields observed"
        ),
        "all_years": summarize(data),
        "by_year": {
            str(int(year)): summarize(group) for year, group in data.groupby("year")
        },
        "state_elderly_cadence_registry": (
            "not built: techdoc 24-48 month values identify SSI-CAP/NYSNIP "
            "cases and do not define statewide elderly certification policy"
        ),
    }


def bbce_registry_cross_check(data: pd.DataFrame) -> dict[str, Any]:
    """Compare official state status with non-unique case CAT_ELIG patterns."""
    assert_required_columns(
        data,
        [
            "year",
            "w",
            "state_bbce",
            "state_bbce_missing",
            "cat_elig_bbce_like_diagnostic",
            "cat_elig_missing_diagnostic",
        ],
        context="BBCE cross-check input",
    )
    by_year: dict[str, Any] = {}
    for year, group in data.groupby("year"):
        cells: dict[str, Any] = {}
        for status in (0, 1):
            cell = group.loc[group["state_bbce"].eq(status)]
            cells[str(status)] = {
                "n": len(cell),
                "cat_elig_2_or_3_n": int(cell["cat_elig_bbce_like_diagnostic"].sum()),
                "cat_elig_2_or_3_weighted_rate": weighted_rate(
                    cell["cat_elig_bbce_like_diagnostic"], cell["w"]
                ),
            }
        by_year[str(int(year))] = {
            "registered_bbce_case_n": int(group["state_bbce"].sum()),
            "state_status_missing_n": int(group["state_bbce_missing"].sum()),
            "cat_elig_missing_n": int(group["cat_elig_missing_diagnostic"].sum()),
            "case_pattern_by_state_status": cells,
        }
    return {
        "interpretation": (
            "diagnostic only: CAT_ELIG codes 2/3 include BBCE but do not "
            "uniquely identify state adoption and are excluded from models"
        ),
        "year_sources": {
            str(year): values for year, values in BBCE_YEAR_SOURCES.items()
        },
        "by_year": by_year,
    }


def medicare_premium_feature_summary(data: pd.DataFrame) -> dict[str, Any]:
    """Return FY2024 band coverage and Colorado SMD-censoring overlap."""
    required = [
        "year",
        "w",
        "premium_only",
        "just_above_premium",
        "part_b_band_applicable",
        "part_b_premium_reference",
        "naive_literal_premium_only",
        "elderly_household_diagnostic",
        "medical_deduction_demo_diagnostic",
        "co_smd_censored_165_diagnostic",
    ]
    assert_required_columns(data, required, context="Medicare summary input")
    fy2024 = data.loc[data["year"].eq(YEAR_TEST)]
    if fy2024.empty:
        raise ValueError("Medicare summary requires FY2024 rows")

    applicable = fy2024["part_b_band_applicable"].eq(1)
    premium_only = fy2024["premium_only"].eq(1)
    just_above = fy2024["just_above_premium"].eq(1)
    demo = fy2024["medical_deduction_demo_diagnostic"].eq(1)
    censored = fy2024["co_smd_censored_165_diagnostic"].eq(1)
    censored_elderly = censored & fy2024["elderly_household_diagnostic"].eq(1)
    naive = fy2024["naive_literal_premium_only"].eq(1)

    def band(mask: pd.Series) -> dict[str, float | int]:
        return {
            "n": int(mask.sum()),
            "weighted_population": float(fy2024.loc[mask, "w"].sum()),
            "share_of_applicable_n": float(mask.sum() / applicable.sum()),
            "smd_demo_overlap_n": int((mask & demo).sum()),
        }

    censored_n = int(censored.sum())
    censored_elderly_n = int(censored_elderly.sum())
    just_above_censored_n = int((censored & just_above).sum())
    return {
        "fiscal_year": YEAR_TEST,
        "definition": (
            "reconstruct gross expense as FSMEDEXP + 35 for positive claims; "
            "for households with FSNELDER > 0, compare with the standard Part B "
            "premium selected by YRMONTH"
        ),
        "population": "elderly households (FSNELDER > 0), excluding disabled-only",
        "premium_only_tolerance_dollars": PREMIUM_ONLY_TOLERANCE,
        "just_above_signed_distance_dollars": [
            PREMIUM_ONLY_TOLERANCE,
            JUST_ABOVE_PREMIUM_MAX,
        ],
        "applicable_n": int(applicable.sum()),
        "reference_counts": {
            f"{float(reference):.2f}": len(group)
            for reference, group in fy2024.groupby("part_b_premium_reference")
        },
        "premium_only": band(premium_only),
        "just_above_premium": band(just_above),
        "co_smd_censored_165": {
            "n": censored_n,
            "elderly_household_n": censored_elderly_n,
            "nonelderly_household_n": censored_n - censored_elderly_n,
            "premium_only_overlap_n": int((censored & premium_only).sum()),
            "premium_only_overlap_rate": float(
                (censored & premium_only).sum() / censored_n
            ),
            "just_above_premium_overlap_n": just_above_censored_n,
            "just_above_premium_overlap_rate": float(
                just_above_censored_n / censored_n
            ),
            "just_above_premium_overlap_rate_among_elderly": float(
                just_above_censored_n / censored_elderly_n
            ),
            "naive_literal_overlap_n": int((censored & naive).sum()),
            "naive_literal_overlap_rate": float((censored & naive).sum() / censored_n),
        },
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
    inputs = [QC_DIR / f"qc_pub_fy{year}.sav" for year in YEARS] + [
        SMD_PATH,
        BBCE_PATH,
        MEDICARE_PART_B_PATH,
    ]
    premium_sources = pd.read_csv(MEDICARE_PART_B_PATH).set_index("calendar_year")[
        "source_url"
    ]
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
        "bbce_registry": {
            "path": str(BBCE_PATH),
            "official_fy2024_report_url": BBCE_REPORT_URL,
            "official_pdf_sha256": None,
            "official_pdf_sha256_note": (
                "not available: the execution sandbox exposed parsed PDF text "
                "but blocked raw-byte download; registry and extracted-panel "
                "hashes remain pinned"
            ),
            "source_extracted_panel_sha256": BBCE_SOURCE_PANEL_SHA256,
            "year_sources": {
                str(year): values for year, values in BBCE_YEAR_SOURCES.items()
            },
        },
        "medicare_part_b_registry": {
            "path": str(MEDICARE_PART_B_PATH),
            "calendar_year_sources": {
                str(int(year)): url for year, url in premium_sources.items()
            },
            "qc_expense_scale": "FSMEDEXP + 35 for positive allowable expenses",
        },
    }


def main() -> None:
    smd_amounts = load_smd_amounts()
    smd_registry = load_smd_registry()
    bbce_registry = load_bbce_registry()
    part_b_premiums = load_medicare_part_b_premiums()
    frames = []
    for year in YEARS:
        source = load_year(year)
        print(
            f"FY{year}: SMD registry {len(smd_registry[year])} states; "
            f"BBCE registry {len(bbce_registry[year])} states"
        )
        frames.append(
            build_features(
                source,
                smd_registry[year],
                bbce_registry[year],
                part_b_premiums,
            )
        )
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
    _, _, baseline = fit_score(train, test, COVARIATES, "covariates + formula anchor")
    burden_columns = COVARIATES + BURDEN_INTERMEDIATES
    _, _, burden = fit_score(
        train,
        test,
        burden_columns,
        "baseline + burden intermediates",
    )
    full_columns = COVARIATES + INTERMEDIATES
    full_model, _, full = fit_score(
        train, test, full_columns, "burden + three additive families"
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
    additive_lift = {
        metric: full[metric] - burden[metric]
        for metric in (
            "roc_auc",
            "pr_auc",
            "precision_at_5pct_weight_budget",
        )
    }
    committed_delta = {
        metric: full[metric] - float(COMMITTED_BURDEN_BASELINE[metric])
        for metric in (
            "roc_auc",
            "pr_auc",
            "precision_at_5pct_weight_budget",
        )
    }
    burden_reproduction_delta = {
        metric: burden[metric] - float(COMMITTED_BURDEN_BASELINE[metric])
        for metric in (
            "roc_auc",
            "pr_auc",
            "precision_at_5pct_weight_budget",
        )
    }
    print(
        "additive vs committed burden baseline: "
        f"AUC {committed_delta['roc_auc']:+.4f}, "
        f"PR-AUC {committed_delta['pr_auc']:+.4f}"
    )

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
    certification_summary = certification_feature_summary(data)
    bbce_cross_check = bbce_registry_cross_check(data)
    medicare_summary = medicare_premium_feature_summary(data)
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
        "schema_version": 3,
        # Schema v3 distinguishes the frozen burden-only comparison from the
        # complete intermediate set. The legacy ``with_intermediates`` alias is
        # retained, but explicit additive names are preferred by new consumers.
        "auc_covariates": baseline["roc_auc"],
        "auc_with_intermediates": full["roc_auc"],
        "auc_with_additive_features": full["roc_auc"],
        "auc_with_burden_intermediates": burden["roc_auc"],
        "pr_covariates": baseline["pr_auc"],
        "pr_with_intermediates": full["pr_auc"],
        "pr_with_additive_features": full["pr_auc"],
        "pr_with_burden_intermediates": burden["pr_auc"],
        "p_at_5pct_budget_covariates": baseline["precision_at_5pct_weight_budget"],
        "p_at_5pct_budget_with_intermediates": full["precision_at_5pct_weight_budget"],
        "p_at_5pct_budget_with_additive_features": full[
            "precision_at_5pct_weight_budget"
        ],
        "train_n": len(train),
        "test_n": len(test),
        "prevalence": prevalence,
        "models": {
            "covariates_only": baseline,
            "with_burden_intermediates": burden,
            "with_intermediates": full,
            "with_additive_features": full,
            "lift": lift,
            "additive_lift_over_refit_burden": additive_lift,
            "additive_lift_over_committed_burden": committed_delta,
            "committed_burden_baseline": COMMITTED_BURDEN_BASELINE,
            "refit_burden_reproduction_delta": burden_reproduction_delta,
        },
        "feature_sets": {
            "covariates": COVARIATES,
            "burden_intermediates": BURDEN_INTERMEDIATES,
            "certification": CERTIFICATION_FEATURES,
            "bbce": BBCE_FEATURES,
            "medicare_premium": MEDICARE_PREMIUM_FEATURES,
            "additive": ADDITIVE_FEATURES,
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
        "certification_features": certification_summary,
        "bbce_registry_cross_check": bbce_cross_check,
        "medicare_premium_features": medicare_summary,
        "provenance": _provenance(),
    }
    output_path = OUT / "model_results.json"
    with output_path.open("w") as output:
        json.dump(results, output, indent=2, allow_nan=False)
        output.write("\n")
    print(f"\nwrote {output_path}")


if __name__ == "__main__":
    main()
