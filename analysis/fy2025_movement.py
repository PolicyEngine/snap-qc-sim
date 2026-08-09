"""FY2024 → FY2025 official-rate movement against simulated sampling noise.

The fiscal 2025 official payment error rates published 2026-06-24 are the
first of the two rates a state may elect for its FY2028 cost share. This
script asks, per state: did the official rate move more than the sampling
noise this simulator attributes to a QC-sized sample? Movements within
noise are what the paper's tier-lottery thesis predicts; movements beyond
it are evidence of process change (or methodology change) between years.

Deterministic: fixed seed, committed inputs. Outputs
``analysis/fy2025_movement.json`` and ``analysis/FY2025_MOVEMENT.md``.
The z convention is disclosed in the artifact: the denominator is the
FY2024-anchored sampling SD only; both years carry sampling noise, so a
two-year-noise 95% band under independence is |z| > 1.96 * sqrt(2) = 2.77.

The artifact also estimates cross-state process drift without changing the
simulator.  Its classical method of moments subtracts twice the mean FY2024
sampling variance from the sample variance of state movements.  A robust
check replaces those summaries with a normal-consistent median absolute
deviation and the median sampling variance.  State-pair bootstrap intervals
describe cross-jurisdiction uncertainty, not uncertainty across transition
years: only FY2024 to FY2025 is observed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from snap_qc_sim import load_cases, simulate

DATA_JSON = REPO_ROOT / "app" / "public" / "data.json"
OUT_JSON = REPO_ROOT / "analysis" / "fy2025_movement.json"
OUT_MD = REPO_ROOT / "analysis" / "FY2025_MOVEMENT.md"
QC_CSV = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
FY25_PDF_SHA256 = "ae3fc57f2398cea36e9c1322f9f2208a39a7045a4524d259bd1ac22e890c754e"

SEED = 11
DRAWS = 4000
DRIFT_BOOTSTRAP_SEED = 202507
DRIFT_BOOTSTRAP_DRAWS = 10_000
EXPECTED_JURISDICTIONS = 53
NORMAL_MAD_SCALE = 0.6744897501960817
# FY2028 cost-share tiers, 7 U.S.C. 2013(a)(2): hand-transcribed pending the
# encoded schedule (rulespec-us 275.11/2013(a)(2) lane).
TIER_CUTS = ((6.0, 0), (8.0, 5), (10.0, 10), (math.inf, 15))
TWO_YEAR_Z = 1.96 * math.sqrt(2)


def tier_share(rate: float) -> int:
    """Return the FY2028 cost-share percentage for a payment error rate."""
    if not math.isfinite(rate) or rate < 0:
        raise ValueError(f"rate must be finite and nonnegative: {rate}")
    for cut, share in TIER_CUTS:
        if rate < cut:
            return share
    raise AssertionError("unreachable")


def delay_applies(rate: float) -> bool:
    """7 U.S.C. 2013(a)(2)(B)(iii): delayed start when rate x 1.5 reaches 20%."""
    if not math.isfinite(rate) or rate < 0:
        raise ValueError(f"rate must be finite and nonnegative: {rate}")
    return rate * 1.5 >= 20.0


def movement_row(
    state: str, fy2024: float, fy2025: float, sd_fy2024_pp: float
) -> dict[str, object]:
    """One state's movement record; pure given the three inputs."""
    delta = fy2025 - fy2024
    z = delta / sd_fy2024_pp if sd_fy2024_pp > 0 else math.inf * math.copysign(1, delta)
    return {
        "state": state,
        "fy2024": fy2024,
        "fy2025": fy2025,
        "delta_pp": round(delta, 4),
        "sampling_sd_fy2024_pp": round(sd_fy2024_pp, 4),
        "z_vs_fy2024_sampling_sd": round(z, 4),
        "beyond_two_year_noise_95": bool(abs(z) > TWO_YEAR_Z),
        "tier_fy2024": tier_share(fy2024),
        "tier_fy2025": tier_share(fy2025),
        "tier_changed": tier_share(fy2024) != tier_share(fy2025),
        "delay_fy2024": delay_applies(fy2024),
        "delay_fy2025": delay_applies(fy2025),
    }


def _validate_drift_inputs(
    deltas_pp: np.ndarray | list[float],
    sampling_sds_pp: np.ndarray | list[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Return validated one-dimensional arrays for the drift estimators."""
    deltas = np.asarray(deltas_pp, dtype=float)
    sampling_sds = np.asarray(sampling_sds_pp, dtype=float)
    if deltas.ndim != 1 or sampling_sds.ndim != 1:
        raise ValueError("deltas and sampling SDs must be one-dimensional")
    if deltas.size != sampling_sds.size:
        raise ValueError("deltas and sampling SDs must have the same length")
    if deltas.size < 2:
        raise ValueError("at least two jurisdictions are required")
    if not np.isfinite(deltas).all():
        raise ValueError("deltas must be finite")
    if not np.isfinite(sampling_sds).all() or (sampling_sds < 0).any():
        raise ValueError("sampling SDs must be finite and nonnegative")
    return deltas, sampling_sds


def _classical_drift_components(
    deltas_pp: np.ndarray, sampling_sds_pp: np.ndarray
) -> tuple[float, float, float, float]:
    """Return observed, sampling, raw drift variances and truncated tau."""
    observed_variance = float(np.var(deltas_pp, ddof=1))
    two_year_sampling_variance = float(2 * np.mean(np.square(sampling_sds_pp)))
    drift_variance = observed_variance - two_year_sampling_variance
    tau = math.sqrt(max(0.0, drift_variance))
    return observed_variance, two_year_sampling_variance, drift_variance, tau


def _robust_drift_components(
    deltas_pp: np.ndarray, sampling_sds_pp: np.ndarray
) -> tuple[float, float, float, float, float, float]:
    """Return median/MAD inputs, variances, and robust truncated tau."""
    median_delta = float(np.median(deltas_pp))
    movement_mad = float(np.median(np.abs(deltas_pp - median_delta)))
    observed_variance = (movement_mad / NORMAL_MAD_SCALE) ** 2
    two_year_sampling_variance = float(2 * np.median(np.square(sampling_sds_pp)))
    drift_variance = observed_variance - two_year_sampling_variance
    tau = math.sqrt(max(0.0, drift_variance))
    return (
        median_delta,
        movement_mad,
        observed_variance,
        two_year_sampling_variance,
        drift_variance,
        tau,
    )


def _bootstrap_summary(samples_pp: np.ndarray) -> dict[str, object]:
    """Summarize deterministic bootstrap samples for the generated artifact."""
    lower, upper = np.quantile(samples_pp, [0.025, 0.975])
    return {
        "standard_error_pp": round(float(np.std(samples_pp, ddof=1)), 4),
        "confidence_interval_95_pp": [round(float(lower), 4), round(float(upper), 4)],
        "zero_estimate_share": round(float(np.mean(samples_pp == 0)), 4),
    }


def estimate_process_drift(
    deltas_pp: np.ndarray | list[float],
    sampling_sds_pp: np.ndarray | list[float],
    *,
    bootstrap_draws: int = DRIFT_BOOTSTRAP_DRAWS,
    seed: int = DRIFT_BOOTSTRAP_SEED,
) -> dict[str, object]:
    """Estimate de-noised process-drift SDs and paired-state uncertainty.

    The method-of-moments estimator uses
    ``Var(delta) = 2 * mean(sampling_sd**2) + tau**2``.  The factor of two
    assumes independent sampling error and the same state-specific sampling
    SD in both years.  The robust check uses the squared normal-consistent MAD
    for observed variance and twice the median state sampling variance.
    Negative variance components are identified but tau is truncated at zero.
    """
    if not isinstance(bootstrap_draws, int) or bootstrap_draws <= 0:
        raise ValueError("bootstrap_draws must be a positive integer")
    deltas, sampling_sds = _validate_drift_inputs(deltas_pp, sampling_sds_pp)

    observed, sampling, raw_drift, tau = _classical_drift_components(
        deltas, sampling_sds
    )
    median, mad, robust_observed, robust_sampling, robust_raw, robust_tau = (
        _robust_drift_components(deltas, sampling_sds)
    )

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, deltas.size, size=(bootstrap_draws, deltas.size))
    boot_deltas = deltas[indices]
    boot_sds = sampling_sds[indices]

    boot_observed = np.var(boot_deltas, axis=1, ddof=1)
    boot_sampling = 2 * np.mean(np.square(boot_sds), axis=1)
    boot_tau = np.sqrt(np.maximum(0, boot_observed - boot_sampling))

    boot_medians = np.median(boot_deltas, axis=1)
    boot_mads = np.median(np.abs(boot_deltas - boot_medians[:, np.newaxis]), axis=1)
    boot_robust_observed = np.square(boot_mads / NORMAL_MAD_SCALE)
    boot_robust_sampling = 2 * np.median(np.square(boot_sds), axis=1)
    boot_robust_tau = np.sqrt(
        np.maximum(0, boot_robust_observed - boot_robust_sampling)
    )

    return {
        "unit": "percentage points",
        "point_estimates": {
            "classical_method_of_moments": {
                "mean_delta_pp": round(float(np.mean(deltas)), 4),
                "observed_movement_variance_pp2": round(observed, 4),
                "two_year_sampling_variance_pp2": round(sampling, 4),
                "untruncated_drift_variance_pp2": round(raw_drift, 4),
                "tau_pp": round(tau, 4),
            },
            "robust_median_mad": {
                "median_delta_pp": round(median, 4),
                "movement_mad_pp": round(mad, 4),
                "normal_consistent_observed_variance_pp2": round(robust_observed, 4),
                "two_year_median_sampling_variance_pp2": round(robust_sampling, 4),
                "untruncated_drift_variance_pp2": round(robust_raw, 4),
                "tau_pp": round(robust_tau, 4),
            },
        },
        "bootstrap": {
            "method": (
                "paired nonparametric i.i.d. bootstrap of jurisdiction "
                "(delta, sampling SD) rows; 95% percentile interval"
            ),
            "draws": bootstrap_draws,
            "seed": seed,
            "classical_tau": _bootstrap_summary(boot_tau),
            "robust_tau": _bootstrap_summary(boot_robust_tau),
        },
    }


def build() -> dict[str, object]:
    data = json.loads(DATA_JSON.read_text())
    cases_by_state = load_cases(QC_CSV)
    rows = []
    for state in sorted(data["states"]):
        st = data["states"][state]
        cases = cases_by_state[state]
        draws = simulate(
            cases,
            st["official"],
            draws=DRAWS,
            rng=np.random.default_rng(SEED),
        )
        rows.append(
            movement_row(
                state, st["official"], st["official_fy2025"], float(np.std(draws))
            )
        )
    if len(rows) != EXPECTED_JURISDICTIONS:
        raise ValueError(
            f"expected {EXPECTED_JURISDICTIONS} jurisdictions, found {len(rows)}"
        )
    deltas = np.array([r["delta_pp"] for r in rows], dtype=float)
    sampling_sds = np.array([r["sampling_sd_fy2024_pp"] for r in rows], dtype=float)
    drift_estimate = estimate_process_drift(deltas, sampling_sds)
    drift_estimate.update(
        {
            "coverage": {
                "jurisdictions_available": len(rows),
                "jurisdictions_used": len(rows),
                "excluded_jurisdictions": [],
            },
            "definition": (
                "Across-state Var(FY2025 - FY2024) = 2 * mean(FY2024 "
                "sampling SD squared) + tau squared"
            ),
            "estimators": {
                "classical_method_of_moments": (
                    "sample variance of state movements (ddof=1), less twice "
                    "the mean squared state sampling SD"
                ),
                "robust_median_mad": (
                    f"squared MAD/{NORMAL_MAD_SCALE:.16f} about the median "
                    "movement, less twice the median squared state sampling SD; "
                    "the MAD scaling is normal-consistent"
                ),
                "boundary": (
                    "tau = sqrt(max(0, estimated drift variance)); the "
                    "untruncated variance is also reported"
                ),
            },
            "assumptions": [
                (
                    "FY2024 and FY2025 state sampling errors are independent; "
                    "correlated QC errors would change the factor of two."
                ),
                (
                    "Each state's FY2025 sampling SD equals its simulated "
                    "FY2024 SD. SDs may differ across states."
                ),
                (
                    "After removing the common movement location, remaining "
                    "state process changes and sampling errors are independent."
                ),
                (
                    "The state-pair bootstrap treats the 53 jurisdictions as "
                    "exchangeable and resamples each delta with its sampling SD."
                ),
            ],
            "caveats": [
                (
                    "Only one transition, FY2024 to FY2025, is observed; this "
                    "cannot identify year-to-year drift stability."
                ),
                (
                    "Any FY2024-to-FY2025 QC methodology or administrative "
                    "change is conflated with process drift."
                ),
                (
                    "The bootstrap interval measures cross-jurisdiction "
                    "sensitivity for this transition, not temporal, model, or "
                    "QC-design uncertainty."
                ),
                (
                    "The sampling SDs are Monte Carlo estimates from FY2024 "
                    "observed-resample simulator draws, not published FY2025 "
                    "design-based standard errors."
                ),
            ],
            "recommendation": (
                "Keep app draws sampling-only. Carry the classical tau as a "
                "candidate process-drift calibration and the robust tau as an "
                "outlier-resistant sensitivity check for the later fable "
                "decision; do not add either to simulator draws yet."
            ),
        }
    )
    beyond = [r["state"] for r in rows if r["beyond_two_year_noise_95"]]
    flips = [
        f"{r['state']} {r['tier_fy2024']}%->{r['tier_fy2025']}%"
        for r in rows
        if r["tier_changed"]
    ]
    delay24 = [r["state"] for r in rows if r["delay_fy2024"]]
    delay25 = [r["state"] for r in rows if r["delay_fy2025"]]
    return {
        "definitions": {
            "delta_pp": "FY2025 official minus FY2024 official, percentage points",
            "sampling_sd_fy2024_pp": (
                "SD of the simulator's FY2024-anchored measured-rate draws "
                f"({DRAWS} draws, seed {SEED}, observed resample, unclipped)"
            ),
            "z_convention": (
                "denominator is FY2024 sampling SD only; both years carry "
                "sampling noise, so the two-year 95% band under independence "
                f"and equal SDs is |z| > {TWO_YEAR_Z:.2f}"
            ),
            "delay_rule": "7 USC 2013(a)(2)(B)(iii): published rate x 1.5 >= 20",
            "tiers": "0/5/10/15% shares at <6, 6-8, 8-10, >=10",
        },
        "provenance": {
            "fy2024_source": "app/public/data.json officials (FNS FY2024 PER)",
            "fy2025_source": f"FNA FY2025 PER pdf sha256 {FY25_PDF_SHA256}",
            "generator": "analysis/fy2025_movement.py",
        },
        "national": data["national"],
        "aggregates": {
            "jurisdictions": len(rows),
            "mean_abs_delta_pp": round(float(np.mean(np.abs(deltas))), 4),
            "persistence_mae_pp": round(float(np.mean(np.abs(deltas))), 4),
            "median_abs_z": round(
                float(np.median([abs(r["z_vs_fy2024_sampling_sd"]) for r in rows])),
                4,
            ),
            "beyond_two_year_noise_95_count": len(beyond),
            "beyond_two_year_noise_95_states": beyond,
            "tier_flip_count": len(flips),
            "tier_flips": flips,
            "delay_fy2024_states": delay24,
            "delay_fy2025_states": delay25,
            "delay_dropped": sorted(set(delay24) - set(delay25)),
            "delay_added": sorted(set(delay25) - set(delay24)),
        },
        "drift_estimate": drift_estimate,
        "states": rows,
    }


def render_markdown(result: dict[str, object]) -> str:
    agg = result["aggregates"]
    drift = result["drift_estimate"]
    classical = drift["point_estimates"]["classical_method_of_moments"]
    robust = drift["point_estimates"]["robust_median_mad"]
    classical_bootstrap = drift["bootstrap"]["classical_tau"]
    robust_bootstrap = drift["bootstrap"]["robust_tau"]
    lines = [
        "<!-- Generated by analysis/fy2025_movement.py; do not edit manually. -->",
        "",
        "# FY2024 to FY2025 official-rate movement",
        "",
        (
            f"National: {result['national']['fy2024']}% (FY2024) to "
            f"{result['national']['fy2025']}% (FY2025). Mean absolute state "
            f"movement {agg['mean_abs_delta_pp']}pp; median |z| against the "
            f"FY2024-anchored sampling SD {agg['median_abs_z']}; "
            f"{agg['beyond_two_year_noise_95_count']} of {agg['jurisdictions']} "
            f"jurisdictions moved beyond the two-year sampling-noise 95% band "
            f"(|z| > {TWO_YEAR_Z:.2f})."
        ),
        "",
        (
            f"Tier changes at the published point rates: {agg['tier_flip_count']} "
            f"({', '.join(agg['tier_flips']) or 'none'})."
        ),
        "",
        (
            f"Delay clause (rate x 1.5 >= 20): {len(agg['delay_fy2024_states'])} "
            f"jurisdictions at FY2024 rates, {len(agg['delay_fy2025_states'])} at "
            f"FY2025 rates; dropped {', '.join(agg['delay_dropped']) or 'none'}; "
            f"added {', '.join(agg['delay_added']) or 'none'}."
        ),
        "",
        "## Process-drift calibration",
        "",
        (
            f"All {drift['coverage']['jurisdictions_used']} jurisdictions are "
            "included, with no exclusions. The classical method-of-moments "
            f"estimate is **tau = {classical['tau_pp']:.4f}pp** (paired-state "
            "bootstrap 95% interval "
            f"{classical_bootstrap['confidence_interval_95_pp'][0]:.4f} to "
            f"{classical_bootstrap['confidence_interval_95_pp'][1]:.4f}pp). "
            f"Observed movement variance is "
            f"{classical['observed_movement_variance_pp2']:.4f}pp^2; subtracting "
            f"the two-year sampling component of "
            f"{classical['two_year_sampling_variance_pp2']:.4f}pp^2 leaves "
            f"{classical['untruncated_drift_variance_pp2']:.4f}pp^2."
        ),
        "",
        (
            "The robust check uses the normal-consistent MAD about the median "
            "movement and twice the median squared state sampling SD. It gives "
            f"**tau = {robust['tau_pp']:.4f}pp** (bootstrap 95% interval "
            f"{robust_bootstrap['confidence_interval_95_pp'][0]:.4f} to "
            f"{robust_bootstrap['confidence_interval_95_pp'][1]:.4f}pp). "
            "Both estimators truncate a negative de-noised variance at zero and "
            "report the untruncated component in the JSON artifact."
        ),
        "",
        "### Assumptions and caveats",
        "",
        *[f"- {item}" for item in drift["assumptions"]],
        "",
        *[f"- {item}" for item in drift["caveats"]],
        "",
        f"**Recommendation:** {drift['recommendation']}",
        "",
        "| State | FY2024 | FY2025 | Delta (pp) | Sampling SD (pp) | z | Tier 24 | Tier 25 | Delay 25 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in result["states"]:
        lines.append(
            f"| {r['state']} | {r['fy2024']:.2f} | {r['fy2025']:.2f} "
            f"| {r['delta_pp']:+.2f} | {r['sampling_sd_fy2024_pp']:.2f} "
            f"| {r['z_vs_fy2024_sampling_sd']:+.2f} | {r['tier_fy2024']}% "
            f"| {r['tier_fy2025']}% | {'yes' if r['delay_fy2025'] else ''} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    result = build()
    OUT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    OUT_MD.write_text(render_markdown(result))
    digest = hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()
    print(f"wrote {OUT_JSON} (sha256 {digest[:16]}...)")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
