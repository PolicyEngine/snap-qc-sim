"""Guards for the engine-comparison artifact and its app projection."""

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from analysis import engine_comparison

REPO = Path(__file__).resolve().parent.parent
ARTIFACT = REPO / "analysis" / "engine_comparison.json"
APP_PAYLOAD = REPO / "app" / "public" / "engine_data.json"
APP_JS = REPO / "app" / "public" / "app.js"


def _universe_fixture() -> pd.DataFrame:
    """Six cases covering every catalog class plus concordant rows."""
    return pd.DataFrame(
        {
            # concordant error, concordant clean, adjustment, correction,
            # nonformula (ssi-cap), nonformula (minimum benefit)
            "HWGT": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "RAWBEN": [100, 200, 250, 120, 300, 23],
            "BENFIX": [80, 200, 250, 100, 300, 23],
            "FSBEN": [80, 200, 291, 99, 260, 30],
            "AMTERR": [20, 0, 0, 20, 0, 0],
            "ALLADJ": [1, 1, 2, 1, 1, 1],
            "AMTADJ": [0, 0, 41, 0, 0, 0],
            "SSI_CAP": [0, 0, 0, 0, 2, 0],
            "FSMINBEN": [0, 0, 0, 0, 0, 1],
        }
    )


def test_catalog_partition_is_exhaustive_and_disjoint():
    catalog = engine_comparison.catalog_for_frame(_universe_fixture())
    classes = catalog["classes"]
    assert catalog["universe"] == 6
    assert catalog["divergent"] == 4
    assert classes["allotment_adjustment"]["n"] == 1
    assert classes["error_correction_arithmetic"]["n"] == 1
    assert classes["recorded_correct_nonformula"]["n"] == 2
    assert (
        classes["allotment_adjustment"]["n"]
        + classes["error_correction_arithmetic"]["n"]
        + classes["recorded_correct_nonformula"]["n"]
        == catalog["divergent"]
    )
    assert classes["allotment_adjustment"]["prorated_n"] == 1
    assert classes["allotment_adjustment"]["amount_reconciles_n"] == 1
    assert classes["recorded_correct_nonformula"]["ssi_cap_coded_n"] == 1
    assert classes["recorded_correct_nonformula"]["minimum_benefit_n"] == 1
    # Weighted shares are of the full state universe.
    assert classes["allotment_adjustment"]["weighted_share_of_universe"] == (
        pytest.approx(3.0 / 21.0)
    )
    assert catalog["concordance_weighted"]["benfix"] == 1.0
    # FSBEN matches the recorded error only where FSBEN == BENFIX:
    # weights 1 + 2 of 21.
    assert catalog["concordance_weighted"]["fsben"] == pytest.approx(3.0 / 21.0)


def test_catalog_rejects_error_anchor_violation():
    frame = _universe_fixture()
    frame.loc[0, "AMTERR"] = 19  # |RAWBEN - BENFIX| is 20
    with pytest.raises(AssertionError, match="RAWBEN - BENFIX"):
        engine_comparison.catalog_for_frame(frame)


def test_catalog_rejects_undocumented_alladj_code():
    frame = _universe_fixture()
    frame.loc[2, "ALLADJ"] = 4
    with pytest.raises(AssertionError, match="ALLADJ"):
        engine_comparison.catalog_for_frame(frame)


def _report_fixture(**overrides):
    report = {
        "suite": "xx-snap-qc",
        "summary": {
            "comparison_count": 2,
            "match_count": 2,
            "mismatch_count": 0,
            "exclusions": {
                "total_loaded": 2,
                "total_excluded": 1,
                "by_reason": {"ssi_cap": 1},
            },
            "provenance": {"pins": {"sha256": "abc", "url": "u"}},
        },
        "mismatches": [],
        "cases": [
            {"case_id": "a", "matched": True},
            {"case_id": "b", "matched": True},
        ],
        "aggregates": [
            {
                "description": f"stage {index}",
                "concept": f"us:x#c{index}",
                "comparison_count": 2,
                "mismatch_count": 0,
            }
            for index in range(6)
        ],
    }
    report.update(overrides)
    return report


def test_parity_extraction_reads_exact_report():
    parity = engine_comparison.parity_from_report(_report_fixture())
    assert parity["compared"] == 2
    assert parity["matched"] == 2
    assert parity["excluded"] == 1
    assert parity["excluded_reasons"] == {"ssi_cap": 1}
    assert [stage["label"] for stage in parity["stages"]] == [
        f"stage {index}" for index in range(6)
    ]


def test_parity_extraction_rejects_mismatched_report():
    report = _report_fixture()
    report["summary"]["match_count"] = 1
    report["summary"]["mismatch_count"] = 1
    with pytest.raises(AssertionError, match="not exact parity"):
        engine_comparison.parity_from_report(report)


def test_parity_extraction_rejects_partial_stage_coverage():
    report = _report_fixture()
    report["aggregates"][3]["comparison_count"] = 1
    with pytest.raises(AssertionError, match="stage"):
        engine_comparison.parity_from_report(report)


# ---- Committed-artifact locks (run without any local data cache) ----------


def _artifact() -> dict:
    with ARTIFACT.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_committed_totals_are_locked():
    totals = _artifact()["totals"]
    assert totals == {
        "universe": 6194,
        "compared": 6081,
        "matched": 6081,
        "excluded": 113,
        "stage_cells": 36486,
        "divergent": 881,
        "excluded_reasons": {"ssi_cap": 113},
    }


def test_committed_state_universe_and_partition_are_consistent():
    artifact = _artifact()
    assert list(artifact["states"]) == list(engine_comparison.VERIFIED_STATES)
    for state in artifact["states"].values():
        parity = state["parity"]
        catalog = state["catalog"]
        assert parity["loaded"] + parity["excluded"] == catalog["universe"]
        assert parity["matched"] == parity["compared"] == parity["loaded"]
        assert len(parity["stages"]) == 6
        assert all(
            stage["matched"] == stage["n"] == parity["compared"]
            for stage in parity["stages"]
        )
        classes = catalog["classes"]
        assert (
            classes["allotment_adjustment"]["n"]
            + classes["error_correction_arithmetic"]["n"]
            + classes["recorded_correct_nonformula"]["n"]
            == catalog["divergent"]
        )
        assert catalog["concordance_weighted"]["benfix"] == 1.0


def test_committed_parity_re_derives_from_snapshot_reports():
    artifact = _artifact()
    for code in engine_comparison.VERIFIED_STATES:
        path = engine_comparison.SNAPSHOT_DIR / f"axiom-snapqc-{code.lower()}-snap.json"
        parity = engine_comparison.parity_from_report(
            engine_comparison.load_report(path)
        )
        pin = parity.pop("qc_pin")
        assert pin == artifact["provenance"]["qc_archive_pin"]
        assert parity == artifact["states"][code]["parity"]


def test_committed_snapshot_hashes_match_recorded_pins():
    recorded = _artifact()["provenance"]["suite_reports"]
    on_disk = {
        path.name: engine_comparison.sha256_of(path)
        for path in sorted(engine_comparison.SNAPSHOT_DIR.glob("axiom-snapqc-*.json"))
    }
    assert on_disk == recorded


def test_committed_national_block_quotes_hurdle_results():
    artifact = _artifact()
    with engine_comparison.HURDLE_RESULTS_PATH.open(encoding="utf-8") as handle:
        concordance = json.load(handle)["target_concordance"]["fy2024"]
    assert artifact["national"]["n"] == concordance["n"]
    assert (
        artifact["national"]["concordance_weighted"]["benfix"]
        == concordance["abs_RAWBEN_minus_BENFIX_equals_AMTERR_weighted"]
    )
    assert (
        artifact["national"]["concordance_weighted"]["fsben"]
        == concordance["abs_RAWBEN_minus_FSBEN_equals_AMTERR_weighted"]
    )


def test_app_payload_is_the_exact_projection():
    with APP_PAYLOAD.open(encoding="utf-8") as handle:
        committed = json.load(handle)
    assert committed == engine_comparison.app_payload(_artifact())


def test_app_js_pins_the_engine_payload_sha256():
    js = APP_JS.read_text()
    pin = re.search(r'const ENGINE_DATA_SHA256 =\s*"([0-9a-f]{64})"', js)
    assert pin, "app.js must pin engine_data.json by SHA-256"
    assert pin.group(1) == engine_comparison.sha256_of(APP_PAYLOAD)
