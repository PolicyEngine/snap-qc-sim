"""The FY2027-mode payload stays consistent with its committed sources.

The payload vendors values from the snap-fy27-margins workspace (not part
of this repo), so these tests lock the committed JSON's internal
consistency and its agreement with in-repo artifacts; the builder's
provenance hashes record the external lineage.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = json.loads((ROOT / "app/public/fy2027_data.json").read_text())
DATA = json.loads((ROOT / "app/public/data.json").read_text())
MOVEMENT = json.loads((ROOT / "analysis/fy2025_movement.json").read_text())
FY2027_PARAMS = json.loads((ROOT / "analysis/fy2027_parameters.json").read_text())

VERIFIED = {"AZ", "CA", "CO", "GA", "MD", "NY", "TX"}


def test_states_and_anchoring_arithmetic():
    assert set(PAYLOAD["states"]) == VERIFIED
    for code, st in PAYLOAD["states"].items():
        assert st["official_fy2025_pct"] == DATA["states"][code]["official_fy2025"]
        for band in st["bands"].values():
            for conv in ("fixed", "proportional"):
                anchored = band[f"anchored_{conv}_pct"]
                mechanical = band[f"mechanical_{conv}_pct"]
                expected = (
                    st["official_fy2025_pct"]
                    + mechanical
                    - st["fy2024_mechanical_pct"]
                )
                assert abs(anchored - expected) < 2e-4, (code, conv)


def test_thresholds_agree_with_in_repo_derivation():
    t27 = PAYLOAD["thresholds"]["2027"]
    assert t27["status"] == "ESTIMATE"
    assert (
        t27["threshold_dollars_strictly_greater_than"]
        == FY2027_PARAMS["fy2027_result"]["threshold_dollars"]
    )
    assert PAYLOAD["thresholds"]["2026"]["threshold_dollars_strictly_greater_than"] == 58


def test_drift_taus_match_movement_artifact():
    pts = MOVEMENT["drift_estimate"]["point_estimates"]
    assert PAYLOAD["drift_tau_pp"]["robust"] == pts["robust_median_mad"]["tau_pp"]
    assert (
        PAYLOAD["drift_tau_pp"]["classical"]
        == pts["classical_method_of_moments"]["tau_pp"]
    )


def test_estimate_status_is_stamped():
    assert PAYLOAD["fy2027_max_allotment_4p_48dc"]["status"] == "ESTIMATE"
    assert PAYLOAD["fy2027_max_allotment_4p_48dc"]["dollars"] == 1029
    assert "conventions" in PAYLOAD["accounting_note"]
