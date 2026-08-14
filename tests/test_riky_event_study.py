"""Fast contract and optional raw-data tests for the RI/KY event study."""

from __future__ import annotations

import hashlib
import json
import math

import pandas as pd
import pytest

from analysis import event_study


def _fixture_panel() -> pd.DataFrame:
    """Return a fixture suitable for tolerance, not platform hash, assertions.

    The optimizer can differ in last-bit floats across BLAS implementations
    (both studies share the fit_weights optimizer), so byte equality on
    regeneration output turns failures into unreadable flakes — one such
    Oregon failure was masking a real regression (see test_event_study.py).
    Tests therefore require same-process byte determinism and recover
    planted effects within tolerance; they never hash optimizer output
    across runs. Raw regeneration is value-locked (structure, key order,
    and non-float values exact; floats at rel=1e-9 with a 1e-12 absolute
    floor — see conftest), not byte-locked; only the committed artifact
    itself gets an exact-byte pin.
    """
    rows = []
    states = ["AL", "CA", "FL", "GA", "KY", "NM", "OR", "RI", "TX"]
    for state_index, state in enumerate(states):
        for year in event_study.RIKY_YEARS:
            trend = year - 2012
            treatment_shift = 0.0
            if year >= 2017:
                treatment_shift = {"RI": 2.0, "KY": 4.0}.get(state, 0.0)
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


def test_riky_fixture_schema_paths_and_donor_exclusions() -> None:
    result = event_study.build_riky_results(_fixture_panel())
    assert result["schema"] == "snap_qc_sim.riky_event_study.v1"
    assert result["scope"]["treated_states"] == ["RI", "KY"]
    assert result["scope"]["donor_pool"] == ["AL", "CA", "TX"]
    assert set(result["units"]) == {"RI", "KY"}
    for state in ("RI", "KY"):
        path = result["units"][state]["specifications"][
            "primary_exclude_fy2016_drop_fy2021"
        ]["outcomes"]["strict_computing_dollars_per_case_month"]["path"]
        assert len(path) == 13
        assert [row["event_time"] for row in path] == list(range(-4, 9))


def test_riky_fixture_is_deterministic_and_recovers_planted_effects() -> None:
    first = event_study.serialize_results(
        event_study.build_riky_results(_fixture_panel())
    )
    second = event_study.serialize_results(
        event_study.build_riky_results(_fixture_panel())
    )
    assert first == second
    result = json.loads(first)
    for state, planted in (("RI", 2.0), ("KY", 4.0)):
        outcome = result["units"][state]["specifications"][
            "primary_exclude_fy2016_drop_fy2021"
        ]["outcomes"]["strict_computing_dollars_per_case_month"]
        assert abs(outcome["effect"] - planted) < 0.05
        pre_gaps = [
            row["gap"] for row in outcome["path"] if row["year"] in range(2012, 2016)
        ]
        assert all(abs(gap) < 0.05 for gap in pre_gaps)
    pooled = result["pooled"]["statistics"]["strict_computing_dollars_per_case_month"][
        "effect"
    ]
    assert abs(pooled - 3.0) < 0.05


def test_committed_riky_artifact_contract() -> None:
    raw = event_study.RIKY_OUT.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "6b8b927033058c550ba9b17c9d249ff6b64a16bb905470511f69a92825df743e"
    )
    result = json.loads(raw)
    assert result["schema"] == "snap_qc_sim.riky_event_study.v1"
    assert result["scope"]["panel_years"] == list(range(2012, 2025))
    assert set(result["units"]) == {"RI", "KY"}
    assert set(result["pooled"]["statistics"]) == set(event_study.OUTCOMES)
    assert result["outcome_definitions"]["strict_codes"] == [17, 19, 20]
    assert result["units"]["RI"]["decision"]["verdict"] == "signal"
    assert result["units"]["KY"]["decision"]["verdict"] == "no_protocol_defined_signal"
    assert result["pooled"]["decision"]["verdict"] == "signal"
    assert (
        result["units"]["RI"]["permutation_inference"][
            "strict_computing_dollars_per_case_month"
        ]["absolute_rank"]
        == 1
    )
    assert (
        result["units"]["KY"]["permutation_inference"][
            "strict_computing_dollars_per_case_month"
        ]["absolute_rank"]
        == 13
    )
    assert (
        result["pooled"]["permutation_inference"][
            "strict_computing_dollars_per_case_month"
        ]["absolute_rank"]
        == 4
    )
    assert result["units"]["RI"]["specifications"][
        "primary_exclude_fy2016_drop_fy2021"
    ]["outcomes"]["strict_computing_dollars_per_case_month"]["effect"] == pytest.approx(
        2.89676409242692
    )
    assert result["units"]["KY"]["specifications"][
        "primary_exclude_fy2016_drop_fy2021"
    ]["outcomes"]["strict_computing_dollars_per_case_month"]["effect"] == pytest.approx(
        -0.5843029139007678
    )


def test_committed_riky_artifact_locks_paper_quoted_numbers() -> None:
    """Every number @sec-events quotes must be pinned to the committed artifact."""
    result = json.loads(event_study.RIKY_OUT.read_bytes())
    ri = result["units"]["RI"]["decision"]
    ky = result["units"]["KY"]["decision"]
    pooled = result["pooled"]["decision"]
    assert ri["strict_p_value"] == pytest.approx(0.023255813953488372)
    assert ri["client_placebo_p_value"] == pytest.approx(0.23255813953488372)
    assert ky["strict_p_value"] == pytest.approx(0.3023255813953488)
    assert ky["client_placebo_p_value"] == pytest.approx(0.11627906976744186)
    assert pooled["strict_p_value"] == pytest.approx(0.09302325581395349)
    assert pooled["client_placebo_p_value"] == pytest.approx(1.0)
    pooled_stat = result["pooled"]["statistics"][
        "strict_computing_dollars_per_case_month"
    ]
    assert pooled_stat["effect"] == pytest.approx(1.156230589263076)
    assert pooled_stat["per_unit_effects"]["RI"] == pytest.approx(2.89676409242692)
    assert pooled_stat["per_unit_effects"]["KY"] == pytest.approx(-0.5843029139007678)
    profile = result["rhode_island_consequence_window_profile"]
    assert profile["outcome"] == "strict_computing_dollars_per_case_month"
    assert profile["consequence_window_mean_gap"] == pytest.approx(4.950350949271175)
    assert profile["later_post_mean_gap"] == pytest.approx(1.4827104665997337)
    assert profile["consequence_minus_later"] == pytest.approx(3.467640482671441)
    assert profile["changes_verdict"] is False


def test_riky_serializer_reproduces_committed_bytes() -> None:
    """serialize_results must rebuild the committed bytes from parsed values.

    The raw regeneration test is value-locked, so it can no longer catch
    a serializer formatting change (indent, trailing newline, escaping);
    this round-trip does, cache-free, in CI.
    """
    raw = event_study.RIKY_OUT.read_bytes()
    assert event_study.serialize_results(json.loads(raw)) == raw


def test_riky_value_lock_detects_planted_drift(assert_artifact_values_match) -> None:
    """The value lock fails on planted drift and tolerates last-ulp noise.

    Adversarial guard on the comparator itself: a relative 1e-6 float
    mutation, an int retyped to float, and a key reorder must each
    fail, while a one-ulp nudge of a nonzero leaf (the byte-flake class
    the lock exists to absorb) must pass.
    """
    committed = json.loads(event_study.RIKY_OUT.read_bytes())

    drifted = json.loads(event_study.RIKY_OUT.read_bytes())
    drifted["units"]["RI"]["decision"]["strict_p_value"] *= 1 + 1e-6
    with pytest.raises(AssertionError):
        assert_artifact_values_match(drifted, committed)

    retyped = json.loads(event_study.RIKY_OUT.read_bytes())
    inference = retyped["units"]["RI"]["permutation_inference"][
        "strict_computing_dollars_per_case_month"
    ]
    inference["absolute_rank"] = float(inference["absolute_rank"])
    with pytest.raises(AssertionError):
        assert_artifact_values_match(retyped, committed)

    reordered = json.loads(event_study.RIKY_OUT.read_bytes())
    scope = reordered["scope"]
    first_key = next(iter(scope))
    scope[first_key] = scope.pop(first_key)
    with pytest.raises(AssertionError):
        assert_artifact_values_match(reordered, committed)

    nudged = json.loads(event_study.RIKY_OUT.read_bytes())
    decision = nudged["units"]["RI"]["decision"]
    decision["strict_p_value"] = math.nextafter(decision["strict_p_value"], math.inf)
    assert_artifact_values_match(nudged, committed)


@pytest.mark.skipif(
    not event_study.riky_raw_inputs_available(),
    reason="complete hash-audited mixed-format cache unavailable",
)
def test_raw_riky_regeneration_matches_committed_artifact(
    assert_artifact_values_match,
) -> None:
    """Regeneration reproduces the committed artifact value-for-value.

    Value-locked, not byte-locked: optimizer floats move in the last
    ulp across BLAS implementations and reruns (both studies share the
    fit_weights optimizer), so byte equality here pins noise and its
    failures read as flakes — the failure mode that masked a real
    Oregon regression (see test_event_study.py). Structure, key order,
    and non-float values must match exactly; floats at rel=1e-9 with a
    1e-12 absolute floor (see conftest). The committed bytes stay
    pinned by the SHA-256 assertion in the contract test above, and the
    serializer by its round-trip test.
    """
    regenerated = event_study.serialize_results(
        event_study.build_riky_results(event_study.build_riky_panel())
    )
    assert_artifact_values_match(
        json.loads(regenerated), json.loads(event_study.RIKY_OUT.read_bytes())
    )
