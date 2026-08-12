"""Build case-aligned rules-engine scenario flags for the browser simulator."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from snap_qc_sim.data import FIPS, THRESHOLD_FY2024, _num

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = Path("~/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv").expanduser()
CAUSE_SHARES = REPO_ROOT / "analysis/cause_shares.json"
DATA_JSON = REPO_ROOT / "app/public/data.json"
OUTPUT = REPO_ROOT / "app/public/engine_scenario_data.json"
SCHEMA = "snap_qc_sim.engine_scenario.v1"
SCENARIOS = {
    "any_strict": "strict_computation",
    "any_broad": "broad_rules_engine",
}
ACCOUNTING_NOTE = (
    "This is an accounting bound under recorded cause codes, not a causal "
    "estimate of errors a verified rules engine would prevent."
)


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def scenario_definitions(cause_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract and validate the serialized scenario definitions across states."""
    definitions: dict[str, dict[str, Any]] = {}
    rows = [row for row in cause_payload["rows"] if row["state"] != "US"]
    for output_name, cause_name in SCENARIOS.items():
        observed = {
            (
                tuple(
                    row["case_attributed"]["scenario_subsets_any_presence"]["classes"][
                        cause_name
                    ]["codes"]
                ),
                row["case_attributed"]["scenario_subsets_any_presence"]["classes"][
                    cause_name
                ]["label"],
            )
            for row in rows
        }
        if len(observed) != 1:
            raise ValueError(f"Inconsistent serialized definition for {cause_name}")
        codes, label = observed.pop()
        definitions[output_name] = {"codes": codes, "label": label}
    return definitions


def load_aligned_rows(
    csv_path: Path, definitions: dict[str, dict[str, Any]]
) -> dict[str, dict[str, list[float] | list[int]]]:
    """Read cases in the exact source order used by ``load_cases``."""
    states: dict[str, dict[str, list[float] | list[int]]] = defaultdict(
        lambda: {
            "weight": [],
            "error": [],
            "issuance": [],
            "any_strict": [],
            "any_broad": [],
        }
    )
    with csv_path.open() as source:
        for row in csv.DictReader(source):
            state = FIPS.get((row.get("STATE") or "").strip())
            if state is None:
                continue
            case_flag = _num(row.get("CASE"))
            if case_flag is not None and case_flag != 1:
                continue
            issuance = _num(row.get("RAWBEN"))
            if issuance is None:
                continue
            weight = _num(row.get("HWGT")) or 0.0
            if weight <= 0:
                continue
            amount = _num(row.get("AMTERR")) or 0.0
            official = (row.get("STATUS") or "").strip() in (
                "2",
                "3",
            ) and amount > THRESHOLD_FY2024
            causes = {
                int(value)
                for slot in range(1, 10)
                if (value := _num(row.get(f"AGENCY{slot}"))) is not None
            }
            state_rows = states[state]
            state_rows["weight"].append(weight)
            state_rows["issuance"].append(issuance)
            state_rows["error"].append(amount if official else 0.0)
            for flag_name in SCENARIOS:
                codes = definitions[flag_name]["codes"]
                state_rows[flag_name].append(int(not causes.isdisjoint(codes)))
    return dict(states)


def build_payload(
    csv_path: Path = DEFAULT_CSV,
    cause_path: Path = CAUSE_SHARES,
    data_path: Path = DATA_JSON,
) -> dict[str, Any]:
    """Build the deterministic export payload from committed definitions."""
    cause_payload = json.loads(cause_path.read_text())
    definitions = scenario_definitions(cause_payload)
    aligned = load_aligned_rows(csv_path, definitions)
    cause_rows = {row["state"]: row for row in cause_payload["rows"]}
    expected_states = set(FIPS.values())
    if set(aligned) != expected_states:
        raise ValueError("Source CSV does not contain all 53 jurisdictions")

    states = {}
    for state in sorted(expected_states):
        source = aligned[state]
        weight = np.asarray(source["weight"], dtype=float)
        error = np.asarray(source["error"], dtype=float)
        dollars = weight * error
        denominator = float(dollars.sum())
        shares = {}
        for flag_name, cause_name in SCENARIOS.items():
            flags = np.asarray(source[flag_name], dtype=bool)
            share = (
                0.0 if denominator == 0 else float(dollars[flags].sum() / denominator)
            )
            committed = cause_rows[state]["case_attributed"][
                "scenario_subsets_any_presence"
            ]["classes"][cause_name]["share_of_official_error_dollars"]
            if abs(share - committed) > 1e-9:
                raise AssertionError(
                    f"Gate A failed for {state} {cause_name}: {share} != {committed}"
                )
            shares[flag_name] = share
        states[state] = {
            "any_strict": source["any_strict"],
            "any_broad": source["any_broad"],
            "shares": shares,
        }

    sav_sha = cause_payload["provenance"]["input_sav"]["sha256"]
    return {
        "schema": SCHEMA,
        "provenance": {
            "sav_sha256": sav_sha,
            "csv_sha256": sha256(csv_path),
            "cause_shares_sha256": sha256(cause_path),
            "data_json_sha256": sha256(data_path),
        },
        "class_codes": {
            "strict": list(definitions["any_strict"]["codes"]),
            "broad": list(definitions["any_broad"]["codes"]),
        },
        "class_labels": {
            "strict": definitions["any_strict"]["label"],
            "broad": definitions["any_broad"]["label"],
        },
        "accounting_note": ACCOUNTING_NOTE,
        "states": states,
    }


def write_payload(payload: dict[str, Any], output_path: Path = OUTPUT) -> None:
    """Write compact, stable JSON with a trailing newline."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    )


def main() -> None:
    """Build the committed browser artifact."""
    write_payload(build_payload())
    print(f"{OUTPUT}: {OUTPUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
