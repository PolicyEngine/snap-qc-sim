"""Hurdle deviation model + state calibration gate (v2a stage 2).

Target: D = RAWBEN - FSBEN (assigned minus true). Three parts:
  1. P(deviate)            = P(|D| > 0)            — classifier
  2. P(cross | deviate)    = P(|D| > threshold)    — classifier
  3. E[|D| | cross]                                — regressor on log|D|

Composition per case: E[error dollars] = P1 * P2 * E[|D| | cross]; the
state-level predicted dollar-weighted rate is the weighted sum over the
FY2024 holdout divided by weighted issuance. The calibration gate compares
predicted vs observed FY2024 rates per state — the simulator must
reproduce reality at baseline before any counterfactual is trusted.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import roc_auc_score

from train_error_model import (
    COVARIATES,
    INTERMEDIATES,
    SMD_DOC,
    THRESHOLD,
    YEARS_TRAIN,
    YEAR_TEST,
    build_features,
    load_year,
)

OUT = Path(__file__).with_name("hurdle_results.json")


def assemble() -> pd.DataFrame:
    frames = []
    for y in YEARS_TRAIN + [YEAR_TEST]:
        df = load_year(y)
        f = build_features(df, SMD_DOC[y])
        f["D"] = df["RAWBEN"].fillna(0).to_numpy() - df["FSBEN"].fillna(0).to_numpy()
        f["fsben"] = df["FSBEN"].fillna(0).to_numpy()
        f["issuance"] = df["RAWBEN"].fillna(0).to_numpy()
        f["thr"] = f["year"].map(THRESHOLD)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    data = assemble()
    data["deviates"] = (data["D"].abs() > 0.5).astype(int)
    data["crosses"] = (data["D"].abs() > data["thr"]).astype(int)
    feats = COVARIATES + INTERMEDIATES + ["fsben"]

    train = data[data["year"] != YEAR_TEST]
    test = data[data["year"] == YEAR_TEST].copy()
    print(f"train {len(train):,} ({train['deviates'].mean():.1%} deviate, "
          f"{train['crosses'].mean():.1%} cross), test {len(test):,} "
          f"({test['deviates'].mean():.1%} / {test['crosses'].mean():.1%})")

    def gbm_cls():
        return HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=63, random_state=7
        )

    # Stage 1: any deviation.
    m1 = gbm_cls()
    m1.fit(train[feats], train["deviates"], sample_weight=train["w"])
    p1 = m1.predict_proba(test[feats])[:, 1]
    print(f"stage 1 P(deviate):        AUC "
          f"{roc_auc_score(test['deviates'], p1, sample_weight=test['w']):.4f}")

    # Stage 2: crossing the official threshold, among deviators.
    dev_tr = train[train["deviates"] == 1]
    m2 = gbm_cls()
    m2.fit(dev_tr[feats], dev_tr["crosses"], sample_weight=dev_tr["w"])
    p2 = m2.predict_proba(test[feats])[:, 1]
    dev_te = test[test["deviates"] == 1]
    auc2 = roc_auc_score(
        dev_te["crosses"], m2.predict_proba(dev_te[feats])[:, 1],
        sample_weight=dev_te["w"],
    )
    print(f"stage 2 P(cross|deviate):  AUC {auc2:.4f} (scored among deviators)")

    # Stage 3: magnitude given crossing.
    cross_tr = train[train["crosses"] == 1]
    m3 = HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.08, max_leaf_nodes=63, random_state=7
    )
    m3.fit(cross_tr[feats], np.log(cross_tr["D"].abs()),
           sample_weight=cross_tr["w"])
    # Duan smearing: exp(E[log|D|]) understates E[|D|]; multiply by the
    # weighted mean of exponentiated training residuals.
    resid = np.log(cross_tr["D"].abs()) - m3.predict(cross_tr[feats])
    smear = float(np.average(np.exp(resid), weights=cross_tr["w"]))
    print(f"Duan smearing factor: {smear:.3f}")
    mag = np.exp(m3.predict(test[feats])) * smear
    cross_te = test[test["crosses"] == 1]
    mag_te = np.exp(m3.predict(cross_te[feats])) * smear
    print(f"stage 3 E[|D| | cross]:    observed mean "
          f"${np.average(cross_te['D'].abs(), weights=cross_te['w']):.0f}, "
          f"predicted mean ${np.average(mag_te, weights=cross_te['w']):.0f}")

    # Compose expected error dollars per case; calibrate by state.
    test["pred_err_dollars"] = p1 * p2 * mag
    test["obs_err_dollars"] = test["D"].abs() * test["crosses"]
    rows = []
    for st, g in test.groupby("state"):
        iss = (g["w"] * g["issuance"]).sum()
        if iss <= 0 or len(g) < 200:
            continue
        pred = 100 * (g["w"] * g["pred_err_dollars"]).sum() / iss
        obs = 100 * (g["w"] * g["obs_err_dollars"]).sum() / iss
        rows.append({"state": st, "n": len(g), "pred_rate": pred, "obs_rate": obs})
    cal = pd.DataFrame(rows).sort_values("obs_rate", ascending=False)
    # State baseline calibration factors (the anchoring the simulator will
    # apply): ratio of observed to predicted at baseline. The model then
    # carries within-state gradients and counterfactual deltas.
    cal["state_factor"] = cal["obs_rate"] / cal["pred_rate"]
    print(f"state calibration factors: median "
          f"{cal['state_factor'].median():.2f}, "
          f"IQR {cal['state_factor'].quantile(0.25):.2f}-"
          f"{cal['state_factor'].quantile(0.75):.2f}, "
          f"max {cal['state_factor'].max():.2f} ({cal.loc[cal['state_factor'].idxmax(), 'state']})")
    corr = cal["pred_rate"].corr(cal["obs_rate"])
    mae = (cal["pred_rate"] - cal["obs_rate"]).abs().mean()
    slope = np.polyfit(cal["pred_rate"], cal["obs_rate"], 1)[0]
    print(f"\n== state calibration, FY2024 holdout ({len(cal)} states) ==")
    print(f"corr {corr:.3f}, MAE {mae:.2f}pp, slope {slope:.2f}")
    print(f"{'state':<7}{'observed':>9}{'predicted':>10}{'gap':>7}")
    for _, r in cal.head(8).iterrows():
        print(f"{r['state']:<7}{r['obs_rate']:>8.2f}%{r['pred_rate']:>9.2f}%"
              f"{r['pred_rate'] - r['obs_rate']:>+6.1f}")
    worst = cal.assign(gap=(cal["pred_rate"] - cal["obs_rate"]).abs()).nlargest(5, "gap")
    print("largest misses:",
          [(r["state"], f"{r['pred_rate'] - r['obs_rate']:+.1f}pp") for _, r in worst.iterrows()])

    json.dump({
        "stage1_auc": float(roc_auc_score(test["deviates"], p1, sample_weight=test["w"])),
        "stage2_auc_among_deviators": float(auc2),
        "calibration_corr": float(corr),
        "calibration_mae_pp": float(mae),
        "calibration_slope": float(slope),
        "states": cal.to_dict("records"),
    }, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
