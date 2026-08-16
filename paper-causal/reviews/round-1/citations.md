# Citation referee findings

## Bibliography attributions

1. **minor — CONFIRMED — `abadie2010synthetic` and `abadie2021using` support the general synthetic-control attribution, but not every implementation detail in the sentence.** Line 127’s convex donor weighting and pretreatment fit are standard and supportable by these works. The manuscript’s particular three-outcome joint objective and donor-SD scaling are protocol-specific and should be understood as such, not as claims sourced from those papers.

2. **minor — CONFIRMED — `crs2018errors` supports the tolerance as the floor used in the official rate, but not the full FY2012–24 series.** The CRS work explains the QC/error-tolerance threshold and historical statutory values through its publication period. The later $39/$48/$54/$56 values require the FNS technical documentation marker already present.

## Every manuscript `[NEEDS CITATION]` marker

1. **major — CONFIRMED — line 91, SNAP QC public-use files and variable definitions.** Partly resolvable from repository-adjacent technical documentation: FY2012–19 PDFs under `~/.cache/axiom-oracles/snap-qc/historical/` and FY2021–24 techdocs under `~/.cache/axiom-oracles/snap-qc/`. Those files are not committed artifacts, so the paper still needs stable public citations.
2. **major — CONFIRMED — line 93, annual tolerance series.** Resolvable from the same FNS technical documents plus the coding audit; stable external FNS citations remain necessary, especially for FY2020–24.
3. **major — CONFIRMED — line 97, FY2024 code revisions.** Resolvable from `~/.cache/axiom-oracles/snap-qc/FY-2024-Tech-Doc.pdf` and summarized in `coding_consistency.json`; the PDF needs a public citation.
4. **minor — CONFIRMED — lines 103 and 167, Kentucky FNS billing record “if any.”** Genuinely external/open research. Absence from `system_migrations.json` proves only that the registry holds no record, not that no bill exists.
5. **minor — CONFIRMED — lines 105 and 248, Oregon vendor.** Genuinely external; no supporting repository artifact is recorded.
6. **minor — CONFIRMED — line 105, Oregon documented launch problems.** Genuinely external; absence from the registry is not evidence of absence.
7. **minor — CONFIRMED — lines 105 and 248, Oregon FNS billing record “if any.”** Genuinely external/open research.
8. **major — CONFIRMED — line 107, Georgia vendor and statewide completion date.** Genuinely external and design-relevant because registry completeness defines donor exclusion.
9. **major — CONFIRMED — line 107, New Mexico ASPEN date/vendor/launch/problems/billing.** Genuinely external and design-relevant; the registry treats NM as a candidate and excludes it.
10. **major — CONFIRMED — line 107, Indiana exact go-live and primary public record.** Genuinely external and design-relevant.
11. **major — CONFIRMED — line 107, Colorado exact go-live/vendor/problems/billing.** Genuinely external and design-relevant.
12. **major — CONFIRMED — line 230, interpretation of RI element codes.** Potentially resolvable from the cached FNS technical documents, but the manuscript explicitly has not extracted labels. Until labels/semantics are checked, the numeric inventory supports codes only, not substantive interpretation.
13. **minor — CONFIRMED — line 252, companion simulation paper.** Resolvable inside the repository (`paper/index.qmd` and its artifacts), but the manuscript needs a bibliographic or cross-document citation.

The companion `GROUND_TRUTH.md` markers for fixed-donor results are resolved by the byte-identical snapshot/main artifact. Its “direct third-party quotation” marker is moot because the manuscript contains no cataloged direct quotation.
