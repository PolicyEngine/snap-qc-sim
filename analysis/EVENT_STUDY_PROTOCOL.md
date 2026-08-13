# System-migration event study protocol

Status: frozen before estimation, 2026-08-13.

## Question and scope

This first run estimates the change in Oregon's SNAP QC outcomes around the
February 2021 expansion of ONE Eligibility to SNAP and other programs. The
estimand is Oregon's bundled system replacement as implemented, including
contemporaneous process and staffing changes. It is not the effect of a rules
engine or of rules engines generally.

The annual panel is FY2017--FY2024. Oregon is the sole primary treated unit.
Georgia Gateway is a sensitivity case only: its February 6, 2017 date is a
county pilot and the registry flags the 2017 statewide completion date
`NEEDS_VERIFICATION`. Rhode Island and Kentucky are excluded because their
2016 launches leave no in-panel pretreatment fiscal year. North Carolina,
Indiana, and Colorado are pre-panel events. Florida and New Mexico are
unverified registry candidates and cannot be donors. This is a small-N event
study with one primary treated state, not a literature-grade ATT.

## Outcomes and annual construction

All outcomes use active cases (`CASE == 1`), positive `HWGT`, adjudicated error
statuses (`STATUS in {2, 3}`), and a researcher-chosen fixed-real threshold of
$56 in FY2024 dollars. Nominal thresholds are $56 multiplied by the annual
CPI-U all-items index (`CUUR0000SA0`) divided by its 2024 index. The pre-named
annual averages are 245.120, 251.107, 255.657, 258.811, 270.970, 292.655,
304.702, and 313.689 for 2017--2024. This avoids reliance on the unavailable
FY2017--FY2019 official nominal tolerances identified by the coding audit.

The three annual state outcomes are:

1. `strict_computing_dollars_per_case_month`: `HWGT * AMTERR` for
   above-threshold cases with any `AGENCY1`--`AGENCY9` code in {17, 19, 20},
   divided by all active-case `HWGT`. This is the file's strict
   computing-apparatus cause coding. Whole case dollars are credited on any
   presence, matching the accounting convention; cause classes can overlap.
2. `total_error_rate`: `HWGT * AMTERR` for every above-threshold case divided
   by `HWGT * RAWBEN` over all active cases, multiplied by 100. This is a
   fixed-real-threshold reconstruction of the total official-error-rate
   concept, not the published rate at each year's changing nominal tolerance.
3. `client_dollars_per_case_month` (placebo): the same dollar-per-case-month
   construction for any cause code mapped to `client_or_fact` in
   `analysis/cause_shares.json` (currently {1, 2, 3, 4, 7}). It is an analysis
   superclass derived from the file's coding, not a binary responsibility
   field.

FY2020 uses the audit's reconciling combined file. FY2021 is both
pandemic-partial and partially exposed: Oregon's February launch places four
fiscal months before and eight after launch. The primary specification drops
FY2021, assigns FY2017--FY2020 as pre and FY2022--FY2024 as post, and reports
event time as fiscal year minus 2021. Sensitivity A includes FY2021 as treated
(intent-to-treat with partial exposure). Sensitivity B drops both FY2020 and
FY2021, leaving FY2017--FY2019 pre and FY2022--FY2024 post.

## Comparison and aggregation

The base donor pool is states and DC with no dated or candidate migration in
`analysis/system_migrations.json`: all registry states are excluded, including
FL and NM. Territories are excluded because their program and sampling context
is not state-comparable. States on either FY2024 or FY2025 statutory
delay-roster artifact are also excluded before estimation: AK, DC, DE, FL, GA,
IL, MA, MD, NJ, NM, NY, and OR. This removes a pre-named set with unusually
high recent measured rates and associated administrative exposure; Oregon is
retained only as the treated unit. Because this exclusion is defined partly by
post-treatment measured rates, results will be described as conditional on the
pre-named pool rather than as representative of all states.

For each treated state/specification, nonnegative donor weights summing to one
minimize pretreatment squared distance jointly across the three outcomes after
each outcome is scaled by the donor-state pretreatment standard deviation.
Optimization is deterministic. We report the treated and synthetic-donor
annual paths and their difference. The simple difference-in-differences
aggregation is the post-period mean gap minus the pre-period mean gap. With one
treated cohort, this is the honest simple aggregation to report; no plain TWFE
model or language will be used.

Georgia's sensitivity uses FY2017 as the partial-exposure treated year and has
no clean in-panel pretreatment year. It therefore reports only a descriptive
path relative to the Oregon-primary donor weights and no DiD or inference. It
cannot support an independently fitted event-study estimate until the
statewide completion date or earlier files are obtained.

## Placebo-in-space inference

For every state in the Oregon donor pool, refit the identical synthetic
comparison treating that state as if treated in FY2021 and using the remaining
donors. For each outcome, rank the absolute Oregon DiD against absolute placebo
DiDs. Ties count against the signal. The finite-sample randomization p-value is
`(1 + count(|placebo| >= |Oregon|)) / (1 + number of placebos)`. The artifact
reports the rank, denominator, p-value, and all placebo estimates. This is
placebo-in-space inference conditional on the selected states, not a
large-sample standard error.

## Reporting rule

There is no adoption gate. A `signal` is reported only if the primary strict
outcome has permutation p < 0.10 and the client-coded placebo outcome has
permutation p >= 0.10. Otherwise the verdict is `no_protocol_defined_signal`.
The total-rate outcome is secondary and cannot change this verdict. Direction,
magnitude, all inference, sensitivities, pre-fit diagnostics, exclusions, and
limitations are reported flatly whichever way they land.

## Reproducibility

`analysis/event_study.py` reads the eight cached public SAV files, verifies
their hashes against `analysis/coding_consistency.json`, and writes sorted,
indented JSON with no timestamp or machine-specific absolute path. A fast test
tier uses a committed synthetic fixture; raw-SAV regeneration tests skip when
the audited cache is unavailable. Two consecutive runs must be byte-identical.
