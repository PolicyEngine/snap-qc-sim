# v2 design: a case-level error model with engine-recomputed intermediates

v1's policy levers are accounting bounds: they remove observed error dollars
in the finding-element categories a policy standardizes away. That can only
delete errors; it cannot generate the errors a new regime creates, reprice
benefits, or shift composition. v2 is the proposed replacement: a case-level
model in which policy enters only through variables a rules engine can
recompute.

This repository contains the corrected diagnostic v2a pipeline and a v2b
signed per-case deviation distribution. It exports FY2024 model parameters for
a browser. The export now includes the attachment-depth tail refit, per-case
physical caps, frozen state dollar factors, and level-gap flags required by the
2026-08-06 adversarial statistical review. A sibling scenario export supplies
case-level SMD adoption parameters and paired-bootstrap intervals in all 53
jurisdictions. The analysis validates the intended browser process with eight
seeds and 4,000 draws per seed. The browser wiring remains unchanged in this
model/export round.

## Implementation status

Statuses describe this repository after the post-audit correction round, not
the external engine or `amterr-lab` work.

| component | status | current boundary |
|---|---|---|
| QC universe, schema checks, and official-error label | Implemented | Uses `CASE == 1`; required columns must exist; the label is `STATUS` in `{2, 3}` and `AMTERR` above the fiscal-year threshold. |
| QC-derived household and burden features | Partially implemented | Includes the available medical, self-employment, utility, deduction-count, and benefit-position proxies. Asset verification, child-support verification, pay-frequency conversion, and distances to eligibility discontinuities remain absent. |
| Diagnostic official-error classifiers | Implemented | Compares a common covariate-plus-formula-anchor baseline with the nested baseline-plus-burden-intermediates specification in the FY2024 evaluation sample. FY2024 has informed pipeline development and is not described as a pristine holdout. |
| v2a hurdle probabilities and conditional magnitude mean | Implemented | Estimates cross-fitted isotonic stage probabilities and an expected absolute magnitude with out-of-fold Duan smearing. It does not estimate a signed conditional distribution. |
| State calibration validation | Implemented | Fits the distributional model through FY2022, estimates EB-shrunken dollar-rate factors from out-of-sample FY2023 state ratios, freezes them, and reports matched raw and factor-adjusted FY2024 dollar rates for all 53 jurisdictions. The EB prior mean is fixed at 1, and the analysis does not propagate factor uncertainty. |
| Medical-error and SMD contrasts | Implemented | Weighted descriptive contrasts use the state-year SMD registry, aligned calendar cells, event counts, and both a post-treatment-conditioned claimant denominator and a stable all-elderly/disabled denominator. They are not causal estimates. |
| Model-primary scenario parameter export | Implemented for SMD only | `model_scenarios.json` reverses the exact case-level `med_doc_required` proxy for current adopters and non-adopters, predicts calibrated `p_dev` and nine magnitude quantiles with the frozen distributional model, normalizes deltas to adoption direction, and ships 10,000-draw paired-bootstrap intervals. The standard self-employment deduction, heat-and-eat, and BBCE are explicitly excluded because the fitted features do not support defensible policy flips. |
| Engine recomputation under alternative policies | Not implemented nationally | The SMD export changes the QC-derived documentation proxy only. The rules engine does not regenerate benefit, deduction, income, or discontinuity features nationally; the separate Colorado join remains the bounded engine-repricing reference. |
| Signed conditional deviation distribution and assigned-benefit draws | Implemented | Estimates calibrated sign probabilities and nine conditional `log(|D|)` quantiles among deviators, sorts each predicted vector, and extends q99 with the weighted mean excess beyond q99 of OOF median residuals. Draws cap `|D|` at `max(BENMAX, observed |D|)` per case-year: `BENMAX`, the case's maximum monthly allotment, supplies the default maximum-allotment-scale ceiling, while the observed-deviation override preserves the 27 realized exceptions. The export omits `p_pos` because measured-rate outputs use only `|D|`. |
| Computation-failure mixture probability π | Not implemented | No separate computation-failure channel or policy lever is estimated or simulated. |
| Input-noise tier | Not implemented | Corrected-versus-original input pairs are not training data for this repository's pipeline. |
| Event-study or causal DiD validation | Not implemented | The SMD results are descriptive weighted pre/post contrasts only. |
| Simulator integration and counterfactual aggregation | Baseline and SMD scenario exports implemented; browser wiring pending | The analysis mirrors case bootstrap, per-occurrence redraw, cap, strict threshold, state factor, model-mean anchor, and zero rate floor for all 53 jurisdictions. The sibling export supplies sparse full flipped parameters, adoption-direction point deltas and CIs, and the seven level-gate flags. `app.js` remains unchanged; observed mode still uses accounting-bound levers until the browser is wired. |
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
distance to each discontinuity. The scenario export now flips the fitted SMD
documentation proxy, but those broader counterfactual engine recomputations
are not performed nationally by this repository today.

Related engine-validation work lives outside this repository; see
`axiom-oracles` PRs [#244](https://github.com/TheAxiomFoundation/axiom-oracles/pull/244),
[#268](https://github.com/TheAxiomFoundation/axiom-oracles/pull/268), and
[#269](https://github.com/TheAxiomFoundation/axiom-oracles/pull/269), plus the
[Colorado FY2024 SNAP QC report](https://axiom.org/reports/colorado-snap-qc-fy2024).
This repository contains no artifact establishing exact seven-state parity
for all cases and stages, so it makes no such claim.

## Training and validation protocol

- Primary diagnostic models use FY2017–19 and FY2022–23. The shipped
  distributional configuration freezes its model after FY2022, fits state
  factors on FY2023 out-of-sample dollar ratios, and evaluates on FY2024.
  FY2020–21 remain excluded. Because FY2024 results informed development, the
  analysis does not treat FY2024 as a pristine final holdout.
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
- State factors are learned without FY2024: fit the model through FY2022,
  predict FY2023, shrink FY2023 observed-to-predicted ratios toward one using
  effective-sample-size precision, and apply the frozen factors in FY2024.
  The analysis reports matched frozen raw and factor-adjusted dollar-rate
  slope, MAE, and correlation with equal-jurisdiction and issuance weighting.
- SMD adoption timing comes from the state-year registry. Medical contrasts
  align treated states and controls to the same pre- and post-adoption
  calendar cells. They are descriptive weighted contrasts, not a natural
  experiment or causal validation.
- Distributional validation reads the same serialized, quantized model-data
  payload exported for the intended disabled model mode. It bootstraps cases
  uniformly, retains HWGT in the ratio, redraws a magnitude for every sampled
  occurrence, caps `|D|`, applies the state factor after the strict threshold,
  anchors each seed at the model's own baseline mean, and clips anchored rates
  at zero downstream. It compares this process with corrected observed
  bootstraps for all 53 jurisdictions.

### Reproducing the analysis

The QC microdata are not committed. With the six `qc_pub_fy*.sav` inputs and
the state-year standard-medical-deduction CSV in the cache paths recorded in
the output provenance, regenerate every checked-in analysis artifact with:

```sh
uv run --frozen --extra analysis python analysis/run_all.py
```

The entry point stages all three analysis JSON files, the generated
`analysis/FINDINGS.md` and `analysis/MODEL_SCENARIOS.md`, and both
`app/public/model_data.json` and `app/public/model_scenarios.json` before
replacing any of them. The JSON provenance records the Python package versions,
SHA256 for each source input, threshold map, random seeds, quantile grid, tail
fit, and OOF settings. The scenario sibling also pins the exact baseline export
SHA256 because its sparse indexes depend on state-local row alignment.
It also records canonical-JSON hashes for `analysis/model_results.json` and the
separately generated `analysis/counterfactual_co_smd.json` engine reference;
`run_all.py` consumes but does not regenerate that Colorado reference.

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
   interpolation and an exponential excess above q99 fit at the same q99
   attachment depth.

The resulting draw sets `D = 0` for nondeviators and samples sign and magnitude
independently conditional on features, then applies the per-case physical cap.
A future counterfactual rules engine could compute policy-specific benefits and
intermediates before applying these draws. This repository now exports the
defensible SMD proxy flip but does not yet perform broader engine recomputation;
the browser consumer does not yet enforce the new scenario fields.

## Proposed counterfactual tiers

- **v2b distributional extension.** The implemented diagnostic model estimates
  the sign and conditional distribution of `D`, including a q99 tail, rather
  than only two probabilities and a conditional mean. The formula benefit
  remains both an anchor and a covariate. The implementation predicts the
  FY2024 error process with a distributional model frozen after FY2022 and
  state factors fit on FY2023; it does not establish causal policy effects or
  transport to thresholds outside the observed setting without additional
  validation.
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
2. Wire the SMD scenario export into the live simulator, then extend the same
   contract only when policy-specific engine outputs support additional levers;
   retain the current app mechanism as a labeled comparison.
3. Build and estimate the separate computation-failure mixture π.
4. Prepare input-noise training pairs and implement the mechanistic v2b tier.
5. Design a credible event-study validation; do not relabel the existing SMD
   descriptive contrasts as DiD.
6. Validate the conditional-independence assumption between sign and magnitude
   and assess tail stability in later QC years.
7. Replace the FY2024 QC sample with calibrated survey microdata aged to
   FY2026–28 for forward-looking estimates.
