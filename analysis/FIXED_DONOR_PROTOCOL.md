# Fixed-donor robustness protocol for the Rhode Island decomposition

Status: frozen before estimation, 2026-08-16. Sibling of
`UHIP_DECOMPOSITION_PROTOCOL.md` (sha ffbf63b1…), motivated by the
design finding recorded in `UHIP_DECOMPOSITION_DEVIATIONS.md`: the
inherited estimator fits donor weights jointly across every outcome in
a run, so the client placebo's permutation p moved from 0.233 (parent
run: strict + total + client) to 0.023 (decomposition run: eight
channels + client) on identical data. This protocol removes that
dependence and pre-registers what a fixed synthetic Rhode Island
implies for every channel.

## Change from the parent estimator (the only change)

Donor weights are fit ONCE, on the parent study's exact outcome set —
`strict_computing_dollars_per_case_month`, `total_error_rate`,
`client_dollars_per_case_month` — with the parent's scaling, donor
pool, exclusions, primary specification (exclude FY2016, drop
FY2021), and optimizer. The fitted weights are then held fixed and
applied to every decomposition channel outcome and to the client
placebo. Channels vary only the outcome; the synthetic Rhode Island
does not move.

Placebo-in-space inference is inherited unchanged, with the same
fixity: for each pseudo-treated donor state, weights are fit once on
the three parent outcomes (excluding that state from its own donor
set) and held for every channel. The finite-sample p-value rule,
plus-one convention, and tie handling are the parent's.

## Pre-registered expectations, stated before running

1. The fixed-donor client placebo must reproduce the parent's client
   effect and p exactly (+3.964, p = 0.233, rank 10 of 43), because
   the fit is the parent's fit. This is a reproduction check; failure
   is a bug, not a finding.
2. Channel effects will differ from the joint-fit run. No direction is
   predicted. The reader should compare the two runs side by side; the
   artifact reports both.

## Outcomes, power gate, verdicts

Identical to `UHIP_DECOMPOSITION_PROTOCOL.md`: the same seven channels
plus `defect_or_mass_change`; the same count-based inferential set
(`mass_change`, `disregard`, `defect_or_mass_change`) and descriptive
set; the parent reporting rule at 0.10 with the inherited client
placebo (now the parent's own), and the family-adjusted verdict at
0.10/3; the verdict-inert consequence-window profile per inferential
channel. The Rhode Island-internal descriptive layers are not
re-estimated (they have no donor).

## Artifacts

`analysis/fixed_donor_decomposition.py` (extends the decomposition
module; the only new code is the fit-once/hold-fixed path),
`analysis/fixed_donor_decomposition_results.json` (both runs' channel
tables side by side, the reproduction check with its pass/fail flag,
donor weights, ranks, p-values, both verdicts, environment and input
hashes, both protocol sha256s), tests (fast artifact locks: schema,
reproduction-check flag TRUE, inferential/descriptive membership,
verdict/p consistency, both protocol pins; fixture determinism +
planted-effect tolerance; value-locked skipif-gated raw regeneration).

## Language

Unchanged: bundled system replacement as implemented; channels
describe how QC coding classified UHIP's failures. The fixed-donor
result and the joint-fit result are two pre-specified estimators of
the same estimand; neither is "the" answer, and the causal paper
reports both with the reproduction check as the bridge.
