#!/usr/bin/env python3
"""Engine-grounded FY2024 SMD accounting counterfactual.

PolicyEngine imports remain inside ``build_artifact`` so the fast repository
tests can import this module without the provisioned rung-3 environment.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
QC_CSV = Path.home() / ".cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
TECHDOC = Path.home() / ".cache/axiom-oracles/snap-qc/FY-2024-Tech-Doc.pdf"
SMD_REGISTRY = (
    Path.home()
    / ".cache/axiom-oracles/snap_qc_repo/additional_data/standard_medical_deductions.csv"
)
PARITY_HARNESS = ROOT / "analysis/rung3/parity_harness.py"
FEATURE_BUILDER = ROOT / "analysis/train_error_model.py"
OUTPUT = ROOT / "analysis/smd_engine_counterfactual.json"
MEMO = ROOT / "analysis/SMD_ENGINE.md"

VERIFIED_STATES = {"AZ", "CA", "CO", "GA", "MD", "NY", "TX"}
SMD_PARAMETERS = {
    "AZ": {"gross_threshold": 180, "standard_deduction": 145},
    "CA": {"gross_threshold": 155, "standard_deduction": 120},
    "CO": {"gross_threshold": 200, "standard_deduction": 165},
    "GA": {"gross_threshold": 196, "standard_deduction": 161},
    "TX": {"gross_threshold": 170, "standard_deduction": 135},
}

TECHDOC_CITATIONS = {
    "smd_rule": {
        "source": "FY-2024-Tech-Doc.pdf",
        "page": 34,
        "lines": "19-32",
        "claim": "Eligible elderly/disabled units with gross medical expenses above $35 and at or below the state threshold receive threshold minus $35; above-threshold units use actual expenses minus $35.",
    },
    "smd_states": {
        "source": "FY-2024-Tech-Doc.pdf",
        "page": 23,
        "lines": "48-51",
        "claim": "The FY2024 SMD-state list includes AZ, CA, CO, GA, and TX but not MD or NY.",
    },
    "expense_field": {
        "source": "FY-2024-Tech-Doc.pdf",
        "page": 75,
        "lines": "11-14",
        "claim": "FSMEDEXP is the reported field for allowable medical expenses in excess of $35.",
    },
    "deduction_field": {
        "source": "FY-2024-Tech-Doc.pdf",
        "page": 74,
        "lines": "46-51",
        "claim": "FSMEDDED is the calculated medical deduction and equals nonnegative FSMEDEXP.",
    },
    "state_amounts": {
        "source": "FY-2024-Tech-Doc.pdf",
        "page": "F-5",
        "lines": "4-35",
        "claim": "The table supplies FY2024 thresholds and standard deductions and says above-threshold deductions equal actual expenses minus $35.",
    },
    "replacement_mechanism": {
        "source": "FY-2024-Tech-Doc.pdf",
        "page": 50,
        "lines": "40-51",
        "claim": "The minimodel replaces a positive expense at or below the SMD range with the standard amount.",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def citation_fields_nonempty(citation: dict[str, object]) -> bool:
    """Return whether a citation has usable source, page, lines, and claim."""
    return all(citation.get(key) not in (None, "") for key in ("source", "page", "lines", "claim"))


def _case_record(row: pd.Series, baseline: int, upper: int, lower: int) -> dict[str, object]:
    return {
        "case_id": row.case_id,
        "yrmonth": int(row.YRMONTH),
        "weight": float(row.HWGT),
        "recorded_medical_deduction": int(row.FSMEDDED),
        "expense_recoverability": "not_recoverable_standardized" if row.is_censored else "recoverable_actual_excess",
        "baseline_benefit": baseline,
        "convention_a_benefit": upper,
        "convention_a_delta": upper - baseline,
        "convention_b_benefit": lower,
        "convention_b_delta": lower - baseline,
    }


def _aggregate(group: pd.DataFrame, baseline_issuance: float, error_dollars: float) -> dict[str, object]:
    baseline_rate = 100 * error_dollars / baseline_issuance
    result: dict[str, object] = {
        "baseline": {
            "issuance_dollars": baseline_issuance,
            "error_dollars_held_fixed": error_dollars,
            "mechanical_measured_rate_pct": baseline_rate,
        }
    }
    for key, delta_column in (("convention_a", "delta_a"), ("convention_b", "delta_b")):
        issuance_delta = float((group.HWGT * group[delta_column]).sum())
        issuance = baseline_issuance + issuance_delta
        rate = 100 * error_dollars / issuance
        result[key] = {
            "issuance_change_dollars": issuance_delta,
            "counterfactual_issuance_dollars": issuance,
            "benefit_changed_cases": int(group[delta_column].ne(0).sum()),
            "mechanical_measured_rate_pct": rate,
            "mechanical_measured_rate_change_pp": rate - baseline_rate,
            "measurement_statement": "The HWGT-weighted AMTERR numerator is held fixed; only HWGT-weighted formula issuance moves.",
        }
    return result


def build_artifact() -> dict[str, object]:
    """Run the provisioned engine and return the deterministic artifact."""
    from analysis.rung3 import parity_harness

    started = time.perf_counter()
    all_cases = parity_harness.load_cases()
    registry = pd.read_csv(SMD_REGISTRY, encoding="utf-8-sig")
    registry_2024 = dict(zip(registry.state_name, registry["2024"], strict=True))
    state_names = {"AZ": "Arizona", "CA": "California", "CO": "Colorado", "GA": "Georgia", "MD": "Maryland", "NY": "New York", "TX": "Texas"}
    registry_amounts = {state: float(registry_2024[name]) for state, name in state_names.items()}
    derived_smd_states = {state for state, amount in registry_amounts.items() if amount > 0}
    if derived_smd_states != set(SMD_PARAMETERS):
        raise AssertionError(f"verified-state SMD registry drifted: {derived_smd_states}")

    claimant = all_cases.loc[
        all_cases.state.isin(SMD_PARAMETERS)
        & ((_num(all_cases.FSNELDER) + _num(all_cases.FSNDIS)) > 0)
        & _num(all_cases.FSMEDDED).gt(0)
    ].copy()
    claimant["is_censored"] = claimant.apply(
        lambda row: bool(
            int(row.MED_DED_DEMO) == 1
            and int(row.FSMEDDED) == SMD_PARAMETERS[row.state]["standard_deduction"]
        ),
        axis=1,
    )
    engine = parity_harness.engine_results(claimant, annualize_housing_cost=True)
    baseline = parity_harness.administrative_results(engine)
    if not baseline.admin_formula_benefit.astype(int).eq(baseline.FSBEN.astype(int)).all():
        raise AssertionError("administrative baseline lost certified parity")

    upper_input = engine.copy()
    lower_input = engine.copy()
    lower_input.loc[lower_input.is_censored, "medical_deduction"] = 0.0
    upper = parity_harness.administrative_results(upper_input)
    lower = parity_harness.administrative_results(lower_input)
    computed = baseline.copy()
    computed["baseline_benefit"] = baseline.admin_formula_benefit.astype(int)
    computed["benefit_a"] = upper.admin_formula_benefit.astype(int)
    computed["benefit_b"] = lower.admin_formula_benefit.astype(int)
    computed["delta_a"] = computed.benefit_a - computed.baseline_benefit
    computed["delta_b"] = computed.benefit_b - computed.baseline_benefit
    if (computed.delta_a > 0).any() or (computed.delta_b > 0).any():
        raise AssertionError("dropping a deduction unexpectedly raised a benefit")

    states: dict[str, object] = {}
    for state in sorted(VERIFIED_STATES):
        state_all = all_cases.loc[all_cases.state.eq(state)]
        issuance = float((state_all.HWGT * state_all.FSBEN).sum())
        error_dollars = float((state_all.HWGT * state_all.AMTERR).sum())
        if state not in SMD_PARAMETERS:
            states[state] = {
                "smd_operated_fy2024": False,
                "recoverability_verdict": "not_computed_no_smd_in_registry",
                "registry_amount": registry_amounts[state],
                "citations": [TECHDOC_CITATIONS["smd_states"]],
            }
            continue
        group = computed.loc[computed.state.eq(state)].copy()
        aggregate = _aggregate(group, issuance, error_dollars)
        states[state] = {
            "smd_operated_fy2024": True,
            "registry_amount": registry_amounts[state],
            "gross_expense_threshold": SMD_PARAMETERS[state]["gross_threshold"],
            "standard_deduction": SMD_PARAMETERS[state]["standard_deduction"],
            "claimant_cases": len(group),
            "standardized_unrecoverable_cases": int(group.is_censored.sum()),
            "actual_excess_recoverable_cases": int((~group.is_censored).sum()),
            "recoverability_verdict": "actual excess is recoverable only when the recorded amount is not the state standard; standardized actuals are censored",
            "bracket_definitions": {
                "convention_a": "For censored records, actual allowable expense above $35 equals the standard deduction; the deduction and benefit are unchanged.",
                "convention_b": "For censored records, gross allowable expense is $35 + epsilon; the above-floor deduction is approximated as $0. No point guess is made.",
            },
            "results": aggregate,
            "cases": [
                _case_record(row, int(row.baseline_benefit), int(row.benefit_a), int(row.benefit_b))
                for _, row in group.iterrows()
            ],
            "citations": [TECHDOC_CITATIONS[key] for key in ("smd_rule", "expense_field", "deduction_field", "state_amounts", "replacement_mechanism")],
        }

    runtime = time.perf_counter() - started
    return {
        "schema": "snap_qc_sim.smd_engine_counterfactual.v1",
        "schema_version": 1,
        "fiscal_year": 2024,
        "construction": "accounting",
        "causal": False,
        "recoverability": {
            "central_question": "For cases whose recorded deduction is the standard amount, are actual allowable expenses recoverable from the file?",
            "answer": "No. FSMEDEXP is the only reported medical-expense field, is on the above-$35 scale, and is replaced by the standard within the SMD range; no separate pre-replacement actual-expense field is documented.",
            "citations": list(TECHDOC_CITATIONS.values()),
            "repo_feature_sources": {
                "claims_medical": "analysis/train_error_model.py:777-782 (FSMEDEXP > 0)",
                "medical_expense_above_floor": "analysis/train_error_model.py:777-784 (FSMEDEXP > 35)",
                "med_doc_required": "analysis/train_error_model.py:529-555,784-789 (expense gate, elderly/disabled, SMD registry)",
                "smd_registry": "analysis/train_error_model.py:37,345-391; ~/.cache/axiom-oracles/snap_qc_repo/additional_data/standard_medical_deductions.csv",
                "bbce_not_used": "analysis/data/state_bbce.csv is the BBCE registry and does not identify SMD policy.",
            },
        },
        "verified_states": sorted(VERIFIED_STATES),
        "smd_verified_states": sorted(SMD_PARAMETERS),
        "states": states,
        "deployed_model_comparison": {
            "scope": "Colorado deployed statistical convention",
            "threshold_crossing_status_flip_cases": 53,
            "expected_crossing_rate_change_pp": -0.060,
            "expected_error_dollars_change_annual_approx": -2_000_000,
            "warning": "The model re-predicts adjudication behavior; this accounting bracket changes recorded formula inputs. Neither is causal and neither validates the other.",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "policyengine": importlib.metadata.version("policyengine"),
            "policyengine_us": importlib.metadata.version("policyengine-us"),
            "runtime_seconds": runtime,
            "command": "~/.cache/axiom-oracles/snap-fy27/rung3-env/bin/python analysis/smd_engine_counterfactual.py",
        },
        "input_hashes": {str(path): sha256(path) for path in (QC_CSV, TECHDOC, SMD_REGISTRY, PARITY_HARNESS, FEATURE_BUILDER)},
        "data_forced_choices": [
            "Only the five positive FY2024 SMD registry entries among the seven parity-verified states are computed.",
            "The claimant domain is elderly/disabled administrative-scope cases with FSMEDDED > 0.",
            "A record is censored only when MED_DED_DEMO == 1 and FSMEDDED equals the state's FY2024 standard; other positive values are treated as recoverable actual excess.",
            "Convention (b) represents $35 + epsilon gross expense as a $0 whole-dollar above-floor deduction.",
            "Recorded cost-neutrality utility adjustments, all nonmedical inputs, eligibility, case weights, and AMTERR are held fixed.",
        ],
    }


def _num(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0)


def render_memo(payload: dict[str, object]) -> str:
    rows = []
    for state in payload["verified_states"]:
        item = payload["states"][state]
        if not item["smd_operated_fy2024"]:
            rows.append(f"| {state} | No | — | — | — | — | — | Not computed |")
            continue
        a = item["results"]["convention_a"]
        b = item["results"]["convention_b"]
        rows.append(
            f"| {state} | Yes | {item['claimant_cases']} | {item['standardized_unrecoverable_cases']} | "
            f"${a['issuance_change_dollars']:,.0f} | ${b['issuance_change_dollars']:,.0f} | "
            f"{b['mechanical_measured_rate_change_pp']:+.4f} pp | {b['benefit_changed_cases']} |"
        )
    citations = payload["recoverability"]["citations"]
    cite_lines = "\n".join(
        f"- {entry['claim']} ({entry['source']}, p. {entry['page']}, lines {entry['lines']})."
        for entry in citations
    )
    runtime = payload["environment"]["runtime_seconds"]
    return f"""# SMD engine accounting counterfactual

## Recoverability verdict

No: for a case recorded at the state standard, actual allowable expenses are not recoverable. `FSMEDEXP` is the only documented reported medical-expense field, on the allowable-above-$35 scale, and the SMD process replaces values in the qualifying range with the standard. Values above the standard remain usable as actual excess expenses. The standardized class therefore receives a bracket, never a point guess.

The five SMD states among the seven parity-verified states are Arizona, California, Colorado, Georgia, and Texas. Maryland and New York are reported rather than computed because their FY2024 registry amounts are zero.

{cite_lines}

The repository feature lane reads `FSMEDEXP` to construct `claims_medical`, `medical_expense_above_floor`, and `med_doc_required`; the last also uses elderly/disabled status and the state-year SMD registry (`analysis/train_error_model.py:529-555, 777-789`). The SMD registry is `~/.cache/axiom-oracles/snap_qc_repo/additional_data/standard_medical_deductions.csv`; `analysis/data/state_bbce.csv` is a different, BBCE-only registry.

## Accounting bracket

Convention (a) sets censored actual allowable expense above $35 equal to the standard deduction, so its delta is zero. Convention (b) sets gross expense to $35 + epsilon, approximated as a $0 whole-dollar deduction. Uncensored above-standard expenses use their recorded actual excess in both conventions.

| State | SMD | Claimants | Censored | Issuance change (a) | Issuance change (b) | Rate change (b) | Changed cases (b) |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

The measured-rate effect is mechanical: each state's HWGT-weighted `AMTERR` numerator is held fixed while HWGT-weighted formula issuance changes. Recorded cost-neutrality utility adjustments, all other deductions and inputs, eligibility, and weights are also held fixed. Negative issuance deltas therefore raise the measured dollar-error rate even though error dollars do not change.

## Comparison with the deployed construction

| Construction | Scope | Crossing-rate result | Dollar result |
|---|---|---:|---:|
| Deployed fitted-error model | 53 Colorado cases whose threshold-crossing status flips | -0.060 pp expected crossing rate | approximately -$2 million/year expected error dollars |
| Formula accounting bracket | Recorded elderly/disabled medical-deduction claimants in five verified SMD states | Per-state mechanical measured-rate changes above; convention (a) is zero | Per-state issuance bracket above |

These are two accounting constructions of one lever; neither is causal. The formula construction asks how recorded-case benefit arithmetic changes when the standardized deduction is replaced under explicit recoverability bounds. The deployed statistical construction re-predicts adjudication behavior after changing a fitted documentation proxy. They answer different questions, and neither validates the other.

## Reproduction and disclosures

Run `{payload['environment']['command']}` for the artifact, then `uv run --frozen --extra dev --extra analysis pytest -q`, `uv run --frozen --extra dev --extra analysis ruff check .`, and `git diff --check`. The engine run took {runtime:.2f} seconds. The JSON records exact input hashes, versions, per-case deltas, every data-forced choice, and the complete bracket definitions.
"""


def write_outputs(payload: dict[str, object], output: Path = OUTPUT, memo: Path = MEMO) -> None:
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    memo.write_text(render_memo(payload), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--memo", type=Path, default=MEMO)
    args = parser.parse_args()
    payload = build_artifact()
    write_outputs(payload, args.output, args.memo)
    print(f"Wrote {args.output} and {args.memo}")


if __name__ == "__main__":
    main()
