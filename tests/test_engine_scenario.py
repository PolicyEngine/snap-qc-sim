"""Contract tests for the case-aligned engine-scenario data export."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from analysis import build_engine_scenario as builder
from snap_qc_sim.data import load_cases

ROOT = Path(__file__).resolve().parents[1]
CSV = builder.DEFAULT_CSV
DATA_PATH = ROOT / "app/public/data.json"
CAUSE_PATH = ROOT / "analysis/cause_shares.json"
EXPORT_PATH = ROOT / "app/public/engine_scenario_data.json"
APP_JS = ROOT / "app/public/app.js"


@pytest.fixture(scope="module")
def artifacts() -> tuple[dict, dict, dict]:
    """Load the three committed artifacts once for the contract tests."""
    return tuple(
        json.loads(path.read_text()) for path in (DATA_PATH, CAUSE_PATH, EXPORT_PATH)
    )


def test_data_json_case_order_exactly_reproduces_load_cases(artifacts) -> None:
    """Lock flags to the public data arrays' source-row ordering invariant."""
    data, _, _ = artifacts
    cases_by_state = load_cases(CSV)
    assert set(cases_by_state) == set(data["states"])
    for state, public in data["states"].items():
        cases = cases_by_state[state]
        assert [round(case.weight, 2) for case in cases] == public["w"], state
        assert [round(case.issuance) for case in cases] == public["iss"], state
        assert [round(case.error) for case in cases] == public["err"], state


def test_export_contract_and_exact_cause_share_gate(artifacts) -> None:
    """Gate A: exported unrounded-path shares reconcile to cause shares."""
    data, cause, export = artifacts
    assert export["schema"] == builder.SCHEMA
    assert "accounting bound" in export["accounting_note"]
    assert "not a causal estimate" in export["accounting_note"]
    assert set(export["states"]) == set(data["states"])
    cause_rows = {row["state"]: row for row in cause["rows"]}
    names = {
        "any_strict": "strict_computation",
        "any_broad": "broad_rules_engine",
    }
    for state, scenario in export["states"].items():
        case_count = len(data["states"][state]["w"])
        for flag_name, cause_name in names.items():
            flags = scenario[flag_name]
            assert len(flags) == case_count, (state, flag_name)
            assert set(flags) <= {0, 1}, (state, flag_name)
            expected = cause_rows[state]["case_attributed"][
                "scenario_subsets_any_presence"
            ]["classes"][cause_name]["share_of_official_error_dollars"]
            assert abs(scenario["shares"][flag_name] - expected) <= 1e-9


def test_rounded_public_arrays_stay_within_serialization_bound(artifacts) -> None:
    """Gate B: rounded arrays remain close at their known serialization scale."""
    data, _, export = artifacts
    differences = []
    for state, scenario in export["states"].items():
        public = data["states"][state]
        dollars = np.asarray(public["w"]) * np.asarray(public["err"])
        denominator = float(dollars.sum())
        for flag_name in ("any_strict", "any_broad"):
            flags = np.asarray(scenario[flag_name], dtype=bool)
            rounded_share = float(dollars[flags].sum() / denominator)
            differences.append(
                (
                    abs(rounded_share - scenario["shares"][flag_name]),
                    state,
                    flag_name,
                )
            )
    observed, state, flag_name = max(differences)
    # Round 1 observed 5.6772764079e-7; this guard allows serialization noise
    # while making the maximum visible if the underlying data contract drifts.
    assert observed <= 2e-6, (
        f"maximum rounded-array drift {observed:.12g} at {state} {flag_name}; "
        "round-1 reference maximum was 5.6772764079e-7"
    )


def test_builder_is_byte_deterministic(tmp_path: Path) -> None:
    """Two complete builds serialize byte-identically."""
    outputs = [tmp_path / "first.json", tmp_path / "second.json"]
    for output in outputs:
        builder.write_payload(builder.build_payload(), output)
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    assert outputs[0].read_bytes() == EXPORT_PATH.read_bytes()


def test_app_js_pins_the_scenario_payload_sha256() -> None:
    """The browser refuses a payload that does not hash to the committed pin."""
    js = APP_JS.read_text()
    pin = re.search(r'const ADOPT_DATA_SHA256 =\s*"([0-9a-f]{64})"', js)
    assert pin, "app.js must pin engine_scenario_data.json by SHA-256"
    assert pin.group(1) == builder.sha256(EXPORT_PATH)
