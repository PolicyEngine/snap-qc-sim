"""Contract tests for the system-migration event registry (design 1)."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "analysis/system_migrations.json").read_text())

CONFIDENCE = set(REGISTRY["confidence_levels"])
POSITIONS = {"pre_panel", "edge", "in_panel"}


def test_registry_schema_and_enums() -> None:
    assert REGISTRY["schema"] == "snap_qc_sim.system_migrations.v1"
    for ev in REGISTRY["events"]:
        assert ev["confidence"] in CONFIDENCE, ev["state"]
        assert ev["panel_position"] in POSITIONS, ev["state"]
        assert ev["notes"], ev["state"]


def test_verified_events_carry_dates_and_sources() -> None:
    """A 'verified' label without a date or source would be vacuous."""
    for ev in REGISTRY["events"]:
        if ev["confidence"].startswith("verified"):
            assert ev["go_live"], ev["state"]
            assert ev["sources"], ev["state"]
            parts = ev["go_live"].split("-")
            assert (
                ev["date_precision"] == {1: "year", 2: "month", 3: "day"}[len(parts)]
            ), ev["state"]
            if ev["date_precision"] == "day":
                datetime.date.fromisoformat(ev["go_live"])
        if ev["confidence"] == "verified_multi_source":
            assert len(ev["sources"]) >= 2, ev["state"]


def test_panel_positions_are_consistent_with_dates() -> None:
    """Panel FY2017 starts 2016-10; dated events must match their label."""
    for ev in REGISTRY["events"]:
        if not ev["go_live"]:
            continue
        year = int(ev["go_live"].split("-")[0])
        if ev["panel_position"] == "in_panel":
            assert year >= 2017, ev["state"]
        if ev["panel_position"] == "pre_panel":
            assert year <= 2016, ev["state"]
        if ev["panel_position"] == "edge":
            assert year == 2016, ev["state"]
