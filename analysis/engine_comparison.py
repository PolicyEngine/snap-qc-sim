"""Build the Axiom rules-engine comparison artifact for the simulator.

The simulator's engine mode displays two things for the seven verified
states, and every number it shows comes from the artifact this module
emits:

* **Stage parity** — the committed axiom-oracles comparison reports
  (byte-identical copies under ``paper/snapshot/oracle-suites/``) replay
  each state's FY2024 QC public-use reviews through the Axiom RuleSpec
  SNAP composition and compare six recorded stages — gross income,
  standard deduction, excess-shelter deduction, net income, maximum
  allotment, and the benefit — at zero tolerance against the file's own
  Minimodel-recomputed values (``FSBEN`` and companions).  This module
  re-derives the per-state parity counts from those reports and asserts
  the exactness the app displays (every compared case matches at every
  stage; excluded cases are enumerated program-structure classes).

* **The formula-benefit divergence catalog** — the public file records
  three benefit anchors per case: ``RAWBEN`` (the allotment the state
  issued), ``BENFIX`` (the allotment corrected for the reviewer's
  findings), and ``FSBEN`` (the Minimodel's full-formula recomputation
  from the edited inputs).  ``|RAWBEN - BENFIX|`` equals the recorded
  error amount ``AMTERR`` for every official-universe case in the seven
  states; ``FSBEN`` differs from ``BENFIX`` for a catalogued minority,
  so a formula recomputation alone conflates recorded allotment
  adjustments with error.  The catalog partitions the divergent cases by
  what the file records: a coded allotment adjustment (``ALLADJ`` 2/3,
  prorated or other), an error correction whose recorded amount is not
  the formula gap (``ALLADJ`` 1 with ``AMTERR`` > 0), or an issuance the
  review judged correct that the formula chain does not produce
  (``ALLADJ`` 1 with ``AMTERR`` = 0; includes coded SSI-CAP standardized
  benefits and minimum-benefit cases).

These are accounting conventions recorded in the file, not causal
attributions.  Regenerate with::

    uv run --frozen --extra analysis python analysis/engine_comparison.py

The QC public-use CSV is required locally (path below or first CLI
argument); its SHA-256 must match the certification report's pin.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO_ROOT / "paper" / "snapshot" / "oracle-suites"
HURDLE_RESULTS_PATH = REPO_ROOT / "analysis" / "hurdle_results.json"
ANALYSIS_OUTPUT = REPO_ROOT / "analysis" / "engine_comparison.json"
REPORT_OUTPUT = REPO_ROOT / "analysis" / "ENGINE_COMPARISON.md"
APP_OUTPUT = REPO_ROOT / "app" / "public" / "engine_data.json"
DEFAULT_QC_CSV = Path("~/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv").expanduser()

SCHEMA = "snap_qc_sim.engine_comparison.v1"

#: FIPS codes for the seven states whose SNAP benefit computations the
#: axiom-oracles suites verify (suite order mirrors the verification arc).
VERIFIED_STATES = {
    "CO": 8,
    "NY": 36,
    "CA": 6,
    "AZ": 4,
    "GA": 13,
    "MD": 24,
    "TX": 48,
}

#: Committed comparison reports copied byte-identically from
#: TheAxiomFoundation/axiom-oracles at the commit below.
ORACLE_REPO = "TheAxiomFoundation/axiom-oracles"
ORACLE_COMMIT = "f30f9a1014ec957d26dcffd33af4356a48b9f174"

#: Certification-probe toolchain pins (Colorado scope), from the committed
#: paper/snapshot/cert/CERT_REPORT.md and engine-leg manifests.
CERTIFIED_TOOLCHAIN = {
    "scope": "Colorado certification probe (paper/snapshot/cert/CERT_REPORT.md)",
    "engine_commit": "de0efdc73b469132ee268e1c832e8f7148b91431",
    "engine_binary_sha256": (
        "bb8ec23689697a5417b74c38196c0488e002e4ee6fe3b33faabb39005e6e5eee"
    ),
    "rulespec_us_commit": "b53ce208771085030939db4b9691762506b6bca2",
    "harness_commit": "d30566266932dbd0b6f62e69dcea8ca3c8801690",
}

#: SHA-256 of the extracted qc_pub_fy2024.csv, pinned by the certification
#: report (the oracle reports pin the source archive; both are recorded).
QC_CSV_SHA256 = "45193eb7370463ab3067d71da23a580fec34a5460341e4e750dda0be061e1aa9"

QC_COLUMNS = [
    "CASE",
    "STATE",
    "HWGT",
    "RAWBEN",
    "BENFIX",
    "FSBEN",
    "AMTERR",
    "ALLADJ",
    "AMTADJ",
    "SSI_CAP",
    "FSMINBEN",
]

#: Dollar band treated as rounding-scale when summarizing gap magnitudes.
ROUNDING_BAND_DOLLARS = 2


def sha256_of(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_report(path: Path) -> dict[str, Any]:
    """Load one committed axiom-oracles comparison report."""
    with path.open(encoding="utf-8") as handle:
        report = json.load(handle)
    if not isinstance(report, dict):
        raise TypeError(f"{path.name} must contain a JSON object")
    return report


def parity_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """Extract and assert the stage-parity facts the app displays.

    Raises if the report shows anything other than exact parity: the app
    renders these counts as certified badges, so a mismatching or
    partially-compared report must fail the build, not soften the badge.
    """
    summary = report["summary"]
    exclusions = summary["exclusions"]
    compared = int(summary["comparison_count"])
    matched = int(summary["match_count"])
    mismatched = int(summary["mismatch_count"])
    if matched != compared or mismatched != 0:
        raise AssertionError(
            f"suite {report['suite']}: {matched}/{compared} matched, "
            f"{mismatched} mismatched — not exact parity"
        )
    if report["mismatches"]:
        raise AssertionError(f"suite {report['suite']}: mismatch rows present")
    cases = report["cases"]
    if len(cases) != compared or not all(case["matched"] for case in cases):
        raise AssertionError(
            f"suite {report['suite']}: case rows disagree with the summary"
        )
    stages = []
    for aggregate in report["aggregates"]:
        stage_compared = int(aggregate["comparison_count"])
        if stage_compared != compared or int(aggregate["mismatch_count"]) != 0:
            raise AssertionError(
                f"suite {report['suite']} stage {aggregate['description']}: "
                "stage comparisons disagree with the case count"
            )
        stages.append(
            {
                "label": aggregate["description"],
                "concept": aggregate["concept"],
                "n": stage_compared,
                "matched": stage_compared - int(aggregate["mismatch_count"]),
            }
        )
    if len(stages) != 6:
        raise AssertionError(
            f"suite {report['suite']}: expected six stages, got {len(stages)}"
        )
    excluded_reasons = {
        reason: int(count) for reason, count in sorted(exclusions["by_reason"].items())
    }
    excluded = int(exclusions["total_excluded"])
    if sum(excluded_reasons.values()) != excluded:
        raise AssertionError(
            f"suite {report['suite']}: exclusion reasons do not sum to the total"
        )
    return {
        "suite": report["suite"],
        "loaded": int(exclusions["total_loaded"]),
        "excluded": excluded,
        "excluded_reasons": excluded_reasons,
        "compared": compared,
        "matched": matched,
        "stages": stages,
        "qc_pin": dict(summary["provenance"]["pins"]),
    }


def catalog_for_frame(frame: pd.DataFrame) -> dict[str, Any]:
    """Partition one state's official-universe cases by benefit-anchor gaps.

    ``frame`` carries the QC columns for a single state's ``CASE == 1``
    rows.  The three divergence classes are disjoint and exhaustive over
    ``FSBEN != BENFIX`` by construction (coded adjustment / error present /
    neither); class-internal identities are asserted, not assumed.
    """
    if not frame["ALLADJ"].isin([1, 2, 3]).all():
        raise AssertionError("ALLADJ outside the documented 1/2/3 codes")
    weight = frame["HWGT"]
    total_weight = float(weight.sum())
    error_matches_benfix = (frame["RAWBEN"] - frame["BENFIX"]).abs() == frame["AMTERR"]
    error_matches_fsben = (frame["RAWBEN"] - frame["FSBEN"]).abs() == frame["AMTERR"]
    if not error_matches_benfix.all():
        raise AssertionError("|RAWBEN - BENFIX| != AMTERR inside a verified state")

    divergent = frame[frame["FSBEN"] != frame["BENFIX"]].copy()
    divergent["gap"] = divergent["FSBEN"] - divergent["BENFIX"]
    adjustment = divergent[divergent["ALLADJ"].isin([2, 3])]
    correction = divergent[(divergent["ALLADJ"] == 1) & (divergent["AMTERR"] > 0)]
    nonformula = divergent[(divergent["ALLADJ"] == 1) & (divergent["AMTERR"] == 0)]
    if len(adjustment) + len(correction) + len(nonformula) != len(divergent):
        raise AssertionError("divergence classes do not partition the divergent cases")
    if not (nonformula["RAWBEN"] == nonformula["BENFIX"]).all():
        raise AssertionError("a no-adjustment, no-error case has RAWBEN != BENFIX")

    def class_block(block: pd.DataFrame) -> dict[str, Any]:
        return {
            "n": len(block),
            "weighted_share_of_universe": float(block["HWGT"].sum() / total_weight),
            "within_rounding_band_n": int(
                (block["gap"].abs() <= ROUNDING_BAND_DOLLARS).sum()
            ),
            "median_abs_gap_dollars": (
                float(block["gap"].abs().median()) if len(block) else None
            ),
        }

    return {
        "universe": len(frame),
        "universe_weight": total_weight,
        "concordance_weighted": {
            "benfix": float((error_matches_benfix * weight).sum() / total_weight),
            "fsben": float((error_matches_fsben * weight).sum() / total_weight),
        },
        "divergent": len(divergent),
        "divergent_weighted_share": float(divergent["HWGT"].sum() / total_weight),
        "classes": {
            "allotment_adjustment": {
                **class_block(adjustment),
                "prorated_n": int((adjustment["ALLADJ"] == 2).sum()),
                "other_adjustment_n": int((adjustment["ALLADJ"] == 3).sum()),
                "no_error_n": int((adjustment["AMTERR"] == 0).sum()),
                "amount_reconciles_n": int(
                    (
                        adjustment["BENFIX"]
                        == adjustment["FSBEN"] - adjustment["AMTADJ"]
                    ).sum()
                ),
            },
            "error_correction_arithmetic": class_block(correction),
            "recorded_correct_nonformula": {
                **class_block(nonformula),
                "ssi_cap_coded_n": int((nonformula["SSI_CAP"] != 0).sum()),
                "minimum_benefit_n": int((nonformula["FSMINBEN"] == 1).sum()),
            },
        },
    }


def load_universe(qc_csv: Path) -> pd.DataFrame:
    """Load the official-universe rows for the seven verified states."""
    frame = pd.read_csv(qc_csv, usecols=QC_COLUMNS)
    frame = frame[frame["CASE"] == 1]
    fips_to_code = {fips: code for code, fips in VERIFIED_STATES.items()}
    frame = frame[frame["STATE"].isin(fips_to_code)].copy()
    frame["code"] = frame["STATE"].map(fips_to_code)
    return frame


def build_artifact(
    reports: dict[str, dict[str, Any]],
    universe: pd.DataFrame,
    hurdle_results: dict[str, Any],
    report_hashes: dict[str, str],
    qc_csv_sha256: str,
) -> dict[str, Any]:
    """Assemble the full engine-comparison artifact."""
    if qc_csv_sha256 != QC_CSV_SHA256:
        raise AssertionError(
            "QC CSV SHA-256 does not match the certification report's pin: "
            f"{qc_csv_sha256}"
        )
    states: dict[str, Any] = {}
    archive_pin: dict[str, Any] | None = None
    for code in VERIFIED_STATES:
        parity = parity_from_report(reports[code])
        pin = parity.pop("qc_pin")
        if archive_pin is None:
            archive_pin = pin
        elif archive_pin != pin:
            raise AssertionError("suite reports disagree on the QC source pin")
        state_frame = universe[universe["code"] == code]
        if len(state_frame) != parity["loaded"] + parity["excluded"]:
            raise AssertionError(
                f"{code}: CSV official universe {len(state_frame)} != "
                f"report loaded {parity['loaded']} + excluded {parity['excluded']}"
            )
        states[code] = {
            "parity": parity,
            "catalog": catalog_for_frame(state_frame),
        }

    totals = {
        "universe": int(sum(s["catalog"]["universe"] for s in states.values())),
        "compared": int(sum(s["parity"]["compared"] for s in states.values())),
        "matched": int(sum(s["parity"]["matched"] for s in states.values())),
        "excluded": int(sum(s["parity"]["excluded"] for s in states.values())),
        "stage_cells": int(
            sum(stage["n"] for s in states.values() for stage in s["parity"]["stages"])
        ),
        "divergent": int(sum(s["catalog"]["divergent"] for s in states.values())),
    }
    excluded_reasons: dict[str, int] = {}
    for state in states.values():
        for reason, count in state["parity"]["excluded_reasons"].items():
            excluded_reasons[reason] = excluded_reasons.get(reason, 0) + count
    totals["excluded_reasons"] = dict(sorted(excluded_reasons.items()))

    concordance = hurdle_results["target_concordance"]["fy2024"]
    national = {
        "n": int(concordance["n"]),
        "concordance_weighted": {
            "benfix": float(
                concordance["abs_RAWBEN_minus_BENFIX_equals_AMTERR_weighted"]
            ),
            "fsben": float(
                concordance["abs_RAWBEN_minus_FSBEN_equals_AMTERR_weighted"]
            ),
        },
    }

    return {
        "schema": SCHEMA,
        "conventions": (
            "Stage parity re-derives the committed axiom-oracles comparison "
            "reports; the divergence catalog partitions FSBEN != BENFIX cases "
            "by fields the public file records (ALLADJ, AMTERR, SSI_CAP, "
            "FSMINBEN). Accounting conventions, not causal attributions."
        ),
        "provenance": {
            "oracle_repo": ORACLE_REPO,
            "oracle_commit": ORACLE_COMMIT,
            "suite_reports": report_hashes,
            "qc_archive_pin": archive_pin,
            "qc_csv_sha256": qc_csv_sha256,
            "certified_toolchain": CERTIFIED_TOOLCHAIN,
            "national_concordance_source": "analysis/hurdle_results.json",
        },
        "national": national,
        "totals": totals,
        "states": states,
    }


def app_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    """Project the compact payload the browser loads.

    Weighted shares round to six decimals; counts pass through.  The
    projection is pure so the committed app payload is testable against
    the committed analysis artifact.
    """

    def round6(value: float) -> float:
        return round(value, 6)

    states = {}
    for code, state in artifact["states"].items():
        parity = state["parity"]
        catalog = state["catalog"]
        classes = {}
        for name, block in catalog["classes"].items():
            projected = {
                "n": block["n"],
                "weighted_share": round6(block["weighted_share_of_universe"]),
                "within_rounding_band_n": block["within_rounding_band_n"],
            }
            if name == "allotment_adjustment":
                projected["prorated_n"] = block["prorated_n"]
                projected["no_error_n"] = block["no_error_n"]
            if name == "recorded_correct_nonformula":
                projected["ssi_cap_coded_n"] = block["ssi_cap_coded_n"]
                projected["minimum_benefit_n"] = block["minimum_benefit_n"]
            classes[name] = projected
        states[code] = {
            "loaded": parity["loaded"],
            "excluded": parity["excluded"],
            "excluded_reasons": parity["excluded_reasons"],
            "compared": parity["compared"],
            "matched": parity["matched"],
            "stages": [
                {"label": stage["label"], "n": stage["n"], "matched": stage["matched"]}
                for stage in parity["stages"]
            ],
            "catalog": {
                "universe": catalog["universe"],
                "divergent": catalog["divergent"],
                "divergent_weighted_share": round6(catalog["divergent_weighted_share"]),
                "concordance_weighted": {
                    "benfix": round6(catalog["concordance_weighted"]["benfix"]),
                    "fsben": round6(catalog["concordance_weighted"]["fsben"]),
                },
                "classes": classes,
            },
        }
    provenance = artifact["provenance"]
    return {
        "schema": artifact["schema"],
        "provenance": {
            "oracle_repo": provenance["oracle_repo"],
            "oracle_commit": provenance["oracle_commit"],
            "qc_archive_sha256": provenance["qc_archive_pin"]["sha256"],
            "certified_toolchain": provenance["certified_toolchain"],
        },
        "national": {
            "n": artifact["national"]["n"],
            "concordance_weighted": {
                "benfix": round6(
                    artifact["national"]["concordance_weighted"]["benfix"]
                ),
                "fsben": round6(artifact["national"]["concordance_weighted"]["fsben"]),
            },
        },
        "totals": artifact["totals"],
        "states": states,
    }


def render_report(artifact: dict[str, Any]) -> str:
    """Render the human-readable companion document."""
    totals = artifact["totals"]
    national = artifact["national"]
    provenance = artifact["provenance"]
    lines = [
        "# Axiom rules-engine comparison",
        "",
        (
            "Generated by `analysis/engine_comparison.py`. Do not edit "
            "reported numbers by hand. This artifact backs the simulator's "
            "engine mode; every number that mode displays traces here or to "
            "the committed suite reports under `paper/snapshot/oracle-suites/`."
        ),
        "",
        "## Stage parity (committed axiom-oracles suite reports)",
        "",
        (
            f"Across the seven verified states the suites compare "
            f"{totals['compared']:,} of {totals['universe']:,} official-universe "
            f"FY2024 cases and match all {totals['matched']:,} at every one of "
            f"six recorded stages ({totals['stage_cells']:,} stage cells) at "
            f"zero tolerance. The {totals['excluded']:,} excluded cases are "
            "enumerated program-structure classes: "
            + ", ".join(
                f"`{reason}` {count}"
                for reason, count in totals["excluded_reasons"].items()
            )
            + " (SSI-CAP standardized-benefit units use a separate benefit "
            "procedure; NYSCAP follows the regular chain and is in scope)."
        ),
        "",
        "| State | Universe | Compared | Matched | Excluded | Stages exact |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for code, state in artifact["states"].items():
        parity = state["parity"]
        catalog = state["catalog"]
        lines.append(
            f"| {code} | {catalog['universe']} | {parity['compared']} | "
            f"{parity['matched']} | {parity['excluded']} | "
            f"{len(parity['stages'])}/6 |"
        )
    lines.extend(
        [
            "",
            (
                "Stage concepts are pinned per state in the suite reports "
                "(Colorado exposes `snap_total_gross_income`/`snap_allotment`; "
                "other states bind their own composition surfaces). The QC "
                "comparison bridge supplies QC-adjudicated deductions, utility "
                "amounts, and eligibility findings as inputs, so parity "
                "certifies the downstream benefit arithmetic given those "
                "intermediates (fact catalog C2)."
            ),
            "",
            "## Formula-benefit divergence catalog",
            "",
            (
                "`|RAWBEN - BENFIX|` equals the recorded error amount for every "
                "official-universe case in the seven states (asserted at "
                "build), and nationally for "
                f"{100 * national['concordance_weighted']['benfix']:.3f}% of "
                f"weighted FY2024 cases (n={national['n']:,}). The Minimodel's "
                "formula benefit taken as the deviation anchor — "
                "`|RAWBEN - FSBEN|` — matches the recorded error for only "
                f"{100 * national['concordance_weighted']['fsben']:.2f}% "
                "weighted, because the formula recomputation conflates "
                "recorded allotment adjustments with error. The catalog "
                "partitions each state's `FSBEN != BENFIX` cases three ways:"
            ),
            "",
            (
                "1. **Coded allotment adjustment** — `ALLADJ` records a "
                "prorated (2) or other (3) adjustment; the recorded allotment "
                "is not the full-month formula amount by design."
            ),
            (
                "2. **Error-correction arithmetic** — no coded adjustment and "
                "`AMTERR > 0`: the reviewer's corrected allotment differs from "
                "the full recomputation (about two-thirds within $2, "
                "rounding-scale)."
            ),
            (
                "3. **Recorded-correct nonformula issuance** — no coded "
                "adjustment, no recorded error, and the issued allotment "
                "(`RAWBEN == BENFIX`, asserted) still differs from the "
                "formula; includes coded SSI-CAP standardized benefits and "
                "minimum-benefit cases."
            ),
            "",
            (
                "| State | Divergent | Weighted share | Adjustment (prorated) | "
                "Error arithmetic (≤$2) | Recorded-correct (SSI-CAP) |"
            ),
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for code, state in artifact["states"].items():
        catalog = state["catalog"]
        classes = catalog["classes"]
        adjustment = classes["allotment_adjustment"]
        correction = classes["error_correction_arithmetic"]
        nonformula = classes["recorded_correct_nonformula"]
        lines.append(
            f"| {code} | {catalog['divergent']}/{catalog['universe']} | "
            f"{100 * catalog['divergent_weighted_share']:.1f}% | "
            f"{adjustment['n']} ({adjustment['prorated_n']}) | "
            f"{correction['n']} ({correction['within_rounding_band_n']}) | "
            f"{nonformula['n']} ({nonformula['ssi_cap_coded_n']}) |"
        )
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            (
                f"Suite reports: `{provenance['oracle_repo']}` @ "
                f"`{provenance['oracle_commit'][:12]}`, copied byte-identically "
                "with SHA-256 pins recorded in `engine_comparison.json`. QC "
                "source archive pin "
                f"`{provenance['qc_archive_pin']['sha256'][:12]}…`; extracted "
                f"CSV `{provenance['qc_csv_sha256'][:12]}…` (certification "
                "report pin). Certified toolchain (Colorado probe): engine "
                f"`{provenance['certified_toolchain']['engine_commit'][:12]}` × "
                "rulespec-us "
                f"`{provenance['certified_toolchain']['rulespec_us_commit'][:12]}`."
            ),
            "",
            (
                "National concordance is quoted from the committed "
                "`analysis/hurdle_results.json` (fact catalog B3). All shares "
                "use `HWGT` case weights. These are accounting conventions "
                "recorded in the public file, not causal attributions."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Build and write the three engine-comparison outputs."""
    qc_csv = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_QC_CSV
    if len(sys.argv) > 2:
        raise SystemExit("usage: python analysis/engine_comparison.py [QC_CSV]")
    reports = {}
    report_hashes = {}
    for code in VERIFIED_STATES:
        path = SNAPSHOT_DIR / f"axiom-snapqc-{code.lower()}-snap.json"
        reports[code] = load_report(path)
        report_hashes[path.name] = sha256_of(path)
    with HURDLE_RESULTS_PATH.open(encoding="utf-8") as handle:
        hurdle_results = json.load(handle)
    artifact = build_artifact(
        reports,
        load_universe(qc_csv),
        hurdle_results,
        report_hashes,
        sha256_of(qc_csv),
    )
    with ANALYSIS_OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=1, sort_keys=False)
        handle.write("\n")
    payload = app_payload(artifact)
    APP_OUTPUT.write_text(
        json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(render_report(artifact), encoding="utf-8", newline="\n")
    print(f"wrote {ANALYSIS_OUTPUT}")
    print(f"wrote {APP_OUTPUT} sha256={sha256_of(APP_OUTPUT)}")
    print(f"wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
