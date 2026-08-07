"""Synthetic tests for the browser model-data export."""

import gzip
import json

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
        },
        {
            "case": 1,
            "state": "CO",
            "w": 1.23456,
            "issuance": 200.456,
            "p_dev": 0.2,
            "p_pos": 0.8,
        },
        {
            "case": 1,
            "state": "NY",
            "w": 3.45678,
            "issuance": 300.789,
            "p_dev": 0.3,
            "p_pos": 0.7,
        },
    ]
    for row_number, row in enumerate(rows):
        for column, value in zip(QUANTILE_COLUMNS, base_quantiles, strict=True):
            row[column] = value + row_number
    return pd.DataFrame(rows)


def _build(tmp_path, predictions=None):
    return build_model_data(
        _predictions() if predictions is None else predictions,
        tail_scale=0.75,
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
    assert payload["tail_scale_log"] == 0.75
    assert payload["q_units"] == "natural_log_dollars"
    assert payload["states"]["CO"]["official"] == 5.25
    assert payload["states"]["CO"]["verified"] == 856
    assert payload["states"]["CO"]["n"] == 1
    # Aggregate issuance and all arrays come from predictions, not data.json.
    assert payload["states"]["CO"]["issuance"] == round(1.23456 * 200.456)
    assert payload["states"]["NY"]["iss"] == [100.7, 300.8]
    assert payload["states"]["NY"]["w"] == [2.346, 3.457]
    assert payload["states"]["NY"]["p_dev"] == [0.1235, 0.3]

    for state in payload["states"].values():
        lengths = {len(state[key]) for key in ("w", "iss", "p_dev", "p_pos", "q")}
        assert lengths == {state["n"]}
        assert {len(row) for row in state["q"]} == {len(QUANTILE_LEVELS)}

    assert report["data"] == payload
    assert report["raw_bytes"] == len(encoded)
    assert report["gzip_bytes"] == len(gzip.compress(encoded, mtime=0))


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda frame: frame.drop(columns=["p_pos"]), "missing.*p_pos"),
        (lambda frame: frame.assign(w=0), "positive weights"),
        (lambda frame: frame.assign(p_dev=1.1), "p_dev"),
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


@pytest.mark.parametrize("tail_scale", [0.0, 1.0, float("nan")])
def test_build_model_data_requires_a_finite_mean_tail(tmp_path, tail_scale):
    with pytest.raises(ValueError, match="strictly between zero and one"):
        build_model_data(
            _predictions(),
            tail_scale=tail_scale,
            output_path=tmp_path / "model_data.json",
            metadata_path=_metadata(tmp_path),
        )


def test_build_model_data_rejects_state_set_mismatch(tmp_path):
    predictions = _predictions().query("state == 'CO'")

    with pytest.raises(ValueError, match=r"state set.*missing.*NY"):
        _build(tmp_path, predictions)


def test_build_model_data_rejects_unequal_quantile_schema(tmp_path):
    with pytest.raises(ValueError, match="same length"):
        build_model_data(
            _predictions(),
            tail_scale=0.75,
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
