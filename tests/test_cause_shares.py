"""Guards for the deterministic FY2024 cause-share artifact."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis import cause_shares
from analysis import train_error_model as error_model


def _loader_fixture() -> pd.DataFrame:
    source = pd.DataFrame(
        {column: np.zeros(2) for column in error_model.REQUIRED_COLS}
    )
    source["CASE"] = [1, 2]
    source["STATE"] = [8, 8]
    source["AGENCY1"] = [17, 1]
    for slot in range(1, 19):
        source[f"SLFEMP{slot}"] = 0.0
    return source


def test_shared_loader_retains_requested_public_cause_fields(monkeypatch):
    source = _loader_fixture()
    monkeypatch.setattr(
        error_model.pyreadstat,
        "read_sav",
        lambda path: (source.copy(), object()),
    )

    loaded = error_model.load_year(2024, additional_columns=["agency1"])

    assert loaded["AGENCY1"].tolist() == [17]
    assert loaded["state"].tolist() == ["CO"]
    assert loaded["CASE"].tolist() == [1]


def test_shared_loader_rejects_missing_requested_public_cause_field(monkeypatch):
    source = _loader_fixture().drop(columns="AGENCY1")
    monkeypatch.setattr(
        error_model.pyreadstat,
        "read_sav",
        lambda path: (source.copy(), object()),
    )

    with pytest.raises(ValueError, match=r"FY2024 SAV.*AGENCY1"):
        error_model.load_year(2024, additional_columns=["AGENCY1"])


def _partition_fixture() -> pd.DataFrame:
    cases = pd.DataFrame(
        {
            "HWGT": [2.0, 1.0, 3.0, 4.0],
            "AMTERR": [100.0, 60.0, 80.0, 70.0],
        }
    )
    for slot in cause_shares.SLOTS:
        cases[f"AGENCY{slot}"] = np.nan
        cases[f"AMOUNT{slot}"] = 0.0
        cases[f"E_FINDG{slot}"] = np.nan
        cases[f"ELEMENT{slot}"] = np.nan
    cases.loc[0, ["AGENCY1", "AMOUNT1", "E_FINDG1", "ELEMENT1"]] = [
        10,
        100,
        2,
        311,
    ]
    cases.loc[1, ["AGENCY1", "AMOUNT1", "E_FINDG1", "ELEMENT1"]] = [
        1,
        60,
        3,
        363,
    ]
    cases.loc[2, ["AGENCY1", "AMOUNT1", "E_FINDG1", "ELEMENT1"]] = [
        10,
        30,
        2,
        311,
    ]
    cases.loc[2, ["AGENCY2", "AMOUNT2", "E_FINDG2", "ELEMENT2"]] = [
        1,
        50,
        3,
        363,
    ]
    # A positive amount without its paired impact code is not an element dollar.
    cases.loc[3, ["AMOUNT1", "ELEMENT1"]] = [70, 311]
    return cases


def test_partition_arithmetic_is_exhaustive_and_handles_overlap():
    cases = _partition_fixture()
    official_dollars = float((cases["HWGT"] * cases["AMTERR"]).sum())

    case_result = cause_shares._case_summary(cases, official_dollars)
    element_result = cause_shares._element_summary(
        cause_shares._long_elements(cases), official_dollars, cases
    )

    fractional = case_result["fractional_class_attribution"]["classes"]
    assert official_dollars == 780
    assert fractional["agency_or_system"]["dollars"] == 320
    assert fractional["client_or_fact"]["dollars"] == 180
    assert fractional["unclassified"]["dollars"] == 280
    assert sum(group["dollars"] for group in fractional.values()) == 780

    exclusive = case_result["exclusive_axis"]["classes"]
    assert exclusive["agency_or_system"]["dollars"] == 200
    assert exclusive["client_or_fact"]["dollars"] == 60
    assert exclusive["mixed_agency_client"]["dollars"] == 240
    assert exclusive["residual_or_unclassified"]["dollars"] == 280

    any_presence = case_result["any_presence"]["classes"]
    assert any_presence["agency_or_system"]["dollars"] == 440
    assert any_presence["client_or_fact"]["dollars"] == 300
    assert element_result["total"]["dollars"] == 500
    assert element_result["classes"]["agency_or_system"]["dollars"] == 290
    assert element_result["classes"]["client_or_fact"]["dollars"] == 210
    assert (
        element_result["reconciliation"][
            "n_cases_without_positive_paired_element"
        ]
        == 1
    )


def test_committed_colorado_values_are_locked():
    artifact_path = Path("analysis/cause_shares.json")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    colorado = next(row for row in artifact["rows"] if row["state"] == "CO")

    assert colorado["universe_n"] == 856
    assert colorado["n"] == 110
    assert colorado["official_error_dollars"] == 94_092_792.02
    fractional = colorado["case_attributed"]["fractional_class_attribution"][
        "classes"
    ]
    assert fractional["agency_or_system"]["dollars"] == 52_852_349.72
    assert fractional["agency_or_system"][
        "share_of_official_error_dollars"
    ] == pytest.approx(0.561704553383, abs=0)
    assert fractional["client_or_fact"]["dollars"] == 40_954_031.43
    assert colorado["element_attributed"]["total"]["dollars"] == 4_177_027.62


def test_committed_artifact_has_all_states_and_additive_national_partition():
    artifact = json.loads(Path("analysis/cause_shares.json").read_text(encoding="utf-8"))
    states = [row for row in artifact["rows"] if row["state"] != "US"]
    national = next(row for row in artifact["rows"] if row["state"] == "US")

    assert len(states) == 53
    assert {row["state"] for row in states} == set(error_model.FIPS.values())
    assert national["universe_n"] == 44_800
    assert national["n"] == 5_428
    assert national["official_error_dollars"] == 6_590_374_140.76
    classes = national["case_attributed"]["fractional_class_attribution"][
        "classes"
    ]
    assert sum(group["dollars"] for group in classes.values()) == pytest.approx(
        national["official_error_dollars"], abs=0.02
    )
