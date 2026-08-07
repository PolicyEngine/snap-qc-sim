"""Pure NumPy draws and moments for the signed SNAP deviation process.

The conditional magnitude model predicts quantiles of ``log(|D|)``.  Between
reported quantiles, its quantile function is linear in log dollars.  The
unreported lower interval is joined to ``log(minimum_magnitude)`` at
probability zero.  Above the final quantile, log magnitude has an exponential
excess with scale ``tail_scale``::

    log(|D|) = log_q99 - tail_scale * log((1 - u) / (1 - q99)).

This continuation is a Pareto tail in dollars.  Reported uncertainty requires
finite variance, so every public calculation enforces ``tail_scale < 0.45``:
the mathematical 0.5 boundary minus a 0.05 regression margin.
"""

from __future__ import annotations

from typing import Any

import numpy as np

QUANTILE_LEVELS = np.array(
    [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975, 0.99],
    dtype=float,
)
FINITE_VARIANCE_TAIL_SCALE = 0.5
TAIL_SCALE_MARGIN = 0.05
MAX_TAIL_SCALE = FINITE_VARIANCE_TAIL_SCALE - TAIL_SCALE_MARGIN


def _minimum_log(minimum_magnitude: float) -> float:
    """Validate the scalar magnitude floor and return its logarithm."""
    value = np.asarray(minimum_magnitude, dtype=float)
    if value.ndim != 0 or not np.isfinite(value) or value <= 0:
        raise ValueError("minimum_magnitude must be a finite positive scalar")
    return float(np.log(value))


def _levels(quantile_levels: Any) -> np.ndarray:
    """Return validated, strictly increasing interior probability levels."""
    levels = np.asarray(quantile_levels, dtype=float)
    if levels.ndim != 1 or levels.size == 0:
        raise ValueError("quantile_levels must be a nonempty one-dimensional array")
    if not np.isfinite(levels).all():
        raise ValueError("quantile_levels must be finite")
    if np.any((levels <= 0) | (levels >= 1)):
        raise ValueError("quantile_levels must lie strictly between zero and one")
    if np.any(np.diff(levels) <= 0):
        raise ValueError("quantile_levels must be strictly increasing")
    return levels


def _finite_array(value: Any, name: str) -> np.ndarray:
    """Convert an input to a finite floating-point array."""
    array = np.asarray(value, dtype=float)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _probability(value: Any, name: str) -> np.ndarray:
    """Return a validated probability array."""
    probability = _finite_array(value, name)
    if np.any((probability < 0) | (probability > 1)):
        raise ValueError(f"{name} must lie between zero and one")
    return probability


def _positive_tail_scale(value: Any) -> np.ndarray:
    """Return a positive scale safely inside the finite-variance region."""
    scale = _finite_array(value, "tail_scale")
    if np.any(scale <= 0):
        raise ValueError("tail_scale must be strictly positive")
    if np.any(scale >= MAX_TAIL_SCALE):
        raise ValueError(
            f"tail_scale must be below {MAX_TAIL_SCALE:.2f}: the dollar-tail "
            "variance requires a scale below 0.5 and the model reserves a "
            f"{TAIL_SCALE_MARGIN:.2f} regression margin"
        )
    return scale


def _magnitude_cap(value: Any, minimum_magnitude: float) -> np.ndarray:
    """Return a finite per-case cap no lower than the modeled support floor."""
    cap = _finite_array(value, "magnitude_cap")
    if np.any(cap < minimum_magnitude):
        raise ValueError("magnitude_cap must be at least the modeled minimum magnitude")
    return cap


def _threshold(value: Any) -> np.ndarray:
    """Return a validated non-negative dollar threshold."""
    threshold = _finite_array(value, "threshold")
    if np.any(threshold < 0):
        raise ValueError("threshold must be non-negative")
    return threshold


def _prepare_quantiles(
    log_quantiles: Any,
    quantile_levels: Any,
    minimum_magnitude: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Validate levels and align them with monotone log quantiles."""
    levels = _levels(quantile_levels)
    minimum_log = _minimum_log(minimum_magnitude)
    quantiles = enforce_monotone_quantiles(log_quantiles, minimum_magnitude)
    if quantiles.shape[-1] != levels.size:
        raise ValueError(
            "log_quantiles' last axis must match the number of quantile_levels"
        )
    return quantiles, levels, minimum_log


def _broadcast_inputs(
    log_quantiles: np.ndarray,
    **arrays: np.ndarray,
) -> tuple[tuple[int, ...], np.ndarray, dict[str, np.ndarray]]:
    """Broadcast per-case arrays against the quantiles' leading dimensions."""
    try:
        shape = np.broadcast_shapes(
            log_quantiles.shape[:-1], *(value.shape for value in arrays.values())
        )
    except ValueError as exc:
        raise ValueError(
            "per-case inputs must broadcast with log_quantiles' leading shape"
        ) from exc

    quantiles = np.broadcast_to(log_quantiles, shape + (log_quantiles.shape[-1],))
    broadcast = {name: np.broadcast_to(value, shape) for name, value in arrays.items()}
    return shape, quantiles, broadcast


def enforce_monotone_quantiles(
    log_quantiles: Any,
    minimum_magnitude: float = 0.5,
) -> np.ndarray:
    """Sort each predicted log-quantile vector and impose its magnitude floor."""
    minimum_log = _minimum_log(minimum_magnitude)
    quantiles = _finite_array(log_quantiles, "log_quantiles")
    if quantiles.ndim == 0 or quantiles.shape[-1] == 0:
        raise ValueError("log_quantiles must have a nonempty final axis")
    return np.sort(np.maximum(quantiles, minimum_log), axis=-1)


def conditional_survival(
    threshold: Any,
    log_quantiles: Any,
    tail_scale: Any,
    quantile_levels: Any = QUANTILE_LEVELS,
    minimum_magnitude: float = 0.5,
) -> np.ndarray:
    """Return ``P(|D| > threshold | D != 0)`` under the quantile model.

    Inverting the monotone quantile function handles flat predicted segments
    as point masses.  Consequently, the comparison remains strictly greater
    than the threshold even when several adjacent quantiles are equal.
    """
    quantiles, levels, minimum_log = _prepare_quantiles(
        log_quantiles, quantile_levels, minimum_magnitude
    )
    scale = _positive_tail_scale(tail_scale)
    threshold_array = _threshold(threshold)
    shape, quantiles, values = _broadcast_inputs(
        quantiles, tail_scale=scale, threshold=threshold_array
    )

    flat_quantiles = quantiles.reshape(-1, quantiles.shape[-1])
    flat_scale = values["tail_scale"].reshape(-1)
    flat_threshold = values["threshold"].reshape(-1)
    log_threshold = np.full(flat_threshold.shape, -np.inf)
    positive = flat_threshold > 0
    log_threshold[positive] = np.log(flat_threshold[positive])

    survival = np.empty(flat_threshold.shape, dtype=float)
    below_support = log_threshold < minimum_log
    survival[below_support] = 1.0

    last_log = flat_quantiles[:, -1]
    in_tail = (~below_support) & (log_threshold >= last_log)
    survival[in_tail] = (1.0 - levels[-1]) * np.exp(
        -(log_threshold[in_tail] - last_log[in_tail]) / flat_scale[in_tail]
    )

    interior = ~(below_support | in_tail)
    if np.any(interior):
        rows = np.flatnonzero(interior)
        nodes = np.concatenate(
            (
                np.full((rows.size, 1), minimum_log),
                flat_quantiles[rows],
            ),
            axis=1,
        )
        x = log_threshold[rows]
        # The rightmost node at or below x skips any flat segment at exactly
        # the threshold, preserving the strict crossing convention.
        left_index = np.sum(nodes <= x[:, None], axis=1) - 1
        node_levels = np.concatenate(([0.0], levels))
        left_level = node_levels[left_index]
        right_level = node_levels[left_index + 1]
        left_log = nodes[np.arange(rows.size), left_index]
        right_log = nodes[np.arange(rows.size), left_index + 1]
        fraction = (x - left_log) / (right_log - left_log)
        crossing_probability = left_level + fraction * (right_level - left_level)
        survival[rows] = 1.0 - crossing_probability

    return survival.reshape(shape)


def _uniform(rng: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    """Draw and validate one independent uniform variate per output cell."""
    if rng is None or not callable(getattr(rng, "random", None)):
        raise TypeError("rng must provide a callable random method")
    draw = np.asarray(rng.random(size=shape), dtype=float)
    if draw.shape != shape:
        raise ValueError(
            f"rng returned shape {draw.shape} for {name}, expected {shape}"
        )
    if not np.isfinite(draw).all() or np.any((draw < 0) | (draw >= 1)):
        raise ValueError("rng.random must return finite values in [0, 1)")
    return draw


def _draw_log_magnitude(
    uniform: np.ndarray,
    log_quantiles: np.ndarray,
    tail_scale: np.ndarray,
    levels: np.ndarray,
    minimum_log: float,
) -> np.ndarray:
    """Evaluate the piecewise conditional log-magnitude quantile function."""
    shape = uniform.shape
    flat_uniform = uniform.reshape(-1)
    flat_quantiles = log_quantiles.reshape(-1, log_quantiles.shape[-1])
    flat_scale = tail_scale.reshape(-1)
    interval = np.searchsorted(levels, flat_uniform, side="right")
    result = np.empty(flat_uniform.shape, dtype=float)

    body = interval < levels.size
    if np.any(body):
        rows = np.flatnonzero(body)
        right_index = interval[rows]
        left_index = np.maximum(right_index - 1, 0)
        left_level = np.where(right_index == 0, 0.0, levels[left_index])
        right_level = levels[right_index]
        left_log = flat_quantiles[rows, left_index]
        left_log = np.where(right_index == 0, minimum_log, left_log)
        right_log = flat_quantiles[rows, right_index]
        fraction = (flat_uniform[rows] - left_level) / (right_level - left_level)
        result[rows] = left_log + fraction * (right_log - left_log)

    tail = ~body
    if np.any(tail):
        rows = np.flatnonzero(tail)
        relative_survival = (1.0 - flat_uniform[rows]) / (1.0 - levels[-1])
        result[rows] = flat_quantiles[rows, -1] - flat_scale[rows] * np.log(
            relative_survival
        )

    return result.reshape(shape)


def draw_deviations(
    p_dev: Any,
    p_pos: Any,
    log_quantiles: Any,
    tail_scale: Any,
    rng: Any,
    *,
    magnitude_cap: Any,
    quantile_levels: Any = QUANTILE_LEVELS,
    minimum_magnitude: float = 0.5,
) -> np.ndarray:
    """Draw one signed, physically capped deviation per parameter cell."""
    quantiles, levels, minimum_log = _prepare_quantiles(
        log_quantiles, quantile_levels, minimum_magnitude
    )
    deviation_probability = _probability(p_dev, "p_dev")
    positive_probability = _probability(p_pos, "p_pos")
    scale = _positive_tail_scale(tail_scale)
    inputs = {
        "p_dev": deviation_probability,
        "p_pos": positive_probability,
        "tail_scale": scale,
        "magnitude_cap": _magnitude_cap(magnitude_cap, minimum_magnitude),
    }
    shape, quantiles, values = _broadcast_inputs(quantiles, **inputs)

    deviates = _uniform(rng, shape, "deviation draw") < values["p_dev"]
    positive = _uniform(rng, shape, "sign draw") < values["p_pos"]
    magnitude_uniform = _uniform(rng, shape, "magnitude draw")
    log_magnitude = _draw_log_magnitude(
        magnitude_uniform,
        quantiles,
        values["tail_scale"],
        levels,
        minimum_log,
    )
    log_magnitude = np.minimum(log_magnitude, np.log(values["magnitude_cap"]))
    with np.errstate(over="ignore"):
        magnitude = np.exp(log_magnitude)
    if not np.isfinite(magnitude).all():
        raise FloatingPointError("drawn magnitude is not finite")
    signed = np.where(positive, magnitude, -magnitude)
    return np.where(deviates, signed, 0.0)


def error_dollars(deviation: Any, threshold: Any) -> np.ndarray:
    """Return absolute deviation dollars only for strict threshold crossings."""
    deviation_array = _finite_array(deviation, "deviation")
    threshold_array = _threshold(threshold)
    try:
        magnitude, threshold_array = np.broadcast_arrays(
            np.abs(deviation_array), threshold_array
        )
    except ValueError as exc:
        raise ValueError(
            "deviation and threshold must be broadcast-compatible"
        ) from exc
    return np.where(magnitude > threshold_array, magnitude, 0.0)


def _linear_segment_integral(
    left_log: np.ndarray,
    right_log: np.ndarray,
    log_threshold: np.ndarray,
    width: float,
) -> np.ndarray:
    """Integrate exp(piecewise-linear log magnitude) above a threshold."""
    result = np.zeros(left_log.shape, dtype=float)
    included = right_log > log_threshold
    if not np.any(included):
        return result

    left = left_log[included]
    right = right_log[included]
    threshold = log_threshold[included]
    slope = right - left
    start = np.zeros(left.shape, dtype=float)
    partial = (left <= threshold) & (slope > 0)
    start[partial] = (threshold[partial] - left[partial]) / slope[partial]

    span = slope * (1.0 - start)
    integral = np.empty(left.shape, dtype=float)
    flat = slope == 0
    integral[flat] = np.exp(left[flat]) * (1.0 - start[flat])
    curved = ~flat
    integral[curved] = (
        np.exp(left[curved] + slope[curved] * start[curved])
        * np.expm1(span[curved])
        / slope[curved]
    )
    result[included] = width * integral
    return result


def _expected_error_dollars_uncapped(
    quantiles: np.ndarray,
    levels: np.ndarray,
    minimum_log: float,
    deviation_probability: np.ndarray,
    scale: np.ndarray,
    threshold_array: np.ndarray,
) -> np.ndarray:
    """Integrate the unbounded piecewise quantile function above a threshold."""
    shape, quantiles, values = _broadcast_inputs(
        quantiles,
        p_dev=deviation_probability,
        tail_scale=scale,
        threshold=threshold_array,
    )

    flat_quantiles = quantiles.reshape(-1, quantiles.shape[-1])
    flat_probability = values["p_dev"].reshape(-1)
    flat_scale = values["tail_scale"].reshape(-1)
    flat_threshold = values["threshold"].reshape(-1)
    log_threshold = np.full(flat_threshold.shape, -np.inf)
    positive = flat_threshold > 0
    log_threshold[positive] = np.log(flat_threshold[positive])

    nodes = np.concatenate(
        (
            np.full((flat_quantiles.shape[0], 1), minimum_log),
            flat_quantiles,
        ),
        axis=1,
    )
    node_levels = np.concatenate(([0.0], levels))
    conditional_moment = np.zeros(flat_probability.shape, dtype=float)
    for index in range(levels.size):
        conditional_moment += _linear_segment_integral(
            nodes[:, index],
            nodes[:, index + 1],
            log_threshold,
            float(node_levels[index + 1] - node_levels[index]),
        )

    last_log = flat_quantiles[:, -1]
    tail_log_integral = np.log1p(-levels[-1]) + last_log - np.log1p(-flat_scale)
    tail_truncated = log_threshold > last_log
    tail_log_integral[tail_truncated] += (
        (last_log[tail_truncated] - log_threshold[tail_truncated])
        * (1.0 - flat_scale[tail_truncated])
        / flat_scale[tail_truncated]
    )
    conditional_moment += np.exp(tail_log_integral)

    result = flat_probability * conditional_moment
    if not np.isfinite(result).all():
        raise FloatingPointError("expected error dollars are not finite")
    return result.reshape(shape)


def expected_error_dollars(
    p_dev: Any,
    log_quantiles: Any,
    tail_scale: Any,
    threshold: Any,
    quantile_levels: Any = QUANTILE_LEVELS,
    minimum_magnitude: float = 0.5,
    magnitude_cap: Any | None = None,
) -> np.ndarray:
    """Return exact expected thresholded error dollars for each case.

    Without ``magnitude_cap`` this is
    ``E[|D| 1{|D| > threshold}]``. With a cap it is
    ``E[min(|D|, cap) 1{min(|D|, cap) > threshold}]``. The capped expression
    uses the identity ``E[M 1(T<M)] - E[M 1(C<M)] + C P(C<M)`` for ``C>T``.
    """
    quantiles, levels, minimum_log = _prepare_quantiles(
        log_quantiles, quantile_levels, minimum_magnitude
    )
    deviation_probability = _probability(p_dev, "p_dev")
    scale = _positive_tail_scale(tail_scale)
    threshold_array = _threshold(threshold)
    unbounded = _expected_error_dollars_uncapped(
        quantiles,
        levels,
        minimum_log,
        deviation_probability,
        scale,
        threshold_array,
    )
    if magnitude_cap is None:
        return unbounded

    cap = _magnitude_cap(magnitude_cap, minimum_magnitude)
    above_cap = _expected_error_dollars_uncapped(
        quantiles,
        levels,
        minimum_log,
        deviation_probability,
        scale,
        cap,
    )
    survival_at_cap = conditional_survival(
        cap,
        quantiles,
        scale,
        levels,
        minimum_magnitude,
    )
    try:
        (
            unbounded,
            above_cap,
            survival_at_cap,
            deviation_probability,
            cap,
            threshold_array,
        ) = np.broadcast_arrays(
            unbounded,
            above_cap,
            survival_at_cap,
            deviation_probability,
            cap,
            threshold_array,
        )
    except ValueError as exc:
        raise ValueError(
            "magnitude_cap must broadcast with the predictive-process inputs"
        ) from exc
    capped = unbounded - above_cap + deviation_probability * cap * survival_at_cap
    capped = np.where(cap > threshold_array, capped, 0.0)
    capped = np.maximum(capped, 0.0)
    if not np.isfinite(capped).all():
        raise FloatingPointError("capped expected error dollars are not finite")
    return capped
