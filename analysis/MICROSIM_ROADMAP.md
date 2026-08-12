# From resampled sample to full-universe microsimulation

Status: architecture memo, 2026-08-12. The claiming issue lives on
PolicyEngine/microcosm; this file is the reference copy beside the code
it will eventually replace.

## Why the current simulator is a scaffold

The deployed simulator resamples the state's own QC sample and anchors
the level to the official rate. That design has served three rungs of
shipping, but it carries three structural compromises, all documented
in the paper and the app:

1. **The wedge.** The official rate exceeds the file-computable rate by
   a layer the file never records case-by-case (federal re-review
   integration, ineligible-case error) — a median 31% of the official
   rate, up to 81% (Alaska). Anchoring carries it as a fixed, noiseless,
   policy-invariant offset. All three adjectives are approximations.
2. **Sampling variance is partial.** The wedge components are
   themselves sample-estimated; our draws omit their noise, and the
   audits lever only shrinks the file component's.
3. **Scenario reach is capped.** Every scenario — model-based or
   accounting-bound — moves only file-visible dollars.

## The end state

A payment-error microsimulation on the full caseload universe, split
exactly along the two-institute line:

- **Deterministic layer (Axiom):** the rules engine computes what
  *should* happen to every case — already exact against the recorded
  benefit chains of seven states' QC files, and served through the
  policyengine.py interface as the encodings migrate to rulespec.
- **Estimation layer (Microcosm side):** a case-level model of what
  *does* happen — the deviation process (incidence, size, element mix)
  as a function of case characteristics and state policy features.
  Payment error is the gap between the layers.
- **Measurement layer:** QC measurement becomes what it is in reality —
  drawing a designed sample *from* the universe and applying thresholds
  and review. Sampling noise, sample-size levers, and review-practice
  variation become derived properties instead of the model's core.

The QC public-use files then hold two jobs they are actually suited
for: verification oracle for the deterministic layer (the paper's
central method) and calibration/validation data for the estimation
layer. They stop being the simulation universe.

This also settles the synthesis question correctly: standalone
synthetic QC records answer to no oracle, but a calibrated population
is Microcosm's entire method — the file-uncovered layer (ineligible
determinations) gets represented the way Microcosm represents
everything, disciplined by calibration to the official rate's published
components rather than invented case by case. The error layer stays a
modeled overlay at analysis time — like take-up — never baked into
certified raw data, so the raw-only doctrine holds.

## What exists

- Microcosm's SNAP caseload with administratively calibrated weights,
  and the C1→C3 forward-margin machinery from snap-fy27-margins.
- The certified engine for seven states' benefit computations.
- A distributional error model (GBM hurdle + quantiles) with committed
  validation results — including its failures.
- The FY2024→FY2025 realized transition as an out-of-sample yardstick,
  and quasi-experimental designs (QUASI_EXPERIMENTS.md) that could
  eventually put design-based parameters into the estimation layer.

## What is missing, in order

1. **A load-bearing error model.** The current model fails
   distributional coverage (all nine gaps one-sided negative), carries
   cross-state level gaps, and gates seven jurisdictions. This is the
   critical path; partner-state administrative data is the most
   promising unlock, more file years the second.
2. **QC-grade case detail on Microcosm units.** Deduction composition,
   certification timing, BBCE status — imputation work for which the QC
   files themselves are the natural training source.
3. **Official-component calibration targets.** Per-state overpayment /
   underpayment / ineligible-case components from the QC annual
   reports, ingested with the same hash-registry discipline as
   params/sources — the targets that pin the wedge as model output.

## Rungs

1. *(shipped)* The resample app with the wedge disclosed per state.
2. Component-target registry (missing item 3) — pure data work, no
   modeling, and it upgrades the wedge from one number to a decomposed
   target set.
3. Colorado-first prototype: Microcosm cases × engine benefits ×
   error-model deviations, calibrated to official components, validated
   against the FY2024→25 movement and the QC file's own moments
   (dispersion, cause mix, element mix). Colorado because its encoding
   is verified and its replay decomposition is the deepest.
4. The measurement simulator on the prototype universe: QC sample
   designs, thresholds, review variance — at which point the deployed
   app's sampling machinery becomes a derived special case.
5. Graduation into the microcosm repository proper, behind its
   certification gates.

Rung 3 is where the claim "pure microsim" becomes true for one state;
rungs 4–5 make it the product.
