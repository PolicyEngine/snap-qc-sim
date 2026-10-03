"""Guards for the deterministic FY2024 cause-share artifact."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from analysis import cause_shares
from analysis import train_error_model as error_model

LAB = Path(__file__).parents[1] / "paper/snapshot/labs/amterr"


def _loader_fixture() -> pd.DataFrame:
    source = pd.DataFrame(
        {column: np.zeros(2) for column in error_model.REQUIRED_COLS}
    )
    source["CASE"] = [1, 2]
    source["STATE"] = [8, 8]
    source["AGENCY1"] = [17, 1]
    for slot in range(1, 19):
        source[f"SLFEMP{slot}"] = 0.0
    return source


def test_shared_loader_retains_requested_public_cause_fields(monkeypatch):
    source = _loader_fixture()
    monkeypatch.setattr(
        error_model.pyreadstat,
        "read_sav",
        lambda path: (source.copy(), object()),
    )

    loaded = error_model.load_year(2024, additional_columns=["agency1"])

    assert loaded["AGENCY1"].tolist() == [17]
    assert loaded["state"].tolist() == ["CO"]
    assert loaded["CASE"].tolist() == [1]


def test_shared_loader_rejects_missing_requested_public_cause_field(monkeypatch):
    source = _loader_fixture().drop(columns="AGENCY1")
    monkeypatch.setattr(
        error_model.pyreadstat,
        "read_sav",
        lambda path: (source.copy(), object()),
    )

    with pytest.raises(ValueError, match=r"FY2024 SAV.*AGENCY1"):
        error_model.load_year(2024, additional_columns=["AGENCY1"])


def _partition_fixture() -> pd.DataFrame:
    cases = pd.DataFrame(
        {
            "HWGT": [2.0, 1.0, 3.0, 4.0],
            "AMTERR": [100.0, 60.0, 80.0, 70.0],
        }
    )
    for slot in cause_shares.SLOTS:
        cases[f"AGENCY{slot}"] = np.nan
        cases[f"AMOUNT{slot}"] = 0.0
        cases[f"E_FINDG{slot}"] = np.nan
        cases[f"ELEMENT{slot}"] = np.nan
    cases.loc[0, ["AGENCY1", "AMOUNT1", "E_FINDG1", "ELEMENT1"]] = [
        10,
        100,
        2,
        311,
    ]
    cases.loc[1, ["AGENCY1", "AMOUNT1", "E_FINDG1", "ELEMENT1"]] = [
        1,
        60,
        3,
        363,
    ]
    cases.loc[2, ["AGENCY1", "AMOUNT1", "E_FINDG1", "ELEMENT1"]] = [
        10,
        30,
        2,
        311,
    ]
    cases.loc[2, ["AGENCY2", "AMOUNT2", "E_FINDG2", "ELEMENT2"]] = [
        1,
        50,
        3,
        363,
    ]
    # A positive amount without its paired impact code is not an element dollar.
    cases.loc[3, ["AMOUNT1", "ELEMENT1"]] = [70, 311]
    return cases


def test_partition_arithmetic_is_exhaustive_and_handles_overlap():
    cases = _partition_fixture()
    official_dollars = float((cases["HWGT"] * cases["AMTERR"]).sum())

    case_result = cause_shares._case_summary(cases, official_dollars)
    element_result = cause_shares._element_summary(
        cause_shares._long_elements(cases), official_dollars, cases
    )

    fractional = case_result["fractional_class_attribution"]["classes"]
    assert official_dollars == 780
    assert fractional["agency_or_system"]["dollars"] == 320
    assert fractional["client_or_fact"]["dollars"] == 180
    assert fractional["unclassified"]["dollars"] == 280
    assert sum(group["dollars"] for group in fractional.values()) == 780

    exclusive = case_result["exclusive_axis"]["classes"]
    assert exclusive["agency_or_system"]["dollars"] == 200
    assert exclusive["client_or_fact"]["dollars"] == 60
    assert exclusive["mixed_agency_client"]["dollars"] == 240
    assert exclusive["residual_or_unclassified"]["dollars"] == 280

    any_presence = case_result["any_presence"]["classes"]
    assert any_presence["agency_or_system"]["dollars"] == 440
    assert any_presence["client_or_fact"]["dollars"] == 300
    assert element_result["total"]["dollars"] == 500
    assert element_result["classes"]["agency_or_system"]["dollars"] == 290
    assert element_result["classes"]["client_or_fact"]["dollars"] == 210
    assert (
        element_result["reconciliation"][
            "n_cases_without_positive_paired_element"
        ]
        == 1
    )


def _finding_nature_fixture() -> pd.DataFrame:
    cases = pd.DataFrame(
        {
            "HWGT": [1.0] * 5,
            "AMTERR": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )
    for slot in cause_shares.SLOTS:
        cases[f"AGENCY{slot}"] = np.nan
        cases[f"ELEMENT{slot}"] = np.nan
        cases[f"NATURE{slot}"] = np.nan

    # Inherent computation nature: pure_math regardless of cause.
    cases.loc[0, ["AGENCY1", "ELEMENT1", "NATURE1"]] = [1, 311, 36]
    # Conditional deduction nature: code 14 is in agency_or_system.
    cases.loc[1, ["AGENCY1", "ELEMENT1", "NATURE1"]] = [14, 363, 52]
    # The client-caused deduction is not made computational by a system cause
    # in a different slot. With no computational finding, this is system input.
    cases.loc[2, ["AGENCY1", "ELEMENT1", "NATURE1"]] = [1, 363, 52]
    cases.loc[2, ["AGENCY2", "ELEMENT2", "NATURE2"]] = [17, 311, 35]
    # One inherent computation finding plus one other finding is mixed.
    cases.loc[3, ["AGENCY1", "ELEMENT1", "NATURE1"]] = [1, 311, 42]
    cases.loc[3, ["AGENCY2", "ELEMENT2", "NATURE2"]] = [1, 331, 35]
    # Client-caused deduction alone is input_other.
    cases.loc[4, ["AGENCY1", "ELEMENT1", "NATURE1"]] = [1, 365, 57]
    return cases


def test_finding_nature_classes_pair_deduction_cause_and_cover_each_class():
    cases = _finding_nature_fixture()

    classes = cause_shares._finding_nature_classes(cases)

    assert classes.tolist() == [
        "pure_math",
        "pure_math",
        "input_system_caused",
        "mixed",
        "input_other",
    ]


def test_lab_legacy_rule_does_not_expand_to_full_agency_class():
    cases = _finding_nature_fixture().iloc[[1]]

    primary = cause_shares._finding_nature_classes(cases)
    legacy = cause_shares._finding_nature_classes(
        cases, system_codes=cause_shares.LAB_LEGACY_SYSTEM_CODES
    )

    assert primary.iloc[0] == "pure_math"
    assert legacy.iloc[0] == "input_other"


def test_committed_colorado_values_are_locked():
    artifact_path = Path("analysis/cause_shares.json")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    colorado = next(row for row in artifact["rows"] if row["state"] == "CO")

    assert colorado["universe_n"] == 856
    assert colorado["n"] == 110
    assert colorado["official_error_dollars"] == 94_092_792.02
    fractional = colorado["case_attributed"]["fractional_class_attribution"][
        "classes"
    ]
    assert fractional["agency_or_system"]["dollars"] == 52_852_349.72
    assert fractional["agency_or_system"][
        "share_of_official_error_dollars"
    ] == pytest.approx(0.561704553383, abs=0)
    assert fractional["client_or_fact"]["dollars"] == 40_954_031.43
    assert colorado["element_attributed"]["total"]["dollars"] == 4_177_027.62

    lab = colorado["finding_nature"]["lab_legacy_broad_rules_engine"][
        "deviation"
    ]
    assert lab["denominator"]["n"] == 305
    assert lab["denominator"]["dollars"] == 112_575_220.49
    assert {
        name: (metric["n"], metric["dollars"])
        for name, metric in lab["classes"].items()
    } == {
        "pure_math": (13, 3_662_840.51),
        "input_system_caused": (19, 7_468_437.90),
        "mixed": (13, 4_683_116.80),
        "input_other": (260, 96_760_825.27),
    }
    assert lab["classes"]["pure_math"][
        "share_of_deviation_dollars"
    ] == pytest.approx(0.032536827296, abs=0)
    assert lab["classes"]["input_system_caused"][
        "share_of_deviation_dollars"
    ] == pytest.approx(0.06634175685, abs=0)
    assert lab["classes"]["mixed"][
        "share_of_deviation_dollars"
    ] == pytest.approx(0.041599890114, abs=0)
    assert lab["classes"]["input_other"][
        "share_of_deviation_dollars"
    ] == pytest.approx(0.85952152574, abs=0)


def test_committed_artifact_has_all_states_and_additive_national_partition():
    artifact = json.loads(Path("analysis/cause_shares.json").read_text(encoding="utf-8"))
    states = [row for row in artifact["rows"] if row["state"] != "US"]
    national = next(row for row in artifact["rows"] if row["state"] == "US")

    assert len(states) == 53
    assert {row["state"] for row in states} == set(error_model.FIPS.values())
    assert national["universe_n"] == 44_800
    assert national["n"] == 5_428
    assert national["official_error_dollars"] == 6_590_374_140.76
    classes = national["case_attributed"]["fractional_class_attribution"][
        "classes"
    ]
    assert sum(group["dollars"] for group in classes.values()) == pytest.approx(
        national["official_error_dollars"], abs=0.02
    )
    for row in artifact["rows"]:
        for denominator in ("deviation", "official_error"):
            summary = row["finding_nature"]["primary_agency_or_system"][
                denominator
            ]
            assert sum(
                metric["n"] for metric in summary["classes"].values()
            ) == summary["denominator"]["n"]
            assert sum(
                metric["dollars"] for metric in summary["classes"].values()
            ) == pytest.approx(summary["denominator"]["dollars"], abs=0.02)


def _replay_reconciliation() -> dict:
    artifact = json.loads(
        Path("analysis/cause_shares.json").read_text(encoding="utf-8")
    )
    return artifact["colorado_replay_reconciliation"]


def test_replay_outcomes_carry_only_the_documented_test():
    replay = _replay_reconciliation()
    labels = set(cause_shares.REPLAY_OUTCOMES)

    assert labels == {"reproduced", "not_reproduced"}
    assert replay["reference"]["classification"] == (
        "reproduced if abs(engine_on_original - RAWBEN) <= 5, else not_reproduced"
    )
    for part in replay["slices"].values():
        assert set(part["outcomes"]) == labels
    for table in (
        "official_replay_fractional_cause_by_engine_outcome",
        "official_replay_any_agency_by_engine_outcome",
    ):
        for row in replay[table].values():
            assert set(row) == labels
    # The lab withdrew the reading that a miss bounds computation-side error.
    text = json.dumps(replay).lower()
    for withdrawn in ("upper bound", "upper_bound", "computation_side", "explained"):
        assert withdrawn not in text


def test_replay_within5_flag_is_the_documented_test():
    """Every committed replay row's flag equals abs(engine - RAWBEN) <= 5."""
    rows = json.loads(cause_shares.REPLAY_PATH.read_text(encoding="utf-8"))
    tolerance = cause_shares.REPLAY_TOLERANCE_DOLLARS

    assert len(rows) == 283
    for row in rows:
        engine, rawben = row["engine_on_original"], row["rawben"]
        expected = (
            engine is not None
            and rawben is not None
            and abs(engine - rawben) <= tolerance
        )
        assert row["within5"] is expected, row["case_id"]
    assert _replay_reconciliation()["reference"]["sha256"] == hashlib.sha256(
        cause_shares.REPLAY_PATH.read_bytes()
    ).hexdigest()


def test_replay_reconciliation_partitions_are_exact():
    replay = _replay_reconciliation()
    slices = replay["slices"]
    outcomes = cause_shares.REPLAY_OUTCOMES

    for part in slices.values():
        total = part["total"]
        metrics = [part["outcomes"][outcome] for outcome in outcomes]
        assert sum(metric["n"] for metric in metrics) == total["n"]
        assert sum(metric["dollars"] for metric in metrics) == pytest.approx(
            total["dollars"], abs=0.02
        )
        assert sum(metric["weighted_n"] for metric in metrics) == pytest.approx(
            total["weighted_n"], abs=2e-6
        )
        assert sum(
            metric["share_of_slice_dollars"] for metric in metrics
        ) == pytest.approx(1, abs=2e-12)

    everything = slices["all_283"]
    official = slices["official_above_threshold_97"]
    subthreshold = slices["subthreshold_186"]
    denominators = replay["denominator_reconciliation"]
    assert everything["total"]["n"] == denominators["replay_all_n"] == 283
    assert official["total"]["n"] == (
        denominators["replay_official_above_threshold_n"]
    ) == 97
    for outcome in outcomes:
        assert (
            official["outcomes"][outcome]["n"]
            + subthreshold["outcomes"][outcome]["n"]
            == everything["outcomes"][outcome]["n"]
        )
        assert official["outcomes"][outcome]["dollars"] + subthreshold[
            "outcomes"
        ][outcome]["dollars"] == pytest.approx(
            everything["outcomes"][outcome]["dollars"], abs=0.02
        )

    fractional = replay["official_replay_fractional_cause_by_engine_outcome"]
    binary = replay["official_replay_any_agency_by_engine_outcome"]
    for outcome in outcomes:
        expected = official["outcomes"][outcome]
        assert sum(
            row[outcome]["fractional_n"] for row in fractional.values()
        ) == pytest.approx(expected["n"], abs=1e-5)
        assert sum(
            row[outcome]["dollars"] for row in fractional.values()
        ) == pytest.approx(expected["dollars"], abs=0.01 * len(fractional))
        assert sum(row[outcome]["n"] for row in binary.values()) == expected["n"]
        assert sum(
            row[outcome]["dollars"] for row in binary.values()
        ) == pytest.approx(expected["dollars"], abs=0.02)

    residual = replay["committed_prose_discrepancy"]
    assert residual["recomputed_broad_residual_n"] <= (
        everything["outcomes"]["not_reproduced"]["n"]
    )


def test_replay_reconciliation_agrees_with_the_lab_claims_audit():
    """Differential check of two implementations of the replay accounting.

    cause_shares.py reads the FY2024 SAV; the lab's audit_claims.py reads the
    May 2026 CSV posting, which carries the same HWGT.
    """
    replay = _replay_reconciliation()
    audit = json.loads((LAB / "claims_audit.json").read_text(encoding="utf-8"))
    case_level = audit["case_level"]["replay"]
    may = audit["by_posting"]["may2026"]
    everything = replay["slices"]["all_283"]
    official = replay["slices"]["official_above_threshold_97"]

    assert audit["conventions"]["reproduced"] == (
        "abs(engine_on_original - RAWBEN) <= 5"
    )
    assert everything["total"]["n"] == case_level["n"] == may["replay"]["replayed"]["n"]
    assert everything["total"]["dollars"] == pytest.approx(
        may["replay"]["replayed"]["dollars"], abs=0.01
    )
    assert official["total"]["n"] == may["replay"]["replayed"]["above_threshold_n"]
    assert (
        everything["solver_engine_within5_concordant_n"]
        == case_level["solver_and_engine_agree_n"]
    )
    for outcome in cause_shares.REPLAY_OUTCOMES:
        ours = everything["outcomes"][outcome]
        theirs = may["replay"][outcome]
        assert ours["n"] == case_level[f"{outcome}_n"] == theirs["n"]
        assert ours["dollars"] == pytest.approx(theirs["dollars"], abs=0.01)
        assert official["outcomes"][outcome]["n"] == theirs["above_threshold_n"]

    broad = may["class_by_replay_outcome"]["broad_10_17_19_20_21_22"]["all_errors"][
        "not_reproduced"
    ]
    residual = replay["committed_prose_discrepancy"]
    assert residual["recomputed_broad_residual_n"] == broad["n"] == (
        audit["case_level"]["broad_coded_misses"]["n"]
    )
    assert residual["recomputed_hwgt_times_amterr_dollars"] == pytest.approx(
        broad["dollars"], abs=0.01
    )


def test_prose_discrepancy_points_at_a_commit_and_the_lab_correction():
    residual = _replay_reconciliation()["committed_prose_discrepancy"]
    commit = cause_shares.PROSE_CLAIM_COMMIT

    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    assert residual["claim_location"] == (
        f"paper/snapshot/labs/amterr/ANALYSIS.md:L62-L67 at commit {commit}"
    )
    analysis = (LAB / "ANALYSIS.md").read_text(encoding="utf-8")
    assert "### The 10 broad-coded cases that do not reproduce" in analysis
    assert "The July text gave $3.28M (3.3%); that figure does not" in analysis
    for figure in ("$4.47M", "$2.91M"):
        assert figure in analysis


def test_prose_discrepancy_lines_hold_the_claim_at_that_commit():
    """Needs the commit in local history; shallow CI checkouts skip."""
    revision = (
        f"{cause_shares.PROSE_CLAIM_COMMIT}:paper/snapshot/labs/amterr/ANALYSIS.md"
    )
    try:
        old = subprocess.run(
            ["git", "show", revision],
            capture_output=True,
            check=True,
            cwd=Path(__file__).parents[1],
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("claim commit is not in local git history")
    cited = "\n".join(old.splitlines()[61:67])

    assert cited.startswith("- **10 of those 37 also carry QC's own")
    assert "$3.28M/yr = 3.3% of replayed" in cited


@given(
    st.lists(
        st.tuples(
            st.floats(0.01, 1e5, allow_nan=False),
            st.floats(0, 5e3, allow_nan=False),
            st.booleans(),
        ),
        min_size=1,
        max_size=40,
    )
)
def test_replay_metric_is_additive_over_the_outcome_partition(rows):
    frame = pd.DataFrame(rows, columns=["HWGT", "AMTERR", "within5"])
    frame["case_dollars"] = frame["HWGT"] * frame["AMTERR"]
    denominator = float(frame["case_dollars"].sum())
    total = cause_shares._replay_metric(frame, denominator)
    parts = [
        cause_shares._replay_metric(frame.loc[frame["within5"].eq(flag)], denominator)
        for flag in (True, False)
    ]

    assert sum(part["n"] for part in parts) == total["n"] == len(frame)
    assert sum(part["dollars"] for part in parts) == pytest.approx(
        total["dollars"], abs=0.011, rel=1e-12
    )
    assert sum(part["weighted_n"] for part in parts) == pytest.approx(
        total["weighted_n"], abs=1.1e-6, rel=1e-12
    )
    if denominator > 0:
        assert total["share_of_slice_dollars"] == 1.0
        assert sum(
            part["share_of_slice_dollars"] for part in parts
        ) == pytest.approx(1, abs=2e-12)
