# Reproducibility referee findings

1. **major — CONFIRMED — The manuscript does not give a reader a complete regeneration map.** It names protocols and, once, `fixed_donor_decomposition_results.json`, but it does not anchor each table/claim to artifact key paths or cite the generator commands and tests. A reader can audit the committed values only by reconstructing the unpublished map supplied in `FACTS.md`.

2. **major — CONFIRMED — The parent event artifacts omit provenance carried by the decomposition artifacts.** `riky_event_study_results.json` and `event_study_results.json` contain no protocol hash, raw-input hashes, or environment block. The decomposition and fixed-donor artifacts do. Thus the two parent artifacts cannot by themselves prove which frozen protocol bytes and raw files produced them.

3. **major — CONFIRMED — Raw regeneration depends on an external cache not distributed with the paper.** The protocols say regeneration reads cached public files and skips unless the hash-audited cache is present. The repository commits hashes and loaders, but not the FY2012–24 raw source files. The manuscript neither identifies a download/build procedure for the complete mixed-format cache nor explains expected skip behavior.

4. **minor — CONFIRMED — The fixed-donor paper anchor points to a path absent from this branch.** Line 212 cites `analysis/fixed_donor_decomposition_results.json`; on the reviewed branch the identical snapshot lives at `paper-causal/_fixed_donor_results.readonly.json`, while the analysis path exists only in `main@4aafd06`. The evidence is recoverable, but a reader checking the manuscript’s own tree encounters a missing path.

5. **minor — PLAUSIBLE — Environment setup is discoverable but not paper-facing.** `pyproject.toml` and `uv.lock` pin the optional analysis dependencies. In the current referee environment, the selected tests fail during collection because `pyreadstat` is not installed. That is not a code-test failure, but it demonstrates that the manuscript gives no executable setup command.

## Reproduction evidence checked

- The three branch analysis artifacts and fixed-donor snapshot match the requested `main@4aafd06` objects byte for byte.
- Tests exist for artifact schemas, quoted values, verdict logic, deterministic serialization, planted effects, and optional raw regeneration. Fixed-donor tests at `main@4aafd06` also lock both protocol hashes and the reproduction check.
- The requested test subset could not collect in the ambient Python 3.14 environment because `pyreadstat` was absent; no test result is represented here as a substantive failure.
