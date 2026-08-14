"""Shared fixtures for the snap-qc-sim test suite."""

from __future__ import annotations

from typing import Any

import pytest


def _assert_values_match(actual: Any, expected: Any, *, path: str = "$") -> None:
    """Assert two parsed JSON artifacts match value-for-value.

    Structure is strict: dicts need identical key lists (same keys, same
    order), lists identical lengths, and every non-float leaf must match
    exactly, type included. Floats compare at rel=1e-9 so last-ulp
    optimizer noise passes while real drift fails.
    """
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: {type(actual).__name__} is not dict"
        assert list(actual) == list(expected), f"{path}: key lists differ"
        for key, value in expected.items():
            _assert_values_match(actual[key], value, path=f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: {type(actual).__name__} is not list"
        assert len(actual) == len(expected), f"{path}: lengths differ"
        for index, value in enumerate(expected):
            _assert_values_match(actual[index], value, path=f"{path}[{index}]")
    elif isinstance(expected, float):
        assert isinstance(actual, float), (
            f"{path}: {type(actual).__name__} is not float"
        )
        assert actual == pytest.approx(expected, rel=1e-9), path
    else:
        assert type(actual) is type(expected), (
            f"{path}: {type(actual).__name__} is not {type(expected).__name__}"
        )
        assert actual == expected, path


@pytest.fixture
def assert_artifact_values_match():
    """Provide the value-lock comparator used by raw regeneration tests."""
    return _assert_values_match
