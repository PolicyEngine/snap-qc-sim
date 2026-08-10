"""Build the case-level policy-scenario export for the browser.

The sibling ``app/public/model_scenarios.json`` deliberately leaves
``model_data.json`` stable.  Its public schema is
``snap_qc_sim.model_scenarios.v1``:

* ``base_model`` binds the sibling to the exact ``model_data.json`` bytes and
  therefore to that file's state-local row order.
* ``states[STATE].levers[LEVER]`` reports the HWGT-weighted expected
  threshold-crossing-probability change and paired-bootstrap interval in the
  common ``adopted - not adopted`` direction, regardless of the state's FY2024
  policy.  It is not an official payment-error dollar-rate anchor shift.
* ``per_case`` is a sparse patch containing full, already-quantized ``p_dev``
  and nine log-dollar quantiles only for rows whose encoded model parameters
  change.  ``patch_endpoint`` says whether applying the patch to the baseline
  arrays constructs the adopted or not-adopted endpoint.  Full replacement
  values are smaller than duplicating every state array and avoid arithmetic
  drift from adding quantized deltas in JavaScript.
* ``source_payloads`` pins the canonical JSON content of the model diagnostics
  and Colorado reference consumed by the generator.

Only the standard medical deduction (SMD) is included.  It flips the exact
``med_doc_required`` predicate shared with ``analysis/counterfactual_join.py``.
The excluded lever definitions remain in the artifact with reasons so a
browser cannot silently fall back to accounting suppression.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis import (
    counterfactual_join,
    distributional_deviation_model,
    hurdle_deviation_model,
    train_error_model,
)
from analysis.predictive_process import conditional_survival
from scripts_build_model_data import _round_decimal, _round_significant

SCHEMA = "snap_qc_sim.model_scenarios.v1"
SCHEMA_VERSION = 1
FISCAL_YEAR = 2024
INCLUDED_LEVERS = ("smd",)
EXCLUDED_LEVERS = ("ssed", "heat_and_eat", "bbce_resources")
BOOTSTRAP_DRAWS = counterfactual_join.BOOTSTRAP_DRAWS
BOOTSTRAP_SEED = counterfactual_join.BOOTSTRAP_SEED
CONFIDENCE_LEVEL = counterfactual_join.CONFIDENCE_LEVEL
MAX_GZIP_BYTES = 1_500_000
LEVEL_RATIO_BOUNDS = (0.7, 1.4)
GATE_REASON = (
    "Factor-adjusted FY2024 model-to-observed dollar-rate ratio is outside "
    "the inclusive [0.7, 1.4] validation range."
)
DEFAULT_OUTPUT = Path("app/public/model_scenarios.json")
DEFAULT_DOCUMENT_OUTPUT = Path("analysis/MODEL_SCENARIOS.md")
DEFAULT_MODEL_DATA = Path("app/public/model_data.json")
DEFAULT_MODEL_RESULTS = Path("analysis/model_results.json")
DEFAULT_COUNTERFACTUAL = Path("analysis/counterfactual_co_smd.json")
QUANTILE_COLUMNS = distributional_deviation_model.QUANTILE_COLUMNS


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _read_json(path: Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _read_bound_model_data(
    path: Path,
    expected_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    """Read the SHA-bound baseline once and reject a divergent caller payload."""
    encoded = Path(path).read_bytes()
    try:
        payload = json.loads(encoded)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"{path} is not valid JSON") from error
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    if payload != expected_payload:
        raise ValueError(
            "model_data payload differs from the bytes bound by base_model.sha256"
        )
    return payload, _sha256_bytes(encoded)


def flip_smd_documentation_features(
    frame: pd.DataFrame,
    smd_states: set[str],
) -> pd.DataFrame:
    """Return FY2024 features with each state's SMD policy reversed.

    SMD policy on means the burden proxy is zero.  Policy off means the proxy
    is one only for elderly/disabled cases whose reported medical expense is
    strictly above $35.  The shared predicate is the bidirectional part of the
    Colorado join; its engine repricing is intentionally not generalized.
    """
    required = {
        "state",
        "medical_expense_above_floor",
        "elderly_or_disabled",
        "med_doc_required",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"SMD flip frame is missing columns: {missing}")
    if frame["state"].isna().any():
        raise ValueError("SMD flip frame contains a missing state")
    unknown = sorted(set(smd_states) - set(frame["state"]))
    if unknown:
        raise ValueError(
            f"SMD registry contains states absent from predictions: {unknown}"
        )

    current_policy = frame["state"].isin(smd_states)
    expected_current = train_error_model.medical_documentation_required(
        frame["medical_expense_above_floor"],
        frame["elderly_or_disabled"],
        current_policy,
    )
    observed = pd.to_numeric(frame["med_doc_required"], errors="coerce")
    if observed.isna().any() or not observed.eq(expected_current).all():
        states = sorted(frame.loc[~observed.eq(expected_current), "state"].unique())
        raise ValueError(
            "baseline med_doc_required does not match the FY2024 SMD registry "
            f"for states: {states}"
        )

    flipped = frame.copy()
    flipped["med_doc_required"] = train_error_model.medical_documentation_required(
        frame["medical_expense_above_floor"],
        frame["elderly_or_disabled"],
        ~current_policy,
    )
    return flipped


def _quantize_parameters(
    frame: pd.DataFrame,
    q_encoding: Mapping[str, Any],
) -> tuple[list[float], list[list[float]]]:
    p_dev = [_round_significant(value) for value in frame["p_dev"]]
    rounding = q_encoding.get("rounding")
    digits = q_encoding.get("digits")
    if not isinstance(digits, int) or digits <= 0:
        raise ValueError("model-data q_encoding digits must be a positive integer")
    quantiles = frame.loc[:, QUANTILE_COLUMNS].to_numpy(dtype=float)
    if rounding == "decimal_places":
        encoded_q = [
            [_round_decimal(value, digits) for value in row] for row in quantiles
        ]
    elif rounding == "significant_figures":
        encoded_q = [
            [_round_significant(value, digits=digits) for value in row]
            for row in quantiles
        ]
    else:
        raise ValueError(f"unsupported model-data q_encoding rounding: {rounding}")
    return p_dev, encoded_q


def _crossing_probability(
    p_dev: Sequence[float],
    quantiles: Sequence[Sequence[float]],
    caps: Sequence[float],
    *,
    threshold: float,
    tail_scale: float,
    deviation_tolerance: float,
) -> np.ndarray:
    probability = np.asarray(p_dev, dtype=float)
    q = np.asarray(quantiles, dtype=float)
    cap = np.asarray(caps, dtype=float)
    if q.shape != (len(probability), len(QUANTILE_COLUMNS)):
        raise ValueError("crossing quantiles must have nine columns per case")
    if cap.shape != probability.shape:
        raise ValueError("crossing caps must match p_dev")
    survival = conditional_survival(
        np.full(len(probability), float(threshold)),
        q,
        float(tail_scale),
        minimum_magnitude=float(deviation_tolerance),
    )
    # Capping above the threshold preserves the crossing event; a cap at or
    # below it makes a strict crossing impossible.
    return probability * survival * (cap > float(threshold))


def _extract_model_diagnostics(
    model_results: Mapping[str, Any],
) -> tuple[float, dict[str, dict[str, float]]]:
    try:
        models = model_results["models"]
        burden_lift = models.get("with_burden_intermediates")
        if burden_lift is None:
            auc_lift = float(models["lift"]["roc_auc"])
        else:
            auc_lift = float(
                burden_lift["roc_auc"] - models["covariates_only"]["roc_auc"]
            )
        populations = model_results["smd_adoption_contrasts"]["populations"]
        claimant = populations["claimant_conditioned"]
        stable = populations["all_elderly_disabled"]
        available_states = [
            state
            for state in ("AZ", "KY", "CA")
            if state in claimant and state in stable
        ]
        if not available_states:
            available_states = sorted(set(claimant) & set(stable))
        if not available_states:
            raise ValueError("no shared descriptive SMD contrasts")
        contrasts = {
            state: {
                "claimant_conditioned_pp": float(
                    claimant[state]["descriptive_contrast_pp"]
                ),
                "stable_all_elderly_disabled_pp": float(
                    stable[state]["descriptive_contrast_pp"]
                ),
            }
            for state in available_states
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("model_results lacks required AUC/SMD diagnostics") from error
    if not math.isfinite(auc_lift):
        raise ValueError("burden-intermediate AUC lift must be finite")
    return auc_lift, contrasts


def _co_reconciliation(
    states: Mapping[str, Any],
    counterfactual_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if "CO" not in states:
        return {"applicable": False}
    try:
        reference = counterfactual_payload["scenarios"]["ceiling"]
        direct = reference["direct_official_error_classifier"]
        direct_delta = float(direct["weighted_delta_pp"])
        direct_ci = [
            float(value) for value in direct["uncertainty"]["confidence_interval"]
        ]
        hurdle_delta = float(
            reference["hurdle_expected_error_dollars"][
                "hurdle_crossing_probability_delta_pp"
            ]
        )
        feature_changes = reference.get("feature_changes")
        if isinstance(feature_changes, Mapping):
            reference_flip_n = int(feature_changes["med_doc_required_0_to_1_cases"])
        else:
            reference_flip_n = int(
                counterfactual_payload["feature_construction"][
                    "documentation_flip_cases"
                ]
            )
        engine = reference["engine_accounting"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "counterfactual payload lacks the CO ceiling reference"
        ) from error
    engine_change_keys = (
        "benefit_changed_cases",
        "medical_deduction_changed_cases",
        "shelter_deduction_changed_cases",
        "net_income_changed_cases",
    )
    if any(int(engine[key]) != 0 for key in engine_change_keys):
        raise ValueError("CO ceiling reference is not a feature-only comparison")

    exported = states["CO"]["levers"]["smd"]
    adoption_delta = float(exported["delta_pp"])
    off_minus_on = -adoption_delta
    export_ci_off_minus_on = [
        -float(exported["ci_hi"]),
        -float(exported["ci_lo"]),
    ]
    mask_matches = int(exported["feature_flip_n"]) == reference_flip_n
    point_sign_matches = (
        np.sign(off_minus_on) == np.sign(direct_delta) == np.sign(hurdle_delta)
    )
    intervals_overlap = max(export_ci_off_minus_on[0], direct_ci[0]) <= min(
        export_ci_off_minus_on[1], direct_ci[1]
    )
    direct_point_in_export_ci = (
        export_ci_off_minus_on[0] <= direct_delta <= export_ci_off_minus_on[1]
    )
    return {
        "applicable": True,
        "reference_artifact": "analysis/counterfactual_co_smd.json",
        "reference_scenario": "ceiling",
        "reference_reason": (
            "ceiling changes the same documentation predicate for "
            f"{reference_flip_n} {'case' if reference_flip_n == 1 else 'cases'} "
            "and has zero engine benefit/deduction/net-income changes"
        ),
        "export_model": (
            "frozen-through-FY2022 distributional p_dev-times-tail-survival crossing"
        ),
        "reference_models": (
            "through-FY2023 primary direct classifier and calibrated hurdle"
        ),
        "feature_flip_n": int(exported["feature_flip_n"]),
        "reference_feature_flip_n": reference_flip_n,
        "reference_delta_direction": "not_adopted_minus_adopted",
        "export_delta_direction": "adopted_minus_not_adopted",
        "reference_delta_pp": direct_delta,
        "reference_adoption_delta_pp": _round_decimal(-direct_delta, 9),
        "export_delta_pp": adoption_delta,
        "difference_pp": _round_decimal(adoption_delta + direct_delta, 9),
        "exported_adopted_minus_not_adopted_pp": adoption_delta,
        "exported_not_adopted_minus_adopted_pp": _round_decimal(off_minus_on, 9),
        "exported_not_minus_adopted_ci": [
            _round_decimal(value, 9) for value in export_ci_off_minus_on
        ],
        "reference_direct_not_minus_adopted_pp": direct_delta,
        "reference_direct_not_minus_adopted_ci": direct_ci,
        "reference_hurdle_not_minus_adopted_pp": hurdle_delta,
        "difference_from_reference_direct_pp": _round_decimal(
            off_minus_on - direct_delta, 9
        ),
        "difference_from_reference_hurdle_pp": _round_decimal(
            off_minus_on - hurdle_delta, 9
        ),
        "feature_flip_count_matches": bool(mask_matches),
        "policy_direction_normalized": True,
        "point_sign_matches": bool(point_sign_matches),
        "exact_case_mask_verified": False,
        "conditional_intervals_overlap_direct": bool(intervals_overlap),
        "reference_direct_point_in_export_interval": bool(direct_point_in_export_ci),
        "reconciled": bool(
            mask_matches
            and point_sign_matches
            and intervals_overlap
            and direct_point_in_export_ci
        ),
        "interpretation": (
            "The estimates need not be equal because the shipped scenario uses a "
            "different frozen distributional estimand. Reconciliation requires "
            "the same documented predicate and flip count, adoption-normalized "
            "direction, concordant point signs, and overlapping conditional "
            "uncertainty. The reference artifact does not expose case IDs, so "
            "exact mask membership cannot be independently verified."
        ),
    }


def prepare_model_scenarios(
    baseline_predictions: pd.DataFrame,
    flipped_predictions: pd.DataFrame,
    *,
    model_data_payload: Mapping[str, Any],
    base_model_sha256: str,
    smd_states: set[str],
    model_results: Mapping[str, Any],
    counterfactual_payload: Mapping[str, Any],
    bootstrap_draws: int = BOOTSTRAP_DRAWS,
) -> dict[str, Any]:
    """Validate aligned predictions and prepare the deterministic scenario payload."""
    if bootstrap_draws <= 0:
        raise ValueError("bootstrap_draws must be positive")
    if not isinstance(baseline_predictions, pd.DataFrame) or not isinstance(
        flipped_predictions, pd.DataFrame
    ):
        raise TypeError("scenario predictions must be pandas DataFrames")
    if not baseline_predictions.index.equals(flipped_predictions.index):
        raise ValueError("baseline and flipped prediction indexes differ")
    required = {
        "state",
        "w",
        "issuance",
        "deviation_cap",
        "p_dev",
        "medical_expense_above_floor",
        "elderly_or_disabled",
        "med_doc_required",
        *QUANTILE_COLUMNS,
    }
    for name, frame in (
        ("baseline", baseline_predictions),
        ("flipped", flipped_predictions),
    ):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{name} scenario predictions are missing: {missing}")
    if not baseline_predictions["state"].equals(flipped_predictions["state"]):
        raise ValueError("baseline and flipped prediction states/order differ")
    for column in ("w", "issuance", "deviation_cap"):
        if not baseline_predictions[column].equals(flipped_predictions[column]):
            raise ValueError(f"baseline and flipped prediction {column} differs")

    model_states = model_data_payload.get("states")
    if not isinstance(model_states, Mapping) or not model_states:
        raise ValueError("model_data payload must contain states")
    prediction_states = set(baseline_predictions["state"])
    if prediction_states != set(model_states):
        raise ValueError("scenario prediction state set differs from model_data")
    if len(base_model_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in base_model_sha256
    ):
        raise ValueError("base_model_sha256 must be a lowercase SHA-256 digest")
    q_encoding = model_data_payload.get("q_encoding")
    if not isinstance(q_encoding, Mapping):
        raise TypeError("model_data q_encoding must be an object")
    threshold = float(model_data_payload["threshold"])
    tail_scale = float(model_data_payload["tail_scale_log"])
    deviation_tolerance = float(model_data_payload["deviation_tolerance"])
    gate_metadata = model_data_payload.get("level_ratio_gate")
    if not isinstance(gate_metadata, Mapping):
        raise TypeError("model_data level_ratio_gate must be an object")
    gate_bounds = tuple(float(value) for value in gate_metadata["inclusive_bounds"])
    if gate_bounds != LEVEL_RATIO_BOUNDS:
        raise ValueError("model_data level-ratio gate differs from [0.7, 1.4]")
    auc_lift, contrasts = _extract_model_diagnostics(model_results)

    state_payload: dict[str, Any] = {}
    for state in sorted(model_states):
        baseline = baseline_predictions.loc[baseline_predictions["state"].eq(state)]
        flipped = flipped_predictions.loc[flipped_predictions["state"].eq(state)]
        if not baseline.index.equals(flipped.index):
            raise ValueError(f"{state}: baseline/flipped row alignment differs")
        model_state = model_states[state]
        n = len(baseline)
        if int(model_state["n"]) != n:
            raise ValueError(f"{state}: prediction count differs from model_data")

        baseline_p, baseline_q = _quantize_parameters(baseline, q_encoding)
        flipped_p, flipped_q = _quantize_parameters(flipped, q_encoding)
        baseline_w = [_round_significant(value) for value in baseline["w"]]
        baseline_issuance = [
            _round_significant(value) for value in baseline["issuance"]
        ]
        baseline_cap = [round(value) for value in baseline["deviation_cap"]]
        if (
            baseline_w != model_state["w"]
            or baseline_issuance != model_state["iss"]
            or baseline_cap != model_state["cap"]
            or baseline_p != model_state["p_dev"]
            or baseline_q != model_state["q"]
        ):
            raise ValueError(
                f"{state}: encoded baseline row arrays differ from model_data"
            )
        level_ratio = float(model_state["level_ratio"])
        expected_level_flag = not gate_bounds[0] <= level_ratio <= gate_bounds[1]
        if bool(model_state["level_flag"]) != expected_level_flag:
            raise ValueError(f"{state}: model_data level flag is inconsistent")

        baseline_adopted = state in smd_states
        current_policy = pd.Series(baseline_adopted, index=baseline.index)
        opposite_policy = ~current_policy
        expected_baseline = train_error_model.medical_documentation_required(
            baseline["medical_expense_above_floor"],
            baseline["elderly_or_disabled"],
            current_policy,
        )
        expected_flipped = train_error_model.medical_documentation_required(
            baseline["medical_expense_above_floor"],
            baseline["elderly_or_disabled"],
            opposite_policy,
        )
        if not baseline["med_doc_required"].eq(expected_baseline).all():
            raise ValueError(f"{state}: baseline SMD feature direction is invalid")
        if not flipped["med_doc_required"].eq(expected_flipped).all():
            raise ValueError(f"{state}: flipped SMD feature direction is invalid")
        feature_flip = expected_baseline.ne(expected_flipped).to_numpy()

        current_cross = _crossing_probability(
            baseline_p,
            baseline_q,
            model_state["cap"],
            threshold=threshold,
            tail_scale=tail_scale,
            deviation_tolerance=deviation_tolerance,
        )
        flipped_cross = _crossing_probability(
            flipped_p,
            flipped_q,
            model_state["cap"],
            threshold=threshold,
            tail_scale=tail_scale,
            deviation_tolerance=deviation_tolerance,
        )
        if baseline_adopted:
            adopted_cross = current_cross
            not_adopted_cross = flipped_cross
        else:
            adopted_cross = flipped_cross
            not_adopted_cross = current_cross
        case_delta_pp = 100 * (adopted_cross - not_adopted_cross)
        weights = pd.Series(np.asarray(model_state["w"], dtype=float))
        bootstrap, _ = counterfactual_join.paired_weighted_bootstrap(
            {"delta_pp": case_delta_pp},
            weights,
            draws=bootstrap_draws,
            seed=BOOTSTRAP_SEED,
        )
        uncertainty = bootstrap["delta_pp"]
        adopted_rate = 100 * float(np.average(adopted_cross, weights=weights))
        not_adopted_rate = 100 * float(np.average(not_adopted_cross, weights=weights))
        adopted_rate = _round_decimal(adopted_rate, 6)
        not_adopted_rate = _round_decimal(not_adopted_rate, 6)
        delta_pp = _round_decimal(adopted_rate - not_adopted_rate, 6)
        baseline_to_patch_delta_pp = _round_decimal(
            100 * float(np.average(flipped_cross - current_cross, weights=weights)),
            6,
        )
        ci_lo, ci_hi = [
            _round_decimal(value, 6) for value in uncertainty["confidence_interval"]
        ]

        parameter_change = np.asarray(baseline_p) != np.asarray(flipped_p)
        parameter_change |= np.any(
            np.asarray(baseline_q) != np.asarray(flipped_q), axis=1
        )
        if np.any(parameter_change & ~feature_flip):
            raise ValueError(f"{state}: parameters changed outside the SMD flip mask")
        indices = np.flatnonzero(parameter_change).tolist()
        per_case = {
            "patch_endpoint": ("not_adopted" if baseline_adopted else "adopted"),
            "i": indices,
            "p_dev": [flipped_p[index] for index in indices],
            "q": [flipped_q[index] for index in indices],
        }
        state_payload[state] = {
            "n": n,
            "level_ratio": float(model_state["level_ratio"]),
            "level_flag": bool(model_state["level_flag"]),
            "levers": {
                "smd": {
                    "baseline_adopted": baseline_adopted,
                    "policy_flip_direction": (
                        "adopted_to_not_adopted"
                        if baseline_adopted
                        else "not_adopted_to_adopted"
                    ),
                    "feature_flip_direction": (
                        "0_to_1" if baseline_adopted else "1_to_0"
                    ),
                    "feature_flip_n": int(feature_flip.sum()),
                    "parameter_patch_n": len(indices),
                    "not_adopted_crossing_rate_pct": not_adopted_rate,
                    "adopted_crossing_rate_pct": adopted_rate,
                    "metric": "expected_threshold_crossing_probability",
                    "weighting": "FY2024 QC household weight (HWGT)",
                    "unit": "percentage_points",
                    "delta_direction": "adopted_minus_not_adopted",
                    "delta_pp": delta_pp,
                    "baseline_to_patch_delta_pp": baseline_to_patch_delta_pp,
                    "ci_lo": ci_lo,
                    "ci_hi": ci_hi,
                    "per_case": per_case,
                }
            },
        }

    flagged_states = [
        state for state, record in state_payload.items() if record["level_flag"]
    ]
    spans_zero = sum(
        record["levers"]["smd"]["ci_lo"] <= 0 <= record["levers"]["smd"]["ci_hi"]
        for record in state_payload.values()
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts_build_model_scenarios.py",
        "fiscal_year": FISCAL_YEAR,
        "base_model": {
            "file": "model_data.json",
            "schema_version": int(model_data_payload["schema_version"]),
            "sha256": base_model_sha256,
            "q_encoding": dict(q_encoding),
            "alignment": (
                "state-local zero-based indexes into the exact base-model arrays"
            ),
        },
        "source_payloads": {
            "model_results": {
                "file": "analysis/model_results.json",
                "canonical_json_sha256": _canonical_json_sha256(model_results),
            },
            "co_smd_reference": {
                "file": "analysis/counterfactual_co_smd.json",
                "canonical_json_sha256": _canonical_json_sha256(counterfactual_payload),
            },
        },
        "included_levers": list(INCLUDED_LEVERS),
        "excluded_levers": list(EXCLUDED_LEVERS),
        "delta_direction": "adopted_minus_not_adopted",
        "per_case_encoding": {
            "kind": "sparse_full_flipped_parameters",
            "i": "zero-based index into the state's model_data arrays",
            "p_dev": "full flipped calibrated deviation probability",
            "q": (
                "full flipped nine-quantile natural-log-dollar vector, using "
                "base-model quantization"
            ),
            "patch_endpoint": (
                "policy endpoint produced by applying replacements to model_data"
            ),
            "unchanged_rows": "retain model_data parameters",
        },
        "crossing": {
            "definition": (
                "p_dev times conditional P(abs(D) strictly above threshold) "
                "from the quantile interpolation and q99 log-tail"
            ),
            "threshold_dollars": threshold,
            "tail_scale_log": tail_scale,
            "deviation_tolerance_dollars": deviation_tolerance,
            "physical_cap_applied": True,
            "state_factor_applied": False,
            "state_factor_reason": (
                "the frozen factor scales expected error dollars, not case "
                "crossing probabilities"
            ),
            "browser_use": (
                "scenario crossing-probability display only; do not use delta_pp "
                "as an official payment-error dollar-rate anchor shift"
            ),
        },
        "uncertainty": {
            "method": (
                "paired nonparametric iid bootstrap of FY2024 QC cases; sample "
                "rows with replacement, retain encoded HWGT inside each weighted "
                "mean, and use percentile intervals"
            ),
            "draws": bootstrap_draws,
            "seed": BOOTSTRAP_SEED,
            "confidence_level": CONFIDENCE_LEVEL,
            "conditional_on_fitted_model": True,
        },
        "level_ratio_gate": {
            **dict(gate_metadata),
            "disabled_reason": GATE_REASON,
            "flagged_states": flagged_states,
        },
        "lever_definitions": {
            "smd": {
                "included": True,
                "label": "Standard medical deduction",
                "feature": "med_doc_required",
                "policy_on_feature_value": 0,
                "policy_off_feature_rule": ("FSMEDEXP > 35 and elderly_or_disabled"),
                "limitation": (
                    "proxy omits the state standard amount, whether it binds, "
                    "and documentation of actual expenses above the standard"
                ),
            },
            "ssed": {
                "included": False,
                "label": "Standard self-employment deduction",
                "reason": (
                    "se_records counts people with positive net self-employment "
                    "income; it is not an expense-documentation requirement"
                ),
            },
            "heat_and_eat": {
                "included": False,
                "label": "Heat-and-eat",
                "reason": (
                    "utility_actuals records observed SUA treatment and cannot "
                    "identify which cases adoption or repeal would move"
                ),
            },
            "bbce_resources": {
                "included": False,
                "label": "Broad-based categorical eligibility resources",
                "reason": "the fitted model has no asset-verification intermediate",
            },
        },
        "interpretation": {
            "causal": False,
            "statement": (
                "Deltas are model-implied associations from burden features that "
                "add only +0.006 ROC AUC; they are not causal policy effects."
            ),
            "burden_intermediate_roc_auc_lift": auc_lift,
            "burden_intermediate_roc_auc_lift_rounded_3": round(auc_lift, 3),
            "ci_spans_zero_states": spans_zero,
            "state_count": len(state_payload),
            "cis_typically_span_zero": spans_zero > len(state_payload) / 2,
            "descriptive_adoption_contrasts_are_calibration_reference": True,
            "descriptive_smd_adoption_contrasts_pp": contrasts,
        },
        "states": state_payload,
    }
    payload["validation"] = {
        "co_smd": _co_reconciliation(state_payload, counterfactual_payload)
    }
    validate_scenario_artifact(
        payload,
        model_data_payload=model_data_payload,
        base_model_sha256=base_model_sha256,
    )
    return payload


def _patched_parameters(
    model_state: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    p_dev = np.asarray(model_state["p_dev"], dtype=float).copy()
    quantiles = np.asarray(model_state["q"], dtype=float).copy()
    patch = scenario["per_case"]
    indices = np.asarray(patch["i"], dtype=int)
    if len(indices):
        p_dev[indices] = np.asarray(patch["p_dev"], dtype=float)
        quantiles[indices] = np.asarray(patch["q"], dtype=float)
    return p_dev, quantiles


def validate_scenario_artifact(
    payload: Mapping[str, Any],
    *,
    model_data_payload: Mapping[str, Any] | None = None,
    base_model_sha256: str | None = None,
) -> None:
    """Validate the public schema and, when supplied, its base-model patches."""
    required = {
        "schema",
        "schema_version",
        "fiscal_year",
        "base_model",
        "source_payloads",
        "included_levers",
        "excluded_levers",
        "delta_direction",
        "per_case_encoding",
        "crossing",
        "uncertainty",
        "level_ratio_gate",
        "lever_definitions",
        "interpretation",
        "validation",
        "states",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"scenario artifact is missing keys: {missing}")
    if payload["schema"] != SCHEMA or payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unexpected model-scenario schema")
    if payload["fiscal_year"] != FISCAL_YEAR:
        raise ValueError("model-scenario artifact has the wrong fiscal year")
    if payload["delta_direction"] != "adopted_minus_not_adopted":
        raise ValueError("scenario deltas must use adoption direction")
    source_payloads = payload["source_payloads"]
    for source in ("model_results", "co_smd_reference"):
        digest = source_payloads[source]["canonical_json_sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"scenario {source} payload digest is invalid")
    if tuple(payload["included_levers"]) != INCLUDED_LEVERS:
        raise ValueError("only SMD may be included")
    if tuple(payload["excluded_levers"]) != EXCLUDED_LEVERS:
        raise ValueError("scenario artifact has the wrong excluded levers")
    definitions = payload["lever_definitions"]
    if definitions["smd"].get("included") is not True or any(
        definitions[lever].get("included") is not False for lever in EXCLUDED_LEVERS
    ):
        raise ValueError("lever inclusion decisions are inconsistent")
    interpretation = payload["interpretation"]
    if interpretation.get("causal") is not False:
        raise ValueError("scenario artifact must explicitly reject causal inference")
    if round(float(interpretation["burden_intermediate_roc_auc_lift"]), 3) != 0.006:
        raise ValueError("scenario artifact must disclose the +0.006 AUC lift")
    uncertainty = payload["uncertainty"]
    if int(uncertainty["draws"]) <= 0 or int(uncertainty["seed"]) != BOOTSTRAP_SEED:
        raise ValueError("scenario bootstrap configuration is invalid")
    if uncertainty.get("conditional_on_fitted_model") is not True:
        raise ValueError("scenario uncertainty must be labeled fixed-fit conditional")

    states = payload["states"]
    if not isinstance(states, Mapping) or not states:
        raise ValueError("scenario artifact must contain states")
    flagged: list[str] = []
    for state, state_record in states.items():
        n = int(state_record["n"])
        if n <= 0:
            raise ValueError(f"{state}: n must be positive")
        if not isinstance(state_record["level_flag"], bool):
            raise TypeError(f"{state}: level_flag must be boolean")
        level_ratio = float(state_record["level_ratio"])
        if not math.isfinite(level_ratio) or level_ratio <= 0:
            raise ValueError(f"{state}: level_ratio must be finite and positive")
        if state_record["level_flag"]:
            flagged.append(state)
        scenario = state_record["levers"]["smd"]
        baseline_adopted = scenario["baseline_adopted"]
        if not isinstance(baseline_adopted, bool):
            raise TypeError(f"{state}: baseline_adopted must be boolean")
        expected_policy_direction = (
            "adopted_to_not_adopted" if baseline_adopted else "not_adopted_to_adopted"
        )
        expected_feature_direction = "0_to_1" if baseline_adopted else "1_to_0"
        expected_endpoint = "not_adopted" if baseline_adopted else "adopted"
        if scenario["policy_flip_direction"] != expected_policy_direction:
            raise ValueError(f"{state}: policy flip direction is inconsistent")
        if scenario["feature_flip_direction"] != expected_feature_direction:
            raise ValueError(f"{state}: feature flip direction is inconsistent")
        if (
            scenario["metric"] != "expected_threshold_crossing_probability"
            or scenario["weighting"] != "FY2024 QC household weight (HWGT)"
            or scenario["unit"] != "percentage_points"
            or scenario["delta_direction"] != "adopted_minus_not_adopted"
        ):
            raise ValueError(f"{state}: scenario metric metadata is inconsistent")
        patch = scenario["per_case"]
        if patch["patch_endpoint"] != expected_endpoint:
            raise ValueError(f"{state}: patch endpoint is inconsistent")
        indices = patch["i"]
        if indices != sorted(set(indices)) or any(
            not isinstance(index, int) or not 0 <= index < n for index in indices
        ):
            raise ValueError(f"{state}: sparse patch indexes are invalid")
        if not (
            len(indices)
            == len(patch["p_dev"])
            == len(patch["q"])
            == int(scenario["parameter_patch_n"])
        ):
            raise ValueError(f"{state}: sparse patch arrays have unequal lengths")
        if (
            not 0
            <= int(scenario["parameter_patch_n"])
            <= int(scenario["feature_flip_n"])
            <= n
        ):
            raise ValueError(f"{state}: flip/patch counts are invalid")
        p_dev = np.asarray(patch["p_dev"], dtype=float)
        if not np.isfinite(p_dev).all() or ((p_dev < 0) | (p_dev > 1)).any():
            raise ValueError(f"{state}: patch p_dev values are invalid")
        q = (
            np.asarray(patch["q"], dtype=float)
            if len(indices)
            else np.empty((0, len(QUANTILE_COLUMNS)), dtype=float)
        )
        if q.shape != (len(indices), len(QUANTILE_COLUMNS)):
            raise ValueError(f"{state}: patch quantile shape is invalid")
        if len(q) and ((np.diff(q, axis=1) < 0).any() or not np.isfinite(q).all()):
            raise ValueError(f"{state}: patch quantiles are invalid")
        minimum_log = math.log(
            float(payload["crossing"]["deviation_tolerance_dollars"])
        )
        if len(q) and (q < minimum_log).any():
            raise ValueError(f"{state}: patch quantiles fall below the model floor")
        statistics = np.asarray(
            [
                scenario["not_adopted_crossing_rate_pct"],
                scenario["adopted_crossing_rate_pct"],
                scenario["delta_pp"],
                scenario["baseline_to_patch_delta_pp"],
                scenario["ci_lo"],
                scenario["ci_hi"],
            ],
            dtype=float,
        )
        if not np.isfinite(statistics).all():
            raise ValueError(f"{state}: scenario statistics must be finite")
        if float(scenario["ci_lo"]) > float(scenario["ci_hi"]):
            raise ValueError(f"{state}: confidence interval is reversed")

    gate = payload["level_ratio_gate"]
    if list(gate["inclusive_bounds"]) != list(LEVEL_RATIO_BOUNDS):
        raise ValueError("scenario gate bounds are invalid")
    if gate["disabled_reason"] != GATE_REASON:
        raise ValueError("scenario gate reason is invalid")
    if list(gate["flagged_states"]) != flagged:
        raise ValueError("scenario gate state list differs from state flags")

    base = payload["base_model"]
    digest = base.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("scenario base-model SHA-256 is invalid")
    if base_model_sha256 is not None and base["sha256"] != base_model_sha256:
        raise ValueError("scenario base-model SHA-256 does not match supplied bytes")
    if model_data_payload is not None:
        model_states = model_data_payload.get("states")
        if set(states) != set(model_states):
            raise ValueError("scenario and base-model state sets differ")
        crossing = payload["crossing"]
        base_gate = model_data_payload["level_ratio_gate"]
        for key, value in base_gate.items():
            if gate.get(key) != value:
                raise ValueError(f"scenario and base-model gate {key} values differ")
        if int(base["schema_version"]) != int(model_data_payload["schema_version"]):
            raise ValueError("scenario and base-model schema versions differ")
        if base["q_encoding"] != model_data_payload["q_encoding"]:
            raise ValueError("scenario and base-model quantile encodings differ")
        crossing_bindings = {
            "threshold_dollars": "threshold",
            "tail_scale_log": "tail_scale_log",
            "deviation_tolerance_dollars": "deviation_tolerance",
        }
        for scenario_key, model_key in crossing_bindings.items():
            if float(crossing[scenario_key]) != float(model_data_payload[model_key]):
                raise ValueError(
                    f"scenario and base-model {scenario_key} values differ"
                )
        for state, state_record in states.items():
            model_state = model_states[state]
            if int(model_state["n"]) != int(state_record["n"]):
                raise ValueError(f"{state}: scenario/base-model n differs")
            if bool(model_state["level_flag"]) != state_record["level_flag"]:
                raise ValueError(f"{state}: scenario/base-model level flag differs")
            if float(model_state["level_ratio"]) != float(state_record["level_ratio"]):
                raise ValueError(f"{state}: scenario/base-model level ratio differs")
            lower, upper = (float(value) for value in gate["inclusive_bounds"])
            expected_flag = not lower <= float(state_record["level_ratio"]) <= upper
            if state_record["level_flag"] != expected_flag:
                raise ValueError(f"{state}: level flag is not implied by level ratio")
            scenario = state_record["levers"]["smd"]
            patched_p, patched_q = _patched_parameters(model_state, scenario)
            baseline_p = np.asarray(model_state["p_dev"], dtype=float)
            baseline_q = np.asarray(model_state["q"], dtype=float)
            baseline_cross = _crossing_probability(
                baseline_p,
                baseline_q,
                model_state["cap"],
                threshold=crossing["threshold_dollars"],
                tail_scale=crossing["tail_scale_log"],
                deviation_tolerance=crossing["deviation_tolerance_dollars"],
            )
            patched_cross = _crossing_probability(
                patched_p,
                patched_q,
                model_state["cap"],
                threshold=crossing["threshold_dollars"],
                tail_scale=crossing["tail_scale_log"],
                deviation_tolerance=crossing["deviation_tolerance_dollars"],
            )
            if scenario["baseline_adopted"]:
                adopted, not_adopted = baseline_cross, patched_cross
            else:
                adopted, not_adopted = patched_cross, baseline_cross
            weights = np.asarray(model_state["w"], dtype=float)
            adopted_rate = _round_decimal(
                100 * float(np.average(adopted, weights=weights)), 6
            )
            not_adopted_rate = _round_decimal(
                100 * float(np.average(not_adopted, weights=weights)), 6
            )
            implied_delta = _round_decimal(adopted_rate - not_adopted_rate, 6)
            baseline_to_patch_delta = _round_decimal(
                100
                * float(np.average(patched_cross - baseline_cross, weights=weights)),
                6,
            )
            if adopted_rate != scenario["adopted_crossing_rate_pct"]:
                raise ValueError(f"{state}: adopted crossing rate is not implied")
            if not_adopted_rate != scenario["not_adopted_crossing_rate_pct"]:
                raise ValueError(f"{state}: not-adopted crossing rate is not implied")
            if implied_delta != scenario["delta_pp"]:
                raise ValueError(f"{state}: crossing delta is not implied by patches")
            if baseline_to_patch_delta != scenario["baseline_to_patch_delta_pp"]:
                raise ValueError(
                    f"{state}: baseline-to-patch delta is not implied by patches"
                )

    co_validation = payload["validation"]["co_smd"]
    if co_validation.get("applicable") and not isinstance(
        co_validation.get("reconciled"), bool
    ):
        raise TypeError("CO SMD reconciliation result must be boolean")
    if int(interpretation["state_count"]) != len(states):
        raise ValueError("scenario interpretation state count is inconsistent")
    actual_spans_zero = sum(
        record["levers"]["smd"]["ci_lo"] <= 0 <= record["levers"]["smd"]["ci_hi"]
        for record in states.values()
    )
    if int(interpretation["ci_spans_zero_states"]) != actual_spans_zero:
        raise ValueError("scenario zero-spanning CI count is inconsistent")
    if bool(interpretation["cis_typically_span_zero"]) != (
        actual_spans_zero > len(states) / 2
    ):
        raise ValueError("scenario typical-CI summary is inconsistent")


def serialize_json(payload: Mapping[str, Any]) -> bytes:
    """Return canonical compact JSON bytes for the scenario artifact."""
    validate_scenario_artifact(payload)
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _signed(value: float, digits: int = 3) -> str:
    return f"{float(value):+.{digits}f}"


def render_document(payload: Mapping[str, Any]) -> str:
    """Render the generated scenario decision and state-delta report."""
    validate_scenario_artifact(payload)
    definitions = payload["lever_definitions"]
    interpretation = payload["interpretation"]
    reconciliation = payload["validation"]["co_smd"]
    uncertainty = payload["uncertainty"]
    gate_bounds = payload["level_ratio_gate"]["inclusive_bounds"]
    ci_count = int(interpretation["ci_spans_zero_states"])
    state_count = int(interpretation["state_count"])
    if interpretation["cis_typically_span_zero"]:
        ci_statement = (
            f"CIs typically span zero: {ci_count} of {state_count} state "
            "intervals do so."
        )
    else:
        ci_statement = (
            "The requested generalization that 'CIs typically span zero' is not "
            f"literally borne out by the completed table: {ci_count} of "
            f"{state_count} state intervals span zero."
        )
    lines = [
        "<!-- Generated by scripts_build_model_scenarios.py; do not edit manually. -->",
        "",
        "# Model-primary policy scenarios",
        "",
        (
            "The browser scenario export includes only the standard medical "
            "deduction (SMD). Its case-level parameters come from the fitted "
            "error model under the opposite `med_doc_required` feature, then all "
            "state results are reported as adopted minus not adopted."
        ),
        "",
        "## Lever decisions",
        "",
        "| Lever | Decision | Reason |",
        "|---|---|---|",
        (
            "| Standard medical deduction | Include | Exact bidirectional proxy: "
            "`FSMEDEXP > 35`, elderly/disabled, and no SMD. |"
        ),
    ]
    for lever in EXCLUDED_LEVERS:
        definition = definitions[lever]
        lines.append(f"| {definition['label']} | Exclude | {definition['reason']}. |")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "Deltas are model-implied associations from features carrying "
                f"{float(interpretation['burden_intermediate_roc_auc_lift']):+.4f} "
                "ROC AUC, which rounds to +0.006. They are not causal policy "
                f"effects. {ci_statement} Descriptive SMD-adoption contrasts are "
                "the calibration reference."
            ),
            "",
            (
                "The SMD feature is itself limited: it does not model the state's "
                "standard amount, whether that amount binds, or documentation of "
                "actual expenses above the standard. Near-zero results are retained "
                "rather than replaced with accounting suppression."
            ),
            "",
            "Descriptive adoption contrasts:",
            "",
            "| State | Claimant-conditioned | Stable all elderly/disabled |",
            "|---|---:|---:|",
        ]
    )
    contrasts = interpretation["descriptive_smd_adoption_contrasts_pp"]
    for state in sorted(contrasts):
        contrast = contrasts[state]
        lines.append(
            f"| {state} | {_signed(contrast['claimant_conditioned_pp'], 2)}pp | "
            f"{_signed(contrast['stable_all_elderly_disabled_pp'], 2)}pp |"
        )
    lines.extend(
        [
            "",
            "## State SMD deltas",
            "",
            (
                "Each delta is the HWGT-weighted difference in expected threshold-"
                "crossing probability, in percentage points; it is not an official "
                "payment-error dollar-rate anchor shift. The point and percentile "
                f"interval use {int(uncertainty['draws']):,} paired case-bootstrap "
                f"draws at seed {int(uncertainty['seed'])}, conditional on the "
                "fitted model. `Gated` "
                "means the browser should disable model output because the state's "
                "factor-adjusted FY2024 model/observed level ratio is outside "
                f"[{gate_bounds[0]}, {gate_bounds[1]}]."
            ),
            "",
            "| State | FY2024 SMD | Feature flip | Cases | Adoption crossing delta (pp) | 95% CI (pp) | Gate |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for state, state_record in payload["states"].items():
        scenario = state_record["levers"]["smd"]
        lines.append(
            f"| {state} | {'adopted' if scenario['baseline_adopted'] else 'not adopted'} "
            f"| `{scenario['feature_flip_direction']}` | "
            f"{int(scenario['feature_flip_n'])} | "
            f"{_signed(scenario['delta_pp'], 4)} | "
            f"[{_signed(scenario['ci_lo'], 4)}, {_signed(scenario['ci_hi'], 4)}] | "
            f"{'Gated' if state_record['level_flag'] else 'Pass'} |"
        )
    if reconciliation.get("applicable"):
        lines.extend(
            [
                "",
                "## Colorado reconciliation",
                "",
                (
                    "The exported Colorado burden-only SMD-off delta is "
                    f"{_signed(reconciliation['exported_not_adopted_minus_adopted_pp'], 4)}pp. "
                    "The feature-only `ceiling` comparison in "
                    "`counterfactual_co_smd.json` is "
                    f"{_signed(reconciliation['reference_direct_not_minus_adopted_pp'], 4)}pp "
                    "for the direct classifier and "
                    f"{_signed(reconciliation['reference_hurdle_not_minus_adopted_pp'], 4)}pp "
                    "for the hurdle crossing. Both use the shared documented "
                    "predicate and report "
                    f"{int(reconciliation['feature_flip_n'])} and "
                    f"{int(reconciliation['reference_feature_flip_n'])} flipped "
                    "cases, respectively. The reference artifact does not expose "
                    "case identifiers, so exact mask membership is not independently "
                    "verified."
                ),
                "",
                (
                    "After normalizing to not adopted minus adopted, the checks "
                    "are: point-sign concordance="
                    f"{'yes' if reconciliation['point_sign_matches'] else 'no'}; "
                    "conditional-interval overlap="
                    f"{'yes' if reconciliation['conditional_intervals_overlap_direct'] else 'no'}; "
                    "reference direct point in export interval="
                    f"{'yes' if reconciliation['reference_direct_point_in_export_interval'] else 'no'}. "
                    "The recorded reconciliation therefore "
                    f"{'passes' if reconciliation['reconciled'] else 'does not pass'}. "
                    "The point estimates are not required to equal one another. "
                    "This export freezes the distributional model after FY2022; "
                    "the reference fits its direct and hurdle estimators through "
                    "FY2023. The reported gaps are "
                    f"{_signed(reconciliation['difference_from_reference_direct_pp'], 4)}pp "
                    "versus direct and "
                    f"{_signed(reconciliation['difference_from_reference_hurdle_pp'], 4)}pp "
                    "versus hurdle."
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Browser contract",
            "",
            (
                "`model_scenarios.json` is valid only with the exact "
                f"`model_data.json` SHA-256 `{payload['base_model']['sha256']}`. "
                "Each sparse patch replaces full quantized parameters at state-local "
                "indexes; unlisted rows retain the baseline values. Reported gzip "
                "size uses compression level 9 with `mtime=0`."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    payload: Mapping[str, Any],
    json_output: Path,
    document_output: Path,
) -> dict[str, Any]:
    """Write deterministic JSON/Markdown outputs and return size/hash metadata."""
    encoded = serialize_json(payload)
    compressed = gzip.compress(encoded, compresslevel=9, mtime=0)
    if len(compressed) >= MAX_GZIP_BYTES:
        raise ValueError(
            f"model scenario export is {len(compressed):,} gzip bytes; "
            f"limit is below {MAX_GZIP_BYTES:,}"
        )
    document = render_document(payload).encode("utf-8")
    json_output = Path(json_output)
    document_output = Path(document_output)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    document_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_bytes(encoded)
    document_output.write_bytes(document)
    return {
        "data": payload,
        "raw_bytes": len(encoded),
        "gzip_bytes": len(compressed),
        "sha256": _sha256_bytes(encoded),
        "document_sha256": _sha256_bytes(document),
        "output_path": str(json_output),
        "document_output_path": str(document_output),
    }


def build_model_scenarios(
    baseline_predictions: pd.DataFrame,
    *,
    distributional_bundle: distributional_deviation_model.DistributionalBundle,
    model_data_payload: Mapping[str, Any],
    base_model_path: Path,
    model_results: Mapping[str, Any],
    counterfactual_payload: Mapping[str, Any],
    output_path: Path,
    document_output_path: Path,
    smd_states: set[str] | None = None,
    bootstrap_draws: int = BOOTSTRAP_DRAWS,
) -> dict[str, Any]:
    """Predict the opposite SMD endpoint, prepare the payload, and write it."""
    states = (
        train_error_model.load_smd_registry()[FISCAL_YEAR]
        if smd_states is None
        else set(smd_states)
    )
    flipped = flip_smd_documentation_features(baseline_predictions, states)
    features = hurdle_deviation_model._feature_columns(baseline_predictions)
    flipped_parameters = distributional_deviation_model.predict_export_parameters(
        distributional_bundle,
        flipped,
        features,
    )
    flipped["p_dev"] = flipped_parameters["p_dev"]
    for column in QUANTILE_COLUMNS:
        flipped[column] = flipped_parameters[column]

    bound_model_data, base_sha256 = _read_bound_model_data(
        base_model_path,
        model_data_payload,
    )
    payload = prepare_model_scenarios(
        baseline_predictions,
        flipped,
        model_data_payload=bound_model_data,
        base_model_sha256=base_sha256,
        smd_states=states,
        model_results=model_results,
        counterfactual_payload=counterfactual_payload,
        bootstrap_draws=bootstrap_draws,
    )
    return write_outputs(payload, output_path, document_output_path)


def main() -> None:
    """Fit/load the frozen model and write both scenario artifacts."""
    artifacts = distributional_deviation_model.analyze()
    model_data_payload = _read_json(DEFAULT_MODEL_DATA)
    if model_data_payload != artifacts.model_data_payload:
        raise ValueError(
            "committed model_data.json differs from the freshly fitted baseline"
        )
    report = build_model_scenarios(
        artifacts.predictions,
        distributional_bundle=artifacts.bundle,
        model_data_payload=model_data_payload,
        base_model_path=DEFAULT_MODEL_DATA,
        model_results=_read_json(DEFAULT_MODEL_RESULTS),
        counterfactual_payload=_read_json(DEFAULT_COUNTERFACTUAL),
        output_path=DEFAULT_OUTPUT,
        document_output_path=DEFAULT_DOCUMENT_OUTPUT,
    )
    print(
        f"{DEFAULT_OUTPUT}: {report['raw_bytes'] / 1e6:.3f} MB raw, "
        f"{report['gzip_bytes'] / 1e6:.3f} MB gzip, "
        f"{len(report['data']['states'])} states"
    )
    print(f"wrote {DEFAULT_DOCUMENT_OUTPUT}")


if __name__ == "__main__":
    main()
