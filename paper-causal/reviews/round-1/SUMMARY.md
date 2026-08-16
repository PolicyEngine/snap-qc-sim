# Referee round 1 summary

Recommendation: **block pending correction of three confirmed claim failures**. The tables and displayed numerical values are exceptionally well aligned with the committed artifacts, but prominent prose exceeds what those artifacts support.

## Blockers

1. **blocker — CONFIRMED:** “never-migrated states” is unsupported. The protocols establish only absence from an incomplete migration registry.
2. **blocker — CONFIRMED:** the abstract says worker/user and data-entry channels “do not separate from the donor,” although both are descriptive and receive no inference.
3. **blocker — CONFIRMED:** FY2017–19 are repeatedly called the fiscal years FNS billed, but the September 2016–December 2019 billing interval also touches FY2016 and FY2020.

## Major findings

- **major — CONFIRMED:** prominent prose collapses the joint-fit `no_protocol_defined_signal`/`signal_family_adjusted` result and fixed-donor `signal`/`signal_family_adjusted` result into the “same mass-change signal,” privileging fixed donor despite the stated neutrality between estimators.
- **major — CONFIRMED:** the abstract makes descriptive channels inferential; mechanism-like glosses elsewhere turn reviewer codes into claims about what the system and workers did.
- **major — CONFIRMED:** “one signal, one null, one refusal” does not preserve the frozen verdict taxonomy; Kentucky and Oregon both have `no_protocol_defined_signal`.
- **major — CONFIRMED:** reproducibility is incomplete for an outside reader. The manuscript lacks artifact-key/generator/test anchors, parent artifacts lack protocol/raw/environment provenance, and full regeneration relies on an external cache.
- **major — CONFIRMED:** unresolved citations include public-use field definitions, tolerance values, codebook revisions, registry facts that determine donor exclusions, and element-code semantics.
- **major — CONFIRMED:** the introduction previews nearly all results and later sections repeat them, against the voice bible.

## Minor findings

Neutrality is substantively sound: no advocacy, procurement advice, or confirmed state-shaming appears. Minor rhetoric (“troubled,” “refuses ... outright”), systematic passive constructions, inanimate carriers, process narration, em-dash chains, and symmetric triads violate `VOICE.md`.

## What passed

- No artifact-supported number was wrong at the stated precision.
- Donor weights, ranks, p-values, RMSPEs, sensitivities, case counts, internal shares, and overlap accounting all match.
- Joint fitting, scaling, post-minus-pre aggregation, permutation rules, plus-one convention, denominators, transition/pandemic handling, and Oregon exclusions are described accurately.
- Table 7 uses every formal verdict correctly and the fixed-donor reproduction check passes exactly.
- The branch artifacts/snapshot are byte-identical to the requested `main@4aafd06` objects.

See `methodology.md`, `red-team.md`, `reproducibility.md`, `citations.md`, `neutrality.md`, and `language.md` for evidence and classifications.
