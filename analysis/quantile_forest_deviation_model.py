"""Quantile-forest conditional SNAP deviation magnitudes.

This module is the quantile-regression-forest counterpart to the shipped
gradient-boosted conditional magnitude stack.  Both estimators target the
nine configured quantiles of ``log(abs(D))`` among benefit deviators and use
the same q99 log-scale exponential tail protocol.

``HWGT`` (the ``w`` column) is passed to ``fit`` as ``sample_weight``.  It
therefore affects the sklearn 1.8 tree splits and impurity calculations, but
not bootstrap draw probabilities.  The quantile-forest package's native
``weighted_quantile`` terminology refers to forest/leaf membership frequency,
not to the magnitudes of the supplied analysis weights.  With
``max_samples_leaf=1``, prediction is the empirical quantile across the one
training response represented by each tree's reached leaf.  Thus HWGT does
not directly reweight the final quantile aggregation.

The forest predicts all nine quantiles jointly, so they are monotone by
construction.  The shipped magnitude floor and monotonicity helper remain as
defensive export safeguards, with explicit diagnostics for any adjustment.
Because this QRF implementation rejects NaNs, its two nullable shipped features
use training-only median imputation; ``SimpleImputer`` does not accept HWGT, so
those medians are unweighted while the forest fit itself is HWGT-weighted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from quantile_forest import RandomForestQuantileRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import KFold

if __package__:
    from .distributional_deviation_model import (
        DEVIATION_TOLERANCE,
        TAIL_ATTACHMENT_QUANTILE,
        TAIL_SEED,
        TailFit,
        _mean_excess_by_cutoff,
    )
    from .hurdle_deviation_model import N_FOLDS, RANDOM_STATE
    from .predictive_process import (
        MAX_TAIL_SCALE,
        QUANTILE_LEVELS,
        TAIL_SCALE_MARGIN,
        enforce_monotone_quantiles,
    )
else:
    from distributional_deviation_model import (
        DEVIATION_TOLERANCE,
        TAIL_ATTACHMENT_QUANTILE,
        TAIL_SEED,
        TailFit,
        _mean_excess_by_cutoff,
    )
    from hurdle_deviation_model import N_FOLDS, RANDOM_STATE
    from predictive_process import (
        MAX_TAIL_SCALE,
        QUANTILE_LEVELS,
        TAIL_SCALE_MARGIN,
        enforce_monotone_quantiles,
    )


QRF_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "max_leaf_nodes": 63,
    "max_samples_leaf": 1,
    "bootstrap": True,
    "n_jobs": 1,
    "random_state": RANDOM_STATE,
}


@dataclass
class QuantileForestBundle:
    """Deployable conditional-magnitude forest, imputer, and tail fit."""

    imputer: SimpleImputer
    model: RandomForestQuantileRegressor
    tail: TailFit
    feature_names: tuple[str, ...]


@dataclass(frozen=True)
class QuantileDiagnostics:
    """Counts describing natural and safeguarded quantile monotonicity."""

    raw_crossing_count: int
    raw_crossing_row_count: int
    floor_adjustment_count: int
    post_helper_adjustment_count: int
    naturally_monotone: bool


@dataclass(frozen=True)
class QuantilePrediction:
    """Safeguarded log-quantile matrix and its adjustment diagnostics."""

    quantiles: np.ndarray
    diagnostics: QuantileDiagnostics


def _feature_names(features: list[str]) -> tuple[str, ...]:
    """Return a validated, order-preserving feature specification."""
    if isinstance(features, str) or not features:
        raise ValueError("features must be a nonempty list of column names")
    names = tuple(features)
    if any(not isinstance(name, str) or not name for name in names):
        raise TypeError("every feature must be a nonempty string")
    if len(set(names)) != len(names):
        raise ValueError("features must not contain duplicate columns")
    return names


def _require_columns(
    frame: pd.DataFrame,
    columns: set[str] | tuple[str, ...],
    context: str,
) -> None:
    """Raise when a model frame omits a requested column."""
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise KeyError(f"{context} is missing required columns: {missing}")


def _feature_matrix(
    frame: pd.DataFrame,
    feature_names: tuple[str, ...],
    context: str,
) -> np.ndarray:
    """Return numeric features, preserving NaNs solely for imputation."""
    _require_columns(frame, feature_names, context)
    selected = frame.loc[:, list(feature_names)]
    numeric = selected.apply(pd.to_numeric, errors="coerce")
    invalid = selected.notna() & numeric.isna()
    if invalid.any().any():
        bad = [name for name in feature_names if invalid[name].any()]
        raise ValueError(f"{context} contains nonnumeric feature values: {bad}")
    matrix = numeric.to_numpy(dtype=float, na_value=np.nan)
    if matrix.ndim != 2 or matrix.shape != (len(frame), len(feature_names)):
        raise ValueError(f"{context} produced an unexpected feature matrix shape")
    infinite = np.isinf(matrix)
    if infinite.any():
        bad = [feature_names[index] for index in np.flatnonzero(infinite.any(axis=0))]
        raise ValueError(f"{context} contains infinite feature values: {bad}")
    return matrix


def _numeric_column(frame: pd.DataFrame, column: str, context: str) -> np.ndarray:
    """Return one finite numeric model column."""
    numeric = pd.to_numeric(frame[column], errors="coerce")
    values = numeric.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all():
        raise ValueError(f"{context} requires finite numeric {column}")
    return values


def _deviator_inputs(
    deviators: pd.DataFrame,
    features: list[str],
) -> tuple[tuple[str, ...], np.ndarray, np.ndarray, np.ndarray]:
    """Validate and return deviator features, log magnitudes, and HWGT."""
    names = _feature_names(features)
    _require_columns(deviators, set(names) | {"D", "w"}, "QRF deviator frame")
    if deviators.empty:
        raise ValueError("QRF fitting requires at least one deviator")
    matrix = _feature_matrix(deviators, names, "QRF deviator frame")
    deviation = _numeric_column(deviators, "D", "QRF deviator frame")
    if np.any(np.abs(deviation) <= DEVIATION_TOLERANCE):
        raise ValueError("QRF deviators must satisfy abs(D) > the deviation tolerance")
    weights = _numeric_column(deviators, "w", "QRF deviator frame")
    if np.any(weights <= 0):
        raise ValueError("QRF sample weights must be strictly positive")
    target = np.log(np.abs(deviation))
    if not np.isfinite(target).all():
        raise ValueError("QRF log-magnitude target must be finite")
    return names, matrix, target, weights


def _imputer() -> SimpleImputer:
    """Return the training-only median imputer used by every forest fit."""
    return SimpleImputer(strategy="median", keep_empty_features=True)


def _quantile_forest() -> RandomForestQuantileRegressor:
    """Return the deterministic joint conditional-quantile estimator."""
    return RandomForestQuantileRegressor(
        default_quantiles=QUANTILE_LEVELS.tolist(),
        **QRF_PARAMS,
    )


def _validate_imputed(
    matrix: np.ndarray,
    expected_shape: tuple[int, int],
    context: str,
) -> np.ndarray:
    """Validate that imputation retained all columns and produced finite data."""
    result = np.asarray(matrix, dtype=float)
    if result.shape != expected_shape:
        raise ValueError(
            f"{context} imputed matrix has shape {result.shape}, "
            f"expected {expected_shape}"
        )
    if not np.isfinite(result).all():
        raise ValueError(f"{context} imputation produced nonfinite values")
    return result


def _predict_raw(
    model: RandomForestQuantileRegressor,
    matrix: np.ndarray,
) -> np.ndarray:
    """Predict all configured quantiles jointly and validate their shape."""
    prediction = np.asarray(
        model.predict(
            matrix,
            quantiles=QUANTILE_LEVELS.tolist(),
            weighted_quantile=True,
        ),
        dtype=float,
    )
    expected = (matrix.shape[0], len(QUANTILE_LEVELS))
    if prediction.shape != expected:
        raise ValueError(
            f"QRF prediction has shape {prediction.shape}, expected {expected}"
        )
    if not np.isfinite(prediction).all():
        raise ValueError("QRF prediction contains nonfinite values")
    return prediction


def _predict_median(
    model: RandomForestQuantileRegressor,
    matrix: np.ndarray,
) -> np.ndarray:
    """Predict the conditional median for the estimator-specific OOF tail."""
    prediction = np.asarray(
        model.predict(matrix, quantiles=[0.5], weighted_quantile=True),
        dtype=float,
    ).reshape(-1)
    if prediction.shape != (matrix.shape[0],):
        raise ValueError("QRF median prediction has an unexpected shape")
    if not np.isfinite(prediction).all():
        raise ValueError("QRF median prediction contains nonfinite values")
    return prediction


def _oof_median_predictions(
    deviators: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, int]:
    """Return deterministic OOF QRF medians with fold-local imputation."""
    _, matrix, target, weights = _deviator_inputs(deviators, features)
    folds = min(N_FOLDS, len(deviators))
    if folds < 2:
        raise ValueError("too few deviators for OOF tail fitting")
    cv = KFold(n_splits=folds, shuffle=True, random_state=TAIL_SEED)
    oof = np.full(len(deviators), np.nan, dtype=float)
    for fit_index, validation_index in cv.split(matrix):
        imputer = _imputer()
        fit_matrix = _validate_imputed(
            imputer.fit_transform(matrix[fit_index]),
            (len(fit_index), matrix.shape[1]),
            "QRF OOF training",
        )
        validation_matrix = _validate_imputed(
            imputer.transform(matrix[validation_index]),
            (len(validation_index), matrix.shape[1]),
            "QRF OOF validation",
        )
        model = _quantile_forest()
        model.fit(
            fit_matrix,
            target[fit_index],
            sample_weight=weights[fit_index],
        )
        oof[validation_index] = _predict_median(model, validation_matrix)
    if not np.isfinite(oof).all():
        raise ValueError("QRF OOF median predictions are incomplete or nonfinite")
    return oof, folds


def _fit_tail(deviators: pd.DataFrame, features: list[str]) -> TailFit:
    """Fit the shipped q99 log-exponential tail to QRF OOF residuals."""
    _, _, target, weights = _deviator_inputs(deviators, features)
    oof_median, folds = _oof_median_predictions(deviators, features)
    diagnostics = _mean_excess_by_cutoff(target - oof_median, weights)
    selected = next(
        row for row in diagnostics if row["cutoff_quantile"] == TAIL_ATTACHMENT_QUANTILE
    )
    scale = float(selected["mean_excess_log"])
    scale_se = float(selected["mean_excess_se_log"])
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("log-tail scale must be finite and positive")
    if scale >= MAX_TAIL_SCALE:
        raise ValueError(
            f"log-tail scale must be below {MAX_TAIL_SCALE:.2f}; finite dollar "
            "variance requires scale < 0.5 and the configured regression "
            f"margin is {TAIL_SCALE_MARGIN:.2f}"
        )
    upper_95 = scale + 1.96 * scale_se
    if not np.isfinite(upper_95) or upper_95 >= 0.5:
        raise ValueError(
            "log-tail scale uncertainty reaches the finite-variance boundary: "
            f"scale + 1.96 * SE = {upper_95:.6f} >= 0.5"
        )
    return TailFit(
        scale=scale,
        scale_se=scale_se,
        residual_cutoff=float(selected["residual_cutoff_log"]),
        cutoff_quantile=TAIL_ATTACHMENT_QUANTILE,
        n=int(selected["n"]),
        effective_n=float(selected["effective_n"]),
        oof_folds=folds,
        mean_excess_by_cutoff=tuple(diagnostics),
    )


def fit_quantile_forest(
    train: pd.DataFrame,
    features: list[str],
) -> QuantileForestBundle:
    """Fit conditional log-magnitude quantiles and their q99 tail.

    Only rows with ``deviates == 1`` contribute to either fit.  The imputer is
    learned once from those training rows for the deployable forest; the tail
    fit separately learns an imputer inside each OOF training fold.
    """
    names = _feature_names(features)
    _require_columns(train, set(names) | {"D", "deviates", "w"}, "QRF training frame")
    if train.empty:
        raise ValueError("QRF training frame must not be empty")
    deviates = _numeric_column(train, "deviates", "QRF training frame")
    if not np.isin(deviates, [0, 1]).all():
        raise ValueError("QRF deviates must be a binary indicator")
    deviators = train.loc[deviates == 1]
    _, matrix, target, weights = _deviator_inputs(deviators, list(names))

    imputer = _imputer()
    imputed = _validate_imputed(
        imputer.fit_transform(matrix),
        matrix.shape,
        "QRF full training",
    )
    model = _quantile_forest()
    model.fit(imputed, target, sample_weight=weights)
    tail = _fit_tail(deviators, list(names))
    return QuantileForestBundle(
        imputer=imputer,
        model=model,
        tail=tail,
        feature_names=names,
    )


def quantile_diagnostics(
    raw_quantiles: np.ndarray,
    minimum_magnitude: float = DEVIATION_TOLERANCE,
) -> QuantileDiagnostics:
    """Describe crossings and safety adjustments in raw QRF predictions."""
    raw = np.asarray(raw_quantiles, dtype=float)
    expected_columns = len(QUANTILE_LEVELS)
    if raw.ndim != 2 or raw.shape[1] != expected_columns:
        raise ValueError(
            "raw_quantiles must be a two-dimensional matrix with "
            f"{expected_columns} columns"
        )
    if not np.isfinite(raw).all():
        raise ValueError("raw_quantiles must contain only finite values")
    minimum = np.asarray(minimum_magnitude, dtype=float)
    if minimum.ndim != 0 or not np.isfinite(minimum) or minimum <= 0:
        raise ValueError("minimum_magnitude must be a finite positive scalar")

    crossing = np.diff(raw, axis=1) < 0
    floored = np.maximum(raw, np.log(float(minimum)))
    safeguarded = enforce_monotone_quantiles(
        raw,
        minimum_magnitude=float(minimum),
    )
    raw_crossing_count = int(crossing.sum())
    return QuantileDiagnostics(
        raw_crossing_count=raw_crossing_count,
        raw_crossing_row_count=int(crossing.any(axis=1).sum()),
        floor_adjustment_count=int((floored != raw).sum()),
        post_helper_adjustment_count=int((safeguarded != floored).sum()),
        naturally_monotone=raw_crossing_count == 0,
    )


def predict_quantiles(
    bundle: QuantileForestBundle,
    data: pd.DataFrame,
    features: list[str],
    *,
    return_diagnostics: bool = False,
) -> np.ndarray | QuantilePrediction:
    """Predict safeguarded conditional log-magnitude quantiles jointly."""
    names = _feature_names(features)
    if names != bundle.feature_names:
        raise ValueError(
            "prediction features must exactly match fitted feature names and order"
        )
    if data.empty:
        raise ValueError("QRF prediction frame must not be empty")
    matrix = _feature_matrix(data, names, "QRF prediction frame")
    imputed = _validate_imputed(
        bundle.imputer.transform(matrix),
        matrix.shape,
        "QRF prediction",
    )
    raw = _predict_raw(bundle.model, imputed)
    diagnostics = quantile_diagnostics(raw)
    quantiles = enforce_monotone_quantiles(
        np.maximum(raw, np.log(DEVIATION_TOLERANCE)),
        minimum_magnitude=DEVIATION_TOLERANCE,
    )
    if quantiles.shape != raw.shape or not np.isfinite(quantiles).all():
        raise ValueError("safeguarded QRF quantiles have invalid shape or values")
    if return_diagnostics:
        return QuantilePrediction(quantiles=quantiles, diagnostics=diagnostics)
    return quantiles
