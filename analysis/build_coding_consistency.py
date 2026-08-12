"""Build the historical SNAP QC coding-consistency inventory.

This is an accounting and schema audit.  It does not estimate causal effects.
Raw SAVs and technical documentation are local inputs and are not committed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pyreadstat

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).with_name("coding_consistency.json")
SOURCE_ROOT = Path.home() / ".cache/axiom-oracles/snap_qc_repo/qc_data"
REFERENCE_PATH = Path(__file__).with_name("cause_shares.json")
YEARS = tuple(range(2017, 2025))
CORE_FIELDS = ("CASE", "HWGT", "RAWBEN", "AMTERR", "STATUS")
FINDING_ROOTS = ("NATURE", "E_FINDG", "ELEMENT")
STRICT_CODES = frozenset({17, 19, 20})
BROAD_CODES = frozenset({10, 17, 19, 20, 21, 22})
K3_NATURE_CODES = frozenset(
    {36, 42, 43, 52, 53, 54, 56, 57, 64, 65, 75, 79, 80, 98, 123}
)
K3_ELEMENT_CODES = frozenset({520})
SCHEMA = "snap-qc-coding-consistency-v1"

# All citations below are to local documents. The earlier-year values are
# intentionally not filled from repository narrative or memory.
THRESHOLDS: dict[int, dict[str, Any]] = {
    2017: {"status": "NEEDS_ACQUISITION", "dollars": None, "citation": None},
    2018: {"status": "NEEDS_ACQUISITION", "dollars": None, "citation": None},
    2019: {"status": "NEEDS_ACQUISITION", "dollars": None, "citation": None},
    2020: {
        "status": "verified_local_techdoc",
        "dollars": 37,
        "citation": "techdoc-2021.pdf p. 6, footnote 8 (FY2020 $37; FY2021 $39)",
    },
    2021: {
        "status": "verified_local_techdoc",
        "dollars": 39,
        "citation": "techdoc-2021.pdf p. 6, footnote 8 (FY2020 $37; FY2021 $39)",
    },
    2022: {
        "status": "verified_local_techdoc",
        "dollars": 48,
        "citation": "techdoc-2022.pdf p. 6, footnote 8 (FY2021 $39; FY2022 $48)",
    },
    2023: {
        "status": "verified_local_techdoc",
        "dollars": 54,
        "citation": "techdoc-2023.pdf p. 6, footnote 9 (FY2022 $48; FY2023 $54)",
    },
    2024: {
        "status": "verified_local_techdoc",
        "dollars": 56,
        "citation": "FY-2024-Tech-Doc.pdf p. 5 (errors $56 or less excluded)",
    },
}


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _slots(columns: pd.Index, root: str) -> list[str]:
    """Return numbered finding columns in numeric suffix order."""
    pattern = re.compile(rf"^{root}([1-9])$")
    return sorted(
        (column for column in columns if pattern.match(column)),
        key=lambda column: int(pattern.match(column).group(1)),  # type: ignore[union-attr]
    )


def _codes(frame: pd.DataFrame, columns: list[str]) -> list[int]:
    """Return sorted observed integer codes across a group of columns."""
    if not columns:
        return []
    values = pd.unique(frame[columns].to_numpy().ravel())
    return sorted(int(value) for value in values if pd.notna(value))


def _distribution(series: pd.Series) -> dict[str, int]:
    """Serialize a numeric value-count distribution deterministically."""
    counts = series.value_counts(dropna=False).sort_index()
    result: dict[str, int] = {}
    for value, count in counts.items():
        key = "missing" if pd.isna(value) else str(int(value))
        result[key] = int(count)
    return result


def _field_inventory(frame: pd.DataFrame, active: pd.DataFrame) -> dict[str, Any]:
    """Inventory presence and missingness of core fields."""
    result = {}
    for field in CORE_FIELDS:
        present = field in frame
        result[field] = {
            "present": present,
            "missing_rows": int(frame[field].isna().sum()) if present else None,
            "missing_share": (
                round(float(frame[field].isna().mean()), 12) if present else None
            ),
            "active_missing_rows": (
                int(active[field].isna().sum()) if present else None
            ),
            "active_missing_share": (
                round(float(active[field].isna().mean()), 12) if present else None
            ),
        }
    return result


def _scenario_share(
    active: pd.DataFrame, agency_columns: list[str], codes: frozenset[int]
) -> dict[str, Any]:
    """Summarize any-presence case and weighted deviation-dollar shares."""
    if not agency_columns:
        return {
            "codes": sorted(codes),
            "present": False,
            "active_cases_any": 0,
            "active_case_share_any": 0.0,
            "deviation_dollar_share_any": None,
        }
    any_code = active[agency_columns].isin(codes).any(axis=1)
    deviation = active["STATUS"].isin((2, 3)) & active["AMTERR"].gt(0)
    dollars = active["HWGT"] * active["AMTERR"]
    denominator = float(dollars.where(deviation, 0).sum())
    numerator = float(dollars.where(deviation & any_code, 0).sum())
    return {
        "codes": sorted(codes),
        "present": bool(any_code.any()),
        "active_cases_any": int(any_code.sum()),
        "active_case_share_any": round(float(any_code.mean()), 12),
        "deviation_dollar_share_any": (
            round(numerator / denominator, 12) if denominator else None
        ),
    }


def audit_file(path: Path, year: int, reference_causes: set[int]) -> dict[str, Any]:
    """Build one fiscal-year audit block from a SAV."""
    frame, _ = pyreadstat.read_sav(str(path))
    active = frame.loc[frame["CASE"].eq(1)].copy()
    agency_columns = _slots(frame.columns, "AGENCY")
    observed_causes = _codes(active, agency_columns)
    findings: dict[str, Any] = {}
    for root in FINDING_ROOTS:
        columns = _slots(frame.columns, root)
        observed = _codes(active, columns)
        findings[root.lower()] = {
            "columns": columns,
            "all_nine_present": columns == [f"{root}{slot}" for slot in range(1, 10)],
            "observed_codes": observed,
        }

    weighted_case_months = float(active["HWGT"].sum())
    rawben_flow = float((active["HWGT"] * active["RAWBEN"]).sum())
    return {
        "fiscal_year": year,
        "source": {
            "path": f"~/.cache/axiom-oracles/snap_qc_repo/qc_data/{path.name}",
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        },
        "row_universe": {
            "total_rows": len(frame),
            "case_distribution": _distribution(frame["CASE"]),
            "active_case_definition": "CASE == 1",
            "active_case_count": len(active),
            "fields": _field_inventory(frame, active),
        },
        "cause_slots": {
            "columns": agency_columns,
            "all_nine_present": agency_columns
            == [f"AGENCY{slot}" for slot in range(1, 10)],
            "observed_codes": observed_causes,
            "codes_absent_from_fy2024_map": sorted(
                set(observed_causes) - reference_causes
            ),
            "strict_computing_apparatus": _scenario_share(
                active, agency_columns, STRICT_CODES
            ),
            "broad_computing_apparatus": _scenario_share(
                active, agency_columns, BROAD_CODES
            ),
        },
        "findings": findings,
        "threshold": THRESHOLDS[year],
        "weights": {
            "hwgt_sum_case_months": round(weighted_case_months, 6),
            "implied_average_monthly_caseload": round(weighted_case_months / 12, 6),
            "weighted_raw_benefit_annual_flow_dollars": round(rawben_flow, 2),
            "scale_sanity": (
                "plausible_national_magnitude"
                if 1_000_000 <= weighted_case_months / 12 <= 100_000_000
                else "pandemic_partial_or_requires_review"
            ),
            "annualization_note": (
                "HWGT is a monthly sample weight; summing the 12 monthly samples "
                "gives case-months and annual benefit flow."
            ),
        },
    }


def _first_exact(years: dict[str, Any], path: tuple[str, ...]) -> int | None:
    """Return first year whose inventory exactly equals FY2024."""

    def get(block: dict[str, Any]) -> Any:
        value: Any = block
        for key in path:
            value = value[key]
        return value

    reference = get(years["2024"])
    return next(
        (int(year) for year, block in years.items() if get(block) == reference), None
    )


def build() -> dict[str, Any]:
    """Build the complete audit payload."""
    reference = json.loads(REFERENCE_PATH.read_text())
    reference_causes = {int(code) for code in reference["cause_codes"]}
    years = {
        str(year): audit_file(
            SOURCE_ROOT / f"qc_pub_fy{year}.sav", year, reference_causes
        )
        for year in YEARS
    }
    fy2024 = years["2024"]
    for block in years.values():
        for root in FINDING_ROOTS:
            finding = block["findings"][root.lower()]
            reference_codes = fy2024["findings"][root.lower()]["observed_codes"]
            finding["vs_fy2024_observed"] = {
                "appeared_by_fy2024": sorted(
                    set(reference_codes) - set(finding["observed_codes"])
                ),
                "absent_by_fy2024": sorted(
                    set(finding["observed_codes"]) - set(reference_codes)
                ),
                "exact_match": finding["observed_codes"] == reference_codes,
            }

    consecutive_changes = {}
    for year in YEARS[1:]:
        previous = years[str(year - 1)]
        current = years[str(year)]
        consecutive_changes[str(year)] = {}
        for name, path in {
            "cause_codes": ("cause_slots", "observed_codes"),
            "nature_codes": ("findings", "nature", "observed_codes"),
            "e_findg_codes": ("findings", "e_findg", "observed_codes"),
            "element_codes": ("findings", "element", "observed_codes"),
        }.items():
            old: Any = previous
            new: Any = current
            for key in path:
                old, new = old[key], new[key]
            consecutive_changes[str(year)][name] = {
                "appeared": sorted(set(new) - set(old)),
                "disappeared": sorted(set(old) - set(new)),
            }

    split_paths = [SOURCE_ROOT / f"qc_pub_fy2020_per{period}.sav" for period in (1, 2)]
    split_rows = []
    split_sources = []
    for path in split_paths:
        metadata = pyreadstat.read_sav(str(path), metadataonly=True)[1]
        split_rows.append(metadata.number_rows)
        split_sources.append(
            {"path": path.name, "rows": metadata.number_rows, "sha256": sha256(path)}
        )

    return {
        "schema": SCHEMA,
        "scope_note": "Inventory/accounting only; no causal claims.",
        "reference_conventions": {
            "cause_codes": sorted(reference_causes),
            "strict_computing_apparatus": sorted(STRICT_CODES),
            "broad_computing_apparatus": sorted(BROAD_CODES),
            "facts_k3_nature_codes": sorted(K3_NATURE_CODES),
            "facts_k3_element_codes": sorted(K3_ELEMENT_CODES),
            "source": "analysis/cause_shares.json and FACTS K3",
        },
        "years": years,
        "cross_year_summary": {
            "first_year_exactly_matching_fy2024_observed_inventory": {
                "cause_codes": _first_exact(years, ("cause_slots", "observed_codes")),
                "nature_codes": _first_exact(
                    years, ("findings", "nature", "observed_codes")
                ),
                "elements": _first_exact(
                    years, ("findings", "element", "observed_codes")
                ),
                "threshold_basis": next(
                    year
                    for year in YEARS
                    if years[str(year)]["threshold"]["status"]
                    == "verified_local_techdoc"
                ),
                "criterion_note": (
                    "Code conventions use exact equality of observed active-case "
                    "inventories to FY2024; threshold basis uses the first year "
                    "whose official threshold is verifiable from a local techdoc."
                ),
            },
            "consecutive_observed_code_changes": consecutive_changes,
            "fy2024_minor_revisions_evidence": {
                "techdoc_citation": (
                    "FY-2024-Tech-Doc.pdf p. 8: minor changes to AGENCY, "
                    "ELEMENT, and NATURE codes"
                ),
                "observed_2023_to_2024": consecutive_changes["2024"],
                "interpretation_limit": (
                    "Observed appearances/disappearances can reflect sampling as "
                    "well as codebook revisions; they are not alone proof of a "
                    "definition change."
                ),
            },
        },
        "pandemic_file_handling": {
            "fy2020": {
                "combined_file": "qc_pub_fy2020.sav",
                "period_files": split_sources,
                "period_row_sum": sum(split_rows),
                "combined_rows": years["2020"]["row_universe"]["total_rows"],
                "row_count_reconciles": sum(split_rows)
                == years["2020"]["row_universe"]["total_rows"],
                "recommendation": "Use the combined file; retain split hashes as provenance.",
            },
            "fy2021": {
                "rows": years["2021"]["row_universe"]["total_rows"],
                "recommendation": (
                    "Treat as pandemic-partial and require explicit sensitivity "
                    "handling; do not treat its smaller sample as a normal full year."
                ),
            },
        },
        "panel_recommendation": {
            "total_rate_fixed_real_threshold": {
                "earliest_defensible_start_year": 2017,
                "evidence": (
                    "CASE, HWGT, RAWBEN, AMTERR, and STATUS plus all nine cause and "
                    "finding slots are present from FY2017, so a researcher-chosen "
                    "fixed real AMTERR threshold does not depend on unavailable "
                    "official historical tolerances."
                ),
                "bounds_and_special_handling": [
                    "FY2017-FY2019 official nominal thresholds remain NEEDS_ACQUISITION.",
                    "FY2020 is a combined two-period pandemic file.",
                    "FY2021 is pandemic-partial and requires sensitivity treatment.",
                ],
            },
            "element_targeted_outcomes": {
                "earliest_defensible_start_year": 2024,
                "evidence": (
                    "The FY2024 techdoc explicitly reports minor AGENCY, ELEMENT, "
                    "and NATURE revisions, and the observed inventories change at "
                    "that boundary. Earlier techdocs are unavailable before FY2021, "
                    "so semantic equivalence cannot be established for FY2017-FY2020."
                ),
                "bounds_and_special_handling": [
                    "Acquire FY2017-FY2020 codebooks before moving the start earlier.",
                    "Validate 2023-to-2024 code meanings, not only numeric presence.",
                    "FY2021 is pandemic-partial even if a targeted coding bridge is built.",
                ],
            },
            "status": "evidence_and_recommendation_not_a_design_decision",
        },
        "provenance": {
            "generator": "analysis/build_coding_consistency.py",
            "reference_artifact_sha256": sha256(REFERENCE_PATH),
            "determinism": "sorted keys, stable ordering, no timestamps or absolute paths",
        },
    }


def main() -> None:
    """Write the deterministic JSON artifact."""
    payload = build()
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)} sha256={sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
