"""Synthetic tests for the browser model-data export."""

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

import scripts_build_model_data as model_export
from scripts_build_model_data import (
    QUANTILE_COLUMNS,
    QUANTILE_LEVELS,
    _quantize_log_quantiles,
    build_model_data,
)


def _metadata(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(
        json.dumps(
            {
                "states": {
                    "CO": {
                        "official": 5.25,
                        "issuance": 999,
                        "n": 999,
                        "verified": 856,
                    },
                    "NY": {
                        "official": 7.5,
                        "issuance": 888,
                        "n": 888,
                        "verified": 847,
                    },
                }
            }
        )
    )
    return path


def _predictions():
    base_quantiles = [-1.23456, -0.25, 0.5, 1.25, 2.0, 2.75, 3.5, 4.25, 5.0]
    rows = [
        {
            "case": 1,
            "state": "NY",
            "w": 2.34567,
            "issuance": 100.678,
            "p_dev": 0.123456,
            "p_pos": 0.654321,
            "D": 125.0,
            "benmax": 500.0,
            "deviation_cap": 500.0,
        },
        {
            "case": 1,
            "state": "CO",
            "w": 1.23456,
            "issuance": 200.456,
            "p_dev": 0.2,
            "p_pos": 0.8,
            "D": -150.0,
            "benmax": 600.0,
            "deviation_cap": 600.0,
        },
        {
            "case": 1,
            "state": "NY",
            "w": 3.45678,
            "issuance": 300.789,
            "p_dev": 0.3,
            "p_pos": 0.7,
            "D": 700.0,
            "benmax": 650.0,
            "deviation_cap": 700.0,
        },
    ]
    for row_number, row in enumerate(rows):
        for column, value in zip(QUANTILE_COLUMNS, base_quantiles, strict=True):
            row[column] = value + row_number
    return pd.DataFrame(rows)


def _state_factors():
    return pd.DataFrame({"state": ["CO", "NY"], "state_factor": [1.1, 0.9]})


def _state_diagnostics():
    return pd.DataFrame(
        {
            "state": ["CO", "NY"],
            "raw_model_to_observed_ratio": [0.8, 1.5],
            "adjusted_model_to_observed_ratio": [0.88, 1.35],
            "adjusted_ratio_outside_0_7_to_1_4": [False, False],
        }
    )


def _build(
    tmp_path,
    predictions=None,
    state_factors=None,
    state_diagnostics=None,
):
    return build_model_data(
        _predictions() if predictions is None else predictions,
        tail_scale=0.25,
        tail_scale_se=0.01,
        state_factors=(_state_factors() if state_factors is None else state_factors),
        state_diagnostics=(
            _state_diagnostics() if state_diagnostics is None else state_diagnostics
        ),
        output_path=tmp_path / "model_data.json",
        metadata_path=_metadata(tmp_path),
    )


def test_build_model_data_is_self_contained_and_preserves_state_row_order(tmp_path):
    predictions = _predictions()

    report = _build(tmp_path, predictions)
    encoded = (tmp_path / "model_data.json").read_bytes()
    payload = json.loads(encoded)

    assert list(payload["states"]) == ["CO", "NY"]
    assert payload["quantile_levels"] == list(QUANTILE_LEVELS)
    assert payload["schema_version"] == 2
    assert payload["tail_scale_log"] == 0.25
    assert payload["tail_scale_se_log"] == 0.01
    assert payload["q_units"] == "natural_log_dollars"
    assert payload["states"]["CO"]["official"] == 5.25
    assert payload["states"]["CO"]["verified"] == 856
    assert payload["states"]["CO"]["n"] == 1
    # Aggregate issuance and all arrays come from predictions, not data.json.
    assert payload["states"]["CO"]["issuance"] == round(1.23456 * 200.456)
    assert payload["states"]["NY"]["iss"] == [100.7, 300.8]
    assert payload["states"]["NY"]["w"] == [2.346, 3.457]
    assert payload["states"]["NY"]["p_dev"] == [0.1235, 0.3]
    assert payload["states"]["CO"]["factor"] == 1.1
    assert payload["states"]["NY"]["level_ratio"] == 1.35
    assert payload["states"]["NY"]["cap"] == [500, 700]
    assert "p_pos" not in payload["states"]["NY"]
    assert payload["p_pos_exported"] is False

    for state in payload["states"].values():
        lengths = {len(state[key]) for key in ("w", "iss", "p_dev", "cap", "q")}
        assert lengths == {state["n"]}
        assert {len(row) for row in state["q"]} == {len(QUANTILE_LEVELS)}

    assert report["data"] == payload
    assert report["raw_bytes"] == len(encoded)
    assert report["gzip_bytes"] == len(gzip.compress(encoded, mtime=0))


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (
            lambda frame: frame.drop(columns=["deviation_cap"]),
            "missing.*deviation_cap",
        ),
        (lambda frame: frame.drop(columns=["benmax"]), "missing.*benmax"),
        (lambda frame: frame.assign(w=0), "positive weights"),
        (lambda frame: frame.assign(p_dev=1.1), "p_dev"),
        (lambda frame: frame.assign(deviation_cap=0), "positive dollar"),
        (
            lambda frame: frame.assign(
                **{
                    QUANTILE_COLUMNS[3]: frame[QUANTILE_COLUMNS[2]] - 1,
                }
            ),
            "monotone",
        ),
    ],
)
def test_build_model_data_rejects_invalid_schema_values(tmp_path, mutation, match):
    with pytest.raises(ValueError, match=match):
        _build(tmp_path, mutation(_predictions()))


def test_build_model_data_rejects_non_case_one_rows(tmp_path):
    predictions = _predictions()
    predictions.loc[0, "case"] = 2

    with pytest.raises(ValueError, match="case == 1"):
        _build(tmp_path, predictions)


@pytest.mark.parametrize("tail_scale", [0.0, 0.45, 0.5, float("nan")])
def test_build_model_data_requires_a_finite_variance_margin(tmp_path, tail_scale):
    with pytest.raises(ValueError, match="below 0.45"):
        build_model_data(
            _predictions(),
            tail_scale=tail_scale,
            tail_scale_se=0.01,
            state_factors=_state_factors(),
            state_diagnostics=_state_diagnostics(),
            output_path=tmp_path / "model_data.json",
            metadata_path=_metadata(tmp_path),
        )


def test_build_model_data_rejects_state_set_mismatch(tmp_path):
    predictions = _predictions().query("state == 'CO'")

    with pytest.raises(ValueError, match=r"state set.*missing.*NY"):
        _build(tmp_path, predictions)


@pytest.mark.parametrize(
    ("factors", "match"),
    [
        (_state_factors().query("state == 'CO'"), "state set.*missing.*NY"),
        (
            pd.concat([_state_factors(), _state_factors().iloc[[0]]]),
            "duplicate states",
        ),
        (_state_factors().assign(state_factor=0), "finite positive"),
    ],
)
def test_build_model_data_rejects_invalid_factor_schema(tmp_path, factors, match):
    with pytest.raises(ValueError, match=match):
        _build(tmp_path, state_factors=factors)


def test_build_model_data_rejects_incorrect_level_gate_flag(tmp_path):
    diagnostics = _state_diagnostics()
    diagnostics.loc[0, "adjusted_ratio_outside_0_7_to_1_4"] = True

    with pytest.raises(ValueError, match="level flags"):
        _build(tmp_path, state_diagnostics=diagnostics)


@pytest.mark.parametrize("bad_flag", [1, 0, "false", None, float("nan")])
def test_build_model_data_requires_boolean_level_gate_flags(tmp_path, bad_flag):
    diagnostics = _state_diagnostics().astype(
        {"adjusted_ratio_outside_0_7_to_1_4": object}
    )
    diagnostics.loc[0, "adjusted_ratio_outside_0_7_to_1_4"] = bad_flag

    with pytest.raises(TypeError, match="only boolean"):
        _build(tmp_path, state_diagnostics=diagnostics)


def test_build_model_data_rejects_cap_not_derived_from_benmax_and_deviation(tmp_path):
    predictions = _predictions()
    predictions.loc[0, "deviation_cap"] = 499.0

    with pytest.raises(ValueError, match=r"max\(benmax, abs\(D\)\)"):
        _build(tmp_path, predictions=predictions)


def test_build_model_data_rejects_unequal_quantile_schema(tmp_path):
    with pytest.raises(ValueError, match="same length"):
        build_model_data(
            _predictions(),
            tail_scale=0.25,
            tail_scale_se=0.01,
            state_factors=_state_factors(),
            state_diagnostics=_state_diagnostics(),
            output_path=tmp_path / "model_data.json",
            metadata_path=_metadata(tmp_path),
            quantile_levels=QUANTILE_LEVELS[:-1],
            quantile_columns=QUANTILE_COLUMNS,
        )


def test_log_quantile_helper_changes_only_q_values():
    states = {
        "CO": {
            "official": 5.25,
            "issuance": 247,
            "n": 1,
            "verified": 856,
            "w": [1.234],
            "iss": [200.5],
            "p_dev": [0.1235],
            "p_pos": [0.6543],
            "q": [[-1.235, 2.345, 12.35]],
        }
    }

    quantized = _quantize_log_quantiles(states, decimals=2)

    assert quantized["CO"]["q"] == [[-1.24, 2.35, 12.35]]
    assert quantized["CO"]["w"] == states["CO"]["w"]
    assert states["CO"]["q"] == [[-1.235, 2.345, 12.35]]


def test_large_export_quantizes_q_directly_to_two_log_dollar_decimals(
    tmp_path, monkeypatch
):
    predictions = _predictions()
    predictions.loc[0, QUANTILE_COLUMNS[0]] = -1.2349
    monkeypatch.setattr(model_export, "MAX_RAW_BYTES", 1)

    report = _build(tmp_path, predictions)
    payload = report["data"]

    assert payload["q_encoding"] == {"rounding": "decimal_places", "digits": 2}
    # Direct decimal rounding is -1.23; rounding first to four significant
    # figures would produce -1.235 and then the incorrect -1.24.
    assert payload["states"]["NY"]["q"][0][0] == -1.23
    assert report["q_decimal_quantization"] == 2


def test_committed_export_contains_caps_factors_and_no_sign_arrays():
    path = Path(__file__).resolve().parents[1] / "app/public/model_data.json"
    payload = json.loads(path.read_text())

    assert payload["schema_version"] == 2
    assert payload["p_pos_exported"] is False
    assert payload["finite_variance_gate"]["point_scale_upper_bound_exclusive"] == 0.45
    assert len(payload["states"]) == 53
    for state in payload["states"].values():
        assert state["factor"] > 0
        assert len(state["cap"]) == state["n"]
        assert min(state["cap"]) > 0
        assert "p_pos" not in state
