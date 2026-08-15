# Addendum: where record-level aging actually lives (2026-08-15, follow-up verification)

The feasibility read stated "no record-level uprating" for Microcosm.
Challenged and re-verified directly; the accurate picture has four
layers, each read in code this session:

1. **microcosm-build's own aging is target-side** — confirmed.
   `target_aging.py` ages calibration-target dollar leaves; the ASEC
   pooling scales weights only (`asec_pool.py:100-125`, person-population
   shares; no dollar rescaling).
2. **The PUF ingestion consumes record-uprated dollars.** The processed
   PUF arrives uprated to the target period
   (`puf_e01000_reconciliation.py`: target status
   `uprated_processed_puf_and_frame`; `puf_source_agi.py:352` implies
   per-source uprating factors). Record-side aging exists at ingestion
   for PUF-donored tax concepts.
3. **Engine-time uprating exists but not on SNAP's drivers.**
   policyengine-core uprates any variable with `uprating` metadata when
   simulated beyond its known inputs
   (`policyengine_core/simulations/simulation.py:830-841`); 90
   policyengine-us variable files declare it — but they are tax-side
   concepts (interest, rental, partnership, alimony,
   child_support_received). `employment_income`,
   `self_employment_income`, `rent`, `snap_utility_allowance`, and
   `social_security` declare none.
4. **The adapter freezes record dollars regardless.**
   `PolicyEngineUSAdapter.materialize(bundle, variables, period)` builds
   a `USSingleYearDataset` from the frame's tables *at the requested
   period* (`adapters/policyengine_us.py`, materialize →
   `_build_dataset(tables, period)`), so FY2024-nominal values are
   asserted as e.g. FY2027 inputs and the core uprating path never
   fires. A future-period materialization today = future rules ×
   frozen nominal attributes — the same half-aging as the margins
   pipeline's D-fixed convention.

Historical note: policyengine-us-data (archived) DID age record
variables when building datasets; Microcosm deliberately moved aging to
targets + weight recalibration. Both memories in the room were right
about different layers.

## Consequence for rung 3

Weight-side aging (aged targets + recalibration) cannot substitute for
record-dollar aging here: the SNAP benefit chain is nonlinear in each
case's nominal dollars (maxima, deduction caps, the QC tolerance
threshold), so per-case levels must age for the error layer to price
kinks correctly. The future-year path is therefore a design decision,
not a port:

- (a) declare `uprating` metadata on the SNAP-driver variables in
  policyengine-us and have the adapter build the dataset at the frame's
  vintage period so engine uprating triggers for future requests
  (engine-side; benefits every consumer; changes adapter semantics), or
- (b) record-level uprating in the frame build (the us-data pattern), or
- (c) aged-targets + recalibration only (weights carry growth) —
  insufficient alone for QC error simulation, for the nonlinearity
  reason above.

The 6–12 lane-day estimate for the future-year population path stands;
this addendum replaces its "port C1/C3" framing with the (a)/(b)/(c)
menu and flags the adapter-period semantics as part of the step-1 unit
contract.
