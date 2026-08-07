"""Synthetic tests for the quantile-regression-forest deviation model."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from quantile_forest import RandomForestQuantileRegressor
from sklearn.impute import SimpleImputer

from analysis import quantile_forest_deviation_model as qrf_model

FEATURES = ["x", "z"]


def _training_frame(n: int = 180) -> pd.DataFrame:
    x = np.linspace(-1.0, 1.0, n)
    z = np.sin(np.linspace(0.0, 4.0 * np.pi, n))
    log_magnitude = 1.2 + 0.35 * x + 0.08 * z
    sign = np.where(np.arange(n) % 2, -1.0, 1.0)
    return pd.DataFrame(
        {
            "x": x,
            "z": z,
            "D": sign * np.exp(log_magnitude),
            "deviates": np.ones(n, dtype=np.int8),
            "w": np.linspace(0.5, 3.0, n),
        }
    )


def _stub_tail() -> SimpleNamespace:
    return SimpleNamespace(
        scale=0.2,
        scale_se=0.01,
        residual_cutoff=0.0,
        cutoff_quantile=0.99,
        n=10,
        effective_n=9.0,
        oof_folds=3,
        mean_excess_by_cutoff=(),
    )


def _use_fast_forest(monkeypatch: pytest.MonkeyPatch, **updates: object) -> None:
    params = {
        **qrf_model.QRF_PARAMS,
        "n_estimators": 20,
        "n_jobs": 1,
        **updates,
    }
    monkeypatch.setattr(qrf_model, "QRF_PARAMS", params)


def _skip_tail_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qrf_model, "_fit_tail", lambda *_args, **_kwargs: _stub_tail())


def test_fit_and_predict_validate_required_columns(monkeypatch):
    _use_fast_forest(monkeypatch)
    _skip_tail_fit(monkeypatch)
    frame = _training_frame().drop(columns=["D", "w"])

    with pytest.raises(KeyError, match=r"D.*w"):
        qrf_model.fit_quantile_forest(frame, FEATURES)

    bundle = qrf_model.fit_quantile_forest(_training_frame(), FEATURES)
    with pytest.raises(KeyError, match="z"):
        qrf_model.predict_quantiles(bundle, pd.DataFrame({"x": [0.0]}), FEATURES)


def test_imputation_preserves_feature_shape_and_finite_predictions(monkeypatch):
    _use_fast_forest(monkeypatch)
    _skip_tail_fit(monkeypatch)
    frame = _training_frame()
    frame.loc[::4, "x"] = np.nan
    frame["z"] = np.nan

    bundle = qrf_model.fit_quantile_forest(frame, FEATURES)
    prediction_frame = pd.DataFrame(
        {"x": [np.nan, -0.25, 0.75], "z": [np.nan, np.nan, np.nan]}
    )
    imputed = bundle.imputer.transform(prediction_frame[FEATURES].to_numpy())
    quantiles = qrf_model.predict_quantiles(bundle, prediction_frame, FEATURES)

    assert imputed.shape == (len(prediction_frame), len(FEATURES))
    assert np.isfinite(imputed).all()
    assert quantiles.shape == (len(prediction_frame), len(qrf_model.QUANTILE_LEVELS))
    assert np.isfinite(quantiles).all()


def test_fit_passes_hwgt_as_sample_weight(monkeypatch):
    _use_fast_forest(monkeypatch, bootstrap=False)
    _skip_tail_fit(monkeypatch)
    frame = _training_frame()

    bundle = qrf_model.fit_quantile_forest(frame, FEATURES)
    root_weight = np.array(
        [
            estimator.tree_.weighted_n_node_samples[0]
            for estimator in bundle.model.estimators_
        ]
    )

    np.testing.assert_allclose(root_weight, frame["w"].sum())


def test_joint_predictions_are_naturally_monotone_and_not_resorted(monkeypatch):
    _use_fast_forest(monkeypatch)
    _skip_tail_fit(monkeypatch)
    frame = _training_frame()
    bundle = qrf_model.fit_quantile_forest(frame, FEATURES)
    evaluation = frame.iloc[::13].copy()

    result = qrf_model.predict_quantiles(
        bundle,
        evaluation,
        FEATURES,
        return_diagnostics=True,
    )
    raw = bundle.model.predict(
        bundle.imputer.transform(evaluation[FEATURES].to_numpy()),
        quantiles=np.asarray(qrf_model.QUANTILE_LEVELS, dtype=float).tolist(),
    )
    expected = np.maximum(raw, np.log(qrf_model.DEVIATION_TOLERANCE))

    assert result.quantiles.shape == (len(evaluation), 9)
    assert (np.diff(raw, axis=1) >= 0).all()
    np.testing.assert_array_equal(result.quantiles, expected)
    assert result.diagnostics.naturally_monotone is True
    assert result.diagnostics.raw_crossing_count == 0
    assert result.diagnostics.raw_crossing_row_count == 0
    assert result.diagnostics.post_helper_adjustment_count == 0


def test_shipped_floor_is_the_only_adjustment_to_monotone_qrf_output():
    raw = np.vstack(
        [
            np.linspace(np.log(0.1), np.log(5.0), 9),
            np.linspace(np.log(0.2), np.log(8.0), 9),
        ]
    )
    imputer = SimpleImputer(strategy="median", keep_empty_features=True).fit(
        np.array([[0.0], [1.0]])
    )

    class FixedQuantileForest:
        def predict(self, x, quantiles=None, weighted_quantile=True):
            assert x.shape == (2, 1)
            assert len(quantiles) == 9
            assert weighted_quantile is True
            return raw.copy()

    bundle = qrf_model.QuantileForestBundle(
        imputer=imputer,
        model=FixedQuantileForest(),
        tail=_stub_tail(),
        feature_names=("x",),
    )
    result = qrf_model.predict_quantiles(
        bundle,
        pd.DataFrame({"x": [0.25, 0.75]}),
        ["x"],
        return_diagnostics=True,
    )
    expected = np.maximum(raw, np.log(qrf_model.DEVIATION_TOLERANCE))

    np.testing.assert_array_equal(result.quantiles, expected)
    assert result.diagnostics.floor_adjustment_count == int((raw < np.log(0.5)).sum())
    assert result.diagnostics.post_helper_adjustment_count == 0
    assert result.diagnostics.naturally_monotone is True


def test_fixed_seed_gives_exactly_repeatable_quantiles(monkeypatch):
    _use_fast_forest(monkeypatch)
    _skip_tail_fit(monkeypatch)
    frame = _training_frame()
    first = qrf_model.fit_quantile_forest(frame, FEATURES)
    second = qrf_model.fit_quantile_forest(frame, FEATURES)

    first_prediction = qrf_model.predict_quantiles(first, frame, FEATURES)
    second_prediction = qrf_model.predict_quantiles(second, frame, FEATURES)

    np.testing.assert_array_equal(first_prediction, second_prediction)


def test_tail_oof_uses_qrf_and_bundle_attaches_finite_q99_tail(monkeypatch):
    _use_fast_forest(monkeypatch)
    frame = _training_frame(90)
    original_class = qrf_model.RandomForestQuantileRegressor
    fit_sizes: list[int] = []

    class RecordingQuantileForest(original_class):
        def fit(self, x, y, sample_weight=None, sparse_pickle=False):
            fit_sizes.append(len(x))
            return super().fit(
                x,
                y,
                sample_weight=sample_weight,
                sparse_pickle=sparse_pickle,
            )

    monkeypatch.setattr(
        qrf_model,
        "RandomForestQuantileRegressor",
        RecordingQuantileForest,
    )
    oof_median, folds = qrf_model._oof_median_predictions(frame, FEATURES)

    assert len(fit_sizes) == folds
    assert oof_median.shape == (len(frame),)
    assert np.isfinite(oof_median).all()

    tail_frame = _training_frame(1_000)
    target = np.log(tail_frame["D"].abs()).to_numpy(dtype=float)
    residual = np.linspace(0.0, 0.2, len(tail_frame))
    monkeypatch.setattr(
        qrf_model,
        "_oof_median_predictions",
        lambda *_args, **_kwargs: (target - residual, 4),
    )

    bundle = qrf_model.fit_quantile_forest(tail_frame, FEATURES)

    assert bundle.tail.cutoff_quantile == pytest.approx(0.99)
    assert bundle.tail.oof_folds == 4
    assert np.isfinite(bundle.tail.scale)
    assert 0 < bundle.tail.scale < qrf_model.MAX_TAIL_SCALE


def test_positive_fit_weights_do_not_reweight_native_one_leaf_quantiles():
    """Document quantile-forest 1.4.1's fit-only sample-weight semantics."""
    x = np.arange(5, dtype=float).reshape(-1, 1)
    y = np.array([0.0, 1.0, 4.0, 9.0, 16.0])
    common = {
        "n_estimators": 1,
        "bootstrap": False,
        "min_samples_split": 6,
        "max_samples_leaf": None,
        "random_state": 17,
        "n_jobs": 1,
    }
    uniform = RandomForestQuantileRegressor(**common)
    concentrated = RandomForestQuantileRegressor(**common)

    assert uniform.fit(x, y, sample_weight=np.ones(5)) is uniform
    assert (
        concentrated.fit(
            x,
            y,
            sample_weight=np.array([1.0, 1.0, 1_000.0, 1.0, 1.0]),
        )
        is concentrated
    )
    assert uniform.estimators_[0].tree_.node_count == 1
    assert concentrated.estimators_[0].tree_.node_count == 1

    quantiles = [0.1, 0.5, 0.9]
    uniform_prediction = uniform.predict([[2.0]], quantiles=quantiles)
    concentrated_prediction = concentrated.predict([[2.0]], quantiles=quantiles)

    np.testing.assert_array_equal(uniform_prediction, concentrated_prediction)
    assert concentrated.estimators_[0].tree_.weighted_n_node_samples[0] == 1_004
