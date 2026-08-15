"""Fast locks for the committed mechanical aging-path artifact."""

import json
from pathlib import Path

from analysis.build_fy2027_app_data import mechanical_rate

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = json.loads((ROOT / "analysis/aging_path.json").read_text())
DATA = json.loads((ROOT / "app/public/data.json").read_text())
CROSS_LOCK = json.loads((ROOT / "app/public/fy2027_data.json").read_text())


def test_all_cells_telescope() -> None:
    assert len(ARTIFACT["cells"]) == 28
    for cell in ARTIFACT["cells"]:
        total = (
            cell["base_pct"]
            + cell["delta_threshold_pp"]
            + cell["delta_reprice_pp"]
            + cell["delta_reweight_pp"]
        )
        assert abs(total - cell["joint_pct"]) <= 1e-9


def test_reweight_matches_vendored_grid_rows() -> None:
    vendored = {
        (row["state"], row["fiscal_year"], row["convention"]): row
        for row in ARTIFACT["inputs_vendored"]["grid_rates"]
    }
    for cell in ARTIFACT["cells"]:
        row = vendored[(cell["state"], cell["fiscal_year"], cell["convention"])]
        expected = row["c3_measured_rate_pct"] - row["fy2024_hwgt_measured_rate_pct"]
        assert abs(cell["delta_reweight_pp"] - expected) <= 1e-12


def test_base_matches_app_mechanical_rate() -> None:
    for cell in ARTIFACT["cells"]:
        expected = mechanical_rate(DATA["states"][cell["state"]])
        assert abs(cell["base_pct"] - expected) <= 1e-12


def test_threshold_never_increases_rate() -> None:
    assert all(cell["delta_threshold_pp"] <= 0 for cell in ARTIFACT["cells"])


def test_aged_centers_cross_lock_to_app_payload() -> None:
    for cell in ARTIFACT["cells"]:
        band = CROSS_LOCK["states"][cell["state"]]["bands"][str(cell["fiscal_year"])]
        key = (
            "anchored_fixed_pct"
            if cell["convention"] == "D-fixed"
            else "anchored_proportional_pct"
        )
        assert round(cell["aged_center_pct"], 4) == band[key]


def test_fy2027_status_is_estimate() -> None:
    rows = [cell for cell in ARTIFACT["cells"] if cell["fiscal_year"] == 2027]
    assert rows
    assert all(cell["parameter_status"] == "ESTIMATE" for cell in rows)
