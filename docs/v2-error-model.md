# v2 design: a case-level error model with engine-recomputed intermediates

v1's policy levers are accounting bounds: they remove observed error dollars
in the finding-element categories a policy standardizes away. That can only
delete errors — it cannot generate the errors a new regime creates, reprice
benefits, or shift composition. v2 replaces the dial with a case-level
model, built so that policy enters only through variables a rules engine
can recompute.

## The core idea

Train the error process not on policy indicators but on **policy-affected
intermediate variables** — the documentation, verification, and computation
burdens a case actually carries:

| intermediate (per case) | which policies move it |
|---|---|
| itemized medical documentation required (claims > $35, no binding standard) | standard medical deduction and its size |
| self-employment expense records required | standard self-employment deduction |
| utility bills required vs. standard allowance entitled | heat-and-eat, SUA policy |
| asset verification required | BBCE resource exemption |
| child-support payment verification required | CS deduction vs. exclusion election |
| income conversion/averaging required (pay frequency ≠ monthly) | reporting/simplified-reporting options |
| number of deductions entering the computation | all of the above |
| distance to the nearest eligibility or benefit discontinuity | BBCE, gross/net tests, allotment structure |
| at maximum / minimum allotment (errors partially invisible) | allotment structure |

The error model is P(error, category, magnitude | intermediates, household
covariates), trained on the multi-year national QC file where these
intermediates vary naturally across cases, states, and years. The policy
counterfactual is then mechanical: for each case, the rules engine
recomputes the intermediates (and the correct benefit) under the
alternative policy, and the trained model maps the new burden profile to a
new error process. Errors are generated as well as removed — a case that
newly claims a standard deduction acquires that instrument's own (smaller)
error surface.

Evidence this is the right feature space: jurisdictions where few cases
carry medical documentation burden show category error rates an order of
magnitude below high-burden jurisdictions — the intermediate, not the
policy label, carries the signal.

## Why the engine matters here

The recomputation step is exactly what a verified rules engine provides:
given a QC household and a policy configuration, compute whether the
medical deduction binds, whether documentation is required, how many
verification-sensitive inputs enter the chain, the correct benefit, and the
distance to every discontinuity. The engine behind this project reproduces
FNS's own QC recomputation exactly for seven states (all cases, all
stages), so the feature generator is itself validated against
administrative ground truth.

## Training and validation protocol

- Train on FY 2017–2023, hold out FY 2024 (the protocol used in the
  giannella/snap_qc rule-mining work); robustness folds on earlier years.
- Regime data per state-year from the FNS SNAP State Options Report
  (option adoption) plus the QC technical documentation's demonstration
  tables.
- **Natural-experiment validation**: states that adopted an option
  mid-sample are out-of-sample tests of the counterfactual mechanism —
  predict their post-adoption category error rates using the pre-adoption
  model plus recomputed intermediates, and score against what happened.
  This is the test that separates a validated counterfactual from a
  scenario dial.
- Aggregate per-case predictions through the same QC sampling layer v1
  ships, so measured-rate distributions, tier probabilities, and
  cost-share dollars come out the other end unchanged in form.

## The modeling target: assigned benefits, not errors

(Reframe, 2026-08-06.) For policy counterfactuals the error cannot be the
modeling target: an error is defined relative to a true benefit that the
policy changes. The estimand is the ASSIGNED benefit — what the agency
actually issues — modeled as a distribution conditional on the household
and its intermediates; the rules engine computes the TRUE benefit under
any policy; the error is their difference, and the measured rate is a
threshold-crossing probability, P(|assigned − true| > the official
threshold). Distributional models (quantile regression forests) rather
than classifiers, because threshold crossings live in the tails.

Two tiers:

- **v2a — deviation model.** Learn D = assigned − true directly from the
  QC file (RAWBEN − FSBEN per case) as a conditional distribution on
  intermediates and covariates. Under policy P′: engine recomputes true′
  and the intermediates; predict D′; assigned′ = true′ + D′. Fast, one
  model, moderately portable.
- **v2b — input-noise model (fully mechanistic).** Most deviations are
  correct arithmetic on wrong inputs (86.9% of replayable error cases in
  the Colorado AMTERR replay), so model the input-misreport process —
  which inputs deviate, by how much, given documentation and verification
  burdens — and run the engine twice per case (true inputs, noised
  inputs). The ML surface shrinks to input noise; the engine carries all
  policy geometry, including new thresholds and cliffs. Training pairs
  (original vs corrected inputs per error case) already exist from the
  giannella/snap_qc raw-value reconstruction. Computation-side errors (the
  small engine-verified class) enter as a separate additive process.

The rule-mining program this grew alongside solves a different problem —
explainable review guidance for auditors under the CURRENT policy regime —
and its outputs are review lists, not predictions. What transfers is
mechanics (holdout discipline, budget-denominated reporting, household
observables); its benchmarks do not (an explainability-constrained
per-state list and an unconstrained pooled score are different objects),
and neither do regime-embedded features. Feature discipline for the
counterfactual tiers: any feature that encodes the policy regime — direct
option indicators, and regime-carrying case facts like the categorical-
eligibility code, which embeds BBCE adoption — is either excluded or
promoted to an engine-recomputed intermediate. It must never enter as a
static covariate, or the counterfactual silently holds the old regime
fixed.

## Staging

1. Feature extraction: per-case intermediates for the QC file via the
   federal 273.10 chain (all states) and full state compositions (verified
   states), plus the state-year option registry.
2. Error model: start from the existing rule-mining/gradient-boosting
   results; add the intermediates; publish lift vs. the no-intermediates
   baseline.
3. Natural-experiment scorecard for mid-sample adopters.
4. Wire into the simulator: levers become policy configurations passed to
   the engine; the accounting bound remains as a labeled comparison.
5. Caseload projection (calibrated survey microdata aged to FY 2026–28)
   replaces the FY 2024 sample for forward-looking bills.
