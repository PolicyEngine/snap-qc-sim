# Literature review — verified anchors and the questions each field must answer

Status: living document, started 2026-08-13. Discipline: a work enters
the VERIFIED table only after its existence, venue, and claim were
confirmed against a primary source this session (link recorded); the
TO-VERIFY queues hold candidate works named from memory, which MUST NOT
be cited anywhere until promoted. This file feeds three artifacts: the
main paper's related-work coverage, the pre-registration note's novelty
framing, and the system-migrations event-study paper.

## Why write it as a paper section

Four questions our claims have so far skipped, which a real related-work
treatment forces:

1. **History.** Cost sharing under noisy QC measurement has a
   1980s precedent era — sanction disputes, GAO reviews, and a National
   Academies panel that redesigned the system. Engaging it either
   strengthens or corrects the tier-lottery framing.
2. **Novelty of the pre-registration note.** Forecast collection before
   results exists in economics (DellaVigna–Pope line). The note's claim
   must be the precise one: model-derived, hash-pinned predictions for
   a statutory regime, committed to a public repository before the
   outcome year closes — not expert elicitation for experiments.
3. **Imported identification lessons.** Small-N synthetic control,
   implementation-failure studies, and the SNAP churn literature carry
   design lessons our event studies should inherit, not rediscover.
4. **Rival predictions.** The burden literature implies directional
   predictions for the OBBBA regime; stating them makes our
   pre-registered nulls informative.

## Verified anchors

| Work | Verified claim | Bears on |
|---|---|---|
| National Research Council, *Rethinking Quality Control: A New System for the Food Stamp Program* (National Academies Press, 1987; catalog 18900) | A CNSTAT panel reviewed and proposed redesigning the food stamp QC system in the sanction-dispute era | The tier-lottery argument has a direct institutional ancestor; the paper should engage what the panel proposed and what survived into today's system. https://nap.nationalacademies.org/catalog/18900/ |
| GAO, *Food Stamp Program: Error Rate Adjustments and Sanctions* (report to House Agriculture subcommittee; HathiTrust 011421420) | GAO reviewed the error-rate adjustment and sanction machinery in the earlier regime | Primary-source record of the first sanctions era; pair with the 2002 Farm Bill revision that narrowed penalties to persistently high-error states. https://catalog.hathitrust.org/Record/011421420 |
| DellaVigna & Pope, "Predicting Experimental Results: Who Knows What?", *Journal of Political Economy* 126(6): 2410–2456 (2018) | Collected 314 academics' forecasts of 18 experimental treatments before results; average forecast beat 96% of individuals | The pre-registration note's novelty must be stated against this line (and its JDE registered-report extension): our contribution is model-derived regime predictions with hash pins, not expert elicitation. https://www.journals.uchicago.edu/doi/10.1086/699976 |
| DellaVigna, Pope et al., "Forecasting the Results of Experiments: Piloting an Elicitation Strategy", *AEA Papers & Proceedings* 110 (2020) | Registered-report forecasting methodology piloted at JDE | Same as above; the venue precedent for registration-then-results publishing. https://www.aeaweb.org/articles?id=10.1257%2Fpandp.20201080 |
| Homonoff & Somerville, "Program Recertification Costs: Evidence from SNAP", *AEJ: Economic Policy* 13(4): 271–298 (2021) | Random assignment of recertification interview dates in San Francisco: late-month dates cut recertification by over 20%, average $600 lost benefits, quarter off SNAP over a year | Anchor for burden-driven churn as an error-process channel; frames Kentucky's Benefind mitigation (6→12-month recertification) as itself error-relevant; source of rival predictions for design 2. https://www.nber.org/papers/w27311 |
| Abadie, "Using Synthetic Controls: Feasibility, Data Requirements, and Methodological Aspects", *Journal of Economic Literature* 59(2): 391–425 (2021) | The methodological survey: where synthetic controls are reliable and where they fail | The formal citation behind the event-study machinery; its reliability conditions are the checklist our Oregon run and the coming RI/KY runs must be argued against. https://www.aeaweb.org/articles?id=10.1257%2Fjel.20191450 |
| Abadie, Diamond & Hainmueller, "Synthetic Control Methods for Comparative Case Studies: Estimating the Effect of California's Tobacco Control Program", *JASA* 105(490): 493–505 (2010) | The canonical single-treated-unit method with placebo-in-space permutation inference | The direct methodological ancestor of the design-1 estimator; permutation inference as implemented is theirs. |

## Field map and TO-VERIFY queues

Nothing below may be cited until verified and promoted to the table.

1. **SNAP QC measurement and its history.** Queue: the CNSTAT panel's
   companion volumes; the 2002 Farm Bill sanction redesign's
   legislative analyses; state-vs-USDA QC litigation of the 1980s-90s;
   ERS/FNS-commissioned error-rate studies; the 2010s payment-accuracy
   controversy (states' QC vendor practices and the resulting OIG
   work — likely the paper's "documented manipulation history" has
   OIG/DOJ primary sources worth citing directly).
2. **Accountability measurement under noise.** Verified adjacent:
   Kane–Staiger (already cited in the paper). Queue: hospital
   report-card and school value-added ranking-stability literature;
   empirical-Bayes shrinkage in performance rankings.
3. **Administrative burden and churn.** Verified: Homonoff–Somerville.
   Queue: Herd–Moynihan (book; already cited), SNAP takeup and
   enforcement work (NBER SNAP eligibility-enforcement line), sludge
   audits.
4. **Rules as code / computational law.** Verified adjacent: Merigoux
   et al. (already cited). Queue: OpenFisca lineage papers; Lawsky on
   formalizing tax law; verification claims in the govtech literature
   to position the oracle method against.
5. **Public-sector IT implementation failure.** Queue: Dutch
   casework-automation literature (Peeters/Widlak line); healthcare.gov
   retrospectives; GAO IT-modernization high-risk series; academic
   post-mortems of UHIP/Benefind if any exist beyond press.
6. **Fiscal federalism and intergovernmental penalties.** Queue:
   Medicaid FMAP incentive literature; TANF penalty design; UI
   administrative-funding incentives — the cross-program frame for
   what error-rate-keyed cost shares do.
7. **Pre-registration and forecasting in policy.** Verified:
   DellaVigna–Pope line. Queue: registered-reports methodology
   statements; adversarial-collaboration precedents; prediction
   platforms for policy outcomes.
8. **Small-N event studies and synthetic control.** Verified: Abadie
   JEL 2021 survey; Abadie–Diamond–Hainmueller JASA 2010. Queue:
   inference refinements (conformal/placebo-based) if the RI/KY runs
   need them.

## Rival predictions to state before fiscal 2027 outcomes

To be drafted against verified sources only: what burden theory
predicts states do under cost sharing (tighten verification →
churn up, takeup down, measured error direction ambiguous); what the
1987 panel's diagnosis implies about measurement-side responses; what
the ranking-stability literature implies about year-to-year tier
persistence absent any behavioral response.
