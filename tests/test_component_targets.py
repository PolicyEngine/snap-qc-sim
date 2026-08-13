"""Gates for the official-versus-file component target registry."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from analysis import build_component_targets as builder

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "analysis/component_targets.json"
DATA_PATH = ROOT / "app/public/data.json"
PAYLOAD = json.loads(ARTIFACT.read_text())
DATA = json.loads(DATA_PATH.read_text())
RAW_SOURCES = (builder.FY2024_PDF, builder.FY2025_PDF, builder.QC_CSV, builder.TECHDOC)
needs_raw_sources = pytest.mark.skipif(
    not all(path.exists() for path in RAW_SOURCES),
    reason="local PDF, CSV, and techdoc regeneration sources are not all present",
)


def test_publication_internal_consistency() -> None:
    """Two-decimal component rounding permits at most 0.01 point discrepancy."""
    exceedances = []
    for state, years in PAYLOAD["registry"].items():
        for year, row in years.items():
            difference = abs(
                row["overpayment_pct"] + row["underpayment_pct"] - row["total_pct"]
            )
            if difference > 0.011:
                exceedances.append((state, year, difference))
    assert not exceedances, f"publication rounding exceedances: {exceedances}"


def test_cross_artifact_locks() -> None:
    """Official totals and the FY2025 PDF pin remain exactly locked."""
    assert (
        PAYLOAD["provenance"]["fy2025_pdf"]["sha256"] == builder.FY2025_EXPECTED_SHA256
    )
    for state, public in DATA["states"].items():
        registry = PAYLOAD["registry"][state]
        assert registry["fy2024"]["total_pct"] == public["official"]
        assert registry["fy2025"]["total_pct"] == public["official_fy2025"]


def test_file_side_totals_reconcile_to_rounded_public_arrays() -> None:
    """Common-basis CSV rates agree with the independently committed arrays."""
    for state, public in DATA["states"].items():
        weights = np.asarray(public["w"], dtype=float)
        point = 100 * np.sum(weights * public["err"]) / np.sum(weights * public["iss"])
        observed = PAYLOAD["file_side"]["fy2024"][state]["total_pct"]
        assert observed == pytest.approx(point, abs=2e-6), state


def test_wedge_share_stats_reproduce_facts_o1() -> None:
    """The decomposed totals retain the previously disclosed wedge statistics."""
    shares = {
        state: row["total_pp"] / PAYLOAD["registry"][state]["fy2024"]["total_pct"]
        for state, row in PAYLOAD["wedge_decomposition"]["states"].items()
    }
    assert float(np.median(list(shares.values()))) == pytest.approx(0.31, abs=0.005)
    assert min(shares.values()) == pytest.approx(-0.034, abs=0.005)
    assert max(shares.values()) == pytest.approx(0.81, abs=0.005)
    assert sorted(state for state, share in shares.items() if share < 0) == [
        "MN",
        "NV",
    ]


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("CO", (7.91, 2.06, 9.97)),
        ("AK", (22.50, 2.16, 24.66)),
        ("NY", (12.65, 1.44, 14.09)),
    ],
)
def test_fy2024_spot_values(state: str, expected: tuple[float, ...]) -> None:
    """Lock named values from the FY2024 publication."""
    row = PAYLOAD["registry"][state]["fy2024"]
    assert (
        row["overpayment_pct"],
        row["underpayment_pct"],
        row["total_pct"],
    ) == expected


def test_accounting_language_and_status_citation() -> None:
    """Prevent the component split from drifting into causal claims."""
    note = PAYLOAD["accounting_note"]
    assert "accounting decomposition, not causal attribution" in note
    assert "not separately identify" in note
    citation = PAYLOAD["provenance"]["techdoc"]["status_semantics_citation"]
    assert "6788" in citation and "2 = Overissuance" in citation
    assert "6794" in citation and "3 = Underissuance" in citation


@needs_raw_sources
def test_raw_source_build_is_byte_deterministic(tmp_path: Path) -> None:
    """Two raw-source builds match one another and the committed artifact."""
    outputs = [tmp_path / "first.json", tmp_path / "second.json"]
    for output in outputs:
        builder.write_payload(builder.build_payload(), output)
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    assert outputs[0].read_bytes() == ARTIFACT.read_bytes()
