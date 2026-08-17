# SMD engine accounting counterfactual

## Recoverability verdict

No: for a case recorded at the state standard, actual allowable expenses are not recoverable. `FSMEDEXP` is the only documented reported medical-expense field, on the allowable-above-$35 scale, and the SMD process replaces values in the qualifying range with the standard. Values above the standard remain usable as actual excess expenses. The standardized class therefore receives a bracket, never a point guess.

The five SMD states among the seven parity-verified states are Arizona, California, Colorado, Georgia, and Texas. Maryland and New York are reported rather than computed because their FY2024 registry amounts are zero.

- Eligible elderly/disabled units with gross medical expenses above $35 and at or below the state threshold receive threshold minus $35; above-threshold units use actual expenses minus $35. (FY-2024-Tech-Doc.pdf, p. 34, lines 19-32).
- The FY2024 SMD-state list includes AZ, CA, CO, GA, and TX but not MD or NY. (FY-2024-Tech-Doc.pdf, p. 23, lines 48-51).
- FSMEDEXP is the reported field for allowable medical expenses in excess of $35. (FY-2024-Tech-Doc.pdf, p. 75, lines 11-14).
- FSMEDDED is the calculated medical deduction and equals nonnegative FSMEDEXP. (FY-2024-Tech-Doc.pdf, p. 74, lines 46-51).
- The table supplies FY2024 thresholds and standard deductions and says above-threshold deductions equal actual expenses minus $35. (FY-2024-Tech-Doc.pdf, p. F-5, lines 4-35).
- The minimodel replaces a positive expense at or below the SMD range with the standard amount. (FY-2024-Tech-Doc.pdf, p. 50, lines 40-51).

The repository feature lane reads `FSMEDEXP` to construct `claims_medical`, `medical_expense_above_floor`, and `med_doc_required`; the last also uses elderly/disabled status and the state-year SMD registry (`analysis/train_error_model.py:529-555, 777-789`). The SMD registry is `~/.cache/axiom-oracles/snap_qc_repo/additional_data/standard_medical_deductions.csv`; `analysis/data/state_bbce.csv` is a different, BBCE-only registry.

## Accounting bracket

Convention (a) sets censored actual allowable expense above $35 equal to the standard deduction, so its delta is zero. Convention (b) sets gross expense to $35 + epsilon, approximated as a $0 whole-dollar deduction. Uncensored above-standard expenses use their recorded actual excess in both conventions.

| State | SMD | Claimants | Censored | Issuance change (a) | Issuance change (b) | Rate change (b) | Changed cases (b) |
|---|---:|---:|---:|---:|---:|---:|---:|
| AZ | Yes | 35 | 30 | $0 | $-4,616,774 | +0.0194 pp | 15 |
| CA | Yes | 28 | 8 | $0 | $-14,321,550 | +0.0128 pp | 7 |
| CO | Yes | 53 | 46 | $0 | $-5,377,123 | +0.0386 pp | 22 |
| GA | Yes | 72 | 58 | $0 | $-14,365,446 | +0.0634 pp | 26 |
| MD | No | — | — | — | — | — | Not computed |
| NY | No | — | — | — | — | — | Not computed |
| TX | Yes | 43 | 19 | $0 | $-11,229,861 | +0.0127 pp | 13 |

The measured-rate effect is mechanical: each state's HWGT-weighted `AMTERR` numerator is held fixed while HWGT-weighted formula issuance changes. Recorded cost-neutrality utility adjustments, all other deductions and inputs, eligibility, and weights are also held fixed. Negative issuance deltas therefore raise the measured dollar-error rate even though error dollars do not change.

## Comparison with the deployed construction

| Construction | Scope | Crossing-rate result | Dollar result |
|---|---|---:|---:|
| Deployed fitted-error model | 53 Colorado cases whose threshold-crossing status flips | -0.060 pp expected crossing rate | approximately -$2 million/year expected error dollars |
| Formula accounting bracket | Recorded elderly/disabled medical-deduction claimants in five verified SMD states | Per-state mechanical measured-rate changes above; convention (a) is zero | Per-state issuance bracket above |

These are two accounting constructions of one lever; neither is causal. The formula construction asks how recorded-case benefit arithmetic changes when the standardized deduction is replaced under explicit recoverability bounds. The deployed statistical construction re-predicts adjudication behavior after changing a fitted documentation proxy. They answer different questions, and neither validates the other.

## Reproduction and disclosures

Run `~/.cache/axiom-oracles/snap-fy27/rung3-env/bin/python analysis/smd_engine_counterfactual.py` for the artifact, then `uv run --frozen --extra dev --extra analysis pytest -q`, `uv run --frozen --extra dev --extra analysis ruff check .`, and `git diff --check`. The engine run took 78.53 seconds. The JSON records exact input hashes, versions, per-case deltas, every data-forced choice, and the complete bracket definitions.
