"""Build the factor-decomposed mechanical aging path.

Run from the repository root:
    uv run --frozen --extra analysis python analysis/aging_path.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MARGINS = REPO.parent / "snap-fy27-margins"
GRID_PATH = MARGINS / "reprice" / "state_rate_implications.json"
MANIFEST_PATH = MARGINS / "reprice" / "manifest.json"
DATA_PATH = REPO / "app" / "public" / "data.json"
PARAMETERS_PATH = REPO / "analysis" / "fy2027_parameters.json"
CROSS_LOCK_PATH = REPO / "app" / "public" / "fy2027_data.json"
DATA_GENERATOR_PATH = REPO / "scripts_build_data.py"
CASE_LOADER_PATH = REPO / "snap_qc_sim" / "data.py"
OUTPUT_PATH = REPO / "analysis" / "aging_path.json"
MEMO_PATH = REPO / "analysis" / "AGING_PATH.md"

STATES = ("AZ", "CA", "CO", "GA", "MD", "NY", "TX")
YEARS = (2026, 2027)
CONVENTIONS = ("D-fixed", "D-proportional")
WEIGHT_BASIS = {year: f"C3_FY{year}_new_weight" for year in YEARS}
BASE_THRESHOLD = 56


def sha256(path: Path) -> str:
    """Return the file's SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mechanical_rate(state: dict, threshold: int | None = None) -> float:
    """Compute weighted counted-error dollars divided by weighted issuance."""
    numerator = sum(
        weight * error
        for weight, error in zip(state["w"], state["err"], strict=True)
        if threshold is None or error > threshold
    )
    denominator = sum(
        weight * issuance
        for weight, issuance in zip(state["w"], state["iss"], strict=True)
    )
    return 100.0 * numerator / denominator


def _thresholds(parameters: dict) -> dict[int, tuple[int, str]]:
    series = {row["fiscal_year"]: row for row in parameters["threshold_series"]}
    assert series[2026]["threshold_dollars"] == 58
    assert series[2026]["status"] == "official"
    assert series[2027]["threshold_dollars"] == 59
    assert series[2027]["status"] == "ESTIMATE"
    return {2026: (58, "PUBLISHED"), 2027: (59, "ESTIMATE")}


def _grid_rows(grid: dict) -> dict[tuple[str, int, str, str], dict]:
    rows = {
        (
            row["jurisdiction"],
            row["fiscal_year"],
            row["convention"],
            row["weight_basis"],
        ): row
        for row in grid["grid"]
        if row.get("applicability") == "VERIFIED_CASE_REPRICING"
    }
    assert len(rows) == len(STATES) * len(YEARS) * len(CONVENTIONS) * 2
    return rows


def build() -> dict:
    """Return the deterministic aging-path artifact."""
    grid = json.loads(GRID_PATH.read_text())
    data = json.loads(DATA_PATH.read_text())
    parameters = json.loads(PARAMETERS_PATH.read_text())
    cross_lock = json.loads(CROSS_LOCK_PATH.read_text())
    thresholds = _thresholds(parameters)
    rows = _grid_rows(grid)
    cells = []
    vendored = []

    for state in STATES:
        source = data["states"][state]
        base = mechanical_rate(source)
        for year in YEARS:
            threshold, status = thresholds[year]
            threshold_rate = mechanical_rate(source, threshold)
            delta_threshold = threshold_rate - base
            assert delta_threshold <= 0
            for convention in CONVENTIONS:
                old_key = (state, year, convention, "FY2024_HWGT")
                new_key = (state, year, convention, WEIGHT_BASIS[year])
                old_row, new_row = rows[old_key], rows[new_key]
                assert old_row["qc_tolerance_threshold_dollars"] == threshold
                assert new_row["qc_tolerance_threshold_dollars"] == threshold
                assert old_row["parameter_status"] == status
                assert new_row["parameter_status"] == status
                old_rate = old_row["measured_rate_percent"]
                joint = new_row["measured_rate_percent"]
                delta_reprice = old_rate - threshold_rate
                delta_reweight = joint - old_rate
                aged_center = source["official_fy2025"] + joint - base
                telescope = base + delta_threshold + delta_reprice + delta_reweight
                assert abs(telescope - joint) <= 1e-9
                band = cross_lock["states"][state]["bands"][str(year)]
                target_key = (
                    "anchored_fixed_pct"
                    if convention == "D-fixed"
                    else "anchored_proportional_pct"
                )
                assert round(aged_center, 4) == band[target_key]
                cells.append(
                    {
                        "state": state,
                        "fiscal_year": year,
                        "convention": convention,
                        "base_pct": base,
                        "delta_threshold_pp": delta_threshold,
                        "delta_reprice_pp": delta_reprice,
                        "delta_reweight_pp": delta_reweight,
                        "joint_pct": joint,
                        "aged_center_pct": aged_center,
                        "flat_center_delta_pp": aged_center - source["official_fy2025"],
                        "qc_threshold_dollars": threshold,
                        "parameter_status": status,
                    }
                )
                vendored.append(
                    {
                        "state": state,
                        "fiscal_year": year,
                        "convention": convention,
                        "fy2024_hwgt_measured_rate_pct": old_rate,
                        "c3_measured_rate_pct": joint,
                    }
                )

    return {
        "schema_version": 1,
        "definitions": {
            "base_pct": "FY2024 mechanical rate using FY2024 weights, FY2024 prices, and the strict $56 threshold.",
            "delta_threshold_pp": "Change from replacing the strict $56 threshold with the fiscal-year threshold while holding FY2024 weights and prices fixed.",
            "delta_reprice_pp": "Residual from the FY2024-weight grid rate, which already embeds the new threshold, after subtracting the threshold-only rate.",
            "delta_reweight_pp": "C3-weight grid rate minus the matching FY2024-weight grid rate.",
            "joint_pct": "Measured rate in the verified C3 grid row after threshold, repricing, and reweighting.",
            "aged_center_pct": "FY2025 official rate plus joint_pct minus base_pct, following the app payload's anchoring convention.",
            "flat_center_delta_pp": "Aged center minus the FY2025 official rate, which is the movement hidden by the current pinned mean.",
            "canonical_order_caveat": "The canonical ladder is threshold, reprice, then reweight; contributions are order-dependent residuals even though their sum and the joint endpoint are fixed.",
            "error_semantics": "data.json err is rounded AMTERR only for CASE=1, positive-weight, STATUS 2/3 cases with AMTERR strictly above $56; zero represents either no adjudicated error or an excluded amount.",
        },
        "input_hashes": {
            "snap-fy27-margins/reprice/state_rate_implications.json": sha256(GRID_PATH),
            "snap-fy27-margins/reprice/manifest.json": sha256(MANIFEST_PATH),
            "app/public/data.json": sha256(DATA_PATH),
            "analysis/fy2027_parameters.json": sha256(PARAMETERS_PATH),
            "app/public/fy2027_data.json": sha256(CROSS_LOCK_PATH),
            "scripts_build_data.py": sha256(DATA_GENERATOR_PATH),
            "snap_qc_sim/data.py": sha256(CASE_LOADER_PATH),
        },
        "inputs_vendored": {"grid_rates": vendored},
        "cells": cells,
        "disclosed_held_fixed": [
            "Composition beyond the committed C3 reweight.",
            "Behavioral response, which is the FY2026 pre-registration's subject rather than this artifact's.",
            "The official-vs-file wedge layer carried by the anchoring convention.",
            "National scope: 368 grid rows are NOT_APPLICABLE_NO_CASE_LEVEL_REPRICING, so no national aged path is reported without verified repricing.",
        ],
    }


def render_memo(artifact: dict) -> str:
    """Render the committed markdown memo from the artifact."""
    lines = [
        "# Aged baseline path",
        "",
        "This memo decomposes the mechanical movement from the FY2024 file rate to each verified C3 repriced rate. Read across each row in canonical order: the threshold contribution is applied first, repricing is the residual to the FY2024-weight grid row, and reweighting reaches the joint endpoint. The contributions are order-dependent, but the endpoint is not. The aged center then anchors that endpoint movement on the FY2025 official rate.",
        "",
        "## Factor ladder",
        "",
        "| State | FY | Convention | Base % | Threshold pp | Reprice pp | Reweight pp | Joint % | Aged center % | Flat delta pp | Status |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cell in artifact["cells"]:
        lines.append(
            f"| {cell['state']} | {cell['fiscal_year']} | {cell['convention']} "
            f"| {cell['base_pct']:.6f} | {cell['delta_threshold_pp']:.6f} "
            f"| {cell['delta_reprice_pp']:.6f} | {cell['delta_reweight_pp']:.6f} "
            f"| {cell['joint_pct']:.6f} | {cell['aged_center_pct']:.6f} "
            f"| {cell['flat_center_delta_pp']:.6f} | {cell['parameter_status']} |"
        )
    lines.extend(["", "## Held fixed", ""])
    lines.extend(f"- {item}" for item in artifact["disclosed_held_fixed"])
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            "Generated by `analysis/aging_path.py`; exact input hashes are recorded in `analysis/aging_path.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Write the JSON artifact and memo."""
    artifact = build()
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    MEMO_PATH.write_text(render_memo(artifact))
    print(f"wrote {OUTPUT_PATH.relative_to(REPO)} and {MEMO_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
