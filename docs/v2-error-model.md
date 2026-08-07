# v2 design: a case-level error model with engine-recomputed intermediates

v1's policy levers are accounting bounds: they remove observed error dollars
in the finding-element categories a policy standardizes away. That can only
delete errors; it cannot generate the errors a new regime creates, reprice
benefits, or shift composition. v2 is the proposed replacement: a case-level
model in which policy enters only through variables a rules engine can
recompute.

This repository contains the corrected diagnostic v2a pipeline and a v2b
signed per-case deviation distribution. It exports FY2024 model parameters for
a browser. A model-based simulator mode consuming that export was implemented
(PR #9) and is currently disabled in production pending fixes from the
2026-08-06 adversarial statistical review (tail refit at the attachment depth,
per-state level factors, 53-state dollar-rate validation; see
paper/reviews/round-1/code-stats-redteam.md).

## Implementation status

Statuses describe this repository after the post-audit correction round, not
the external engine or `amterr-lab` work.

| component | status | current boundary |
|---|---|---|
| QC universe, schema checks, and official-error label | Implemented | Uses `CASE == 1`; required columns must exist; the label is `STATUS` in `{2, 3}` and `AMTERR` above the fiscal-year threshold. |
| QC-derived household and burden features | Partially implemented | Includes the available medical, self-employment, utility, deduction-count, and benefit-position proxies. Asset verification, child-support verification, pay-frequency conversion, and distances to eligibility discontinuities remain absent. |
| Diagnostic official-error classifiers | Implemented | Compares a common covariate-plus-formula-anchor baseline with the nested baseline-plus-burden-intermediates specification in the FY2024 evaluation sample. FY2024 has informed pipeline development and is not described as a pristine holdout. |
| v2a hurdle probabilities and conditional magnitude mean | Implemented | Estimates cross-fitted isotonic stage probabilities and an expected absolute magnitude with out-of-fold Duan smearing. It does not estimate a signed conditional distribution. |
| State calibration validation | Implemented | Fits through FY2022, estimates shrunken state factors from FY2023, freezes them, and evaluates factor-adjusted results on FY2024. FY2024-derived factors are descriptive anchors only. |
| Medical-error and SMD contrasts | Implemented | Weighted descriptive contrasts use the state-year SMD registry, aligned calendar cells, event counts, and both a post-treatment-conditioned claimant denominator and a stable all-elderly/disabled denominator. They are not causal estimates. |
| Engine recomputation under alternative policies | Not implemented | Current intermediates are extracted from QC fields; the rules engine does not yet regenerate them under a counterfactual policy. |
| Signed conditional deviation distribution and assigned-benefit draws | Implemented | Estimates calibrated sign probabilities and nine conditional `log(|D|)` quantiles among deviators, sorts each predicted vector, extends q99 with a training-only OOF-residual log-exponential tail, and exports parameters for signed draws. Native HistGB quantile loss preserves the hurdle's feature, missing-value, and HWGT behavior without adding a dependency. Sign and magnitude are conditionally independent given features. |
| Computation-failure mixture probability π | Not implemented | No separate computation-failure channel or policy lever is estimated or simulated. |
| Input-noise tier | Not implemented | Corrected-versus-original input pairs are not training data for this repository's pipeline. |
| Event-study or causal DiD validation | Not implemented | The SMD results are descriptive weighted pre/post contrasts only. |
| Simulator integration and counterfactual aggregation | Implemented, disabled | A model-based mode (bootstrap + per-case redraw, official-anchored) ships in the app but is hidden in production pending adversarial-review fixes; counterfactual aggregation remains not implemented; the observed mode keeps the accounting-bound levers. |
| Forward caseload projection | Not implemented | No calibrated FY2026–28 survey-microdata projection is part of this pipeline. |

## Round-2 spine: Microcosm population simulation (approved direction, 2026-08-07)

The QC file supports counterfactuals whose affected population is already
enrolled: intensive-margin changes in both directions, and extensive-margin
exits. Extensive-margin entries — eligibility expansions — require a
population dataset. The approved round-2 design: Microcosm survey microdata
supplies the population (including non-participants), aged forward to the
FY2025–27 measurement years; PolicyEngine computes eligibility and benefits
under baseline and counterfactual policy, applying its existing take-up
assumptions (including for newly eligible units); QC-trained error-process
parameters and burden features transfer to Microcosm households by
statistical matching on shared covariates; the engine leg's verified
computations anchor the deterministic chain. This is required even for
baseline projection of the priced FY2025–27 rates, because OBBBA's own
eligibility changes shift caseload composition away from the FY2024 QC file,
and because the cost-share denominator (issuance) moves under eligibility
change. Take-up among newly eligible units uses PolicyEngine's take-up
machinery; imputation quality and match diagnostics get the same adversarial
treatment as everything else here.

## The core idea

The target architecture trains the error process on **policy-affected
intermediate variables**: the documentation, verification, and computation
burdens a case carries. A rules engine could then recompute those variables
under another policy.

| target intermediate (per case) | which policies move it |
|---|---|
| itemized medical documentation required | standard medical deduction and its size |
| self-employment expense records required | standard self-employment deduction |
| utility bills required versus standard allowance entitled | heat-and-eat, SUA policy |
| asset verification required | BBCE resource exemption |
| child-support payment verification required | CS deduction versus exclusion election |
| income conversion or averaging required | reporting and simplified-reporting options |
| number of deductions entering the computation | all of the above |
| distance to the nearest eligibility or benefit discontinuity | BBCE, gross/net tests, allotment structure |
| at maximum or minimum allotment | allotment structure |

The current `med_doc_required` variable is only a proxy. It applies the $35
excess-expense gate (`FSMEDEXP > 35`), but does not yet model the state's
standard amount, whether that standard binds for the case, or documentation
of actual expenses above the standard. These are known feature gaps.

An earlier exploratory cross-section found medical-element error rates of
6.9% in SMD state-year cells and 4.5% in non-SMD cells among elderly or
disabled claimants. That is a 1.5-times contrast, not an order of magnitude,
and it does not identify a policy mechanism or causal effect.

## Why the engine matters here

A verified rules engine can, in principle, compute whether a medical
deduction binds, whether documentation is required, how many
verification-sensitive inputs enter the chain, the formula benefit, and the
distance to each discontinuity. Those counterfactual recomputations are not
performed by this repository today.

Related engine-validation work lives outside this repository; see
`axiom-oracles` PRs [#244](https://github.com/TheAxiomFoundation/axiom-oracles/pull/244),
[#268](https://github.com/TheAxiomFoundation/axiom-oracles/pull/268), and
[#269](https://github.com/TheAxiomFoundation/axiom-oracles/pull/269), plus the
[Colorado FY2024 SNAP QC report](https://axiom.org/reports/colorado-snap-qc-fy2024).
This repository contains no artifact establishing exact seven-state parity
for all cases and stages, so it makes no such claim.

## Training and validation protocol

- Training years are FY2017–19 and FY2022–23. FY2020–21 remain excluded, and
  FY2024 is the evaluation year. Because FY2024 results informed development,
  they are not a pristine final holdout.
- A stage-1 adjudicated-benefit deviation is defined using a currency tolerance
  of `|D| > 0.5`, rather than exact floating-point inequality. Stage 2 is fit
  only within those stage-1 positives. The handful of official errors with a
  public-file reconciliation anomaly (`|D| <= 0.5`) retain their diagnostic
  label but are counted and excluded from the stage-2 and magnitude fits.
- The diagnostic official-error label uses each year's official `AMTERR`
  threshold. It is not constructed from a benefit difference.
- A medical outcome requires that official label plus a medical element with
  payment impact in the same detailed finding slot: `ELEMENTi == 365`,
  `E_FINDGi ∈ {2, 3, 4}`, and `AMOUNTi > 0`, scanning all nine public slots.
- Stage probabilities are calibrated out of fold within the training data;
  Duan's smearing factor is also estimated from out-of-fold residuals.
- Headline FY2024 calibration is unfactored and reported both with equal
  jurisdiction weight and with issuance weight.
- State factors are learned without FY2024: fit the model through FY2022,
  predict FY2023, shrink FY2023 observed-to-predicted ratios toward one using
  effective-sample-size precision, and apply the frozen factors in FY2024.
- SMD adoption timing comes from the state-year registry. Medical contrasts
  align treated states and controls to the same pre- and post-adoption
  calendar cells. They are descriptive weighted contrasts, not a natural
  experiment or causal validation.
- Distributional validation aggregates signed case draws using the official
  centering convention and compares them with corrected observed bootstraps.
  The app's (currently disabled) model-based mode instead bootstraps cases
  and redraws deviations, anchored at the model's own baseline mean — a
  configuration not yet validated; see the review findings.

### Reproducing the analysis

The QC microdata are not committed. With the six `qc_pub_fy*.sav` inputs and
the state-year standard-medical-deduction CSV in the cache paths recorded in
the output provenance, regenerate every checked-in analysis artifact with:

```sh
uv run --frozen --extra analysis python analysis/run_all.py
```

The entry point stages all three analysis JSON files, the generated
`analysis/FINDINGS.md`, and `app/public/model_data.json` before replacing any
of them. The JSON provenance records the Python package versions, SHA256 for
each source input, threshold map, random seeds, quantile grid, tail fit, and OOF
settings.

## Targets and estimands

The diagnostic label and the deviation target serve different purposes and
must not be substituted for one another:

- **Official-error label:** `STATUS ∈ {2, 3}` and `AMTERR` exceeds the
  fiscal-year threshold. These are adjudication fields.
- **Signed adjudicated deviation:** `D = RAWBEN − BENFIX`, where `RAWBEN` is
  the issued allotment and `BENFIX` is the allotment adjusted for errors.
- **Formula anchor:** `FSBEN`, exposed to the model as `formula_benefit`, is an
  engine-computable feature. It is deliberately not used to define either
  label.

This distinction matters because `BENFIX` incorporates the legitimate
adjustments recognized in adjudication, including adjustments such as
proration. Therefore, `RAWBEN − FSBEN` can mix error with legitimate
adjustments. In weighted FY2024 data, `|RAWBEN − BENFIX| == AMTERR` for
99.99689% of cases, compared with 83.64472% for
`|RAWBEN − FSBEN| == AMTERR`.

The implemented diagnostic hurdle has three pieces:

1. `P(|D| > 0.5 | features)`.
2. `P(official error | stage-1 positive, features)`.
3. `E(|D| | official error, features)`.

It composes these into expected absolute error dollars. The measured payment
error rate is **weighted error dollars divided by weighted issuance**. An
official-error probability is a threshold-crossing probability, but the
payment error rate is not.

The v2b extension learns the signed conditional distribution of deviation:

1. `P(|D| > 0.5 | features)` from the existing calibrated stage 1.
2. `P(D > 0 | |D| > 0.5, features)` with a separately calibrated classifier.
3. Nine conditional quantiles of `log(|D|)` among deviators, with log-linear
   interpolation and a fitted exponential excess above q99.

The resulting draw sets `D = 0` for nondeviators and samples sign and magnitude
independently conditional on features. A future counterfactual rules engine
could compute policy-specific benefits and intermediates before applying these
draws. This repository does not yet perform that engine recomputation; the
exported process is wired into the app's model-based mode, which is disabled
in production pending validation fixes.

## Proposed counterfactual tiers

- **v2b distributional extension.** The implemented diagnostic model estimates
  the sign and conditional distribution of `D`, including a q99 tail, rather
  than only two probabilities and a conditional mean. The formula benefit
  remains both an anchor and a covariate. The implementation predicts the
  FY2024 error process from FY2017–19 and FY2022–23 data; it does not establish
  causal policy effects or transport to thresholds outside the observed
  setting without additional validation.
- **Computation-failure mixture.** Separate cases whose issuance can be
  reproduced by correct arithmetic on incorrect inputs from cases requiring
  another computation-error channel. The external `amterr-lab` analysis
  reports that 246 of 283 qualifying Colorado FY2024 cases are reproduced by
  the original inputs. That 246/283 result is not generated or stored by this
  repository; its external context is in the
  [Colorado report](https://axiom.org/reports/colorado-snap-qc-fy2024) and
  `axiom-oracles` PRs
  [#268](https://github.com/TheAxiomFoundation/axiom-oracles/pull/268) and
  [#269](https://github.com/TheAxiomFoundation/axiom-oracles/pull/269). Estimating
  a mixture probability π and treating it as a policy lever remain future work.
- **v2b input-noise model.** Model which inputs differ and by how much, given
  documentation and verification burdens, then run the engine on true and
  noised inputs. The ML component would model input noise while the engine
  carries policy geometry, including new thresholds and cliffs. Preparing
  portable training pairs and adding a computation-side error process remain
  future work.

The rule-mining program this design grew alongside solves a different
problem: explainable review guidance for auditors under the current policy
regime. Its outputs are review lists, not counterfactual predictions. What can
transfer is mechanics such as holdout discipline, budget-denominated
reporting, and household observables; its benchmarks do not transfer
directly.

Feature discipline for every counterfactual tier is strict: a feature that
encodes the policy regime—a direct option indicator or a regime-carrying case
fact such as categorical-eligibility code—must be excluded as a static
covariate or promoted to an engine-recomputed intermediate. Otherwise, a
counterfactual silently holds the old regime fixed. The corrected diagnostic
pipeline therefore excludes `CAT_ELIG` from its static covariates.

## Next steps for v2b

These are explicit future steps, not claims about the current pipeline:

1. Replace QC proxies with engine-recomputed intermediates, including state
   medical-standard amounts, whether the standard binds, actuals above the
   standard, verification requirements, and distances to discontinuities.
2. Integrate the exported signed-deviation process with policy-specific engine
   outputs and the live simulator, retaining the current app mechanism as a
   labeled comparison.
3. Build and estimate the separate computation-failure mixture π.
4. Prepare input-noise training pairs and implement the mechanistic v2b tier.
5. Design a credible event-study validation; do not relabel the existing SMD
   descriptive contrasts as DiD.
6. Validate the conditional-independence assumption between sign and magnitude
   and assess tail stability in later QC years.
7. Replace the FY2024 QC sample with calibrated survey microdata aged to
   FY2026–28 for forward-looking estimates.
