"""Estimate the protocol-frozen fixed-donor UHIP decomposition."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyreadstat

from analysis import event_study, uhip_decomposition

PROTOCOL_PATH = Path(__file__).with_name("FIXED_DONOR_PROTOCOL.md")
DECOMPOSITION_PROTOCOL_PATH = Path(__file__).with_name("UHIP_DECOMPOSITION_PROTOCOL.md")
PARENT_RESULTS_PATH = Path(__file__).with_name("riky_event_study_results.json")
JOINT_RESULTS_PATH = Path(__file__).with_name("uhip_decomposition_results.json")
OUT = Path(__file__).with_name("fixed_donor_decomposition_results.json")
MEMO_OUT = Path(__file__).with_name("FIXED_DONOR.md")
PROTOCOL_SHA256 = "80dad3c0a3fb7400edc1720b02eaf3e8dd861fc1ea73a478c965595040a13ae7"
DECOMPOSITION_PROTOCOL_SHA256 = (
    "ffbf63b17a9241e55952e86aed5e0cead8b51133fc123e620de3a59f5f3ee57c"
)
SCHEMA = "snap_qc_sim.fixed_donor_decomposition.v1"
PARENT_FIT_OUTCOMES = event_study.OUTCOMES
ANALYSIS_OUTCOMES = uhip_decomposition.FITTED_CHANNELS + (
    uhip_decomposition.CLIENT_OUTCOME,
)
EXPECTED_CLIENT = {
    "effect": 3.9642021849522484,
    "p_value": 0.23255813953488372,
    "absolute_rank": 10,
    "rank_denominator": 43,
}


def raw_inputs_available() -> bool:
    return uhip_decomposition.raw_inputs_available()


def build_panel() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Merge the imported parent and decomposition panel builders."""
    channels, descriptive = uhip_decomposition.build_panel()
    parent = event_study.build_riky_panel()
    return parent.merge(
        channels, on=["state", "year"], validate="one_to_one"
    ), descriptive


def _apply_weights(
    panel: pd.DataFrame,
    treated: str,
    weights: dict[str, float],
    pre_years: list[int],
    post_years: list[int],
) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    for name in ANALYSIS_OUTCOMES:
        wide = event_study._wide(panel, name)
        synthetic = wide[list(weights)] @ pd.Series(weights)
        gap = wide[treated] - synthetic
        outcomes[name] = {
            "effect": float(gap.loc[post_years].mean() - gap.loc[pre_years].mean()),
            "pre_rmspe": float(np.sqrt(np.mean(np.square(gap.loc[pre_years])))),
            "path": [
                {
                    "year": int(year),
                    "event_time": int(year - 2016),
                    "treated": float(wide.loc[year, treated]),
                    "synthetic_donor": float(synthetic.loc[year]),
                    "gap": float(gap.loc[year]),
                }
                for year in event_study.RIKY_YEARS
            ],
        }
    return {"donor_weights": weights, "outcomes": outcomes}


def estimate_fixed(
    panel: pd.DataFrame,
    treated: str,
    donors: list[str],
    pre_years: list[int],
    post_years: list[int],
) -> dict[str, Any]:
    """Fit once on the parent's outcomes, then apply the weights unchanged."""
    weights = event_study.fit_weights(
        panel, treated, donors, pre_years, outcomes=PARENT_FIT_OUTCOMES
    )
    return _apply_weights(panel, treated, weights, pre_years, post_years)


def permutation_inference_fixed(
    panel: pd.DataFrame,
    treated_result: dict[str, Any],
    donors: list[str],
    pre_years: list[int],
    post_years: list[int],
) -> dict[str, Any]:
    """Run placebos with one parent-outcome fit per pseudo-treated donor."""
    placebo_effects = {name: {} for name in ANALYSIS_OUTCOMES}
    placebo_weights: dict[str, dict[str, float]] = {}
    for pseudo_treated in donors:
        pseudo_donors = [state for state in donors if state != pseudo_treated]
        estimate = estimate_fixed(
            panel, pseudo_treated, pseudo_donors, pre_years, post_years
        )
        placebo_weights[pseudo_treated] = estimate["donor_weights"]
        for name in ANALYSIS_OUTCOMES:
            placebo_effects[name][pseudo_treated] = estimate["outcomes"][name]["effect"]
    inference = {
        name: event_study._rank_in_space(
            treated_result["outcomes"][name]["effect"], placebo_effects[name]
        )
        for name in ANALYSIS_OUTCOMES
    }
    return {"outcomes": inference, "placebo_donor_weights": placebo_weights}


def _reproduction_check(client: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "effect": bool(
            np.isclose(client["effect"], EXPECTED_CLIENT["effect"], rtol=1e-9, atol=0)
        ),
        "p_value": client["p_value"] == EXPECTED_CLIENT["p_value"],
        "absolute_rank": client["absolute_rank"] == EXPECTED_CLIENT["absolute_rank"],
        "rank_denominator": client["rank_denominator"]
        == EXPECTED_CLIENT["rank_denominator"],
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "expected": EXPECTED_CLIENT,
        "observed": {key: client[key] for key in EXPECTED_CLIENT},
        "effect_relative_tolerance": 1e-9,
        "diagnosis_if_failed": (
            None
            if all(checks.values())
            else "The fixed fit path did not reproduce the committed parent; this is an estimator implementation bug, not a finding."
        ),
    }


def _channel_table(
    source: dict[str, Any], client_p: float, *, fixed: bool
) -> dict[str, Any]:
    table: dict[str, Any] = {}
    for name in uhip_decomposition.CHANNEL_CODES:
        if name == "recert":
            table[name] = {
                "effect": 0.0,
                "p_value": None,
                "absolute_rank": None,
                "rank_denominator": None,
                "verdict": None,
                "verdict_family_adjusted": None,
                "profile": None,
                "status": "observed_zero_no_fit",
            }
            continue
        if fixed:
            outcome = source["primary_specification"]["outcomes"][name]
            inference = (
                source["permutation_inference"][name]
                if name in uhip_decomposition.INFERENTIAL_CHANNELS
                else {}
            )
        elif name in uhip_decomposition.INFERENTIAL_CHANNELS:
            outcome = source["inferential_channels"][name]
            inference = outcome
        else:
            outcome = source["descriptive_channels"][name]
            inference = {}
        inferential = name in uhip_decomposition.INFERENTIAL_CHANNELS
        p_value = inference.get("p_value")
        table[name] = {
            "effect": outcome["effect"],
            "p_value": p_value,
            "absolute_rank": inference.get("absolute_rank"),
            "rank_denominator": inference.get("rank_denominator"),
            "verdict": (
                "signal"
                if inferential and p_value < 0.10 and client_p >= 0.10
                else "no_protocol_defined_signal"
                if inferential
                else None
            ),
            "verdict_family_adjusted": (
                "signal_family_adjusted"
                if inferential and p_value < 0.10 / 3
                else "no_family_adjusted_signal"
                if inferential
                else None
            ),
            "profile": uhip_decomposition._profile(outcome),
            "status": "inferential" if inferential else "descriptive_only",
        }
    return table


def build_results(
    panel: pd.DataFrame, descriptive: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the fixed-donor artifact and imported joint-fit comparison."""
    descriptive = descriptive or {}
    donors = event_study.riky_donor_pool(panel)
    years = event_study.RIKY_PRIMARY_YEARS
    primary = estimate_fixed(
        panel, "RI", donors, years["pre_years"], years["post_years"]
    )
    permutation = permutation_inference_fixed(
        panel, primary, donors, years["pre_years"], years["post_years"]
    )
    inference = {
        name: permutation["outcomes"][name]
        for name in uhip_decomposition.INFERENTIAL_CHANNELS
        + (uhip_decomposition.CLIENT_OUTCOME,)
    }
    client = {
        **primary["outcomes"][uhip_decomposition.CLIENT_OUTCOME],
        **inference[uhip_decomposition.CLIENT_OUTCOME],
    }
    joint = json.loads(JOINT_RESULTS_PATH.read_text())
    reproduction = _reproduction_check(client)
    fixed_source = {
        "primary_specification": primary,
        "permutation_inference": inference,
    }
    hashes = {
        "fixed_donor_protocol": event_study._sha256(PROTOCOL_PATH),
        "decomposition_protocol": event_study._sha256(DECOMPOSITION_PROTOCOL_PATH),
        "parent_results": event_study._sha256(PARENT_RESULTS_PATH),
        "joint_fit_results": event_study._sha256(JOINT_RESULTS_PATH),
        "coding_consistency": event_study._sha256(event_study.AUDIT_PATH),
        "cause_shares": event_study._sha256(event_study.CAUSE_PATH),
        "system_migrations": event_study._sha256(event_study.MIGRATION_PATH),
        "raw_by_fiscal_year": {
            str(year): event_study._sha256(event_study._riky_source_path(year))
            for year in event_study.RIKY_YEARS
        }
        if raw_inputs_available()
        else {},
    }
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "protocol_sha256": hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest(),
        "decomposition_protocol_sha256": hashlib.sha256(
            DECOMPOSITION_PROTOCOL_PATH.read_bytes()
        ).hexdigest(),
        "reproduction_check": reproduction,
        "scope": {
            "treated_state": "RI",
            "panel_years": list(event_study.RIKY_YEARS),
            "donor_pool": donors,
            "inferential_channels": list(uhip_decomposition.INFERENTIAL_CHANNELS),
            "descriptive_channels": list(uhip_decomposition.DESCRIPTIVE_CHANNELS),
            "parent_fit_outcomes": list(PARENT_FIT_OUTCOMES),
        },
        "primary_specification": {
            **primary,
            "pre_years": years["pre_years"],
            "post_years": years["post_years"],
        },
        "permutation_inference": inference,
        "placebo_donor_weights": permutation["placebo_donor_weights"],
        "client_placebo": client,
        "side_by_side": {
            "joint_fit": _channel_table(
                joint, joint["client_placebo"]["p_value"], fixed=False
            ),
            "fixed_donor": _channel_table(fixed_source, client["p_value"], fixed=True),
        },
        **descriptive,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyreadstat": pyreadstat.__version__,
            "byteorder": sys.byteorder,
        },
        "input_hashes": hashes,
    }


def serialize_results(payload: dict[str, Any]) -> bytes:
    return event_study.serialize_results(payload)


def render_memo(payload: dict[str, Any]) -> str:
    check = payload["reproduction_check"]
    lines = [
        "# Fixed-donor UHIP decomposition",
        "",
        "## Reproduction check",
        "",
        f"**{'PASS' if check['passed'] else 'FAIL'}** — fixed-donor client effect {check['observed']['effect']:.15g}, p {check['observed']['p_value']:.15g}, rank {check['observed']['absolute_rank']} of {check['observed']['rank_denominator']}.",
        "",
        "## Side-by-side results",
        "",
        "| Channel | Estimator | Effect | p-value | Rank | Parent verdict | Family-adjusted verdict | Consequence minus later |",
        "|---|---|---:|---:|---:|---|---|---:|",
    ]
    for name in uhip_decomposition.CHANNEL_CODES:
        for estimator in ("joint_fit", "fixed_donor"):
            value = payload["side_by_side"][estimator][name]
            p = "—" if value["p_value"] is None else f"{value['p_value']:.6f}"
            rank = (
                "—"
                if value["absolute_rank"] is None
                else f"{value['absolute_rank']}/{value['rank_denominator']}"
            )
            profile = value["profile"]
            consequence = (
                "—" if profile is None else f"{profile['consequence_minus_later']:.6f}"
            )
            lines.append(
                f"| {name} | {estimator} | {value['effect']:.6f} | {p} | {rank} | "
                f"{value['verdict'] or '—'} | {value['verdict_family_adjusted'] or '—'} | {consequence} |"
            )
    lines.extend(
        [
            "",
            "## Language",
            "",
            'Unchanged: bundled system replacement as implemented; channels describe how QC coding classified UHIP\'s failures. The fixed-donor result and the joint-fit result are two pre-specified estimators of the same estimand; neither is "the" answer, and the causal paper reports both with the reproduction check as the bridge.',
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    panel, descriptive = build_panel()
    payload = build_results(panel, descriptive)
    if not payload["reproduction_check"]["passed"]:
        raise RuntimeError(json.dumps(payload["reproduction_check"], indent=2))
    OUT.write_bytes(serialize_results(payload))
    MEMO_OUT.write_text(render_memo(payload))


if __name__ == "__main__":
    main()
