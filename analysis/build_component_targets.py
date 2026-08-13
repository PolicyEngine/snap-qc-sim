"""Build official and file-computable SNAP payment-error components."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from snap_qc_sim.data import FIPS, THRESHOLD_FY2024, _num

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "analysis/component_targets.json"
DATA_JSON = REPO_ROOT / "app/public/data.json"
SOURCE_ROOT = Path("~/.cache/axiom-oracles/snap-qc").expanduser()
FY2024_PDF = SOURCE_ROOT / "snap-fy24QC-PER.pdf"
FY2025_PDF = SOURCE_ROOT / "snap-qcfy25-per.pdf"
QC_CSV = SOURCE_ROOT / "qc_pub_fy2024.csv"
TECHDOC = SOURCE_ROOT / "techdoc.txt"
FY2025_EXPECTED_SHA256 = (
    "ae3fc57f2398cea36e9c1322f9f2208a39a7045a4524d259bd1ac22e890c754e"
)
SCHEMA = "snap_qc_sim.component_targets.v1"
RATE_DIGITS = 8

STATE_NAMES = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "GUAM": "GU",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGIN ISLANDS": "VI",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}

ACCOUNTING_NOTE = (
    "This is an accounting decomposition, not causal attribution. The published "
    "tables split payment error into overpayment and underpayment components, but "
    "do not separately identify the ineligible-case truncation and federal "
    "re-review integration. The local FY2024 techdoc was searched for federal "
    "re-review, ineligible-unit, overissuance, and underissuance detail: lines "
    "742-744 describe re-review integration and lines 1202-1205 describe an "
    "ineligible-unit weighting correction, but neither supplies state component "
    "amounts for a sharper split. Additional published state-level detail would "
    "be required."
)


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def parse_publication(pdf_path: Path) -> dict[str, dict[str, float]]:
    """Parse a PER PDF's fixed-layout state table using ``pdftotext``."""
    text = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rows: dict[str, dict[str, float]] = {}
    pattern = re.compile(
        r"^\s*([A-Z][A-Z ]+?)\s{2,}(\d+\.\d{2})\s{2,}"
        r"(\d+\.\d{2})\s{2,}(\d+\.\d{2})\s*$"
    )
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        name = match.group(1).strip()
        code = "US" if name == "UNITED STATES" else STATE_NAMES.get(name)
        if code is None:
            continue
        rows[code] = {
            "overpayment_pct": float(match.group(2)),
            "underpayment_pct": float(match.group(3)),
            "total_pct": float(match.group(4)),
        }
    expected = set(FIPS.values()) | {"US"}
    if set(rows) != expected:
        raise ValueError(f"Publication rows differ: missing={expected - set(rows)}")
    return rows


def file_side_rates(csv_path: Path) -> tuple[dict[str, dict[str, float]], dict]:
    """Compute HWGT-weighted FY2024 rates in the active-case error universe."""
    sums: dict[str, dict[str, float]] = defaultdict(
        lambda: {"issuance": 0.0, "overpayment": 0.0, "underpayment": 0.0}
    )
    with csv_path.open() as source:
        for row in csv.DictReader(source):
            state = FIPS.get((row.get("STATE") or "").strip())
            if state is None:
                continue
            case = _num(row.get("CASE"))
            if case is not None and case != 1:
                continue
            issuance = _num(row.get("RAWBEN"))
            weight = _num(row.get("HWGT")) or 0.0
            if issuance is None or weight <= 0:
                continue
            amount = _num(row.get("AMTERR")) or 0.0
            status = (row.get("STATUS") or "").strip()
            # Match the committed data.json serialization basis so its arrays
            # provide a byte-independent reconciliation oracle.
            weight = round(weight, 2)
            issuance = round(issuance)
            counted_amount = round(amount)
            sums[state]["issuance"] += weight * issuance
            if amount > THRESHOLD_FY2024 and status == "2":
                sums[state]["overpayment"] += weight * counted_amount
            elif amount > THRESHOLD_FY2024 and status == "3":
                sums[state]["underpayment"] += weight * counted_amount

    def rates(values: dict[str, float]) -> dict[str, float]:
        denominator = values["issuance"]
        over = 100 * values["overpayment"] / denominator
        under = 100 * values["underpayment"] / denominator
        return {
            "overpayment_pct": round(over, RATE_DIGITS),
            "underpayment_pct": round(under, RATE_DIGITS),
            "total_pct": round(over + under, RATE_DIGITS),
        }

    expected = set(FIPS.values())
    if set(sums) != expected:
        raise ValueError(f"CSV states differ: missing={expected - set(sums)}")
    states = {state: rates(sums[state]) for state in sorted(sums)}
    national_sums = {
        key: sum(values[key] for values in sums.values())
        for key in ("issuance", "overpayment", "underpayment")
    }
    return states, rates(national_sums)


def _wedge(official: dict[str, float], file_side: dict[str, float]) -> dict:
    """Subtract file-computable rates from official rates by component."""
    return {
        key.replace("_pct", "_pp"): round(official[key] - file_side[key], 8)
        for key in ("overpayment_pct", "underpayment_pct", "total_pct")
    }


def build_payload(
    fy2024_pdf: Path = FY2024_PDF,
    fy2025_pdf: Path = FY2025_PDF,
    csv_path: Path = QC_CSV,
    techdoc_path: Path = TECHDOC,
    data_path: Path = DATA_JSON,
) -> dict[str, Any]:
    """Build and validate the complete component-target registry."""
    fy2025_sha = sha256(fy2025_pdf)
    if fy2025_sha != FY2025_EXPECTED_SHA256:
        raise ValueError(f"FY2025 PDF SHA-256 mismatch: {fy2025_sha}")
    publications = {
        "fy2024": parse_publication(fy2024_pdf),
        "fy2025": parse_publication(fy2025_pdf),
    }
    file_states, file_national = file_side_rates(csv_path)
    data = json.loads(data_path.read_text())
    registry = {}
    for state in sorted(FIPS.values()):
        if (
            publications["fy2024"][state]["total_pct"]
            != data["states"][state]["official"]
        ):
            raise ValueError(f"FY2024 total lock failed for {state}")
        if (
            publications["fy2025"][state]["total_pct"]
            != data["states"][state]["official_fy2025"]
        ):
            raise ValueError(f"FY2025 total lock failed for {state}")
        registry[state] = {
            year: publications[year][state] for year in ("fy2024", "fy2025")
        }
    wedges = {
        state: _wedge(registry[state]["fy2024"], file_states[state])
        for state in sorted(registry)
    }
    return {
        "schema": SCHEMA,
        "unit": "percentage points",
        "provenance": {
            "fy2024_pdf": {"sha256": sha256(fy2024_pdf)},
            "fy2025_pdf": {"sha256": fy2025_sha},
            "qc_csv": {"sha256": sha256(csv_path)},
            "techdoc": {
                "sha256": sha256(techdoc_path),
                "status_semantics_citation": (
                    "techdoc.txt lines 6782, 6788, 6794: 1 = Amount correct; "
                    "2 = Overissuance; 3 = Underissuance"
                ),
            },
            "data_json": {"sha256": sha256(data_path)},
            "pdf_extraction": "pdftotext -layout; anchored fixed-decimal row regex",
        },
        "method": {
            "file_universe": "CASE == 1 (or missing), nonmissing RAWBEN, HWGT > 0",
            "file_numerator": "HWGT * AMTERR where AMTERR > $56 and STATUS is 2 or 3",
            "file_denominator": "HWGT * RAWBEN over the file universe",
            "rounding": (
                "Before rate calculation, HWGT is rounded to 2 decimals and "
                "RAWBEN and counted AMTERR to whole dollars, matching data.json; "
                "rates are then rounded to 8 decimal percentage points."
            ),
        },
        "accounting_note": ACCOUNTING_NOTE,
        "registry": registry,
        "file_side": {"fy2024": file_states},
        "wedge_decomposition": {
            "definition": "official FY2024 minus file-computable FY2024",
            "states": wedges,
            "national_weighted_summary": {
                "official": publications["fy2024"]["US"],
                "file_side": file_national,
                "wedge": _wedge(publications["fy2024"]["US"], file_national),
                "weighting": "national CSV ratio of summed HWGT-weighted dollars",
            },
        },
    }


def write_payload(payload: dict[str, Any], output_path: Path = OUTPUT) -> None:
    """Write compact, sorted JSON with a trailing newline."""
    output_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    )


def main() -> None:
    """Build the committed component-target artifact."""
    write_payload(build_payload())
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} sha256={sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
