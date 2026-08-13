"""The committed national adoption sums stay true to their sources.

Fast tier: the artifact's sums equal the values the paper and app quote,
its provenance hashes match the committed inputs, and its exemplar rows
equal a live mirror recomputation. Full tier: the artifact regenerates
byte-identically from the mirror (about 45 seconds of bit-faithful RNG).
"""

from __future__ import annotations

import json

import pytest

from analysis import build_adoption_national as builder
from analysis.adoption_mirror import DATA, run_state

ARTIFACT = json.loads(builder.OUTPUT.read_text())


def test_schema_and_provenance_match_current_inputs() -> None:
    assert ARTIFACT["schema"] == builder.SCHEMA
    assert ARTIFACT["engine"] == {
        "seed": 11,
        "draws": 4000,
        "convention": "additive_anchor",
    }
    prov = ARTIFACT["provenance"]
    assert prov["data_json_sha256"] == builder.sha256(
        builder.ROOT / "app/public/data.json"
    )
    assert prov["engine_scenario_data_sha256"] == builder.sha256(
        builder.ROOT / "app/public/engine_scenario_data.json"
    )
    assert set(ARTIFACT["states_expected_fy2028_bills_usd"]) == set(DATA["states"])


def test_national_sums_match_the_quoted_figures() -> None:
    """FACTS M2 and the app takeaway quote these three sums."""
    n = ARTIFACT["national_expected_fy2028_bills_usd"]
    assert n["base"] == pytest.approx(7.671e9, abs=0.5e6)
    assert n["strict"] == pytest.approx(7.574e9, abs=0.5e6)
    assert n["broad"] == pytest.approx(6.941e9, abs=0.5e6)
    per_state = ARTIFACT["states_expected_fy2028_bills_usd"]
    for key in ("base", "strict", "broad"):
        assert sum(row[key] for row in per_state.values()) == pytest.approx(
            n[key], abs=1.0
        )


def test_exemplar_rows_equal_live_mirror() -> None:
    """Ties the artifact to the engine mirror, not just to itself."""
    for code in ("CO", "NY", "GA"):
        live = run_state(code)
        row = ARTIFACT["states_expected_fy2028_bills_usd"][code]
        for key in ("base", "strict", "broad"):
            assert row[key] == pytest.approx(live[key]["e28"], abs=0.01), (code, key)


def test_full_regeneration_is_byte_identical(tmp_path) -> None:
    """The strongest lock: rebuild all 53 states and compare bytes."""
    out = tmp_path / "adoption_national.json"
    builder.write_payload(builder.build_payload(), out)
    assert out.read_bytes() == builder.OUTPUT.read_bytes()
