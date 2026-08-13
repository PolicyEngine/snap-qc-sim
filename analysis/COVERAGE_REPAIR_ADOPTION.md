# Coverage-repair adoption decision

Written after results and kept OUTSIDE analysis/COVERAGE_REPAIR_PROTOCOL.md
so the pre-registered protocol stays byte-frozen (its SHA-256 is pinned in
analysis/coverage_repair_results.json). An earlier revision appended this
text to the protocol file itself, which broke that pin; relocated here.

## Adoption decision — written after results, labeled as such

The mechanical verdict (USE `conformal_remap`: mean absolute gap
4.644pp to 4.082pp, guards passing) stands as the committed record.
Adoption downstream is declined, for two reasons the pre-registered
rule did not guard:

1. **Per-level pathology.** The remap improves the upper tail (q99
   −3.55pp to −0.35pp) by collapsing the lower one: q05 coverage falls
   from 4.6% to 0.02% (gap −0.38pp to −4.98pp), adding over-3pp flags
   at q05 and q10 where the baseline was clean. A mean-absolute
   criterion allows trading a uniform small miss for tail collapse; a
   v2 protocol needs per-level guards.
2. **The failure is location, not dispersion.** Every mechanism leaves
   all nine gaps negative, and the baseline's worst misses sit at the
   middle levels (q50–q90 near −7pp) with small tail gaps. Coverage
   below nominal at every level means the predicted quantiles sit
   systematically low — a shifted predictive distribution, consistent
   with the documented cross-state level underprediction. Post-hoc
   dispersion surgery redistributes that miss; it cannot clear it.

Consequence: no export, app, or paper artifact consumes any repair
mechanism. The named next experiment is location repair on the
quantile path (state-level calibration of predicted quantile levels,
or a training-objective change), for which partner-state
administrative data remains the strongest unlock.
