# Quasi-experimental designs for causal effects of the policy levers

Status: design memo, 2026-08-12. Nothing here is estimated yet; every
data claim below is either verified in this repository's artifacts or
marked as requiring verification before use. The paper's standing
caveat — "adoption contrasts are descriptive contrasts of policy
bundles; nothing here identifies causal effects" — is the gap this memo
proposes to close.

## What we uniquely bring

Three assets most SNAP quasi-experiments lack:

1. **Case-level outcomes with consistent definitions.** Published error
   rates are non-comparable across years (the QC tolerance threshold
   moved $48→$54→$56→$57→$58 across FY2022–26 alone, and the series has
   older breaks). We hold the case files and the parameter machinery,
   so outcomes can be recomputed under a fixed real threshold — the
   published series' breaks become a robustness check instead of a
   confound.
2. **Cause- and element-coded dollars.** Every error case carries up to
   nine cause codes and finding elements. A lever should move *its own*
   element class (SMD → medical-deduction variances; BBCE → resource
   variances), and the untargeted classes are built-in placebos. That
   converts weak state-year power into a sharper triple difference:
   state × time × element class.
3. **A deployed, committed simulator.** Predictions can be committed
   with hashes *before* outcome years publish — fixing, prospectively,
   the pre-registration gap the paper discloses for fiscal 2025
   (FACTS J9).

## Ranked designs

### 1. Eligibility-system migration event studies (validates the adoption bound)

**Question:** what does the computing apparatus causally contribute to
measured error — the quantity the adoption panel brackets by accounting
convention (strict 3.5% / broad 19.3% of error dollars nationally)?

**Design:** staggered event study around state eligibility-system
replacements (go-live dates from public procurement and press records —
candidate events widely reported and to be date-verified include Rhode
Island's UHIP, Kentucky's Benefind, and North Carolina's NC FAST).
Outcome: computing-apparatus cause-coded error dollars per case-month
(the strict class {17, 19, 20}), with client-caused classes as
placebos, under a fixed real threshold. Modern staggered-adoption
estimators (Callaway–Sant'Anna / Sun–Abraham), never plain two-way
fixed effects.

**Why it matters here:** it is the direct empirical check on the
adoption panel — an accounting bound and a quasi-experimental estimate
of the same object, published side by side. Transition spikes versus
steady-state levels separate migration cost from apparatus quality.

**Threats:** migrations bundle process redesign and staffing change
(bundling is the estimand: "system replacement as implemented");
anticipation and phase-in (event-time profile handles this);
sparse events (each event is also a case study).

### 2. Option-adoption staggered difference-in-differences with element-targeted outcomes

**Question:** the causal effect of the levers the simulator once
carried as accounting toggles — SMD, BBCE, heat-and-eat, SSED — on
measured error.

**Design:** adoption dates from successive State Options Report
editions (the FY2024 registry is already ingested with the 16th
edition; earlier editions supply timing). Outcome: targeted-element
error dollars under a fixed real threshold; placebo: untargeted
elements; estimator as above. The SMD model association (+0.006 AUC,
sign-unstable) and the accounting bound both exist for the same lever —
a third, design-based estimate would adjudicate the sign disagreement
the paper reports.

**Threats:** adoption is endogenous to error history (event-study
pre-trends are the test); option bundles adopted together
(regressor sets from the registry); few switchers for some options
(report which levers are identified, not all of them).

### 3. The OBBBA regime itself, pre-registered (prospective)

**Registered 2026-08-12**: see `PREREGISTRATION_OBBBA_BOUNDARY.md` and
the hash-pinned `preregistration_obbba_boundary.json` (windows,
estimators, per-state null predictions, outcomes, falsifications).

**Question:** does cost-sharing exposure causally change measurement
and program behavior — sampling plans, review practice, measured
rates?

**Design:** the statute created discontinuous incentives at the tier
boundaries (6/8/10) and the delay threshold (13.33%) in the locked
fiscal 2025 rate. States just above versus just below a boundary face
sharply different marginal returns to error reduction (and New York's
delay-lottery position is a one-state discontinuity of its own).
Outcomes over fiscal 2026–27: measured rates, precision-waiver and
sampling-plan elections, cause-mix shifts. Commit the design, the
running-variable windows, and simulator-based predictions now — before
the June 2027 publication — with hashes.

**Threats:** few states per window (this is a small-N discontinuity —
report it as such); manipulation of the running variable is itself a
finding (the rate is measured with the noise we quantify, which limits
precise sorting in the first binding year).

### 4. Bunching at the QC tolerance threshold

**Question:** strategic measurement — do adjudicated error amounts
bunch just below the tolerance threshold, and does the bunch track the
threshold as it moves ($54→$56→$57→$58)?

**Design:** bunching estimator on the distribution of recorded error
amounts around the moving threshold, pooled across years with the
threshold as the running variable. A moving bunch is hard to explain
without discretion responding to the cutoff. This tests the
measurement system, not a policy lever, but it sharpens the paper's
documented-manipulation-history thread with a design rather than an
anecdote.

## Sequencing

Design 1 first (validates the adoption bound; events are public and
few), design 3's pre-registration immediately (it is time-sensitive —
value decays as fiscal 2026 closes September 30), designs 2 and 4 as
the historical-file ingestion lands. First concrete step for 1 and 2:
ingest prior-year QC public files and earlier State Options Report
editions, with the same hash-registry discipline as
`params/sources/official_hashes.json`; verify how far back cause and
element coding is consistent before committing to a panel start year.

## Coding-consistency audit results (2026-08-14)

The extended audit (`analysis/coding_consistency.json`, FY2012–24) provides
evidence and a recommendation, not a design decision:

- **RI and KY gain five pre-period years.** All nine AGENCY slots and each
  strict computing-apparatus cause code {17, 19, 20} are observed in every
  FY2012–24 file. The inventory therefore supports strict-class sensitivity
  panels spanning the Kentucky (2016-02-29) and Rhode Island (2016-09)
  go-lives. Numeric presence does not establish unchanged semantics, and the
  FY2024 techdoc reports minor AGENCY revisions, so those facts bound causal
  interpretation. The broad class remains unsuitable as the primary historical
  outcome because code 22 first appears in FY2023.
- **Total-rate sensitivity panels can start in FY2012** under a fixed real
  AMTERR threshold. CASE, HWGT, RAWBEN, AMTERR, STATUS, and all nine cause and
  finding slots are present throughout; HWGT implies plausible national-scale
  monthly caseloads. Local techdocs verify the complete nominal tolerance
  series: $50/$50/$37/$38/$38/$38 for FY2012–17, $37/$37 for FY2018–19,
  and $37/$39/$48/$54/$56 for FY2020–24 — no acquisition gaps remain.
  FY2020 is the reconciled two-period pandemic file,
  and FY2021 is pandemic-partial (9,832 rows), so the recommendation is strict
  plus total-rate FY2012–24 sensitivity outcomes with those bounds explicit.
- **Finding-targeted outcomes remain gated.** Pre-period NATURE and ELEMENT
  inventories vary across years, and FY2014 alone contains alphabetic E_FINDG
  code `A`; observed inventories match FY2024 exactly only in FY2024. A semantic
  bridge is still required before treating those targeted outcomes as stable.
  The independently acquired FY2017 CSV and existing SAV reconcile exactly on
  45,530 rows and all AGENCY/NATURE/E_FINDG/ELEMENT observed-code inventories.
