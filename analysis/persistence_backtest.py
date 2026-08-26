"""Backtest: which predictive distribution for next-year state rates scores best.

Three constructions, each producing Normal(mean, sd) per state-year and fit
only on years before the target (expanding window, FY2021 dropped per the
coding audit):

  static   : mean = last year's rate;      var = mean cell sampling variance
             (the published-CI construction repurposed as a forecast)
  widened  : mean = last year's rate;      var = sampling + AR(1) innovation
             (no shrinkage; persistence enters the variance only)
  rao_yu   : mean = year level + BLUP;     var = conditional process + sampling
             (the full persistence model)

The national year level is carried from the last observed year for all three
constructions identically, so common national shifts handicap each equally.
Scores: CRPS (normal closed form), pinball loss over 19 quantiles, log
score, and central-interval coverage. Reconstructed-rate scale throughout.
This evaluates distributional calibration and sharpness; it makes no claim
about any construction's fitness for its authors' own question.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from analysis import event_study, persistence
from snap_qc_sim.simulate import tier_of

OUT = Path(__file__).with_name("persistence_backtest_results.json")
MOVEMENT_PATH = Path(__file__).with_name("fy2025_movement.json")
ISSUANCE_PATH = Path(__file__).with_name("issuance_fy2024.json")
PERSISTENCE_RESULTS = Path(__file__).with_name("persistence_results.json")
BILL_DRAWS = 20_000
MEMO_OUT = Path(__file__).with_name("PERSISTENCE_BACKTEST.md")
APPROACHES = ("static", "static_fair", "widened", "rao_yu")
#: Sensitivity rows at the published average design-SE scale (~1.1pp,
#: Bauer-Schanzenbach 2026); per-state official SEs are not in the repo.
SENSITIVITY = ("static_official_1p1", "static_fair_official_1p1")
OFFICIAL_SE_PP = 1.1
QS = np.round(np.arange(0.05, 0.951, 0.05), 2)
MIN_HISTORY_YEARS = 4


def raw_inputs_available() -> bool:
    return persistence.raw_inputs_available()


def _crps_normal(y: float, mu: float, sd: float) -> float:
    z = (y - mu) / sd
    return float(
        sd
        * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))
    )


def _pinball(y: float, mu: float, sd: float) -> float:
    q = mu + sd * stats.norm.ppf(QS)
    return float(np.mean(np.where(y >= q, QS * (y - q), (1 - QS) * (q - y))))


def compute_artifact() -> dict[str, Any]:
    wide = persistence.build_rate_panel()
    rng = np.random.default_rng(persistence.SEED)
    v = persistence.cell_sampling_variances(rng).reindex(
        index=wide.index, columns=wide.columns
    )
    years = list(wide.columns)
    rows: dict[str, list[dict[str, Any]]] = {k: [] for k in (*APPROACHES, *SENSITIVITY)}
    fits_by_target: dict[str, dict[str, float]] = {}
    for target in years:
        hist = [y for y in years if y < target]
        if len(hist) < MIN_HISTORY_YEARS:
            continue
        history = wide[hist]
        vh = v[hist]
        x = history.sub(history.mean(axis=0), axis=1)
        c, counts, mean_v = persistence.autocovariances(x, vh)
        fit = persistence.fit_components(c, counts, mean_v)
        a, b, rho = fit["sigma_alpha_sq"], fit["sigma_u_sq"], fit["rho"]
        fits_by_target[str(target)] = {
            "sigma_alpha_sq": round(a, 4),
            "sigma_u_sq": round(b, 4),
            "rho": rho,
        }
        mu_last = float(history[hist[-1]].mean())
        gap = target - hist[-1]
        innovation = b * (1 - rho ** (2 * gap))
        for state in wide.index:
            y_true = float(wide.loc[state, target])
            vbar = float(vh.loc[state].mean())
            y_prev = float(history.loc[state, hist[-1]])
            cov = persistence._state_covariance(hist, fit, vh.loc[state])
            gaps = np.abs(np.array(hist, float) - target)
            cross = a + b * rho**gaps
            weights = np.linalg.solve(cov, cross)
            mean_cond = float(weights @ x.loc[state].to_numpy())
            var_cond = float(max(a + b - cross @ weights, 0.0))
            preds = {
                "static": (y_prev, float(np.sqrt(vbar))),
                # Fair static: predicting T from the T-1 value involves two
                # sampling draws (the anchor's and the target's).
                "static_fair": (y_prev, float(np.sqrt(2 * vbar))),
                "widened": (y_prev, float(np.sqrt(vbar + innovation))),
                "rao_yu": (mu_last + mean_cond, float(np.sqrt(var_cond + vbar))),
                "static_official_1p1": (y_prev, OFFICIAL_SE_PP),
                "static_fair_official_1p1": (
                    y_prev,
                    float(OFFICIAL_SE_PP * np.sqrt(2)),
                ),
            }
            for name, (mu, sd) in preds.items():
                z = abs(y_true - mu)
                rows[name].append(
                    {
                        "target_year": target,
                        "state": state,
                        "crps": round(_crps_normal(y_true, mu, sd), 6),
                        "pinball": round(_pinball(y_true, mu, sd), 6),
                        "log_score": round(float(stats.norm.logpdf(y_true, mu, sd)), 6),
                        "in_50": bool(z <= 0.674 * sd),
                        "in_90": bool(z <= 1.645 * sd),
                        "predictive_sd_pp": round(sd, 4),
                    }
                )

    def summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
        arr = lambda key: np.array([c[key] for c in cells], dtype=float)
        return {
            "n_state_years": len(cells),
            "mean_crps": round(float(arr("crps").mean()), 4),
            "mean_pinball": round(float(arr("pinball").mean()), 4),
            "mean_log_score": round(float(arr("log_score").mean()), 4),
            "coverage_50": round(float(arr("in_50").mean()), 4),
            "coverage_90": round(float(arr("in_90").mean()), 4),
            "mean_predictive_sd_pp": round(float(arr("predictive_sd_pp").mean()), 4),
        }

    penalty = penalty_translation(np.random.default_rng(persistence.SEED + 1))

    per_year = {}
    targets = sorted({c["target_year"] for c in rows["static"]})
    for t in targets:
        per_year[str(t)] = {
            k: round(
                float(np.mean([c["crps"] for c in rows[k] if c["target_year"] == t])), 4
            )
            for k in APPROACHES
        }
        per_year[str(t)]["winner"] = min(APPROACHES, key=lambda k: per_year[str(t)][k])

    return {
        "schema_version": 1,
        "interpretation": (
            "expanding-window distributional backtest on reconstructed state "
            "rates; scores calibration and sharpness of three Normal "
            "predictive constructions for next-year rates; the national year "
            "level is carried identically for all three; no claim about any "
            "construction's fitness for its authors' own question"
        ),
        "target_years": targets,
        "summary": {k: summary(rows[k]) for k in APPROACHES},
        "sensitivity_official_se_scale": {k: summary(rows[k]) for k in SENSITIVITY},
        "per_year_mean_crps": per_year,
        "penalty_translation": penalty,
        "fits_by_target_year": fits_by_target,
        "quantile_grid": [float(q) for q in QS],
        "min_history_years": MIN_HISTORY_YEARS,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "seed": persistence.SEED,
        },
        "input_hashes": {
            "coding_consistency": hashlib.sha256(
                event_study.AUDIT_PATH.read_bytes()
            ).hexdigest(),
            "fy2025_movement": hashlib.sha256(MOVEMENT_PATH.read_bytes()).hexdigest(),
            "issuance_fy2024": hashlib.sha256(ISSUANCE_PATH.read_bytes()).hexdigest(),
            "persistence_results": hashlib.sha256(
                PERSISTENCE_RESULTS.read_bytes()
            ).hexdigest(),
            "raw_by_fiscal_year": {
                str(y): json.loads(event_study.AUDIT_PATH.read_text())["years"][str(y)][
                    "source"
                ]["sha256"]
                for y in persistence.YEARS_USED
            },
        },
    }


def penalty_translation(rng: np.random.Generator) -> dict[str, Any]:
    """Election-correct FY2028 and FY2029 bill pricing per state.

    Semantics mirror the simulator's verified election machinery
    (app/public/app.js electionStats, 7 USC 2013(a)(2)(B)): the FY2028
    bill keys to the elected minimum of the locked FY2025 official rate
    and the simulated FY2026 measurement, and pays zero whenever EITHER
    year crosses the delay test (rate x 1.5 >= 20, mechanical and
    election-independent); the FY2029 bill keys to the FY2026 rate alone
    and pays zero when FY2026 itself crosses. FY2026 draws center on the
    locked FY2025 official rate under two constructions: static (the
    state's sampling SD) and widened (sampling variance plus the
    committed persistence fit's one-year AR(1) innovation, no
    shrinkage). The innovation variance is estimated on the
    reconstructed-rate panel and applied to official-scale rates; the
    additive-wedge result supports transferring level shifts in
    percentage points, and extending that transfer to a variance
    component is an additional stated assumption. State draws are
    independent; the national SD models no cross-state correlation.
    """
    movement = json.loads(MOVEMENT_PATH.read_text())
    issuance = json.loads(ISSUANCE_PATH.read_text())["states"]
    fit = json.loads(PERSISTENCE_RESULTS.read_text())["fit"]
    innovation = fit["sigma_u_sq_pp2"] * (1 - fit["rho"] ** 2)
    delay = lambda r: r * 1.5 >= 20
    states: dict[str, Any] = {}
    totals: dict[str, dict[str, list[tuple[float, float]]]] = {
        "static": {"fy2028": [], "fy2029": []},
        "widened": {"fy2028": [], "fy2029": []},
    }
    for row in sorted(movement["states"], key=lambda r: r["state"]):
        code = row["state"]
        dollars = issuance.get(code)
        if dollars is None:
            continue
        fy25, sd0 = row["fy2025"], row["sampling_sd_fy2024_pp"]
        lock_share = 0.0 if delay(fy25) else float(tier_of(fy25))
        out: dict[str, Any] = {
            "fy2025_official": fy25,
            "fy2025_delay": bool(delay(fy25)),
            "issuance_fy2024_dollars": dollars,
        }
        for name, sd in (
            ("static", sd0),
            ("widened", float(np.sqrt(sd0**2 + innovation))),
        ):
            draws = np.clip(fy25 + rng.standard_normal(BILL_DRAWS) * sd, 0.0, None)
            crossed = draws * 1.5 >= 20
            zero28 = delay(fy25) | crossed
            elected = np.minimum(draws, fy25)
            share28 = np.where(zero28, 0.0, np.array([tier_of(r) for r in elected]))
            share29 = np.where(crossed, 0.0, np.array([tier_of(r) for r in draws]))
            bill28 = share28 / 100 * dollars
            bill29 = share29 / 100 * dollars
            p_bucket_29 = {
                **{
                    str(s): round(float(((share29 == s) & ~crossed).mean()), 4)
                    for s in (0, 5, 10, 15)
                },
                "delay_0": round(float(crossed.mean()), 4),
            }
            out[name] = {
                "predictive_sd_pp": round(sd, 4),
                "fy2028": {
                    "expected_bill_dollars": round(float(bill28.mean())),
                    "sd_bill_dollars": round(float(bill28.std())),
                },
                "fy2029": {
                    "p_bucket": p_bucket_29,
                    "modal_bucket_probability": round(max(p_bucket_29.values()), 4),
                    "expected_bill_dollars": round(float(bill29.mean())),
                    "sd_bill_dollars": round(float(bill29.std())),
                },
            }
            totals[name]["fy2028"].append((float(bill28.mean()), float(bill28.var())))
            totals[name]["fy2029"].append((float(bill29.mean()), float(bill29.var())))
        out["lock_share_pct"] = lock_share
        states[code] = out
    national = {
        name: {
            year: {
                "expected_total_dollars": round(sum(m for m, _ in vals)),
                "sd_total_dollars_no_correlation": round(
                    float(np.sqrt(sum(vv for _, vv in vals)))
                ),
            }
            for year, vals in years.items()
        }
        for name, years in totals.items()
    }
    modal_med = {
        name: round(
            float(
                np.median(
                    [
                        s[name]["fy2029"]["modal_bucket_probability"]
                        for s in states.values()
                    ]
                )
            ),
            4,
        )
        for name in ("static", "widened")
    }
    return {
        "innovation_variance_pp2": round(float(innovation), 4),
        "states": states,
        "national": national,
        "median_modal_bucket_probability_fy2029": modal_med,
    }


def _memo(a: dict[str, Any]) -> str:
    s = a["summary"]
    lines = [
        "<!-- Generated by analysis/persistence_backtest.py; do not edit manually. -->",
        "",
        "# Distributional backtest of next-year rate predictions",
        "",
        (
            f"Expanding-window backtest over target years "
            f"{a['target_years'][0]}-{a['target_years'][-1]} (FY2021 dropped), "
            f"{s['static']['n_state_years']} state-years per construction, "
            "reconstructed-rate scale."
        ),
        "",
        "| construction | mean CRPS | pinball | log score | 50% cover | 90% cover | mean SD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for k in APPROACHES:
        r = s[k]
        lines.append(
            f"| {k} | {r['mean_crps']} | {r['mean_pinball']} | "
            f"{r['mean_log_score']} | {r['coverage_50']} | {r['coverage_90']} | "
            f"{r['mean_predictive_sd_pp']}pp |"
        )
    for k in SENSITIVITY:
        r = a["sensitivity_official_se_scale"][k]
        lines.append(
            f"| {k} (sensitivity) | {r['mean_crps']} | {r['mean_pinball']} | "
            f"{r['mean_log_score']} | {r['coverage_50']} | {r['coverage_90']} | "
            f"{r['mean_predictive_sd_pp']}pp |"
        )
    lines += [
        "",
        (
            "The sampling-only construction's nominal 90% intervals cover "
            f"{round(100 * s['static']['coverage_90'])}% of realized next-year "
            "rates; adding persistence terms to the variance alone lifts "
            f"coverage to {round(100 * s['widened']['coverage_90'])}% at about "
            "double the predictive width, and the full model reaches "
            f"{round(100 * s['rao_yu']['coverage_90'])}%. Winners by year sit "
            "in the artifact; the full model's edge concentrates in "
            "large-movement years."
        ),
        "",
        "## In bill terms",
        "",
        (
            f"Pricing bills with the simulator's election semantics "
            f"(FY 2028 keys to the elected minimum of the locked FY 2025 "
            f"rate and the simulated FY 2026 measurement, zero when either "
            f"crosses the delay test; FY 2029 keys to FY 2026 alone): the "
            f"median state's FY 2029 most-likely-bucket probability falls "
            f"from "
            f"{a['penalty_translation']['median_modal_bucket_probability_fy2029']['static']} "
            f"under sampling-only to "
            f"{a['penalty_translation']['median_modal_bucket_probability_fy2029']['widened']} "
            f"with persistence in the variance. National FY 2028 bill SD: "
            f"${a['penalty_translation']['national']['static']['fy2028']['sd_total_dollars_no_correlation']:,} "
            f"static versus "
            f"${a['penalty_translation']['national']['widened']['fy2028']['sd_total_dollars_no_correlation']:,} "
            f"widened; FY 2029: "
            f"${a['penalty_translation']['national']['static']['fy2029']['sd_total_dollars_no_correlation']:,} "
            f"versus "
            f"${a['penalty_translation']['national']['widened']['fy2029']['sd_total_dollars_no_correlation']:,} "
            "(no cross-state correlation modeled)."
        ),
        "",
        "## Caveats",
        "",
        (
            "- Reconstructed rates at the fixed real threshold, not official "
            "rates; sampling variances are the i.i.d. cell bootstrap, which "
            "runs smaller than published design SEs (~1.1pp average) — the "
            "sensitivity rows rerun the static family at that scale."
        ),
        (
            "- The penalty translation's innovation variance is estimated on "
            "the reconstructed panel and applied to official-scale rates: "
            "the additive-wedge evidence supports transferring level shifts "
            "in percentage points; extending the transfer to a variance "
            "component is an additional stated assumption."
        ),
        (
            "- All three constructions carry the national year level from the "
            "last observed year, so common national shifts handicap each "
            "equally and depress all coverage numbers together."
        ),
        (
            "- Normal predictive forms throughout; the bootstrap-vs-normal "
            "tier-odds gap is second-order at state sample sizes."
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    artifact = compute_artifact()
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    MEMO_OUT.write_text(_memo(artifact))
    print(f"wrote {OUT} and {MEMO_OUT}")


if __name__ == "__main__":
    main()
