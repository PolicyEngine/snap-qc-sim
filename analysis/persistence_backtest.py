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
APPROACHES = ("static", "widened", "rao_yu")
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
    rows: dict[str, list[dict[str, Any]]] = {k: [] for k in APPROACHES}
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
                "widened": (y_prev, float(np.sqrt(vbar + innovation))),
                "rao_yu": (mu_last + mean_cond, float(np.sqrt(var_cond + vbar))),
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
    """What the calibration gap means in FY2028 bill terms, per state.

    Each construction centers on the FY2025 official rate (location only)
    and draws a next-measured-rate distribution: static uses the state's
    sampling SD alone; widened adds the committed persistence fit's
    one-year AR(1) innovation to the variance (no shrinkage). Draws map
    through the 7 USC 2013(a)(2) shares with the delay rule (rate x 1.5
    >= 20 pays zero in the first billed year) times official FY2024
    issuance. Percentage points transfer across the reconstructed and
    official scales under the empirically supported additive-wedge
    convention. State draws are independent; the national SD carries no
    cross-state process correlation and is a lower bound in that respect.
    """
    movement = json.loads(MOVEMENT_PATH.read_text())
    issuance = json.loads(ISSUANCE_PATH.read_text())["states"]
    fit = json.loads(PERSISTENCE_RESULTS.read_text())["fit"]
    innovation = fit["sigma_u_sq_pp2"] * (1 - fit["rho"] ** 2)
    shares_grid = (0, 5, 10, 15)
    states: dict[str, Any] = {}
    totals = {"static": [], "widened": []}
    for row in sorted(movement["states"], key=lambda r: r["state"]):
        code = row["state"]
        dollars = issuance.get(code)
        if dollars is None:
            continue
        anchor, sd0 = row["fy2025"], row["sampling_sd_fy2024_pp"]
        out: dict[str, Any] = {
            "fy2025_official": anchor,
            "issuance_fy2024_dollars": dollars,
        }
        for name, sd in (
            ("static", sd0),
            ("widened", float(np.sqrt(sd0**2 + innovation))),
        ):
            draws = np.clip(anchor + rng.standard_normal(BILL_DRAWS) * sd, 0.0, None)
            shares = np.array(
                [0.0 if r * 1.5 >= 20 else float(tier_of(r)) for r in draws]
            )
            bills = shares / 100 * dollars
            p_bucket = {
                **{
                    str(s): round(
                        float(((shares == s) & ~(draws * 1.5 >= 20)).mean()), 4
                    )
                    for s in shares_grid
                },
                "delay_0": round(float((draws * 1.5 >= 20).mean()), 4),
            }
            # a zero-share draw is either below 6 or delayed; report modal prob over the 5 buckets
            modal = max(p_bucket.values())
            out[name] = {
                "predictive_sd_pp": round(sd, 4),
                "p_bucket": p_bucket,
                "modal_bucket_probability": round(modal, 4),
                "expected_bill_dollars": round(float(bills.mean())),
                "sd_bill_dollars": round(float(bills.std())),
            }
            totals[name].append((float(bills.mean()), float(bills.var())))
        states[code] = out
    national = {
        name: {
            "expected_total_dollars": round(sum(m for m, _ in vals)),
            "sd_total_dollars_independent": round(
                float(np.sqrt(sum(vv for _, vv in vals)))
            ),
        }
        for name, vals in totals.items()
    }
    modal_med = {
        name: round(
            float(
                np.median(
                    [s[name]["modal_bucket_probability"] for s in states.values()]
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
        "median_modal_bucket_probability": modal_med,
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
            f"Centering every state on its FY 2025 official rate and pricing "
            f"the FY 2028 bill (delay-aware, official FY 2024 issuance): the "
            f"median state's most-likely-bucket probability falls from "
            f"{a['penalty_translation']['median_modal_bucket_probability']['static']} "
            f"under sampling-only to "
            f"{a['penalty_translation']['median_modal_bucket_probability']['widened']} "
            f"with persistence in the variance, and the national bill SD "
            f"rises from "
            f"${a['penalty_translation']['national']['static']['sd_total_dollars_independent']:,} "
            f"to "
            f"${a['penalty_translation']['national']['widened']['sd_total_dollars_independent']:,} "
            "(independent state draws; cross-state process correlation would "
            "raise the widened figure further)."
        ),
        "",
        "## Caveats",
        "",
        (
            "- Reconstructed rates at the fixed real threshold, not official "
            "rates; sampling variances are the i.i.d. cell bootstrap."
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
