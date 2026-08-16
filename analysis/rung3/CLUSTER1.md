# Rung-3 cluster 1: Colorado deduction composition

## Finding

The prototype uses the **current sparse Microcosm frame's 1,281 Colorado SPM
units**. It does not expand the take-up flag onto the 4,670-unit dense frame.
All 1,281 current-frame units join uniquely to dense units on
`spm_unit_source_id`, `spm_unit_support_channel`, and
`spm_unit_support_clone_index`, but the current build is only a subset. A
dense-wide join would therefore fabricate 3,389 take-up values. The current
frame is the only supplied artifact with both `pre_subsidy_rent` and
`takes_up_snap_if_eligible`.

The output is an estimation-layer table. It contains no `BENFIX`, `RAWBEN`,
`AMTERR`, or `STATUS`; a benefit engine remains responsible for statutory
deductions and benefits.

## Sources and locks

| Artifact | SHA-256 |
|---|---|
| FY2024 QC CSV | `45193eb7370463ab3067d71da23a580fec34a5460341e4e750dda0be061e1aa9` |
| Dense Microcosm HDF5 | `a86d91aef9f82819abb0c845b042e92c677b9720dc9bf6014778ce299730d32f` |
| Current sparse Microcosm HDF5 | `48b9d479fb4fd1c3537f9383ce4697d130b6f618658409d74f6233c43b994c7e` |

The sandbox refused the requested copy to
`~/.cache/axiom-oracles/snap-fy27/populace_us_2024_buildp.h5` because that
cache is outside the writable workspace. Both the source path and hash are
locked instead.

The sparse-build zeroing caveat was checked on all 3,274 Colorado persons
that underlie the selected units. Every person joined uniquely to dense on
the three source-identity fields. `WSAL_VAL`, `SEMP_VAL`, `PTOTVAL`, `A_AGE`,
`SPM_CHILDCAREXPNS`, `SPM_MEDXPNS`, and `SPM_CHILDSUPPD` agreed exactly in all
3,274 rows; their sparse nonzero counts were respectively 1,663, 238, 814,
3,235, 377, 3,197, and 38. The imputation features use only the first four of
these audited fields. Fitted rent exists only in current and is not
re-imputed.

## Take-up semantics

Microcosm's state stage operates at SPM-unit grain. Reported positive
`SPM_SNAPSUB` is an unconditional anchor. Non-reporters receive a stable draw
under a state fill rate and eligible non-anchors are greedily reassigned to
the FNS average-monthly household target. Assignment is deliberately not
masked by build-time eligibility: off-domain units retain a propensity for
eligibility-expanding reforms. At baseline, modeled caseload is the flag
intersected with engine eligibility. These semantics are stated and
implemented in
`packages/microcosm-build/src/microcosm/build/us_runtime/snap_state_take_up.py:1-43,101-170,225-305`.

Thus `takes_up_snap_if_eligible` does **not** mean that every flagged unit was
eligible during the build, nor does it represent within-year churn. The
selected frame has 842 true and 439 false Colorado flags; 94 units report
positive `SPM_SNAPSUB`.

## Feature map and model

The model is a seeded, survey-weighted nested hot deck trained on all 856
Colorado `CASE == 1` FY2024 QC cases. A held-out quarter is selected by a
stable hash of case ID. For each target, one QC donor supplies utility
treatment, utility dollars, all four deduction claim indicators/dollars, and
the homeless claim jointly. Matching backs off through progressively coarser
cells but always retains elderly/disabled status; medical is then forced to
zero outside that statutory domain. This preserves observed dependence and
structural zeros rather than fitting independent marginal classifiers.

| Concept | QC source | Microcosm counterpart | Use |
|---|---|---|---|
| Unit size | `CERTHHSZ` (QC technical document pp. 56, 65) | count of `person_id` by `person_spm_unit_id` in current `/person` | bands: 1, 2, 3, 4+ |
| Monthly earned income | `FSEARN` | sum of audited raw `WSAL_VAL + SEMP_VAL` by SPM unit, divided by 12 | bands |
| Monthly unearned income | `FSUNEARN` | audited `max(PTOTVAL - earned, 0)` summed by SPM unit, divided by 12 | gross-income bands |
| Elderly/disabled | `FSNELDER + FSNDIS > 0` (technical document pp. 56, 65-66) | `A_AGE >= 60` or any `PEDIS* == 1` in current `/person` | retained at every fallback level; medical domain |
| Children | `FSKID > 0` (technical document pp. 56, 65) | any `A_AGE < 18` in linked persons | composition cells |
| Shelter band | recorded `RENT` | maximum `pre_subsidy_rent` in linked persons, divided by 12 | joint utility-treatment matching; never imputed |
| Weight | `HWGT` | linked `household_weight` | donor probabilities and reporting |

No QC-only field enters the feature set. `SUA1`, `UTIL`, `FSMEDEXP`,
`FSDEPDED`, `FSCSDED`, and `HOMEDED` are outcomes only. The QC codebook defines
`FSMEDEXP` as allowable medical expenses already above the $35 floor and
defines `SUA1 == 2` as actual expenses (technical document pp. 74, 76).

The transparent artifact records every donor, weight, feature level, pool,
seed, validation result, source hash, and application rate in
`cluster1_models.json`.

## Distributional validation

The deterministic holdout contains 209 cases. Weighted claim-rate results:

| Claim | Held-out truth | Prediction | Ratio |
|---|---:|---:|---:|
| Actual utility expense (`SUA1 == 2`) | 0.0000 | 0.0000 | n/a |
| Medical | 0.0607 | 0.0737 | 1.215 |
| Dependent care | 0.0243 | 0.0043 | 0.175 |
| Child support | 0.0135 | 0.0184 | 1.365 |
| Homeless standard deduction | 0.0000 | 0.0231 | n/a |

Colorado has no `SUA1 == 2` cases in either train or holdout, so the fitted
actual-expense probability is correctly zero; the artifact retains the full
1/3/4/5/6/7/8 utility-treatment categories rather than collapsing them.
Rare dependent-care and homeless outcomes are unstable in a one-quarter
holdout. This is an honest limitation of 856 state cases, not a tuned match.

Conditional positive-dollar weighted quantiles (truth / prediction):

| Amount | p25 | p50 | p75 | p90 |
|---|---:|---:|---:|---:|
| Utility | 560 / 560 | 560 / 560 | 560 / 560 | 560 / 560 |
| Medical above floor | 165 / 165 | 165 / 165 | 165 / 165 | 165 / 227 |
| Dependent care | 7 / 37 | 108 / 37 | 119 / 37 | 200 / 37 |
| Child support | 281 / 100 | 396 / 608 | 851 / 608 | 851 / 608 |

The full utility-treatment by shelter-band weighted cross-tab is serialized
under `validation.utility_by_shelter_band` in the model artifact.

## Applied-frame sanity (not calibrated)

| Claim | QC weighted rate | Frame weighted rate | Frame/QC |
|---|---:|---:|---:|
| Actual utility expense | 0.0000 | 0.0000 | n/a |
| Medical | 0.0586 | 0.1088 | 1.857 |
| Dependent care | 0.0145 | 0.0191 | 1.312 |
| Child support | 0.0145 | 0.0060 | 0.416 |
| Homeless standard deduction | 0.0110 | 0.0034 | 0.310 |

These are reported without tuning. The elevated medical rate follows the
current frame's elderly/disabled mix and conditional donor matching.

## Limitations

- The SPM unit is only a proxy for the administrative SNAP assistance unit.
- Current is a 1,281-unit subset of dense, so this prototype does not cover
  all 4,670 dense Colorado units.
- `pre_subsidy_rent` is the supplied ACS-fitted rental cost; zero is retained
  for non-renters. Mortgage/property-tax shelter costs are not invented.
- The weighted hot deck preserves empirical combinations but cannot estimate
  smooth tails from 12 dependent-care and 12 child-support claims.
- Colorado supplies no actual-utility (`SUA1 == 2`) training examples.
- The pinned environment lacks `pyarrow` and `fastparquet`; train/apply and
  JSON generation run in about four seconds, but Parquet materialization is
  blocked locally. No network installation was attempted.
