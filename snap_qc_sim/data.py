"""Load the SNAP QC public-use file and official payment error rates.

The QC file is public but served behind a browser check; ``download()``
fetches and sha256-verifies it into a local cache. The official rates come
from FNS's published FY table (PDF), parsed with pdftotext when available.
"""

from __future__ import annotations

import csv
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

#: FY2024 official error threshold (7 USC 2025(c)(1)(A)(ii), indexed).
THRESHOLD_FY2024 = 56.0

QC_URL_FY2024 = "https://snapqcdata.net/sites/default/files/2026-05/qcfy2024_csv.zip"
PER_URL_FY2024 = (
    "https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-fy24QC-PER.pdf"
)

FIPS = {
    "1": "AL", "2": "AK", "4": "AZ", "5": "AR", "6": "CA", "8": "CO", "9": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID",
    "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA",
    "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ",
    "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK",
    "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN",
    "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "66": "GU", "78": "VI",
}

_STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DIST. OF COLUMBIA": "DC", "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL",
    "GEORGIA": "GA", "GUAM": "GU", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGIN ISLANDS": "VI", "VIRGINIA": "VA",
    "WASHINGTON": "WA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI",
    "WYOMING": "WY",
}


@dataclass(frozen=True)
class QcCase:
    """One QC review: weight, issued benefit, counted error dollars, elements."""

    weight: float
    issuance: float
    error: float
    elements: frozenset[int]


def _num(value: str | None) -> float | None:
    value = (value or "").strip()
    if not value or value == ".":
        return None
    return float(value)


def load_cases(
    csv_path: str | Path, *, threshold: float = THRESHOLD_FY2024
) -> dict[str, list[QcCase]]:
    """Per-state QC cases with error dollars counted at the official threshold."""
    by_state: dict[str, list[QcCase]] = defaultdict(list)
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            state = FIPS.get((row.get("STATE") or "").strip())
            if state is None:
                continue
            # Official error-rate universe only (CASE == 1).
            case_flag = _num(row.get("CASE"))
            if case_flag is not None and case_flag != 1:
                continue
            issued = _num(row.get("RAWBEN"))
            if issued is None:
                continue
            weight = _num(row.get("HWGT")) or 0.0
            # Zero-weight rows contribute nothing to weighted sums but would
            # occupy bootstrap slots; drop them.
            if weight <= 0:
                continue
            amterr = _num(row.get("AMTERR")) or 0.0
            # The official error definition: adjudicated status with the
            # recorded error amount above the year's tolerance threshold.
            counted = (
                (row.get("STATUS") or "").strip() in ("2", "3")
                and amterr > threshold
            )
            elements = frozenset(
                int(e)
                for i in range(1, 10)
                if (e := _num(row.get(f"ELEMENT{i}"))) is not None
            )
            by_state[state].append(
                QcCase(weight, issued, amterr if counted else 0.0, elements)
            )
    return dict(by_state)


def load_official_rates(
    pdf_path: str | Path, *, include_national: bool = False
) -> dict[str, float]:
    """Parse an official FY payment error rate table (FNS/FNA PDF).

    The FY2024 and FY2025 tables share one layout: state, overpayment,
    underpayment, total. With ``include_national`` the UNITED STATES row
    is returned under the key ``US``.
    """
    text = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rates: dict[str, float] = {}
    for line in text.splitlines():
        m = re.match(
            r"\s*([A-Z][A-Z .]+?)\s{2,}([\d.]+)\s{2,}([\d.]+)\s{2,}([\d.]+)\s*$",
            line,
        )
        if not m:
            continue
        name = m.group(1).strip()
        if name in _STATE_NAMES:
            rates[_STATE_NAMES[name]] = float(m.group(4))
        elif include_national and name == "UNITED STATES":
            rates["US"] = float(m.group(4))
    return rates
