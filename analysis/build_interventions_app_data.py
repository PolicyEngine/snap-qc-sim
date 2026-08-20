"""Build the slim, hash-pinned interventions payload for the simulator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SOURCE = Path("analysis/interventions_results.json")
OUTPUT = Path("app/public/interventions_data.json")


def build_payload(source: dict) -> dict:
    scenarios = []
    for scenario in source["scenario_grid"]:
        states = {}
        for state, result in scenario["states"].items():
            single = result["single_measurement"]
            states[state] = {
                "single_measurement_delta_pp": result[
                    "single_measurement_delta_pp"
                ],
                "single_measurement_expected_share_pct": single[
                    "expected_share_pct"
                ],
                "single_measurement_expected_cost_share_dollars": single[
                    "expected_cost_share_dollars"
                ],
                "sustained_fy2028_30": {
                    year: {"expected_share_pct": values["expected_share_pct"]}
                    for year, values in result[
                        "sustained_intervention_fy2028_30"
                    ].items()
                },
                "sustained_expected_cost_share_dollars_3yr": result[
                    "sustained_expected_cost_share_dollars_3yr"
                ],
                "issuance_fy2024_dollars": result["issuance_fy2024_dollars"],
            }
        scenarios.append(
            {
                "ranking_rule": scenario["ranking_rule"],
                "coverage_pct": scenario["coverage_pct"],
                "effectiveness_pct": scenario["effectiveness_pct"],
                "states": states,
            }
        )
    return {
        "schema": "snap_qc_sim.interventions.v1",
        "interpretation": source["interpretation"],
        "sustained_intervention_assumption": source[
            "sustained_intervention_assumption"
        ],
        "delay_clause_not_modeled": source["delay_clause_not_modeled"],
        "threshold_convention": source["threshold_convention"],
        "boundary_case_rule": source["boundary_case_rule"],
        "scenarios": scenarios,
    }


def main() -> None:
    source = json.loads(SOURCE.read_bytes())
    payload = build_payload(source)
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(encoded)
    print(hashlib.sha256(encoded).hexdigest())


if __name__ == "__main__":
    main()
