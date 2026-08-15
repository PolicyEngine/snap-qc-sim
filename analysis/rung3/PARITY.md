# PolicyEngine SNAP parity

## Promotion verdict

**NOT YET.** Blockers: AZ, CA, CO, GA, MD, NY, TX have non-matching cases.

## Parity results

| State | In scope | Exact matches | Match rate |
|---|---:|---:|---:|
| AZ | 922 | 559 | 60.63% |
| CA | 883 | 370 | 41.90% |
| CO | 856 | 436 | 50.93% |
| GA | 945 | 446 | 47.20% |
| MD | 722 | 332 | 45.98% |
| NY | 847 | 363 | 42.86% |
| TX | 906 | 366 | 40.40% |

## Divergence diagnoses

- `deduction_concept`: 2,393 cases.
- `rounding_convention`: 814 cases.
- `engine_rule_difference`: 2 cases.

### Deduction concepts

The dominant class first diverges in gross, shelter, or net income despite the uniform direct overrides. It captures definition and arithmetic differences between PE-US's composed deduction tree and the recorded administrative intermediates; it is not state SUA re-derivation because recorded `UTIL` is forced.

### Rounding convention

These cases first differ only at the final allotment or at a whole-dollar intermediate. PolicyEngine-US retains fractional deductions and computes 30 percent of floored net income, while the QC replay floors the earned deduction and ceilings the benefit reduction.

### Engine rule difference

Two Colorado cases follow PE-US's conditional homeless maximum rather than the QC replay's claimed flat homeless deduction. This is a formula-encoding difference, not an unavailable-input classification.

## Execution and mapping

The full run used vectorized `policyengine_us.Microsimulation` batches grouped by exact `YRMONTH`; runtime was 64.24 seconds. The public policyengine.py route is annual-only, so its 50-case January spot check annualized monthly inputs and divided annual output by 12: 50/50 exact, maximum absolute difference 2.03451e-05. The machine-readable artifact records every mapping decision and installed-source citation.

The formula comparator is `snap_normal_allotment`, not `snap`: the former is the ordinary allotment before take-up, emergency allotments, and DC supplements. Recorded `UTIL` directly overrides `snap_utility_allowance`; the harness does not re-derive state SUA rules. Eligibility is uniformly forced true for this positive-FSBEN certified-recipient scope, so BBCE, assets, immigration, and work requirements do not silently redefine the oracle population.

## Version skew

This run used policyengine 5.0.2 and policyengine-us 1.764.6, the versions certified by policyengine.py's manifest in the provisioned environment. Installing policyengine-us 1.808.0 fails policyengine.py's provenance gate at import; that known skew was not bypassed.
