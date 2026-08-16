# Fixed-donor UHIP decomposition

## Reproduction check

**PASS** — fixed-donor client effect 3.96420218495225, p 0.232558139534884, rank 10 of 43.

## Side-by-side results

| Channel | Estimator | Effect | p-value | Rank | Parent verdict | Family-adjusted verdict | Consequence minus later |
|---|---|---:|---:|---:|---|---|---:|
| defect | joint_fit | 0.906759 | — | — | — | — | 1.526533 |
| defect | fixed_donor | 0.613676 | — | — | — | — | 0.788005 |
| mass_change | joint_fit | 2.082104 | 0.023256 | 1/43 | no_protocol_defined_signal | signal_family_adjusted | 2.776080 |
| mass_change | fixed_donor | 2.141524 | 0.023256 | 1/43 | signal | signal_family_adjusted | 2.996784 |
| arithmetic | joint_fit | 0.309172 | — | — | — | — | 0.113372 |
| arithmetic | fixed_donor | 0.432588 | — | — | — | — | 0.235907 |
| user | joint_fit | 0.273861 | — | — | — | — | 0.366796 |
| user | fixed_donor | 0.247953 | — | — | — | — | 0.404371 |
| entry | joint_fit | 0.655759 | — | — | — | — | 0.449881 |
| entry | fixed_donor | 0.567427 | — | — | — | — | 0.552711 |
| disregard | joint_fit | 0.557492 | 0.790698 | 34/43 | no_protocol_defined_signal | no_family_adjusted_signal | 2.044472 |
| disregard | fixed_donor | 1.373084 | 0.511628 | 22/43 | no_protocol_defined_signal | no_family_adjusted_signal | 1.197094 |
| recert | joint_fit | 0.000000 | — | — | — | — | — |
| recert | fixed_donor | 0.000000 | — | — | — | — | — |
| defect_or_mass_change | joint_fit | 2.757760 | 0.023256 | 1/43 | no_protocol_defined_signal | signal_family_adjusted | 3.763371 |
| defect_or_mass_change | fixed_donor | 2.529373 | 0.023256 | 1/43 | signal | signal_family_adjusted | 3.257857 |

## Language

Unchanged: bundled system replacement as implemented; channels describe how QC coding classified UHIP's failures. The fixed-donor result and the joint-fit result are two pre-specified estimators of the same estimand; neither is "the" answer, and the causal paper reports both with the reproduction check as the bridge.
