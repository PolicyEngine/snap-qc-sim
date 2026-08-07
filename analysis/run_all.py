"""Regenerate every v2 analysis artifact from one deterministic entry point.

Run from the repository root with::

    uv run --frozen --extra analysis python analysis/run_all.py

All model scripts and the app-data builder finish into a staging directory
before any checked-in artifact is replaced. This keeps the Markdown, JSON,
and browser export on the same successful run if fitting or rendering fails.
"""

from __future__ import annotations

import json
import os
import sys
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

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts_build_model_data

if __package__:
    from . import (
        distributional_deviation_model,
        hurdle_deviation_model,
        train_error_model,
    )
else:
    import distributional_deviation_model
    import hurdle_deviation_model
    import train_error_model


ANALYSIS_DIR = Path(__file__).resolve().parent
MODEL_RESULTS = ANALYSIS_DIR / "model_results.json"
HURDLE_RESULTS = ANALYSIS_DIR / "hurdle_results.json"
DISTRIBUTIONAL_RESULTS = ANALYSIS_DIR / "distributional_results.json"
FINDINGS = ANALYSIS_DIR / "FINDINGS.md"
MODEL_DATA = REPO_ROOT / "app" / "public" / "model_data.json"


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


def _render_distributional_findings(
    distributional: Mapping[str, Any],
) -> list[str]:
    sign = distributional["sign"]
    magnitude = distributional["magnitude_distribution"]
    coverage = magnitude["fy2024_weighted_coverage"]
    crossing = distributional["crossing_validation"]
    simulation = distributional["measured_rate_simulation"]
    export = distributional["export"]
    tail = magnitude["tail_fit"]
    lines = [
        "## Distributional deviation process",
        "",
        (
            "The distributional model predicts the FY2024 SNAP QC error process "
            "from FY2017–19 and FY2022–23 records. It does not identify causal "
            "effects. Among cases with `|D| > $0.50`, it estimates `P(D > 0)`, "
            "nine conditional quantiles of `log(|D|)`, and a log-scale "
            "exponential tail beyond q99. Sign and magnitude are conditionally "
            "independent given the model features."
        ),
        "",
        (
            f"The tail scale is {_metric(tail['scale_log'], 4)} log dollars. "
            f"The fit uses {_integer(tail['n'])} top-decile OOF residual "
            f"exceedances (effective n {_metric(tail['effective_n'], 1)})."
        ),
        "",
        (
            "Native HistGB quantile loss retains the hurdle's feature set, NaN "
            "routing, and HWGT support without adding another dependency."
        ),
        "",
        "Sign probabilities use HWGT and the same nested outer/inner OOF isotonic calibration as the hurdle stages.",
        "",
        "| sign model/sample | raw AUC | calibrated AUC | raw PR-AUC | calibrated PR-AUC | raw Brier | calibrated Brier | raw calibration-in-the-large | calibrated calibration-in-the-large |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        _probability_row(
            "Training deviators, nested OOF",
            sign["training_oof_cross_fitted"],
        ),
        _probability_row(
            "FY2024 deviators",
            sign["fy2024_among_deviators"],
        ),
        "",
        "### Weighted FY2024 quantile coverage",
        "",
        (
            "Coverage uses FY2024 deviators and HWGT. A flag marks an absolute "
            "difference from nominal coverage greater than 3 percentage points."
        ),
        "",
        "| quantile | weighted coverage | difference | >3pp flag |",
        "|---:|---:|---:|:---:|",
    ]
    for row in coverage:
        lines.append(
            f"| {_number(row['quantile'], context='quantile'):.3f} | "
            f"{_pct(row['weighted_coverage'])} | "
            f"{_signed(row['gap_pp'], 2, 'pp')} | "
            f"{'Yes' if row['flag_over_3pp'] else 'No'} |"
        )

    lines.extend(
        [
            "",
            "### Threshold-crossing validation",
            "",
            (
                "The observed FY2024 official-error prevalence is "
                f"{_metric(crossing['observed_official_national_prevalence_pct'], 4, '%')}. "
                "Literal `|D| > $56` prevalence is "
                f"{_metric(crossing['observed_literal_D_crossing_national_prevalence_pct'], 4, '%')}. "
                f"{_integer(crossing['official_vs_literal_discordant_n'])} "
                "reconciliation-anomaly case separates the two definitions."
            ),
            "",
            "| route | specification | national predicted prevalence | equal-state MAE | issuance-weighted MAE |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in crossing["comparison_rows"]:
        lines.append(
            f"| {row['route']} | {row['specification']} | "
            f"{_metric(row['national_predicted_prevalence_pct'], 3, '%')} | "
            f"{_metric(row['equal_state_mae_pp'], 3, 'pp')} | "
            f"{_metric(row['issuance_weighted_mae_pp'], 3, 'pp')} |"
        )
    differences = crossing["primary_distributional_minus_direct_mae_pp"]
    equal_difference = _number(
        differences["equal_state"], context="equal-state MAE difference"
    )
    issuance_difference = _number(
        differences["issuance_weighted"],
        context="issuance-weighted MAE difference",
    )
    equal_direction = "higher (worse)" if equal_difference > 0 else "lower (better)"
    issuance_direction = (
        "higher (worse)" if issuance_difference > 0 else "lower (better)"
    )
    rows_by_key = {
        (row["route"], row["specification"]): row for row in crossing["comparison_rows"]
    }
    frozen_specification = "frozen model through FY2022, unfactored"
    factored_specification = "frozen model through FY2022, FY2023-fit factor adjusted"
    frozen_direct = rows_by_key[("direct stage-2", frozen_specification)]
    frozen_distributional = rows_by_key[
        ("distributional implied crossing", frozen_specification)
    ]
    differences_by_specification = crossing[
        "distributional_minus_direct_mae_pp_by_specification"
    ]
    frozen_difference = differences_by_specification[frozen_specification]
    factored_difference = differences_by_specification[factored_specification]
    lines.extend(
        [
            "",
            (
                "For the primary unfactored FY2024 comparison, the distributional "
                f"route's equal-state MAE is {abs(equal_difference):.3f}pp "
                f"{equal_direction} than the direct model, and its "
                f"issuance-weighted MAE is {abs(issuance_difference):.3f}pp "
                f"{issuance_direction}."
            ),
            "",
            (
                "The frozen, unfactored distributional route is materially worse "
                "on issuance-weighted state MAE: "
                f"{_metric(frozen_distributional['issuance_weighted_mae_pp'], 3, 'pp')} "
                "versus "
                f"{_metric(frozen_direct['issuance_weighted_mae_pp'], 3, 'pp')} "
                f"for the direct route ({_signed(frozen_difference['issuance_weighted'], 3, 'pp')}). "
                "Its equal-state difference is "
                f"{_signed(frozen_difference['equal_state'], 3, 'pp')}. After "
                "FY2023-fit factors, the distributional route remains higher by "
                f"{_metric(factored_difference['equal_state'], 3, 'pp')} "
                "equal-state and "
                f"{_metric(factored_difference['issuance_weighted'], 3, 'pp')} "
                "issuance-weighted."
            ),
            "",
            "### Model process versus observed bootstrap",
            "",
            (
                f"Each row uses {int(simulation['draws']):,} draws. The model "
                "draws one signed deviation for every fixed FY2024 CASE == 1 "
                "record. The observed comparator uniformly bootstraps corrected "
                "case errors. Both retain HWGT inside the measured-rate ratio and "
                "apply the official-rate level adjustment from `simulate.py`."
            ),
            "",
            "| state | official | model mean | model SD | observed-bootstrap mean | observed-bootstrap SD |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in simulation["rows"]:
        lines.append(
            f"| {row['state']} | {_metric(row['official_rate_pct'], 3, '%')} | "
            f"{_metric(row['model']['mean_pct'], 3, '%')} | "
            f"{_metric(row['model']['sd_pp'], 3, 'pp')} | "
            f"{_metric(row['observed_bootstrap']['mean_pct'], 3, '%')} | "
            f"{_metric(row['observed_bootstrap']['sd_pp'], 3, 'pp')} |"
        )
    quantization = export.get("q_decimal_quantization")
    quantization_text = (
        f" Quantile logs use {int(quantization)} decimal places because the "
        "four-significant-figure draft exceeded 2.5 MB."
        if quantization is not None
        else " Quantile logs retain four significant figures."
    )
    lines.extend(
        [
            "",
            (
                "The self-contained FY2024 browser export contains "
                f"{_integer(export['fy2024_cases'])} CASE == 1 records across "
                f"{_integer(export['state_count'])} jurisdictions. Its final size "
                f"is {_metric(export['model_data_raw_bytes'] / 1_000_000, 2)} MB "
                "raw and "
                f"{_metric(export['model_data_gzip_bytes'] / 1_000_000, 2)} MB "
                f"under deterministic gzip.{quantization_text}"
            ),
            "",
        ]
    )
    return lines


def render_findings(
    model_results: Mapping[str, Any],
    hurdle_results: Mapping[str, Any],
    distributional_results: Mapping[str, Any],
) -> str:
    """Render prose only from the three just-produced JSON payloads."""
    lines = [
        "# Corrected v2 diagnostic results",
        "",
        (
            "This file is generated by `analysis/run_all.py` from "
            "`model_results.json`, `hurdle_results.json`, and "
            "`distributional_results.json`. Do not edit reported numbers by hand."
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
    lines.extend(_render_distributional_findings(distributional_results))
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            (
                "These are diagnostic and descriptive results. FY2024 informed "
                "pipeline development across the audit-and-correct rounds and is "
                "not a pristine holdout. This repository implements and exports a "
                "signed conditional deviation process; the live simulator's "
                "model-based mode consumes that export but is disabled in "
                "production pending adversarial-review fixes (tail refit, state "
                "factors, dollar-rate validation). The headline factor-validation "
                "row (0.885pp equal-state MAE) belongs to the frozen expected-"
                "dollar hurdle route, not the unfactored distributional export "
                "the app consumes. Not yet implemented: a computation-failure "
                "mixture, an input-noise tier, an event-study design, and engine "
                "recomputation under alternative policies. "
                "See `docs/v2-error-model.md` for the implementation-status table."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Run every analysis and export, then replace all outputs together."""
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
        staged_distributional = staging / DISTRIBUTIONAL_RESULTS.name
        staged_findings = staging / FINDINGS.name
        staged_model_data = staging / MODEL_DATA.name
        hurdle_deviation_model.main(staged_hurdle)
        distributional_artifacts = distributional_deviation_model.main(
            staged_distributional
        )
        export_report = scripts_build_model_data.build_model_data(
            distributional_artifacts.predictions,
            tail_scale=distributional_artifacts.bundle.tail.scale,
            output_path=staged_model_data,
            metadata_path=MODEL_DATA.with_name("data.json"),
            threshold=distributional_deviation_model.THRESHOLD[
                distributional_deviation_model.YEAR_TEST
            ],
            deviation_tolerance=(distributional_deviation_model.DEVIATION_TOLERANCE),
            quantile_levels=distributional_deviation_model.QUANTILE_LEVELS,
            quantile_columns=distributional_deviation_model.QUANTILE_COLUMNS,
        )
        distributional_artifacts.result["export"].update(
            {
                "model_data_raw_bytes": export_report["raw_bytes"],
                "model_data_gzip_bytes": export_report["gzip_bytes"],
                "q_decimal_quantization": export_report["q_decimal_quantization"],
            }
        )
        distributional_deviation_model._write_result(
            distributional_artifacts.result,
            staged_distributional,
        )

        model_payload = _read_json(staged_model)
        hurdle_payload = _read_json(staged_hurdle)
        distributional_payload = _read_json(staged_distributional)
        report = render_findings(
            model_payload,
            hurdle_payload,
            distributional_payload,
        )
        staged_findings.write_text(report, encoding="utf-8", newline="\n")

        for staged, destination in (
            (staged_model, MODEL_RESULTS),
            (staged_hurdle, HURDLE_RESULTS),
            (staged_distributional, DISTRIBUTIONAL_RESULTS),
            (staged_findings, FINDINGS),
            (staged_model_data, MODEL_DATA),
        ):
            os.replace(staged, destination)

    print(f"wrote {MODEL_RESULTS}")
    print(f"wrote {HURDLE_RESULTS}")
    print(f"wrote {DISTRIBUTIONAL_RESULTS}")
    print(f"wrote {FINDINGS}")
    print(f"wrote {MODEL_DATA}")


if __name__ == "__main__":
    main()
