# UHIP cause-channel decomposition protocol

Status: frozen before estimation, 2026-08-16. Extends
`RIKY_EVENT_STUDY_PROTOCOL.md`; every clause of that protocol not
overridden here applies unchanged (inputs, fixed-real threshold, donor
pool, weight fitting, permutation inference, pandemic and transition
specifications, event time). This file adds outcomes and a reporting
rule; it changes nothing about the estimator.

## Question

The Rhode Island UHIP event study estimated one bundled quantity —
strict computing-apparatus error dollars per weighted case-month, cause
codes {17, 19, 20} — and found a signal. This decomposition asks which
recorded cause channels carried it. The QC file's cause coding
(`AGENCY1`–`AGENCY9`) distinguishes failure hypotheses that the pooled
outcome conflates:

| Channel | Codes | Label (FY2024 codebook, `cause_shares.json`) | Failure hypothesis |
|---|---|---|---|
| defect | 17 | computer programming error | the system computed wrong |
| mass_change | 19 | computer-generated mass-change error | batch actions computed wrong |
| arithmetic | 20 | arithmetic computation error | manual/derived computation wrong |
| user | 21 | computer user error | workers could not drive the system |
| entry | 18 | data entry and/or coding error | conversion and keying |
| disregard | 12 | reported information disregarded or not applied | information reached the agency and died |
| recert | 23, 24, 25 | recertification procedure: notices, interviews, time frames | process machinery broke |

The estimand for every channel is unchanged: Rhode Island's bundled
system replacement as implemented. The decomposition attributes the
measured rise to recorded cause channels; it does not isolate software
from process, because the coder's classification is itself part of the
measurement (a reviewer's choice between 17, 21, and 12 for one UHIP
failure is a coding-practice question). Results describe how the QC
system classified UHIP's failures.

## Outcomes

Seven channel outcomes, each `HWGT * AMTERR` for above-threshold
adjudicated cases with any `AGENCY1`–`AGENCY9` code in the channel's
set, divided by all active-case `HWGT` — the exact construction of the
parent protocol's strict outcome with the code set swapped. Whole case
dollars credit on any presence; channels can overlap; the parent's
strict outcome equals the union of defect, mass_change, and arithmetic
only up to overlap, and the artifact reports the overlap.

The client-coded placebo outcome (`{1, 2, 3, 4, 7}`) is inherited
unchanged and estimated once.

## Power gate, fixed from observed pre-registration counts

Rhode Island's sampled adjudicated-error cases in the consequence
window FY2017–19 number 325, 206, and 482. Cause-code presence counts
in those years (recorded before this protocol froze; not outcomes):

| Code | FY2017 | FY2018 | FY2019 |
|---|---:|---:|---:|
| 17 | 44 | 12 | 21 |
| 19 | 139 | 93 | 98 |
| 20 | 7 | 3 | 14 |
| 21 | 1 | 4 | 8 |
| 18 | 5 | 13 | 18 |
| 12 | 84 | 51 | 137 |
| 23–25 | 0 | 0 | 0 |

The full-panel presence counts were also observed before freezing and
are recorded here so the reader can judge what the author knew (the
power gate depends only on the FY2017–19 rows; the pre-period rows are
disclosed, not used):

| FY | n active | n error | 17 | 19 | 20 | 21 | 18 | 12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2012 | 1014 | 402 | 0 | 2 | 1 | 1 | 3 | 93 |
| 2013 | 1016 | 380 | 2 | 6 | 1 | 0 | 1 | 114 |
| 2014 | 994 | 355 | 2 | 14 | 3 | 0 | 1 | 78 |
| 2015 | 986 | 309 | 1 | 6 | 11 | 2 | 4 | 23 |
| 2016 | 977 | 303 | 3 | 1 | 9 | 0 | 8 | 41 |
| 2017 | 681 | 325 | 44 | 139 | 7 | 1 | 5 | 84 |
| 2018 | 417 | 206 | 12 | 93 | 3 | 4 | 13 | 51 |
| 2019 | 946 | 482 | 21 | 98 | 14 | 8 | 18 | 137 |
| 2020 | 570 | 274 | 16 | 41 | 10 | 0 | 8 | 66 |
| 2021 | 230 | 104 | 4 | 7 | 1 | 1 | 4 | 21 |
| 2022 | 671 | 317 | 10 | 34 | 2 | 5 | 9 | 46 |
| 2023 | 984 | 470 | 10 | 75 | 10 | 6 | 22 | 110 |
| 2024 | 980 | 481 | 7 | 9 | 3 | 3 | 9 | 64 |

Codes 23–25 are zero in every Rhode Island year. These are raw presence
counts, not weighted outcomes, and they contain no comparison unit;
the estimation below is what turns them into evidence.

Rule: a channel is **inferential** if its Rhode Island post-window
presence count is at least 30 in every year FY2017–19 — mass_change
(19), disregard (12), and defect (17, at 44/12/21, fails FY2018 and is
therefore not inferential; see below). A channel is **descriptive** if
any year falls below 30: defect, arithmetic, user, entry, and recert
(zero presence — reported as an observed zero, no estimation). To keep
the defect channel testable, the protocol pre-names one **inferential
composite**: `defect_or_mass_change` (codes {17, 19}), the two
software-computed channels, which clears the gate every year (183, 105,
119). Inferential channels receive the parent's permutation inference
and enter the reporting rule; descriptive channels receive paths, gaps,
and effect sizes with no p-values and no verdicts.

Inferential set, fixed: `mass_change`, `disregard`,
`defect_or_mass_change`. Descriptive set, fixed: `defect`, `arithmetic`,
`user`, `entry`, `recert`.

## Reporting rule

For each inferential channel, `signal` requires the channel's primary
permutation p-value strictly below 0.10 with the client placebo
p-value at least 0.10 — the parent rule. Because three inferential
channels are tested, the artifact also reports a family-adjusted
verdict: `signal_family_adjusted` requires p strictly below 0.10/3.
Both verdicts are reported; neither is an adoption gate. Descriptive
channels carry no verdict field.

The pre-named profile check for each inferential channel repeats the
parent's consequence-window comparison: mean gap FY2017–19 versus mean
gap in later non-FY2021 post-years, and their difference. It is
descriptive and verdict-inert.

Nothing here changes the parent study's published verdicts.

## Rhode Island-internal descriptive layers

Two within-Rhode-Island descriptions with no comparison unit and no
inference — they characterize the post-window cases, not effects:

1. **Element mix.** For strict-coded (17/19/20) error cases, the
   distribution of finding elements (`ELEMENT` slots) in FY2017–19
   versus FY2012–15, restricted to element codes whose semantics the
   coding audit records as present in both windows; codes absent from
   either window are listed, not compared. This is within-state
   composition, exempt from the cross-panel element gate only because
   no cross-state comparison is made.
2. **Certification-vintage split.** Post-window strict-coded cases split
   by whether the recorded certification (from `CERTMTH`/`LASTCERT`
   semantics as the loader documents them; the estimation lane must
   read and cite the field definitions before use) predates or
   postdates the September 2016 go-live. Converted cases versus cases
   certified in UHIP. Counts and dollar shares only.

## Artifacts

`analysis/uhip_decomposition.py` (extends `event_study.py`; no fork),
`analysis/uhip_decomposition_results.json` (per-channel paths, gaps,
effects, ranks, p-values where inferential, both verdicts, profile
checks, overlap accounting, element mix, vintage split, donor weights,
environment and input hashes), tests (fast committed-artifact locks:
schema, inferential/descriptive set membership fixed as above, verdict
consistency with p-values, overlap identity; same-process determinism
+ planted-effect tolerance on a fixture; no cross-platform byte hashes
on optimizer output; raw regeneration value-locked and skipif-gated).

## Language

Bundled system replacement as implemented. Channels attribute the
measured rise to recorded cause classes under QC coding practice. No
channel result is "the effect of software" or "the effect of a rules
engine."
