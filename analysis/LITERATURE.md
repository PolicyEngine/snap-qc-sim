# Literature review — verified anchors and the questions each field must answer

Status: living document, started 2026-08-13; developments section
added 2026-10-24. Discipline: a work enters
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

## Developments since 2026-08-14 (verified 2026-10-24)

Policy, state-law, and tool developments after the anchor table was
built. Same discipline: each row was read at the primary source linked
in it; claims seen only in secondary coverage sit in queue 9 below.

| Work | Verified claim | Bears on |
|---|---|---|
| USDA, *Supplemental Nutrition Assistance Program: Payment Error Rates, Fiscal Year 2025* (dated 2026-06-24) | National rate 10.62% (overpayments 9.28%, underpayments 1.33%); QC tolerance threshold $57 | The simulator's locked FY2025 rates. All 53 `official_fy2025` values and `national.fy2025` in `app/public/data.json` match the table to two decimals (differential check run 2026-10-24). https://www.fns.usda.gov/sites/default/files/resource-files/snap-qcfy25-per.pdf |
| S. 5526, *Agricultural Act of 2026* (Boozman) | Original measure reported by Senate Agriculture on 2026-09-24 without written report; placed on the Senate calendar under General Orders (Calendar No. 683). Congress.gov lists no later action as of 2026-10-24 | Status record: pending, not enacted. https://www.congress.gov/bill/119th-congress/senate-bill/5526/all-actions |
| CRS, *Senate Committee Reports a Farm Bill That Would Delay Onset of States Sharing SNAP Benefit Costs* (IN12723, updated 2026-10-05) | S. 5526 would start benefit cost sharing in FY2029, keyed to the lower of the FY2026 or FY2027 rate; delay to FY2030 states at 13.33% or higher in both FY2025 and FY2026; and raise the top share from 15% to 20% from FY2031. The House-passed H.R. 7567 keeps current law. USDA has issued no regulations or guidance, and CRS's figure assumes cost sharing keys to the point estimate | The statute the simulator encodes could change before the first bill: the election pair moves from {FY2025, FY2026} to {FY2026, FY2027}, the delay test becomes a two-year conjunction, and a 20% tier enters. CRS's point-estimate assumption is the open implementation question the tier-lottery argument addresses. https://www.everycrsreport.com/reports/IN12723.html |
| Bergh & Rosenbaum (CBPP), "New Data Underscore SNAP Cost Shift's Harm to Low-Income Families and State Budgets" (2026-07-23) | On FY2025 point estimates: 9 states and the Virgin Islands below 6%; 6 states at 5%; 16 at 10%; 13 and Guam at 15%; 6 states and DC delayed. About $9 billion shifts to states in FY2028, priced on annualized first-half FY2026 issuance. New Jersey fell from 14.33% to 6.86%, leaving the delay group for a 5% share | Independent cross-check: CBPP's delay roster (AK, DE, DC, GA, IL, NM, OR) and New York at 13.18% match the paper's. The simulator prices on FY2024 issuance (`analysis/INTERVENTIONS.md`) and reports expectations over tier odds, so reconcile issuance bases before setting CBPP's $9 billion beside the paper's summed expected bill. https://www.cbpp.org/sites/default/files/7-23-26fa.pdf |
| Corinth (AEI COSM), "How Fixing SNAP's Payment Error Rate Formula Would Change State Cost Shares" (2026-08-19) | The rate divides error dollars by benefits paid, so an overpayment also enlarges the denominator. For a household eligible for $300, a $400 payment scores 0.25 and a $200 payment 0.50; dividing by correctly computed benefits scores both 0.33. Approximated from published FY2025 figures, every state's rate rises (0.04–5.09pp) and 16 states' FY2028 shares change, 7 of them by crossing 13.33% into the delay | A definitional sensitivity separate from sampling noise, with a perverse sign at the delay cliff: the stricter definition lowers FY2028 state bills by a net $2.70 billion. The worked example and the approximation (corrected rate = rate / (1 − over + under)) were checked by hand. The simulator encodes the statutory definition; a definitional lens is a candidate extension. https://cosm.aei.org/how-fixing-snaps-payment-error-rate-formula-would-change-state-cost-shares/ |
| North Carolina S.L. 2026-41 (S.B. 257), §9J.14, approved 2026-07-07, creating G.S. 108A-52.2 | Passes any state benefit cost share to counties by withholding sales-tax distributions. Each county pays a flat 0.75% of its base-year sales-tax allocation plus a proportional assessment scaled by its "penalty factor", its portion of the statewide PER dollar amount. §9J.14(b) writes the FY2028 election into statute: FY2025 unless FY2026 yields a lesser obligation. Nickodem (UNC SOG, 2026-08-17) puts the FY2025 rate at 7.36% and the FY2028 share at about $150 million | The first verified sub-state pass-through, and a second measurement layer. The statute does not say how PER dollars are attributed to counties; if from QC cases, the repo's FY2024 NC file has 955 cases and 127 with errors across 100 counties, so the tier lottery recurs at the county level on one or two error cases each. The statutory election matches the simulator's minimum-obligation election semantics. https://www.ncleg.gov/EnactedLegislation/SessionLaws/PDF/2025-2026/SL2026-41.pdf · https://canons.sog.unc.edu/blog/2026/08/17/state-appropriations-act-shifts-potential-federal-snap-benefit-cost-sharing-to-north-carolina-counties/ |
| McClurg, SNAP payment error rate tool (released 2026-06-24) | State liabilities from point estimates on FY2023 issuance, with timeliness and PAI correlations and CAPER profiles; no sampling uncertainty, election, or delay modeling | The nearest public tool. Its gaps mark the simulator's distinct contribution: tier odds under sampling and process noise, and the election and delay semantics. https://snap-per.joelmcclurg.ai |

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
6. **Fiscal federalism and intergovernmental penalties.** Verified:
   North Carolina's county pass-through (G.S. 108A-52.2). Queue:
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
9. **Implementation and state responses (opened 2026-10-24).**
   Verified: the developments table above. Queue: FFIS's reported
   roughly $9.4 billion annual cost-shift estimate (seen only in
   secondary coverage); Illinois DHS's "up to $80 million" against the
   Civic Federation's roughly $550 million on a 14.67% FY2025 rate that
   qualifies for the delay; APHSA's survey of state root-cause work;
   any USDA implementation guidance (none as of IN12723, 2026-10-05);
   NC DHHS's county attribution method and its first report (due
   2027-02-01); other states' pass-through or appropriation statutes;
   Corinth's companion piece, "SNAP's New Cost Share Requirement Is a
   Blunt but Necessary Tool".

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

4. **Sub-state pass-through (G.S. 108A-52.2; added 2026-10-24).**
   Where a state bills counties by attributed error dollars,
   prediction 3's measurement-side pressure gains a county margin:
   county agencies have a direct budget stake in how QC errors are
   attributed and contested. Distinguishing observable: in North
   Carolina, county QC practice and attribution disputes change after
   the first assessments; the statute's annual DHHS report on
   assessment amounts by county (due each February 1) supplies the
   county series to read them against.

Adjudication protocol: the fiscal 2026 pre-registration's committed
nulls arbitrate 1; 2 and 3 are directional and need the FY2026-27
files plus elections data — state them now, score them when the files
publish.
