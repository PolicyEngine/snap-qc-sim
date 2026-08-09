"""Derive the FY2027 SNAP QC error-tolerance parameter.

The statutory calculation starts with the FY2014 $37 threshold and scales it
by the change in the monthly Thrifty Food Plan (TFP) cost for the statutory
reference family of four from June 2013 to June immediately preceding the
fiscal year.  Published FY2022--FY2026 thresholds reveal that USDA discards
the fractional dollar (floor), rather than rounding to nearest or ceiling.

USDA had published costs only through May 2026 when this source audit was
performed on 2026-08-09.  Consequently this generator emits an explicitly
labeled FY2027 estimate, not an official or fully derived FY2027 threshold.

Deterministic and offline: all audited observations and receipt metadata are
pinned below.  Running this file performs no network or sibling-repository
access and writes ``analysis/fy2027_parameters.json`` and
``analysis/FY2027_PARAMETERS.md``.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = REPO_ROOT / "analysis" / "fy2027_parameters.json"
OUT_MD = REPO_ROOT / "analysis" / "FY2027_PARAMETERS.md"

AUDIT_AS_OF = "2026-08-09"
BASE_THRESHOLD = Decimal(37)
BASE_TFP = Decimal("632.30")

FNA_THRESHOLD_URL = "https://www.fns.usda.gov/snap/qc/ett"
FNA_FOOD_PLAN_ARCHIVE_URL = (
    "https://fns-prod.azureedge.us/research/cnpp/usda-food-plans/"
    "cost-food-monthly-reports"
)
FNA_OLD_TFP_WORKBOOK_URL = (
    "https://fns-prod.azureedge.us/sites/default/files/resource-files/"
    "usda-thriftyplan-march2007-june2021.xlsx"
)
FNA_CURRENT_TFP_WORKBOOK_URL = (
    "https://fns-prod.azureedge.us/sites/default/files/resource-files/"
    "usda-thriftyplan-june2021-present.xlsx"
)
FNA_TFP_2021_URL = (
    "https://fns-prod.azureedge.us/sites/default/files/resource-files/TFP2021.pdf"
)
FNA_MAY_2026_URL = (
    "https://fns-prod.azureedge.us/sites/default/files/resource-files/"
    "cnpp-costfood-tfp-may2026.pdf"
)

ROUNDING_MODES = {
    "floor": ROUND_FLOOR,
    "nearest_half_up": ROUND_HALF_UP,
    "ceiling": ROUND_CEILING,
}

# Exact monthly amounts as published by USDA.  Costs are strings so Decimal
# construction never passes through binary floating point.
VALIDATION_ROWS = (
    {
        "fiscal_year": 2022,
        "basis_month": "2021-06",
        "tfp_cost": "835.57",
        "published_threshold": 48,
        "source_label": "fna",
        "source_url": FNA_TFP_2021_URL,
    },
    {
        "fiscal_year": 2023,
        "basis_month": "2022-06",
        "tfp_cost": "939.90",
        "published_threshold": 54,
        "source_label": "fna",
        "source_url": FNA_CURRENT_TFP_WORKBOOK_URL,
    },
    {
        "fiscal_year": 2024,
        "basis_month": "2023-06",
        "tfp_cost": "973.30",
        "published_threshold": 56,
        "source_label": "fna",
        "source_url": FNA_CURRENT_TFP_WORKBOOK_URL,
    },
    {
        "fiscal_year": 2025,
        "basis_month": "2024-06",
        "tfp_cost": "975.70",
        "published_threshold": 57,
        "source_label": "fna",
        "source_url": FNA_CURRENT_TFP_WORKBOOK_URL,
    },
    {
        "fiscal_year": 2026,
        "basis_month": "2025-06",
        "tfp_cost": "994.40",
        "published_threshold": 58,
        "source_label": "fna",
        "source_url": FNA_CURRENT_TFP_WORKBOOK_URL,
    },
)

PUBLISHED_THRESHOLDS = {
    2014: 37,
    2015: 38,
    2016: 38,
    2017: 38,
    2018: 37,
    2019: 37,
    2020: 37,
    2021: 39,
    2022: 48,
    2023: 54,
    2024: 56,
    2025: 57,
    2026: 58,
}

AXIOM_RECEIPTS = (
    {
        "fiscal_year": 2024,
        "path": "us/policies/usda/snap/fy-2024-cola/maximum-allotments.yaml",
        "sha256": "623ecc0728b6a498437045e1eb8203b82e26ab23cecd62b3d8a2ca863997495a",
        "four_person_max_allotment_dollars": 973,
    },
    {
        "fiscal_year": 2026,
        "path": "us/policies/usda/snap/fy-2026-cola/maximum-allotments.yaml",
        "sha256": "2e4708b8df906b506f07d091fe93dbcc6aefe603a31500502ecc270d436e9f2e",
        "four_person_max_allotment_dollars": 994,
    },
)

PE_OBSERVATION = {
    "interface": "policyengine.py",
    "policyengine.py_version": "4.18.8",
    "policyengine_us_version": "1.752.2",
    "parameter": "gov.usda.snap.max_allotment.main.CONTIGUOUS_US.4",
    "values_by_effective_date": {
        "2021-10-01": 835,
        "2022-10-01": 939,
        "2023-10-01": 973,
        "2024-10-01": 975,
        "2025-10-01": 994,
        "2026-10-01": 1016.2814445828143,
        "2027-10-01": 1038.2534246575344,
    },
}


def _as_decimal(value: Decimal | str | float) -> Decimal:
    """Convert a numeric input to a finite Decimal without float artifacts."""
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite():
        raise ValueError("amounts must be finite")
    return result


def unrounded_threshold(
    current_tfp: Decimal | str | float,
    *,
    base_tfp: Decimal | str | float = BASE_TFP,
    base_threshold: Decimal | str | float = BASE_THRESHOLD,
) -> Decimal:
    """Return the statutory scaled threshold before whole-dollar treatment."""
    current = _as_decimal(current_tfp)
    base_cost = _as_decimal(base_tfp)
    threshold = _as_decimal(base_threshold)
    if current <= 0 or base_cost <= 0 or threshold < 0:
        raise ValueError("TFP costs must be positive and the threshold nonnegative")
    return threshold * current / base_cost


def apply_rounding(value: Decimal | str | float, convention: str) -> int:
    """Apply one of the candidate whole-dollar conventions."""
    if convention not in ROUNDING_MODES:
        raise ValueError(f"unknown rounding convention: {convention}")
    amount = _as_decimal(value)
    return int(amount.to_integral_value(rounding=ROUNDING_MODES[convention]))


def derive_threshold(
    current_tfp: Decimal | str | float, convention: str = "floor"
) -> int:
    """Scale the FY2014 baseline and apply a named whole-dollar convention."""
    return apply_rounding(unrounded_threshold(current_tfp), convention)


def tfp_boundary_for_threshold(threshold: int) -> Decimal:
    """Return the minimum TFP cost whose floored result is ``threshold``."""
    if threshold < 0:
        raise ValueError("threshold must be nonnegative")
    return Decimal(threshold) * BASE_TFP / BASE_THRESHOLD


def _tfp_boundary_fraction(threshold: int) -> Fraction:
    """Return the exact rational-dollar boundary from the pinned baseline."""
    return Fraction(threshold * 63_230, 37 * 100)


def _first_sufficient_published_tenth(value: Decimal) -> Decimal:
    """Round a decision boundary up to USDA's published ten-cent precision."""
    return (value * 10).to_integral_value(rounding=ROUND_CEILING) / 10


def _nearby_sensitivity() -> list[dict[str, Any]]:
    """Describe nearby floor outcomes without asserting an evidence-bound range."""
    rows = []
    for threshold in range(58, 62):
        lower = tfp_boundary_for_threshold(threshold)
        upper = tfp_boundary_for_threshold(threshold + 1)
        rows.append(
            {
                "threshold_dollars": threshold,
                "june_tfp_lower_inclusive_exact_fraction": str(
                    _tfp_boundary_fraction(threshold)
                ),
                "june_tfp_lower_inclusive_decimal": str(lower),
                "june_tfp_upper_exclusive_exact_fraction": str(
                    _tfp_boundary_fraction(threshold + 1)
                ),
                "june_tfp_upper_exclusive_decimal": str(upper),
                "first_sufficient_published_tenth_dollars": float(
                    _first_sufficient_published_tenth(lower)
                ),
            }
        )
    return rows


def evaluate_rounding_conventions(
    rows: tuple[dict[str, Any], ...] = VALIDATION_ROWS,
) -> dict[str, Any]:
    """Test floor, nearest-half-up, and ceiling against published thresholds."""
    comparisons = []
    for row in rows:
        raw = unrounded_threshold(row["tfp_cost"])
        candidates = {name: apply_rounding(raw, name) for name in ROUNDING_MODES}
        comparisons.append(
            {
                "fiscal_year": row["fiscal_year"],
                "basis_month": row["basis_month"],
                "tfp_cost_dollars": float(Decimal(row["tfp_cost"])),
                "unrounded_threshold_dollars": f"{raw:.6f}",
                "candidate_thresholds_dollars": candidates,
                "published_threshold_dollars": row["published_threshold"],
                "source_label": row["source_label"],
                "source_url": row["source_url"],
            }
        )

    matches = [
        name
        for name in ROUNDING_MODES
        if all(
            comparison["candidate_thresholds_dollars"][name]
            == comparison["published_threshold_dollars"]
            for comparison in comparisons
        )
    ]
    return {
        "years_tested": [row["fiscal_year"] for row in rows],
        "candidate_conventions": list(ROUNDING_MODES),
        "matching_conventions": matches,
        "unique_match": matches == ["floor"],
        "comparisons": comparisons,
        "correction": (
            "FY2021 is $39; the $48 threshold begins in FY2022. "
            "The self-test therefore covers the five-year published sequence "
            "FY2022-FY2026: $48/$54/$56/$57/$58."
        ),
    }


def _record_sha256(record: dict[str, Any]) -> str:
    """Hash a canonical observation record (not the bytes at its source URL)."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _source_receipts() -> dict[str, Any]:
    fna_observations = [
        {
            "basis_month": "2013-06",
            "reference_family_monthly_cost_dollars": 632.3,
            "source_label": "fna",
            "url": FNA_OLD_TFP_WORKBOOK_URL,
        },
        *[
            {
                "basis_month": row["basis_month"],
                "reference_family_monthly_cost_dollars": float(
                    Decimal(row["tfp_cost"])
                ),
                "source_label": row["source_label"],
                "url": row["source_url"],
            }
            for row in VALIDATION_ROWS
        ],
        {
            "basis_month": "2026-05",
            "reference_family_monthly_cost_dollars": 1018.2,
            "source_label": "fna",
            "url": FNA_MAY_2026_URL,
        },
    ]
    for observation in fna_observations:
        observation["observation_record_sha256"] = _record_sha256(observation)
        observation["source_file_sha256"] = None
        observation["source_file_sha256_status"] = (
            "not downloaded; official source was inspected through a rendered "
            "web resource that did not expose source bytes"
        )

    pe_observation = dict(PE_OBSERVATION)
    pe_observation["observation_record_sha256"] = _record_sha256(PE_OBSERVATION)
    return {
        "axiom": {
            "repository": "TheAxiomFoundation/rulespec-us",
            "source_label": "axiom",
            "result": (
                "No encoded June-30 reference-family TFP cost series or QC "
                "threshold series was found. FY2024 and FY2026 COLA modules "
                "provide rounded maximum-allotment cross-checks only."
            ),
            "receipts": list(AXIOM_RECEIPTS),
        },
        "pe": {
            "source_label": "pe",
            "result": (
                "The policyengine.py interface exposes rounded official maximum "
                "allotments through FY2026 and forecast-uprated future values, "
                "but not the required June-30 TFP cost series. Forecast values "
                "are not used in the FY2027 point estimate."
            ),
            "receipt": pe_observation,
        },
        "fna": {
            "source_label": "fna",
            "result": (
                "Official USDA/FNS/FNA monthly TFP reports supply the exact "
                "reference-family inputs. The archive was current only through "
                "May 2026 at the audit date."
            ),
            "archive_url": FNA_FOOD_PLAN_ARCHIVE_URL,
            "threshold_table_url": FNA_THRESHOLD_URL,
            "observations": fna_observations,
        },
        "network_fetches_by_generator": [],
    }


def build() -> dict[str, Any]:
    """Build the complete deterministic FY2027 parameter artifact."""
    self_test = evaluate_rounding_conventions()
    if self_test["matching_conventions"] != ["floor"]:
        raise RuntimeError("historical thresholds do not uniquely support floor")

    latest_cost = Decimal("1018.20")
    raw_estimate = unrounded_threshold(latest_cost)
    boundary_cost = tfp_boundary_for_threshold(60)
    threshold_series = [
        {
            "fiscal_year": year,
            "threshold_dollars": threshold,
            "status": "official",
            "source_label": "fna",
            "source_url": FNA_THRESHOLD_URL,
        }
        for year, threshold in PUBLISHED_THRESHOLDS.items()
    ]
    threshold_series.append(
        {
            "fiscal_year": 2027,
            "threshold_dollars": derive_threshold(latest_cost),
            "status": "ESTIMATE",
            "source_label": "fna",
            "input_required": "June 2026 reference-family TFP cost",
            "input_used": "May 2026 reference-family TFP cost",
            "input_used_dollars": float(latest_cost),
            "source_url": FNA_MAY_2026_URL,
            "input_uncertainty_bounded_by_available_evidence": False,
        }
    )

    return {
        "schema_version": 1,
        "generated_by": "analysis/fy2027_parameters.py",
        "audit_as_of": AUDIT_AS_OF,
        "legal_formula": {
            "citation": "7 USC 2025(c)(1)(A)(ii)",
            "description": (
                "$37 for FY2014, adjusted by the percentage change in the "
                "48-state/DC reference-family TFP cost from June 30, 2013 to "
                "June 30 immediately preceding the fiscal year"
            ),
            "base_threshold_dollars": int(BASE_THRESHOLD),
            "base_tfp_basis_month": "2013-06",
            "base_tfp_cost_dollars": float(BASE_TFP),
            "calculation": "floor(37 * current_June_TFP / 632.30)",
            "whole_dollar_convention": "floor",
        },
        "rounding_self_test": self_test,
        "threshold_series": threshold_series,
        "fy2027_result": {
            "status": "ESTIMATE",
            "threshold_dollars": derive_threshold(latest_cost),
            "convention_ambiguity": "none; floor is the unique historical match",
            "latest_official_input_month": "2026-05",
            "latest_official_tfp_cost_dollars": float(latest_cost),
            "unrounded_using_latest_input_dollars": f"{raw_estimate:.6f}",
            "required_input_month": "2026-06",
            "missing_input": True,
            "input_uncertainty_bounded_by_available_evidence": False,
            "nearby_threshold_sensitivity": _nearby_sensitivity(),
            "boundary_for_60_dollars_exact_fraction": str(_tfp_boundary_fraction(60)),
            "boundary_for_60_dollars_decimal": str(boundary_cost),
            "first_sufficient_published_tenth_for_60_dollars": 1025.4,
            "explanation": (
                "USDA's official archive ended at May 2026 on the audit date. "
                "May implies $59 under the historically validated floor rule. "
                "An official June cost of at least $1,025.351351... (therefore "
                "$1,025.40 at USDA's published ten-cent precision) implies $60. "
                "Available evidence does not bound the missing June input, so "
                "no finite threshold estimate range is claimed."
            ),
        },
        "source_audit": _source_receipts(),
        "limitations": [
            "The FY2027 result is not official because the June 2026 TFP input is missing.",
            (
                "The monthly archive values used for FY2023-FY2026 are "
                "published to ten cents; the separate 2021 TFP reevaluation "
                "reports its June 2021 cost as $835.57."
            ),
            (
                "No source binary was downloaded by this offline generator. "
                "Receipt hashes for FNA observations hash the canonical "
                "observation record, not remote source-file bytes."
            ),
        ],
    }


def render_markdown(result: dict[str, Any]) -> str:
    """Render the human-readable deterministic companion artifact."""
    fy27 = result["fy2027_result"]
    self_test = result["rounding_self_test"]
    lines = [
        "<!-- Generated by analysis/fy2027_parameters.py; do not edit manually. -->",
        "",
        "# FY2027 SNAP QC tolerance parameter",
        "",
        (
            f"**ESTIMATE: ${fy27['threshold_dollars']} using the May 2026 proxy.** "
            "This is not an official FY2027 value or a bounded estimate range: "
            "the legally required June 2026 TFP input was not published in "
            "USDA's archive as of "
            f"{result['audit_as_of']}."
        ),
        "",
        "## Derivation",
        "",
        (
            "7 USC 2025(c)(1)(A)(ii) starts with the FY2014 $37 threshold and "
            "scales it by the change in the four-person reference-family TFP "
            "cost from June 2013 ($632.30) to June immediately preceding the "
            "fiscal year. The published history identifies the operation as "
            "`floor(37 * current June TFP / 632.30)`."
        ),
        "",
        (
            "The latest official value is May 2026 at $1,018.20. Substitution "
            f"gives {fy27['unrounded_using_latest_input_dollars']}, or $59 after "
            "flooring. There is no rounding-convention ambiguity: floor is the "
            "unique historical match. The FY2027 result becomes $60 at the "
            "exact June boundary $37,938/37 (about $1,025.351351...), "
            "and $1,025.40 is the first sufficient value at USDA's published "
            "ten-cent precision."
        ),
        "",
        (
            "Available evidence does not bound the absent June value, so the "
            "following rows are nearby decision bands, not a forecast range."
        ),
        "",
        "| Threshold | June TFP lower bound (inclusive) | Upper bound (exclusive) | First sufficient published tenth |",
        "|---:|---:|---:|---:|",
    ]
    for row in fy27["nearby_threshold_sensitivity"]:
        lines.append(
            f"| ${row['threshold_dollars']} "
            f"| ${Decimal(row['june_tfp_lower_inclusive_decimal']):,.6f} "
            f"| ${Decimal(row['june_tfp_upper_exclusive_decimal']):,.6f} "
            f"| ${row['first_sufficient_published_tenth_dollars']:,.2f} |"
        )
    lines.extend(
        [
            "",
            "## Rounding self-test",
            "",
            self_test["correction"],
            "",
            "| Fiscal year | June TFP | Unrounded | Floor | Nearest | Ceiling | Published |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in self_test["comparisons"]:
        candidates = row["candidate_thresholds_dollars"]
        lines.append(
            f"| {row['fiscal_year']} | ${row['tfp_cost_dollars']:,.2f} "
            f"| {row['unrounded_threshold_dollars']} | ${candidates['floor']} "
            f"| ${candidates['nearest_half_up']} | ${candidates['ceiling']} "
            f"| ${row['published_threshold_dollars']} |"
        )
    lines.extend(
        [
            "",
            "Only **floor** reproduces all five published thresholds exactly.",
            "",
            "## Source audit",
            "",
            "| Source | June-pinned TFP series? | Finding |",
            "|---|:---:|---|",
            (
                "| rulespec-us (`axiom`) | no | FY2024 and FY2026 modules "
                "encode rounded COLA maximum allotments ($973 and $994 for "
                "four people), but not the exact June TFP or QC threshold. |"
            ),
            (
                "| policyengine.py (`pe`) | no | The interface exposes rounded "
                "official maximum allotments through FY2026 and forecast-uprated "
                "future values, not the required June-30 TFP series. |"
            ),
            (
                "| USDA FNS/FNA (`fna`) | through May 2026 | Official monthly "
                "reports supply the exact validation inputs and latest estimate "
                "input; June 2026 is absent. |"
            ),
            "",
            "## Receipts and limitations",
            "",
            (
                f"Official threshold table: {FNA_THRESHOLD_URL}. Official monthly "
                f"report archive: {FNA_FOOD_PLAN_ARCHIVE_URL}. Per-observation "
                "URLs, source labels, local rulespec file SHA-256 hashes, and "
                "canonical observation-record hashes are in the JSON artifact."
            ),
            "",
            (
                "The generator is offline and fetched no files. FNA source-file "
                "SHA-256 fields are therefore null and explicitly distinguished "
                "from hashes of the pinned observation records."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    result = build()
    OUT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    OUT_MD.write_text(render_markdown(result))
    digest = hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()
    print(f"wrote {OUT_JSON} (sha256 {digest[:16]}...)")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
