"""Estimate the protocol-frozen Rhode Island UHIP cause decomposition."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyreadstat

from analysis import event_study

PROTOCOL_PATH = Path(__file__).with_name("UHIP_DECOMPOSITION_PROTOCOL.md")
OUT = Path(__file__).with_name("uhip_decomposition_results.json")
MEMO_OUT = Path(__file__).with_name("UHIP_DECOMPOSITION.md")
PROTOCOL_SHA256 = "ffbf63b17a9241e55952e86aed5e0cead8b51133fc123e620de3a59f5f3ee57c"
SCHEMA = "snap_qc_sim.uhip_decomposition.v1"

CHANNEL_CODES = {
    "defect": frozenset({17}),
    "mass_change": frozenset({19}),
    "arithmetic": frozenset({20}),
    "user": frozenset({21}),
    "entry": frozenset({18}),
    "disregard": frozenset({12}),
    "recert": frozenset({23, 24, 25}),
    "defect_or_mass_change": frozenset({17, 19}),
}
INFERENTIAL_CHANNELS = ("mass_change", "disregard", "defect_or_mass_change")
DESCRIPTIVE_CHANNELS = ("defect", "arithmetic", "user", "entry", "recert")
FITTED_CHANNELS = tuple(name for name in CHANNEL_CODES if name != "recert")
CLIENT_OUTCOME = "client"
FIT_OUTCOMES = FITTED_CHANNELS + (CLIENT_OUTCOME,)
PRIMARY = "primary_exclude_fy2016_drop_fy2021"
SPECIFICATIONS = {
    PRIMARY: event_study.RIKY_PRIMARY_YEARS,
    "include_fy2021_as_post": event_study.RIKY_SPECIFICATIONS["include_fy2021_as_post"],
    "drop_fy2020_and_fy2021": event_study.RIKY_SPECIFICATIONS["drop_fy2020_and_fy2021"],
    "ri_fy2016_as_pre": event_study.RIKY_TIMING_SPECIFICATIONS["RI"][
        "ri_fy2016_as_pre"
    ],
}


def raw_inputs_available() -> bool:
    """Return whether the parent's complete audited mixed-format cache exists."""
    return event_study.riky_raw_inputs_available()


def _read_year(year: int, required: list[str]) -> pd.DataFrame:
    path = event_study._riky_source_path(year)
    audit = json.loads(event_study.AUDIT_PATH.read_text())
    if (
        not path.is_file()
        or event_study._sha256(path) != audit["years"][str(year)]["source"]["sha256"]
    ):
        raise FileNotFoundError(f"Missing or hash-mismatched audited input: {path}")
    return event_study._read_raw_frame(path, required)


def build_panel() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build channel outcomes and RI-only accounting from audited raw files."""
    client_codes = event_study._client_codes()
    agency_cols = [f"AGENCY{slot}" for slot in range(1, 10)]
    element_cols = [f"ELEMENT{slot}" for slot in range(1, 10)]
    required = [
        "STATE",
        "CASE",
        "STATUS",
        "HWGT",
        "AMTERR",
        "YRMONTH",
        "CERTMTH",
        "LASTCERT",
        *agency_cols,
        *element_cols,
    ]
    rows: list[dict[str, Any]] = []
    overlap: list[dict[str, Any]] = []
    selected_elements: dict[str, Counter[int]] = {
        "fy2012_2015": Counter(),
        "fy2017_2019": Counter(),
    }
    selected_case_counts = Counter()
    vintage = Counter()
    vintage_dollars = Counter()
    for year in event_study.RIKY_YEARS:
        frame = _read_year(year, required)
        frame = frame.loc[frame["CASE"].eq(1) & frame["HWGT"].gt(0)].copy()
        frame["state"] = frame["STATE"].astype(int).map(event_study.FIPS)
        agency = frame[agency_cols]
        threshold = (
            event_study.RIKY_FIXED_REAL_THRESHOLD
            * event_study.CPI_U[year]
            / event_study.CPI_U[2024]
        )
        counted = frame["STATUS"].isin((2, 3)) & frame["AMTERR"].gt(threshold)
        base_dollars = frame["HWGT"] * frame["AMTERR"]
        outcome_dollars: dict[str, pd.Series] = {}
        for name, codes in CHANNEL_CODES.items():
            outcome_dollars[name] = base_dollars * (
                counted & agency.isin(codes).any(axis=1)
            )
        outcome_dollars[CLIENT_OUTCOME] = base_dollars * (
            counted & agency.isin(client_codes).any(axis=1)
        )
        grouped = frame.groupby("state", sort=True)["HWGT"].sum()
        for state, denominator in grouped.items():
            state_mask = frame["state"].eq(state)
            row = {"state": state, "year": year}
            row.update(
                {
                    name: float(dollars.loc[state_mask].sum() / denominator)
                    for name, dollars in outcome_dollars.items()
                }
            )
            rows.append(row)

        ri = frame["state"].eq("RI")
        strict = counted & agency.isin(event_study.STRICT_CODES).any(axis=1)
        three_presence = pd.DataFrame(
            {
                name: agency.isin(codes).any(axis=1)
                for name, codes in {
                    "defect": CHANNEL_CODES["defect"],
                    "mass_change": CHANNEL_CODES["mass_change"],
                    "arithmetic": CHANNEL_CODES["arithmetic"],
                }.items()
            }
        )
        strict_dollars = float((base_dollars * (ri & strict)).sum())
        channel_sum = float(
            sum(outcome_dollars[name].loc[ri].sum() for name in three_presence)
        )
        overlapping = ri & counted & three_presence.sum(axis=1).gt(1)
        overlap.append(
            {
                "year": year,
                "strict_outcome_dollars": strict_dollars,
                "sum_channel_dollars": channel_sum,
                "duplicate_credit_dollars": channel_sum - strict_dollars,
                "overlap_case_count": int(overlapping.sum()),
                "overlap_weighted_case_count": float(
                    frame.loc[overlapping, "HWGT"].sum()
                ),
            }
        )

        ri_strict = frame.loc[ri & strict]
        if year in (*range(2012, 2016), *range(2017, 2020)):
            window = "fy2012_2015" if year <= 2015 else "fy2017_2019"
            selected_case_counts[window] += len(ri_strict)
            for values in ri_strict[element_cols].itertuples(index=False, name=None):
                selected_elements[window].update(
                    {int(value) for value in values if pd.notna(value) and value > 0}
                )
        if year in range(2017, 2020):
            for row in ri_strict.itertuples(index=False):
                # YRMONTH is the sampled issuance month (YYYYMM); LASTCERT is
                # months since the last SNAP certification. CERTMTH is the
                # length of the current certification/recertification period.
                yrmonth = int(row.YRMONTH) if pd.notna(row.YRMONTH) else 0
                lastcert = float(row.LASTCERT) if pd.notna(row.LASTCERT) else np.nan
                if yrmonth >= 100001 and np.isfinite(lastcert) and lastcert >= 0:
                    year_part, month_part = divmod(yrmonth, 100)
                    month_index = year_part * 12 + month_part - 1 - int(lastcert)
                    certification_ym = (month_index // 12) * 100 + month_index % 12 + 1
                    group = (
                        "predates_2016_09_go_live"
                        if certification_ym < 201609
                        else "on_or_after_2016_09_go_live"
                    )
                else:
                    group = "not_classifiable"
                vintage[group] += 1
                vintage_dollars[group] += float(row.HWGT * row.AMTERR)

    panel = pd.DataFrame(rows).sort_values(["state", "year"]).reset_index(drop=True)
    audit = json.loads(event_study.AUDIT_PATH.read_text())
    pre_inventory = set().union(
        *(
            audit["years"][str(year)]["findings"]["element"]["observed_codes"]
            for year in range(2012, 2016)
        )
    )
    post_inventory = set().union(
        *(
            audit["years"][str(year)]["findings"]["element"]["observed_codes"]
            for year in range(2017, 2020)
        )
    )
    comparable = sorted(pre_inventory & post_inventory)
    element_mix = {
        "unit": "strict-coded Rhode Island error cases; case-level code presence",
        "comparable_codes": comparable,
        "absent_from_pre_window_inventory": sorted(post_inventory - pre_inventory),
        "absent_from_post_window_inventory": sorted(pre_inventory - post_inventory),
        "windows": {},
    }
    for window in ("fy2012_2015", "fy2017_2019"):
        denominator = selected_case_counts[window]
        element_mix["windows"][window] = {
            "case_count": denominator,
            "codes": {
                str(code): {
                    "case_count": selected_elements[window][code],
                    "case_share": selected_elements[window][code] / denominator,
                }
                for code in comparable
            },
        }
    total_dollars = sum(vintage_dollars.values())
    vintage_split = {
        "method": "YRMONTH minus integer LASTCERT months; CERTMTH is period length and does not date certification",
        "field_definitions": {
            "CERTMTH": "FY2017 Tech Doc pp. 55, 59: reviewer-recorded months in current certification or recertification period",
            "LASTCERT": "FY2017 Tech Doc pp. 55, 59: constructed months since last SNAP certification",
            "loader": "snap_qc_sim/data.py load_cases does not expose either field",
        },
        "limitation": "Month arithmetic supports a recorded-certification vintage split, not direct identification of conversion status.",
        "groups": {
            group: {
                "case_count": vintage[group],
                "weighted_error_dollars": vintage_dollars[group],
                "dollar_share": vintage_dollars[group] / total_dollars
                if total_dollars
                else 0.0,
            }
            for group in (
                "predates_2016_09_go_live",
                "on_or_after_2016_09_go_live",
                "not_classifiable",
            )
        },
    }
    return panel, {
        "overlap_accounting": overlap,
        "element_mix": element_mix,
        "certification_vintage_split": vintage_split,
    }


def _profile(outcome: dict[str, Any]) -> dict[str, Any]:
    gaps = {row["year"]: row["gap"] for row in outcome["path"]}
    consequence = float(np.mean([gaps[year] for year in (2017, 2018, 2019)]))
    later = float(np.mean([gaps[year] for year in (2020, 2022, 2023, 2024)]))
    return {
        "consequence_window_years": [2017, 2018, 2019],
        "later_post_years": [2020, 2022, 2023, 2024],
        "consequence_window_mean_gap": consequence,
        "later_post_mean_gap": later,
        "consequence_minus_later": consequence - later,
        "changes_verdict": False,
    }


def build_results(
    panel: pd.DataFrame, descriptive: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the complete deterministic decomposition result."""
    descriptive = descriptive or {
        "overlap_accounting": [],
        "element_mix": {},
        "certification_vintage_split": {},
    }
    donors = event_study.riky_donor_pool(panel)
    specifications: dict[str, Any] = {}
    for name, years in SPECIFICATIONS.items():
        estimated_outcomes = FIT_OUTCOMES if name == PRIMARY else INFERENTIAL_CHANNELS
        estimated = event_study._estimate(
            panel,
            "RI",
            donors,
            years["pre_years"],
            years["post_years"],
            path_years=event_study.RIKY_YEARS,
            treatment_year=2016,
            outcomes=estimated_outcomes,
        )
        estimated["pre_years"] = years["pre_years"]
        estimated["post_years"] = years["post_years"]
        specifications[name] = estimated
    primary = specifications[PRIMARY]
    inference = event_study._permutation_inference(
        panel,
        primary,
        donors,
        event_study.RIKY_PRIMARY_YEARS["pre_years"],
        event_study.RIKY_PRIMARY_YEARS["post_years"],
        path_years=event_study.RIKY_YEARS,
        treatment_year=2016,
        outcomes=FIT_OUTCOMES,
    )
    inference = {
        name: inference[name] for name in INFERENTIAL_CHANNELS + (CLIENT_OUTCOME,)
    }
    client_p = inference[CLIENT_OUTCOME]["p_value"]
    inferential: dict[str, Any] = {}
    for name in INFERENTIAL_CHANNELS:
        p_value = inference[name]["p_value"]
        inferential[name] = {
            **primary["outcomes"][name],
            **inference[name],
            "profile": _profile(primary["outcomes"][name]),
            "verdict": "signal"
            if p_value < 0.10 and client_p >= 0.10
            else "no_protocol_defined_signal",
            "verdict_family_adjusted": "signal_family_adjusted"
            if p_value < 0.10 / 3
            else "no_family_adjusted_signal",
        }
    descriptive_channels = {
        name: primary["outcomes"][name]
        for name in DESCRIPTIVE_CHANNELS
        if name != "recert"
    }
    descriptive_channels["recert"] = {
        "status": "observed_zero_no_fit",
        "observed_path": [
            {"year": year, "treated": 0.0} for year in event_study.RIKY_YEARS
        ],
    }
    input_hashes = {
        "protocol": event_study._sha256(PROTOCOL_PATH),
        "parent_protocol": event_study._sha256(
            Path(__file__).with_name("RIKY_EVENT_STUDY_PROTOCOL.md")
        ),
        "coding_consistency": event_study._sha256(event_study.AUDIT_PATH),
        "cause_shares": event_study._sha256(event_study.CAUSE_PATH),
        "system_migrations": event_study._sha256(event_study.MIGRATION_PATH),
        "raw_by_fiscal_year": {
            str(year): event_study._sha256(event_study._riky_source_path(year))
            for year in event_study.RIKY_YEARS
        }
        if raw_inputs_available()
        else {},
    }
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "protocol_sha256": hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest(),
        "scope": {
            "treated_state": "RI",
            "panel_years": list(event_study.RIKY_YEARS),
            "donor_pool": donors,
            "inferential_channels": list(INFERENTIAL_CHANNELS),
            "descriptive_channels": list(DESCRIPTIVE_CHANNELS),
        },
        "outcome_definitions": {
            "channel_codes": {
                name: sorted(codes) for name, codes in CHANNEL_CODES.items()
            },
            "client_codes": sorted(event_study._client_codes()),
            "fixed_real_threshold_2024_dollars": event_study.RIKY_FIXED_REAL_THRESHOLD,
        },
        "primary_specification": primary,
        "sensitivity_specifications": {
            name: value for name, value in specifications.items() if name != PRIMARY
        },
        "inferential_channels": inferential,
        "descriptive_channels": descriptive_channels,
        "client_placebo": {
            **primary["outcomes"][CLIENT_OUTCOME],
            **inference[CLIENT_OUTCOME],
        },
        **descriptive,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyreadstat": pyreadstat.__version__,
            "byteorder": sys.byteorder,
        },
        "input_hashes": input_hashes,
    }


def serialize_results(payload: dict[str, Any]) -> bytes:
    return event_study.serialize_results(payload)


def render_memo(payload: dict[str, Any]) -> str:
    """Render the protocol-ordered results memo from an artifact payload."""
    lines = [
        "# UHIP cause-channel decomposition",
        "",
        "## Reading this memo",
        "",
        "The inferential table applies permutation-in-space comparisons to the three pre-named channels and reports both the parent 0.10 rule and the 0.10/3 family-adjusted rule. The descriptive tables report classification patterns and accounting only; the consequence-window profiles are verdict-inert.",
        "",
        "## Inferential channels",
        "",
        "| Channel | Effect | p-value | Rank | Parent verdict | Family-adjusted verdict | Consequence minus later |",
        "|---|---:|---:|---:|---|---|---:|",
    ]
    for name in INFERENTIAL_CHANNELS:
        value = payload["inferential_channels"][name]
        lines.append(
            f"| {name} | {value['effect']:.6f} | {value['p_value']:.6f} | "
            f"{value['absolute_rank']}/{value['rank_denominator']} | {value['verdict']} | "
            f"{value['verdict_family_adjusted']} | {value['profile']['consequence_minus_later']:.6f} |"
        )
    lines.extend(
        [
            "",
            f"Client-coded placebo: effect {payload['client_placebo']['effect']:.6f}; p-value {payload['client_placebo']['p_value']:.6f}; rank {payload['client_placebo']['absolute_rank']}/{payload['client_placebo']['rank_denominator']}.",
            "",
            "## Descriptive channels",
            "",
            "| Channel | Primary simple effect | Status |",
            "|---|---:|---|",
        ]
    )
    for name in DESCRIPTIVE_CHANNELS:
        value = payload["descriptive_channels"][name]
        if name == "recert":
            lines.append("| recert | 0 | observed zero; no fit |")
        else:
            lines.append(f"| {name} | {value['effect']:.6f} | descriptive only |")
    lines.extend(
        [
            "",
            "## Overlap accounting",
            "",
            "| FY | Strict dollars | Sum of three channels | Duplicate credit | Overlap cases |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["overlap_accounting"]:
        lines.append(
            f"| {row['year']} | {row['strict_outcome_dollars']:.2f} | {row['sum_channel_dollars']:.2f} | {row['duplicate_credit_dollars']:.2f} | {row['overlap_case_count']} |"
        )
    mix = payload["element_mix"]
    lines.extend(
        [
            "",
            "## Element mix",
            "",
            f"Comparable inventory codes: {', '.join(map(str, mix['comparable_codes']))}.",
            f"Absent from FY2012–15 inventory: {', '.join(map(str, mix['absent_from_pre_window_inventory'])) or 'none'}.",
            f"Absent from FY2017–19 inventory: {', '.join(map(str, mix['absent_from_post_window_inventory'])) or 'none'}.",
            "",
            "| Element | FY2012–15 cases (share) | FY2017–19 cases (share) |",
            "|---:|---:|---:|",
        ]
    )
    for code in mix["comparable_codes"]:
        pre = mix["windows"]["fy2012_2015"]["codes"][str(code)]
        post = mix["windows"]["fy2017_2019"]["codes"][str(code)]
        lines.append(
            f"| {code} | {pre['case_count']} ({pre['case_share']:.3f}) | {post['case_count']} ({post['case_share']:.3f}) |"
        )
    vintage = payload["certification_vintage_split"]
    lines.extend(
        [
            "",
            "## Certification-vintage split",
            "",
            f"{vintage['field_definitions']['CERTMTH']}; {vintage['field_definitions']['LASTCERT']}. {vintage['limitation']}",
            "",
            "| Recorded certification vintage | Cases | Weighted error dollars | Dollar share |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, value in vintage["groups"].items():
        lines.append(
            f"| {name} | {value['case_count']} | {value['weighted_error_dollars']:.2f} | {value['dollar_share']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Language",
            "",
            'Bundled system replacement as implemented. Channels attribute the measured rise to recorded cause classes under QC coding practice. No channel result is "the effect of software" or "the effect of a rules engine."',
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    panel, descriptive = build_panel()
    payload = build_results(panel, descriptive)
    OUT.write_bytes(serialize_results(payload))
    MEMO_OUT.write_text(render_memo(payload))


if __name__ == "__main__":
    main()
