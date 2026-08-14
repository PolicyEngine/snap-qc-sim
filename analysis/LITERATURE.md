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
| DellaVigna, Otis & Vivalt, "Forecasting the Results of Experiments: Piloting an Elicitation Strategy", *AEA Papers & Proceedings* 110: 75–79 (2020) — authorship Crossref-verified 2026-08-14 (not Pope) | Registered-report forecasting methodology piloted at JDE | Same as above; the venue precedent for registration-then-results publishing. https://www.aeaweb.org/articles?id=10.1257%2Fpandp.20201080 |
| GAO, "Food Stamp Program: Payment Errors and Trafficking Have Declined despite Increased Program Participation", GAO-07-422T, testimony 2007-01-31 | Pre-2002, states above the national average were sanctioned — about half of states each year; the 2002 Farm Bill moved to liability only at 95% statistical probability of exceeding 105% of the national average for 2 consecutive years, pay-or-reinvest, plus $48M/yr performance bonuses | Full text read (govinfo) 2026-08-14. THE primary source for the 2002 narrowing sentence in @sec-related — and for the observation that the 2002 design priced sampling noise into the liability rule while the 2025 tiers price point estimates. https://www.gao.gov/products/gao-07-422t |
| Goldstein & Spiegelhalter, "League Tables and Their Limitations: Statistical Issues in Comparisons of Institutional Performance", *JRSS-A* 159(3): 385–409 (1996), DOI 10.2307/2983325 | The canonical treatment of ranking institutions under sampling noise: interval estimates, shrinkage, and the instability of league-table positions | Verified 2026-08-14 (Oxford Academic + RePEc + full-text PDFs). Pairs with Kane–Staiger as the second anchor for the tier-persistence rival prediction. https://academic.oup.com/jrsssa/article/159/3/385/7102490 |
| Peeters & Widlak, "The digital cage: Administrative exclusion through information architecture", *Government Information Quarterly* 35(2): 175–183 (2018), DOI 10.1016/j.giq.2018.02.003 | System architecture itself as an administrative-exclusion mechanism (Dutch civil registry case) | Verified 2026-08-14 (Crossref). Frames UHIP/Benefind as members of a documented class for the event-study paper, not one-off anecdotes. |
| Peeters & Widlak, "Administrative exclusion in the infrastructure-level bureaucracy: The case of the Dutch daycare benefit scandal", *Public Administration Review* 83(4): 863–877 (2023), DOI 10.1111/puar.13615 | The consequence side: automated error attribution driving wrongful clawbacks at scale | Verified 2026-08-14 (Crossref). Bib-verified only — read before citing content claims. |
| Press & Tanur, "The Confluence of Sociology, Statistics, and Public Policy in the Quality Control of the Food Stamps, AFDC, and Medicaid Family Assistance Programs", *Evaluation Review* 15(3): 315–332 (1991), DOI 10.1177/0193841x9101500302 | First-party retrospective spanning both CNSTAT QC panels | Verified 2026-08-14 (Crossref). The bridge to the AFDC/Medicaid companion volume (still unlocated — HHS DAB No. 948 (1988) references an NAS AFDC/Medicaid QC study; probe NAP catalog + this paper's references). Bib-verified only — read before citing content claims. |
| Lawsky, "A Logic for Statutes", *Florida Tax Review* 21 (2017), DOI 10.5744/ftr.2017.0002 | Formalizing statutory logic from legal scholarship's side | Verified 2026-08-14 (Crossref; also SSRN 3088206). Queue-4 anchor. |
| Lawsky (co-author), "Coding the Code: Catala and Computationally Accessible Tax Law", *SMU Law Review* 75: 535 (2022), DOI 10.25172/smulr.75.3.4 | Legal-scholarship treatment of the Catala line the paper already cites | Verified 2026-08-14 (Crossref matched Lawsky as author). Confirm full coauthor list before a bib entry. |
| Homonoff & Somerville, "Program Recertification Costs: Evidence from SNAP", *AEJ: Economic Policy* 13(4): 271–298 (2021) | Random assignment of recertification interview dates in San Francisco: late-month dates cut recertification by over 20%, average $600 lost benefits, quarter off SNAP over a year | Anchor for burden-driven churn as an error-process channel; frames Kentucky's Benefind mitigation (6→12-month recertification) as itself error-relevant; source of rival predictions for design 2. https://www.nber.org/papers/w27311 |
| Abadie, "Using Synthetic Controls: Feasibility, Data Requirements, and Methodological Aspects", *Journal of Economic Literature* 59(2): 391–425 (2021) | The methodological survey: where synthetic controls are reliable and where they fail | The formal citation behind the event-study machinery; its reliability conditions are the checklist our Oregon run and the coming RI/KY runs must be argued against. https://www.aeaweb.org/articles?id=10.1257%2Fjel.20191450 |
| Abadie, Diamond & Hainmueller, "Synthetic Control Methods for Comparative Case Studies: Estimating the Effect of California's Tobacco Control Program", *JASA* 105(490): 493–505 (2010) | The canonical single-treated-unit method with placebo-in-space permutation inference | The direct methodological ancestor of the design-1 estimator; permutation inference as implemented is theirs. |

| GAO, *Federal and State Liability for Inaccurate Payments of Food Stamp, AFDC, and SSI Program Benefits* (RCED-84-155, 1984) | Documents the first sanction regime: food stamp error-rate thresholds of 9% (FY1983), 7% (FY1984), 5% (FY1985); state liability tied to federally reimbursed administrative costs; waiver and reinvestment machinery | The direct precedent for cost sharing keyed to noisy error rates — thresholds stepping down while measurement noise stayed put; the NRC 1987 panel is its institutional response, and the paper's OBBBA analysis inherits this lineage. https://gao.justia.com/social-security-administration/1984/4/federal-and-state-liability-for-inaccurate-payments-of-food-stamp-afdc-and-ssi-program-benefits-rced-84-155 |
| DOJ False Claims Act settlements over SNAP QC manipulation (2016–2021): Virginia, Wisconsin, Alaska, Texas ($15M+), Mississippi, Louisiana, Florida ($17.5M), Tennessee ($6.85M); Osnes Consulting ($751,571); $67M+ recovered | A USDA-OIG nationwide audit found third-party consultants advised states to diminish identified QC errors (2008–2013); states and the consultant settled FCA liability | The paper's "documented manipulation history" now cites named federal records rather than a gloss; the bunching design (design 4) has its motivating episode — discretion demonstrably responded to the measurement system. https://www.justice.gov/opa/pr/texas-health-and-human-services-commission-agrees-pay-over-15-million-resolve-false-claims · https://justice.gov/opa/pr/florida-department-children-and-families-agrees-pay-175-million-resolve-false-claims-act · https://www.justice.gov/usao-edwa/pr/consultant-agrees-pay-751571-settle-false-claims-act-liability-alleged-falsification |
| CRS, *Errors and Fraud in the Supplemental Nutrition Assistance Program* (R45147) | The Congressional Research Service synthesis of the error-measurement and manipulation episode | The neutral secondary source tying the QC system, the OIG audit, and the sanction history together for a policy audience. https://www.everycrsreport.com/reports/R45147.html |

## Field map and TO-VERIFY queues

Nothing below may be cited until verified and promoted to the table.

1. **SNAP QC measurement and its history.** Verified: GAO RCED-84-155
   (the first sanction regime), the DOJ FCA settlement cluster and
   Osnes consultant settlement (the manipulation episode's primary
   sources), CRS R45147 (synthesis). Queue: the CNSTAT panel's
   companion volumes; the 2002 Farm Bill sanction redesign's
   legislative analyses (GAO-07-422T now verified and promoted — the
   mechanics; PL 107-171 Title IV and FR 2003-10-16 located, unread); the underlying USDA-OIG audit reports
   themselves; ERS/FNS-commissioned error-rate studies.
2. **Accountability measurement under noise.** Verified:
   Goldstein–Spiegelhalter 1996 (promoted); Kane–Staiger (already
   cited in the paper). Queue: empirical-Bayes shrinkage refinements
   beyond the 1996 treatment if the rival-predictions draft needs
   them.
3. **Administrative burden and churn.** Verified: Homonoff–Somerville.
   Queue: Herd–Moynihan (book; already cited), SNAP takeup and
   enforcement work (NBER SNAP eligibility-enforcement line), sludge
   audits.
4. **Rules as code / computational law.** Verified: Lawsky 2017 and
   the Catala SMU piece (promoted); Merigoux et al. (already cited).
   Queue: OpenFisca lineage papers; verification claims in the govtech
   literature to position the oracle method against.
5. **Public-sector IT implementation failure.** Verified:
   Peeters–Widlak 2018 and 2023 (promoted). Queue: healthcare.gov
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

## Rival predictions — first draft (2026-08-14, verified anchors only)

Statements to commit before any fiscal 2027 outcome publishes; each
rests only on the anchor table above plus this repository's artifacts.

1. **Ranking-stability null (Goldstein–Spiegelhalter; Kane–Staiger).**
   Absent any behavioral response, sampling variation alone reshuffles
   tier positions year to year: the simulator's FY2028 election lens
   already quantifies this repository's version (per-state tier
   probabilities under the no-response null). The rival prediction to
   beat: observed FY2027 tier assignments are statistically
   indistinguishable from draws under the committed no-response nulls.
2. **Burden-response direction (Homonoff–Somerville; Herd–Moynihan).**
   If states respond to cost sharing by tightening verification and
   recertification, participation falls among high-churn cases while
   the measured error direction is ambiguous (fewer active cases to
   err on; more procedural terminations, which QC counts differently
   than payment errors). Distinguishing observable: recertification
   cadence and procedural-denial shares move before measured rates do.
3. **Measurement-side response (NRC 1987; GAO-07-422T; the DOJ
   record).** The 1987 panel's diagnosis and the settlement history
   both predict pressure lands on the measurement pipeline first —
   sampling plans, review practice, arbitration — because that is the
   cheapest margin. Distinguishing observable: cause-mix and
   adjudication-stage shifts (the wedge components) without matching
   movement in file-computable error.

Adjudication protocol: the fiscal 2026 pre-registration's committed
nulls arbitrate 1; 2 and 3 are directional and need the FY2026-27
files plus elections data — state them now, score them when the files
publish.
