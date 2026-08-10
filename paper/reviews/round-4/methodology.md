# Methodology review — revision-4 delta (verbatim, 2026-08-09)

## Methodology review — paper-fy2025-revision delta (`paper/index.qmd`)

Scope note: no Bash tool was available in this environment, so I could not run `git diff origin/main`. I located all six described passages in the working tree (abstract lines 34–38; rename parenthetical lines 73–75; FY2027 parenthetical lines 134–140; footnote `[^delay]` lines 56–66; `### Fiscal 2025 as an out-of-sample test` lines 611–667; feature-round paragraph lines 504–524) and verified them against the committed artifacts, reading `.git/logs/HEAD` directly for history (reflog confirms HEAD is on `paper-fy2025-revision`).

### Findings

**1. BLOCKING — the abstract's temporal pre-registration claim is contradicted by the repository's own history.**
Quote (abstract, lines 34–36): *"The fiscal 2025 rates, published in June 2026 after this prediction was committed, test it out of sample"*.
Evidence: `.git/logs/HEAD` line 1 shows the initial commit ("Initial scaffold: QC sampling Monte Carlo with audit and policy levers") created at Unix 1785962388 = **2026-08-05 16:39 EDT**; the manuscript was first committed 2026-08-06/07; the FY2025 movement analysis on 2026-08-09. The FY2025 rates were published **2026-06-24** (per `analysis/fy2025_movement.py` line 3 and `paper/references.bib` line 160). The publication precedes the prediction's commitment by ~6 weeks; there is no reading under which "published … after this prediction was committed" is true, and nothing committed anywhere in this repo predates June 24. The section text (lines 613–616: *"was committed against fiscal 2024 data. On June 24, 2026, FNS published the fiscal 2025 rates, and the claim met its first realized year"*) implies the same false ordering. The honest and still-strong framing — which the orchestrator's brief anticipates — is **data-vintage** out-of-sample: the simulator and model consume only fiscal 2024 and earlier inputs; no FY2025 information enters the pipeline; the realized year tests the noise-dominance mechanism, not a state forecast. Correction: delete "after this prediction was committed"; in the abstract say e.g. "provide a realized-year check of a prediction built solely from fiscal 2024 inputs"; in §sec-fy2025 add one disclosure sentence that the rates were public before the repository's first commit and that the out-of-sample property is data-vintage, not temporal pre-registration. If a verifiable pre-June-24 external commitment exists, cite it instead — none exists in this repo. For a paper whose selling point is verification discipline, a checkable false pre-registration claim is disqualifying as written.

**2. BLOCKING — adopting the feature round ("is retained") leaves sibling passages and @tbl-validate stale against the regenerated committed artifacts — the exact failure mode the introduction claims is "all corrected here."**
The in-scope paragraph's own numbers all verify: *"classifier ROC AUC 0.7666 to 0.7679"* (= 0.766626→0.767947, `analysis/model_results.json` and `analysis/FEATURES_REPORT.md`), *"hurdle stage-1 AUC 0.8356 to 0.8397"* (0.835617→0.839738), *"equal-state calibration MAE 1.83 to 1.71"* (1.827→1.714; new value 1.7144 confirmed), *"mean absolute gap 4.38 to 4.64"* (4.3761→4.6438). But the regeneration replaced the artifact values that unchanged text still quotes, and the old values survive in no committed artifact:
- @tbl-validate: 1.81pp / 1.65pp / 0.885pp / 0.785pp / corr 0.90 vs committed 1.8434 / 1.5421 / 0.8746 / 0.8083 / 0.9092 [note: the fix applied used the matched FY2024 frozen-model rows 1.7285/1.5699/0.5624 for the unfactored column — the same block the old 1.8097/1.6466/0.5176 values came from].
- *"calibrated AUC 0.686 in the shipped frozen configuration"* vs committed 0.6998.
- Coverage gaps *"−0.2 to −7.4 points"* vs committed −0.38 to −7.30 ("two of nine" and "worst at the 75th–90th" remain true).
- Tail *"log scale 0.271"* vs committed `scale_log` 0.2516 (the "from 0.467" still matches, 0.4662).
- *"$183 against $189"* vs committed $185.7 / $189.3. (The Duan smear 1.173 still matches: 1.1726.)
- The QRF benchmark sentence ("4.10 against 4.38 … the gradient-boosted stack is retained") now describes a benchmark run against the superseded stack; the retained stack (4.64) was never QRF-benchmarked.
Correction: regenerate the sibling numbers from the new artifacts with supersession notes in the fact catalog, or explicitly date-stamp @tbl-validate and the validation paragraph as pre-feature-round with `analysis/FEATURES_REPORT.md` as provenance for the old values.

**3. MINOR — the fact catalog was not extended for any new claim.** `paper/FACTS.md` ends at row I7; there are no rows for the FY2025 movement set, the FY2027 threshold, the FNA rename, the feature-round metrics, or the election pricing, and existing rows E1/E2/E4/E5 are now stale against artifacts with no supersession notes. Correction: add a J-series of rows (and supersession notes on E2/E4/E5).

**4. MINOR — "All figures quote the committed movement artifact" overreaches within the subsection, and two figures are pinned nowhere.** The movement, z, τ, roster, tail, and national figures all do quote `analysis/fy2025_movement.json` (verified). But the *"roughly $63M a year"* repricing comes from `paper/snapshot/labs/results_by_state_corrected.json` (FACTS F2: $63.4M), the June 24 date from `fy2025_movement.py`/`references.bib`, and the *"53% probability … worth about $31M a year"* election figures are runtime outputs of `app/public/app.js` (`electionStats`, seed 11, 4000 draws) committed in no data artifact. Mechanics and magnitudes verified correct. Correction: scope the sentence to the movement figures and commit the election numbers to an artifact or FACTS row.

**5. MINOR — the rename parenthetical's justification clause and the publisher attribution.** The rename date is correct (announced April 30, 2026; effective June 1, 2026 — verified externally). But the FY2025 PER is an FNA publication; "FNS published the fiscal 2025 rates" names an agency that no longer existed under that name on June 24. Correction applied: "the renamed agency published" and the parenthetical now cites the letterhead.

**6. MINOR — the 18-vs-10 juxtaposition invites a false subset reading.** Both counts are correct, but the sets overlap in only **7** states — DE, FL, and IL cleared the noise bar without changing tiers (all 15% both years), so **11 of the 18 tier changes are within the noise band**. The natural reading ("10 of the 18") is false, and the true overlap is actually the sharper version of the paper's point.

**7. MINOR — "Process drift is real" over-asserts relative to the committed uncertainty and caveats.** The robust CI (0–1.74) includes zero, 5.4% of robust bootstrap draws hit the zero boundary, and a single transition conflates any FY2024→FY2025 QC-methodology or administrative change with process drift. "Comparable in scale to sampling noise" is fair (τ 1.07–1.62 vs the two-year sampling SD ≈ 1.12pp).

**8. MINOR — "New Jersey's improvement" attributes cause.** The −7.47pp move is established as non-noise, but improvement-vs-measurement-practice change is not identified.

**9. MINOR — the delay footnote's "first bill in FY2029" is stated unconditionally.** If a state's fiscal 2026 rate also crosses — near-certain for Alaska — the start moves to FY2030.

**10. NIT — "Five of the slots … turned over"**: the FY2024 roster is counterfactual and "turned over" mislabels net exits (5 dropped, 2 joined, 10→7).

**11. NIT — "state-pair bootstrap"** can be read as resampling pairs of states; the artifact's method is a paired i.i.d. bootstrap over jurisdiction (Δ, sampling-SD) rows.

**12. NIT — abstract's "beyond what two years of sampling noise explains"** drops the 95% qualifier; "explains" reads as attribution where the criterion is non-rejection.

**13. NIT — the 53%/$31M juxtaposition** invites the wrong arithmetic: 53% is P(FY2026 draw below the locked 10.09% *rate*), while the $31M expectation is driven by P(draw below the 10% *tier boundary*) ≈ 49% times the $63.4M step.

### Verified correct (explicitly checked, no discrepancies)

- **2.77-SD criterion**: stated exactly per the artifact's `z_convention` — z denominates by the FY2024 sampling SD only; under independence and equal SDs, Var(Δ)=2σ², so the 95% band is |Δ|/σ > 1.96·√2 = 2.772 ≈ 2.77. Borderline flags all consistent (AL 2.09, AZ 2.48, NM 2.56, VI 2.37 not flagged; FL −3.01, MN 3.04 flagged).
- **Variance decomposition**: recomputed 2·mean(sd²) = 1.2576 from all 53 SDs (artifact 1.2577), τ² = 3.8843−1.2577 = 2.6266, τ = 1.6207 → "1.62" ✓; CI 0.81–2.25 ✓; robust chain (MAD 1.03 → 2.332 → τ 1.074, CI 0–1.74) ✓.
- **Movement figures**: 18/53 ✓; ten beyond-noise states exactly ✓; median 1.38 ✓; CO/HI/NJ/KY exhibit rows ✓; national 10.93→10.62 ✓; seed 11 / 4000 draws ✓.
- **Delay rosters**: FY2025 seven ✓; FY2024 ten incl. NY 14.09 ✓; NY FY2025 13.18 below threshold ✓; roster deltas ✓; citation matches the artifact's delay rule, the intro, FACTS A3, and the app's `delayMet`; zero-dollar delay modeling matches `electionStats`/`zero28`/`bill29`.
- **FY2027 parenthetical**: every number matches the artifact; floor uniqueness self-test confirmed (incl. the 54.999684 → 54 case that kills nearest-rounding); $60 boundary 37938/37 = 1025.3514 → $1,025.40 ✓.
- **Feature round**: all counts, semantics, metric pairs, and the Colorado band mapping match `analysis/FEATURES_REPORT.md` and the regenerated artifacts.
- **Dates/naming**: June 24, 2026 ✓; FNA rename effective June 1, 2026 confirmed externally.
- **No causal overreach** beyond findings 7–8; the mechanism framing of §sec-fy2025 is the right one — it just must not be dressed as temporal pre-registration (finding 1).

Bottom line: the numbers in the delta are clean — every artifact-backed figure verifies, several re-derived from scratch. The two blockers are claims *about* the evidence, not the evidence.
