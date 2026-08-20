"""Lock the browser interventions export to its analysis artifact."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "analysis" / "interventions_results.json"
PAYLOAD = ROOT / "app" / "public" / "interventions_data.json"
APP_JS = ROOT / "app" / "public" / "app.js"


def test_interventions_payload_schema_and_hash_pin() -> None:
    payload = json.loads(PAYLOAD.read_bytes())
    assert payload["schema"] == "snap_qc_sim.interventions.v1"
    digest = hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()
    pin = re.search(
        r'const INTERVENTIONS_DATA_SHA256 =\s*"([0-9a-f]{64})"',
        APP_JS.read_text(),
    )
    assert pin and pin.group(1) == digest


def test_every_interventions_value_is_copied_from_source() -> None:
    source = json.loads(SOURCE.read_bytes())
    payload = json.loads(PAYLOAD.read_bytes())
    source_grid = {
        (row["ranking_rule"], row["coverage_pct"], row["effectiveness_pct"]): row
        for row in source["scenario_grid"]
    }
    assert len(payload["scenarios"]) == len(source_grid)
    for row in payload["scenarios"]:
        original = source_grid[
            (row["ranking_rule"], row["coverage_pct"], row["effectiveness_pct"])
        ]
        assert set(row["states"]) == set(original["states"])
        for state, value in row["states"].items():
            old = original["states"][state]
            expected = {
                "single_measurement_delta_pp": old["single_measurement_delta_pp"],
                "single_measurement_expected_share_pct": old["single_measurement"][
                    "expected_share_pct"
                ],
                "single_measurement_expected_cost_share_dollars": old[
                    "single_measurement"
                ]["expected_cost_share_dollars"],
                "sustained_fy2028_30": {
                    year: {"expected_share_pct": result["expected_share_pct"]}
                    for year, result in old[
                        "sustained_intervention_fy2028_30"
                    ].items()
                },
                "sustained_expected_cost_share_dollars_3yr": old[
                    "sustained_expected_cost_share_dollars_3yr"
                ],
                "issuance_fy2024_dollars": old["issuance_fy2024_dollars"],
            }
            assert value == expected


def test_interventions_conventions_are_present_verbatim() -> None:
    source = json.loads(SOURCE.read_bytes())
    payload = json.loads(PAYLOAD.read_bytes())
    for key in (
        "interpretation",
        "sustained_intervention_assumption",
        "delay_clause_not_modeled",
        "threshold_convention",
        "boundary_case_rule",
    ):
        assert payload[key] == source[key]
