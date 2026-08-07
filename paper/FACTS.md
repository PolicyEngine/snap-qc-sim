# Fact catalog

Every quantitative claim in the manuscript traces to a row here; every row
names its artifact. Artifacts live in this repository unless noted.
Numbers from the superseded pre-audit pipeline (before PR #7) are banned.

## A. Program and statute

| # | Fact | Source |
|---|---|---|
| A1 | Beginning FY2028, states pay a share of SNAP benefit costs set by their payment error rate: 0% below 6%, 5% for 6–8, 10% for 8–10, 15% at or above 10 | 7 U.S.C. 2013(a)(2) |
| A2 | The FY2028 share is keyed to the state's FY2025 or FY2026 rate (state election); FY2029 onward uses the third preceding fiscal year | 7 U.S.C. 2013(a)(2)(B)(ii) |
| A3 | Implementation is delayed to FY2029 (FY2030) for states whose FY2025 (FY2026) rate × 1.5 reaches 20% | 7 U.S.C. 2013(a)(2)(B)(iii) |
| A4 | QC active-case annual minimum sample: 300 for N≤10,000; 300+0.042(N−10,000) capped at 2,400; reduced option 300 / 300+0.0153(N−12,941) capped 1,020. Negative: 150 / 150+0.144(N−500) capped 800; reduced 150 / 150+0.1224(N−683) capped 680 | 7 C.F.R. 275.11(b) (verified formula-for-formula vs eCFR); FY2024 technical documentation restates the formulas |
| A5 | All states elected the reduced (optional) active sampling schedule in FY2024 | FY2024 QC technical documentation (techdoc lines ~894–895) |
| A6 | Official error tolerance threshold (FY2024): $56; per-year 2017–2024: 38/37/37/48/54/56 (2020–21 pandemic years excluded from this work) | FNS QC guidance; analysis/train_error_model.py THRESHOLD |

## B. Data

| # | Fact | Source |
|---|---|---|
| B1 | SNAP QC public-use files FY2017–19, 2022–24; FY2024 has 44,891 records, 44,800 in the CASE==1 official universe across 53 jurisdictions | snapqcdata.net; analysis/FINDINGS.md |
| B2 | Weighted official-error prevalence: 10.62% train years, 13.39% FY2024 | analysis/FINDINGS.md; model_results.json |
| B3 | |RAWBEN−BENFIX| equals AMTERR for 99.997% of FY2024 weighted cases; |RAWBEN−FSBEN| only 83.65% — BENFIX (allotment adjusted for errors) is the deviation anchor; FSBEN is the full formula benefit | hurdle_results.json target_concordance; independently verified 2026-08-06 |
| B4 | HWGT weights sum to annual case-months; weight × monthly dollars = annual dollars | FY2024 technical documentation |

## C. Verification oracle (external artifacts: TheAxiomFoundation/axiom-oracles)

| # | Fact | Source |
|---|---|---|
| C1 | Seven states' encoded benefit computations reproduce the QC file's Minimodel chain exactly at zero tolerance for every in-scope case: 6,081 of 6,194 official-universe cases (CO 856/856, NY 847/885, CA 883/883, AZ 922/925, GA 945/945, MD 722/745, TX 906/955; 113 exclusions are enumerated program-structure classes); six asserted values per case | axiom-oracles PRs #244, #268, #269; committed suite reports; per-state suite configs ("in-scope") |
| C2 | Scope caveat: the comparison bridge supplies several QC-derived intermediates as inputs (QC-calculated medical and child-support deductions, QC utility amount, QC categorical-eligibility status), so parity certifies the downstream benefit arithmetic given those intermediates, not independent derivation of every state-policy path | axiom-oracles bridge (snap_qc_compare.py); engine-leg recon 2026-08-06 |
| C3 | Reaching parity surfaced and fixed two defects in the encodings themselves: a stale regulatory dollar literal superseded by statute, and a missing whole-dollar rounding step in the benefit computation | rulespec-us PRs (COLA backfill; #826 rounding); axiom-oracles #268 history |
| C4 | The process also surfaced errata in FNS's own FY2024 technical documentation (variable-description inconsistencies identified while mapping), documented in the lab analysis and report page | paper/snapshot/labs/amterr/ANALYSIS.md; axiom.org/reports/colorado-snap-qc-fy2024 |
| C5 | A certification probe (2026-08-06) attested a reproducible toolchain: engine commit de0efdc7 (binary SHA-256 bb8ec236…) × rulespec-us b53ce208 reproduces CO 856/856 benefits and 5,136/5,136 stage cells at zero tolerance; 856 cases in 3.73 s end-to-end (230 cases/s; 279/s with compile amortized) | CERT_REPORT (paper/snapshot/cert/CERT_REPORT.md) |
| C6 | Extrapolation at certified throughput: 6,081 cases ≈ 26 s; 44,800 × 5 scenarios ≈ 16 minutes single-threaded on a laptop | CERT_REPORT extrapolation table |

## D. Decomposition of measured error (Colorado FY2024)

| # | Fact | Source |
|---|---|---|
| D1 | Colorado FY2024: 856 sampled cases, 305 with payment errors (STATUS 2/3); $112.6M/yr weighted error dollars on $1.268B issuance (8.88% file-derived; official regression-adjusted rate 9.97% = 7.91 over + 2.06 under) | paper/snapshot/labs/amterr/ANALYSIS.md; FNS FY2024 PER (https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-fy24QC-PER.pdf) |
| D2 | QC cause coding: strict computation classes (programming/arithmetic/mass change) carry $8.2M/yr (7.3% of error dollars); adding policy-misapplied, budgeted-wrong, computer-user reaches $11.9M (10.5%). National: $320M/yr (3.9%) strict, $1.5B/yr (18.4%) broad, of $8.1B/yr weighted error dollars | paper/snapshot/labs/amterr/native_decomposition.json + ANALYSIS.md |
| D3 | Finding-nature classification: pure-math 3.3%, input-with-system-cause 6.6%, mixed 4.2%, other input 86.0% of error dollars | paper/snapshot/labs/phase_a_classification.json |
| D4 | Replay: reconstructing pre-edit original values (public $3-shift solver, FY2024 adaptation) and replaying through the verified engine explains 246/283 filtered error cases (86.9%) as correct arithmetic on wrong facts; solver and engine partition the 283 cases identically; 37 cases form the computation-side upper bound | paper/snapshot/labs/amterr/amterr_replay_results.json (283 per-case rows) + reconstruct_co_fy2024.R + amterr_replay.py |

## E. Error models (corrected pipeline, PRs #7–#8 only)

| # | Fact | Source |
|---|---|---|
| E1 | Official-error classifier, FY2024 weighted: ROC AUC 0.7609 (covariates + formula anchor) → 0.7666 (+ burden intermediates), +0.0057; PR-AUC +0.0030; precision at a 5% weighted review budget 47.6% → 47.8% | model_results.json; FINDINGS.md |
| E2 | Hurdle: stage-1 P(deviate) AUC 0.8356; stage-2 P(cross | deviate) 0.7233; OOF Duan smear 1.1725; predicted vs observed conditional magnitude $183 vs $189 | hurdle_results.json |
| E3 | Distributional model: nine conditional quantiles of log|D|, per-case monotone, exponential-in-logs tail (scale 0.4674) fitted on top-decile OOF residuals; weighted FY2024 quantile coverage within 3pp at 7 of 9 levels; ALL NINE gaps negative (under-coverage; q.75 −3.5pp, q.90 −3.3pp — the model UNDERSTATES mid-upper magnitudes) | distributional_results.json; FINDINGS.md |
| E4 | Sign model P(D>0 | deviate) calibrated AUC 0.6996 | distributional_results.json |
| E5 | State calibration, FY2024. Primary-model unfactored: equal-jurisdiction MAE 1.83pp (slope 0.954), issuance-weighted 1.45pp (slope 0.769); matched FROZEN-model unfactored: 1.81pp / 1.65pp (the manuscript quotes the matched frozen pair). With factors fit on out-of-sample FY2023 (train ≤ FY2022, empirical-Bayes shrinkage, frozen): equal 0.885pp, issuance-weighted 0.785pp, corr 0.906 | hurdle_results.json state_calibration |
| E6 | Model-vs-bootstrap simulated measured rate (official-centering convention): the model's raw level underpredicts high-error states (NY model mean 11.02% vs bootstrap 14.10%; CO 8.62 vs 9.98) — any app use must anchor levels and disclose per-state gaps (model mode currently disabled pending review fixes) | distributional_results.json simulation_validation; FINDINGS.md |
| E7 | Cross-sectional medical-event rates under the corrected event definition (element 365 paired with payment-impact finding, slots 1–9): 2.97% where no standard medical deduction requires documentation vs 2.60% where it does (claimant denominator) | model_results.json |
| E8 | SMD adoption contrasts are descriptive, calendar-aligned, both denominators, with unweighted event counts: AZ +2.07pp claimant-conditioned (+0.64 stable), CA +0.11 (−1.40), KY −0.42 (−0.01), LA −0.08 (−0.15), MI +0.16 (−0.19) | model_results.json; FINDINGS.md |
| E9 | Two complete pipeline reruns are byte-identical; independently reproduced (SHA-256 match on all artifacts) 2026-08-06; 46 tests | run_all.py provenance; PR #8 |

## F. Simulation and stakes (FY2024 basis)

| # | Fact | Source |
|---|---|---|
| F1 | Tier assignment near boundaries is noisy at regulatory sample sizes: P(different tier than the official point rate implies) — ND 50%, WA 48%, CO 49%, KS 47%, NV 46% | paper/snapshot/labs/results_by_state_corrected.json (official error gate, CASE==1) |
| F2 | Colorado: official 9.97% (0.03pp below the 15% boundary), $1.268B issuance, expected FY2028-rule cost $156.4M/yr, SD $32.8M; the 10%→15% tier step is $63.4M/yr | paper/snapshot/labs/results_by_state_corrected.json |
| F3 | Audit volume is a two-sided lever: +500 reviews raises expected cost for just-above-boundary states (CA −$30.3M, PA −$13.1M, TX −$13.1M expectation) and lowers it for just-below states (MO +$3.9M, TN +$3.7M, IN +$3.3M); it nearly always cuts the SD of the bill (CA −$44M) | paper/snapshot/labs/results_by_state_corrected.json |
| F4 | Category-suppression accounting bound: removing 50% (100%) of observed error dollars in the four named simplification categories corresponds to ≈$609M/yr (≈$1,310M/yr) nationally in expected cost share | paper/snapshot/labs/results_by_state_corrected.json |
| F5 | These lever numbers are accounting bounds on the observed FY2024 error mix — scenario dials, not causal estimates; the error process is held fixed (no behavioral response, no audit-feedback channel) | mc lab DESIGN; app method notes |

## G. Prohibitions (ground truth for writers and referees)

- No causal language for SMD contrasts or any lever (descriptive only).
- Parity claims always carry the C2 scope caveat.
- No numbers from the pre-correction pipeline (superseded by PR #7).
- Unfactored cross-state correlation ≈0.51 (frozen model; factored 0.91) — never "about half of variance", and always say which configuration.
- The engine-recomputed-counterfactual leg is future work; the live tool's
  levers are accounting bounds and its model mode covers baseline + audit
  volume only. Say so wherever relevant.
- No references to private conversations; the reconstruction solver is cited
  as the public software it is.

## H. System and statute facts added in revision (round-2 verified)

| # | Fact | Source |
|---|---|---|
| H1 | DOJ recovered more than $67 million in False Claims Act settlements from eight states (VA, WI, AK, TX, LA, MS, FL, TN) over 2017–2021 concerning bias in QC error-review processes; national rates for FY2015–16 were not published | DOJ settlement releases (cumulative line in the Tennessee release); CRS R45147 |
| H2 | Maryland FY2024: official rate 13.64 = 8.85 over + 4.79 under; 4.79 is the nation's highest underpayment rate | FNS FY2024 PER table (verified full-column scan) |
| H3 | FY2024 public-use file exclusions: 1,037 ineligible-finding cases and 406 cases with overissuance ≥ issued benefit | FY2024 technical documentation Table II.1 |
| H4 | Delay-clause threshold: rates above 13.33% (13.34% at published precision; 13.33 × 1.5 = 19.995 < 20); exactly ten jurisdictions qualify at FY2024 rates (AK, DC, FL, GA, MA, MD, NJ, NM, NY, OR) | 7 U.S.C. 2013(a)(2)(B)(iii); FY2024 PER table |
| H5 | OBBBA cut the federal share of SNAP administrative costs from 50% to 25% beginning FY2027 | OBBBA § 10106; Federal Register 2026-12696 |
| H6 | OBBBA § 10103 restricts the LIHEAP-triggered heat-and-eat utility allowance to households with an elderly or disabled member | Pub. L. 119-21 § 10103; state implementation letters |
| H7 | Colorado deviation universe: 305 = 110 above-threshold official errors + 195 sub-threshold deviations; sub-threshold dollars $18.5M of $112.6M (16%); official-gate file-derived rate 7.42% | recomputed from qc_pub_fy2024.csv (official gate); paper/snapshot/labs/amterr/amterr_replay_results.json |
| H8 | Replay explanation rates by threshold status: 76/97 = 78.4% above threshold; 170/186 = 91.4% below; 33 of 246 explained cases have deviations ≤ $5 (within comparison tolerance mechanically) | paper/snapshot/labs/amterr/amterr_replay_results.json |
