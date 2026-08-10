# Red-team review — revision-4 delta (verbatim, 2026-08-09)

## Red-Team Review

### Verdict: Major Revisions

### Headline finding
The revision's framing claim is false on the repo's own history. The abstract asserts the fiscal 2025 rates were "published in June 2026 **after this prediction was committed**" — but this repository's first commit is 2026-08-05 (`076e509`) and the manuscript was first committed 2026-08-06 (`bce8eb6`), while the FY2025 rates were published **June 24, 2026** (verified from the official PDF, dated June 24, 2026). The prediction was committed six weeks *after* the data that supposedly tests it. Every number in the section is genuine and reproduces byte-for-byte, but the "out-of-sample test of a committed prediction" narrative inverts the actual timeline — and because the simulator was built while the FY2025 rates were already public, temporal precedence cannot be claimed at all. The defensible claim is input-independence (the simulator consumes only FY2024 QC microdata; FY2025 rates are not an input), which is weaker and must be stated instead.

### Verification attacks

**Core claim verification.**
| Claim | Source cited | Independent verification | Verdict |
|-------|--------------|--------------------------|---------|
| "published in June 2026 after this prediction was committed" (abstract); "was committed against fiscal 2024 data. On June 24, 2026, FNS published…" (§fy2025) | repo history | Initial commit 2026-08-05; paper added 2026-08-06; FY2025 PER dated 2026-06-24 | **FALSE — BLOCKING (finding 1)** |
| 18 of 53 tier changes; roster of flips | `analysis/fy2025_movement.json` | Recounted from state rows with independently applied tier rule: 18, identical list | Verified |
| 10 beyond-noise (DE FL HI IL KY MN NC NJ OH WV); criterion 2.77 | same | Recomputed z = Δ/SD per state; 10 at \|z\|&gt;1.96√2=2.7719; identical set. 2.77 factor derived independently | Verified |
| Median 1.38 SD | same | Recomputed median \|z\| = 1.3836 | Verified |
| CO 9.97→10.09, Δ0.12, z 0.13, 10%→15%; HI 6.68→10.92, z 11.2, 5%→15%; NJ 14.33→6.86, z −11.2; KY 9.11→4.70, z −7.2, →0%; national 10.93→10.62 | same | All recomputed from rates+SDs; all match; both years' rates then diffed against official PDFs (below) | Verified |
| FY2024 delay roster 10 (incl. NY 14.09); FY2025 roster 7 (AK DC DE GA IL NM OR); dropped FL MA MD NJ NY, added DE IL | same | Recomputed rate×1.5≥20 per state per year from official rates; exact match; each of the 7 confirmed crossing (min: OR 14.14×1.5=21.21) | Verified |
| τ = 1.62 [0.81, 2.25]; robust 1.07 [0, 1.74] | same | Method-of-moments and median/MAD recomputed from raw deltas+SDs (1.6207, 1.0740); bootstrap CIs reproduced to 4 decimals with an independent implementation at seed 202507 | Verified |
| Whole artifact "deterministic at seed 11" | `analysis/fy2025_movement.py` | Full pipeline rerun in a clean clone at origin/main (`uv run --frozen`): output SHA-256 `11faaf42…` byte-identical to committed file | Verified |
| FY2027 threshold est. $59; 59.581528 on $1,018.20; $60 needs ≥$1,025.40; 48/54/56/57/58 uniquely floored | `analysis/fy2027_parameters.json` | Exact-fraction recompute: floor(37×1018.20/632.30)=59.581528→59; $60 boundary 37938/37=1025.3514→$1,025.40 at ten-cent precision; floor matches all 5 years, nearest fails 2022–24, ceiling fails all. May 2026 TFP $1,018.20 verified in official USDA PDF (`cnpp-costfood-tfp-may2026.pdf`); $56/$57 tolerance confirmed in FY24/FY25 PER footnotes | Verified |
| Feature round: 17 features; AUC 0.7666→0.7679; stage-1 0.8356→0.8397; MAE 1.83→1.71; coverage 4.38→4.64 worse, retained; 44 BBCE adopters; CAT_ELIG excluded; 36/36 CO elderly at $200; 6 naive misclassified | `model_results.json`, `hurdle_results.json`, `distributional_results.json`, FEATURES_REPORT | All read from machine artifacts; "committed" baselines pulled from git parent `f0a6714^` (1.8274; 4.3761 recomputed from quantile rows); 44 adopters recounted from vendored CSV (9 nonadopters); CAT_ELIG absent from all feature lists; $165+$35=$200 inside (+$5,+$50] of both $164.90 and $174.70; overlap 36/36 elderly, naive 6 | Verified |
| CO $63M/yr tier step | `app/public/data.json` | 0.05 × $1,267,963,388 = $63.4M | Verified |
| CO election: 53% probability, ~$31M/yr | deployed simulator | Reimplemented `mulberry32`+`simulate`+`electionStats` (app.js:33–126) in Node: pWin = 0.525 (2,100/4,000; app displays "53%" via toFixed(0)), lock28−elect28 = $31.1M/yr | Verified (see NIT on 52.5%) |
| Statute: ×1.5≥20 ⇔ ≥13.33%; tiers; FY2028 elected FY2025/26; FY2029 = third preceding year; FY2025 crossing→FY2029, FY2026→FY2030; election-independent | 7 U.S.C. § 2013(a)(2) | Fetched uscode.house.gov prelim text: all confirmed, incl. delay keyed to each year's rate independent of election; NY 13.18×1.5 = 19.77 &lt; 20 confirmed | Verified (but see finding 2) |
| FY2025 rates real; published June 24, 2026 | `@fna2025per`; provenance sha256 | Downloaded `snap-qcfy25-per.pdf` from fna.usda.gov: SHA-256 **exactly matches** artifact provenance (`ae3fc57f…`); all 53 state rates + national 10.62 diffed — zero mismatches; dated June 24, 2026; FNA letterhead confirmed visually | Verified |
| FY2024 rates | `data.json` / `@fns2024per` | Downloaded `snap-fy24QC-PER.pdf`: all 53 rates match; CO 9.97 = 7.91+2.06; MD 13.64 w/ 4.79 under; AK 24.66; national 10.93 | Verified |
| FNS renamed FNA, 2026 | `@fna2025per` letterhead | Rename effective June 1, 2026 (USDA announced April 30, 2026; 30-day congressional notice ended May 30); FNA letterhead on the cited PDF verified | Verified |

**Self-citation / @misc / unverifiable-source audit.**
| Citation | Type | Audit artifact found? | Values reproduce? | Verdict |
|----------|------|----------------------|-------------------|---------|
| `@fna2025per` (references.bib:156) | @misc, gov URL | Source PDF not in repo, but provenance SHA-256 in artifact; I retrieved the official PDF and hash-matched it | Yes, all 53 values byte-exact | Clean |
| `analysis/fy2025_movement.json` (self artifact) | committed artifact | Generator + inputs present (QC CSV cached locally) | Byte-identical regeneration | Clean |
| `analysis/fy2027_parameters.json` (self artifact) | committed artifact | Offline generator; observation records hashed but source bytes not pinned (disclosed in artifact) | All arithmetic exact; inputs verified against live USDA PDFs | Clean |

**Cross-revision checks.**
| Change | Relabel or regenerate? | Values consistent across revisions? | Verdict |
|--------|------------------------|-------------------------------------|---------|
| FNS/FNA parenthetical rewritten **mid-review** (working tree changed between my two diffs): "effective June 1, 2026" dropped, `[@fna2025per]` letterhead citation added | Relabel (prose only) | Both variants externally true | Clean, but note the file is being concurrently edited; this review is of diff sha `eda3cc61…` |
| Footnote FY2024 "roughly ten" → FY2025 seven-state roster | Regenerated from new official data | Yes, both rosters verified against both official PDFs | Clean |
| "Committed" baselines (1.83 MAE, 4.38 coverage) vs new values | Regenerated; old values confirmed in git parent `f0a6714^` | Yes | Clean |

### Falsification attempt on headline claim
The headline numerical claim — 18 of 53 tier flips with only 10 beyond two-year sampling noise — survives every attack I could mount: I recounted both from raw state rows with an independently derived tier rule and noise criterion, reproduced the artifact byte-for-byte from its generator in a clean clone, and diffed all 106 underlying official rates against the two USDA PDFs (one hash-matched to the artifact's pinned SHA-256). I cannot falsify the numbers. What I *can* falsify — and did — is the claim's advertised epistemic status: it is presented as a prediction committed before the June 24, 2026 publication, and the repo's own history proves the opposite order. The number is right; the "out-of-sample prediction" story around it is not.

### Other damaging findings
- **(2) MINOR (statutory overstatement, internally contradicted):** footnote `[^delay]` states the seven FY2025-crossing jurisdictions have "their first bill in FY2029 keyed to the fiscal 2026 rate." That is conditional, not settled: an FY2026 crossing moves the start to FY2030, zeroing FY2029 — as the paper's own §fy2025 and the app (`app.js:95–110`) correctly state. For Alaska (24.66→23.15) an FY2026 crossing is near-certain, so the footnote's flat assertion will very likely be false for at least one of the seven. Should read "no bill before FY2029."

### Findings below your threshold
- "a 53% probability" is exactly 52.5% (2,100/4,000 draws at the committed seed); the app's `toFixed(0)` displays 53%. Quote 52.5% or "about 53%" in the paper.
- "Five of the slots that zero a state's FY2028 bill turned over" — the FY2024 roster never had legal force (the delay test keys only to FY2025/FY2026); the counterfactual is disclosed one sentence earlier, but "slots that zero" reads as actual.
- "On June 24, 2026, FNS published" — the publisher of record was FNA (letterhead verified); consistent with the paper's disclosed keep-FNS convention, so acceptable as written.
- The working tree changed mid-review; whoever lands this should re-render `app/public/paper/index.html`/`index.pdf` from the final qmd (both are currently modified alongside it).

Recomputed/verified: 6 repo artifacts (movement JSON incl. byte-identical pipeline regeneration and 4-decimal bootstrap reproduction, FY2027 parameters via exact fractions, model/hurdle/distributional results with git-parent baselines, data.json, app election engine reimplemented in Node) against 4 official external sources (FY2025 PER PDF hash-matched + all 53 rates, FY2024 PER PDF all 53 rates, May 2026 TFP PDF, 7 U.S.C. § 2013(a)(2) text) — roughly 60 distinct quantitative claims, of which all verified except the two findings above. Key paths: `paper/index.qmd`, `analysis/fy2025_movement.json`, `analysis/fy2027_parameters.json`, `app/public/app.js`, `app/public/data.json`.
