"""Commit the all-53 adoption sums the paper and app quote.

Runs the bit-faithful Python mirror of the browser engine
(analysis/adoption_mirror.py) over every jurisdiction at the committed
seed and draw count, and serializes per-state expected FY2028 bills for
the baseline and both cause-class scenarios plus their national sums.
The always-run contract test locks the quoted sums to this artifact and
ties the artifact to the live mirror through the exemplar states; full
regeneration is the local gate (several minutes of pure-Python RNG).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis.adoption_mirror import DATA, ROOT, run_state

OUTPUT = ROOT / "analysis/adoption_national.json"
SCHEMA = "snap_qc_sim.adoption_national.v1"


def sha256(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def build_payload() -> dict:
    states = {}
    sums = {"base": 0.0, "strict": 0.0, "broad": 0.0}
    for code in sorted(DATA["states"]):
        r = run_state(code)
        row = {k: round(r[k]["e28"], 2) for k in ("base", "strict", "broad")}
        states[code] = row
        for k in sums:
            sums[k] += r[k]["e28"]
    return {
        "schema": SCHEMA,
        "engine": {"seed": 11, "draws": 4000, "convention": "additive_anchor"},
        "provenance": {
            "data_json_sha256": sha256(ROOT / "app/public/data.json"),
            "engine_scenario_data_sha256": sha256(
                ROOT / "app/public/engine_scenario_data.json"
            ),
        },
        "national_expected_fy2028_bills_usd": {k: round(v, 2) for k, v in sums.items()},
        "states_expected_fy2028_bills_usd": states,
    }


def write_payload(payload: dict, output_path: Path = OUTPUT) -> None:
    output_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    )


def main() -> None:
    write_payload(build_payload())
    print(OUTPUT)


if __name__ == "__main__":
    main()
