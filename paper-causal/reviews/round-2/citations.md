# Citations referee report — resolving pass

## Bibliography attributions

1. **minor — CONFIRMED — `abadie2010synthetic` and `abadie2021using` support convex synthetic-control weighting and pretreatment matching, but not this implementation's full sentence.** Line 101's three-outcome objective and donor-preperiod-SD scaling are protocol-specific choices, not attributable to those papers. The general attribution is sound; the sentence should distinguish literature-backed method from frozen implementation. Primary sources checked: the 2010 JASA paper and the 2021 JEL article.

2. **minor — CONFIRMED — `crs2018errors` supports the tolerance as an exclusion floor in the official error rate, but not the FY2012–24 sequence.** The annual series needs FNS documentation. FNS now publishes the complete series, and the cached annual techdocs independently support it.

## Every remaining manuscript marker

1. **major — CONFIRMED — line 65, public-use files/fields, resolvable from the FY2024 techdoc.** Cite *FY 2024 SNAP QC Technical Documentation*: printed pp. 6 and 54–55 (PDF pp. 16 and 64–65) for active-case sampling/database scope; printed pp. 65–66 (PDF pp. 75–76) for `HWGT`; printed p. 64 (PDF p. 74) for `STATUS`; printed p. 77 (PDF p. 87) for `AMTERR`; printed pp. 88–90 (PDF pp. 98–100) for nine `AGENCY`, `ELEMENT`, and `NATURE` slots. Earlier annual PDFs can establish continuity, but this marker's variable definitions are directly resolvable.

2. **major — CONFIRMED — line 67, tolerance series, fully resolvable.** Exact cached-techdoc cites: FY2012 $50, FY2012 doc PDF p. 128; FY2013 $50, FY2013 doc PDF p. 126; FY2014 $37, FY2014 doc printed p. 5/PDF p. 10; FY2015 $38, FY2015 printed p. 5/PDF p. 10; FY2016 $38, FY2016 printed p. 5/PDF p. 10; FY2017 $38, FY2017 printed p. 5/PDF p. 10; FY2018 $37, FY2018 printed p. 6/PDF p. 14; FY2019 $37, FY2019 printed p. 4/PDF p. 10; FY2020 $37 and FY2021 $39, FY2021 printed p. 6/PDF p. 14; FY2022 $48, FY2022 printed p. 6/PDF p. 14; FY2023 $54, FY2023 printed p. 6/PDF p. 14; FY2024 $56, FY2024 printed p. 6/PDF p. 16. Note that `coding_consistency.json` says FY2024 “p. 5”; the located statement is printed p. 6/PDF p. 16, so the artifact's page note is off by one.

3. **major — CONFIRMED — line 71, FY2024 revisions, resolvable but the artifact's page note is wrong.** The sentence “minor changes … including AGENCY, ELEMENT, and NATURE codes” appears on printed p. 3/PDF p. 13 of `FY-2024-Tech-Doc.pdf`, not p. 8 as recorded in `coding_consistency.json:.cross_year_summary.fy2024_minor_revisions_evidence.techdoc_citation`.

4. **minor — CONFIRMED — lines 77 and 141, Kentucky FNS billing record.** Not resolvable from the techdocs or repository. `system_migrations.json` establishes only that this registry has no record. Genuine external research remains necessary if the author wants to assert whether a bill exists.

5. **minor — CONFIRMED — line 79, Oregon vendor.** Not resolvable from SNAP QC techdocs or committed artifacts; external procurement/agency sourcing is required.

6. **minor — CONFIRMED — line 79, Oregon launch problems.** Not resolvable from the techdocs or registry; external reporting/agency records are required.

7. **minor — CONFIRMED — line 79, Oregon FNS billing record.** Not resolvable internally; absence in the registry is not evidence of absence.

8. **major — CONFIRMED — line 81, Georgia vendor and statewide completion.** Genuinely external and design-relevant because registry completeness defines donor exclusion.

9. **major — CONFIRMED — line 81, New Mexico ASPEN details.** Genuinely external and design-relevant.

10. **major — CONFIRMED — line 81, Indiana go-live/primary record.** Genuinely external and design-relevant.

11. **major — CONFIRMED — line 81, Colorado go-live/vendor/problems/billing.** Genuinely external and design-relevant.

12. **major — CONFIRMED — line 204, element-code interpretation, resolvable.** Insert the FY2024 codebook cites and restore these exact labels: **331 “RSDI benefits”** and **333 “SSI and/or State SSI supplement”** on printed p. 89/PDF p. 99; **361 “Standard deduction,” 363 “Shelter deduction,” 364 “Standard utility allowance,” and 365 “Medical expense deductions”** on printed p. 90/PDF p. 100. These labels also appear in older techdocs (for example FY2015 PDF pp. 108–109), supporting the window comparison, but the manuscript should still preserve its semantic-stability caveat.

13. **minor — CONFIRMED — line 259, companion simulation paper.** Resolvable within the repository (`paper/index.qmd` and its artifact chain), but it needs a formal cross-document/bibliographic citation rather than a placeholder.

No additional `[NEEDS CITATION]` marker appears in the manuscript. The external source checks support the three bibliography attributions; exact PDF page findings above come from the local cached documents, not guessed pagination.
