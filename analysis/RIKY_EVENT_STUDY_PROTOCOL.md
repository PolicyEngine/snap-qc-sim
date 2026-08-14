# Rhode Island and Kentucky event-study protocol

Status: frozen before estimation, 2026-08-14.

## Question and scope

This study estimates changes in SNAP QC outcomes around Kentucky's Benefind
go-live on February 29, 2016 and Rhode Island's UHIP go-live in September
2016. Each estimand is the state's bundled system replacement as implemented,
including contemporaneous process, staffing, and mitigation changes. It does
not isolate any specific software component.

The annual panel is FY2012--FY2024. Kentucky's launch leaves seven exposed
months in FY2016. Rhode Island's month-precision launch leaves at most one
exposed month in FY2016. The primary specification excludes FY2016 as a
transition year for both states, uses FY2012--FY2015 as pre-periods, and treats
FY2017 onward as post-periods. Kentucky's timing sensitivity treats FY2016 as
post; Rhode Island's timing sensitivity treats FY2016 as pre. This is a
small-N event study with two treated states, not a literature-grade ATT.

## Inputs, threshold, and annual outcomes

FY2012 and FY2013 use the audited SAS9 files. FY2014--FY2016 use the audited
CSVs. FY2017 uses the audited SAV, rather than the also-available CSV, because
that continues the existing FY2017--FY2024 loader path; the coding audit found
the FY2017 sources reconcile exactly. FY2018--FY2024 use the audited SAVs. All
files are verified against `analysis/coding_consistency.json` before use.

All outcomes use active cases (`CASE == 1`), positive `HWGT`, and adjudicated
error statuses (`STATUS in {2, 3}`). The inclusion floor is fixed at $68.31385 in
FY2024 dollars, the maximum real value of the audited FY2012--FY2024 official
nominal tolerances (FY2012's $50). Nominal floors equal $50 multiplied by each
year's annual-average CPI-U all-items index (`CUUR0000SA0`) divided by the
FY2012 index. The pre-named CPI-U values for FY2012--FY2024 are 229.594,
232.957, 236.736, 237.017, 240.007, 245.120, 251.107, 255.657, 258.811,
270.970, 292.655, 304.702, and 313.689. The resulting nominal floors are
approximately $50.00, $50.73, $51.56, $51.62, $52.27, $53.38, $54.69,
$55.68, $56.36, $59.01, $63.73, $66.36, and $68.31. The unrounded formula is
authoritative. This fixed-real, maximum-official-real convention prevents a
changing FNS nominal tolerance from defining the event-study outcome and does
not count errors below any year's audited official threshold ($50, $50, $37,
$38, $38, $38, $37, $37, $37, $39, $48, $54, and $56).

The three annual state outcomes follow the Oregon machinery:

1. `strict_computing_dollars_per_case_month`: `HWGT * AMTERR` for
   above-threshold cases with any `AGENCY1`--`AGENCY9` code in {17, 19, 20},
   divided by all active-case `HWGT`. The coding audit observes these strict
   computing-apparatus codes in every FY2012--FY2024 file. Whole case dollars
   are credited on any presence, matching the accounting convention; cause
   classes can overlap.
2. `total_error_rate`: `HWGT * AMTERR` for every above-threshold case divided
   by `HWGT * RAWBEN` over all active cases, multiplied by 100. This is a
   fixed-real-threshold reconstruction of the official-error-rate concept,
   not the published rate at each year's changing nominal tolerance.
3. `client_dollars_per_case_month` (placebo): the same dollar-per-case-month
   construction for any cause code mapped to `client_or_fact` in
   `analysis/cause_shares.json` (currently {1, 2, 3, 4, 7}). This is an
   analysis superclass derived from the file's coding, not a binary
   responsibility field.

## Pandemic and transition specifications

The primary specification drops FY2021 as pandemic-partial, retains FY2020,
and uses FY2022--FY2024 as later post-periods alongside FY2017--FY2020. The
first pandemic sensitivity includes FY2021 as post. The second drops both
FY2020 and FY2021. Each pandemic specification uses the primary transition
assignment. The two treatment-timing sensitivities use the primary pandemic
handling: Kentucky treats FY2016 as post, and Rhode Island treats FY2016 as
pre. Event time is fiscal year minus 2016, while paths retain the transition
and excluded pandemic years even when they do not enter an aggregate.

FNS billed Rhode Island $37.3 million for overpayments covering September 2016
through December 2019. The design therefore predicts that any Rhode Island
elevation should concentrate in FY2017--FY2019. A pre-named profile check
reports the mean gap in that consequence window, the mean gap in later
non-FY2021 post-years (FY2020 and FY2022--FY2024), and their difference. This
profile is descriptive and does not change the signal rule.

## Comparison and aggregation

For both treated units, the donor pool is states and DC with no dated or
candidate migration in `analysis/system_migrations.json`, excluding Rhode
Island, Kentucky, Oregon (treated in 2021), Georgia, and the registry's
unverified candidates Florida and New Mexico. All other registry states are
also excluded, including pre-panel candidates. Oregon and Georgia enter no
fit, estimate, or permutation. Territories are excluded because their program
and sampling context is not state-comparable.

For each treated state and specification, nonnegative donor weights summing to
one minimize pretreatment squared distance jointly across the three outcomes,
after each outcome is scaled by the donor-state pretreatment standard
deviation. Optimization is deterministic. The artifact reports treated and
synthetic-donor annual paths and their gap. The simple effect is the mean
post-period gap minus the mean pre-period gap. No plain TWFE model or causal
language broader than the bundled system replacement as implemented will be
used.

The pre-named pooled statistic for each outcome is the equal-weight arithmetic
mean of the Rhode Island and Kentucky effects. Equal state weights prevent
either state's QC sample size from silently determining the pooled result and
keep the pooled estimand transparent.

## Placebo-in-space inference

For each treated unit, every state in its donor pool is refit as pseudo-treated
using the remaining donors and the identical year assignment. For each
outcome, the absolute treated effect is ranked against absolute placebo
effects; ties count against the signal. The finite-sample p-value is
`(1 + count(|placebo| >= |treated|)) / (1 + number of placebos)`.

For pooled inference, each donor state supplies one pooled placebo: its two
pseudo-effects are estimated under the Rhode Island and Kentucky primary
procedures, each excluding that pseudo-treated state from its donor set, and
then equal-weight averaged exactly like the observed statistic. The pooled
absolute statistic is ranked against these pooled placebos with the same
plus-one rule. The artifact reports ranks, denominators, p-values, and all
placebo estimates. These are permutation-in-space comparisons conditional on
the selected donor pool, not large-sample standard errors.

## Reporting rule

There is no adoption gate. A unit-level `signal` is reported only if that
unit's primary strict-outcome permutation p-value is strictly below 0.10 and
its client-coded placebo p-value is at least 0.10. The pooled verdict applies
the identical rule to the pooled strict and pooled client statistics. The
total-rate outcome and Rhode Island consequence-window profile cannot change
a verdict. Otherwise the corresponding verdict is
`no_protocol_defined_signal`. `RETAIN/NULL` is acceptable: direction,
magnitude, inference, sensitivities, pre-fit diagnostics, exclusions, and
limitations will be reported flatly whichever way they land.

## Reproducibility

`analysis/event_study.py` will extend its shared loader and estimator rather
than fork them. It will write sorted, indented JSON without timestamps or
machine-specific absolute paths. Fast tests will lock the committed artifact's
schema and selected substantive values, verify same-process byte determinism,
and recover a planted fixture effect within tolerance. They will not impose a
cross-platform byte hash on optimizer output. Raw regeneration will skip when
the complete hash-audited cache is unavailable.
