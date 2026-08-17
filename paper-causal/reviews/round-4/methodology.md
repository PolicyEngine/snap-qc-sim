# Referee round 4 — methodology findings

Target: `migrations-rev2` at `a9a168c450aeed8c4b0d282c5773b505ba921b3a`.

## Findings

1. **Major — CONFIRMED — the manuscript repeats the adjusted p outside the prescribed three locations.** `0.070` appears in the abstract (`paper-causal/index.qmd:8`), full design disclosure (`:114`), RI-results pointer (`:139`), and limitations (`:267`). The limitations occurrence is not merely a timing disclosure: it repeats the number while asserting the arithmetic appears once in design.

2. **Major — CONFIRMED — the six-test boundary is directionally correct but not reported with the required exact numerical display.** The manuscript gives `0.10/6 = 0.017` and unnamed decimal floors `1/43` and `1/35` (`paper-causal/index.qmd:116–118`). The requested statement is `0.10/6 = 0.0167 < 1/43 = 0.0233` and `1/35 = 0.0286`. No conclusion changes—the threshold remains below both attainable floors—but the round-3 correction did not land in full.

## Artifact checks

- `analysis/riky_event_study_results.json` fixes RI at strict `0.023255813953488372 = 1/43`, client `0.23255813953488372 = 10/43`, verdict `signal`; and KY at strict `0.3023255813953488 = 13/43`, client `0.11627906976744186 = 5/43`, verdict `no_protocol_defined_signal`.
- `analysis/event_study_results.json` fixes OR at strict `0.7142857142857143 = 25/35`, client `0.02857142857142857 = 1/35`, verdict `no_protocol_defined_signal`.
- Bonferroni for RI is `3/43 = 0.069767...`, correctly rounded to `0.070`. Holm tests RI at `3 × 1/43 = 0.069767... < 0.10`, then stops at KY because `0.302325... > 0.05`; the manuscript's “0.302 against 0.05” is numerically right (`paper-causal/index.qmd:112–115`).
- The manuscript states the protocol verdict rule in protocol terms: strict p below `0.10` and client placebo at or above `0.10`, otherwise `no protocol-defined signal` (`:104`). Unit results retain `signal` for RI (`:139`), `no_protocol_defined_signal` for KY (`:158`), and `no_protocol_defined_signal` for OR because its placebo fires (`:175`). These match the JSON artifacts and are unchanged.
- The dependence statement is methodologically correct: RI/KY share the pool and panel, OR overlaps, a product of marginal probabilities does not characterize joint false-positive probability, and Bonferroni remains valid under arbitrary dependence (`:112–123`).
- The pooled statistic is correctly described as aggregation rather than family correction (`:106–109`) and does not replace unit verdicts (`:104`).

## Disposition

The methodology correction is **partially applied**. The central adjusted-p arithmetic, dependence disclosure, family rationale, Holm stopping point, and frozen unit verdicts are correct. The exact six-test numerical boundary and the promised placement discipline are not.
