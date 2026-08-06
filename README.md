# snap-qc-sim

**Interactive tool: https://snap-qc-sim.vercel.app** — pick a state, adjust
audit volume and simplification options, watch the measured-rate
distribution and the cost-share bill respond. States whose encoded rules
are verified against their full QC sample (CO, NY, CA, AZ, GA, MD, TX)
carry a verification badge.

Monte Carlo simulation of SNAP payment error rates: given a state's USDA
Quality Control sample, simulate the distribution of its **measured** payment
error rate — and therefore its 7 USC 2013(a)(2) cost-share tier and dollars —
under two kinds of state choice:

- **audit volume**: the QC sample size (states may voluntarily review more
  cases than the federal minimum);
- **policy simplification options** that standardize away whole error
  categories: the standard medical deduction, standard self-employment
  deduction, heat-and-eat, and broad-based categorical eligibility.

Beginning FY 2028, a state's payment error rate sets its share of SNAP
benefit costs (0% below a 6% rate, 5% from 6–8, 10% from 8–10, 15% at or
above 10), keyed initially to its FY 2025 or FY 2026 rate. Small rate
movements near a boundary are therefore worth roughly 5% of a state's annual
issuance — tens of millions of dollars for mid-sized states — and sampling
noise alone materially affects tier assignment.

## What v0.1 finds (FY 2024 file, all 53 jurisdictions)

- **Tier assignment is noisy.** Several states' tiers are near coin flips
  under QC sampling variation (Colorado: official rate 9.97%, 0.03 points
  from the 15% boundary, with a ±0.9-point sampling SD).
- **Simplification options carry large expected values** where they can move
  a state across a boundary: on the order of $600M/yr in combined expected
  state cost-share reduction nationally at 50% category-suppression
  effectiveness.
- **The audit-volume effect is two-sided.** More audits shrink variance
  around the state's underlying rate: that lowers expected cost share for
  states just below a boundary and raises it for states just above one,
  while reducing the variance of the bill in both cases.

Numbers above are FY 2024-sample estimates with the caveats below; treat
them as illustrative magnitudes, not forecasts.

## Method

The state's QC public-use sample supplies the error process (which cases
carry errors above the official threshold, their dollar sizes, and their
finding-element categories). Scenarios re-draw QC-style samples of the
chosen size and recompute the weighted measured rate, centered on the
official published rate. Policy levers suppress the error contribution of
the element categories they standardize away, at a chosen effectiveness.

```python
from snap_qc_sim import load_cases, load_official_rates, simulate, summarize, LEVERS

cases = load_cases("qc_pub_fy2024.csv")["CO"]
official = load_official_rates("snap-fy24QC-PER.pdf")["CO"]
rates = simulate(cases, official, extra_audits=500,
                 suppressed=LEVERS["smd"], effectiveness=0.5)
summarize(rates, issuance=1.27e9)
```

Data: the [SNAP QC public-use files](https://snapqcdata.net/datafiles) and
FNS's published payment error rate tables.

## Caveats

- Lever *effectiveness* is a scenario dial, not a causal estimate;
  states adopt options endogenously and standardization suppresses
  categories only partially in practice.
- The underlying error process is held fixed: no behavioral response and no
  corrective-feedback channel from auditing more cases.
- Case bootstrap approximates the stratified monthly QC design; official
  rates embed a regression adjustment this model applies only as a level.
- Element attribution is single-shot (a case's error is split evenly across
  its finding elements).
- The QC sample is designed for national estimates; within-state dollar
  levels carry wide uncertainty. Shares and comparative statics are more
  robust than levels.

## Roadmap

The lever mechanism in v0.1 is an accounting bound. The v2 design —
a case-level error model trained on policy-affected intermediate
variables (documentation and verification burdens) that the rules engine
recomputes under alternative policies — is specified in
[docs/v2-error-model.md](docs/v2-error-model.md).

- Caseload-based v2: state caseloads from calibrated survey microdata aged
  to FY 2026–28, benefits repriced under changed rules by
  [PolicyEngine](https://github.com/PolicyEngine/policyengine-us) /
  [Axiom](https://github.com/TheAxiomFoundation/rulespec-us) rules
  (so options change benefits, not only error categories), with
  characteristic-based error models.
- Record-realism scoring of QC households against calibrated microdata.
- Stratified sampling design; per-lever empirical effectiveness estimates.

Grew out of open collaboration with Eric Giannella's
[snap_qc](https://github.com/giannella/snap_qc) error-modeling work and Ben
Molin's [SNAP Screener QC analysis](https://www.snapscreener.com/blog/qc-data).

## License

Apache-2.0
