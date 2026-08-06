# v2 stage 1-3 first results (2026-08-05)

Six-year QC stack (FY2017-19 + 2022-23 train, n=217,693; FY2024 holdout,
n=44,891; pandemic years excluded). SMD regime registry: 21 pre-2020
states (Health Affairs 2023), tech-doc lists FY2021-24; documented
adopters Michigan (by FY2021), Arizona (FY2022), Louisiana (FY2023),
Kentucky (FY2024). `model_results.json` carries the metrics.

## 1. Holdout lift is real and comes from computation position

Covariates-only AUC 0.7397 → with intermediates 0.7632 (+0.024; PR-AUC
+0.010). Permutation importance says the lift is carried by
computation-position features — net_share_of_gross dominates (+0.024),
then ben_rel_max — not by documentation burdens. Where a case sits in the
benefit formula predicts error risk; this is also exactly the feature
family a rules engine computes best (and, in v2 proper, under
counterfactual policies).

## 2. The documentation-burden channel is confounded cross-sectionally —
##    which is the argument FOR the natural-experiment design

Among elderly/disabled medical claimants, medical-element error rates are
HIGHER where documentation is not required (SMD states, 6.9%) than where
it is (non-SMD, 4.5%). Backward from the hypothesis — and expected:
states adopted the SMD demonstration because they had medical-deduction
error problems (treatment assigned on the outcome), SMD raises claiming
(more marginal claimants), and the SMD has its own error modes (wrong
standard applied). Cross-sectional comparisons cannot identify this
channel; within-state adoption changes can.

## 3. Adoption DiD (medical-element errors, elderly/disabled claimants)

Never-adopter trend pre→FY2024: −0.7pp. Against it:
- Kentucky (adopted FY2024): 8.2% → 2.1%, DiD −5.3pp
- Louisiana (FY2023): 6.0% → 4.3%, DiD −1.0pp
- Arizona (FY2022): 1.6% → 3.7%, DiD +2.8pp

Two of three supportive, Kentucky strongly; Arizona contrary. Cell sizes
are small (42-105 claimants). Candidate explanations for Arizona worth
testing: SMD amount relative to the Medicare Part B premium (an SMD below
the premium binds for almost no one and adds a misapplication error mode),
FY2022-23 unwinding turbulence, and post-adoption claimant composition.

## Next

- Add FY2020-21 files for the Michigan adoption and more pre-period.
- Composition-adjust the DiD (reweight post-adoption claimants to
  pre-adoption characteristics).
- SMD size vs Part B premium as a moderator (per-state SMD amounts:
  FRAC appendix).
- Category-specific models (P(medical-element error)) rather than pooled.
- This is the collaboration surface with the giannella/snap_qc modeling
  program: their machinery, these features, shared natural experiments.
