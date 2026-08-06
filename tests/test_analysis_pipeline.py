"""Synthetic guards for the QC analysis pipeline (no microdata required)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis import hurdle_deviation_model as hurdle_model
from analysis import run_all
from analysis import train_error_model as error_model
from analysis.hurdle_deviation_model import (
    add_hurdle_targets,
    weighted_calibration_metrics,
)


def test_threshold_map_matches_official_fiscal_year_amounts():
    assert error_model.THRESHOLD == {
        2017: 38,
        2018: 37,
        2019: 37,
        2022: 48,
        2023: 54,
        2024: 56,
    }


def test_weighted_mean_uses_only_nonmissing_values_and_positive_weights():
    values = pd.Series([0.0, 1.0, 0.25, np.nan, 1.0])
    weights = pd.Series([1.0, 3.0, 0.0, 99.0, -2.0])

    assert error_model.weighted_mean(values, weights) == pytest.approx(0.75)
    assert error_model.weighted_rate(values, weights) == pytest.approx(0.75)
    assert np.isnan(
        error_model.weighted_mean(pd.Series([1.0, np.nan]), pd.Series([0.0, 1.0]))
    )


def test_required_column_assertion_names_missing_columns():
    frame = pd.DataFrame({"present": [1]})

    with pytest.raises(ValueError, match=r"fixture.*missing.*absent"):
        error_model.assert_required_columns(
            frame, ["present", "absent"], context="fixture"
        )


def test_load_year_raises_when_sav_omits_a_requested_column(monkeypatch):
    source = pd.DataFrame(
        {column: [0.0] for column in error_model.REQUIRED_COLS if column != "FSBEN"}
    )
    source["SLFEMP1"] = 0.0

    monkeypatch.setattr(
        error_model.pyreadstat,
        "read_sav",
        lambda path: (source.copy(), object()),
    )

    with pytest.raises(ValueError, match=r"FY2024 SAV.*FSBEN"):
        error_model.load_year(2024)


def test_load_year_requires_every_fy2024_self_employment_slot(monkeypatch):
    source = pd.DataFrame({column: [0.0] for column in error_model.REQUIRED_COLS})
    for slot in range(1, 18):
        source[f"SLFEMP{slot}"] = 0.0

    monkeypatch.setattr(
        error_model.pyreadstat,
        "read_sav",
        lambda path: (source.copy(), object()),
    )

    with pytest.raises(ValueError, match=r"SLFEMP18"):
        error_model.load_year(2024)


def test_load_year_keeps_only_case_one(monkeypatch):
    row_count = 3
    source = pd.DataFrame(
        {column: np.zeros(row_count) for column in error_model.REQUIRED_COLS}
    )
    source["CASE"] = [1, 2, 3]
    source["STATE"] = [1, 2, 4]
    source["YRMONTH"] = [202401, 202402, 202403]
    for slot in range(1, 19):
        source[f"SLFEMP{slot}"] = 0.0
    source["SLFEMP1"] = [0.0, 10.0, 20.0]
    requested_paths: list[Path] = []

    def fake_read_sav(path):
        requested_paths.append(Path(path))
        return source.copy(), object()

    monkeypatch.setattr(error_model.pyreadstat, "read_sav", fake_read_sav)

    loaded = error_model.load_year(2024)

    assert requested_paths[0].name == "qc_pub_fy2024.sav"
    assert loaded["CASE"].tolist() == [1]
    assert loaded["YRMONTH"].tolist() == [202401]
    assert loaded["year"].tolist() == [2024]
    assert loaded["state"].tolist() == ["AL"]


def test_smd_registry_is_derived_from_state_year_amounts(tmp_path):
    years = [str(year) for year in range(2017, 2025)]
    registry = pd.DataFrame(
        {
            "state_name": list(error_model.STATE_NAME_TO_ABBR),
            **{year: 0 for year in years},
        }
    )
    registry.loc[registry["state_name"].eq("California"), "2018"] = 120
    path = tmp_path / "standard_medical_deductions.csv"
    registry.to_csv(path, index=False)

    treated = error_model.load_smd_registry(path)

    assert "CA" not in treated[2017]
    assert "CA" in treated[2018]
    assert "AK" not in treated[2018]


def test_medical_payment_impact_requires_a_same_slot_complete_pair():
    row_count = 5
    findings = pd.DataFrame(
        {
            name: np.zeros(row_count)
            for slot in error_model.FINDING_SLOTS
            for name in (
                f"ELEMENT{slot}",
                f"E_FINDG{slot}",
                f"AMOUNT{slot}",
            )
        }
    )
    findings.loc[0, ["ELEMENT4", "E_FINDG4", "AMOUNT4"]] = [365, 2, 10]
    findings.loc[1, ["ELEMENT4", "E_FINDG4", "AMOUNT4"]] = [365, 0, 10]
    findings.loc[2, ["ELEMENT4", "E_FINDG4", "AMOUNT4"]] = [365, 2, 0]
    findings.loc[3, ["ELEMENT4", "E_FINDG5", "AMOUNT5"]] = [365, 2, 10]
    findings.loc[4, ["ELEMENT9", "E_FINDG9", "AMOUNT9"]] = [365, 4, 25]

    assert error_model._medical_payment_impact(findings).tolist() == [
        True,
        False,
        False,
        False,
        True,
    ]


def test_features_use_person_self_employment_and_35_dollar_medical_gate():
    row_count = 4
    source = pd.DataFrame(
        {column: np.zeros(row_count) for column in error_model.REQUIRED_COLS}
    )
    for slot in range(1, 19):
        source[f"SLFEMP{slot}"] = 0.0
    source["CASE"] = 1
    source["year"] = 2024
    source["state"] = "AK"
    source["FSNELDER"] = 1
    source["FSMEDEXP"] = [35.0, 36.0, 100.0, np.nan]
    source["SLFEMP1"] = [0.0, 10.0, 0.0, 0.0]
    source["SLFEMP18"] = [0.0, 0.0, 20.0, 0.0]

    features = error_model.build_features(source, smd_states=set())

    assert features["se_records"].tolist() == [0, 1, 1, 0]
    assert features["med_doc_required"].tolist() == [0, 1, 1, 0]
    assert features["claims_medical_missing"].tolist() == [0, 0, 0, 1]
    assert "cat_elig" not in features
    assert "deductions_per_member" not in error_model.COVARIATES
    assert "deductions_per_member" in error_model.INTERMEDIATES


def test_build_features_rejects_non_case_one_rows():
    source = pd.DataFrame({column: np.zeros(1) for column in error_model.REQUIRED_COLS})
    source["CASE"] = 2
    source["year"] = 2024
    source["state"] = "AK"
    source["SLFEMP1"] = 0.0

    with pytest.raises(ValueError, match=r"CASE == 1"):
        error_model.build_features(source, smd_states=set())


def test_state_calibration_helper_supports_equal_and_issuance_weights():
    rates = pd.DataFrame(
        {
            "pred_rate": [1.0, 2.0, 3.0],
            "obs_rate": [3.0, 5.0, 7.0],
            "issuance_total": [1.0, 1.0, 8.0],
        }
    )

    equal = weighted_calibration_metrics(rates)
    issuance = weighted_calibration_metrics(rates, "issuance_total")

    assert equal == pytest.approx(
        {
            "states": 3,
            "slope": 2.0,
            "intercept_pp": 1.0,
            "mae_pp": 3.0,
            "rmse_pp": np.sqrt(29 / 3),
            "corr": 1.0,
        }
    )
    assert issuance == pytest.approx(
        {
            "states": 3,
            "slope": 2.0,
            "intercept_pp": 1.0,
            "mae_pp": 3.7,
            "rmse_pp": np.sqrt(14.1),
            "corr": 1.0,
        }
    )


@pytest.fixture
def official_label_cases():
    cases = pd.DataFrame(
        {
            "year": [2024, 2024, 2024, 2024, 2023],
            "STATUS": [2, 3, 1, 2, 3],
            "AMTERR": [57.0, 57.0, 500.0, 56.0, 55.0],
            # Benefit differences deliberately disagree with adjudication.
            "RAWBEN": [100.0, 900.0, 900.0, 900.0, 100.0],
            "BENFIX": [100.0, 100.0, 100.0, 100.0, 100.0],
            "FSBEN": [0.0, 900.0, 0.0, 0.0, 900.0],
        }
    )
    expected = pd.Series([1, 1, 0, 0, 1], dtype=int)
    return cases, expected


def test_official_label_uses_status_and_amterr_not_benefit_differences(
    official_label_cases,
):
    cases, expected = official_label_cases

    actual = error_model.official_error_label(cases)
    benefit_difference_guess = (
        (cases["RAWBEN"] - cases["BENFIX"]).abs()
        > cases["year"].map(error_model.THRESHOLD)
    ).astype(int)

    pd.testing.assert_series_equal(actual, expected)
    assert not benefit_difference_guess.equals(expected)


def test_hurdle_stage_two_positives_are_nested_in_stage_one():
    frame = pd.DataFrame(
        {
            # The first row exercises the rare adjudication/deviation mismatch.
            # It keeps its global official label but is outside the stage-2 model
            # population because it is not a stage-1 deviation.
            "D": [0.0, 0.5, 0.51, -25.0, 100.0],
            "official_error": [1, 0, 0, 1, 0],
        }
    )

    targets = add_hurdle_targets(frame)
    stage_one_positives = set(targets.index[targets["deviates"].eq(1)])
    stage_two_population = targets.loc[targets["deviates"].eq(1)]

    assert set(stage_two_population.index) <= stage_one_positives
    assert 0 not in stage_two_population.index
    assert targets["crosses"].tolist() == frame["official_error"].tolist()
    assert targets["deviates"].tolist() == [0, 0, 1, 1, 1]


def test_probability_calibration_uses_inner_oof_scores_per_outer_fold(
    monkeypatch,
):
    rng = np.random.default_rng(12)
    n = 60
    frame = pd.DataFrame(
        {
            "x": rng.normal(size=n),
            "target": np.tile([0, 1], n // 2),
            "w": rng.uniform(0.5, 2.0, size=n),
        }
    )
    monkeypatch.setattr(hurdle_model, "N_FOLDS", 3)
    monkeypatch.setattr(
        hurdle_model,
        "MODEL_PARAMS",
        {**hurdle_model.MODEL_PARAMS, "max_iter": 10, "max_leaf_nodes": 7},
    )
    inner_score_population_sizes: list[int] = []
    original = hurdle_model._weighted_cross_val_predict

    def record_inner_population(estimator, x, y, weights, cv, method):
        inner_score_population_sizes.append(len(x))
        return original(estimator, x, y, weights, cv, method)

    monkeypatch.setattr(
        hurdle_model,
        "_weighted_cross_val_predict",
        record_inner_population,
    )

    stage = hurdle_model._fit_probability_stage(
        frame,
        ["x"],
        "target",
        seed=31,
    )

    # Three inner OOF runs, each restricted to a 40-row outer training set.
    # A full-data OOF call here would reintroduce the calibration leakage.
    assert inner_score_population_sizes == [40, 40, 40]
    assert stage.oof_metrics["oof_method"] == "nested_outer_inner"
    assert stage.oof_metrics["outer_folds"] == 3
    assert stage.oof_metrics["inner_folds_by_outer_fold"] == [3, 3, 3]
    assert np.isfinite(stage.oof_metrics["weighted_brier_calibrated"])
    assert np.isfinite(stage.oof_metrics["calibration_in_the_large_calibrated"])


def test_magnitude_diagnostics_fit_smear_inside_each_outer_training_fold(
    monkeypatch,
):
    rng = np.random.default_rng(27)
    n = 45
    x = pd.DataFrame({"x": rng.normal(size=n)})
    log_magnitude = pd.Series(4 + 0.2 * x["x"] + rng.normal(0, 0.2, size=n))
    weights = pd.Series(rng.uniform(0.5, 2.0, size=n))
    monkeypatch.setattr(hurdle_model, "N_FOLDS", 3)
    monkeypatch.setattr(
        hurdle_model,
        "MODEL_PARAMS",
        {**hurdle_model.MODEL_PARAMS, "max_iter": 10, "max_leaf_nodes": 7},
    )
    inner_residual_population_sizes: list[int] = []
    original = hurdle_model._weighted_cross_val_predict

    def record_inner_population(estimator, x, y, weights, cv, method):
        inner_residual_population_sizes.append(len(x))
        return original(estimator, x, y, weights, cv, method)

    monkeypatch.setattr(
        hurdle_model,
        "_weighted_cross_val_predict",
        record_inner_population,
    )

    oof_log, nested_magnitude, fold_smears, inner_folds = (
        hurdle_model._nested_magnitude_oof_predictions(
            x,
            log_magnitude,
            weights,
            n_splits=3,
            seed=41,
        )
    )

    assert inner_residual_population_sizes == [30, 30, 30]
    assert inner_folds == [3, 3, 3]
    assert len(fold_smears) == 3
    assert np.isfinite(fold_smears).all()
    assert (np.asarray(fold_smears) > 0).all()
    assert np.isfinite(oof_log).all()
    assert np.isfinite(nested_magnitude).all()


def test_run_all_stages_outputs_before_replacing_checked_in_artifacts(
    monkeypatch, tmp_path
):
    model_destination = tmp_path / "model_results.json"
    hurdle_destination = tmp_path / "hurdle_results.json"
    findings_destination = tmp_path / "FINDINGS.md"
    for destination in (model_destination, hurdle_destination, findings_destination):
        destination.write_text("old\n")

    monkeypatch.setattr(run_all, "ANALYSIS_DIR", tmp_path)
    monkeypatch.setattr(run_all, "MODEL_RESULTS", model_destination)
    monkeypatch.setattr(run_all, "HURDLE_RESULTS", hurdle_destination)
    monkeypatch.setattr(run_all, "FINDINGS", findings_destination)

    def fake_classifier_main():
        path = run_all.train_error_model.OUT / model_destination.name
        path.write_text(json.dumps({"classifier": "new"}))

    def fake_hurdle_main(path):
        Path(path).write_text(json.dumps({"hurdle": "new"}))

    monkeypatch.setattr(run_all.train_error_model, "main", fake_classifier_main)
    monkeypatch.setattr(run_all.hurdle_deviation_model, "main", fake_hurdle_main)
    monkeypatch.setattr(run_all, "render_findings", lambda model, hurdle: "new\n")

    run_all.main()

    assert json.loads(model_destination.read_text()) == {"classifier": "new"}
    assert json.loads(hurdle_destination.read_text()) == {"hurdle": "new"}
    assert findings_destination.read_text() == "new\n"
