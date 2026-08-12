"""Locks for the prospective OBBBA boundary preregistration artifact."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest

from analysis.preregister_obbba_boundary import (
    ALL_BOUNDARIES,
    DATA_JSON,
    DELAY_THRESHOLD,
    DRAWS,
    OUT_JSON,
    QUANTILE_LEVELS,
    TIER_CUTS,
    delay_secondary_test,
    election_stats,
    fixed_width_partition,
    main,
    mulberry32_stream,
    mulberry32_stream_loop,
    placebo_cut_rosters,
    placebo_cuts_test,
    pre_period_placebo_test,
    primary_test,
    rtm_shrinkage_parameters,
    rtm_shrunken_sensitivity_test,
    simulate,
)
from tests.test_adoption_numbers import election as adoption_election

ROOT = Path(__file__).resolve().parents[1]


def _artifact() -> dict:
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _payload() -> dict:
    return _artifact()["payload"]


def _key(value: float) -> str:
    return f"{value:g}"


@pytest.mark.parametrize("seed", [11, 1107])
def test_vectorized_mulberry32_matches_loop_reference(seed: int) -> None:
    count = 200_000
    assert np.array_equal(
        mulberry32_stream(seed, count),
        mulberry32_stream_loop(seed, count),
    )


def test_regeneration_is_byte_identical(tmp_path: Path) -> None:
    regenerated = tmp_path / OUT_JSON.name
    main(regenerated)
    assert regenerated.read_bytes() == OUT_JSON.read_bytes()


def test_payload_sha256_self_pin() -> None:
    artifact = _artifact()
    assert set(artifact) == {"payload", "payload_sha256"}
    canonical = json.dumps(
        artifact["payload"], sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == artifact["payload_sha256"]


@pytest.mark.parametrize("code", ["CO", "GA"])
def test_full_election_port_matches_existing_python_mirror(code: str) -> None:
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    state = data["states"][code]
    draws = simulate(state)
    actual = election_stats(state, draws)
    expected = adoption_election(state, draws)
    assert actual["elect28"] == pytest.approx(expected["e28"], rel=1e-12)
    assert actual["bill29"] == pytest.approx(expected["b29"], rel=1e-12)
    assert actual["pWin"] == expected["pWin"]
    assert actual["pDelay26"] == expected["pDelay26"]
    assert actual["lockShare"] == expected["lock"]


def test_committed_exemplar_and_national_goldens() -> None:
    predictions = _payload()["predictions"]
    states = predictions["states"]
    co = states["CO"]["variants"]["baseline"]["election"]
    ny = states["NY"]["variants"]["baseline"]["election"]
    ga = states["GA"]["variants"]["baseline"]["election"]

    assert co["elect28"] == pytest.approx(158.9e6, abs=0.05e6)
    assert co["pWin"] == pytest.approx(0.525, abs=0.002)
    assert ny["elect28"] == pytest.approx(629.9e6, abs=0.1e6)
    assert ny["pDelay26"] == pytest.approx(0.417, abs=0.002)
    assert ga["elect28"] == 0.0
    assert ga["pDelay26"] == pytest.approx(0.981, abs=0.002)
    assert ga["bill29"] == pytest.approx(8.7e6, abs=0.1e6)

    # The $7.671B quote's last displayed place is $1M; half that unit is the
    # honest rounding tolerance for the full-precision $7,671,249,968 result.
    assert predictions["national"]["sum_elect28_baseline"] == pytest.approx(
        7.671e9, abs=0.5e6
    )


def test_probability_window_rosters_reconstruct_from_predictions() -> None:
    payload = _payload()
    states = payload["predictions"]["states"]
    rosters = payload["design"]["rosters"]
    tier_windows = rosters["tier_probability_windows"]

    qualifying: dict[str, list[float]] = {code: [] for code in states}
    for cut in TIER_CUTS:
        key = _key(cut)
        probability_key = f"p_below_{int(cut)}"
        qualifiers = sorted(
            code
            for code, state in states.items()
            if 0.10 <= state["variants"]["baseline"][probability_key] <= 0.90
        )
        for code in qualifiers:
            qualifying[code].append(cut)
        expected = {
            "qualifiers": qualifiers,
            "above": [
                code for code in qualifiers if states[code]["official_fy2025"] >= cut
            ],
            "below": [
                code for code in qualifiers if states[code]["official_fy2025"] < cut
            ],
        }
        assert tier_windows["raw"][key] == expected

    assigned = {cut: [] for cut in TIER_CUTS}
    for code, cuts in qualifying.items():
        if cuts:
            fy25 = states[code]["official_fy2025"]
            cut = min(cuts, key=lambda value: (abs(fy25 - value), value))
            assigned[cut].append(code)
    for cut, qualifiers in assigned.items():
        expected = {
            "qualifiers": qualifiers,
            "above": [
                code for code in qualifiers if states[code]["official_fy2025"] >= cut
            ],
            "below": [
                code for code in qualifiers if states[code]["official_fy2025"] < cut
            ],
        }
        assert tier_windows["assigned"][_key(cut)] == expected

    delay_qualifiers = sorted(
        code
        for code, state in states.items()
        if 0.10 <= state["variants"]["baseline"]["p_delay26"] <= 0.90
    )
    expected_delay = {
        "qualifiers": delay_qualifiers,
        "above": [code for code in delay_qualifiers if states[code]["delay_fy2025"]],
        "below": [
            code for code in delay_qualifiers if not states[code]["delay_fy2025"]
        ],
    }
    assert rosters["delay_probability_window"] == expected_delay


def test_fixed_width_rosters_reconstruct_from_official_rates() -> None:
    payload = _payload()
    states = payload["predictions"]["states"]
    fixed = payload["design"]["rosters"]["fixed_width_windows"]
    for width in (0.75, 1.25):
        for boundary in ALL_BOUNDARIES:
            expected = sorted(
                code
                for code, state in states.items()
                if abs(state["official_fy2025"] - boundary) <= width
            )
            boundary_key = "13.3333" if boundary == DELAY_THRESHOLD else _key(boundary)
            assert fixed[_key(width)][boundary_key] == expected


def test_state_prediction_sanity() -> None:
    payload = _payload()
    states = payload["predictions"]["states"]
    assert len(states) == 53
    assert list(states) == sorted(states)
    assert payload["definitions"]["quantiles"]["levels"] == list(QUANTILE_LEVELS)

    for code, state in states.items():
        baseline = state["variants"]["baseline"]
        assert abs(baseline["mean"] - state["official_fy2025"]) < 0.25, code
        for variant_name, variant in state["variants"].items():
            assert (
                variant["p_below_6"]
                <= variant["p_below_8"]
                <= variant["p_below_10"]
            ), (code, variant_name)
            assert sum(variant["tier_probabilities"].values()) == pytest.approx(
                1.0, abs=5e-4
            ), (code, variant_name)
            quantiles = [variant["quantiles"][_key(q)] for q in QUANTILE_LEVELS]
            assert quantiles == sorted(quantiles), (code, variant_name)
            assert variant["p_win"] == variant["election"]["pWin"]
            assert variant["p_delay26"] == variant["election"]["pDelay26"]
            counts = variant["counts_of_4000"]
            assert variant["p_win"] == round(counts["win"] / DRAWS, 4)
            assert variant["p_delay26"] == round(counts["delay26"] / DRAWS, 4)
            for cut in (6, 8, 10):
                assert variant[f"p_below_{cut}"] == round(
                    counts[f"below_{cut}"] / DRAWS, 4
                ), (code, variant_name, cut)
            tier_count_total = 0
            for share in (0, 5, 10, 15):
                tier_count = counts[f"tier_{share}"]
                tier_count_total += tier_count
                assert variant["tier_probabilities"][f"p{share}"] == round(
                    tier_count / DRAWS, 4
                ), (code, variant_name, share)
            assert tier_count_total == DRAWS, (code, variant_name)


def test_committed_power_mc_locks() -> None:
    power = _payload()["power"]
    expected = {
        "primary": {"0.0": 0.0485, "0.25": 0.2205, "0.5": 0.534, "1.0": 0.9495},
        "delay": {"0.0": 0.052, "0.25": 0.1785, "0.5": 0.426, "1.0": 0.917},
        "primary_drift_robust_median_mad": {
            "0.0": 0.105, "0.25": 0.2085, "0.5": 0.3565, "1.0": 0.6935,
        },
        "delay_drift_robust_median_mad": {
            "0.0": 0.0915, "0.25": 0.1905, "0.5": 0.3625, "1.0": 0.7305,
        },
        "primary_drift_classical_method_of_moments": {
            "0.0": 0.114, "0.25": 0.203, "0.5": 0.3005, "1.0": 0.534,
        },
        "delay_drift_classical_method_of_moments": {
            "0.0": 0.1115, "0.25": 0.1985, "0.5": 0.3085, "1.0": 0.595,
        },
    }
    assert set(power) == set(expected)
    for name, rates in expected.items():
        assert power[name]["rejection_rates_by_delta_pp"] == rates, name
    # The drift-world delta = 0 rows are the registered test's size
    # distortion under the committed tau worlds; they must stay disclosed.
    for name in expected:
        if "drift" in name:
            assert power[name]["rejection_rates_by_delta_pp"]["0.0"] > 0.05


def test_simulation_draw_count_lock() -> None:
    assert DRAWS == 4_000


def test_rtm_shrinkage_sensitivity_locks() -> None:
    """The registered regression-to-the-mean sensitivity is executable and
    its global-Gaussian shrinkage magnitudes are locked (they are the
    committed evidence that published-rate RTM re-centering is small)."""
    shrinkage = rtm_shrinkage_parameters()
    assert shrinkage["mean_rate"] == pytest.approx(9.8166, abs=1e-3)
    assert shrinkage["var_true"] == pytest.approx(14.9144, abs=1e-3)
    lambdas = [entry["lambda"] for entry in shrinkage["states"].values()]
    assert min(lambdas) > 0.90
    assert max(lambdas) < 1.0
    assert shrinkage["states"]["CO"]["shift_pp"] == pytest.approx(
        -0.0142, abs=1e-3
    )

    payload = _payload()
    states = payload["predictions"]["states"]
    assigned = payload["design"]["rosters"]["tier_probability_windows"]["assigned"]
    window = sorted(
        code
        for cut in map(_key, TIER_CUTS)
        for side in ("above", "below")
        for code in assigned[cut][side]
    )
    result = rtm_shrunken_sensitivity_test(
        {code: states[code]["official_fy2025"] for code in window}
    )
    assert 0.0 <= result["p_value"] <= 1.0
    assert result["statistic"] == pytest.approx(0.0154, abs=5e-4)


def test_document_and_facts_quote_the_artifact_hashes() -> None:
    """The registration document, FACTS row, and artifact cannot drift apart.

    The pre-amendment body must carry exactly the current pins; a dated
    "## Amendments" section, if one ever exists, may quote historical pins
    (an append-only amendment necessarily lists old and new hashes).
    """
    file_hash = hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()
    payload_hash = _artifact()["payload_sha256"]
    document = (
        ROOT / "analysis" / "PREREGISTRATION_OBBBA_BOUNDARY.md"
    ).read_text(encoding="utf-8")
    facts = (ROOT / "paper" / "FACTS.md").read_text(encoding="utf-8")
    body = document.split("\n## Amendments", 1)[0]
    for text, name in ((body, "registration document"), (facts, "FACTS")):
        assert file_hash in text, f"artifact file hash missing from {name}"
        assert payload_hash in text, f"payload self-pin missing from {name}"
    assert set(re.findall(r"\b[0-9a-f]{64}\b", body)) == {
        file_hash,
        payload_hash,
    }


def test_preregistered_test_callables_run_on_locked_fy2025_rates() -> None:
    """Executable-spec smoke test: feed the locked FY2025 rates as if realized.

    With realized == official_fy2025, the midrank PIT reduces to p_win up to
    ties (draws are continuous, so ties are at most a few per state) and the
    4-decimal serialization of p_win.
    """
    payload = _payload()
    states = payload["predictions"]["states"]
    rosters = payload["design"]["rosters"]
    assigned = rosters["tier_probability_windows"]["assigned"]
    above = sorted(
        code for cut in map(_key, TIER_CUTS) for code in assigned[cut]["above"]
    )
    below = sorted(
        code for cut in map(_key, TIER_CUTS) for code in assigned[cut]["below"]
    )
    realized = {
        code: states[code]["official_fy2025"] for code in above + below
    }
    result = primary_test(realized)
    assert result["above"] == above
    assert result["below"] == below
    assert result["alternative"] == "T < 0"
    assert 0.0 <= result["p_value"] <= 1.0
    for code, pit in result["pit"].items():
        assert pit == pytest.approx(
            states[code]["variants"]["baseline"]["p_win"], abs=1e-3
        ), code
    expected_statistic = float(
        np.mean([states[code]["variants"]["baseline"]["p_win"] for code in above])
        - np.mean([states[code]["variants"]["baseline"]["p_win"] for code in below])
    )
    assert result["statistic"] == pytest.approx(expected_statistic, abs=2e-3)

    delay_codes = rosters["delay_probability_window"]["qualifiers"]
    delay_result = delay_secondary_test(
        {code: states[code]["official_fy2025"] for code in delay_codes}
    )
    assert delay_result["states"] == sorted(delay_codes)
    assert delay_result["alternative"] == "U > 0.5"
    assert 0.0 <= delay_result["p_value"] <= 1.0


def test_fixed_width_partition_and_missing_jurisdiction_rules() -> None:
    """The registered micro-rules are executable and locked."""
    partition = fixed_width_partition(1.25)
    assert partition["6"]["above"] == ["NJ", "NV", "OH", "WA", "WV"]
    assert partition["8"]["above"] == ["AR", "LA", "MO", "MT", "NH", "SC"]
    assert partition["10"]["above"] == ["AZ", "CA", "CO", "HI", "ME", "OK"]
    assert partition["13.3333"]["above"] == ["OR"]
    assert partition["13.3333"]["below"] == [
        "FL", "MA", "MD", "MN", "NY", "RI", "VA",
    ]
    assigned_states = [
        code
        for boundary in partition.values()
        for side in boundary.values()
        for code in side
    ]
    assert len(assigned_states) == len(set(assigned_states))

    payload = _payload()
    states = payload["predictions"]["states"]
    assigned = payload["design"]["rosters"]["tier_probability_windows"]["assigned"]
    window = sorted(
        code
        for cut in map(_key, TIER_CUTS)
        for side in ("above", "below")
        for code in assigned[cut][side]
    )
    realized = {
        code: states[code]["official_fy2025"] for code in window if code != "VI"
    }
    with pytest.raises(ValueError):
        primary_test(realized)
    reduced = primary_test(realized, missing_ok=True)
    assert reduced["missing"] == ["VI"]
    assert len(reduced["above"]) + len(reduced["below"]) == len(window) - 1
    assert 0.0 <= reduced["p_value"] <= 1.0


def test_pre_period_placebo_committed_result() -> None:
    """The FY2024-anchored placebo's outcome predates registration: lock it.

    Registered rule: FY2024-anchored draws (anchor = data.json "official"),
    windows/sides/assignment from those draws and the FY2024 rates, outcome
    = the published FY2025 rates, MC seed 20260935. The registration quotes
    these numbers; they may never drift silently.
    """
    result = pre_period_placebo_test()
    assert len(result["above"]) == 15
    assert len(result["below"]) == 17
    assert result["statistic"] == pytest.approx(0.073234, abs=5e-6)
    assert result["p_value"] == pytest.approx(0.76265, abs=5e-6)
    assert result["p_value"] > result["alpha"]


def test_placebo_cut_rosters_lock() -> None:
    """The 7/9 placebo windows are fixed by the committed draws and rates."""
    rosters = placebo_cut_rosters()
    assert rosters["assigned"]["7"]["above"] == ["NC"]
    assert rosters["assigned"]["7"]["below"] == ["NJ", "NV", "OH", "WA", "WV"]
    assert rosters["assigned"]["9"]["above"] == [
        "AL", "CO", "CT", "KS", "MI", "MS", "ND", "PA", "TN", "TX",
    ]
    assert rosters["assigned"]["9"]["below"] == [
        "AR", "LA", "MO", "MT", "NH", "SC",
    ]
    assert rosters["multi_window_reassignments"] == []

    payload = _payload()
    states = payload["predictions"]["states"]
    smoke = placebo_cuts_test(
        {
            code: states[code]["official_fy2025"]
            for cut in ("7", "9")
            for side in ("above", "below")
            for code in rosters["assigned"][cut][side]
        }
    )
    assert 0.0 <= smoke["p_value"] <= 1.0
