# Literature review — verified anchors and the questions each field must answer

Status: living document, started 2026-08-13; developments section
added 2026-10-24; October queue sweep added and status rows refreshed
2026-11-18. Discipline: a work enters
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

## Developments since 2026-08-14 (verified 2026-10-24; status rows refreshed 2026-11-18)

Policy, state-law, and tool developments after the anchor table was
built. Same discipline: each row was read at the primary source linked
in it; claims seen only in secondary coverage sit in queue 9 below.

| Work | Verified claim | Bears on |
|---|---|---|
| USDA, *Supplemental Nutrition Assistance Program: Payment Error Rates, Fiscal Year 2025* (dated 2026-06-24) | National rate 10.62% (overpayments 9.28%, underpayments 1.33%); QC tolerance threshold $57 | The simulator's locked FY2025 rates. All 53 `official_fy2025` values and `national.fy2025` in `app/public/data.json` match the table to two decimals (differential check run 2026-10-24). https://www.fns.usda.gov/sites/default/files/resource-files/snap-qcfy25-per.pdf |
| S. 5526, *Agricultural Act of 2026* (Boozman) | Original measure reported by Senate Agriculture on 2026-09-24 without written report; placed on the Senate calendar under General Orders (Calendar No. 683). Congress.gov lists no later action as of 2026-11-18, and one CBO cost estimate (not yet read) | Status record: pending, not enacted. https://www.congress.gov/bill/119th-congress/senate-bill/5526/all-actions |
| CRS, *Senate Committee Reports a Farm Bill That Would Delay Onset of States Sharing SNAP Benefit Costs* (IN12723, updated 2026-10-05; still the current version on 2026-11-18) | S. 5526 would start benefit cost sharing in FY2029, keyed to the lower of the FY2026 or FY2027 rate; delay to FY2030 states at 13.33% or higher in both FY2025 and FY2026; and raise the top share from 15% to 20% from FY2031. The House-passed H.R. 7567 keeps current law. USDA has issued no regulations or guidance, and CRS's figure assumes cost sharing keys to the point estimate | The statute the simulator encodes could change before the first bill: the election pair moves from {FY2025, FY2026} to {FY2026, FY2027}, the delay test becomes a two-year conjunction, and a 20% tier enters. CRS's point-estimate assumption is the open implementation question the tier-lottery argument addresses. https://www.everycrsreport.com/reports/IN12723.html |
| Bergh & Rosenbaum (CBPP), "New Data Underscore SNAP Cost Shift's Harm to Low-Income Families and State Budgets" (2026-07-23) | On FY2025 point estimates: 9 states and the Virgin Islands below 6%; 6 states at 5%; 16 at 10%; 13 and Guam at 15%; 6 states and DC delayed. About $9 billion shifts to states in FY2028, priced on annualized first-half FY2026 issuance. New Jersey fell from 14.33% to 6.86%, leaving the delay group for a 5% share | Independent cross-check: CBPP's delay roster (AK, DE, DC, GA, IL, NM, OR) and New York at 13.18% match the paper's. The simulator prices on FY2024 issuance (`analysis/INTERVENTIONS.md`) and reports expectations over tier odds, so reconcile issuance bases before setting CBPP's $9 billion beside the paper's summed expected bill. https://www.cbpp.org/sites/default/files/7-23-26fa.pdf |
| Corinth (AEI COSM), "How Fixing SNAP's Payment Error Rate Formula Would Change State Cost Shares" (2026-08-19) | The rate divides error dollars by benefits paid, so an overpayment also enlarges the denominator. For a household eligible for $300, a $400 payment scores 0.25 and a $200 payment 0.50; dividing by correctly computed benefits scores both 0.33. Approximated from published FY2025 figures, every state's rate rises (0.04–5.09pp) and 16 states' FY2028 shares change, 7 of them by crossing 13.33% into the delay | A definitional sensitivity separate from sampling noise, with a perverse sign at the delay cliff: the stricter definition lowers FY2028 state bills by a net $2.70 billion. The worked example and the approximation (corrected rate = rate / (1 − over + under)) were checked by hand. The simulator encodes the statutory definition; a definitional lens is a candidate extension. https://cosm.aei.org/how-fixing-snaps-payment-error-rate-formula-would-change-state-cost-shares/ |
| North Carolina S.L. 2026-41 (S.B. 257), §9J.14, approved 2026-07-07, creating G.S. 108A-52.2 | Passes any state benefit cost share to counties by withholding sales-tax distributions. Each county pays a flat 0.75% of its base-year sales-tax allocation plus a proportional assessment scaled by its "penalty factor", its portion of the statewide PER dollar amount. §9J.14(b) writes the FY2028 election into statute: FY2025 unless FY2026 yields a lesser obligation. Nickodem (UNC SOG, 2026-08-17) puts the FY2025 rate at 7.36% and the FY2028 share at about $150 million | The first verified sub-state pass-through, and a second measurement layer. The statute does not say how PER dollars are attributed to counties; if from QC cases, the repo's FY2024 NC file has 955 cases and 127 with errors across 100 counties, so the tier lottery recurs at the county level on one or two error cases each. The statutory election matches the simulator's minimum-obligation election semantics. https://www.ncleg.gov/EnactedLegislation/SessionLaws/PDF/2025-2026/SL2026-41.pdf · https://canons.sog.unc.edu/blog/2026/08/17/state-appropriations-act-shifts-potential-federal-snap-benefit-cost-sharing-to-north-carolina-counties/ |
| McClurg, SNAP payment error rate tool (released 2026-06-24) | State liabilities from point estimates on FY2023 issuance, with timeliness and PAI correlations and CAPER profiles; no sampling uncertainty, election, or delay modeling | A nearby public tool. Correction (2026-11-18): this row first called tier odds under sampling noise the simulator's distinct contribution, but Bauer and Schanzenbach (Brookings, 2026-08-25, Appendix B) already compute one-year tier odds from published FY2023 rates and standard errors (sweep table below). Brookings' fifth bin is the 13.33% delay threshold, but each of its probabilities is for a single year. What remains distinct from both: resampling QC cases instead of drawing from published standard errors; the two-year structure of the FY2028 election and delay test; and the pre-registration's committed drift variants. The drift variants matter because the repo's backtest finds sampling-only nominal 90% intervals cover 48% of realized next-year rates (`analysis/PERSISTENCE_BACKTEST.md`, reconstructed-rate scale). https://snap-per.joelmcclurg.ai |

## October 2026 queue sweep (verified 2026-10-25; checked 2026-11-18)

Four Subfleet review lanes worked the open queues on 2026-10-25 under
this file's discipline: lane A took queues 1 and 3, lane B queues 5 and
6, lane C queues 7 and 8, and lane D ran a 2025–26 novelty and
competitor scan. The rows below condense their reports. On 2026-11-18
every DOI was re-checked against Crossref or DataCite, and a script
requested the 91 links in this section as committed: 57 opened and 34
refused automated clients or redirected without opening (GAO, CBPP,
CBO and most journal publishers). Earlier browser spot-checks of a
sample of refused links opened. None returned 404; the one dead lane
URL, the RI Auditor General's report, is noted in its row without a
link. Rows marked † were re-read at the primary source during
integration. Apart from Herd & Moynihan (`herd2018burden`), none of
these works is cited in `paper/references.bib` or
`paper-causal/references.bib` on origin/main as of 2026-11-18. Before
either paper rests a sentence on an unmarked row, re-open the source.

### Queue 1: SNAP QC measurement and its history

| Work | Verified claim | Bears on |
|---|---|---|
| National Research Council, *From Quality Control to Quality Improvement in AFDC and Medicaid: Summary and Recommendations*, F. D. Kramer, ed. (National Academy Press, 1988). [NAP catalog 19102](https://nap.nationalacademies.org/catalog/19102/from-quality-control-to-quality-improvement-in-afdc-and-medicaid) | Bibliographic only: title, editor, year and a 25-page summary. The scanned contents were unreadable, and the DOI the lane recorded (10.17226/19102) did not resolve on 2026-11-18 | The AFDC/Medicaid companion volume the Press–Tanur anchor row was looking for. Its recommendations remain unread |
| Hand, "A Resampling Analysis of Federal Family Assistance Program Quality Control Data: An Application of the Bootstrap", *Evaluation Review* 14(4): 391–410 (1990), DOI [10.1177/0193841X9001400404](https://journals.sagepub.com/doi/10.1177/0193841X9001400404) † | Bootstraps Oregon Food Stamp QC data to study the regression estimator's efficiency when its assumptions fail. Abstract and references only; the numerical results were not accessible | Bootstrapping SNAP QC data dates to 1990. What the simulator adds is carrying resampled rates through the statutory tiers |
| HHS Departmental Grant Appeals Board, *FY 1981 Medicaid Quality Control Disallowances*, Decision No. 948 (1988-04-18). [Full text](https://www.hhs.gov/sites/default/files/static/dab/decisions/board-decisions/1988/dab948.html) | Remands excess-resource error calculations, separating legal ineligibility from avoidable program loss. Footnote 8 cites the NAS AFDC/Medicaid study (ch. 7, p. 44) | Rival prediction 3: a case where adjudicating how errors are valued changed fiscal liability without changing the eligibility finding. Legitimate adjudication, not manipulation |
| Matt & Cook, "The War on Fraud and Error in the Food Stamp Program: An Evaluation of Its Effects in the Carter and Reagan Administrations", *Evaluation Review* 17(1): 4–26 (1993), DOI [10.1177/0193841X9301700102](https://journals.sagepub.com/doi/10.1177/0193841X9301700102) | From the abstract: payment accuracy and eligible participation improved together under Carter, while the first Reagan administration's fall in overpaid cases came with falling eligible participation | Rival prediction 2: an early precedent for scoring accuracy and access together. Observational |
| P.L. 107-171 §4118, *Farm Security and Rural Investment Act of 2002*, 116 Stat. 317–319. [Enacted text](https://www.govinfo.gov/content/pkg/PLAW-107publ171/pdf/PLAW-107publ171.pdf) † | From FY2004, liability attaches when there is a 95% statistical probability that a state's rate exceeds 105% of the national performance measure, for a second or subsequent consecutive year. Amount: allotments × (rate − 6%) × 10%. The Secretary may waive it, require up to 50% as new investment with no federal match, or designate up to 50% at risk, payable if liability is established the next year | Replaces the reliance on GAO-07-422T's summary with the enacted formula, and separates establishing liability from collecting it |
| FNS, "Food Stamp Program: Non-Discretionary Quality Control Provisions of Title IV of Public Law 107-171", interim rule, 68 FR 59519–59524 (2003-10-16). [Full text](https://www.govinfo.gov/content/pkg/FR-2003-10-16/pdf/03-26176.pdf) | FY2003 is the first comparison year, and the national measure is weighted by issuance. Implements waiver, reinvestment and conditional collection. Corrective action applies at rates of 6% or more, separately from liability | "Pay or reinvest" understates the 2002 mechanics |
| USDA OIG, *FNS Quality Control Process for SNAP Error Rate*, Audit 27601-0002-41 (2015-09-23). [Full text](https://www.oig.usda.gov/sites/default/files/reports/2025-09/27601-0002-41.pdf) | In eight purposively chosen states: selective scrutiny of error cases, inconsistent income averaging, offsetting deductions, and review committees reducing reported errors. Renews the NRC call for one-tier federal review. No population projections; FNS disputed attribution and generalization | Read with the DOJ settlement row. Lane A warns against equating its eight audited states with the settlement states; no one has compared the lists. Supplies mechanisms for rival prediction 3, not their timing |
| McGill, Thorn, Trippe, Tadler & Tucker, *Enhancing SNAP Quality Control Completion Rates: Final Report* (Insight Policy Research for FNS, 2016-01). [Full text](https://www.govinfo.gov/content/pkg/GOVPUB-A98-PURL-gpo144508/pdf/GOVPUB-A98-PURL-gpo144508.pdf) | Respondents describe pressure to leave potentially erroneous reviews incomplete. Independent reviewers completed 11 of 64 incomplete cases, and 3 had overpayments. The authors reject national conclusions from so small a sample | Which cases reach a completed review is itself a measurement margin. Track incomplete dispositions alongside adjudicated errors |
| USDA OIG, *Semiannual Report to Congress*, No. 80, FY2018 second half (2018-11). [Full text](https://www.oig.usda.gov/sites/default/files/reports/2026-07/sarc2018_2nd_half_508.pdf) | Recommendations 1 and 11 of the 2015 audit were still awaiting final action | Recommendation tracking, not a new audit |
| Mills, Laliberty & Rodger, *Food Stamp Certification Periods and Payment Accuracy: State Experience During 1997–2001*, ERS E-FAN-04-012 (2004-11). [Full text](https://ers.usda.gov/sites/default/files/_laserfiche/publications/43574/33355_efan04012.pdf) | A QC-based Markov model predicts lower participation from more frequent recertification of earnings cases. The case error-rate response flips sign across base years. Simulations, not causal estimates | Rival prediction 2's pairing of falling participation with an ambiguous error direction has a 2004 modeling ancestor |
| Logan, Rhodes & Sabia, *Food Stamp Program Costs and Error Rates, 1989–2001*, ERS CCR-15 (2006-01). [Full text](https://ers.usda.gov/sites/default/files/_laserfiche/publications/86030/CCR-15.pdf) | Models administrative effort against an index combining positive and negative case errors. Cost measurement is inconsistent, and automation effects could not be isolated | Earlier QC-based production research. Motivates using concrete system events over spending proxies |
| Logan, Kling & Rhodes, *Food Stamp Program Certification Costs and Errors, 1989–2005*, ERS CCR-45 (2008-06). [Full text](https://www.govinfo.gov/content/pkg/GOVPUB-A93-PURL-gpo16513/pdf/GOVPUB-A93-PURL-gpo16513.pdf) | Short certification periods and simplification both go with a lower composite error index (not official dollar rates). Automation spending failed as a proxy; the report proposes studying specific automation changes | Accuracy gains need not raise household burden. Supports the events paper's system-migration design |
| McGill, Thorn, Cody, Wagner, Ramaswamy & Cunnyngham, *Feasibility of Revising the SNAP Quality Control Review Process* (Insight Policy Research for FNS, 2019-12), Appendix F. [Full text](https://fns-prod.azureedge.us/sites/default/files/resource-files/SNAPQC_Feasibility.pdf) † | Draws 200 replicate files per sample-reduction scenario from 2016 QC data and finds substantial added state-level uncertainty. The estimator uses weighted household error proportions, so it measures the uncertainty that smaller samples add, not total uncertainty in the dollar rate | A second QC-resampling predecessor, from inside FNS |

### Queue 3: administrative burden and churn

| Work | Verified claim | Bears on |
|---|---|---|
| Herd & Moynihan, *Administrative Burden: Policymaking by Other Means* (Russell Sage, 2018; Crossref lists 2019), DOI [10.7758/9781610448789](https://doi.org/10.7758/9781610448789) | Chapter 6, on cycles of burden in SNAP, runs pp. 143–164. The introduction lays out the learning, compliance and psychological cost framework | Confirms the bibliography's 2018 year and locates the SNAP chapter. Chapter text unread |
| Giannella, Homonoff, Rino & Somerville, "Administrative Burden and Procedural Denials: Experimental Evidence from SNAP", *AEJ: Economic Policy* 16(4): 316–340 (2024), DOI [10.1257/pol.20220701](https://www.aeaweb.org/articles?id=10.1257/pol.20220701) | In a Los Angeles experiment with about 65,000 applicants, flexible applicant-initiated interviews raised approvals by 6pp and longer-run participation by more than 2pp. The interview was still required | Rival prediction 2: procedural flexibility differs from dropping verification |
| Finkelstein & Notowidigdo, "Take-Up and Targeting: Experimental Evidence from SNAP", *QJE* 134(3): 1505–1556 (2019), DOI [10.1093/qje/qjz013](https://doi.org/10.1093/qje/qjz013) | Among about 30,000 likely-eligible older nonparticipants, nine-month enrollment was 6% for controls, 11% with information and 18% with information plus assistance. Marginal enrollees had higher incomes and were less sick | Participation and the composition of who participates need separate predictions |
| Unrath, *Targeting, Screening, and Retention: Evidence from the Supplemental Nutrition Assistance Program in California*, working paper (2024-03). [Manuscript](https://mattunrath.github.io/files/research/Unrath_SNAP.pdf) | Moving from quarterly to semiannual reporting raised six-month retention by more than 11%, disproportionately among households predicted to be less food insecure. The welfare analysis still favors less frequent verification | Kentucky's recertification change may move retention, targeting and cost differently. Working paper |
| Sunstein, "Sludge Audits", *Behavioural Public Policy* 6(4): 654–673 (issue 2022; online 2020-01-06), DOI [10.1017/bpp.2019.32](https://doi.org/10.1017/bpp.2019.32) | From the abstract: proposes regular audits of excessive or unjustified procedural frictions | An established audit concept. No SNAP rate effect |
| OECD, *Fixing Frictions: "Sludge Audits" around the World*, Public Governance Policy Paper 48 (2024-06-12), DOI [10.1787/5e9bb35c-en](https://www.oecd.org/en/publications/fixing-frictions-sludge-audits-around-the-world_5e9bb35c-en.html) | Ten case studies and nine practice principles. New South Wales maps steps, waiting, effort and inclusion without one aggregate score, and treats justified eligibility checks as legitimate | Burden measurement beyond payment errors |
| Sunstein & Gosset, "Optimal Sludge? The Price of Program Integrity", *Duke Law Journal Online* 70: 74–90 (2020). [Record](https://scholarship.law.duke.edu/dlj_online/74/) | From the abstract: eligibility requirements screen out eligible as well as ineligible applicants; reviews competing normative approaches and a pilot survey | The access–integrity tradeoff predates OBBBA |
| Wu & Meyer, "Certification and Recertification in Welfare Programs: What Happens When Automation Goes Wrong?", *AEJ: Economic Policy*, forthcoming; NBER WP 31437 (2023). [AEA record](https://www.aeaweb.org/articles?id=10.1257/pol.20250309) † | From October 2007, Indiana rolled out IBM's automated processing of applications and recertifications in three county waves, reaching 59 of 92 counties before the rollout halted in January 2009. The system automated caseworker assistance, and the state kept final eligibility determinations. Four quarters after rollout, treated counties had 15% fewer SNAP individuals. Needier recipients exited at recertification, while less needy applicants were screened out at entry. Appendix Figure A8 shows, descriptively, Indiana's QC overpayment rate falling sharply after 2008 relative to the U.S. The AEA page lists DOI 10.1257/pol.20250309, which was not yet registered on 2026-11-18 | The events paper's closest predecessor on automated welfare processing and participation, and it already charts QC overpayment trends. The events paper's synthetic-control estimates on QC outcomes and its decomposition remain distinct |
| Cook, Cox & East, "SNAP Work Requirements, Administrative Burden, and Procedural Denials", *AEA Papers and Proceedings* 116: 309–313 (2026), DOI [10.1257/pandp.20261086](https://www.aeaweb.org/articles?id=10.1257/pandp.20261086) | In one state's administrative data, removing ABAWD work requirements reduced procedural denials | Procedural denials as an observable for rival prediction 2 |

### Queue 5: public-sector IT implementation failure

| Work | Verified claim | Bears on |
|---|---|---|
| GAO-14-694, *Healthcare.gov: Ineffective Planning and Oversight Practices Underscore the Need for Improved Contract Management* (2014-07-30). [Record](https://www.gao.gov/products/gao-14-694) | CMS began procurement before key requirements were known, skipped acquisition planning, postponed readiness reviews and launched without verifying performance requirements | Governance and procurement mechanisms. No SNAP rate estimate |
| GAO-15-238, *Healthcare.gov: CMS Has Taken Steps to Address Problems, but Needs to Further Implement Systems Development Best Practices* (2015-03-04). [Record](https://www.gao.gov/products/gao-15-238) | Inadequate capacity planning, coding errors and missing functionality at launch, with weak requirements traceability, testing and schedules | Separates rule computation from capacity and integration failures |
| HHS OIG, *HealthCare.gov: Case Study of CMS Management of the Federal Marketplace*, OEI-06-14-00350 (2016-02). [Record](https://oig.hhs.gov/reports/all/2016/healthcaregov-case-study-of-cms-management-of-the-federal-marketplace/) | Drawing on 86 interviews: unclear leadership, poor policy–technical coordination and contract-management failures. Recovery took organizational changes as well as technical repairs | Recovery measures compete as explanations for change after a launch |
| GAO-15-290, *High-Risk Series: An Update* (2015-02-11), and GAO-25-107852, *High-Risk Series: Critical Actions Needed to Urgently Address IT Acquisition and Management Challenges* (2025-01-23). [2015](https://www.gao.gov/products/gao-15-290) · [2025](https://www.gao.gov/products/gao-25-107852) | IT acquisition and operations entered GAO's high-risk list in 2015 and remained there in 2025, with nine critical actions | The institutional setting for eligibility-system migrations |
| Beane, *An Assessment of the Unified Health Infrastructure Project: A Report to Governor Gina M. Raimondo* (RI DHS, 2017-02-15). [Full text](https://transparency.ri.gov/uhip/documents/assessments/UHIP%2030-day%20assessment.pdf) | Incorrectly encoded rules, missing interfaces, conversion problems and inadequate training. More than 60 staff were laid off. SNAP lacked wage verification, and the problems impaired overpayment recovery and QC. Some applications were expedited despite expected errors | The events paper's RI event mixes computation, information, staffing and access |
| Hoyle, *UHIP/RIBridges and HealthSource RI Project Costs: Review Report* (RI Auditor General, 2017-05). Lane URL `oag.ri.gov/reports/UHIP_RIB_HSRI_CostsReport2017.PDF` returned 404 on 2026-11-18 | Weak state project management, unclear contract acceptance and unresolved verification warnings. Required sample eligibility tests were delayed. The $407.3 million total combines UHIP/RIBridges and HealthSource RI | Testing eligibility software against case samples predates the oracle. The lane read this on 2026-10-25; find an archived copy before citing |
| Kentucky Program Review and Investigations Committee, *Minutes*, 2016-07-14. [Minutes](https://apps.legislature.ky.gov/minutes/prog_rev/160714OK.HTM) | Postponed launches, February 29 implementation, weak training and pilot, and erroneous notices. Deloitte testified that March benefits used the old system and Benefind-based decisions began April 1. Testimony, not audit findings | Treatment-date sensitivity for Kentucky: the launch date and the first decision date differ |
| *Gemmell v. Beane*, C.A. 16-00650 (D.R.I.): stipulation (signed 2017-02-24) and Special Master Report #1 (2017-12-01). [Stipulation](https://transparency.ri.gov/uhip/documents/additional/Stipulation%20-%20final%20for%20filing.pdf) · [Report](https://transparency.ri.gov/uhip/documents/fns-reports/snap-special-master-reports/SNAP%20-%20Special%20Master%20Report%201%2012-1.pdf) | Timeliness targets rising to 96%, monthly reporting and sample audits. The consent order was entered 2017-02-28. The report describes missing documents, inbox failures, understaffing and incorrect notices | Court supervision is an intervention inside the post-launch window. Timeliness is a separate outcome from payment accuracy |
| RI Governor's Office, "Governor Raimondo Extends Contract with Deloitte, Secures Millions for Rhode Island" (2019-03-15). [Announcement](https://www.ri.gov/press/view/35447) | A $50 million payment, discounted services, an operations extension through June 2021 and a waiver of claims. The "more than $210 million" total combines cash and discounts | Announced terms only |
| Lipps (FNS) to Hawkins (RI DHS), FY2019 error-rate liability letter (2020-07-06). [Letter](https://transparency.ri.gov/uhip/documents/legislative-reports/07-17-2020/Error%20Rate%20Penalty%20letter%20-%20FNS%20Notification%20-%20FFY%202019%207-6-2020.pdf) | $4,068,578 liability on a 22.66% FY2019 rate. The repeat triggered repayment of the at-risk half of the FY2018 liability; the other half had gone to approved new investment | Actual fiscal stakes under the 2002 regime during recovery. Does not attribute the rate to UHIP |

### Queue 6: cross-program penalties

| Work | Verified claim | Bears on |
|---|---|---|
| HHS OIG, *Eligibility Errors Resulting in Misspent Funds in the Medicaid Program*, OAI-04-87-00014 (1988-05). [Full text](https://oig.hhs.gov/documents/evaluation/1384/OAI-04-87-00014-Complete%20Report.pdf) | Interviews with 151 respondents: disallowance threats raised management attention and accuracy effort. Respondents also described volatility from high-dollar sampled cases and resistance to sampling changes that might raise measured rates. Not a representative design | Historical evidence for both operational improvement and measurement-side responses under noisy penalties |
| 42 CFR 431.1010 and the 431.958 definitions (PERM eligibility disallowance; final rule CMS-6068-F, 82 FR 31158, 2017). [eCFR](https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-431/subpart-Q/section-431.1010) † | Disallowance equals federal medical assistance funds × (lower limit − 3%), where the lower limit is the lower bound of the 95% confidence interval for the state's eligibility improper payment rate, excluding underpayments. A good-faith waiver requires MEQC pilot participation and corrective action plans | A comparator in force today that keys to a confidence bound. Read it with the enforcement record in the next two rows |
| GAO-20-157, *Medicaid Eligibility: Accuracy of Determinations and Efforts to Recoup Federal Funds Due to Errors* (2020-01-13). [Record](https://www.gao.gov/products/gao-20-157) | CMS had not imposed eligibility-error disallowances for decades. Some audit errors were incomplete documentation for applicants later found eligible | Legal exposure is not enforcement, and missing documentation is not ineligibility |
| GAO-26-108017, *Medicaid: Improved Oversight Needed of State Eligibility Error Corrective Action Plans* (2026-08-18; released 2026-09-17). [Record](https://www.gao.gov/products/gao-26-108017) | CMS reported no eligibility-error withholding in the period reviewed, and accepted incomplete corrective plans | Current enforcement record. Released after the August pre-registration |
| P.L. 119-21 §71106, *Payment Reduction Related to Certain Erroneous Excess Payments under Medicaid*, 139 Stat. 295–296 (2025). [Enacted text](https://www.govinfo.gov/content/pkg/PLAW-119publ21/html/PLAW-119publ21.htm) | From FY2030, limits good-faith waiver relief and expands the treatment of payments with insufficient eligibility information | Same law as the SNAP provision (§10105). A Medicaid comparison must separate today's regulation from the FY2030 change |
| Bundorf & Kessler, "The Responsiveness of Medicaid Spending to the Federal Subsidy", *National Tax Journal* 75(4): 661–680 (2022), DOI [10.1086/721912](https://www.journals.uchicago.edu/doi/abs/10.1086/721912) | Expansion states raised spending per previously eligible enrollee by about 15%; elasticities with respect to the after-subsidy price run from −0.494 to −0.579 | Federal match rates move state spending. Not transportable to error tiers |
| Leung, *State Responses to Federal Matching Grants: The Case of Medicaid*, Princeton IRS WP 647 (2021-02). [Record](https://irs.princeton.edu/publications/working-papers/state-responses-federal-matching-grants-case-medicaid). Published as *Journal of Public Economics* 216: 104746 (2022), DOI 10.1016/j.jpubeco.2022.104746 (Crossref bibliographic check only) | Working paper: a kink in the matching formula implies that a one-point rise in the federal match raises per-beneficiary spending by 3% | Use the working paper's numbers until the journal version is read |
| Baicker & Staiger, "Fiscal Shenanigans, Targeted Federal Health Care Funds, and Patient Mortality", *QJE* 120(1): 345–386 (2005), DOI [10.1162/0033553053327461](https://academic.oup.com/qje/article/120/1/345/1931466) | Medicaid DSH payments were diverted in the states most able to appropriate them; non-diverted payments reduced mortality, diverted ones did not | Federal transfers can prompt fiscal reallocation. A different margin from measured-error manipulation |
| 45 CFR 261.50 (TANF work-participation penalty), with 261.52 and 262.6. [eCFR](https://www.ecfr.gov/current/title-45/subtitle-B/chapter-II/part-261/subpart-E/section-261.50) † | The base penalty is 5% of the adjusted State Family Assistance Grant after a penalty-free year, rising 2 points for each consecutive penalty year, capped at 21%. Reasonable cause and corrective compliance can avert it | Penalizes participation shortfalls through the grant, not benefit costs through error rates. Escalates with persistence |
| GAO-05-821, *Welfare Reform: HHS Should Exercise Oversight to Help Ensure TANF Work Participation Is Measured Consistently across States* (2005-08-19). [Record](https://www.gao.gov/products/gao-05-821) | Differences in countable activities, reported hours and controls undermined comparisons. Stricter measurement could raise penalty exposure and push states toward separate programs | Measurement practice shapes accountability outcomes |
| GAO-10-525, *Temporary Assistance for Needy Families: Implications of Recent Legislative and Economic Changes for State Programs and Work Participation Rates* (2010-05-28). [Record](https://www.gao.gov/products/gao-10-525) | Twenty-nine states served selected families through solely state-funded programs outside the participation-rate denominator, nearly all starting after the Deficit Reduction Act | A denominator response that need not cost families assistance |
| 20 CFR 602.43 (UI quality control), with 602.40 and 602.42. [eCFR](https://www.ecfr.gov/current/title-20/chapter-V/part-602) † | DOL may use neither sanctions nor funding incentives to influence the achievement of specified state error rates. Under 602.42, a state found after notice and hearing not to maintain a compliant QC program loses eligibility for Title III grants; 602.40 lets DOL allocate added resources for QC analysis and corrective action | A design that deliberately separates measured error rates from money |
| GAO-02-697, *Unemployment Insurance: Increased Focus on Program Integrity Could Reduce Billions in Overpayments* (2002-07-12). [Record](https://www.gao.gov/products/gao-02-697) | UI performance management emphasized payment speed over accuracy and made limited use of administrative funding for integrity | Accuracy, speed and remediation funding are separate design dimensions |
| Lachowska, Mas & Woodbury, "Poor Performance as a Predictable Outcome: Financing the Administration of Unemployment Insurance", *AEA Papers and Proceedings* 112: 102–106 (2022), DOI [10.1257/pandp.20221073](https://www.aeaweb.org/articles?id=10.1257/pandp.20221073) | Treats UI administrative financing as a federal–state principal–agent problem, with descriptive workload–performance evidence | A framework precedent. No causal estimate |

### Queue 7: pre-registration and forecasting

| Work | Verified claim | Bears on |
|---|---|---|
| Chambers & Tzavella, "The past, present and future of Registered Reports", *Nature Human Behaviour* 6: 29–42 (2022), DOI [10.1038/s41562-021-01193-7](https://www.nature.com/articles/s41562-021-01193-7) | Registered Reports combine peer review before results with in-principle acceptance | A repository registration does not have Registered Report status |
| Arpinon & Espinosa, "A practical guide to Registered Reports for economists", *Journal of the Economic Science Association* 9(1): 90–122 (2023), DOI [10.1007/s40881-022-00123-1](https://link.springer.com/article/10.1007/s40881-022-00123-1) | Covers pre-results review, conditional acceptance, analysis plans, power and multiple testing | Commit adjudication rules and power alongside predictions |
| Nosek, Ebersole, DeHaven & Mellor, "The preregistration revolution", *PNAS* 115(11): 2600–2606 (2018), DOI [10.1073/pnas.1708274114](https://www.pnas.org/doi/full/10.1073/pnas.1708274114) † | Its "Challenge 3: Data Are Preexisting" discusses economists preregistering predictions of government data that exist but are not yet released, and stresses disclosing prior knowledge | Preregistering forecasts of unreleased administrative statistics is established methodology |
| Mellers, Hertwig & Kahneman, "Do Frequency Representations Eliminate Conjunction Effects? An Exercise in Adversarial Collaboration", *Psychological Science* 12(4): 269–275 (2001), DOI [10.1111/1467-9280.00350](https://journals.sagepub.com/doi/abs/10.1111/1467-9280.00350); erratum DOI 10.1111/1467-9280.00399 | Opposing researchers agreed on tests in advance, with an arbiter. The erratum withdraws the novelty claim and credits an earlier collaboration | Our process is adversarial review; scientific opponents did not jointly design tests |
| IARPA, "IARPA Announces Publication of Data from the Good Judgment Project" (2017-04-28). [Release](https://www.iarpa.gov/newsroom/article/iarpa-announces-publication-of-data-from-the-good-judgment-project) | Millions of forecasts across four years of the ACE program, later released publicly | Policy-relevant forecasting tournaments exist. No evidence the forecasts were hash-committed |
| Metaculus, FAQ, and question 7346 on July 2021 initial jobless claims. [FAQ](https://www.metaculus.com/faq/) · [Question](https://www.metaculus.com/questions/7346/initial-jobless-claims-july-2021/) | Probabilistic forecasts with resolution criteria and revision until close, including an administrative statistic | Public forecasting of policy statistics exists |
| Cramer et al., "The United States COVID-19 Forecast Hub dataset", *Scientific Data* 9: 462 (2022), DOI [10.1038/s41597-022-01517-w](https://doi.org/10.1038/s41597-022-01517-w) † | Real-time model forecasts were timestamped in public GitHub and Zoltar archives, and Git tags preserved each week's ensemble inputs. Targets came from HHS reports | Public, commit-versioned model forecasts of later-released administrative statistics predate this project |
| CDC, COVID-19 Forecast Hub repository protocol (accessed 2026-10-25). [README](https://raw.githubusercontent.com/CDCgov/covid19-forecast-hub/main/README.md) · [Model outputs](https://raw.githubusercontent.com/CDCgov/covid19-forecast-hub/main/model-output/README.md) | Model forecasts of NHSN and NSSP statistics arrive as pull requests against fixed deadlines and release schedules. Previous-week nowcasts can use preliminary data | The same precedent in a live protocol |

### Queue 8: small-N event studies and synthetic control

| Work | Verified claim | Bears on |
|---|---|---|
| Chernozhukov, Wüthrich & Zhu, "An Exact and Robust Conformal Inference Method for Counterfactual and Synthetic Controls", *JASA* 116(536): 1849–1864 (2021), DOI [10.1080/01621459.2021.1920957](https://doi.org/10.1080/01621459.2021.1920957) | Tests specified effect paths by permuting residuals over time and inverts the tests for confidence sets. Exactness requires exchangeability; dependent data need further conditions | Four pre-periods give the method little to work with |
| Firpo & Possebom, "Synthetic Control Method: Inference, Sensitivity Analysis and Confidence Sets", *Journal of Causal Inference* 6(2): 20160026 (2018), DOI [10.1515/jci-2016-0026](https://doi.org/10.1515/jci-2016-0026) | Extends equal-weight placebo inference with weighted p-values, sensitivity analysis and confidence sets | Asks whether RI's floor p-value survives unequal placebo weights |
| Arkhangelsky, Athey, Hirshberg, Imbens & Wager, "Synthetic Difference-in-Differences", *AER* 111(12): 4088–4118 (2021), DOI [10.1257/aer.20190159](https://www.aeaweb.org/articles?id=10.1257/aer.20190159) | Combines unit weights, time weights and fixed effects. With one treated unit, its placebo variance requires comparable noise across units | An alternative estimator that needs its own inference check |
| Ferman & Pinto, "Placebo Tests for Synthetic Controls", MPRA Paper 78079 (2017). [Record](https://mpra.ub.uni-muenchen.de/78079/) | Unscaled placebo comparisons can mislead; post/pre error ratios help but can still distort size. Abstract only | `analysis/event_study.py` ranks absolute, unstudentized effects |

Lane C's application to the events paper: none of these methods
changes a frozen verdict until a specified rerun produces one. RI's
`signal` is the frozen protocol's result under one placebo reference
distribution, and the KY and OR non-rejections do not establish zero
effects.

### 2025–26 novelty and competitor scan

| Work | Verified claim | Bears on |
|---|---|---|
| Molin, "Is SNAP Screener Accurate? Testing the Calculator Against the SNAP Quality Control Data", SNAP Screener (2025-10-17; updated 2026-07). [Post](https://www.snapscreener.com/blog/qc-data) † | Tests an independent benefit calculator against 37,009 FY2023 QC records, skipping eligibility screening: 98.64% agree within $2. The validation surfaced corrections to historical utility and medical-deduction parameters | Validating benefit code against QC records predates the oracle. The six-stage, zero-tolerance protocol remains distinct. Separate from the cited `@giannella_snapqc` software |
| Bauer & Schanzenbach, "The SNAP state cost-shift policy leaves the program's existence to chance", Brookings (2026-08-25). [Article](https://www.brookings.edu/articles/the-snap-state-cost-shift-policy-leaves-the-programs-existence-to-chance/) † | Appendix B computes the probability of each of the five OBBBA bins from FY2023 published rates and standard errors under a Normal(PER, SE) sampling distribution, without shrinkage. The fifth bin is 13.33% or higher, the delay threshold. Each probability is for a single year's draw | Overlaps the tier-lottery result, using published standard errors where the simulator resamples cases. The two-year FY2028 election and delay test are outside its calculation. This file makes no priority claim either way |
| Bauer & Schanzenbach, "SNAP cuts in the One Big Beautiful Bill Act will significantly impair recession response", Brookings (2025-10-08). [Article](https://www.brookings.edu/articles/snap-cuts-in-the-one-big-beautiful-bill-act-will-significantly-impair-recession-response/) | Describes how a state with a high, delayed rate moves into positive cost sharing when its rate falls | The delay's perverse incentive was described in 2025 |
| Bauer, Cole, Patt & Powell, "SNAP payment error rates by state, FY 2003–25", Brookings interactive (2026-06-25). [Interactive](https://www.brookings.edu/articles/snap-payment-error-rates-by-state-fy-2003-24/) | Historical state rates, cost-share boundaries and FY2025 placements | The June Brookings item, distinct from the August analysis |
| Bleich, Hamad & Plata-Nino, "The Challenges of Linking SNAP State Cost Sharing to Payment Error Rates", *JAMA Health Forum* 7(10): e264880 (2026-10-15), DOI [10.1001/jamahealthforum.2026.4880](https://jamanetwork.com/journals/jama-health-forum/fullarticle/2855585) | A qualitative critique: small QC samples, random annual variation, budget unpredictability, review and coding changes, and access incentives | The measurement argument, made qualitatively |
| Fannin, "Can reducing administrative burdens increase benefit amounts? Evidence from SNAP simplified reporting", *Applied Economic Perspectives and Policy* 47(3): 965–982 (2025), DOI [10.1002/aepp.13508](https://onlinelibrary.wiley.com/doi/10.1002/aepp.13508) | Difference-in-differences on FY2005–2014 QC microdata: simplified reporting lowered measured payment errors and raised benefits by about 7%. Much of the error reduction reflects which interim changes count as errors | A policy-to-measurement channel for rival predictions 2 and 3 |
| Goutagny, Fromherz & Monat, "CUTECat: Concolic Execution for Computational Law", ESOP 2025, LNCS 15695: 31–61, DOI [10.1007/978-3-031-91121-7_2](https://doi.org/10.1007/978-3-031-91121-7_2) | Generates tests for Catala programs by concrete and symbolic execution, targeting missing cases, conflicts and runtime errors | Structural testing, a different property from agreement with administrative outputs |
| Kennan, Singh, Garcia Guevara, Ahmed & Goodman, *AI-Powered Rules as Code: Experiments with Public Benefits Policy* (Beeck Center and Massive Data Institute, 2025-03-24; updated 2025-09-04). [Report](https://digitalgovernmenthub.org/publications/ai-powered-rules-as-code-experiments-with-public-benefits-policy/) | Four SNAP and Medicaid policy-to-code experiments, evaluated qualitatively. Names the lack of expert-curated test cases as a gap | Benefits-specific verification work that names a testing gap |
| Gosciak, Giannella, Guo, Chen & Koenecke, "LLMs in social services: How does chatbot accuracy affect human accuracy?", arXiv:2603.11213 (2026). [Abstract](https://arxiv.org/abs/2603.11213) | Builds 770 expert-verified CalFresh questions, partly informed by national QC error patterns, then randomizes chatbot assistance for caseworkers | QC-informed evaluation. Not benefit replay |
| Huang, Zhang & Hinds, "SNAP's New Reality", *Applied Economics Education and Extension* 8(4): 1–8 (2026), DOI [10.71162/aeee.155443](https://aeee.scholasticahq.com/article/171840-snap-s-new-reality-expanded-work-requirements-cost-shifts-to-states-and-benefit-adjustment-changes) | Maps state obligations from FY2024 point rates held constant; separately uses FY2023 QC microdata for work-requirement exposure | Earlier QC-based OBBBA exposure work |
| Wheaton, Waxman & Giannarelli, *How Would a State Cost Share Affect SNAP in a Recession?* (Urban, 2025-04-30). [Report](https://www.urban.org/research/publication/how-would-state-cost-share-affect-snap-recession) | ATTIS simulation of recession exposure under a hypothetical flat 10% state share | Earlier state-liability microsimulation |
| Wheaton, Giannarelli, Minton & Dehry, *How the Senate Budget Reconciliation SNAP Proposals Will Affect Families in Every US State* (Urban, 2025-07-02). [Report](https://www.urban.org/research/publication/how-senate-budget-reconciliation-snap-proposals-will-affect-families-every-us) | ATTIS models the Senate package, including the rate-linked 5–15% shares | Same |
| Gutierrez, "Federal Changes to the Social Safety Net Are Tightening State Budgets. School Meal Programs Could Pay the Price" (Urban, 2026-04-09). [Report](https://www.urban.org/research/publication/federal-changes-social-safety-net-are-tightening-state-budgets-school-meal) | FY2023 QC and ACS data: $11.1 billion benefit-cost exposure plus $2.6 billion administrative cost | Same |
| Bergh, *Research Note: Senate Agriculture Committee's Revised Proposal Risks Deep Cuts* (CBPP, updated 2025-06-30). [PDF](https://www.cbpp.org/sites/default/files/6-13-25fa-researchnote.pdf) | Compares FY2023 and FY2024 implied shares; tiers change even as the national rate falls | Historical tier switching, without attributing switches to sampling noise |
| Bergh & Rosenbaum, *Congressional Delay of SNAP Cost Shift Urgently Needed* (CBPP, 2026-01-08). [Report](https://www.cbpp.org/research/food-assistance/congressional-delay-of-snap-cost-shift-urgently-needed-to-protect-food) | FY2024-based liabilities; 11 jurisdictions within 0.5pp of a higher tier | Threshold proximity, without crossing probabilities |
| Bergh & Llobrera, "States' First-Ever Bill for SNAP Benefits Could Cost Billions" (CBPP, 2026-06-24). [Post](https://www.cbpp.org/blog/states-first-ever-bill-for-snap-benefits-could-cost-billions) | FY2025 shares and about $9 billion on annualized first-half FY2026 issuance | The same basis as the developments table's July CBPP row |
| McConnell, DiCicco & Bolen, *States Are Rushing to Respond As Congress' SNAP Cost Shift Approaches. Are They Ready?* (CBPP, 2026-10-09). [Report](https://www.cbpp.org/research/food-assistance/states-are-rushing-to-respond-as-congress-snap-cost-shift-approaches-are) | Reviews about 100 bills in 35 states changing verification, self-attestation, recertification and eligibility | Observable state responses for rival prediction 2 |
| FFIS, *One Big Beautiful Bill Act: Nutrition Provisions Affecting States*, Budget Brief 25-10 (2025-07-10; updated 07-15). [Record](https://ffis.org/budget-brief/one-big-beautiful-bill-act/) | Publisher summary: about $15 billion a year on FY2024 rates. Attachment not read | An early exposure estimate |
| FFIS, *FY 2025 SNAP Payment Error Rates Point to Increased Costs for States*, Issue Brief 26-14 (2026-06-25). [Record](https://ffis.org/issue-brief/fy-2025-snap-payment-error-rates-point-to-increased-costs-for-states/) | Publisher summary: $9.4 billion a year on FY2025 rates, with state estimates in an attachment that refused access | Resolves queue 9's FFIS item to the publisher's own record |
| FFIS, *Senate Farm Bill Delays SNAP Benefit Cost Share; Makes Other Changes*, Issue Brief 26-20 (2026-09-02). [Record](https://ffis.org/issue-brief/senate-farm-bill-delays-snap-benefit-cost-share-makes-other-changes/) | Publisher summary of S. 5526's timing and top-share changes, with state estimates on FY2025 rates | A proposal, not enacted law |
| CBO, *Dynamic Analysis of Changes to SNAP in H.R. 1* (2025-06). [Slides](https://www.cbo.gov/system/files/2025-06/61505-SNAP.pdf) | Slides 12–16 project spending and probabilistic aggregate state responses, including withdrawal | An earlier House version with different shares |
| CBO, *Estimated Effects of Public Law 119-21 on Participation and Benefits Under SNAP* (2025-08-11; amended 08-13). [PDF](https://www.cbo.gov/system/files/2025-08/61367-SNAP.pdf) | About $35 billion in state benefit payments, with participation responses modeled probabilistically | Uncertainty about behavior, a different object from uncertainty in measured rates |
| APHSA, *State Strategies to Improve SNAP Payment Accuracy: Early Lessons from the First Year of H.R. 1 Implementation* (2026-07; updated 07-07). [PDF](https://aphsa.org/wp-content/uploads/2026/06/2026-06_APHSA-State-SNAP-Survey-Results.pdf) | An Urban–APHSA survey of 39 states, fielded May 19–June 5: root-cause analysis, verification changes, predictive tools and staffing | Resolves queue 9's APHSA item. State responses extend beyond tightening eligibility |
| NCSL, "NCSL Statement in Response to FY 2025 SNAP Payment Error Rates" (2026-06-25). [Statement](https://www.ncsl.org/resources/details/ncsl-statement-in-response-to-fy-2025-snap-payment-error-rates) | FY2025 placements, delayed jurisdictions, and systems and staffing responses | Context |
| NASBO, *Summaries of Fiscal Year 2027 Proposed Budgets* (2026-04-07; updated 06-02). [PDF](https://higherlogicdownload.s3.amazonaws.com/NASBO/9d2d2db1-c943-4f1b-b750-0fca152d64c2/UploadedImages/Issue%20Briefs%20/Proposed_Budget_Summaries_FY27_6_2__S_.pdf) | Proposed SNAP administrative backfills, payment-accuracy tools, staffing, systems and QC funding across states | Budget observables for operational responses |
| Code for America, "Reducing Payment Error Rates for SNAP" (2025-12-11). [Post](https://codeforamerica.org/news/reducing-payment-error-rates-for-snap/) | Recommends targeted QA, worker tools, better change reporting and separate evaluation, while watching timeliness and procedural denials | Practitioner alternatives to tightening |
| Nava PBC, "Nava awarded contract to reduce SNAP payment error rate in Pennsylvania" (2025-12-23). [Announcement](https://www.navapbc.com/news/pennsylvania-snap-hr1) | Automation and tools for Pennsylvania DHS | An intervention in progress, with no evaluated effect |
| Vardr Partners, Benefits Gateway exposure table and FY2028 projection brief (2026-09). [Table](https://vardrpartners.com/products/benefits-gateway) | Lane: FY2025 rates × annualized issuance, deferrals marked, $8.32 billion first-year exposure. A static fetch on 2026-11-18 did not show the figure (the page may render it in the browser) | A commercial exposure interface on point rates |
| Higgins Strategy, *Every State Dollar*, Study XIX (2026-10-12). [Study](https://higginsstrategy.com/studies/every-state-dollar/) † | Exhibit 9: $11.1 billion a year at FY2025 benefit levels and rates, labeled arithmetic rather than a forecast | A point-rate baseline, not comparable to delay-adjusted expected bills |
| Rachidi, "SNAP's New Cost Share Requirement Is a Blunt, But Necessary Tool", AEI COSM (2026-07-28). [Commentary](https://cosm.aei.org/snaps-new-cost-share-requirement-is-a-blunt-but-necessary-tool/) † | Argues that states should cut errors by improving operations rather than by restricting eligibility or raising costs, and calls the cost share a blunt but necessary integrity tool | The integrity case for the policy. Queue 9 had attributed this piece to Corinth |

Lineage, not new competitors: Giannella and Molin's `snap_qc` is already
cited as `@giannella_snapqc`; Mathematica's QC documentation is already
cited; Axiom's QC oracle playbook is this project's own lineage.

### TO-VERIFY candidates the sweep surfaced

Not citable until read.

- Antwi-Wiafe, Sykuta, Mukembo & Giwa-Daramola, "Evaluating State
  Fiscal Exposure Under OBBBA's SNAP Cost-Share Reform", SSRN 7542138
  (Crossref record exists; content unread). The closest unread fiscal
  competitor.
- Corinth, "Paying for Payment Errors: State Incentives and Caseload
  Responses to SNAP Cost Sharing" (AEI working paper, 2026; title
  confirmed on the author's page, text unread). Bears directly on the
  rival predictions.
- Rachidi, "Why Congress Shouldn't Change SNAP's New Payment Error
  Approach" (indexed 2026-09-02); Weidinger & Rachidi, "The Empty
  Threat That States Will Stop Operating SNAP" (indexed 2026-09-15).
- Latham, Erez & Locke (1988), the earlier adversarial collaboration
  the Mellers erratum credits (Crossref record confirmed; content
  unread).
- Hash-sealed forecast claims: Chernets, "Sealed Before the Open",
  SSRN 7653679 (Crossref record exists; content unread), and
  Comuvia's "Forecast Ledger" page (opened; its registry and digests
  were not accessible). Both reportedly postdate August 2026.
- Leung's 2022 journal version; Ferman–Pinto's 2019 *REStat* article;
  Chernozhukov–Wüthrich–Zhu, "Debiasing and t-tests for synthetic
  control inference" (JPE acceptance listed on an author page).
- The NRC 1988 full report; Bawden et al., *Evaluation of the Federal
  One-Tier Quality Control Pilot Project* (Urban for FNS, 1989);
  Hansen & Tepping's two 1989 Westat QC reports; Mills et al.,
  *Evaluating the Hunger Prevention Act Quality Control Reforms*
  (Abt, 1991); Brodkin & Lipsky, "Quality Control in AFDC as an
  Administrative Strategy" (1983).
- Kentucky's FY2016 Statewide Single Audit (findings 2016-044 and
  -045); FNS's FFY2018 formal warning letter to Rhode Island (scanned,
  unreadable); executed Rhode Island–Deloitte terms.
- Needels et al.'s 2024 and 2026 DOL studies of UI administrative
  funding; Davidson & Martin (1998).
- Homonoff, Lee & Meckel, NBER WP 34434 (2025).
- Code for America, *Common Missteps on the Road to Lower SNAP Payment
  Error Rates* (2026-04); U.S. Digital Response's SNAP payment accuracy
  playbook; Mathematica's undated SNAP analytics page.
- Conference programs (APPAM and NTA 2026) could not be browsed, so
  this file makes no absence claim about conference papers.

### What the sweep changes

1. **Novelty boundaries narrow.** Prior work already covers:
   resampling SNAP QC data (Hand 1990; FNS 2019, Appendix F); one-year
   tier odds under sampling noise (Bauer & Schanzenbach 2026, Appendix
   B, from published standard errors); validating benefit code against
   QC records (Molin 2025); preregistering forecasts of unreleased
   administrative statistics, including public commit-versioned model
   forecasts (Nosek et al. 2018; Cramer et al. 2022); the delay's
   perverse incentive (Brookings 2025; CBPP 2026 on New Jersey); and
   automated caseworker assistance and participation, with a
   descriptive QC overpayment chart (Wu & Meyer). Lane D
   found no explicit priority claim in the main paper's abstract or
   introduction, but both papers' related-work sections should cite
   these. Those are paper edits, outside this file.
2. **Comparators that key to confidence bounds exist.** The 2002 SNAP
   rule required a 95% probability of exceeding 105% of the national
   measure, and today's PERM disallowance subtracts 3% from the lower
   bound of a 95% interval. Whether SNAP's 2025 tiers key to the point
   estimate is open: CRS's figure assumes they do, and CRS notes USDA
   has issued no regulations or guidance. TANF's
   penalty escalates with persistence, and UI's rules forbid
   error-rate incentives outright.
3. **The rival predictions need more rivals.** Operational
   improvement (HHS OIG 1988; APHSA, NASBO and Code for America in
   2025–26), reporting rules that change what counts as an error
   (Fannin 2025), denominator responses (GAO-10-525) and selection into
   completed reviews (McGill et al. 2016) all compete with tightening
   and measurement pressure. Dated notes on predictions 1–3 below
   record this.
4. **The events paper's pooled test needs a wording fix.** The RI and
   KY donor-placebo dictionaries are identical (42 of 42 entries),
   because the donor pools, years and fitting procedure coincide. So
   the pooled routine compares a two-state mean effect with
   single-state placebos, and its p = 0.093 is not a two-treated-unit
   calibration. `paper-causal/index.qmd` describes this as ranking
   "against pooled placebos built the same way". Pair-mean placebos
   would likely be less dispersed, which would make the current test
   conservative; that direction is inferred, not computed. The fix
   belongs in the paper, outside this file.

## Field map and TO-VERIFY queues

Nothing below may be cited until verified and promoted to a table
above.

1. **SNAP QC measurement and its history.** Verified: GAO RCED-84-155
   (the first sanction regime), the DOJ FCA settlement cluster and
   Osnes consultant settlement (the manipulation episode's primary
   sources), CRS R45147 (synthesis). Queue: the CNSTAT panel's
   companion volumes; the 2002 Farm Bill sanction redesign's
   legislative analyses (GAO-07-422T now verified and promoted — the
   mechanics; PL 107-171 Title IV and FR 2003-10-16 located, unread); the underlying USDA-OIG audit reports
   themselves; ERS/FNS-commissioned error-rate studies. Sweep
   (2026-10-25): §4118, the 2003 rule, the 2015 OIG audit, Hand 1990,
   DAB 948 and the ERS/FNS studies (Mills 2004; Logan 2006 and 2008;
   McGill 2016 and 2019) promoted; the NRC 1988 summary is
   bibliographic only. Still open: the NRC 1988 full report and the
   1989–91 FNS-commissioned QC studies.
2. **Accountability measurement under noise.** Verified:
   Goldstein–Spiegelhalter 1996 (promoted); Kane–Staiger (already
   cited in the paper). Queue: empirical-Bayes shrinkage refinements
   beyond the 1996 treatment if the rival-predictions draft needs
   them.
3. **Administrative burden and churn.** Verified: Homonoff–Somerville.
   Queue: Herd–Moynihan (book; already cited), SNAP takeup and
   enforcement work (NBER SNAP eligibility-enforcement line), sludge
   audits. Sweep: Giannella et al. 2024, Finkelstein–Notowidigdo,
   Unrath, Wu–Meyer, Cook–Cox–East and the sludge-audit sources
   promoted; Herd–Moynihan's SNAP chapter located, text unread.
4. **Rules as code / computational law.** Verified: Lawsky 2017 and
   the Catala SMU piece (promoted); Merigoux et al. (already cited).
   Queue: OpenFisca lineage papers; verification claims in the govtech
   literature to position the oracle method against. Sweep: Molin
   2025, Kennan et al. 2025 and CUTECat promoted; the OpenFisca line
   remains open.
5. **Public-sector IT implementation failure.** Verified:
   Peeters–Widlak 2018 and 2023 (promoted). Queue: healthcare.gov
   retrospectives; GAO IT-modernization high-risk series; academic
   post-mortems of UHIP/Benefind if any exist beyond press. Sweep: the
   official healthcare.gov retrospectives, the GAO high-risk series,
   Rhode Island's assessment, auditor review, court record and FNS
   liability letter, and Kentucky's committee minutes promoted. Still
   open: Kentucky's single audit and any scholarly UHIP or Benefind
   post-mortem.
6. **Fiscal federalism and intergovernmental penalties.** Verified:
   North Carolina's county pass-through (G.S. 108A-52.2). Queue:
   Medicaid FMAP incentive literature; TANF penalty design; UI
   administrative-funding incentives — the cross-program frame for
   what error-rate-keyed cost shares do. Sweep: PERM, TANF and UI rules,
   their GAO records, HHS OIG 1988 and the matching-grant studies
   promoted. Still open: causal evidence on responses to PERM
   penalties, and on responses to SNAP's tiers specifically.
7. **Pre-registration and forecasting in policy.** Verified:
   DellaVigna–Pope line. Queue: registered-reports methodology
   statements; adversarial-collaboration precedents; prediction
   platforms for policy outcomes. Sweep: Chambers–Tzavella,
   Arpinon–Espinosa, Nosek et al., Mellers–Hertwig–Kahneman, IARPA,
   Metaculus and the COVID-19 Forecast Hub promoted. Still open: Latham
   et al. 1988's content and the hash-sealed forecast claims.
8. **Small-N event studies and synthetic control.** Verified: Abadie
   JEL 2021 survey; Abadie–Diamond–Hainmueller JASA 2010. Queue:
   inference refinements (conformal/placebo-based) if the RI/KY runs
   need them. Sweep: Chernozhukov–Wüthrich–Zhu, Firpo–Possebom,
   synthetic difference-in-differences and Ferman–Pinto promoted.
   Whether any of them changes a verdict needs specified reruns.
9. **Implementation and state responses (opened 2026-10-24).**
   Verified: the developments table above. Resolved by the sweep:
   FFIS's $9.4 billion estimate (Issue Brief 26-14, publisher summary;
   attachment unread), APHSA's survey, and "SNAP's New Cost Share
   Requirement Is a Blunt, But Necessary Tool", which is Rachidi's
   (2026-07-28), not Corinth's. Queue: Illinois DHS's "up to $80
   million" against the Civic Federation's roughly $550 million on a
   14.67% FY2025 rate that qualifies for the delay; any USDA
   implementation guidance (none as of IN12723, 2026-10-05, still
   current 2026-11-18); NC DHHS's county attribution method and its
   first report (due 2027-02-01); other states' pass-through or
   appropriation statutes; the CBO estimate for S. 5526.

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
   *Note (2026-11-18):* Bauer and Schanzenbach compute the same kind of
   one-year tier odds from published standard errors. The repo's
   backtest finds sampling-only nominal 90% intervals cover 48% of
   realized next-year rates (`analysis/PERSISTENCE_BACKTEST.md`), so
   on that evidence rejecting the sampling-only baseline is likely
   even with no response; the pre-registration also commits drift
   variants. Rejection alone cannot say whether drift, burden or
   measurement produced it (lane C).
2. **Burden-response direction (Homonoff–Somerville; Herd–Moynihan).**
   If states respond to cost sharing by tightening verification and
   recertification, participation falls among high-churn cases while
   the measured error direction is ambiguous (fewer active cases to
   err on; more procedural terminations, which QC counts differently
   than payment errors). Distinguishing observable: recertification
   cadence and procedural-denial shares move before measured rates do.
   *Note (2026-11-18):* Mills et al. 2004 already model this
   prediction's core, falling participation with an error response
   whose sign depends on the base year. Giannella et al. 2024 show
   procedural flexibility can raise access while verification stays in
   place. Unrath shows less frequent reporting raises retention, and
   Fannin 2025 shows reporting rules change which changes count as
   errors. CBPP's 2026-10-09 inventory of
   about 100 state bills supplies the policy changes to score this
   against.
3. **Measurement-side response (NRC 1987; GAO-07-422T; the DOJ
   record).** The 1987 panel's diagnosis and the settlement history
   both predict pressure lands on the measurement pipeline first —
   sampling plans, review practice, arbitration — because that is the
   cheapest margin. Distinguishing observable: cause-mix and
   adjudication-stage shifts (the wedge components) without matching
   movement in file-computable error.
   *Note (2026-11-18):* "first, because cheapest" is not established.
   The 2015 OIG audit and the 2016 completion study verify measurement
   margins, but neither establishes their cost or timing, and DAB 948
   shows adjudication can move liability legitimately. HHS OIG's 1988
   inspection supports operational improvement as a rival response
   under the same penalties. So the observable should also track
   training, staffing and corrective investment (APHSA, NASBO) next
   to adjudication-stage shifts.

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
