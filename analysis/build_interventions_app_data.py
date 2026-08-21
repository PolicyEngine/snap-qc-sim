"""Build the slim, hash-pinned interventions payload for the simulator.

Includes each jurisdiction's per-case out-of-sample model scores so the
browser's model ranking is the artifact's ranking, not the fitted-risk
array the scenario machinery ships for other purposes. Emission asserts
the analysis frame's per-case weight, issuance, and counted-error
sequences equal data.json's exactly, which proves the score arrays align
with the client's case order.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

SOURCE = Path("analysis/interventions_results.json")
DATA_JSON = Path("app/public/data.json")
OUTPUT = Path("app/public/interventions_data.json")


def per_state_scores() -> dict[str, list[float]]:
    """Out-of-sample FY2024 model scores in data.json case order.

    The SAV-derived analysis frame and the CSV-derived client payload
    order cases differently and store the same values with different
    float precision, so both sides sort by (weight, issuance,
    counted-error) and pair positionally. Each pair must agree within a
    cent on every key; cases tied on the full key are interchangeable in
    every quantity the app computes from a membership, so stable-sort
    occurrence pairing cannot change any displayed number. The
    delta-equality test locks the end result.
    """
    from analysis import interventions

    _, joined = interventions._case_inputs()
    client = json.loads(DATA_JSON.read_text())["states"]
    scores: dict[str, list[float]] = {}
    for state, group in joined.groupby("state", sort=True):
        if state not in client:
            continue
        cases = client[state]
        cw = np.asarray(cases["w"], dtype=float)
        ciss = np.asarray(cases["iss"], dtype=float)
        cerr = np.asarray(cases["err"], dtype=float)
        # Mirror scripts_build_data.py's client rounding exactly so both
        # sides sort identically: weight 2dp, dollars to whole units.
        aw = np.round(group["HWGT"].to_numpy(float), 2)
        aiss = np.round(group["RAWBEN"].to_numpy(float))
        aerr = np.round(group["counted_error_dollars"].to_numpy(float))
        ascore = group["model_score"].to_numpy(float)
        if len(cw) != len(aw):
            raise AssertionError(f"{state}: case counts differ")
        corder = np.lexsort((cerr, ciss, cw))
        aorder = np.lexsort((aerr, aiss, aw))
        for ours, theirs, label in (
            (aw[aorder], cw[corder], "weight"),
            (aiss[aorder], ciss[corder], "issuance"),
            (aerr[aorder], cerr[corder], "error"),
        ):
            gap = float(np.abs(ours - theirs).max())
            if gap > 0.011:  # both sides now share the client's rounding
                raise AssertionError(
                    f"{state}: sorted {label} sequences differ by {gap}"
                )
        out = np.empty(len(cw))
        out[corder] = ascore[aorder]
        scores[state] = [round(float(s), 8) for s in out]
    return scores


def build_payload(source: dict) -> dict:
    scenarios = []
    for scenario in source["scenario_grid"]:
        states = {}
        for state, result in scenario["states"].items():
            single = result["single_measurement"]
            states[state] = {
                "single_measurement_delta_pp": result["single_measurement_delta_pp"],
                "single_measurement_expected_share_pct": single["expected_share_pct"],
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
        "model_scores": per_state_scores(),
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
