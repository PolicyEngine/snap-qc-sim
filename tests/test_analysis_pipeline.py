"""Synthetic guards for the QC analysis pipeline (no microdata required)."""

import json
from pathlib import Path
from types import SimpleNamespace

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


def test_state_rates_raise_on_nonpositive_predicted_total():
    frame = pd.DataFrame(
        {
            "state": ["AA", "AA"],
            "w": [1.0, 2.0],
            "issuance": [100.0, 200.0],
            "obs_error_dollars": [10.0, 20.0],
            "pred_err_dollars": [0.0, 0.0],
        }
    )

    with pytest.raises(ValueError, match="AA.*predicted error-dollar total"):
        hurdle_model._state_rates(frame)


def test_tail_fit_selects_q99_mean_excess_and_reports_all_cutoffs(monkeypatch):
    distributional = run_all.distributional_deviation_model
    n = 1_000
    target = np.linspace(3.0, 4.0, n)
    residual = np.linspace(0.0, 1.0, n)
    frame = pd.DataFrame(
        {
            "x": np.linspace(-1.0, 1.0, n),
            "D": np.exp(target),
            "w": np.ones(n),
        }
    )
    monkeypatch.setattr(
        distributional,
        "_weighted_cross_val_predict",
        lambda *args, **kwargs: target - residual,
    )

    tail = distributional._fit_tail(frame, ["x"])

    assert [row["cutoff_quantile"] for row in tail.mean_excess_by_cutoff] == [
        0.85,
        0.9,
        0.95,
        0.975,
        0.99,
        0.995,
    ]
    q90 = next(
        row for row in tail.mean_excess_by_cutoff if row["cutoff_quantile"] == 0.9
    )
    q99 = next(
        row for row in tail.mean_excess_by_cutoff if row["cutoff_quantile"] == 0.99
    )
    assert tail.cutoff_quantile == 0.99
    assert tail.scale == pytest.approx(q99["mean_excess_log"])
    assert tail.scale != pytest.approx(q90["mean_excess_log"])
    assert tail.scale_se > 0


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


def test_weighted_quantile_coverage_has_one_row_per_configured_quantile():
    levels = np.array([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975, 0.99])
    frame = pd.DataFrame(
        {
            "deviates": [1, 1, 1],
            "D": [2.0, -4.0, 8.0],
            "w": [1.0, 2.0, 3.0],
        }
    )
    for index, column in enumerate(
        run_all.distributional_deviation_model.QUANTILE_COLUMNS
    ):
        frame[column] = np.log([2.0, 4.0, 8.0]) + index / 100

    rows = run_all.distributional_deviation_model.weighted_quantile_coverage(frame)

    assert len(rows) == 9
    assert [row["quantile"] for row in rows] == pytest.approx(levels)
    assert all(
        set(row)
        == {
            "quantile",
            "n",
            "effective_n",
            "weighted_coverage",
            "gap_pp",
            "flag_over_3pp",
        }
        for row in rows
    )


def test_seed_aggregation_reports_between_seed_mc_error():
    distributional = run_all.distributional_deviation_model
    rows = [
        {
            "mean_pct": 9.0 + index,
            "sd_pp": 1.0 + index / 10,
            "tier_probabilities": {
                "0": 0.1,
                "5": 0.2,
                "10": 0.3,
                "15": 0.4,
            },
        }
        for index in range(8)
    ]

    result = distributional._aggregate_seed_statistics(rows)

    assert result["mean_pct"] == pytest.approx(12.5)
    assert result["mean_mc_se_pp"] > 0
    assert result["sd_mc_se_pp"] > 0
    assert sum(
        cell["probability"] for cell in result["tier_probabilities"].values()
    ) == pytest.approx(1.0)


@pytest.mark.parametrize(("cap", "expected_rate"), [(100.0, 200.0), (40.0, 0.0)])
def test_published_model_bootstrap_caps_before_threshold_then_applies_factor(
    monkeypatch, cap, expected_rate
):
    distributional = run_all.distributional_deviation_model
    monkeypatch.setattr(distributional, "SIMULATION_DRAWS", 16)
    monkeypatch.setattr(distributional, "SIMULATION_BATCH_SIZE", 8)

    class FixedRng:
        @staticmethod
        def integers(_low, _high, *, size):
            return np.zeros(size, dtype=int)

        @staticmethod
        def random(*, size):
            return np.full(size, 0.5)

    monkeypatch.setattr(
        distributional.np.random, "default_rng", lambda _seed: FixedRng()
    )
    group = pd.DataFrame(
        {
            "w": [1.0],
            "issuance": [100.0],
            "p_dev": [1.0],
            "deviation_cap": [cap],
            **{column: [np.log(1_000.0)] for column in distributional.QUANTILE_COLUMNS},
        }
    )

    rates = distributional._model_bootstrap_draws(
        group,
        tail_scale=0.25,
        state_factor=2.0,
        seed=123,
    )

    assert rates.tolist() == pytest.approx([expected_rate] * 16)


def test_run_all_stages_outputs_before_replacing_checked_in_artifacts(
    monkeypatch, tmp_path
):
    model_destination = tmp_path / "model_results.json"
    hurdle_destination = tmp_path / "hurdle_results.json"
    distributional_destination = tmp_path / "distributional_results.json"
    findings_destination = tmp_path / "FINDINGS.md"
    model_data_destination = tmp_path / "model_data.json"
    model_scenarios_destination = tmp_path / "model_scenarios.json"
    model_scenarios_document_destination = tmp_path / "MODEL_SCENARIOS.md"
    for destination in (
        model_destination,
        hurdle_destination,
        distributional_destination,
        findings_destination,
        model_data_destination,
        model_scenarios_destination,
        model_scenarios_document_destination,
    ):
        destination.write_text("old\n")

    monkeypatch.setattr(run_all, "ANALYSIS_DIR", tmp_path)
    monkeypatch.setattr(run_all, "MODEL_RESULTS", model_destination)
    monkeypatch.setattr(run_all, "HURDLE_RESULTS", hurdle_destination)
    monkeypatch.setattr(
        run_all,
        "DISTRIBUTIONAL_RESULTS",
        distributional_destination,
    )
    monkeypatch.setattr(run_all, "FINDINGS", findings_destination)
    monkeypatch.setattr(run_all, "MODEL_DATA", model_data_destination)
    monkeypatch.setattr(run_all, "MODEL_SCENARIOS", model_scenarios_destination)
    monkeypatch.setattr(
        run_all,
        "MODEL_SCENARIOS_DOCUMENT",
        model_scenarios_document_destination,
    )
    counterfactual_destination = tmp_path / "counterfactual_co_smd.json"
    counterfactual_destination.write_text(json.dumps({"counterfactual": "reference"}))
    monkeypatch.setattr(run_all, "COUNTERFACTUAL_SMD", counterfactual_destination)

    def fake_classifier_main():
        path = run_all.train_error_model.OUT / model_destination.name
        path.write_text(json.dumps({"classifier": "new"}))

    def fake_hurdle_main(path):
        Path(path).write_text(json.dumps({"hurdle": "new"}))

    def fake_distributional_main(path):
        result = {"distributional": "new", "export": {}}
        Path(path).write_text(json.dumps(result))
        return SimpleNamespace(
            result=result,
            predictions=pd.DataFrame(),
            bundle=SimpleNamespace(tail=SimpleNamespace(scale=0.25, scale_se=0.01)),
            state_factors=pd.DataFrame(),
            state_diagnostics=pd.DataFrame(),
            model_data_payload={"model_data": "new"},
        )

    def fake_build_model_data(
        predictions,
        *,
        tail_scale,
        tail_scale_se,
        state_factors,
        state_diagnostics,
        output_path,
        metadata_path,
        threshold,
        deviation_tolerance,
        quantile_levels,
        quantile_columns,
    ):
        assert predictions.empty
        assert tail_scale == 0.25
        assert tail_scale_se == 0.01
        assert state_factors.empty
        assert state_diagnostics.empty
        assert metadata_path == model_data_destination.with_name("data.json")
        assert threshold == 56
        assert deviation_tolerance == 0.5
        assert len(quantile_levels) == len(quantile_columns) == 9
        Path(output_path).write_text(json.dumps({"model_data": "new"}))
        return {
            "data": {"model_data": "new"},
            "raw_bytes": 21,
            "gzip_bytes": 37,
            "q_decimal_quantization": None,
        }

    def fake_build_model_scenarios(
        predictions,
        *,
        distributional_bundle,
        model_data_payload,
        base_model_path,
        model_results,
        counterfactual_payload,
        output_path,
        document_output_path,
    ):
        assert predictions.empty
        assert distributional_bundle.tail.scale == 0.25
        assert model_data_payload == {"model_data": "new"}
        assert Path(base_model_path).name == model_data_destination.name
        assert Path(base_model_path).read_text() == json.dumps({"model_data": "new"})
        assert model_results == {"classifier": "new"}
        assert counterfactual_payload == {"counterfactual": "reference"}
        Path(output_path).write_text(json.dumps({"model_scenarios": "new"}))
        Path(document_output_path).write_text("scenario report\n")
        return {
            "data": {
                "model_scenarios": "new",
                "included_levers": ["smd"],
            },
            "raw_bytes": 25,
            "gzip_bytes": 41,
        }

    monkeypatch.setattr(run_all.train_error_model, "main", fake_classifier_main)
    monkeypatch.setattr(run_all.hurdle_deviation_model, "main", fake_hurdle_main)
    monkeypatch.setattr(
        run_all.distributional_deviation_model,
        "main",
        fake_distributional_main,
    )
    monkeypatch.setattr(
        run_all.scripts_build_model_data,
        "build_model_data",
        fake_build_model_data,
    )
    monkeypatch.setattr(
        run_all.scripts_build_model_scenarios,
        "build_model_scenarios",
        fake_build_model_scenarios,
    )
    monkeypatch.setattr(
        run_all,
        "render_findings",
        lambda model, hurdle, distributional: "new\n",
    )

    run_all.main()

    assert json.loads(model_destination.read_text()) == {"classifier": "new"}
    assert json.loads(hurdle_destination.read_text()) == {"hurdle": "new"}
    assert json.loads(distributional_destination.read_text()) == {
        "distributional": "new",
        "export": {
            "model_data_gzip_bytes": 37,
            "model_data_raw_bytes": 21,
            "model_scenarios_gzip_bytes": 41,
            "model_scenarios_included_levers": ["smd"],
            "model_scenarios_raw_bytes": 25,
            "q_decimal_quantization": None,
        },
    }
    assert findings_destination.read_text() == "new\n"
    assert json.loads(model_data_destination.read_text()) == {"model_data": "new"}
    assert json.loads(model_scenarios_destination.read_text()) == {
        "model_scenarios": "new"
    }
    assert model_scenarios_document_destination.read_text() == "scenario report\n"

    destinations = (
        model_destination,
        hurdle_destination,
        distributional_destination,
        findings_destination,
        model_data_destination,
        model_scenarios_destination,
        model_scenarios_document_destination,
    )
    for destination in destinations:
        destination.write_text(f"old-{destination.name}\n")

    def fail_scenario_build(*args, **kwargs):
        raise RuntimeError("scenario build failed")

    monkeypatch.setattr(
        run_all.scripts_build_model_scenarios,
        "build_model_scenarios",
        fail_scenario_build,
    )
    with pytest.raises(RuntimeError, match="scenario build failed"):
        run_all.main()
    for destination in destinations:
        assert destination.read_text() == f"old-{destination.name}\n"


def test_committed_distributional_artifact_contains_review_gates():
    path = Path(__file__).resolve().parents[1] / "analysis/distributional_results.json"
    payload = json.loads(path.read_text())
    magnitude = payload["magnitude_distribution"]
    tail = magnitude["tail_fit"]
    dollar_validation = payload["dollar_rate_validation"]
    simulation = payload["measured_rate_simulation"]

    assert [row["cutoff_quantile"] for row in tail["mean_excess_by_cutoff"]] == [
        0.85,
        0.9,
        0.95,
        0.975,
        0.99,
        0.995,
    ]
    assert tail["fit_residual_cutoff_quantile"] == 0.99
    assert tail["scale_se_log"] > 0
    assert tail["implied_pareto_tail_index"] > 2
    assert tail["finite_variance_gate"]["passed"] is True
    assert (
        magnitude["physical_cap"]["unfactored_frozen_model"][
            "expected_error_dollars_removed_fraction"
        ]
        > 0
    )
    assert (
        magnitude["physical_cap"]["factor_adjusted_frozen_model"][
            "expected_error_dollars_removed_fraction"
        ]
        > 0
    )
    assert magnitude["coverage_signed_gap_pattern"]["all_nine_negative"] is True
    assert "effective_n_scaled_cvm" in magnitude["fy2024_weighted_pit"]
    assert len(dollar_validation["states"]) == 53
    assert dollar_validation["matched_model_pair"] is True
    assert simulation["state_count"] == 53
    assert simulation["seed_count"] >= 8
    assert simulation["draws_per_seed"] >= 4_000
    assert simulation["model_input"]["uses_encoded_arrays_and_state_factors"] is True
    cutoff_rows = {row["cutoff_quantile"]: row for row in tail["mean_excess_by_cutoff"]}
    assert cutoff_rows[0.85]["fy2024_prediction_source"].endswith("q75_q90")
    assert cutoff_rows[0.995]["fy2024_prediction_source"].endswith("above_q99")
