"""Vendor the FY2027-mode app payload from the margins artifacts.

Reads the C4b rate grid and C4a projections from the snap-fy27-margins
workspace (hash-recording every input), joins them with the app's own
committed data.json to compute each verified state's FY2024 mechanical
official-gate rate, and emits app/public/fy2027_data.json — the payload
the simulator's FY2027 panel renders.

Anchoring convention (matches the app's level discipline): the panel
displays official_fy2025 + (repriced_mechanical_rate − fy2024_mechanical
rate) per deviation convention, so parameter/composition effects ride as
deltas on the official anchor. The D-fixed/D-proportional pair brackets
the accounting-convention uncertainty; both are conventions, not
behavioral predictions.

Run from the repo root:
    uv run --frozen --extra analysis python analysis/build_fy2027_app_data.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MARGINS = REPO.parent / "snap-fy27-margins"
GRID_PATH = MARGINS / "reprice" / "state_rate_implications.json"
REPRICE_MANIFEST = MARGINS / "reprice" / "manifest.json"
PARAMS_FY2027 = MARGINS / "params" / "fy2027_params_projected.json"
DATA_JSON = REPO / "app" / "public" / "data.json"
MOVEMENT = REPO / "analysis" / "fy2025_movement.json"
OUT = REPO / "app" / "public" / "fy2027_data.json"

VERIFIED = ("AZ", "CA", "CO", "GA", "MD", "NY", "TX")
WEIGHT_BASIS = {2026: "C3_FY2026_new_weight", 2027: "C3_FY2027_new_weight"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mechanical_rate(state: dict) -> float:
    """The app engine's `point`: weighted error dollars over weighted issuance."""
    err = sum(w * e for w, e in zip(state["w"], state["err"], strict=True))
    iss = sum(w * i for w, i in zip(state["w"], state["iss"], strict=True))
    return 100.0 * err / iss


def main() -> None:
    grid = json.loads(GRID_PATH.read_text())
    data = json.loads(DATA_JSON.read_text())
    movement = json.loads(MOVEMENT.read_text())
    fy2027_params = json.loads(PARAMS_FY2027.read_text())

    rows = {
        (r["jurisdiction"], r["fiscal_year"], r["convention"]): r
        for r in grid["grid"]
        if r.get("applicability") == "VERIFIED_CASE_REPRICING"
        and r.get("weight_basis") == WEIGHT_BASIS[r["fiscal_year"]]
    }
    assert len(rows) == len(VERIFIED) * 2 * 2, sorted(rows)

    states = {}
    for code in VERIFIED:
        st = data["states"][code]
        base = mechanical_rate(st)
        bands = {}
        for year in (2026, 2027):
            fixed = rows[(code, year, "D-fixed")]["measured_rate_percent"]
            prop = rows[(code, year, "D-proportional")]["measured_rate_percent"]
            bands[str(year)] = {
                "mechanical_fixed_pct": round(fixed, 4),
                "mechanical_proportional_pct": round(prop, 4),
                "anchored_fixed_pct": round(st["official_fy2025"] + fixed - base, 4),
                "anchored_proportional_pct": round(
                    st["official_fy2025"] + prop - base, 4
                ),
            }
        states[code] = {
            "fy2024_mechanical_pct": round(base, 4),
            "official_fy2025_pct": st["official_fy2025"],
            "bands": bands,
        }

    tau = movement["drift_estimate"]["point_estimates"]
    thresholds = grid["qc_thresholds"]
    four_person = fy2027_params["parameters"]["maximum_allotment"]["values"][
        "48_states_dc"
    ]["4"]

    payload = {
        "schema": "snap_qc_sim.fy2027_mode.v1",
        "accounting_note": (
            "D-fixed and D-proportional are accounting conventions for "
            "carrying observed FY2024 deviations to repriced benefits, not "
            "behavioral predictions; the band between them is "
            "convention uncertainty."
        ),
        "provenance": {
            "grid_sha256": sha256(GRID_PATH),
            "reprice_manifest_sha256": sha256(REPRICE_MANIFEST),
            "fy2027_params_sha256": sha256(PARAMS_FY2027),
            "data_json_sha256": sha256(DATA_JSON),
            "movement_sha256": sha256(MOVEMENT),
        },
        "thresholds": thresholds,
        "fy2027_max_allotment_4p_48dc": {
            "dollars": four_person["possible_published_values"][0],
            "possible_published_values": four_person["possible_published_values"],
            "status": four_person["status"],
            "rule": "OBBBA §10101: June-to-June CPI-U indexation of 7 U.S.C. 2012(u)",
        },
        "drift_tau_pp": {
            "robust": tau["robust_median_mad"]["tau_pp"],
            "classical": tau["classical_method_of_moments"]["tau_pp"],
            "calibration": "single FY2024→FY2025 transition; see analysis/fy2025_movement.json",
        },
        "states": states,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(REPO)} sha256={sha256(OUT)[:16]}…")


if __name__ == "__main__":
    main()
