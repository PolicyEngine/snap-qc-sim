# SNAP QC oracle-suite comparison reports (seven verified states)

These seven JSON files are byte-identical copies of the committed
axiom-oracles dashboard comparison reports for the FY2024 SNAP QC replay
suites, taken from `TheAxiomFoundation/axiom-oracles` at commit
`f30f9a1014ec957d26dcffd33af4356a48b9f174`
(`dashboard/public/data/axiom-snapqc-{state}-snap.json`). Verify any copy
against the source repository with:

```bash
git -C <axiom-oracles> show f30f9a1014ec:dashboard/public/data/axiom-snapqc-co-snap.json | shasum -a 256
```

Each report carries the suite's own facts: the six compared stages with
zero-tolerance match counts (`aggregates`), the per-case matched rows
(`cases`), the exclusion log (`summary.exclusions`, all `ssi_cap` —
SSI-CAP standardized-benefit units use a separate benefit procedure;
NYSCAP units follow the regular chain and are in scope), the QC
source-archive pin (`summary.provenance.pins`), and the generating run's
overlay file hashes. The registry re-emits committed reports on runners
without the engine and data (`provenance.reemitted_report`), so the
top-level `generated_at` reflects the latest registry pass while
`summary.provenance` reflects the generating run.

`analysis/engine_comparison.py` re-derives the parity counts from these
copies, asserts exactness, and records each file's SHA-256 in
`analysis/engine_comparison.json`; `tests/test_engine_comparison.py`
locks the hashes and the derivation. The app's engine mode displays only
numbers that trace here or to `analysis/engine_comparison.json`.
