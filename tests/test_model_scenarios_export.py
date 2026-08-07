"""Contract tests for the case-level browser scenario export."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from analysis import counterfactual_join
from scripts_build_model_data import QUANTILE_COLUMNS, QUANTILE_LEVELS
from scripts_build_model_scenarios import (
    _canonical_json_sha256,
    _crossing_probability,
    _read_bound_model_data,
    flip_smd_documentation_features,
    prepare_model_scenarios,
    render_document,
    serialize_json,
    validate_scenario_artifact,
    write_outputs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DATA = REPO_ROOT / "app" / "public" / "model_data.json"
MODEL_SCENARIOS = REPO_ROOT / "app" / "public" / "model_scenarios.json"
SCENARIO_DOCUMENT = REPO_ROOT / "analysis" / "MODEL_SCENARIOS.md"
MODEL_RESULTS = REPO_ROOT / "analysis" / "model_results.json"
COUNTERFACTUAL_SMD = REPO_ROOT / "analysis" / "counterfactual_co_smd.json"
BASE_SHA256 = "a" * 64
SMD_STATES_2024 = {
    "AL",
    "AR",
    "AZ",
    "CA",
    "CO",
    "GA",
    "IA",
    "ID",
    "IL",
    "KS",
    "KY",
    "LA",
    "MA",
    "MI",
    "MO",
    "ND",
    "NH",
    "OR",
    "RI",
    "SC",
    "SD",
    "TX",
    "VA",
    "VT",
    "WY",
}
LEVEL_GATED_STATES = {"AK", "HI", "ID", "MN", "SD", "VI", "WY"}
EXCLUDED_LEVERS = {
    "ssed",
    "heat_and_eat",
    "bbce_resources",
}


def _quantiles(value: float) -> dict[str, float]:
    return {column: value for column in QUANTILE_COLUMNS}


def _predictions() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return aligned current-policy and opposite-SMD-policy predictions."""
    baseline_rows = [
        {
            "case": 1,
            "state": "CO",
            "w": 1.0,
            "issuance": 100.0,
            "deviation_cap": 500.0,
            "p_dev": 0.10,
            "p_cross_distributional": 0.10,
            "medical_expense_above_floor": 1,
            "elderly_or_disabled": 1,
            "med_doc_required": 0,
            **_quantiles(4.6),
        },
        {
            "case": 1,
            "state": "CO",
            "w": 3.0,
            "issuance": 200.0,
            "deviation_cap": 500.0,
            "p_dev": 0.20,
            "p_cross_distributional": 0.20,
            "medical_expense_above_floor": 0,
            "elderly_or_disabled": 1,
            "med_doc_required": 0,
            **_quantiles(4.6),
        },
        {
            "case": 1,
            "state": "NY",
            "w": 2.0,
            "issuance": 300.0,
            "deviation_cap": 500.0,
            "p_dev": 0.30,
            "p_cross_distributional": 0.30,
            "medical_expense_above_floor": 1,
            "elderly_or_disabled": 1,
            "med_doc_required": 1,
            **_quantiles(4.6),
        },
        {
            "case": 1,
            "state": "NY",
            "w": 2.0,
            "issuance": 400.0,
            "deviation_cap": 500.0,
            "p_dev": 0.40,
            "p_cross_distributional": 0.40,
            "medical_expense_above_floor": 1,
            "elderly_or_disabled": 0,
            "med_doc_required": 0,
            **_quantiles(4.6),
        },
    ]
    baseline = pd.DataFrame(baseline_rows, index=[11, 13, 17, 19])
    flipped = baseline.copy()

    # CO currently has an SMD, so its opposite-policy prediction is SMD-off.
    flipped.loc[11, "med_doc_required"] = 1
    flipped.loc[11, "p_dev"] = 0.15
    flipped.loc[11, "p_cross_distributional"] = 0.15
    flipped.loc[11, list(QUANTILE_COLUMNS)] = 4.7

    # NY currently lacks an SMD, so its opposite-policy prediction is SMD-on.
    flipped.loc[17, "med_doc_required"] = 0
    flipped.loc[17, "p_dev"] = 0.25
    flipped.loc[17, "p_cross_distributional"] = 0.25
    flipped.loc[17, list(QUANTILE_COLUMNS)] = 4.5
    return baseline, flipped


def _model_data_payload() -> dict:
    q = [[4.6] * len(QUANTILE_LEVELS), [4.6] * len(QUANTILE_LEVELS)]
    return {
        "schema_version": 2,
        "threshold": 56.0,
        "deviation_tolerance": 0.5,
        "quantile_levels": list(QUANTILE_LEVELS),
        "tail_scale_log": 0.25,
        "q_units": "natural_log_dollars",
        "q_encoding": {"rounding": "significant_figures", "digits": 4},
        "level_ratio_gate": {
            "scalar_key": "level_ratio",
            "flag_key": "level_flag",
            "inclusive_bounds": [0.7, 1.4],
            "ratio": "factor-adjusted analytic model / observed FY2024 sample",
        },
        "states": {
            "CO": {
                "n": 2,
                "w": [1.0, 3.0],
                "iss": [100.0, 200.0],
                "p_dev": [0.10, 0.20],
                "cap": [500, 500],
                "q": copy.deepcopy(q),
                "level_ratio": 1.0,
                "level_flag": False,
            },
            "NY": {
                "n": 2,
                "w": [2.0, 2.0],
                "iss": [300.0, 400.0],
                "p_dev": [0.30, 0.40],
                "cap": [500, 500],
                "q": copy.deepcopy(q),
                "level_ratio": 1.5,
                "level_flag": True,
            },
        },
    }


def _model_results() -> dict:
    contrast = {
        "adoption_year": 2024,
        "descriptive_contrast_pp": 0.25,
    }
    return {
        "models": {
            "covariates_only": {"roc_auc": 0.760},
            "with_intermediates": {"roc_auc": 0.766},
            "lift": {"roc_auc": 0.006},
        },
        "smd_treatment_by_year": {
            "2024": {"treated_state_count": 1, "treated_states": ["CO"]}
        },
        "smd_adoption_contrasts": {
            "interpretation": "Descriptive calibration reference; not causal.",
            "populations": {
                "claimant_conditioned": {"CO": copy.deepcopy(contrast)},
                "all_elderly_disabled": {"CO": copy.deepcopy(contrast)},
            },
        },
    }


def _counterfactual_payload() -> dict:
    return {
        "schema": "snap_qc_sim.counterfactual_co_smd.v1",
        "feature_construction": {"documentation_flip_cases": 1},
        "scenarios": {
            "ceiling": {
                "engine_accounting": {
                    "benefit_changed_cases": 0,
                    "medical_deduction_changed_cases": 0,
                    "shelter_deduction_changed_cases": 0,
                    "net_income_changed_cases": 0,
                },
                "direct_official_error_classifier": {
                    "weighted_delta_pp": -0.75,
                    "uncertainty": {"confidence_interval": [-1.0, 0.1]},
                },
                "hurdle_expected_error_dollars": {
                    "hurdle_crossing_probability_delta_pp": -0.50
                },
            }
        },
    }


def _prepared_payload(*, bootstrap_draws: int = 256) -> dict:
    baseline, flipped = _predictions()
    report = prepare_model_scenarios(
        baseline,
        flipped,
        model_data_payload=_model_data_payload(),
        base_model_sha256=BASE_SHA256,
        smd_states={"CO"},
        model_results=_model_results(),
        counterfactual_payload=_counterfactual_payload(),
        bootstrap_draws=bootstrap_draws,
    )
    return report.get("data", report)


def _apply_parameter_patch(
    baseline_state: dict, scenario: dict
) -> tuple[list[float], list[list[float]]]:
    p_dev = list(baseline_state["p_dev"])
    quantiles = copy.deepcopy(baseline_state["q"])
    patch = scenario["per_case"]
    assert len(patch["i"]) == len(patch["p_dev"]) == len(patch["q"])
    for case_index, probability, row in zip(
        patch["i"], patch["p_dev"], patch["q"], strict=True
    ):
        p_dev[case_index] = probability
        quantiles[case_index] = row
    return p_dev, quantiles


def test_flip_smd_documentation_features_handles_both_policy_directions():
    baseline, _ = _predictions()
    original = baseline.copy(deep=True)

    flipped = flip_smd_documentation_features(baseline, {"CO"})

    assert flipped.index.equals(baseline.index)
    assert flipped["med_doc_required"].tolist() == [1, 0, 0, 0]
    pd.testing.assert_frame_equal(baseline, original)
    pd.testing.assert_frame_equal(
        flipped.drop(columns="med_doc_required"),
        baseline.drop(columns="med_doc_required"),
    )


def test_prepare_model_scenarios_normalizes_direction_and_exports_sparse_patches():
    payload = _prepared_payload()
    model_data = _model_data_payload()

    validate_scenario_artifact(
        payload,
        model_data_payload=model_data,
        base_model_sha256=BASE_SHA256,
    )
    assert payload["schema"] == "snap_qc_sim.model_scenarios.v1"
    assert payload["schema_version"] == 1
    assert payload["base_model"]["sha256"] == BASE_SHA256
    assert list(payload["states"]) == ["CO", "NY"]

    co = payload["states"]["CO"]
    co_smd = co["levers"]["smd"]
    assert co["level_flag"] is False
    assert co_smd["baseline_adopted"] is True
    assert co_smd["policy_flip_direction"] == "adopted_to_not_adopted"
    assert co_smd["feature_flip_direction"] == "0_to_1"
    assert co_smd["feature_flip_n"] == 1
    assert co_smd["parameter_patch_n"] == 1
    assert co_smd["delta_pp"] == pytest.approx(
        co_smd["adopted_crossing_rate_pct"] - co_smd["not_adopted_crossing_rate_pct"]
    )
    assert co_smd["delta_pp"] < 0
    assert co_smd["metric"] == "expected_threshold_crossing_probability"
    assert co_smd["unit"] == "percentage_points"
    assert co_smd["baseline_to_patch_delta_pp"] == pytest.approx(-co_smd["delta_pp"])
    assert co_smd["ci_lo"] <= co_smd["ci_hi"]
    assert co_smd["per_case"]["patch_endpoint"] == "not_adopted"
    assert co_smd["per_case"]["i"] == [0]
    co_p_dev, co_q = _apply_parameter_patch(model_data["states"]["CO"], co_smd)
    assert co_p_dev == pytest.approx([0.15, 0.20])
    assert co_q[0] == pytest.approx([4.7] * len(QUANTILE_LEVELS))
    assert co_q[1] == pytest.approx([4.6] * len(QUANTILE_LEVELS))

    ny = payload["states"]["NY"]
    ny_smd = ny["levers"]["smd"]
    assert ny["level_flag"] is True
    assert ny_smd["baseline_adopted"] is False
    assert ny_smd["policy_flip_direction"] == "not_adopted_to_adopted"
    assert ny_smd["feature_flip_direction"] == "1_to_0"
    assert ny_smd["feature_flip_n"] == 1
    assert ny_smd["parameter_patch_n"] == 1
    assert ny_smd["delta_pp"] == pytest.approx(
        ny_smd["adopted_crossing_rate_pct"] - ny_smd["not_adopted_crossing_rate_pct"]
    )
    assert ny_smd["delta_pp"] < 0
    assert ny_smd["baseline_to_patch_delta_pp"] == pytest.approx(ny_smd["delta_pp"])
    assert ny_smd["per_case"]["patch_endpoint"] == "adopted"
    assert ny_smd["per_case"]["i"] == [0]
    ny_p_dev, ny_q = _apply_parameter_patch(model_data["states"]["NY"], ny_smd)
    assert ny_p_dev == pytest.approx([0.25, 0.40])
    assert ny_q[0] == pytest.approx([4.5] * len(QUANTILE_LEVELS))
    assert ny_q[1] == pytest.approx([4.6] * len(QUANTILE_LEVELS))


def test_scenario_schema_carries_honest_inclusions_exclusions_and_gate_metadata():
    payload = _prepared_payload()

    definitions = payload["lever_definitions"]
    assert definitions["smd"]["included"] is True
    for lever in EXCLUDED_LEVERS:
        assert definitions[lever]["included"] is False
        assert definitions[lever]["reason"]

    gate = payload["level_ratio_gate"]
    assert gate["inclusive_bounds"] == [0.7, 1.4]
    assert gate["flagged_states"] == ["NY"]
    assert gate["disabled_reason"]


def test_scenario_serialization_and_documents_are_deterministic(tmp_path):
    first_payload = _prepared_payload()
    second_payload = _prepared_payload()

    assert serialize_json(first_payload) == serialize_json(second_payload)
    document = render_document(first_payload)
    lowered = document.lower()
    assert "model-implied association" in lowered
    assert "+0.006" in document
    assert "256 paired case-bootstrap" in document
    assert "does not pass" in document
    assert "for 1 case and" in first_payload["validation"]["co_smd"]["reference_reason"]
    assert "typically span zero" in lowered
    assert "descriptive adoption contrasts" in lowered

    first_json = tmp_path / "first.json"
    first_doc = tmp_path / "first.md"
    second_json = tmp_path / "second.json"
    second_doc = tmp_path / "second.md"
    write_outputs(first_payload, first_json, first_doc)
    write_outputs(second_payload, second_json, second_doc)

    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_doc.read_bytes() == second_doc.read_bytes()
    assert first_json.read_bytes() == serialize_json(first_payload)
    assert first_doc.read_text() == document


def test_validator_rejects_a_patch_index_outside_the_baseline_state():
    payload = _prepared_payload()
    payload["states"]["CO"]["levers"]["smd"]["per_case"]["i"] = [2]

    with pytest.raises(ValueError, match="index|range|bounds"):
        validate_scenario_artifact(
            payload,
            model_data_payload=_model_data_payload(),
            base_model_sha256=BASE_SHA256,
        )


def test_bound_model_data_rejects_payload_bytes_mismatch(tmp_path):
    path = tmp_path / "model_data.json"
    payload = _model_data_payload()
    path.write_text(json.dumps(payload))

    parsed, digest = _read_bound_model_data(path, payload)
    assert parsed == payload
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()

    changed = copy.deepcopy(payload)
    changed["threshold"] += 1
    with pytest.raises(ValueError, match="differs from the bytes"):
        _read_bound_model_data(path, changed)


def test_prepare_rejects_duplicate_prediction_rows_reordered_against_base_arrays():
    baseline, flipped = _predictions()
    baseline.loc[[11, 13], "p_dev"] = 0.10
    flipped.loc[13, "p_dev"] = 0.10
    model_data = _model_data_payload()
    model_data["states"]["CO"]["p_dev"] = [0.10, 0.10]
    order = [13, 11, 17, 19]

    with pytest.raises(ValueError, match="encoded baseline row arrays"):
        prepare_model_scenarios(
            baseline.loc[order],
            flipped.loc[order],
            model_data_payload=model_data,
            base_model_sha256=BASE_SHA256,
            smd_states={"CO"},
            model_results=_model_results(),
            counterfactual_payload=_counterfactual_payload(),
            bootstrap_draws=16,
        )


@pytest.mark.parametrize(
    ("scenario_key", "model_key"),
    [
        ("threshold_dollars", "threshold"),
        ("tail_scale_log", "tail_scale_log"),
        ("deviation_tolerance_dollars", "deviation_tolerance"),
    ],
)
def test_validator_binds_crossing_metadata_to_the_baseline(
    scenario_key,
    model_key,
):
    payload = _prepared_payload()
    model_data = _model_data_payload()
    payload["crossing"][scenario_key] = float(model_data[model_key]) + 1

    with pytest.raises(ValueError, match=scenario_key):
        validate_scenario_artifact(
            payload,
            model_data_payload=model_data,
            base_model_sha256=BASE_SHA256,
        )


def test_validator_binds_schema_and_quantile_encoding_to_the_baseline():
    model_data = _model_data_payload()
    for mutation in ("schema_version", "q_encoding"):
        payload = _prepared_payload()
        if mutation == "schema_version":
            payload["base_model"]["schema_version"] += 1
        else:
            payload["base_model"]["q_encoding"]["digits"] += 1

        with pytest.raises(ValueError, match="schema versions|quantile encodings"):
            validate_scenario_artifact(
                payload,
                model_data_payload=model_data,
                base_model_sha256=BASE_SHA256,
            )


def test_committed_scenario_artifact_schema_directions_gates_and_size():
    model_data = json.loads(MODEL_DATA.read_text())
    payload = json.loads(MODEL_SCENARIOS.read_text())
    base_sha256 = hashlib.sha256(MODEL_DATA.read_bytes()).hexdigest()

    validate_scenario_artifact(
        payload,
        model_data_payload=model_data,
        base_model_sha256=base_sha256,
    )
    assert len(payload["states"]) == 53
    assert set(payload["states"]) == set(model_data["states"])
    assert {
        state
        for state, data in payload["states"].items()
        if data["levers"]["smd"]["baseline_adopted"]
    } == SMD_STATES_2024
    assert {
        state for state, data in payload["states"].items() if data["level_flag"]
    } == LEVEL_GATED_STATES
    for state, data in payload["states"].items():
        smd = data["levers"]["smd"]
        expected_policy_direction = (
            "adopted_to_not_adopted"
            if state in SMD_STATES_2024
            else "not_adopted_to_adopted"
        )
        expected_feature_direction = "0_to_1" if state in SMD_STATES_2024 else "1_to_0"
        expected_endpoint = "not_adopted" if state in SMD_STATES_2024 else "adopted"
        assert smd["policy_flip_direction"] == expected_policy_direction
        assert smd["feature_flip_direction"] == expected_feature_direction
        assert smd["per_case"]["patch_endpoint"] == expected_endpoint

    definitions = payload["lever_definitions"]
    assert definitions["smd"]["included"] is True
    for lever in EXCLUDED_LEVERS:
        assert definitions[lever]["included"] is False
        assert definitions[lever]["reason"]

    assert payload["base_model"]["sha256"] == base_sha256
    assert payload["source_payloads"]["model_results"][
        "canonical_json_sha256"
    ] == _canonical_json_sha256(json.loads(MODEL_RESULTS.read_text()))
    assert payload["source_payloads"]["co_smd_reference"][
        "canonical_json_sha256"
    ] == _canonical_json_sha256(json.loads(COUNTERFACTUAL_SMD.read_text()))
    assert payload["uncertainty"]["draws"] == 10_000
    assert payload["uncertainty"]["seed"] == 202408
    encoded = serialize_json(payload)
    assert len(gzip.compress(encoded, mtime=0)) < 1_500_000
    assert encoded == MODEL_SCENARIOS.read_bytes()
    assert render_document(payload).encode() == SCENARIO_DOCUMENT.read_bytes()


def test_committed_co_reconciliation_normalizes_the_reference_direction():
    payload = json.loads(MODEL_SCENARIOS.read_text())
    comparison = payload["validation"]["co_smd"]
    export_delta = payload["states"]["CO"]["levers"]["smd"]["delta_pp"]

    assert comparison["reference_scenario"] == "ceiling"
    assert comparison["reference_delta_direction"] == "not_adopted_minus_adopted"
    assert comparison["export_delta_direction"] == "adopted_minus_not_adopted"
    assert comparison["reference_adoption_delta_pp"] == pytest.approx(
        -comparison["reference_delta_pp"]
    )
    assert comparison["export_delta_pp"] == pytest.approx(export_delta)
    assert comparison["difference_pp"] == pytest.approx(
        export_delta - comparison["reference_adoption_delta_pp"]
    )
    assert comparison["feature_flip_n"] == 53
    assert comparison["reconciled"] is True
    assert comparison["feature_flip_count_matches"] is True
    assert comparison["policy_direction_normalized"] is True
    assert comparison["point_sign_matches"] is True
    assert comparison["exact_case_mask_verified"] is False


def test_committed_intervals_recompute_from_the_encoded_case_deltas():
    model_data = json.loads(MODEL_DATA.read_text())
    payload = json.loads(MODEL_SCENARIOS.read_text())
    crossing = payload["crossing"]
    uncertainty = payload["uncertainty"]

    for state, state_record in payload["states"].items():
        model_state = model_data["states"][state]
        scenario = state_record["levers"]["smd"]
        patched_p, patched_q = _apply_parameter_patch(model_state, scenario)
        baseline_cross = _crossing_probability(
            model_state["p_dev"],
            model_state["q"],
            model_state["cap"],
            threshold=crossing["threshold_dollars"],
            tail_scale=crossing["tail_scale_log"],
            deviation_tolerance=crossing["deviation_tolerance_dollars"],
        )
        patched_cross = _crossing_probability(
            patched_p,
            patched_q,
            model_state["cap"],
            threshold=crossing["threshold_dollars"],
            tail_scale=crossing["tail_scale_log"],
            deviation_tolerance=crossing["deviation_tolerance_dollars"],
        )
        if scenario["baseline_adopted"]:
            adopted_cross, not_adopted_cross = baseline_cross, patched_cross
        else:
            adopted_cross, not_adopted_cross = patched_cross, baseline_cross
        bootstrap, _ = counterfactual_join.paired_weighted_bootstrap(
            {"delta_pp": 100 * (adopted_cross - not_adopted_cross)},
            pd.Series(model_state["w"], dtype=float),
            draws=uncertainty["draws"],
            seed=uncertainty["seed"],
        )
        expected = [
            round(value, 6) for value in bootstrap["delta_pp"]["confidence_interval"]
        ]
        assert [scenario["ci_lo"], scenario["ci_hi"]] == expected
