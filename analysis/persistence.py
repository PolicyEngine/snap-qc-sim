"""State persistence of SNAP payment error rates, FY2012-24.

The FY2024-to-FY2025 movement analysis measured one year of process drift
(tau) and could not separate persistent state differences from transitory
movement. This module uses the full audited FY2012-24 panel to make that
split: each state-year reconstructed total error rate decomposes into a
year effect (removed), a persistent state component alpha, a transitory
AR(1) process u, and a sampling layer e with per-cell variance estimated
by bootstrap from the raw microdata.

    rate[s, t] - year_mean[t] = alpha[s] + u[s, t] + e[s, t]
    var(alpha) = sigma_alpha^2;  u AR(1) with sigma_u^2, rho;
    var(e[s, t]) = v[s, t]  (known, heteroskedastic, bootstrap-estimated)

Estimation is method of moments on the demeaned panel's autocovariances,
matching the movement memo's estimator family. Outputs: the variance
split, per-state single-year reliabilities, an out-of-sample validation
against demeaned FY2025 official rates, and a multi-year cost-share
exposure simulator on the 7 USC 2013(a)(2) tiers.

Conventions inherited from the event studies: the FY2012-24 panel from
``event_study.build_riky_panel`` (hash-audited raw files, fixed real
counted-error threshold so nominal threshold changes cannot masquerade as
drift), and FY2021 dropped as pandemic-partial per the coding audit. All
53 jurisdictions enter; states are treated as exchangeable when demeaning
and bootstrapping, as in the movement analysis.

This quantifies persistence in the reconstructed measurement process. It
is a description of the panel, not a causal model of state behavior.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis import event_study
from snap_qc_sim.simulate import tier_of

OUT = Path(__file__).with_name("persistence_results.json")
MEMO_OUT = Path(__file__).with_name("PERSISTENCE.md")
MOVEMENT_PATH = Path(__file__).with_name("fy2025_movement.json")

#: FY2021 is pandemic-partial per the coding audit's fy2021 note.
YEARS_USED: tuple[int, ...] = tuple(y for y in event_study.RIKY_YEARS if y != 2021)
MAX_LAG = 6
CELL_BOOTSTRAP_DRAWS = 1000
STATE_BOOTSTRAP_REPS = 1000
EXPOSURE_DRAWS = 20_000
EXPOSURE_YEARS: tuple[int, ...] = (2028, 2029, 2030)
RHO_GRID = np.round(np.arange(-0.50, 0.996, 0.005), 3)
SEED = 20260817


def raw_inputs_available() -> bool:
    """True when the audited FY2012-24 raw cache is present."""
    return event_study.riky_raw_inputs_available()


def build_rate_panel() -> pd.DataFrame:
    """State-year total error rates for the years used, wide (state x year)."""
    panel = event_study.build_riky_panel()
    panel = panel.loc[panel["year"].isin(YEARS_USED)]
    wide = panel.pivot(index="state", columns="year", values="total_error_rate")
    return wide.sort_index()


def cell_sampling_variances(rng: np.random.Generator) -> pd.DataFrame:
    """Bootstrap sampling variance of each state-year rate from raw cases."""
    audit = json.loads(event_study.AUDIT_PATH.read_text())
    required = ["STATE", "CASE", "STATUS", "HWGT", "RAWBEN", "AMTERR"]
    records: dict[int, dict[str, float]] = {}
    for year in YEARS_USED:
        path = event_study._riky_source_path(year)
        expected = audit["years"][str(year)]["source"]["sha256"]
        if not path.is_file() or event_study._sha256(path) != expected:
            raise FileNotFoundError(f"Missing or hash-mismatched input: {path}")
        frame = event_study._read_raw_frame(path, required)
        frame = frame.loc[frame["CASE"].eq(1) & frame["HWGT"].gt(0)].copy()
        frame["state"] = frame["STATE"].astype(int).map(event_study.FIPS)
        threshold = (
            event_study.RIKY_FIXED_REAL_THRESHOLD
            * event_study.CPI_U[year]
            / event_study.CPI_U[2024]
        )
        counted = frame["STATUS"].isin((2, 3)) & frame["AMTERR"].gt(threshold)
        frame["err"] = frame["AMTERR"].where(counted, 0.0)
        by_year: dict[str, float] = {}
        for state, group in frame.groupby("state"):
            w = group["HWGT"].to_numpy()
            err = group["err"].to_numpy()
            iss = group["RAWBEN"].to_numpy()
            n = len(group)
            idx = rng.integers(0, n, size=(CELL_BOOTSTRAP_DRAWS, n))
            boots = 100.0 * (w * err)[idx].sum(axis=1) / (w * iss)[idx].sum(axis=1)
            by_year[state] = float(boots.var(ddof=1))
        records[year] = by_year
    return pd.DataFrame(records).sort_index()


def demean_by_year(wide: pd.DataFrame) -> pd.DataFrame:
    """Remove each year's cross-state mean (states exchangeable)."""
    return wide.sub(wide.mean(axis=0), axis=1)


def autocovariances(
    x: pd.DataFrame, v: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, float]:
    """Mean products at calendar lags 0..MAX_LAG, pair counts, mean cell variance.

    Demeaning by the cross-state mean of S exchangeable states shrinks
    the expected same-state product by (S-1)/S at every lag, so the
    S/(S-1) correction applies to all lags (a 1/53 = 1.9 percent
    systematic factor at S = 53).
    """
    years = list(x.columns)
    n_states = x.shape[0]
    c = np.zeros(MAX_LAG + 1)
    counts = np.zeros(MAX_LAG + 1)
    for i, t in enumerate(years):
        for t2 in years[i:]:
            k = t2 - t
            if k > MAX_LAG:
                continue
            prod = (x[t] * x[t2]).mean() * n_states / (n_states - 1)
            c[k] += prod * len(x)
            counts[k] += len(x)
    c = c / np.where(counts > 0, counts, 1.0)
    return c, counts, float(v.to_numpy().mean())


def fit_components(
    c: np.ndarray, counts: np.ndarray, mean_v: float
) -> dict[str, float]:
    """Method of moments: sigma_alpha^2, sigma_u^2, rho from the moments.

    For each rho on a grid, (sigma_alpha^2, sigma_u^2) solves weighted
    least squares of [C_0 - mean_v, C_1, ..., C_K] on [1, rho^k] with
    nonnegativity by corner clipping; rho minimizes the weighted SSE.
    Negative de-noised moments truncate at zero with the untruncated
    value reported, matching the movement memo.
    """
    targets = c.copy()
    targets[0] = c[0] - mean_v
    weights = counts / counts.sum()
    best: dict[str, float] | None = None
    for rho in RHO_GRID:
        basis = np.stack([np.ones(MAX_LAG + 1), rho ** np.arange(MAX_LAG + 1)], axis=1)
        wmat = basis * weights[:, None]
        try:
            coef, *_ = np.linalg.lstsq(wmat.T @ basis, wmat.T @ targets, rcond=None)
        except np.linalg.LinAlgError:
            continue
        candidates = [coef]
        if coef[0] < 0 or coef[1] < 0:
            for fixed_alpha, _fixed_u in ((0.0, None), (None, 0.0)):
                if fixed_alpha == 0.0:
                    b_only = float(
                        (weights * targets * basis[:, 1]).sum()
                        / (weights * basis[:, 1] ** 2).sum()
                    )
                    candidates.append(np.array([0.0, max(b_only, 0.0)]))
                else:
                    a_only = float((weights * targets).sum() / weights.sum())
                    candidates.append(np.array([max(a_only, 0.0), 0.0]))
        for cand in candidates:
            if cand[0] < 0 or cand[1] < 0:
                continue
            resid = targets - basis @ cand
            sse = float((weights * resid**2).sum())
            if best is None or sse < best["sse"]:
                best = {
                    "sigma_alpha_sq": float(cand[0]),
                    "sigma_u_sq": float(cand[1]),
                    "rho": float(rho),
                    "sse": sse,
                }
    assert best is not None
    best["untruncated_lag0_component"] = float(targets[0])
    return best


def _state_covariance(
    years: list[int], fit: dict[str, float], v_row: pd.Series
) -> np.ndarray:
    a, b, rho = fit["sigma_alpha_sq"], fit["sigma_u_sq"], fit["rho"]
    t = np.array(years, dtype=float)
    gaps = np.abs(t[:, None] - t[None, :])
    cov = a + b * rho**gaps
    cov[np.diag_indices_from(cov)] += np.array([v_row[y] for y in years])
    return cov


def predict_demeaned(
    x: pd.DataFrame,
    v: pd.DataFrame,
    fit: dict[str, float],
    target_year: int,
) -> pd.Series:
    """Conditional mean of the demeaned true rate at target_year per state."""
    years = list(x.columns)
    a, b, rho = fit["sigma_alpha_sq"], fit["sigma_u_sq"], fit["rho"]
    preds = {}
    for state in x.index:
        cov = _state_covariance(years, fit, v.loc[state])
        gaps = np.abs(np.array(years, dtype=float) - target_year)
        cross = a + b * rho**gaps
        weights = np.linalg.solve(cov, cross)
        preds[state] = float(weights @ x.loc[state].to_numpy())
    return pd.Series(preds).sort_index()


def validate_fy2025(
    x: pd.DataFrame, v: pd.DataFrame, fit: dict[str, float]
) -> dict[str, Any]:
    """Cross-scale check against demeaned FY2025 official rates.

    The predictor is a latent-rate conditional mean built from the
    reconstructed panel; the target is the measured official series,
    which carries sampling and regression-adjustment noise this model
    does not observe. Scores therefore describe this one transition
    across scales; they are not a clean model comparison, and the
    artifact labels them accordingly. Baselines: the state's demeaned
    FY2024 reconstructed rate carried forward, the demeaned FY2024
    official rate carried forward (the target's own scale), and zero
    (the national mean).
    """
    movement = json.loads(MOVEMENT_PATH.read_text())
    official = pd.Series({row["state"]: row["fy2025"] for row in movement["states"]})
    official = official.reindex(x.index).dropna()
    target = official - official.mean()
    official_2024 = pd.Series(
        {row["state"]: row["fy2024"] for row in movement["states"]}
    ).reindex(target.index)
    pred = predict_demeaned(x, v, fit, 2025).reindex(target.index)
    naive = x[2024].reindex(target.index)
    naive_official = official_2024 - official_2024.mean()

    def score(p: pd.Series) -> dict[str, float]:
        return {
            "mae_pp": float((p - target).abs().mean()),
            "rmse_pp": float(((p - target) ** 2).mean() ** 0.5),
            "corr": float(np.corrcoef(p, target)[0, 1]) if p.std() > 0 else 0.0,
        }

    return {
        "n_states": len(target),
        "semantics": (
            "latent-rate predictions scored against the measured official "
            "series; descriptive of this single cross-scale transition, "
            "not a clean model comparison"
        ),
        "shrinkage_prediction": score(pred),
        "naive_fy2024_carryforward": score(naive),
        "official_fy2024_carryforward": score(naive_official),
        "national_mean_only": score(pd.Series(0.0, index=target.index)),
        "per_state": {
            s: {
                "predicted_demeaned_pp": round(float(pred[s]), 4),
                "official_fy2025_demeaned_pp": round(float(target[s]), 4),
            }
            for s in target.index
        },
    }


def exposure(
    x: pd.DataFrame,
    v: pd.DataFrame,
    fit: dict[str, float],
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Multi-year cost-share exposure per state on the 2013(a)(2) tiers.

    Measured-rate draws for each horizon year: the state's conditional
    demeaned true-rate path given its reconstructed history (alpha +
    AR(1) u), plus a sampling draw at the state's FY2024 bootstrap SD
    (the movement memo's proxy convention). Levels are set by a LOCATION
    CALIBRATION: the whole path translates so the FY2025 point
    prediction equals the FY2025 official rate. This deliberately
    preserves the history-only conditional dispersion — including
    latent FY2025 uncertainty and its covariance with later years — and
    does NOT condition on the FY2025 official observation, whose
    observation variance on the official scale this model does not
    carry. Future national means are held at FY2025 (no national
    forecast). Cost share is percent of issuance; dollar exposure is
    that share times a sourced issuance.
    """
    movement = json.loads(MOVEMENT_PATH.read_text())
    official_2025 = {row["state"]: row["fy2025"] for row in movement["states"]}
    sampling_sd = {
        row["state"]: row["sampling_sd_fy2024_pp"] for row in movement["states"]
    }
    years = list(x.columns)
    a, b, rho = fit["sigma_alpha_sq"], fit["sigma_u_sq"], fit["rho"]
    horizon = [2025, *EXPOSURE_YEARS]
    results: dict[str, Any] = {}
    for state in x.index:
        if state not in official_2025:
            continue
        cov_hist = _state_covariance(years, fit, v.loc[state])
        t_hist = np.array(years, dtype=float)
        t_new = np.array(horizon, dtype=float)
        cross = a + b * rho ** np.abs(t_new[:, None] - t_hist[None, :])
        cov_new = a + b * rho ** np.abs(t_new[:, None] - t_new[None, :])
        solve = np.linalg.solve(cov_hist, cross.T)
        mean_new = solve.T @ x.loc[state].to_numpy()
        cond_cov = cov_new - cross @ solve
        cond_cov = (cond_cov + cond_cov.T) / 2
        min_eig = float(np.linalg.eigvalsh(cond_cov).min())
        assert min_eig > -1e-8, f"conditional covariance not PSD: {min_eig}"
        chol = np.linalg.cholesky(cond_cov + 1e-9 * np.eye(len(horizon)))
        draws = mean_new + rng.standard_normal((EXPOSURE_DRAWS, len(horizon))) @ chol.T
        # Location calibration (translation only; dispersion unchanged).
        anchored = official_2025[state] + draws - mean_new[0]
        sd = sampling_sd[state]
        by_year: dict[str, Any] = {}
        share_paths = np.zeros((EXPOSURE_DRAWS, len(EXPOSURE_YEARS)))
        for j, year in enumerate(EXPOSURE_YEARS):
            unclipped = anchored[:, j + 1] + rng.standard_normal(EXPOSURE_DRAWS) * sd
            measured = np.clip(unclipped, 0.0, None)
            clipped_mass = float((unclipped < 0.0).mean())
            shares = np.array([tier_of(r) for r in measured], dtype=float)
            share_paths[:, j] = shares
            by_year[str(year)] = {
                "mean_rate": round(float(measured.mean()), 3),
                "sd_rate": round(float(measured.std()), 3),
                "p_tier": {
                    str(s): round(float((shares == s).mean()), 4)
                    for s in (0, 5, 10, 15)
                },
                "expected_share_pct": round(float(shares.mean()), 3),
                "p_clipped_at_zero": round(clipped_mass, 4),
            }
        results[state] = {
            "fy2025_official_anchor": official_2025[state],
            "sampling_sd_pp": sd,
            "years": by_year,
            "expected_share_pct_3yr_sum": round(
                float(share_paths.sum(axis=1).mean()), 3
            ),
        }
    return results


def state_bootstrap(
    x: pd.DataFrame, v: pd.DataFrame, rng: np.random.Generator
) -> dict[str, Any]:
    """Percentile intervals by resampling states with replacement.

    Conditional on the estimated cell sampling variances: the state
    resample propagates cross-state uncertainty only, not the per-cell
    microdata bootstrap's own noise.
    """
    fits = []
    states = list(x.index)
    for _ in range(STATE_BOOTSTRAP_REPS):
        sample = rng.choice(len(states), size=len(states), replace=True)
        xs = x.iloc[sample].reset_index(drop=True)
        vs = v.iloc[sample].reset_index(drop=True)
        xs = xs.sub(xs.mean(axis=0), axis=1)
        c, counts, mean_v = autocovariances(xs, vs)
        fits.append(fit_components(c, counts, mean_v))
    frame = pd.DataFrame(fits)
    return {
        key: {
            "p2_5": round(float(frame[key].quantile(0.025)), 4),
            "p97_5": round(float(frame[key].quantile(0.975)), 4),
        }
        for key in ("sigma_alpha_sq", "sigma_u_sq", "rho")
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_artifact() -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    wide = build_rate_panel()
    v = cell_sampling_variances(rng)
    v = v.reindex(index=wide.index, columns=wide.columns)
    assert not v.isna().any().any()
    x = demean_by_year(wide)
    c, counts, mean_v = autocovariances(x, v)
    fit = fit_components(c, counts, mean_v)
    total_process = fit["sigma_alpha_sq"] + fit["sigma_u_sq"]
    reliability = {
        state: round(float(total_process / (total_process + v.loc[state].mean())), 4)
        for state in x.index
    }
    validation = validate_fy2025(x, v, fit)
    exposures = exposure(x, v, fit, rng)
    intervals = state_bootstrap(x, v, rng)

    artifact = {
        "method": "year-demeaned method-of-moments variance decomposition; "
        "state FE + AR(1) process + bootstrap-estimated heteroskedastic "
        "sampling layer",
        "years_used": list(YEARS_USED),
        "years_dropped": {"2021": "pandemic-partial per coding audit"},
        "outcome": "total_error_rate (reconstructed, fixed real threshold)",
        "n_states": len(x),
        "moments": {
            "lags": list(range(MAX_LAG + 1)),
            "mean_products_pp2": [round(float(val), 4) for val in c],
            "pair_counts": [int(n) for n in counts],
            "mean_sampling_variance_pp2": round(mean_v, 4),
        },
        "fit": {
            "sigma_alpha_sq_pp2": round(fit["sigma_alpha_sq"], 4),
            "sigma_u_sq_pp2": round(fit["sigma_u_sq"], 4),
            "rho": fit["rho"],
            "untruncated_lag0_component_pp2": round(
                fit["untruncated_lag0_component"], 4
            ),
            "persistent_share_of_process_variance": round(
                fit["sigma_alpha_sq"] / total_process, 4
            )
            if total_process > 0
            else None,
        },
        "state_bootstrap_95_conditional_on_cell_variances": intervals,
        "single_year_reliability": reliability,
        "fy2025_validation": validation,
        "exposure_fy2028_30": exposures,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "seed": SEED,
        },
        "input_hashes": {
            "coding_consistency": _sha256_file(event_study.AUDIT_PATH),
            "fy2025_movement": _sha256_file(MOVEMENT_PATH),
            "raw_by_fiscal_year": {
                str(year): json.loads(event_study.AUDIT_PATH.read_text())["years"][
                    str(year)
                ]["source"]["sha256"]
                for year in YEARS_USED
            },
        },
    }
    return artifact


def main() -> None:
    artifact = compute_artifact()
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    MEMO_OUT.write_text(_memo(artifact))
    print(f"wrote {OUT} and {MEMO_OUT}")


def _memo(a: dict[str, Any]) -> str:
    fit = a["fit"]
    val = a["fy2025_validation"]
    lines = [
        "<!-- Generated by analysis/persistence.py; do not edit manually. -->",
        "",
        "# State persistence of payment error rates, FY2012-24",
        "",
        (
            "The year-demeaned reconstructed total error rate splits into a "
            f"persistent state component of **{fit['sigma_alpha_sq_pp2']}pp^2**, "
            f"a transitory AR(1) component of **{fit['sigma_u_sq_pp2']}pp^2** "
            f"(rho = {fit['rho']}), and a bootstrap-estimated sampling layer "
            f"averaging {a['moments']['mean_sampling_variance_pp2']}pp^2 per "
            "state-year. The persistent share of process variance is "
            f"**{fit['persistent_share_of_process_variance']}**."
        ),
        "",
        (
            f"A cross-scale check scores latent-rate predictions against "
            f"the demeaned FY2025 official rates for "
            f"{val['n_states']} jurisdictions: shrinkage MAE "
            f"{val['shrinkage_prediction']['mae_pp']:.3f}pp "
            f"(corr {val['shrinkage_prediction']['corr']:.3f}), "
            f"reconstructed FY2024 carry-forward "
            f"{val['naive_fy2024_carryforward']['mae_pp']:.3f}pp, official "
            f"FY2024 carry-forward "
            f"{val['official_fy2024_carryforward']['mae_pp']:.3f}pp, "
            f"national mean alone "
            f"{val['national_mean_only']['mae_pp']:.3f}pp. The official "
            "target carries sampling and regression-adjustment noise the "
            "model does not observe, so these scores describe one "
            "transition across scales; they are not a clean model "
            "comparison."
        ),
        "",
        (
            "State history predicts — every history-based predictor beats "
            "the national mean by about a point — and no history-based "
            "predictor separates cleanly from the others on this single "
            "transition. The decomposition's value for the simulator is "
            "the dispersion: how wide a state's multi-year rate "
            "distribution is once process variance joins sampling "
            "variance. The exposure module sets levels by location "
            "calibration at the FY2025 official rate and deliberately "
            "keeps the history-only conditional dispersion."
        ),
        "",
        "## Assumptions and caveats",
        "",
        (
            "- The outcome is the reconstructed rate at a fixed real "
            "counted-error threshold, not the official regression-adjusted "
            "rate; validation compares relative (demeaned) positions across "
            "the two scales."
        ),
        (
            "- FY2021 is dropped as pandemic-partial; FY2020 stays, so any "
            "pandemic distortion in FY2020 loads into the transitory "
            "component."
        ),
        (
            "- Year demeaning treats the 53 jurisdictions as exchangeable and "
            "absorbs national methodology changes; state-specific methodology "
            "changes load into the process components."
        ),
        (
            "- Sampling draws are independent across years; the AR(1) form is "
            "an assumption, checked only against lags up to "
            f"{a['moments']['lags'][-1]}."
        ),
        (
            "- Exposure simulations hold future national means at FY2025 and "
            "use FY2024 bootstrap sampling SDs as the future sampling proxy; "
            "they price the measurement process, not policy or caseload "
            "change."
        ),
        "",
        (
            "Full parameters, per-state reliabilities, FY2025 validation "
            "detail, and FY2028-30 tier exposures are in "
            "`analysis/persistence_results.json`."
        ),
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
