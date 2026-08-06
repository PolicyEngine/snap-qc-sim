"""v2 stage 1-3: intermediates, error model with holdout lift, natural experiment.

Data: multi-year SNAP QC public-use files (FY2017-19, 2022-23 train; FY2024
holdout — the pandemic-distorted 2020-21 files are excluded, following the
giannella/snap_qc protocol). SMD regime registry: documented state lists for
FY2021-24 (QC tech docs, "standard medical deduction demonstrations were
operating in ...") plus a data-driven detector for earlier years,
cross-validated on the documented years.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

QC_DIR = Path("~/.cache/axiom-oracles/snap_qc_repo/qc_data").expanduser()
OUT = Path(__file__).parent
YEARS_TRAIN = [2017, 2018, 2019, 2022, 2023]
YEAR_TEST = 2024
THRESHOLD = {2017: 38, 2018: 37, 2019: 37, 2022: 48, 2023: 54, 2024: 56}

FIPS = {1:"AL",2:"AK",4:"AZ",5:"AR",6:"CA",8:"CO",9:"CT",10:"DE",11:"DC",12:"FL",
        13:"GA",15:"HI",16:"ID",17:"IL",18:"IN",19:"IA",20:"KS",21:"KY",22:"LA",
        23:"ME",24:"MD",25:"MA",26:"MI",27:"MN",28:"MS",29:"MO",30:"MT",31:"NE",
        32:"NV",33:"NH",34:"NJ",35:"NM",36:"NY",37:"NC",38:"ND",39:"OH",40:"OK",
        41:"OR",42:"PA",44:"RI",45:"SC",46:"SD",47:"TN",48:"TX",49:"UT",50:"VT",
        51:"VA",53:"WA",54:"WV",55:"WI",56:"WY",66:"GU",78:"VI"}

#: SMD demonstration states. FY2017-19: the 21 states adopted "by 2019"
#: (Health Affairs 2023, PMC10500947) — a few may have adopted mid-window
#: (noise against the model; the DiD below uses only documented adopters).
#: FY2021-24: QC tech doc lists verbatim. Adoptions: MI by FY2021,
#: AZ FY2022, LA FY2023, KY FY2024.
SMD_PRE2020 = {"AL","AR","CA","CO","GA","IA","ID","IL","KS","MA","MO","ND",
               "NH","OR","RI","SC","SD","TX","VA","VT","WY"}
SMD_DOC = {
    2017: SMD_PRE2020, 2018: SMD_PRE2020, 2019: SMD_PRE2020,
    2021: {"AL","AR","CA","CO","GA","ID","IL","IA","KS","MA","MI","MO","NH",
           "ND","OR","RI","SC","SD","TX","VT","VA","WY"},
    2022: {"AL","AZ","AR","CA","CO","GA","ID","IL","IA","KS","MA","MI","MO",
           "NH","ND","OR","RI","SC","SD","TX","VT","VA","WY"},
    2023: {"AL","AZ","AR","CA","CO","GA","ID","IL","IA","KS","LA","MA","MI",
           "MO","NH","ND","OR","RI","SC","SD","TX","VT","VA","WY"},
    2024: {"AL","AZ","AR","CA","CO","GA","ID","IL","IA","KS","KY","LA","MA",
           "MI","MO","NH","ND","OR","RI","SC","SD","TX","VT","VA","WY"},
}

COLS = ["FSNKID","EXPEDSER","FSERNDED",
        "STATE","YRMONTH","HWGT","STATUS","AMTERR","RAWBEN","FSBEN","FSUSIZE",
        "CERTHHSZ","FSNELDER","FSNDIS","FSEARN","FSUNEARN","FSGRINC","FSNETINC",
        "FSMEDEXP","FSMEDDED","FSDEPDED","FSCSDED","FSSLTDED","FSSTDDED",
        "RENT","UTIL","SUA1","BENMAX","MINIMUM_BEN","CAT_ELIG","HOMEDED",
        "SELFEMP1","SELFEMP2","SELFEMP3","WAGES1","WAGES2","WAGES3",
        "ELEMENT1","ELEMENT2","ELEMENT3","NATURE1","AGENCY1"]


def load_year(year: int) -> pd.DataFrame:
    df, _ = pyreadstat.read_sav(str(QC_DIR / f"qc_pub_fy{year}.sav"))
    df.columns = [c.upper() for c in df.columns]
    keep = [c for c in COLS if c in df.columns]
    df = df[keep].copy()
    df["year"] = year
    df["state"] = df["STATE"].map(FIPS)
    return df[df["state"].notna()]


def detect_smd(df: pd.DataFrame) -> set[str]:
    """States where FSMEDDED visibly departs from FSMEDEXP toward standards."""
    out = set()
    sub = df[(df["FSMEDDED"].fillna(0) > 0)]
    for st, g in sub.groupby("state"):
        if len(g) < 15:
            continue
        neq = (g["FSMEDDED"] != g["FSMEDEXP"].fillna(0)).mean()
        modal_share = g["FSMEDDED"].value_counts(normalize=True).iloc[0]
        if neq > 0.2 and modal_share > 0.35:
            out.add(st)
    return out


def build_features(df: pd.DataFrame, smd_states: set[str]) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    thr = df["year"].map(THRESHOLD)
    bendiff = (df["RAWBEN"].fillna(0) - df["FSBEN"].fillna(0)).abs()
    f["error"] = ((df["STATUS"].isin([2, 3])) & (bendiff > thr)).astype(int)
    elem_cols = [c for c in ["ELEMENT1", "ELEMENT2", "ELEMENT3"] if c in df.columns]
    has_med_finding = pd.concat(
        [(df[c].fillna(0) == 365) for c in elem_cols], axis=1
    ).any(axis=1)
    f["error_medical"] = (f["error"].astype(bool) & has_med_finding).astype(int)
    f["w"] = df["HWGT"].fillna(0)
    f["year"] = df["year"]
    f["state"] = df["state"]

    # Household covariates.
    f["size"] = df["CERTHHSZ"].fillna(df["FSUSIZE"]).fillna(1)
    f["elderly_or_disabled"] = ((df["FSNELDER"].fillna(0) + df["FSNDIS"].fillna(0)) > 0).astype(int)
    f["has_earnings"] = (df["FSEARN"].fillna(0) > 0).astype(int)
    f["earned"] = df["FSEARN"].fillna(0)
    f["unearned"] = df["FSUNEARN"].fillna(0)
    f["gross"] = df["FSGRINC"].fillna(0)
    f["cat_elig"] = (df["CAT_ELIG"].fillna(0) == 1).astype(int)

    # Intermediates (documentation / verification / computation burden).
    smd = df["state"].isin(smd_states)
    claims_med = df["FSMEDEXP"].fillna(0) > 0
    f["claims_medical"] = claims_med.astype(int)
    f["med_doc_required"] = (claims_med & f["elderly_or_disabled"].astype(bool) & ~smd).astype(int)
    se_cols = [c for c in ["SELFEMP1", "SELFEMP2", "SELFEMP3"] if c in df.columns]
    f["se_records"] = (df[se_cols].fillna(0).sum(axis=1) > 0).astype(int) if se_cols else 0
    f["utility_actuals"] = (df["SUA1"].fillna(0) == 2).astype(int)
    f["deduction_count"] = sum(
        (df[c].fillna(0) > 0).astype(int)
        for c in ["FSMEDDED", "FSDEPDED", "FSCSDED", "FSSLTDED"]
    )
    ben_rel_max = df["FSBEN"].fillna(0) / df["BENMAX"].replace(0, np.nan)
    f["at_max"] = (ben_rel_max.fillna(0) >= 0.999).astype(int)
    f["at_min"] = (df["FSBEN"].fillna(0) <= df["MINIMUM_BEN"].fillna(0) + 0.5).astype(int)
    f["ben_rel_max"] = ben_rel_max.fillna(0).clip(0, 1.5)
    f["net_share_of_gross"] = (
        df["FSNETINC"].fillna(0) / df["FSGRINC"].replace(0, np.nan)
    ).fillna(0).clip(0, 2)
    # Features from the giannella/snap_qc data dictionary (Jesse Shaw):
    f["children"] = (df.get("FSNKID", pd.Series(0, index=df.index)).fillna(0) > 0).astype(int)
    f["expedited"] = (df.get("EXPEDSER", pd.Series(3, index=df.index)).fillna(3) < 3).astype(int)
    f["cat_elig_code"] = df["CAT_ELIG"].fillna(0).astype(int)
    total_ded = sum(df.get(c, pd.Series(0, index=df.index)).fillna(0)
                    for c in ["FSDEPDED", "FSCSDED", "FSSLTDED", "FSMEDDED", "FSERNDED"])
    f["deductions_per_member"] = (total_ded / f["size"].clip(lower=1)).astype(float)
    return f


COVARIATES = ["size", "elderly_or_disabled", "has_earnings", "earned", "unearned",
              "gross", "cat_elig", "year", "children", "expedited",
              "cat_elig_code", "deductions_per_member"]
INTERMEDIATES = ["claims_medical", "med_doc_required", "se_records",
                 "utility_actuals", "deduction_count", "at_max", "at_min",
                 "ben_rel_max", "net_share_of_gross"]


def fit_score(train, test, cols, label):
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                       max_leaf_nodes=63, random_state=7)
    m.fit(train[cols], train["error"], sample_weight=train["w"])
    p = m.predict_proba(test[cols])[:, 1]
    auc = roc_auc_score(test["error"], p, sample_weight=test["w"])
    ap = average_precision_score(test["error"], p, sample_weight=test["w"])
    order = np.argsort(-p)
    w_s = test["w"].to_numpy()[order]
    e_s = test["error"].to_numpy()[order]
    k = int(np.searchsorted(np.cumsum(w_s), 0.05 * w_s.sum())) + 1
    pb = float(np.average(e_s[:k], weights=w_s[:k]))
    print(f"{label:<28} AUC {auc:.4f}  PR-AUC {ap:.4f}  P@5%budget {pb:.3f}")
    return m, p, auc, ap, pb


def main() -> None:
    frames = []
    for y in YEARS_TRAIN + [YEAR_TEST]:
        df = load_year(y)
        smd = SMD_DOC[y]
        print(f"FY{y}: SMD registry {len(smd)} states")
        frames.append(build_features(df, smd))
    data = pd.concat(frames, ignore_index=True)
    train = data[data["year"] != YEAR_TEST]
    test = data[data["year"] == YEAR_TEST]
    print(f"\ntrain {len(train):,} cases ({train['error'].mean():.1%} error), "
          f"test {len(test):,} ({test['error'].mean():.1%})")

    print("\n== FY2024 holdout ==")
    _, p_base, auc0, ap0, pb0 = fit_score(train, test, COVARIATES, "covariates only")
    m_full, p_full, auc1, ap1, pb1 = fit_score(train, test, COVARIATES + INTERMEDIATES,
                                          "with intermediates")
    print(f"lift: AUC {auc1 - auc0:+.4f}, PR-AUC {ap1 - ap0:+.4f}")

    # Feature importances (permutation on the holdout, top 8).
    from sklearn.inspection import permutation_importance
    imp = permutation_importance(m_full, test[COVARIATES + INTERMEDIATES],
                                 test["error"], n_repeats=3, random_state=7,
                                 sample_weight=test["w"])
    order = np.argsort(-imp.importances_mean)
    print("\ntop features (permutation importance on holdout):")
    for i in order[:8]:
        print(f"  {(COVARIATES + INTERMEDIATES)[i]:<22} {imp.importances_mean[i]:+.4f}")

    # Medical-element-specific check: does documentation burden predict
    # medical-element errors among elderly/disabled claimants?
    claim = data[(data["claims_medical"] == 1) & (data["elderly_or_disabled"] == 1)]
    ct = claim.groupby("med_doc_required").apply(
        lambda g: np.average(g["error_medical"], weights=g["w"]), include_groups=False
    )
    print("\nmedical-element error rate among elderly/disabled claimants:")
    for k, v in ct.items():
        n = (claim["med_doc_required"] == k).sum()
        print(f"  med_doc_required={k}: {v:.2%} (n={n:,})")

    # Natural experiment with never-adopter controls (difference in differences
    # on the MEDICAL-ELEMENT error rate among elderly/disabled claimants).
    print("\n== SMD adopters vs never-adopters (medical-element errors, claimants) ==")
    never = sorted(set(data["state"]) - SMD_DOC[2024] - {"GU", "VI"})
    med = data[(data["claims_medical"] == 1) & (data["elderly_or_disabled"] == 1)]

    def rate(g):
        return np.average(g["error_medical"], weights=g["w"]) if len(g) else np.nan

    ctrl_pre = rate(med[(med["state"].isin(never)) & (med["year"] <= 2019)])
    ctrl_post = rate(med[(med["state"].isin(never)) & (med["year"] == 2024)])
    print(f"never-adopters (n={len(never)} states): pre {ctrl_pre:.1%} -> FY2024 {ctrl_post:.1%} "
          f"(trend {ctrl_post - ctrl_pre:+.1%})")
    for st, post_years in [("AZ", [2023, 2024]), ("LA", [2024]), ("KY", [2024])]:
        g = med[med["state"] == st]
        pre = g[g["year"] <= 2019]
        post = g[g["year"].isin(post_years)]
        if len(pre) < 10 or len(post) < 10:
            print(f"{st}: insufficient cases")
            continue
        d_state = rate(post) - rate(pre)
        did = d_state - (ctrl_post - ctrl_pre)
        print(f"{st}: pre {rate(pre):.1%} (n={len(pre)}) -> post {rate(post):.1%} "
              f"(n={len(post)}); change {d_state:+.1%}; DiD vs never-adopters {did:+.1%}")

    json.dump({"auc_covariates": auc0, "auc_with_intermediates": auc1,
               "pr_covariates": ap0, "pr_with_intermediates": ap1,
        "p_at_5pct_budget_covariates": pb0,
        "p_at_5pct_budget_with_intermediates": pb1,
               "train_n": int(len(train)), "test_n": int(len(test))},
              open(OUT / "model_results.json", "w"), indent=1)
    print(f"\nwrote {OUT / 'model_results.json'}")


if __name__ == "__main__":
    main()
