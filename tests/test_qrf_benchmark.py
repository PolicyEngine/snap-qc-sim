"""Fast protocol tests for the QRF-versus-GBM benchmark runner."""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from analysis import qrf_benchmark as benchmark


def _estimator_metrics(
    *,
    coverage_mean_absolute_gap: float,
    factored_equal_state_mae: float,
) -> dict[str, object]:
    dollar_metrics = {
        specification: {
            weighting: {"mae_pp": 0.75}
            for weighting in ("equal_jurisdiction", "issuance_weighted")
        }
        for specification in (
            "raw_frozen_model",
            "factor_adjusted_frozen_model",
        )
    }
    dollar_metrics["factor_adjusted_frozen_model"]["equal_jurisdiction"]["mae_pp"] = (
        factored_equal_state_mae
    )
    return {
        "coverage": {
            "levels": [
                {"gap_pp": coverage_mean_absolute_gap}
                for _ in benchmark.QUANTILE_LEVELS
            ],
            "mean_absolute_gap_pp": coverage_mean_absolute_gap,
        },
        "pit": {"mean_gap": 0.01, "effective_n_scaled_cvm": 0.2},
        "dollar_rate_validation": {"metrics": dollar_metrics},
        "simulation": {
            "states": {
                state: {"absolute_sd_gap_to_observed_pp": 0.1}
                for state in benchmark.TARGET_STATES
            }
        },
        "export": {
            "schema_version": 2,
            "raw_bytes": 1_000,
            "gzip_bytes": 500,
            "cases": 8,
            "states": 4,
            "quantile_vector_shape": [8, len(benchmark.QUANTILE_LEVELS)],
            "per_case_quantile_vector_shape": [len(benchmark.QUANTILE_LEVELS)],
        },
        "tail": {"finite_variance_gate": {"passed": True}},
    }


def _benchmark_core(
    *,
    qrf_coverage: float = 0.9,
    qrf_calibration: float = 0.9,
) -> dict[str, object]:
    equivalence = {
        "passed": True,
        "tolerance": 1e-10,
        "max_absolute_delta": 0.0,
    }
    return {
        "schema_version": 1,
        "protocol": {"common_probability_stage_fit_once": True},
        "shipped_gbm_equivalence": equivalence,
        "validity_gates": {"shipped_gbm_equivalence": equivalence.copy()},
        "estimators": {
            "gbm": _estimator_metrics(
                coverage_mean_absolute_gap=1.0,
                factored_equal_state_mae=1.0,
            ),
            "qrf": _estimator_metrics(
                coverage_mean_absolute_gap=qrf_coverage,
                factored_equal_state_mae=qrf_calibration,
            ),
        },
    }


def _timing_record(repetition: int) -> dict[str, object]:
    offset = 10.0 * repetition
    order = ["gbm", "qrf"] if repetition % 2 == 0 else ["qrf", "gbm"]
    return {
        "fit_order": order,
        "gbm": {
            "fit_seconds": 1.0 + offset,
            "prediction_seconds": 2.0 + offset,
        },
        "qrf": {
            "fit_seconds": 3.0 + offset,
            "prediction_seconds": 4.0 + offset,
        },
    }


@pytest.mark.parametrize(
    ("coverage_delta", "calibration_delta", "coverage_ok", "calibration_ok"),
    [
        (-0.25, -0.25, True, True),
        (0.0, 0.0, True, True),
        (
            benchmark.TIE_TOLERANCE / 2,
            benchmark.TIE_TOLERANCE / 2,
            True,
            True,
        ),
        (4 * benchmark.TIE_TOLERANCE, -0.25, False, True),
        (-0.25, 4 * benchmark.TIE_TOLERANCE, True, False),
    ],
)
def test_verdict_switches_if_and_only_if_qrf_ties_or_wins_both_primary_gates(
    coverage_delta,
    calibration_delta,
    coverage_ok,
    calibration_ok,
):
    core = _benchmark_core(
        qrf_coverage=1.0 + coverage_delta,
        qrf_calibration=1.0 + calibration_delta,
    )
    runtime = benchmark._runtime_summary([_timing_record(0), _timing_record(1)])
    determinism = {"estimator_exact_match": {"gbm": True, "qrf": True}}

    verdict = benchmark._build_verdict(core, runtime, determinism)

    assert verdict["primary_gate_results"] == {
        "coverage_qrf_ties_or_wins": coverage_ok,
        "calibration_qrf_ties_or_wins": calibration_ok,
    }
    should_switch = coverage_ok and calibration_ok
    assert verdict["recommendation"] == (
        "switch_to_qrf" if should_switch else "retain_gbm"
    )
    assert {gate["id"] for gate in verdict["gates"] if gate["primary"]} == {
        "coverage_mean_absolute_gap",
        "dollar_factored_equal_state_mae",
    }


def test_canonical_hash_is_order_independent_and_strict():
    first = {"z": np.array([np.int64(2)]), "a": Path("fixture.json")}
    second = {"a": "fixture.json", "z": [2]}

    assert benchmark._canonical_json(first) == benchmark._canonical_json(second)
    assert benchmark._sha256(first) == benchmark._sha256(second)
    with pytest.raises(ValueError, match="nonfinite"):
        benchmark._canonical_json({"invalid": np.nan})


def test_run_benchmark_hashes_only_the_core_and_fits_probability_once(
    tmp_path,
    monkeypatch,
):
    metadata_path = tmp_path / "metadata.json"
    shipped_path = tmp_path / "shipped.json"
    metadata_path.write_text("{}", encoding="utf-8")
    shipped_path.write_text("{}", encoding="utf-8")
    data = pd.DataFrame(
        {
            "year": [2022, 2023, 2024],
            "feature": [0.0, 1.0, 2.0],
            "deviates": [1, 0, 1],
        }
    )
    fit_calls: list[int] = []
    prediction_row_counts: list[int] = []

    def predict(frame):
        prediction_row_counts.append(len(frame))
        return np.full(len(frame), 0.5)

    probability = SimpleNamespace(oof_metrics={"auc": 0.6}, predict=predict)

    def fit_probability(*_args, **_kwargs):
        fit_calls.append(1)
        return probability

    core = _benchmark_core()

    def run_once(*args):
        repetition = args[-1]
        return copy.deepcopy(core), _timing_record(repetition)

    monkeypatch.setattr(benchmark, "assemble", lambda: data.copy())
    monkeypatch.setattr(benchmark, "_feature_columns", lambda _data: ["feature"])
    monkeypatch.setattr(benchmark, "_fit_probability_stage", fit_probability)
    monkeypatch.setattr(benchmark, "_run_once", run_once)

    result = benchmark.run_benchmark(
        metadata_path=metadata_path,
        shipped_results_path=shipped_path,
        repetitions=2,
    )

    expected_hash = benchmark._sha256(core)
    assert fit_calls == [1]
    assert prediction_row_counts == [1, 1]
    assert result["determinism"]["core_sha256_by_repetition"] == [
        expected_hash,
        expected_hash,
    ]
    assert result["determinism"]["exact_match"] is True
    assert result["determinism"]["timing_excluded"] is True
    assert result["runtime"]["excluded_from_deterministic_core_sha256"] is True
    assert result["runtime"]["estimators"]["gbm"]["magnitude_fit_plus_prediction"][
        "seconds_by_repetition"
    ] == [3.0, 23.0]


def test_run_once_refuses_a_non_equivalent_shipped_gbm(monkeypatch):
    def estimator_run(estimator, *_args, **_kwargs):
        metrics = _estimator_metrics(
            coverage_mean_absolute_gap=1.0,
            factored_equal_state_mae=1.0,
        )
        return metrics, {}, {"fit_seconds": 0.0, "prediction_seconds": 0.0}

    monkeypatch.setattr(benchmark, "_estimator_run", estimator_run)
    monkeypatch.setattr(
        benchmark,
        "_simulation_comparison",
        lambda *_args: (
            {"observed_bootstrap": {}},
            {"gbm": {}, "qrf": {}},
        ),
    )
    monkeypatch.setattr(
        benchmark,
        "_shipped_gbm_equivalence",
        lambda *_args: {
            "passed": False,
            "tolerance": 1e-10,
            "max_absolute_delta": 0.01,
        },
    )

    with pytest.raises(RuntimeError, match="does not reproduce the shipped comparator"):
        benchmark._run_once(
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            [],
            np.array([]),
            np.array([]),
            {},
            Path("metadata.json"),
            Path("shipped.json"),
            {},
            0,
        )


def test_prediction_frame_preserves_schema_and_applies_per_case_caps():
    source = pd.DataFrame(
        {
            "case_id": [10, 11],
            "thr": [1.0, 2.0],
            "deviation_cap": [5.0, 20.0],
        }
    )
    probability = np.array([1.0, 0.5])
    raw_quantiles = np.vstack(
        [
            np.log([100, 90, 80, 70, 60, 50, 40, 30, 20]),
            np.log([200, 150, 100, 80, 60, 40, 20, 10, 5]),
        ]
    )
    original_quantiles = raw_quantiles.copy()
    tail = SimpleNamespace(scale=0.2)

    result = benchmark._prediction_frame(
        source,
        probability,
        raw_quantiles,
        tail,
    )

    expected_quantiles = benchmark.enforce_monotone_quantiles(raw_quantiles)
    expected_columns = [
        *source.columns,
        "p_dev",
        *benchmark.QUANTILE_COLUMNS,
        "pred_err_dollars_uncapped",
        "pred_err_dollars",
    ]
    assert result.columns.tolist() == expected_columns
    np.testing.assert_array_equal(
        result[list(benchmark.QUANTILE_COLUMNS)].to_numpy(),
        expected_quantiles,
    )
    np.testing.assert_array_equal(raw_quantiles, original_quantiles)
    np.testing.assert_allclose(
        result["pred_err_dollars"],
        benchmark.expected_error_dollars(
            probability,
            expected_quantiles,
            tail.scale,
            source["thr"],
            minimum_magnitude=benchmark.DEVIATION_TOLERANCE,
            magnitude_cap=source["deviation_cap"],
        ),
    )
    assert (result["pred_err_dollars"] < result["pred_err_dollars_uncapped"]).all()
    assert (
        result["pred_err_dollars"].to_numpy()
        <= probability * source["deviation_cap"].to_numpy()
    ).all()

    with pytest.raises(ValueError, match="wrong shape"):
        benchmark._prediction_frame(
            source,
            probability,
            raw_quantiles[:, :-1],
            tail,
        )


@pytest.mark.parametrize("blocked_output", ["json", "markdown"])
def test_write_reports_refuses_every_app_output_before_writing(
    blocked_output,
    tmp_path,
):
    app_root = Path(benchmark.__file__).resolve().parents[1] / "app"
    forbidden = app_root / f".qrf-benchmark-forbidden-{tmp_path.name}"
    json_path = (
        forbidden.with_suffix(".json")
        if blocked_output == "json"
        else (tmp_path / "result.json")
    )
    markdown_path = (
        forbidden.with_suffix(".md")
        if blocked_output == "markdown"
        else tmp_path / "result.md"
    )
    assert not json_path.exists()
    assert not markdown_path.exists()

    with pytest.raises(ValueError, match=r"must not be written under app/"):
        benchmark.write_reports(
            {},
            json_path=json_path,
            markdown_path=markdown_path,
        )

    assert not json_path.exists()
    assert not markdown_path.exists()
