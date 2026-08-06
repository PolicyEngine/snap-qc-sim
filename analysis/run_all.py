"""Regenerate every v2 analysis artifact from one deterministic entry point.

Run from the repository root with::

    uv run --frozen --extra analysis python analysis/run_all.py

Both model scripts finish into a staging directory before any checked-in
artifact is replaced.  This keeps ``FINDINGS.md`` and the two JSON files on
the same successful run if model fitting or report rendering fails.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

# Make repeated fits stable across machines with different default thread
# counts.  These must be set before importing numpy/scikit-learn transitively.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

if __package__:
    from . import hurdle_deviation_model, train_error_model
else:
    import hurdle_deviation_model
    import train_error_model


ANALYSIS_DIR = Path(__file__).resolve().parent
MODEL_RESULTS = ANALYSIS_DIR / "model_results.json"
HURDLE_RESULTS = ANALYSIS_DIR / "hurdle_results.json"
FINDINGS = ANALYSIS_DIR / "FINDINGS.md"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise TypeError(f"{path.name} must contain a JSON object")
    return payload


def _number(value: Any, *, context: str) -> float:
    if not isinstance(value, (int, float)):
        raise TypeError(f"{context} must be numeric, got {type(value).__name__}")
    return float(value)


def _pct(value: Any, digits: int = 2) -> str:
    return f"{100 * _number(value, context='rate'):.{digits}f}%"


def _signed(value: Any, digits: int = 4, suffix: str = "") -> str:
    return f"{_number(value, context='signed statistic'):+.{digits}f}{suffix}"


def _metric(value: Any, digits: int = 4, suffix: str = "") -> str:
    return f"{_number(value, context='metric'):.{digits}f}{suffix}"


def _integer(value: Any) -> str:
    return f"{int(_number(value, context='count')):,}"


def _years(values: list[int]) -> str:
    return ", ".join(f"FY{int(value)}" for value in values)


def _medical_cell(cell: Mapping[str, Any]) -> str:
    return (
        f"{_pct(cell['rate'])} "
        f"({_integer(cell['event_count'])} events / {_integer(cell['n'])} cases)"
    )


def _probability_row(label: str, metrics: Mapping[str, Any]) -> str:
    return (
        f"| {label} | {_metric(metrics['auc_raw'])} | "
        f"{_metric(metrics['auc_calibrated'])} | "
        f"{_metric(metrics['pr_auc_raw'])} | "
        f"{_metric(metrics['pr_auc_calibrated'])} | "
        f"{_metric(metrics['weighted_brier_raw'])} | "
        f"{_metric(metrics['weighted_brier_calibrated'])} | "
        f"{_signed(metrics['calibration_in_the_large_raw'])} | "
        f"{_signed(metrics['calibration_in_the_large_calibrated'])} |"
    )


def _calibration_row(label: str, metrics: Mapping[str, Any]) -> str:
    correlation = _number(metrics["corr"], context="calibration correlation")
    return (
        f"| {label} | {_metric(metrics['slope'], 3)} | "
        f"{_signed(metrics['intercept_pp'], 3, 'pp')} | "
        f"{_metric(metrics['mae_pp'], 3, 'pp')} | "
        f"{_metric(metrics['rmse_pp'], 3, 'pp')} | "
        f"{correlation:.3f} | {correlation**2:.3f} |"
    )


def _render_classifier_findings(model: Mapping[str, Any]) -> list[str]:
    prevalence = model["prevalence"]
    train_prevalence = prevalence["train"]
    test_prevalence = prevalence["test"]
    models = model["models"]
    baseline = models["covariates_only"]
    full = models["with_intermediates"]
    lift = models["lift"]
    auc_lift = _number(lift["roc_auc"], context="AUC lift")
    pr_lift = _number(lift["pr_auc"], context="PR-AUC lift")
    interpretation = (
        "The burden intermediates change FY2024 discrimination by "
        f"{auc_lift:+.4f} ROC AUC and {pr_lift:+.4f} PR-AUC. These are "
        "predictive evaluation-sample differences, not mechanism estimates."
    )

    lines = [
        "## Official-error classifier",
        "",
        (
            f"The training sample contains {_integer(model['train_n'])} CASE == 1 "
            "records from FY2017–19 and FY2022–23. Its official-error prevalence "
            f"is {_pct(train_prevalence['weighted'])} weighted and "
            f"{_pct(train_prevalence['unweighted'])} unweighted. The FY2024 "
            f"evaluation sample contains {_integer(model['test_n'])} records, with "
            f"prevalence {_pct(test_prevalence['weighted'])} weighted and "
            f"{_pct(test_prevalence['unweighted'])} unweighted."
        ),
        "",
        "| FY2024 specification | weighted ROC AUC | weighted PR-AUC | precision at 5% weighted review budget |",
        "|---|---:|---:|---:|",
        (
            f"| Covariates + formula anchor | {_metric(baseline['roc_auc'])} | "
            f"{_metric(baseline['pr_auc'])} | "
            f"{_pct(baseline['precision_at_5pct_weight_budget'])} |"
        ),
        (
            f"| Baseline + burden intermediates | {_metric(full['roc_auc'])} | "
            f"{_metric(full['pr_auc'])} | "
            f"{_pct(full['precision_at_5pct_weight_budget'])} |"
        ),
        (
            f"| Difference | {_signed(auc_lift)} | {_signed(pr_lift)} | "
            f"{_signed(100 * _number(lift['precision_at_5pct_weight_budget'], context='precision lift'), 2, 'pp')} |"
        ),
        "",
        interpretation,
        "",
    ]

    importance = model["permutation_importance_weighted_roc_auc"]
    ranked = sorted(
        importance.items(),
        key=lambda item: _number(
            item[1]["mean_auc_decrease"], context="permutation importance"
        ),
        reverse=True,
    )[:8]
    lines.extend(
        [
            (
                "The largest FY2024 weighted ROC-AUC permutation importances are "
                "shown below. They are predictive associations, not mechanism "
                "estimates."
            ),
            "",
            "| feature | mean ROC-AUC decrease | standard deviation |",
            "|---|---:|---:|",
        ]
    )
    lines.extend(
        f"| `{feature}` | {_signed(values['mean_auc_decrease'])} | "
        f"{_metric(values['std'])} |"
        for feature, values in ranked
    )
    lines.append("")
    return lines


def _render_medical_findings(model: Mapping[str, Any]) -> list[str]:
    cross_section = model["medical_cross_section"]
    contrasts = model["smd_adoption_contrasts"]
    lines = [
        "## Medical outcome and SMD contrasts",
        "",
        (
            "A medical event requires the official-error label and a payment-impact "
            "finding paired in the same public-file slot: `ELEMENTi == 365`, "
            "`E_FINDGi` in `{2, 3, 4}`, and `AMOUNTi > 0`, scanning slots 1–9."
        ),
        "",
        "Cross-sectional weighted medical-event rates:",
        "",
        "| denominator | `med_doc_required=0` | `med_doc_required=1` |",
        "|---|---:|---:|",
    ]
    for label, key in (
        ("Post-treatment-conditioned medical claimants", "claimant_conditioned"),
        ("All elderly/disabled households", "all_elderly_disabled"),
    ):
        cells = cross_section[key]
        lines.append(
            f"| {label} | {_medical_cell(cells['0'])} | {_medical_cell(cells['1'])} |"
        )
    lines.extend(
        [
            "",
            f"Known proxy limitation: {cross_section['limitations']}.",
            "",
            f"Claimant denominator warning: {contrasts['claimant_conditioning_note']}",
            "",
            (
                "The following are descriptive weighted contrasts, not causal "
                "estimates. Each adopter and its never-treated controls use the "
                "same listed calendar cells. Event counts are unweighted; rates use "
                "QC household weights."
            ),
            "",
        ]
    )

    for population_label, population_key in (
        (
            "Post-treatment-conditioned medical claimants",
            "claimant_conditioned",
        ),
        ("Stable denominator: all elderly/disabled", "all_elderly_disabled"),
    ):
        lines.extend(
            [
                f"### {population_label}",
                "",
                "| adopter | adoption | pre cells | post cells | adopter pre | adopter post | controls pre | controls post | contrast |",
                "|---|---:|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        states = contrasts["populations"][population_key]
        for state, result in sorted(states.items()):
            lines.append(
                f"| {state} | FY{int(result['adoption_year'])} | "
                f"{_years(result['pre_years'])} | {_years(result['post_years'])} | "
                f"{_medical_cell(result['state_pre'])} | "
                f"{_medical_cell(result['state_post'])} | "
                f"{_medical_cell(result['control_pre'])} | "
                f"{_medical_cell(result['control_post'])} | "
                f"{_signed(result['descriptive_contrast_pp'], 2, 'pp')} |"
            )
        if not states:
            lines.append(
                "| _No eligible within-window adopters_ | — | — | — | — | — | — | — | — |"
            )
        lines.append("")
    return lines


def _render_hurdle_findings(hurdle: Mapping[str, Any]) -> list[str]:
    train_prevalence = hurdle["prevalence"]["training_through_fy2023"]
    test_prevalence = hurdle["prevalence"]["fy2024"]
    stage1_oof = hurdle["stage1"]["training_oof_cross_fitted"]
    stage1_test = hurdle["stage1"]["fy2024"]
    stage2_oof = hurdle["stage2"]["training_oof_cross_fitted"]
    stage2_test = hurdle["stage2"]["fy2024_among_stage1_positives"]
    stage3 = hurdle["stage3"]
    magnitude = stage3["fy2024"]
    concordance = hurdle["target_concordance"]["fy2024"]
    calibration = hurdle["calibration"]
    headline = calibration["headline_fy2024_unfactored"]
    factor_validation = calibration["fy2023_fit_factor_validation"]

    lines = [
        "## Diagnostic hurdle",
        "",
        (
            "The signed deviation is `D = RAWBEN - BENFIX`; `FSBEN` remains only "
            "the engine-computable `formula_benefit` feature. Stage 1 is "
            "`|D| > $0.50`. Stage 2 is fit and evaluated only among those stage-1 "
            "positives; rare official errors with `|D| <= $0.50` retain their "
            "diagnostic label but are outside the stage-2 and magnitude fits."
        ),
        "",
        (
            "Training weighted/unweighted prevalence is "
            f"{_pct(train_prevalence['deviates']['weighted'])}/"
            f"{_pct(train_prevalence['deviates']['unweighted'])} for stage 1 and "
            f"{_pct(train_prevalence['official_error']['weighted'])}/"
            f"{_pct(train_prevalence['official_error']['unweighted'])} for the "
            "official-error label. FY2024 weighted/unweighted prevalence is "
            f"{_pct(test_prevalence['deviates']['weighted'])}/"
            f"{_pct(test_prevalence['deviates']['unweighted'])} and "
            f"{_pct(test_prevalence['official_error']['weighted'])}/"
            f"{_pct(test_prevalence['official_error']['unweighted'])}, respectively."
        ),
        "",
        "Probability metrics use QC weights. The OOF rows are cross-fitted training estimates; FY2024 is the evaluation year.",
        "",
        "| probability stage/sample | raw AUC | calibrated AUC | raw PR-AUC | calibrated PR-AUC | raw Brier | calibrated Brier | raw calibration-in-the-large | calibrated calibration-in-the-large |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        _probability_row("Stage 1, training OOF", stage1_oof),
        _probability_row("Stage 1, FY2024", stage1_test),
        _probability_row("Stage 2, training OOF", stage2_oof),
        _probability_row("Stage 2, FY2024 among stage-1 positives", stage2_test),
        "",
        (
            f"Stage 3 uses weighted OOF Duan smearing ({_metric(stage3['smear'], 3)}; "
            f"n={_integer(stage3['oof_n'])}). In FY2024 official-error cases, "
            f"weighted observed `|D|` averages ${_metric(magnitude['observed_abs_D_mean_weighted'], 2)} "
            f"and predicted magnitude averages ${_metric(magnitude['predicted_abs_D_mean_weighted'], 2)}. "
            f"The weighted observed signed mean is ${_signed(magnitude['observed_signed_D_mean_weighted'], 2)}."
        ),
        "",
        (
            "FY2024 target concordance supports the target choice: "
            f"`|RAWBEN-BENFIX| == AMTERR` for {_pct(concordance['abs_RAWBEN_minus_BENFIX_equals_AMTERR_weighted'], 5)} "
            "weighted cases, versus "
            f"{_pct(concordance['abs_RAWBEN_minus_FSBEN_equals_AMTERR_weighted'], 5)} "
            "for the formula-benefit difference."
        ),
        "",
        "### State-rate calibration",
        "",
        (
            "Headline calibration is unfactored FY2024. Correlation squared is "
            "reported as a descriptive cross-jurisdiction summary, not a mechanism "
            "or causal decomposition."
        ),
        "",
        "| FY2024 weighting | slope | intercept | MAE | RMSE | correlation | correlation squared |",
        "|---|---:|---:|---:|---:|---:|---:|",
        _calibration_row("Equal jurisdiction", headline["equal_jurisdiction"]),
        _calibration_row("Issuance weighted", headline["issuance_weighted"]),
        "",
        (
            "The validated factor path trains the model through FY2022, estimates "
            "effective-sample-size precision-shrunken factors from out-of-sample "
            "FY2023 state ratios, freezes them, and applies them to FY2024."
        ),
        "",
        "| FY2024 factor validation | slope | intercept | MAE | RMSE | correlation | correlation squared |",
        "|---|---:|---:|---:|---:|---:|---:|",
        _calibration_row(
            "Frozen model, unfactored, equal jurisdiction",
            factor_validation["fy2024_unfactored_frozen_model"]["equal_jurisdiction"],
        ),
        _calibration_row(
            "FY2023-fit factors, equal jurisdiction",
            factor_validation["fy2024_factor_adjusted"]["equal_jurisdiction"],
        ),
        _calibration_row(
            "Frozen model, unfactored, issuance weighted",
            factor_validation["fy2024_unfactored_frozen_model"]["issuance_weighted"],
        ),
        _calibration_row(
            "FY2023-fit factors, issuance weighted",
            factor_validation["fy2024_factor_adjusted"]["issuance_weighted"],
        ),
        "",
        (
            "Any factor computed from FY2024 in the state records is a descriptive "
            "anchor only. State residuals are unidentified combinations of model "
            "error, omitted state/policy features, sampling noise, and possibly "
            "administration; this analysis does not assign them to a mechanism."
        ),
        "",
    ]
    return lines


def render_findings(
    model_results: Mapping[str, Any], hurdle_results: Mapping[str, Any]
) -> str:
    """Render prose only from the two just-produced JSON payloads."""
    lines = [
        "# Corrected v2 diagnostic results",
        "",
        (
            "This file is generated by `analysis/run_all.py` from "
            "`model_results.json` and `hurdle_results.json`. Do not edit reported "
            "numbers by hand."
        ),
        "",
        (
            "The analysis covers FY2017–19 and FY2022–24, excludes pandemic years "
            "FY2020–21, and filters every source to the official `CASE == 1` universe. "
            "The diagnostic label is `STATUS in {2, 3}` and `AMTERR` greater than "
            "the fiscal-year threshold."
        ),
        "",
    ]
    lines.extend(_render_classifier_findings(model_results))
    lines.extend(_render_medical_findings(model_results))
    lines.extend(_render_hurdle_findings(hurdle_results))
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            (
                "These are diagnostic and descriptive results. This repository does "
                "not yet implement a signed conditional distribution, assigned-benefit "
                "draws, a computation-failure mixture, an input-noise tier, an "
                "event-study design, or model integration with the live simulator. "
                "See `docs/v2-error-model.md` for the implementation-status table."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Run both analyses, render findings, then replace all outputs together."""
    with TemporaryDirectory(prefix=".run-all-", dir=ANALYSIS_DIR) as directory:
        staging = Path(directory)

        # train_error_model predates the path-taking entry point. Redirecting its
        # output directory lets us stage without weakening its standalone command.
        original_classifier_out = train_error_model.OUT
        train_error_model.OUT = staging
        try:
            train_error_model.main()
        finally:
            train_error_model.OUT = original_classifier_out

        staged_model = staging / MODEL_RESULTS.name
        staged_hurdle = staging / HURDLE_RESULTS.name
        staged_findings = staging / FINDINGS.name
        hurdle_deviation_model.main(staged_hurdle)

        model_payload = _read_json(staged_model)
        hurdle_payload = _read_json(staged_hurdle)
        report = render_findings(model_payload, hurdle_payload)
        staged_findings.write_text(report, encoding="utf-8", newline="\n")

        for staged, destination in (
            (staged_model, MODEL_RESULTS),
            (staged_hurdle, HURDLE_RESULTS),
            (staged_findings, FINDINGS),
        ):
            os.replace(staged, destination)

    print(f"wrote {MODEL_RESULTS}")
    print(f"wrote {HURDLE_RESULTS}")
    print(f"wrote {FINDINGS}")


if __name__ == "__main__":
    main()
