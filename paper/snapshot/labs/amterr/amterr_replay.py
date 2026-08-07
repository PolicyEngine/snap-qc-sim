"""AMTERR replay: engine over reconstructed ORIGINAL inputs vs RAWBEN.

For each Colorado FY2024 error case (STATUS 2/3) whose pre-edit original
values the Giannella/Molin solver reconstructed (co_fy2024_reconstruction.csv),
build the case through the proven map_qc_unit — but from a proxy unit carrying
the ORIGINAL values — run the engine, and compare the allotment to RAWBEN
(the benefit the agency actually issued).

Interpretation:
  match  -> the issuance is explained by correct arithmetic on the original
            facts: an input/information error, faithfully propagated.
  miss   -> no plausible original value + correct math reproduces the
            issuance: computation-side error (or reconstruction failure —
            correctednotes/at_max separate those).

Run from the axiom-oracles worktree:
  uv run python /Users/maxghenis/.cache/axiom-oracles/amterr-lab/amterr_replay.py
with AXIOM_SNAP_QC_RULESPEC_ROOT / AXIOM_SNAP_QC_AXIOM_BINARY set.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

from axiom_oracles.bridges.snap_qc_compare import (
    _LABELS,
    NOMINAL_PERIOD,
    QC_JURISDICTIONS,
    _load_base_member,
    _output_id_by_label,
    _run_cases,
    map_qc_unit,
    sua_amounts_from_overlay,
)
from axiom_oracles.bridges.rulespec_overlay import build_overlay, load_overlay_spec
from axiom_oracles.bridges.snap_populace import (
    axiom_rules_env,
    load_base_inputs,
    month_period,
    output_to_python,
    resolve_axiom_binary,
    resolve_workspace_root,
)
from axiom_oracles.populations.snap_qc import load_qc_units

LAB = Path("/Users/maxghenis/.cache/axiom-oracles/amterr-lab")


def _num(v):
    v = (v or "").strip()
    if not v or v == ".":
        return None
    return float(v)


def load_reconstruction() -> dict[tuple[int, int], dict]:
    rows = {}
    with open(LAB / "co_fy2024_reconstruction.csv") as f:
        for row in csv.DictReader(f):
            key = (int(float(row["YRMONTH"])), int(float(row["HHLDNO"])))
            rows[key] = row
    return rows


def proxy_member(member) -> SimpleNamespace:
    return SimpleNamespace(
        index=member.index,
        age=member.age,
        elderly_or_disabled=member.elderly_or_disabled,
        social_security=0.0,
        ssi=0.0,
        tanf=0.0,
        general_assistance=0.0,
        child_support=0.0,
        alimony=0.0,
        earned_income=lambda: 0.0,
        unearned_income=lambda: 0.0,
    )


def proxy_unit(unit, rec: dict) -> SimpleNamespace:
    rawearn = _num(rec.get("rawearn")) or 0.0
    rawunearn = _num(rec.get("rawunearn")) or 0.0
    rawmedded = _num(rec.get("rawmedded")) or 0.0
    members = [proxy_member(m) for m in unit.members]
    return SimpleNamespace(
        case_id=unit.case_id,
        yrmonth=unit.yrmonth,
        certified_size=int(float(rec["rawusize"])),
        shelter_expense=_num(rec.get("rawrent")) or 0.0,
        utility_tier=unit.utility_tier,
        utility_amount=_num(rec.get("rawutil")),
        medical_expenses=rawmedded,
        dependent_care_expense=_num(rec.get("rawdepded")) or 0.0,
        child_support_expense=_num(rec.get("rawcsded")) or 0.0,
        categorically_eligible=unit.categorically_eligible,
        homeless_deduction_claimed=unit.homeless_deduction_claimed,
        liquid_resources=unit.liquid_resources,
        weight=unit.weight,
        members=members,
        unit_has_elderly_or_disabled=getattr(unit, "unit_has_elderly_or_disabled", None),
        expected=SimpleNamespace(
            benefit=_num(rec.get("RAWBEN")),
            medical_deduction=rawmedded if rawmedded > 0 else None,
        ),
        earned_income=lambda rawearn=rawearn: rawearn,
        unearned_income=lambda rawunearn=rawunearn: rawunearn,
    )


def main() -> None:
    config = QC_JURISDICTIONS["us-co"]
    workspace_root = resolve_workspace_root(None)
    rulespec_root = Path(os.environ["AXIOM_SNAP_QC_RULESPEC_ROOT"]).expanduser()
    binary = resolve_axiom_binary(
        workspace_root, Path(os.environ["AXIOM_SNAP_QC_AXIOM_BINARY"]).expanduser()
    )
    period = month_period(*NOMINAL_PERIOD)

    spec = load_overlay_spec(config.overlay)
    output_id_by_label = _output_id_by_label(config, spec.module_id_rewrites)
    benefit_label = next(label.label for label in _LABELS if label.is_benefit)
    benefit_output = output_id_by_label[benefit_label]

    units, _ = load_qc_units(2024, state_fips=config.state_fips)
    recon = load_reconstruction()

    matched_units = []
    for unit in units:
        raw = unit.raw
        key = (int(float(raw["YRMONTH"])), int(float(raw["HHLDNO"])))
        if key in recon:
            matched_units.append((unit, recon[key]))
    print(f"reconstruction rows: {len(recon)}; joined to loader units: {len(matched_units)}")

    base_inputs = load_base_inputs(rulespec_root / config.template)
    base_member = _load_base_member(rulespec_root / config.template, config.base.relation_id)

    overlay_dir = Path(tempfile.mkdtemp(prefix="snap-qc-amterr-"))
    try:
        build = build_overlay(spec, rulespec_root, overlay_dir)
        env = axiom_rules_env(build.program_path, workspace_root)
        env["AXIOM_RULESPEC_REPO_ROOTS"] = str(build.overlay_root)
        sua = sua_amounts_from_overlay(spec)
        cases = [
            map_qc_unit(proxy_unit(unit, rec), base_inputs, base_member, sua_amount_by_tier=sua)
            for unit, rec in matched_units
        ]
        results = _run_cases(
            binary=binary,
            program_path=build.program_path,
            cases=cases,
            period=period,
            output_ids=list(output_id_by_label.values()),
            config=config,
            env=env,
        )
    finally:
        shutil.rmtree(overlay_dir, ignore_errors=True)

    from axiom_oracles.bridges.snap_qc_compare import _axiom_value
    from axiom_oracles.bridges.snap_populace import outputs_by_reference

    summary = []
    for (unit, rec), result in zip(matched_units, results):
        references = outputs_by_reference(result.get("outputs", {}))
        engine_ben = _axiom_value(references, benefit_output)
        rawben = _num(rec.get("RAWBEN"))
        fsben = _num(rec.get("FSBEN"))
        amterr = _num(rec.get("AMTERR"))
        d = None if engine_ben is None or rawben is None else engine_ben - rawben
        summary.append({
            "case_id": unit.case_id,
            "yrmonth": rec["YRMONTH"],
            "hhldno": rec["HHLDNO"],
            "status": rec["STATUS"],
            "weight": unit.weight,
            "amterr": amterr,
            "rawben": rawben,
            "fsben": fsben,
            "engine_on_original": engine_ben,
            "diff": d,
            "exact": d is not None and abs(d) < 0.5,
            "within1": d is not None and abs(d) <= 1,
            "within5": d is not None and abs(d) <= 5,
            "rawben_recreated": _num(rec.get("rawben_recreated")),
            "solver_within5": (
                _num(rec.get("rawben_recreated")) is not None
                and rawben is not None
                and abs(_num(rec.get("rawben_recreated")) - rawben) <= 5
            ),
            "correctednotes": rec.get("correctednotes"),
            "at_max": rec.get("at_max"),
            "second_element": rec.get("second_element_i"),
            "element1": rec.get("ELEMENT1"),
            "nature1": rec.get("NATURE1"),
            "agency1": rec.get("AGENCY1"),
        })

    n = len(summary)
    for tol, key in [("exact", "exact"), ("<=$1", "within1"), ("<=$5", "within5")]:
        k = sum(1 for s in summary if s[key])
        print(f"engine(original) vs RAWBEN {tol}: {k}/{n} ({100*k/n:.1f}%)")
    solver_ok = sum(1 for s in summary if s["solver_within5"])
    both = sum(1 for s in summary if s["solver_within5"] and s["within5"])
    print(f"solver within $5: {solver_ok}/{n}; engine agrees (<=$5) on {both} of those")
    json.dump(summary, open(LAB / "amterr_replay_results.json", "w"), indent=1)
    print(f"wrote {LAB / 'amterr_replay_results.json'}")


if __name__ == "__main__":
    main()
