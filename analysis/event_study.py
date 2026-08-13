"""Estimate the protocol-frozen SNAP system-migration event study."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyreadstat

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name("event_study_results.json")
AUDIT_PATH = Path(__file__).with_name("coding_consistency.json")
CAUSE_PATH = Path(__file__).with_name("cause_shares.json")
MIGRATION_PATH = Path(__file__).with_name("system_migrations.json")
QC_DIR = Path.home() / ".cache/axiom-oracles/snap_qc_repo/qc_data"

YEARS = tuple(range(2017, 2025))
OUTCOMES = (
    "strict_computing_dollars_per_case_month",
    "total_error_rate",
    "client_dollars_per_case_month",
)
CPI_U = {
    2017: 245.120,
    2018: 251.107,
    2019: 255.657,
    2020: 258.811,
    2021: 270.970,
    2022: 292.655,
    2023: 304.702,
    2024: 313.689,
}
STRICT_CODES = frozenset({17, 19, 20})
TREATED_STATE = "OR"
TREATMENT_YEAR = 2021
REGISTRY_EXCLUSIONS = frozenset({"RI", "KY", "GA", "OR", "NC", "FL", "NM", "IN", "CO"})
DELAY_ROSTER_EXCLUSIONS = frozenset(
    {"AK", "DC", "DE", "FL", "GA", "IL", "MA", "MD", "NJ", "NM", "NY", "OR"}
)
TERRITORIES = frozenset({"GU", "VI"})
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

SPECIFICATIONS = {
    "primary_drop_fy2021": {
        "pre_years": [2017, 2018, 2019, 2020],
        "post_years": [2022, 2023, 2024],
    },
    "include_fy2021_as_treated": {
        "pre_years": [2017, 2018, 2019, 2020],
        "post_years": [2021, 2022, 2023, 2024],
    },
    "drop_fy2020_and_fy2021": {
        "pre_years": [2017, 2018, 2019],
        "post_years": [2022, 2023, 2024],
    },
}


def _sha256(path: Path) -> str:
    """Return a file SHA-256 digest."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def raw_inputs_available() -> bool:
    """Return whether all hash-audited raw inputs are locally available."""
    audit = json.loads(AUDIT_PATH.read_text())
    return all((QC_DIR / f"qc_pub_fy{year}.sav").is_file() for year in YEARS) and all(
        _sha256(QC_DIR / f"qc_pub_fy{year}.sav")
        == audit["years"][str(year)]["source"]["sha256"]
        for year in YEARS
    )


def _client_codes() -> frozenset[int]:
    reference = json.loads(CAUSE_PATH.read_text())
    return frozenset(
        int(code)
        for code, details in reference["cause_codes"].items()
        if details["class"] == "client_or_fact"
    )


def build_panel() -> pd.DataFrame:
    """Build the state-year outcome panel from hash-verified public SAV files."""
    audit = json.loads(AUDIT_PATH.read_text())
    client_codes = _client_codes()
    required = ["STATE", "CASE", "STATUS", "HWGT", "RAWBEN", "AMTERR"] + [
        f"AGENCY{slot}" for slot in range(1, 10)
    ]
    rows: list[dict[str, Any]] = []
    for year in YEARS:
        path = QC_DIR / f"qc_pub_fy{year}.sav"
        expected_hash = audit["years"][str(year)]["source"]["sha256"]
        if not path.is_file() or _sha256(path) != expected_hash:
            raise FileNotFoundError(f"Missing or hash-mismatched audited input: {path}")
        frame, _ = pyreadstat.read_sav(
            str(path), apply_value_formats=False, usecols=required
        )
        frame = frame.loc[frame["CASE"].eq(1) & frame["HWGT"].gt(0)].copy()
        frame["state"] = frame["STATE"].astype(int).map(FIPS)
        if frame["state"].isna().any():
            raise ValueError(f"FY{year} has an unmapped state code")
        agency = frame[[f"AGENCY{slot}" for slot in range(1, 10)]]
        threshold = 56.0 * CPI_U[year] / CPI_U[2024]
        counted = frame["STATUS"].isin((2, 3)) & frame["AMTERR"].gt(threshold)
        frame["strict_dollars"] = (
            frame["HWGT"]
            * frame["AMTERR"]
            * (counted & agency.isin(STRICT_CODES).any(axis=1))
        )
        frame["client_dollars"] = (
            frame["HWGT"]
            * frame["AMTERR"]
            * (counted & agency.isin(client_codes).any(axis=1))
        )
        frame["error_dollars"] = frame["HWGT"] * frame["AMTERR"] * counted
        frame["issuance"] = frame["HWGT"] * frame["RAWBEN"]
        grouped = frame.groupby("state", sort=True).agg(
            case_months=("HWGT", "sum"),
            issuance=("issuance", "sum"),
            strict_dollars=("strict_dollars", "sum"),
            error_dollars=("error_dollars", "sum"),
            client_dollars=("client_dollars", "sum"),
        )
        for state, values in grouped.iterrows():
            rows.append(
                {
                    "state": state,
                    "year": year,
                    "strict_computing_dollars_per_case_month": (
                        values.strict_dollars / values.case_months
                    ),
                    "total_error_rate": 100.0 * values.error_dollars / values.issuance,
                    "client_dollars_per_case_month": (
                        values.client_dollars / values.case_months
                    ),
                }
            )
    panel = pd.DataFrame(rows)
    expected = {(state, year) for state in FIPS.values() for year in YEARS}
    observed = set(zip(panel["state"], panel["year"], strict=True))
    if observed != expected:
        raise ValueError("Raw files do not form the expected balanced state-year panel")
    return panel.sort_values(["state", "year"]).reset_index(drop=True)


def donor_pool(panel: pd.DataFrame) -> list[str]:
    """Return the protocol-frozen donor pool present in the panel."""
    excluded = REGISTRY_EXCLUSIONS | DELAY_ROSTER_EXCLUSIONS | TERRITORIES
    return sorted(set(panel["state"]) - excluded)


def _wide(panel: pd.DataFrame, outcome: str) -> pd.DataFrame:
    return panel.pivot(index="year", columns="state", values=outcome).sort_index()


def fit_weights(
    panel: pd.DataFrame, treated: str, donors: list[str], pre_years: list[int]
) -> dict[str, float]:
    """Fit deterministic nonnegative synthetic weights jointly across outcomes."""
    if treated in donors or not donors:
        raise ValueError("Treated state must be separate from a nonempty donor pool")
    target_blocks = []
    donor_blocks = []
    for outcome in OUTCOMES:
        wide = _wide(panel, outcome).loc[pre_years]
        scale = float(wide[donors].stack().std(ddof=0))
        if not np.isfinite(scale) or scale == 0:
            scale = 1.0
        target_blocks.append(wide[treated].to_numpy(dtype=float) / scale)
        donor_blocks.append(wide[donors].to_numpy(dtype=float) / scale)
    target = np.concatenate(target_blocks)
    design = np.vstack(donor_blocks)
    weights = np.full(len(donors), 1.0 / len(donors))
    spectral_norm = float(np.linalg.norm(design, ord=2))
    step = 1.0 / (2.0 * spectral_norm**2) if spectral_norm else 1.0
    for _ in range(50_000):
        previous = weights
        gradient = 2.0 * design.T @ (design @ weights - target)
        candidate = weights - step * gradient
        ordered = np.sort(candidate)[::-1]
        cumulative = np.cumsum(ordered) - 1.0
        valid = ordered - cumulative / np.arange(1, len(ordered) + 1) > 0
        rho = int(np.flatnonzero(valid)[-1])
        theta = cumulative[rho] / (rho + 1)
        weights = np.maximum(candidate - theta, 0.0)
        if np.max(np.abs(weights - previous)) < 1e-13:
            break
    return {state: float(weight) for state, weight in zip(donors, weights, strict=True)}


def _estimate(
    panel: pd.DataFrame,
    treated: str,
    donors: list[str],
    pre_years: list[int],
    post_years: list[int],
) -> dict[str, Any]:
    weights = fit_weights(panel, treated, donors, pre_years)
    result: dict[str, Any] = {"donor_weights": weights, "outcomes": {}}
    for outcome in OUTCOMES:
        wide = _wide(panel, outcome)
        synthetic = wide[list(weights)] @ pd.Series(weights)
        gap = wide[treated] - synthetic
        did = float(gap.loc[post_years].mean() - gap.loc[pre_years].mean())
        pre_rmspe = float(np.sqrt(np.mean(np.square(gap.loc[pre_years]))))
        result["outcomes"][outcome] = {
            "effect": did,
            "pre_rmspe": pre_rmspe,
            "path": [
                {
                    "year": int(year),
                    "event_time": int(year - TREATMENT_YEAR),
                    "treated": float(wide.loc[year, treated]),
                    "synthetic_donor": float(synthetic.loc[year]),
                    "gap": float(gap.loc[year]),
                }
                for year in YEARS
            ],
        }
    return result


def _permutation_inference(
    panel: pd.DataFrame,
    treated_result: dict[str, Any],
    donors: list[str],
    pre_years: list[int],
    post_years: list[int],
) -> dict[str, Any]:
    placebo_effects = {outcome: {} for outcome in OUTCOMES}
    for pseudo_treated in donors:
        pseudo_donors = [state for state in donors if state != pseudo_treated]
        estimate = _estimate(
            panel, pseudo_treated, pseudo_donors, pre_years, post_years
        )
        for outcome in OUTCOMES:
            placebo_effects[outcome][pseudo_treated] = estimate["outcomes"][outcome][
                "effect"
            ]
    inference = {}
    for outcome in OUTCOMES:
        effect = treated_result["outcomes"][outcome]["effect"]
        extreme = sum(
            abs(placebo) >= abs(effect) for placebo in placebo_effects[outcome].values()
        )
        inference[outcome] = {
            "absolute_rank": 1 + extreme,
            "rank_denominator": 1 + len(donors),
            "p_value": (1 + extreme) / (1 + len(donors)),
            "placebo_effects": placebo_effects[outcome],
        }
    return inference


def _ga_descriptive(
    panel: pd.DataFrame, primary_weights: dict[str, float]
) -> dict[str, Any]:
    result = {
        "status": "descriptive_only_no_clean_in_panel_preperiod",
        "treatment_date": "2017-02-06 pilot; statewide completion NEEDS_VERIFICATION",
        "outcomes": {},
    }
    for outcome in OUTCOMES:
        wide = _wide(panel, outcome)
        synthetic = wide[list(primary_weights)] @ pd.Series(primary_weights)
        result["outcomes"][outcome] = {
            "path": [
                {
                    "year": int(year),
                    "event_time": int(year - 2017),
                    "treated": float(wide.loc[year, "GA"]),
                    "synthetic_donor": float(synthetic.loc[year]),
                    "gap": float(wide.loc[year, "GA"] - synthetic.loc[year]),
                }
                for year in YEARS
            ]
        }
    return result


def build_results(panel: pd.DataFrame) -> dict[str, Any]:
    """Build the complete deterministic results payload from a balanced panel."""
    donors = donor_pool(panel)
    estimates = {}
    for name, years in SPECIFICATIONS.items():
        estimates[name] = _estimate(
            panel,
            TREATED_STATE,
            donors,
            years["pre_years"],
            years["post_years"],
        )
        estimates[name]["pre_years"] = years["pre_years"]
        estimates[name]["post_years"] = years["post_years"]
    primary = estimates["primary_drop_fy2021"]
    inference = _permutation_inference(
        panel,
        primary,
        donors,
        SPECIFICATIONS["primary_drop_fy2021"]["pre_years"],
        SPECIFICATIONS["primary_drop_fy2021"]["post_years"],
    )
    strict_p = inference["strict_computing_dollars_per_case_month"]["p_value"]
    placebo_p = inference["client_dollars_per_case_month"]["p_value"]
    verdict = (
        "signal"
        if strict_p < 0.10 and placebo_p >= 0.10
        else "no_protocol_defined_signal"
    )
    return {
        "schema": "snap_qc_sim.event_study.v1",
        "scope": {
            "primary_treated_state": "OR",
            "treatment_fiscal_year": 2021,
            "panel_years": list(YEARS),
            "donor_pool": donors,
            "excluded_edge_events": ["KY", "RI"],
            "ga_status": "sensitivity_only_statewide_completion_NEEDS_VERIFICATION",
            "framing": "one-state bundled-system-replacement event study; not a literature-grade ATT",
        },
        "outcome_definitions": {
            "fixed_real_threshold_2024_dollars": 56.0,
            "cpi_u_annual_average": {str(year): value for year, value in CPI_U.items()},
            "strict_codes": sorted(STRICT_CODES),
            "client_codes": sorted(_client_codes()),
        },
        "specifications": estimates,
        "permutation_inference": inference,
        "georgia_sensitivity": _ga_descriptive(panel, primary["donor_weights"]),
        "decision": {
            "rule": "strict permutation p < 0.10 and client placebo p >= 0.10",
            "strict_p_value": strict_p,
            "client_placebo_p_value": placebo_p,
            "verdict": verdict,
            "adoption_gate": False,
        },
    }


def serialize_results(payload: dict[str, Any]) -> bytes:
    """Serialize results with stable ordering and numeric precision."""
    return (
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def main() -> None:
    """Regenerate the event-study results artifact."""
    OUT.write_bytes(serialize_results(build_results(build_panel())))


if __name__ == "__main__":
    main()
