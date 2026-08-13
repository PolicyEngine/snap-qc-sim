# Pre-registration: the OBBBA boundary quasi-experiment

Status: registered design — drafted 2026-08-12, adversarial
verification rounds 2026-08-12/13, effective at the merge of pull
request #49. This document and its
machine-readable companion commit the design, the running-variable
windows, the estimators and their decision rules, per-state no-response
null predictions, the outcome list, and the falsification battery for
design 3 of `QUASI_EXPERIMENTS.md` — before fiscal 2026 closes
(September 30, 2026) and well before its rates publish (~mid-2027 by
precedent). **The registration event is the merge of the registering
pull request (#49) to `main`** — that merge, with its hosted public
timestamp, is when this design takes effect; the pull-request branch
preserves, in public history, the drafting and adversarial-verification
rounds that preceded it (including rounds that corrected four
numerically degenerate SD fields and added the drift-world power
tables, each re-pinning the hashes). After the registration event,
nothing in this document may be edited except through a dated, appended
"Amendments" section that leaves the original text intact; the artifact
hash pins below make silent revision detectable, and the hash-lock test
permits historical pins only inside that section.

- Machine-readable predictions artifact:
  `analysis/preregistration_obbba_boundary.json`
- Artifact file SHA-256:
  `cb3d10fb1640b25c7921ee62d4d781af7c6d3d541ad070dd99ac26ac936cde31`
- Payload self-pin (SHA-256 of the canonical payload serialization,
  recorded inside the file):
  `dd212c78b43f2c6ce00c261a8c7aad986627b65bbadb84ae5835262f9417fad2`
- Generator (deterministic; regeneration is byte-identical and
  test-locked): `analysis/preregister_obbba_boundary.py`;
  locks in `tests/test_preregistration.py`
- Registration record: the public commit history of
  `PolicyEngine/snap-qc-sim` (public repository; first commit 076e509,
  2026-08-05), base commit c205e53, pull request #49. GitHub's hosted
  timestamps on that pull request and its merge are the tamper-evident
  record.

## Why this registration exists

The manuscript discloses (FACTS J9) that the fiscal 2025 analysis was
not pre-registered: the repository's first commit postdates the June 24,
2026 publication of the fiscal 2025 rates, so that exercise is a check
of input independence, not a registered forecast. This document is the
prospective fix for fiscal 2026. Fiscal 2026 is the first measurement
year the statute exposes end to end — it opened October 1, 2025, after
enactment, and closes September 30, 2026 — and its rates are unpublished
as of registration. To be precise about what "prospective" means here:
the year is ten and a half months underway, its case reviews are
accruing inside agencies, and its sampling plans were necessarily set
before it began; what does not yet exist is any official fiscal 2026
outcome, and none is observable to us. Every prediction below is
computable from artifacts committed before official fiscal 2026
outcomes are published or observable, and the value of this document
decays to zero the day they publish. That is the point: after
publication, only designs committed before it can claim to have
predicted rather than fit.

## The design in one paragraph

Public Law 119-21 (enacted July 4, 2025; enactment date per the GPO
record for PLAW-119publ21, govinfo.gov) prices each state's SNAP benefit
cost share by its payment error rate: 0% below 6%, 5% from 6 to below 8,
10% from 8 to below 10, and 15% at or above 10 (FACTS A1). The fiscal
2028 share keys to the state's fiscal 2025 or 2026 rate at the state's
election; fiscal 2029 keys to fiscal 2026 (FACTS A2). A separate,
mechanical, election-independent delay test — published rate × 1.5 ≥ 20,
i.e. above 13.33% — pushes a state's first billed year to fiscal 2029
(fiscal 2025 crossing) or fiscal 2030 (fiscal 2026 crossing) (FACTS A3,
H4). The fiscal 2025 rates published June 24, 2026 and are locked
history (FACTS J1). States just above a tier cut therefore face sharply
different marginal returns to their fiscal 2026 measured rate than
states just below it, and states near the delay threshold face a
discontinuity of the opposite sign: crossing it zeroes near-term bills.
This registration commits, per state, the distribution its fiscal 2026
measured rate should follow if nothing responds — same error process as
the fiscal 2024 case file, centered at the locked fiscal 2025 rate,
sampling noise only — and the tests that will compare realized rates to
that null.

## Verified statutory mechanics this design rests on

Every mechanism claim here is grounded in a committed artifact; the
sources are the fact catalog (`paper/FACTS.md`), the deployed engine
(`app/public/app.js`), and the manuscript (`paper/index.qmd`).

| Mechanic | Source |
|---|---|
| Tier schedule 0/5/10/15% at cuts 6/8/10, at-or-above on the upper side | FACTS A1; app.js `TIERS`, `tierOf` |
| FY2028 keys to elected FY2025-or-FY2026; FY2029 to FY2026 (third preceding year) | FACTS A2; app.js `electionStats` |
| Delay test rate × 1.5 ≥ 20, mechanical and election-independent; FY2025 cross → FY2029 start, FY2026 cross → FY2030 | FACTS A3, H4; app.js `DELAY_THRESHOLD` |
| FY2025 rates published 2026-06-24 by FNA; national 10.62 | FACTS J1 |
| FY2025 delay roster: AK DC DE GA IL NM OR; NY at 13.18 misses (19.77 < 20) | FACTS J5 |
| QC sample-size formulas; reduced vs standard schedules; all 53 elected reduced in FY2024 | FACTS A4, A5 |
| Electing the reduced schedule contractually waives precision disputes; OBBBA §10106 cut the federal admin match 50%→25% from FY2027, repricing reviews | paper §sec-qc ("Precision was contractually waived"); FACTS H5 |
| Expected cost share falls with added sample volume just below a boundary and rises just above | paper §sec-simulate; FACTS F3 |
| QC tolerance threshold $48/$54/$56/$57/$58 for FY2022–26 | FACTS J6, A6 |
| Two-year movement distinguishable from noise only beyond \|z\| > 2.77 single-year SDs | FACTS J2 |

## The running variable and why it is credible

The running variable is the published two-decimal fiscal 2025 rate. It
was measured over October 2024–September 2025 — roughly nine of its
twelve sample months predate enactment — and published June 24, 2026,
long after the year closed. Per-state sampling standard deviations run
0.33 to 1.28 percentage points (median 0.76; committed per state in the
artifact), so precise sorting of the running variable around a specific
cut was infeasible even for the exposed final quarter. Manipulation of
the *outcome* — the fiscal 2026 measurement — is not a threat to this
design; it is the treatment response itself. The design memo makes the
companion point about the running variable: at this noise, sorting the
fiscal 2025 rate was infeasible, and "manipulation of the running
variable is itself a finding."

## The no-response null

The null is the deployed simulator's observed-resample engine, exactly
as committed and CI-mirrored (`app/public/app.js` `simulate()`;
bit-faithful Python mirror in `analysis/adoption_mirror.py`, exercised
by `tests/test_adoption_numbers.py`): for
each of the 53 jurisdictions, resample the fiscal 2024 QC case file
(m = n draws with replacement), center the resampled weighted rate on
the locked fiscal 2025 official rate, seed 11, 4,000 replications. This
keeps the fiscal 2024 case composition and its sampling-error
distribution, re-anchors the level to the locked fiscal 2025 rate, adds
sampling noise only, and assumes no response of any kind — no behavioral
improvement, no measurement or adjudication change, no sampling-plan
change.

Committed variants, all in the artifact:

- **baseline** — m = n, the primary null.
- **extra_sample_300 / extra_sample_500** — m = n + 300 / n + 500, the
  precision counterfactuals behind the sampling-plan outcome (each
  restarts the seed-11 stream, matching the app).
- **drift_robust_median_mad / drift_classical_method_of_moments** —
  baseline plus independent-across-states N(0, τ²) process drift, τ =
  1.074 / 1.6207 pp read from `analysis/fy2025_movement.json` (FACTS
  J4). These widen the null for sensitivity re-runs; the primary stays
  sampling-only, a disclosed lower bound on year-over-year dispersion.
  Streams are per-state (Mulberry32 seed 1107 + k in sorted state-code
  order, Box–Muller as in the app), deliberately departing from the app
  toggle's shared-stream display convention because the drift artifact's
  own decomposition treats residual state changes as independent.

Per state and variant the artifact commits: mean, SD, fifteen quantiles,
crossing probabilities for the 6/8/10 cuts and the delay test, tier
probabilities, the probability the fiscal 2026 draw beats the locked
fiscal 2025 rate (p_win), the full election block (expected FY2028 lock
and elected bills, their SD, expected FY2029 bill), and — because
rounded probabilities are summaries, not commitments — the exact integer
draw counts out of 4,000 for every crossing and tier event.

**Disclosed basis caveat (threshold).** The resample basis is the fiscal
2024 file under its $56 error threshold; fiscal 2026 will be measured
under $58 (FACTS J6). No committed artifact quantifies the measured-rate
sensitivity to that move. Its mechanical direction is downward (errors
of $57–58 stop counting). To the extent the shift is common across
states — unquantified, hence conditional — the design absorbs it three
ways: the primary statistic contrasts above versus below groups (a
common shift largely cancels), the rank-sum secondary is exactly
invariant to any common shift, and the delay test's alternative is
upward (a common downward shift is conservative). The residual,
state-varying part of the threshold effect is a disclosed limitation,
not a modeled term.

## Windows and rosters

Committed windows (rosters serialized in the artifact; sides split by
the published fiscal 2025 rate, equality on the upper side):

**Probability windows (primary):** state s enters window W_c for cut
c ∈ {6, 8, 10} iff its committed null crossing probability
P(draw < c) lies in [0.10, 0.90]. A state qualifying at multiple cuts is
assigned to the nearest by |fy2025 − c| (tie → lower cut; the only such
state is CT, assigned to 10). The delay window uses the same rule on
P(draw × 1.5 ≥ 20).

| Window | Above (fy2025 ≥ cut) | Below |
|---|---|---|
| 6% cut | NV 6.22, OH 6.76, WV 6.69 | IA 5.34, NE 5.90, VI 5.36, VT 5.38, WI 5.72 |
| 8% cut | LA 8.14, MO 8.67, MT 8.86, NH 8.85 | NC 7.36 |
| 10% cut | AZ 10.80, CA 10.93, CO 10.09, ME 10.81, OK 11.04 | AL 9.52, CT 9.08, IN 9.77, KS 9.44, MI 9.89, MS 9.51, ND 9.89, PA 9.21, TN 9.44, TX 9.34 |
| Delay (13.33) | OR 14.14 | FL 12.97, GU 11.70, MA 12.49, MD 13.08, MN 12.58, NY 13.18, RI 12.42, VA 12.32 |

Pooled tier-window sample: 12 above, 16 below (28 states). Honesty
notes, committed now: the 8% window is lopsided (one below-state, NC),
so the pooled contrast leans on the 6% and 10% windows; two territories
(VI, GU) appear in windows and the falsification battery includes
dropping them.

**Fixed-width sensitivity windows:** |fy2025 − c| ≤ 0.75 and ≤ 1.25 pp
for all four boundaries, rosters serialized in the artifact.

## Committed predictions: what the null says will happen

Everything below is in the artifact at full roster coverage; exemplars
here for the registered record (baseline variant, exact counts out of
4,000 draws):

- **Colorado (10.09, just above the 10 cut):** P(fiscal 2026 draw below
  the locked fiscal 2025 rate) = 0.525 (2,100/4,000 — the committed
  election lens of FACTS J8); P(below 10) = 0.484; expected FY2028
  elected bill $158,939,211; under +500 reviews the expected bill
  *rises* to $160,429,068 — precision hurts a just-above state.
- **New York (13.18, 0.15 below the delay threshold):** 1,669 of 4,000
  draws cross the delay test (p = 0.4173; 0.4487 under robust drift).
  Crossing zeroes FY2028 and FY2029 bills (deferral, not forgiveness).
  Precision works against the lottery: under +500 reviews crossing odds
  fall to 0.4128 and the expected FY2028 bill rises from $629,878,694 to
  $634,742,622.
- **Oregon (14.14, above the threshold; FY2025-delayed):** crossing odds
  0.7525 baseline, 0.8073 under +500 reviews — a delayed state's
  precision *raises* its odds of deferring again.
- **National:** summed expected FY2028 elected bills across all 53:
  $7,671,249,968 baseline (reproducing FACTS M2's $7.671B), rising to
  $7,787,458,205 (+300 reviews) and $7,862,176,494 (+500) — with most
  states above a cut (16 in the 10% tier, 21 in the 15% tier at fiscal
  2025 rates), added precision raises expected national bills.

Cross-locks: the committed values reproduce the fact catalog's committed
goldens (J8, M2, M3) exactly, and `tests/test_preregistration.py`
enforces this in CI, along with byte-identical regeneration and the
payload self-pin.

## Realized-outcome conventions (fixed now)

- r26(s) is the total payment error rate printed for jurisdiction s in
  the first official FNA fiscal 2026 PER publication, read from the
  total column at its published two-decimal precision, never recomputed
  from components. Any later agency revision: report both, primary on
  the first publication.
- Tier and delay evaluations of r26 use the statutory conventions above
  (at-or-above upper tier; delay iff r26 × 1.5 ≥ 20 on the published
  two-decimal value).
- PIT u_s = (#{null draws < r26} + 0.5 · #{null draws = r26}) / 4,000,
  against the regenerated full-precision baseline draws (regeneration is
  byte-locked, so "regenerated" and "registered" are the same numbers).
  The scale mismatch — a two-decimal published rate ranked against
  full-precision draws — is fixed here as the convention; with per-state
  SDs of 0.33–1.28 pp, the rounding of r26 moves u_s by well under one
  percent of its range, and the Monte Carlo reference distribution is an
  approximation, not an enumeration.
- A jurisdiction missing from the publication is excluded from every
  statistic and reported as missing. This rule is executable: the
  registered callables accept `missing_ok`, drop the missing state from
  its registered roster, rebuild the Monte Carlo reference for the
  reduced roster under the registered seed, and require both sides of a
  window to stay non-empty (test-locked).
- The analysis runs and publishes (repository + manuscript revision)
  within one month of the fiscal 2026 PER publication.

## Estimators and decision rules

**Primary test (confirmatory).** T = mean(u_s | above) − mean(u_s |
below), pooled across the three tier probability windows (assigned
partition). H1, one-sided: T < 0 — above-cut states push their measured
fiscal 2026 rates down, relative to their own no-response nulls, more
than below-cut states. α = 0.05. Null distribution: 20,000 Monte Carlo
replications (seed 20260930), each window state drawing u independently
from the discrete uniform {(k + 0.5)/4,000}; p = fraction of null T ≤
realized T. Against the committed independent-null DGP the test is exact
at any window size up to three approximations, stated now: the finite
20,000-draw reference, the inclusive-tail no-+1 p-value convention, and
the two-decimal rounding of published outcomes ranked against continuous
draws (all pinned in the artifact). With 12 above and 16 below it is a
small-N design and is reported as such. Pooling across the three cuts
assumes a common response *sign*, not a common magnitude. Implementation
is committed and executable now: `primary_test()` in the generator,
smoke-locked in CI.

This is a Fisherian test against a committed structural null, in the
spirit of local-randomization RD inference (Cattaneo, Frandsen and
Titiunik 2015): H0 is not "no discontinuity in a conditional mean" but
"no response — fiscal 2026 measurement behaves exactly as the committed
resample of fiscal 2024 says." Rejection is therefore evidence against
that committed null. Attributing it to boundary *response* — of either
kind: real error reduction, or measurement-side change in review
practice, adjudication, and dispute behavior — runs through the
registered falsifications and sensitivities, because null
misspecification (side-correlated drift, regression to the mean,
methodology change) can also reject. The auxiliary outcomes below are
the discriminators, and the interpretation rules are committed before
the data exist.

**Regression to the mean, named and handled.** The leading no-response
alternative is persistence-plus-noise: true state rates persist, both
years' published rates carry measurement noise, and the published fiscal
2025 value — which defines window membership and side and centers the
null — regresses toward each state's true rate on remeasurement. Three
committed answers. First, the first-order effect follows the local
density of true rates (Tweedie's formula: the bias tracks the density
slope), which is continuous across a cut — so it enters both sides of a
window nearly equally and largely differences out of T; the residual
exposure is local curvature. Second, the executable sensitivity:
`rtm_shrunken_sensitivity_test()` re-runs the primary with every null
re-centered at its global-Gaussian empirical-Bayes shrunken value
(shrinkage weights from committed quantities alone; λ ranges 0.90–0.99
across states, and window-state centers move by hundredths of a point —
Colorado's by −0.014 pp — the committed evidence that published-rate
shrinkage is small at these signal-to-noise ratios). Third, the
falsifications already probe it empirically: RTM from smooth-density
curvature would also appear at the 7/9 placebo cuts, and the pre-period
placebo — the same design run on fiscal 2024 windows against realized
fiscal 2025 — shows T = +0.073 (p = 0.763), the *opposite* sign of an
RTM signature at these windows.

**Delay-window test (committed secondary).** U = mean(u_s) over the
nine delay-window states; H1, one-sided: U > 1/2; α = 0.05; same MC
machinery, seed 20260931. Deferral is valuable on both sides of the
threshold — a below-threshold state that crosses zeroes FY2028 and
FY2029; an already-delayed state that crosses again pushes its start to
FY2030 — so the committed alternative is upward drift for the whole
window. U is a pooled deviation test against the null, not a
boundary-discontinuity contrast: Oregon's margin is FY2030 deferral
while the below-threshold eight can defer FY2028 and FY2029, and a
common upward process shock also rejects — a delay rejection is
therefore read jointly with the tail-share drift check and the
drift-widened sensitivity. Reported: the frozen roster with each
state's locked rate,
committed crossing odds, realized rate, crossing indicator, and u_s;
then U, U − 1/2, and the MC p-value. New York is additionally a named
descriptive singleton: its committed crossing odds are 0.4173
(1,669/4,000); we will report whether it crossed and its u_NY, with no
singleton p-value.

**Secondary estimators (labeled, non-confirmatory).**

1. z-version of the primary: z_s = (r26 − fy2025)/sd_s, with sd_s frozen
   at the artifact's committed baseline `sampling_sd`; statistic Z =
   mean(z | above) − mean(z | below), one-sided Z < 0. Reference
   distribution: 20,000 replications drawing each window state's rate
   from its own committed null draws (seed 20260933) — z is not
   rank-based, so its null is simulated from the committed state nulls
   rather than discrete-uniform.
2. Design-based stratified rank-sum: within each assigned cut stratum,
   midrank the raw movements Δ_s = r26 − fy2025 and center the above-cut
   rank sum; sum the centered statistics across the 6/8/10 strata;
   one-sided alternative that above-cut movements are smaller. Reference
   distribution by permuting side labels within each stratum, holding
   each stratum's observed above/below counts fixed (all assignments
   enumerated when feasible, else 20,000 draws, seed 20260934). Trusts
   no simulator scale; exactly invariant to common level shifts
   (including the threshold-move mechanical shift). Its permutation
   reference adds a within-stratum exchangeability assumption the
   committed state-specific null does not itself imply; divergence
   between it and the primary is diagnostic, not error.
3. Window-restricted graded exposure: within the 28 pooled tier-window
   states, I_s = (fy2025 − assigned cut)/sd_s — the signed distance to
   the state's *own* assigned cut in committed-SD units (assigned cuts
   from the artifact's rosters; sd_s the committed `sampling_sd`).
   Spearman correlation between u_s and I_s; one-sided negative under
   response; permutation p-value (20,000 permutations of the u values
   across the 28 states, seed 20260932; midrank ties). Within a window,
   distance to the own cut is a locally coherent exposure measure;
   across the whole rate line it is not, which is why the all-state
   version is descriptive only:
4. All-jurisdiction descriptive scatter: the same Spearman over all 53
   using the nearest tier cut in {6, 8, 10} (tie → lower), reported
   *without* a committed direction. A single signed nearest-cut index is
   sawtoothed across tiers — a state just above 7% is nearest the 8 cut
   from below while its cost-saving margin is the 6 cut — and the
   artifact's `signed_distance_pp` field is not this index (it mixes in
   the delay boundary, whose incentive points the other way; New York's
   −0.15 is distance to 13.33, not its +3.18 to the nearest tier cut).
5. Drift-widened re-runs of the primary and delay tests under both
   committed τ variants (sensitivity, not confirmation).
6. Fixed-width window re-runs (±0.75, ±1.25 pp).
7. Sampling-plan-adjusted re-run: the null fixes each state's QC sample
   at its fiscal 2024 comparable size (m = n), so a state that changes
   its sampling plan changes its own measurement dispersion — a null
   violation that is itself outcome 2. Sensitivity: recompute each
   window state's PIT against its committed variant nearest its
   realized fiscal 2026 comparable record count (baseline, +300, or
   +500), and re-run the primary and delay tests. The committed
   extra-sample variants exist for exactly this purpose.

## Committed power (and what we cannot detect)

Simulated under the null DGP with shifts injected into the treated
group (2,000 replications; seeds 20270601/20270602; common random
numbers across shift sizes; size checks at δ = 0). The first two columns
are the sampling-only world; the drift columns draw realized rates from
the committed drift-widened worlds while the test keeps its registered
sampling-only reference — their δ = 0 rows are the registered test's
*size distortion* under those worlds, committed rather than hidden:

| Uniform shift δ | Primary | Delay | Primary, τ=1.074 | Delay, τ=1.074 | Primary, τ=1.62 | Delay, τ=1.62 |
|---|---|---|---|---|---|---|
| 0 (size) | 0.0485 | 0.052 | 0.105 | 0.0915 | 0.114 | 0.1115 |
| 0.25 pp | 0.2205 | 0.1785 | 0.2085 | 0.1905 | 0.203 | 0.1985 |
| 0.50 pp | 0.534 | 0.426 | 0.3565 | 0.3625 | 0.3005 | 0.3085 |
| 1.00 pp | 0.9495 | 0.917 | 0.6935 | 0.7305 | 0.534 | 0.595 |

Honest reading, committed now, variant-specific. Sampling-only world:
the primary detects a coordinated one-point response with ~95% power
(delay ~92%), a half-point response with roughly even odds (delay 43%),
and a quarter-point response rarely; 80% power sits near 0.8 pp for the
primary and near 0.9 pp for the delay test by interpolation (not
committed grid points). Drift worlds: the same registered tests reject
a true one-point response only ~53–73% of the time, and their false
positive rates at δ = 0 inflate to ~9–11% — which is why the tail-share
trigger and drift-widened re-runs govern a drift-classified year. All
rows are pointwise power against coordinated, homogeneous additive
shifts — not an MDE for heterogeneous, sparse, or correlated responses,
which the design detects with lower probability at the same average
size. A null result is consistent with "no response", with "coordinated
response below ~0.5 pp", and with larger responses that are
heterogeneous, sparse, or offsetting; we commit to reporting it that
way. The value of registering a small-N design is not power — it is
that whatever happens, the classes of claims that survive are fixed in
advance.

## Outcome list

| # | Outcome | Definition and source | First observable | Class | Committed direction |
|---|---|---|---|---|---|
| 1 | Fiscal 2026 measured rates | Published two-decimal total rate per jurisdiction, first FNA FY2026 PER publication (FACTS J1 precedent); derived: Δ, PIT u_s, tier, delay test | ~mid-2027 (precedent-based; unsourced) | Primary | Above-window states down relative to null vs below (primary test) |
| 2 | Sampling-plan election and realized sample size | Reduced vs standard active-case schedule election per jurisdiction, transcribed from the FY2026 QC technical documentation (FACTS A4/A5 precedent: all 53 elected reduced in FY2024, waiving precision disputes); realized comparable record count n26 constructed exactly as `data.json` n (a filtered analysis count, not a planned sample). Honesty note: the FY2026 election was necessarily made before the measurement year began — i.e., before this registration — so it is registered as a sealed, unpublished record to be transcribed, not a choice this registration predates; fiscal 2027's election is the first a state could still change post-registration | With the FY2026 public-use file (lag unknown) | Secondary | Committed exposure: sign of elect28(+500) − elect28(baseline) per state (micro-rules; +300 reported alongside; LA and NY flip between variants, disclosed); predicted-benefit states move toward the standard schedule / larger samples; Fisher exact one-sided (exploratory) |
| 3 | Additional sampling/precision relief | Any FNA-disclosed QC sampling or precision relief beyond the reduced-schedule bundle, with record identifiers. The repository grounds no standalone "precision waiver" program — the operative waiver is the reduced-schedule election (outcome 2) | Conditional on such records existing | Conditional | None (report-only) |
| 4 | FY2025-vs-FY2026 election for the FY2028 share | Explicit public record only; never inferred from which rate is lower. Compared to committed p_win per state | Timing ungrounded | Conditional | None (report-only) |
| 5 | Cause-mix shifts | Shares of official error dollars by the exact classes serialized in `analysis/cause_shares.json` (strict {17,19,20}; broad {10,17,19,20,21,22}; 14-code agency set; client codes {1,2,3,4,7} as contrast classes; codes 8 and 26 as code-specific negative-control diagnostics under the exclusive/fractional conventions), window states vs others, FY2024 → FY2026; any-presence convention primary, the artifact's other serialized conventions reported alongside; year-specific official thresholds primary, fixed-gate recomputation as robustness | With FY2026 microdata (lag unknown; snapqcdata.net precedent) | Exploratory | None committed; measurement-side response predicts concentration in agency-side classes among exposed states |
| 6 | Tolerance-threshold bunching | Distribution of recorded error amounts around the $58 FY2026 threshold (design 4 of the memo), window states vs others | With FY2026 microdata | Exploratory | Mass at or just below $58 concentrated in window states, if adjudication responds to the cutoff |
| 7 | National rate | Published FY2026 national rate (context) | With outcome 1 | Secondary | None (report-only) |

Dropped, with reasons committed: a state-level negative-case
(case-and-procedure) error-rate outcome — the manuscript grounds the
incentive (the unpriced metric absorbs front-door tightening) but the
repository grounds no state-level publication precedent, so no
operational definition survives; it may return as a conditional record
if publication materializes.

## Falsification tests

1. **Placebo cuts at 7% and 9%.** Identical window construction and
   pooled test at cuts with no statutory step, executable-unique as
   `placebo_cuts_test()` (MC seed 20260936). The committed rosters
   (test-locked): 7% — NC above vs NJ NV OH WA WV below, a thin and
   lopsided window, disclosed; 9% — AL CO CT KS MI MS ND PA TN TX above
   vs AR LA MO MT NH SC below. Expected under H0: null. Under a true
   boundary response the placebo statistic is not exactly
   null-distributed — placebo groups contain real-cut-treated states —
   so a small placebo effect alongside a large primary effect reads as
   contamination; a placebo effect *without* a primary effect is the
   damaging pattern.
2. **Pre-period placebo (FY2024 → FY2025), executed at registration.**
   The identical design anchored at fiscal 2024, executable-unique as
   `pre_period_placebo_test()`: draws anchored at the published FY2024
   rate, windows, sides, and nearest-cut assignment from those draws and
   the FY2024 rates, outcome = the published fiscal 2025 rates, MC seed
   20260935. The outcome predates registration, so the result is
   computed now and test-locked: 15 above, 17 below, T = +0.073,
   p = 0.763 — no rejection, and the point estimate sits *opposite* the
   response direction. Committed interpretation: fiscal 2025 was
   partially exposed (its final quarter followed the July 4, 2025
   enactment per the GPO record, and the congressional consideration
   that preceded enactment was public record), so this null supports
   design validity without proving the absence of early response; it
   speaks only to the tested direction.
3. **Placebo outcome classes.** Two layers, both from the classes
   serialized in `analysis/cause_shares.json`. Negative-control
   diagnostics: code 8 (`excluded_federal_match` — the codebook excludes
   its variance from error determination) and code 26
   (`no_required_action`), tabulated *code-specifically* under the
   artifact's exclusive/fractional conventions — under the overlapping
   any-presence convention, correcting a co-coded error would move them
   mechanically, which is why any-presence is not used for them.
   Movement there flags coding-practice change, itself a possible
   measurement-side channel; they are diagnostics, not universal
   invariants. Contrast classes: client-caused codes ({1,2,3,4,7})
   versus agency-side codes — real error reduction plausibly moves
   client classes; a purely adjudicative response concentrates in
   agency-side codes. Read jointly with outcome 5.
4. **Exclusion sensitivity.** Drop territories (GU, VI); drop the
   FY2025 delay-roster states from tier windows; fixed-width windows.
5. **Common-shift robustness.** The rank-sum secondary is exactly
   invariant to common level shifts (the threshold move, national
   drift). A primary rejection that vanishes under it is sensitivity
   evidence to report and weigh — the two tests differ in estimand,
   scale trust, and power, so divergence alone does not identify a
   common-shift artifact; the drift sensitivities and the tail-share
   trigger carry that diagnosis.
6. **Tail-share drift check.** If many non-window states also land in
   their nulls' tails (beyond the FACTS J2 |z| > 2.77 share logic), the
   year moved for reasons the sampling-only null excludes; the
   drift-widened variants arbitrate, and no boundary claim will be made
   from a rejection that disappears under the committed τ = 1.074
   sensitivity.

## Registered micro-rules

Conventions an analyst would otherwise choose at analysis time, fixed
now:

- Fixed-width windows: a state inside two fixed-width windows is
  assigned by the same nearest-cut rule (tie → lower cut); sides by the
  published rate, equality above — executable as
  `fixed_width_partition()`, with the ±1.25 partition test-locked (nine
  states fall inside two windows there).
- The secondary re-runs (1–7) and the exclusion falsifications are
  specified in prose with pinned seeds, conventions, and these
  micro-rules; unlike the primary, delay, placebo, RTM, and partition
  machinery they are not CI-locked executables, and any residual
  ambiguity found at analysis time resolves by the written spec and is
  reported transparently.
- Rank ties anywhere (Wilcoxon, Spearman, PIT): midranks.
- Stratified rank-sum reference: enumerate all within-stratum side-label
  assignments when the product across strata is ≤ 20,000; otherwise
  20,000 Monte Carlo assignments, seed 20260934.
- Sampling-plan-adjusted re-run (secondary 7): each state maps to the
  committed variant minimizing |realized comparable record count −
  variant m|; an exact tie maps toward the baseline variant.
- Missing jurisdictions: rosters stay as registered; a missing state
  drops from every statistic it would have entered, with the reduced
  roster reported.
- Empirical p-values: inclusive tails, no +1 correction, reject at
  p ≤ α — exactly as serialized in the artifact's inference pins.
- Exclusion sensitivities are applied one at a time, never crossed.
- Outcome capture: on first observation of the official fiscal 2026
  state PER table, the exact published bytes are SHA-256-hashed and
  committed to this repository (the fiscal 2025 precedent: the PER PDF's
  hash in FACTS J1); that committed capture is the primary outcome
  source. Precedence: the agency's publication file itself over
  announcements. A same-URL revision after capture counts as a revision
  (reported alongside, primary on the capture). FNA's official successor
  agency, if any, is treated as FNA.
- Sampling-plan concordance exposure (outcome 2): the predicted
  precision-value sign per state is the sign of
  elect28(extra_sample_500) − elect28(baseline) from the committed
  artifact; the +300 variant is reported alongside, and the two states
  whose sign flips between the variants (LA, NY) are disclosed now. A
  zero delta excludes the state from the sign table. Fisher test
  one-sided, alternative odds ratio > 1.
- Tail-share drift trigger, numerically: z_s = (r26 − fy2025)/sd_s with
  the committed SDs; under the sampling-only null with independence,
  P(|z| > 2.77) = 5% per state (the FACTS J2 two-year band). The year is
  drift-classified when ≥ 8 of 53 jurisdictions exceed the band
  (probability 0.0046 under that null); a drift-classified year's
  headline claims run under the drift-widened sensitivities.

## Multiplicity and reporting commitments

One confirmatory test (the pooled tier-window primary, α = 0.05,
one-sided). One committed secondary with its own α = 0.05 (the delay
window) — no experiment-wide error rate is claimed across the pair.
Everything else — secondaries, falsifications, outcomes 2–7 — is labeled
and will be reported in full, with no selection: every statistic named
in this document appears in the results publication regardless of sign
or significance. No non-primary p-value will be described as
confirmatory; passing falsifications cannot rescue a failed primary.
Analyses beyond this document will be labeled post hoc.

## Pre-committed interpretation rules

Throughout, "rejects" means evidence against the committed no-response
null, consistent with boundary response; the channel readings below are
suggestive, never identification.

- Primary rejects, cause-mix shifts concentrate in agency-side classes
  among exposed states, or bunching sharpens at $58 → measurement-side
  response is the leading reading.
- Primary rejects, no cause-mix anomaly, sampling-plan changes align
  with the committed precision-value signs → provisionally consistent
  with real behavioral response — provisional because sampling-plan
  changes are themselves measurement choices, so this pattern supports
  but cannot prove a purely behavioral mechanism.
- Primary fails to reject → consistent with no response at the committed
  power; explicitly also consistent with sub-half-point responses.
- Delay-window U significantly above 1/2 → deferral-seeking drift; New
  York's singleton outcome is reported against its committed 0.4173
  crossing odds either way.
- Many-state tail landings (the ≥ 8-of-53 trigger) without a boundary
  pattern → process drift, not boundary response; drift-widened
  sensitivity governs, including its committed size-distortion rows.
- At analysis time, the fiscal 2026 technical documentation is audited
  against fiscal 2024/2025 for QC-methodology and federal re-review
  changes (threshold, sampling formulas, re-review procedure); a
  material state-varying change is reported, and affected jurisdictions
  get an exclusion sensitivity — the committed simulator holds the
  re-review layer fixed and cannot itself detect such a change.

## Threats and limitations, committed now

**What this registration does and does not remove.** The design
necessarily postdates the fiscal 2025 publication — the running
variable *is* that publication — so freedom in choosing the design
conditional on fiscal 2025 was real, and no registration can remove it.
What registration removes is freedom conditional on the *outcomes*:
window rules, statistics, seeds, directions, and the report-all
commitment are fixed while fiscal 2026 is unmeasurable. The discipline
on the former is structural: one confirmatory test, canonical window
rules stated with their sensitivity variants, and every named statistic
reported regardless of result.

Small N (28 pooled window states; a one-state 8%-below cell); the
FY2024-composition and $56-threshold basis of the null (disclosed
above); sampling-only dispersion as a lower bound (drift variants are
sensitivity, not the primary); the null's fixed fiscal-2024 sample sizes
(a state that changes its sampling plan changes its own dispersion —
secondary 7 is the committed adjustment); cross-state error correlation
beyond common shifts (the rank-sum secondary absorbs exactly-common
shocks; correlated idiosyncratic shocks remain a disclosed exposure of
the independence assumption, and shocks *aligned with above/below
membership* would move the primary's size, not just its power);
territories with distinct QC regimes
inside windows (exclusion sensitivity); the election and some outcome
records may never publish (conditionals); and the design detects
response, not its welfare sign — a state that genuinely reduces errors
and one that games measurement move the same primary statistic, which is
why the outcome battery, not the primary alone, carries the
interpretation.

## Artifact integrity and regeneration

`analysis/preregistration_obbba_boundary.json` is
`{payload, payload_sha256}` where `payload_sha256` is the SHA-256 of the
canonical compact serialization of the payload (sorted keys). The file
regenerates byte-identically via:

    uv run --frozen --extra analysis python analysis/preregister_obbba_boundary.py

`tests/test_preregistration.py` locks, in CI: bit-faithful equality of
the vectorized RNG against the loop reference; byte-identical
regeneration; the self-pin; the FACTS J8/M2/M3 golden cross-locks;
roster reconstruction from the serialized per-state probabilities;
integer-count/probability consistency; sanity invariants; all six
committed power tables including the drift-world size-distortion rows;
an executable-spec run of the registered test callables on the locked
fiscal 2025 rates; the committed pre-period placebo result (15/17,
T = +0.073, p = 0.763); the 7/9 placebo-cut rosters; the ±1.25
fixed-width partition and the missing-jurisdiction rule; and the
regression-to-the-mean shrinkage parameters and sensitivity. The hashes
at the top of this document are asserted against the committed artifact
by the same test file (historical pins permitted only inside a dated
Amendments section), so the document and the artifact cannot drift
apart silently.

## Relation to the manuscript

The manuscript's §"The realized fiscal 2025 rates" and FACTS J9 disclose
that fiscal 2025 was not pre-registered. This registration closes that
gap prospectively for fiscal 2026: predictions committed, hashed, and
publicly timestamped before the measurement year closes and before its
official outcomes exist or are observable. The manuscript gains a
pointer to this document; results will enter a future revision under
the reporting commitments above.
