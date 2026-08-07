# What share of SNAP payment errors could a verified rules engine prevent?

Colorado FY2024, from the USDA SNAP QC public-use file. Built 2026-07-11 on
top of the 856/856 benefit-parity result (axiom-oracles#268) and the
Giannella/Molin raw-variable reconstruction (github.com/giannella/snap_qc,
run for FY2024 in this lab: `reconstruct_co_fy2024.R`).

## The three layers (increasing strictness)

All dollars HWGT-weighted and annualized from the FY2024 file; Colorado has
856 sampled cases, 305 with payment errors (STATUS 2/3), $112.6M/yr weighted
error dollars on $1.268B issuance (8.88% file-derived; FNS's official
regression-adjusted FY2024 Colorado rate is **9.97%** — over 7.91 + under
2.06, snap-fy24QC-PER.pdf).

### Layer 1 — QC's own cause coding (native, no model needed)

Every error finding carries an AGENCY cause code (codebook: FY-2024 Tech Doc).
Case-attributed error dollars (a case counts if any finding has the code;
per-finding AMOUNTs are mostly zero-filled in Colorado, so case attribution
is the usable metric):

| class | cause codes | cases | $/yr | share of error $ |
|---|---|---|---|---|
| strict computation (programming 17, arithmetic 20, mass change 19) | 17/19/20 | — | $8.2M | 7.3% |
| + policy misapplied 10, budgeted wrong 22, computer user 21 | +10/21/22 | 35 | $11.9M | 10.5% |

National, same coding: strict $320M/yr (3.9%); broad $1.5B/yr (18.4%) of
$8.1B/yr weighted error dollars on $88.8B issuance.

### Layer 2 — finding-nature classification (cause-disambiguated)

Natures that inherently describe computation (rounding 36, conversion 42,
averaging 43, wrong standard 54/64/65, benefit incorrectly computed 75,
allotment tables 79, proration 80/123, transcription-or-computation 98,
element 520) plus deduction-amount natures 52/53/56/57 only when the cause
code is system-side:

| class | cases | $/yr | share |
|---|---|---|---|
| pure_math (all findings computation) | 13 | $3.66M | 3.3% |
| input_system_caused | 19 | $7.47M | 6.6% |
| mixed | 13 | $4.68M | 4.2% |
| input_other | 260 | $96.8M | 86.0% |

### Layer 3 — engine-verified (the demonstrable core)

Method: reconstruct each error case's pre-edit ORIGINAL values with the
Giannella/Molin $3-shift solver (FY2024 adaptation, smoothing off), replay
them through the Axiom engine (the one proven 856/856 exact on corrected
inputs), compare to RAWBEN (what the agency actually issued), at the file's
own $5 editing tolerance.

- 283 of 305 error cases survive the authors' consistency filters.
- **246/283 (86.9%): engine(original) ≈ RAWBEN** — the issuance is correct
  arithmetic on wrong facts. Input/information errors, faithfully propagated.
  (Perfect concordance: the R solver and the Rust engine partition the 283
  cases identically — 246 explained by both, 37 by neither.)
- **37/283: no single-variable original value + correct math reproduces the
  issuance.** Upper bound on computation-side; includes solver limitations
  (multi-element, household-composition interactions).
- **10 of those 37 also carry QC's own computation/policy cause coding**:
  the engine-verified computation class. **$3.28M/yr = 3.3% of replayed
  error dollars.** For each, on the facts the agency recorded, the verified
  engine returns the reviewer-certified correct benefit and the agency
  system did not — e.g. 202312-40441: issued $704, correct $973 = engine
  (a $269/month underpayment from "benefit incorrectly computed").

Colorado's computation-class error patterns: initial-month proration bugs,
"benefit/allotment incorrectly computed," wrong SUA standard applied,
child-support deduction programming errors, Social Security COLA mass-change
failures, wage conversion/averaging misapplied, and one homeless-shelter
deduction wrongly omitted (element 362 — the same provision whose stale $143
literal our own first run caught).

## Why this is millions: the OBBBA cost-share tiers

7 USC 2013(a)(2) (verified from the US Code, prelim): beginning FY2028 the
state share of benefit costs is 0% / 5% / 10% / 15% for payment error rates
<6 / 6–8 / 8–10 / ≥10, keyed for FY2028 to the state's FY2025 or FY2026 rate
(state's election), then to the third preceding year.

- One tier ≈ 5% of Colorado's ~$1.27B issuance ≈ **$63M/yr**.
- Colorado's official FY2024 rate is **9.97% — 0.03 points from the 15%
  tier**. Its QC-coded system/policy-application errors are ~10.5% of its
  error dollars ≈ **~1.0 point of the rate** — 30× the margin to the worse
  tier, and half the distance to the better (8%) one.
- Nationally: 10.93% official FY2024 rate; the broad system/policy class is
  $1.5B/yr of weighted error dollars.

The rate that determines the FY2028 share is FY2025/FY2026 — being measured
NOW. Computation-class errors are the share a state can eliminate by fixing
software, without changing verification practice or client behavior.

## Distinguishing rules-engine causes from others

Two axes separate "the software did it" from worker and client causes.

**Axis 1 — QC cause codes.** Software-specific codes are 17 (computer
programming error) and 19 (computer-generated mass change): unambiguous
system attribution by the reviewer. Worker-computation codes: 20
(arithmetic), 21 (computer user error). Human keying: 18 (data entry).
Ambiguous human-or-software: 10 (policy incorrectly applied), 22 (budgeted
wrong). Case-attributed error dollars:

| class | Colorado | share | National | share |
|---|---|---|---|---|
| software (17+19) | $7.0M/yr (18 cases) | 6.2% | $240.6M/yr | 3.0% |
| worker computation (20+21) | $1.2M/yr | 1.1% | $107.1M/yr | 1.3% |
| data entry (18) | $18.5M/yr | 16.4% | $176.2M/yr | 2.2% |
| policy misapplied / budgeted wrong (10+22) | $3.7M+/yr | 3.3%+ | $1,210M/yr | 14.9% |

Colorado's software-coded share is double the national rate (6.2% vs 3.0%),
and its data-entry share is 7x national — a CBMS-specific signature.
Worker arithmetic is nearly extinct (5 CO cases): the system does the math,
so when the math is wrong it is mostly the system.

**Axis 2 — the engine replay splits HOW the software failed.** Of the 16
replayable software-coded (17/19) Colorado cases:

- **14 = automation fed itself the wrong input** ($4.3M/yr): COLA mass
  changes writing wrong RSDI/SSI amounts, interfaces budgeting wrong child
  support or rent — then computing correctly on the bad value. The engine
  reproduces the issuance from the reconstructed wrong input. Fixed by
  verified data integrations, not by rules logic.
- **2 = computation logic itself wrong** ($2.4M/yr): no input value under
  correct rules reproduces what the system issued.

The complementary class — the 10 engine-verified computation cases
($3.3M/yr) from layer 3 — includes those 2 plus worker-arithmetic and
policy-misapplication cases: everything where the benefit determination
was wrong GIVEN the recorded facts. That is the class a verified rules
engine eliminates regardless of whether human or machine did the math,
because it replaces both. Together with the automation-fed class, the
"modern verified eligibility stack" claim covers ~$7.6M/yr ≈ 6.7% of
Colorado's error dollars.

Cause-coding caveat: reviewer cause assignment varies in quality across
states (the tech doc notes FY2024 coding-definition changes); the engine
replay is the independent check on it, which is exactly the role it plays
in axis 2.

## Caveats (do not drop these when quoting)

- Within-state tabulations from the QC sample are not designed to be
  state-representative (tech doc warning); the official PER uses regression
  adjustment. Shares (%) are more defensible than $ levels; both are
  FY2024-sample-based.
- Cause codes mix software and caseworker action: 17/19/20/21 are
  machine/system; 10/22 can be either. "System or policy-application"
  is the honest label for the broad class; the engine-verified 10 are the
  individually demonstrable core.
- The engine replay validates the BENEFIT COMPUTATION; eligibility-side
  errors (person included/excluded) are only partially modeled (household
  size shifts approximate member effects).
- The solver is $3-granular; $5 (the file's own edit-loop tolerance) is the
  operating comparison tolerance. Exact-tolerance rates are not meaningful
  at this layer.
- FY2024 evaluated via the compile-time COLA overlay at the nominal period
  (rulespec-us#759 pending), same as the parity run.

## Artifacts

- `native_decomposition.json`, `phase_a_classification.json` — layers 1–2
- `reconstruct_co_fy2024.R` → `co_fy2024_reconstruction.csv` (283 CO rows),
  `fy2024_reconstruction_national.csv` (15,902 rows, all states)
- `amterr_replay.py` → `amterr_replay_results.json` (engine vs RAWBEN per case)
- Official rate table: `../snap-qc/snap-fy24QC-PER.pdf`; tiers: 7 USC 2013(a)(2)
