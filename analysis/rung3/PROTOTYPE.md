# Rung-3 Colorado prototype

## Construction and convention

The accounting chain is: 1,281 current-frame Colorado SPM units → linked
current-build people → PolicyEngine-US eligibility and administrative SNAP
formula amount → committed signed distributional deviation scorer → measured
component dollars. Uncalibrated output is reported first. One exponential
calibration then matches four sums only: average-monthly caseload, annual
issuance, and official overpayment and underpayment dollars (official rates
times issuance). It is an accounting construction, never a causal estimate.

Baseline eligibility is the engine's SPM-unit `is_snap_eligible`, exactly the
variable passed into Microcosm's state take-up stage
(`snap_state_take_up.py:86,101-120,162`). The takes-up flag was assigned
against build-time engine eligibility under those same defaults, so any other
eligibility concept would make `flag ∩ eligibility` incoherent; this is the
flag's own definition, adopted as a documented convention, not an imputation
of observed data.

## Engine inputs and provenance

Monthly earned and unearned income, unit size, elderly/disabled status and
rent come from the Cluster-1 frame. Utility, allowable medical-above-floor,
dependent-care, child-support and homeless concepts are Cluster-1's joint QC
hot-deck outputs. Housing cost is annualized before assignment, following the
6,081/6,081 administrative parity sequence. Ages, disability, full-time
college status, hours, pregnancy, incapacity, immigration status, and the
person-level `is_snap_abawd_discretionary_exempt` come from the current sparse
build's uniquely linked people. The dense/current audit in `CLUSTER1.md`
established equality for the income/demographic sources used here.

Dense `immigration_status_str` values (`CITIZEN`, `UNDOCUMENTED`,
`LEGAL_PERMANENT_RESIDENT`, `CUBAN_HAITIAN_ENTRANT`, `DACA`) are congruent
with the engine enum and are supplied. The engine converts the string at
`variables/household/demographic/person/immigration_status.py:18-28`; SNAP
tests it at `variables/gov/usda/snap/eligibility/
is_snap_immigration_status_eligible.py:15-26`.

## Eligibility defaults

Every unobserved terminal input reached by the FY2024 eligibility chain is
listed below. PolicyEngine-Core's type default is zero, false, or the declared
enum default unless a PE-US variable declares another value.

| Defaulted input | Default | PE-US definition/use | Directional note |
|---|---:|---|---|
| `bank_account_assets`, `stock_assets`, `bond_assets` | $0 | `snap_assets.py:4-25`; sources parameter | Raises normal eligibility by passing the asset test. |
| `ssi`, `tanf`, `is_tanf_non_cash_eligible` participation | $0 / false | `meets_snap_categorical_eligibility.py:12-17`; `categorical_eligibility.yaml:1-16` | Lowers categorical eligibility. |
| SNAP employment/training or work-incentive student placement | false | `student/is_snap_ineligible_student.py:29-36` | Can make observed higher-ed students ineligible; downward eligibility bias. |
| SNAP work-program participation | false | `meets_snap_general_work_requirements.py:46-50` | Non-exempt registrants fail; downward eligibility bias. |
| Weekly SNAP work-program hours | 0 | `meets_snap_abawd_work_requirements.py:43-61` | Non-exempt ABAWDs are less likely to pass; downward bias. |
| SNAP workfare participation | false | `meets_snap_abawd_work_requirements.py:55-61` | Downward eligibility bias. |
| TANF-work-requirement compliance | false | `is_snap_work_registration_exempt_non_age.py:29-31` | Downward eligibility bias for that exemption. |
| Unemployment compensation / drug-alcohol treatment-program participation used by registration exemptions | $0 / false | `is_snap_work_registration_exempt_non_age.py:15-58` | Downward eligibility bias. |
| Veteran and former-foster-youth status | false | `meets_snap_abawd_work_requirements.py:99-112` | Downward eligibility bias for pre-HR1 exemptions. |
| Indian/tribal exemption and ABAWD waived-area flag | false | `meets_snap_abawd_work_requirements.py:79-97` | Downward eligibility bias. |
| Parent/tax-dependent relationship and single-parent student exception inputs | false/default member roles | `student/is_snap_ineligible_student.py:41-46`; ABAWD file `:64-74` | May miss parent/student and ABAWD exemptions; downward bias. |

Not defaulted: age, disability, full-time college status, annual weekly hours,
pregnancy, incapacity, immigration, and the existing person-level ABAWD
discretionary exemption are supplied from linked people.

Colorado BBCE is **not encoded** in this installed PE-US version. The only
categorical parameter entries are SSI, TANF cash, and TANF non-cash
(`parameters/gov/usda/snap/categorical_eligibility.yaml:1-16`). Consequently,
the asset default is not inert under this engine construction, even though
Colorado policy uses BBCE; this is a material downward-policy-fidelity caveat
paired with an upward zero-asset default.

## Results and validation

Machine-readable uncalibrated component ratios appear first in
`prototype_results.json`, followed by the single rake and the FY2025 replay.
The flag-only caseload is a sensitivity row only; every downstream result uses
`flag ∩ eligibility`. FY2025 holds calibrated FY2024 weights fixed and changes
the strict dollar threshold from $56 to $57.

The error scorer uses its native HistGradientBoosting missing routing. The
artifact counts every unavailable feature. Its known geographic/coverage
failure carries as disclosure, not a blocker. QC-moment comparison is limited
to the predicted component/sign mix in this prototype; no `BENFIX`, `RAWBEN`,
`AMTERR`, or `STATUS` is imputed.

Uncalibrated, the convention yields 954,822.6 weighted cases and $2.900
billion issuance; flag-only yields 1,694,242.9 cases. Predicted overpayment is
35.695% (4.513 times the 7.91% target) and underpayment is 4.903% (2.380 times
the 2.06% target). These ratios precede and are independent of calibration.
The four-sum rake matches its targets numerically, but is diagnosed as
degenerate: Kish ESS is 75.6 of 1,281, despite a moderate 1.212 maximum weight
ratio. Calibrated output is therefore a diagnostic, not an endorsed estimate.
With those weights held fixed, the FY2025 replay rises 1.059pp, versus the
official 0.12pp rise (9.97% to 10.09%): direction agrees and magnitude does
not. Runtime was 2,087 seconds (34.8 minutes), 4.8 minutes above the requested
30-minute envelope because of the committed nested-OOF scorer.

## Limitations and Task B

The 1,281 units are a thin current-frame subset, and an SPM unit is only a
proxy for an administrative assistance unit. Cluster-1 rare-component and
housing-cost limitations continue unchanged. The environment split requires
a local deterministic subprocess between the supplied engine and repository
environments. Task B remains a wall-time stub: the deployed statistical-flip
figures (-0.060pp crossing, -$2 million expected FY2028 bill) are recorded but
no engine-grounded SMD result is claimed. Either construction would be
accounting, not causal.
