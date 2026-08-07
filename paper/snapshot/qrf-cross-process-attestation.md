# QRF benchmark cross-process determinism attestation

Date: 2026-08-07. Recorded by the merge gate for PR #15.

The benchmark's own run (committed as `analysis/qrf_benchmark_results.json`)
executes two full repetitions in one process and records identical
deterministic-core hashes. Before merging, the gate additionally re-ran the
complete benchmark in a separate process from a clean invocation:

```
uv run --frozen --extra dev --extra analysis python analysis/qrf_benchmark.py \
  --json-output <scratch>/results.json --markdown-output <scratch>/report.md
```

Both repetitions of that independent run reproduced the identical hashes:

- deterministic core SHA-256 (both repetitions, both processes):
  `817d5925b850de46bb3b0c28627f9fda7b698996a505f717fef98a0284c24e0d`
- per-estimator GBM SHA-256:
  `53297e28bbd161d59f4aea9ee2b2456933fd49020de78c55be00392f588bc685`
- per-estimator QRF SHA-256:
  `17ed4b886d80a11310a83f807a9039dddd5cbdb3e2d3f20c6020c97391e0c3b0`

Hash algorithm: SHA-256 over sorted compact strict JSON, timings excluded
(the benchmark's `determinism` block documents the construction). The
independent run's full results file matched the committed artifact on every
deterministic field.

Pre-registration provenance: the decision rule ("switch only if QRF ties or
wins both mean absolute FY2024 coverage gap and factor-adjusted equal-state
FY2024 dollar-rate MAE") was committed in the protocol commit `3e1b347`,
which precedes the results commit `1d06262`; PR #15's branch history
preserves the ordering, and the rule is additionally embedded in the results
artifact, whose recorded verdict follows it.
