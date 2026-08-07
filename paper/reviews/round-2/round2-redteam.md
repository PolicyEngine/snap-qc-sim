All checks complete. Compiling the report.

## Red-Team Review — Round 2 (revised manuscript, commit 27e1b09)

### Recommendation: Major Revisions

The quantitative core is unusually verifiable and mostly survives attack — I independently reproduced the headline simulation artifact to four decimals from the raw QC file. But the revision contains one factually wrong external claim (propagated unverified from a round-1 review), one place where the manuscript's "now corrected" claim is contradicted by the code committed on its own branch, and one newly-introduced factual error in the verification table's exclusion taxonomy. None is fatal; all are checkable; all must be fixed.

### Headline finding

**The False Claims Act sentence is wrong on both numbers and mis-cited** (`paper/index.qmd:134-137`): "the Department of Justice recovered more than $32 million in False Claims Act settlements from six states … [@crs2024snap]".

- **"$32 million" is the mid-investigation running total from the DOJ Texas press release** ("Including this settlement, the United States recovered over $32 million…"), at which point **four** states (VA, WI, AK, TX) plus the Osnes consultancy had settled.
- **"Six states" comes from a different snapshot** — the DOJ Florida release lists six *prior* settlers (VA, WI, TX, LA, AK, MS); with Florida ($17.5M) and Tennessee ($6.85M), **eight states** settled, and DOJ's own cumulative line in the Tennessee release reads "**more than $67 million**." There is no point in the timeline at which six states paired with $32M.
- **The citation cannot support the claim.** The cited CRS In Focus IF10860 (current version, per the April 2025 everycrsreport snapshot) contains *no* settlement content at all; the full CRS report R45147 describes only the three 2017 settlements (VA $7,150,436; WI $6,991,905; AK $2,489,999 ≈ $16.6M). The unpublished-FY2015–16-rates fact is in R45147, not IF10860.
- The error runs *against* the paper's own thesis — it understates the documented manipulation history by half. It also has **no FACTS.md row**, despite the manuscript's claim that "a fact catalog maps every quantitative claim to a committed artifact."
- **Provenance of the defect**: round-1's domain referee wrote "$32M" while listing seven states totaling ~$61M (`paper/reviews/round-1/referee-domain.md:22` — internally inconsistent), and the revision transcribed it without verification. This is precisely the prior-round hand-off failure mode. Fix: ">$67 million from eight states (2017–2021)", cite the DOJ releases directly.

### Verification attacks (18 claims traced; summary)

| Claim | Independent check | Verdict |
|---|---|---|
| tbl-verify counts (922/883/856/945/722/847/906 of 925/883/856/945/745/885/955; 113) | `app/public/data.json` n/verified fields; external suite reports in axiom-oracles; my own CASE==1 count from raw `qc_pub_fy2024.csv` | **Verified, three ways** |
| 1,037 ineligible / 406 full-overissuance national exclusions | techdoc Table II.1 (`~/.cache/axiom-oracles/snap-qc/techdoc.txt:1002-1043`); STATUS=2 & RAWBEN≤AMTERR definition at line 934 | **Verified** |
| $32M FCA / six states | DOJ Texas, Florida, Tennessee releases; CRS IF10860 and R45147 | **Wrong; mis-cited** |
| MD 13.64 = 8.85+4.79; 4.79 = nation's highest underpayment | FY2024 PER table (full scan of the Under column) | **Verified** |
| 13.33% delay threshold; "roughly ten jurisdictions" | 20/1.5 arithmetic; FY2024 PER — exactly 10 (AK, DC, FL, GA, MA, MD, NJ, NM, NY, OR) | **Count verified; boundary off** (13.33×1.5=19.995<20 — the trigger is *above* 13.33, i.e. 13.34 at reporting precision) |
| Admin match 50→25% FY2027 | Federal Register 2026-12696 (OBBBA §10106 amends §16(a)) | **Verified** |
| Binomial SE ≈2pts on 37/283 | √(.1307·.8693/283) = 2.00pp; 246/283 = 86.93% | **Verified** |
| Engine/solver partition identity | `amterr_replay_results.json`: 283/283 rows agree case-by-case (246/37 both) | **Verified** |
| CO 305 cases, $112.6M, $1.268B, 8.88% | Recomputed from raw file with HWGT | **Verified** |
| tbl-boundary (5 states, P(diff), E[cost], SD), $63.4M step, audit deltas, $609M/$1,310M | `results_by_state_corrected.json`; plus my own from-scratch bootstrap of the CO cell (official gate, seed 11): mean 9.9756, sd 0.9041, P₁₅ 0.4765 — exact match | **Verified; artifact genuine** |
| "Five states nearest boundaries" | Ranked all 53 by flip probability and by distance — the named five are the top five states both ways | **Verified** |
| Layers 1–2 shares (7.3/10.5; 3.9/18.4 of $8.1B; 3.3/6.6/4.2/86.0) | Recomputed from `native_decomposition.json`, `phase_a_classification.json` | **Verified** |
| Model metrics (0.761→0.767, +0.003 PR, 47.8% @13.4%, 0.8356/0.7233, smear 1.173, $183/$189, sign 0.700, all-nine-negative gaps −0.3…−3.5, 7/9 within 3pp) | `analysis/*.json` | **Verified** (83.65% is 83.64% in the artifact — nit) |
| SMD contrasts (AZ +2.07/+0.64; CA +0.11/−1.40; KY −0.42/−0.01; LA; MI); 2.60 vs 2.97 | Recomputed DiD from `model_results.json` cells | **Verified** (LA/MI have *zero* treated events — see Minor) |
| KY −5.3 earlier-pipeline claim | `git show 2254fd8:analysis/FINDINGS.md` ("8.2% → 2.1%, DiD −5.3pp") | **Verified** |
| Reduced-schedule election + no-dispute waiver; 300–2,400/300–1,020; $56/$37 | techdoc lines 851-895; PER footnote 1 | **Verified** |
| "Archived unedited" (11 reviews) | `git diff 40fd333..HEAD -- paper/reviews/` (additions only, no edits) | **Verified** |
| Cert claims (856/856, 5,136 cells, 230/s, byte-identical rebuild) | `paper/snapshot/cert/CERT_REPORT.md` incl. its adversarial addendum | **Consistent** (as attested; external CSV-authenticity dependency disclosed) |

### Major issues

1. **The FCA settlements sentence** (headline finding above). Wrong total, wrong state count, citation that doesn't contain the claim, no FACTS row.

2. **The branch of record contradicts the manuscript's "now corrected" claim, and the headline artifact has no committed generator.** On the `paper` branch, `snap_qc_sim/data.py` (`load_cases`) still gates counted errors on `abs(issued − correct) > threshold` with `correct = FSBEN` — the exact "banned benefit-difference definition" the paper says was "now corrected" (`index.qmd`, §sec-simulate), and `app/public/data.json` still carries the FSBEN-gated errors (CO: 112 cases/$92.8M — the wrong-gate signature round 1 measured). The fix (d2e3972) exists **only on `main`**, which is not an ancestor of 27e1b09; the intro's "all corrected here" is false on its own branch. Meanwhile `paper/snapshot/labs/results_by_state_corrected.json` — the artifact behind every number in §sec-simulate — has **no generator anywhere in the repo**; the committed `mc_tool.py` in the same directory still carries the banned gate and writes a different file. Mitigations I verified: the deployed app serves corrected data (CO 110/$94.1M), and my clean-room bootstrap from the raw file with the official gate reproduces the corrected artifact **exactly** (same seed) — the numbers are genuine. The failure is provenance and branch hygiene, in a paper whose method is that provenance failures are disqualifying. Fix: merge/rebase so the corrected loader, rebuilt data.json, and a committed corrected generator are ancestors of the manuscript commit.

3. **The verification table's exclusion taxonomy is factually wrong — a new error introduced by this revision.** All 113 exclusions are **SSI-CAP** (Combined Application Project) standardized-benefit units: the committed suite reports record `by_reason: {ssi_cap: 3/23/38/49}` for AZ/MD/NY/TX and nothing else. The manuscript (`index.qmd:180-182`, and the tbl-verify caption) says "standardized-benefit units under **SSI cash-out and MFIP**, and records **missing required fields**": SSI cash-out is a different (defunct) program; MFIP is Minnesota-only — zero MFIP units among the seven states; zero missing-field exclusions fired. Round-1's editorial (T1) correctly wrote "SSI-CAP"; the revision garbled it.

4. **The abstract misstates the model→simulator relationship and its own scope.** "I then fit and validate a distributional model … and embed the results in an open Monte Carlo simulator of measured error rates" — the model-based mode is disabled in production and "this paper quotes it nowhere" (§sec-model); every simulation number is observed-case resampling. The abstract's arc implies the fitted model underlies the central 46–50% finding; it does not. Also: "6,081 of 6,194 **in-scope** fiscal 2024 cases" misplaces the modifier (6,194 is the official universe; 6,081 *is* the in-scope set — 100% of in-scope cases matched, which is the stronger and correct statement); and "surfaced and **fixed** two defects in the encodings **and errata** in the federal technical documentation" grammatically claims to have fixed FNS's documentation — and the errata's upstream report remains unlocatable (flagged in round 1, still no link or artifact).

5. **"A fact catalog maps every quantitative claim to a committed artifact" is false as stated** (`index.qmd:96-97`; FACTS.md header). No rows exist for: the FCA settlements figures, MD 13.64/4.79, the 1,037/406 exclusions, 13.33%/ten jurisdictions, the 50→25% match cut, §10103. Five of those six verify against primary sources; the sixth is the one that's wrong — which is the argument for the catalog discipline the paper claims but didn't apply to its own revision.

### Falsification attempt on the headline claim (46–50% tier flips)

I attacked it four ways: (a) rebuilt the Colorado bootstrap from the raw public file with the official error definition, official-rate centering, and the artifact's design — reproduced the committed cell to four decimals; (b) confirmed the official rates against the FNS PER table; (c) confirmed the five states are the top five by both boundary distance and flip probability (Guam sixth); (d) probed the two known biases — i.i.d. resampling vs. actual state designs, and PUF truncation of ineligible/full-overissuance error — both disclosed, both pushing the true flip risk *up*, so they cannot rescue a "the claim is overstated" argument. **I could not construct a falsification.** The claim is robust as scoped (fixed error process, re-review adjustment as level shift — both stated).

### Minor issues

- **13.33% boundary arithmetic** (`index.qmd:44, 51`): 13.33 × 1.5 = 19.995 < 20. The delay trigger is rates *above* 13.33% (13.34% at the PER's two-decimal reporting). A paper about tier-boundary mechanics should state its one statutory boundary exactly. (No listed jurisdiction changes.)
- **tbl-validate mixes configurations**: the frozen-model unfactored correlation is 0.5176 (→0.52); the printed 0.51 is the full-model 0.507. And FACTS E5's "unfactored" row (1.83/1.45) is the full model while the manuscript prints frozen 1.81/1.65 — catalog and manuscript disagree on which configuration is canonical.
- "83.65%" vs artifact 0.836447 → 83.64% (`hurdle_results.json`).
- **"Per-case outputs for all three decomposition layers" (§sec-availability) is inaccurate**: layer 1 (`native_decomposition.json`) is aggregate-only; layer 2 (`phase_a_classification.json`) carries rows for only 32 of 305 cases (pure_math 13 + input_system_caused 19); only layer 3 is complete (283 rows).
- LA and MI adoption contrasts have **zero treated events in both windows** (artifact `event_count` 0/0) — "single-digit event counts for several adopters" understates; those two "contrasts" are pure control-trend artifacts and should be labeled as such.
- "California by $43M" SD reduction — artifact delta is $43.8M (rounds to $44M).
- "Independent clean-room reruns reproduce all artifacts byte-for-byte" (intro): the byte-for-byte evidence covers the five *analysis-pipeline* artifacts (one referee clean-clone rerun + E9); the snapshot labs behind the headline table were never independently rerun and, on this branch, cannot be (Major 2). Scope "all artifacts" explicitly, as §sec-availability already does.
- Hardcoded `/Users/maxghenis/...` paths persist in `mc_tool.py` and `scripts_build_data.py` on this branch (round-1 item; unresolved here).

### Strengths

- **The artifact discipline is real where it exists.** Eighteen of the claims I attacked — including every number in the boundary table, the audit-volume asymmetry, the lever bounds, all three decomposition layers, the model metrics, and the SMD contrasts — reproduce exactly from committed artifacts, and the load-bearing ones reproduce from the *raw public file*. Independently rebuilding the paper's central Monte Carlo cell from scratch and matching it to four decimals is a result few papers would survive.
- The verification-table counts verify three independent ways (paper table ↔ app data ↔ external suite reports ↔ raw-file universe counts).
- The revision's honesty language is mostly earned: the parity-scope section (§sec-oracle-scope) is now precise; the direction-of-effect fixes (under-coverage; SMD cell labels) were applied correctly per the artifacts; the reviews are genuinely archived unedited (git history confirms); the disclosed biases (truncation, i.i.d. approximation) run against the paper's convenience.
- The one-sided reporting of validation failures (all nine coverage gaps negative; disabled model mode) is the opposite of the usual sales job.

Sources: [DOJ Texas HHSC settlement](https://www.justice.gov/opa/pr/texas-health-and-human-services-commission-agrees-pay-over-15-million-resolve-false-claims), [Oversight.gov Tennessee DHS settlement](https://www.oversight.gov/tennessee-department-human-services-agrees-pay-6854416-resolve-false-claims-act-liability), [Oversight.gov Florida DCF settlement](https://oversight.gov/investigative-press-releases/Florida-Department-Children-and-Families-Agrees-Pay-175-Million-Resolve), [CRS R45147 (Errors and Fraud in SNAP)](https://www.congress.gov/crs_external_products/R/PDF/R45147/R45147.4.pdf), [everycrsreport IF10860](https://www.everycrsreport.com/reports/IF10860.html), [Federal Register: SNAP Federal-State Administrative Cost Sharing](https://www.federalregister.gov/documents/2026/06/24/2026-12696/supplemental-nutrition-assistance-program-changes-in-federal-state-administrative-cost-sharing), [DOJ Louisiana DCFS settlement](https://www.justice.gov/archives/opa/pr/louisiana-department-children-and-family-services-agrees-pay-over-39-million-resolve-false), [DOJ Mississippi DHS settlement](https://www.justice.gov/archives/opa/pr/mississippi-department-health-services-agrees-pay-5-million-resolve-false-claims-act).

Key file paths: `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/index.qmd` (lines 134-137 FCA claim; 178-203 exclusion taxonomy; abstract lines 19-24), `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/snap_qc_sim/data.py` (banned gate, `load_cases`), `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/app/public/data.json` (FSBEN-gated on this branch), `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/snapshot/labs/mc_tool.py` (stale generator), `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/snapshot/labs/results_by_state_corrected.json` (genuine but generator-less), `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/FACTS.md` (missing rows).