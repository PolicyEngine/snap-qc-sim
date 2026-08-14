"""Fast contract and optional raw-data tests for the event study."""

from __future__ import annotations

import hashlib
import json
import math

import pandas as pd
import pytest

from analysis import event_study


def _fixture_panel() -> pd.DataFrame:
    rows = []
    states = ["AL", "CA", "GA", "OR", "TX"]
    for state_index, state in enumerate(states):
        for year in event_study.YEARS:
            trend = year - 2017
            treatment_shift = 2.0 if state == "OR" and year >= 2022 else 0.0
            rows.append(
                {
                    "state": state,
                    "year": year,
                    "strict_computing_dollars_per_case_month": (
                        1.0 + state_index * 0.2 + trend * 0.1 + treatment_shift
                    ),
                    "total_error_rate": (
                        4.0 + state_index * 0.3 + trend * 0.2 + treatment_shift
                    ),
                    "client_dollars_per_case_month": (
                        2.0 + state_index * 0.1 + trend * 0.05
                    ),
                }
            )
    return pd.DataFrame(rows)


def test_result_schema_and_paths() -> None:
    result = event_study.build_results(_fixture_panel())
    assert result["schema"] == "snap_qc_sim.event_study.v1"
    assert result["scope"]["primary_treated_state"] == "OR"
    assert result["scope"]["donor_pool"] == ["AL", "CA", "TX"]
    assert set(result["specifications"]) == set(event_study.SPECIFICATIONS)
    assert set(result["permutation_inference"]) == set(event_study.OUTCOMES)
    for outcome in event_study.OUTCOMES:
        path = result["specifications"]["primary_drop_fy2021"]["outcomes"][outcome][
            "path"
        ]
        assert len(path) == 8
        assert [row["event_time"] for row in path] == list(range(-4, 4))


def test_verdict_follows_frozen_rule() -> None:
    decision = event_study.build_results(_fixture_panel())["decision"]
    expected = (
        "signal"
        if decision["strict_p_value"] < 0.10
        and decision["client_placebo_p_value"] >= 0.10
        else "no_protocol_defined_signal"
    )
    assert decision["verdict"] == expected
    assert decision["adoption_gate"] is False


def test_fixture_is_deterministic_and_recovers_the_planted_effect() -> None:
    """Same-process byte determinism plus tolerance checks on the fixture.

    No cross-platform byte hash here: the synthetic-control weights come
    from an optimizer whose last-bit floats differ between macOS
    Accelerate and Linux OpenBLAS, so a fixture hash pins the platform,
    not the science. The same class bites within one machine: a
    2026-08-14 rerun of the raw regeneration moved last-ulp float bytes
    while a value-level walk found zero differences at rel=1e-9. The
    committed-artifact test below therefore pins exact bytes, while raw
    regeneration is value-locked, not byte-locked: identical structure,
    key order, and non-float values, floats at rel=1e-9 with a 1e-12
    absolute floor at near-zero leaves (see conftest).
    """
    first = event_study.serialize_results(event_study.build_results(_fixture_panel()))
    second = event_study.serialize_results(event_study.build_results(_fixture_panel()))
    assert first == second
    result = json.loads(first)
    path = result["specifications"]["primary_drop_fy2021"]["outcomes"][
        "strict_computing_dollars_per_case_month"
    ]["path"]
    # The fixture plants its +2.0 shift from 2022 (event time 1 onward);
    # event time 0 (FY2021) carries no planted effect.
    shifted = [row["gap"] for row in path if row["event_time"] >= 1]
    unshifted = [row["gap"] for row in path if row["event_time"] <= 0]
    assert all(abs(g) < 0.05 for g in unshifted), unshifted
    assert all(abs(g - 2.0) < 0.05 for g in shifted), shifted


def test_committed_result_schema_and_sha() -> None:
    raw = event_study.OUT.read_bytes()
    result = json.loads(raw)
    assert result["schema"] == "snap_qc_sim.event_study.v1"
    assert result["decision"]["verdict"] == "no_protocol_defined_signal"
    assert (
        hashlib.sha256(raw).hexdigest()
        == "2ad9107b6633ffb55e969d07c11f5b7602e857d4b691e0e9498d4c82debcc37f"
    )


def test_serializer_reproduces_committed_bytes() -> None:
    """serialize_results must rebuild the committed bytes from parsed values.

    The raw regeneration test is value-locked, so it can no longer catch
    a serializer formatting change (indent, trailing newline, escaping);
    this round-trip does, cache-free, in CI. Optimizer nondeterminism is
    not involved: parsed committed floats re-serialize exactly by repr
    round-trip.
    """
    raw = event_study.OUT.read_bytes()
    assert event_study.serialize_results(json.loads(raw)) == raw


def test_value_lock_tolerance_contract(assert_artifact_values_match) -> None:
    """Executably pin the tolerance function: max(1e-9 * |expected|, 1e-12).

    The absolute floor exists for exact-zero leaves (optimizer-clipped
    donor weights), where the relative term vanishes and regeneration
    may emit sub-1e-12 boundary noise. It is far larger than one ulp at
    zero, which is why the policy is pinned here rather than assumed.
    """
    assert_artifact_values_match(9.0e-13, 0.0)
    with pytest.raises(AssertionError):
        assert_artifact_values_match(2.0e-12, 0.0)
    assert_artifact_values_match(1.0 + 5.0e-10, 1.0)
    with pytest.raises(AssertionError):
        assert_artifact_values_match(1.0 + 2.0e-9, 1.0)


def test_value_lock_detects_planted_drift(assert_artifact_values_match) -> None:
    """The value lock fails on planted drift and tolerates last-ulp noise.

    Adversarial guard on the comparator itself: a relative 1e-6 float
    mutation, a non-float change, a dropped key, and a 2e-12 lift of an
    exact-zero donor weight must each fail, while a one-ulp nudge of a
    nonzero leaf (the byte-flake class the lock exists to absorb) must
    pass.
    """
    committed = json.loads(event_study.OUT.read_bytes())

    drifted = json.loads(event_study.OUT.read_bytes())
    drifted["decision"]["strict_p_value"] *= 1 + 1e-6
    with pytest.raises(AssertionError):
        assert_artifact_values_match(drifted, committed)

    relabeled = json.loads(event_study.OUT.read_bytes())
    relabeled["decision"]["verdict"] = "signal"
    with pytest.raises(AssertionError):
        assert_artifact_values_match(relabeled, committed)

    thinned = json.loads(event_study.OUT.read_bytes())
    del thinned["decision"]["strict_p_value"]
    with pytest.raises(AssertionError):
        assert_artifact_values_match(thinned, committed)

    lifted = json.loads(event_study.OUT.read_bytes())
    weights = lifted["specifications"]["drop_fy2020_and_fy2021"]["donor_weights"]
    assert weights["AL"] == 0.0, "expected an exact-zero clipped donor weight"
    weights["AL"] = 2.0e-12
    with pytest.raises(AssertionError):
        assert_artifact_values_match(lifted, committed)

    nudged = json.loads(event_study.OUT.read_bytes())
    nudged["decision"]["strict_p_value"] = math.nextafter(
        nudged["decision"]["strict_p_value"], math.inf
    )
    assert_artifact_values_match(nudged, committed)


@pytest.mark.skipif(
    not event_study.raw_inputs_available(), reason="audited raw SAV cache unavailable"
)
def test_raw_sav_regeneration_matches_committed_artifact(
    assert_artifact_values_match,
) -> None:
    """Regeneration reproduces the committed artifact value-for-value.

    Value-locked, not byte-locked: this regeneration byte-flaked on one
    machine on 2026-08-14 — last-ulp floats, zero value-level
    differences at rel=1e-9 — so byte equality here pins noise, not
    science. Structure, key order, and non-float values must match
    exactly; floats at rel=1e-9 with a 1e-12 absolute floor (see
    conftest). The committed bytes themselves stay pinned by the
    SHA-256 test above, and the serializer by its round-trip test.
    """
    regenerated = event_study.serialize_results(
        event_study.build_results(event_study.build_panel())
    )
    assert_artifact_values_match(
        json.loads(regenerated), json.loads(event_study.OUT.read_bytes())
    )
