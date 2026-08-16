# Facts

- F1 | Paper estimand | bundled system replacement as implemented; contemporaneous process, staffing, mitigation, and software included; component isolation excluded | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:7-19`; `analysis/EVENT_STUDY_PROTOCOL.md:7-20`
- F2 | RI/KY panel | FY2012–FY2024; FY2016 transition excluded; pre FY2012–15; post FY2017–20 and FY2022–24; FY2021 dropped | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:13-19,62-71`; `analysis/riky_event_study_results.json:scope.panel_years`; `.units.RI.specifications.primary_exclude_fy2016_drop_fy2021`; `.units.KY.specifications.primary_exclude_fy2016_drop_fy2021`
- F3 | Oregon panel | FY2017–FY2024; pre FY2017–20; post FY2022–24; FY2021 dropped; February launch implies 4 pre-launch and 8 post-launch fiscal months in FY2021 | `analysis/EVENT_STUDY_PROTOCOL.md:13-20,49-55`; `analysis/event_study_results.json:scope.panel_years`; `.specifications.primary_drop_fy2021`
- F4 | Outcome universe | active cases `CASE == 1`; `HWGT > 0`; adjudicated `STATUS in {2,3}` | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:29-30`; `analysis/EVENT_STUDY_PROTOCOL.md:24-25`
- F5 | RI/KY fixed-real floor | $68.31384966506094 FY2024 dollars; maximum audited official real tolerance; nominal CPI-scaled floors FY2012–24 = 50.0000, 50.7324, 51.5554, 51.6165, 52.2677, 53.3812, 54.6850, 55.6759, 56.3628, 59.0107, 63.7332, 66.3567, 68.3138 | `analysis/riky_event_study_results.json:outcome_definitions`
- F6 | Audited official nominal tolerance series FY2012–24 | $50, $50, $37, $38, $38, $38, $37, $37, $37, $39, $48, $54, $56 | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:39-42`; `analysis/coding_consistency.json:years.*.threshold.dollars`
- F7 | Oregon fixed-real floor | $56 FY2024 dollars; CPI-U annual averages FY2017–24 = 245.120, 251.107, 255.657, 258.811, 270.970, 292.655, 304.702, 313.689 | `analysis/EVENT_STUDY_PROTOCOL.md:24-30`; `analysis/event_study_results.json:outcome_definitions`
- F8 | Strict outcome | codes {17,19,20}; whole `HWGT * AMTERR` credited upon any slot presence; dollars per all-active-case weighted case-month; overlap permitted | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:44-51`; `analysis/cause_shares.json:cause_codes.17,.19,.20`
- F9 | Total-rate outcome | above-floor `HWGT * AMTERR` / all-active-case `HWGT * RAWBEN` × 100; reconstruction, not changing-threshold published rate | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:52-55`
- F10 | Client placebo | codes {1,2,3,4,7}; analysis superclass; no binary responsibility field | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:56-60`; `analysis/cause_shares.json:class_semantics.client_or_fact`
- F11 | Synthetic comparison | nonnegative weights summing to 1; pretreatment squared-distance minimization; joint scaling by donor-state pretreatment SD; three parent outcomes | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:90-97`
- F12 | Effect aggregation | post mean gap minus pre mean gap | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:90-97`
- F13 | Inference | permutation in space; absolute effect rank; ties against signal; `(1 + exceedances)/(1 + placebos)` | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:104-119`
- F14 | Unit reporting rule | strict p < 0.10 and client p >= 0.10; total rate and RI consequence profile verdict-inert | `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:121-131`
- F15 | RI primary | strict effect +$2.8967640924/case-month; pre-RMSPE 0.3448723426; rank 1/43; p 0.0232558140; client effect +$3.9642021850; client rank 10/43; client p 0.2325581395; total-rate effect +2.5648898637 pp; verdict `signal` | `analysis/riky_event_study_results.json:units.RI.specifications.primary_exclude_fy2016_drop_fy2021`; `.units.RI.permutation_inference`; `.units.RI.decision`
- F16 | RI pandemic sensitivities | strict +2.9666514070 with FY2020–21 dropped; +2.5786023032 with FY2021 included as post | `analysis/riky_event_study_results.json:units.RI.specifications.drop_fy2020_and_fy2021.outcomes.strict_computing_dollars_per_case_month.effect`; `.include_fy2021_as_post.outcomes.strict_computing_dollars_per_case_month.effect`
- F17 | RI timing sensitivity | FY2016 as pre; strict +3.0969199808; client +4.2000766710; total +3.1750855318 pp | `analysis/riky_event_study_results.json:units.RI.specifications.ri_fy2016_as_pre.outcomes`
- F18 | RI consequence profile | FY2017–19 mean strict gap +$4.9503509493; later FY2020/FY2022–24 +$1.4827104666; difference +$3.4676404827; `changes_verdict=false` | `analysis/riky_event_study_results.json:rhode_island_consequence_window_profile`
- F19 | RI billing | $37,343,809.68; SNAP overpayments; September 2016–December 2019; billing record excluded from estimation | `analysis/system_migrations.json:events[0].notes`; `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:73-78`
- F20 | Kentucky primary | strict −$0.5843029139/case-month; pre-RMSPE 0.0794976955; rank 13/43; p 0.3023255814; client −$4.5346879362; client rank 5/43; p 0.1162790698; total −3.6953879037 pp; verdict `no_protocol_defined_signal` | `analysis/riky_event_study_results.json:units.KY.specifications.primary_exclude_fy2016_drop_fy2021`; `.units.KY.permutation_inference`; `.units.KY.decision`
- F21 | Kentucky pandemic sensitivities | strict −0.7298962965 with FY2020–21 dropped; −0.3852700755 with FY2021 included | `analysis/riky_event_study_results.json:units.KY.specifications.drop_fy2020_and_fy2021.outcomes.strict_computing_dollars_per_case_month.effect`; `.include_fy2021_as_post.outcomes.strict_computing_dollars_per_case_month.effect`
- F22 | Kentucky timing sensitivity | FY2016 treated; strict −0.5376248519; client −4.2694456695; total −3.4131422975 pp | `analysis/riky_event_study_results.json:units.KY.specifications.ky_fy2016_as_treated.outcomes`
- F23 | Pooled statistic | equal-state strict +1.1562305893; p 0.0930232558; rank 4/43; client −0.2852428756; p 1.0; rank 43/43; total −0.5652490200 pp; verdict `signal` | `analysis/riky_event_study_results.json:pooled.statistics`; `.pooled.permutation_inference`; `.pooled.decision`
- F24 | Oregon primary | strict −$0.1997241318/case-month; pre-RMSPE 0.5501675544; rank 25/35; p 0.7142857143; client +$10.5341615541; p 0.0285714286; rank 1/35; total +5.7567189038 pp; total p 0.0285714286; verdict `no_protocol_defined_signal` | `analysis/event_study_results.json:specifications.primary_drop_fy2021`; `.permutation_inference`; `.decision`
- F25 | Oregon sensitivities | strict +0.2080622920 with FY2021 treated; −0.1705713992 with FY2020–21 dropped | `analysis/event_study_results.json:specifications.include_fy2021_as_treated.outcomes.strict_computing_dollars_per_case_month.effect`; `.specifications.drop_fy2020_and_fy2021.outcomes.strict_computing_dollars_per_case_month.effect`
- F26 | RI/KY donor pool | 42 states/DC; registry states CO, FL, GA, IN, KY, NC, NM, OR, RI excluded | `analysis/riky_event_study_results.json:scope.donor_pool`; `.scope.excluded_registry_states`
- F27 | Oregon donor pool | 34 states; delay-roster and registry exclusions pre-named; result conditional on pool | `analysis/event_study_results.json:scope.donor_pool`; `analysis/EVENT_STUDY_PROTOCOL.md:59-68`
- F28 | RI primary nonzero donor weights | CT 0.193045; DC 0.040676; MI 0.353813; VT 0.054649; WV 0.357817 | `analysis/riky_event_study_results.json:units.RI.specifications.primary_exclude_fy2016_drop_fy2021.donor_weights`
- F29 | Kentucky primary nonzero donor weights | CT 0.316995; DC 0.230464; DE 0.192273; IL 0.023308; MI 0.044494; NY 0.179827; SD 0.012638 | `analysis/riky_event_study_results.json:units.KY.specifications.primary_exclude_fy2016_drop_fy2021.donor_weights`
- F30 | Oregon primary nonzero donor weights | CT 0.186672; IA 0.672668; MO 0.024572; WI 0.116088 | `analysis/event_study_results.json:specifications.primary_drop_fy2021.donor_weights`
- F31 | Coding coverage | all 9 AGENCY slots and strict codes {17,19,20} present FY2012–24; numeric presence ≠ unchanged semantics; FY2024 techdoc: minor AGENCY/ELEMENT/NATURE revisions | `analysis/coding_consistency.json:panel_recommendation.strict_class_outcomes`; `.cross_year_summary.fy2024_minor_revisions_evidence`
- F32 | Broad-class instability | code 22 first observed FY2023; codes 23–25 first observed FY2024; broad class excluded as primary historical outcome | `analysis/coding_consistency.json:cross_year_summary.consecutive_observed_code_changes.2023.cause_codes`; `.2024.cause_codes`; `.panel_recommendation.strict_class_outcomes`
- F33 | Finding-code ceiling | exact FY2024 inventory match first occurs FY2024 for cause, element, and nature; FY2014 `E_FINDG` includes alphabetic `A`; semantic bridge required for cross-panel finding-targeted outcomes | `analysis/coding_consistency.json:cross_year_summary.first_year_exactly_matching_fy2024_observed_inventory`; `analysis/QUASI_EXPERIMENTS.md:152-157`
- F34 | FY2017 cross-check | CSV/SAV 45,530 rows each; row difference 0; AGENCY/NATURE/E_FINDG/ELEMENT inventories exact-match | `analysis/coding_consistency.json:source_cross_checks.fy2017_csv_vs_sav`
- F35 | FY2020 file | combined 27,112 rows = period 1 18,319 + period 2 8,793; reconciliation true | `analysis/coding_consistency.json:pandemic_file_handling.fy2020`
- F36 | FY2021 file | 9,832 rows; pandemic-partial; sensitivity handling required | `analysis/coding_consistency.json:pandemic_file_handling.fy2021`
- F37 | Decomposition channels | defect 17; mass-change 19; arithmetic 20; user 21; entry 18; disregard 12; recertification 23–25 | `analysis/UHIP_DECOMPOSITION_PROTOCOL.md:19-35`; `analysis/cause_shares.json:cause_codes`
- F38 | Decomposition power counts FY2017/18/19 | adjudicated errors 325/206/482; code 17 = 44/12/21; 19 = 139/93/98; 20 = 7/3/14; 21 = 1/4/8; 18 = 5/13/18; 12 = 84/51/137; 23–25 = 0/0/0 | `analysis/UHIP_DECOMPOSITION_PROTOCOL.md:50-64`
- F39 | Inferential gate | >=30 presences in each FY2017–19; inferential: mass-change, disregard, defect-or-mass-change; composite counts 183/105/119; descriptive: defect, arithmetic, user, entry, recertification | `analysis/UHIP_DECOMPOSITION_PROTOCOL.md:91-106`
- F40 | Joint-fit decomposition client placebo | +$5.6372208133; pre-RMSPE 1.3127805769; rank 1/43; p 0.0232558140 | `analysis/uhip_decomposition_results.json:client_placebo`
- F41 | Joint-fit mass-change | effect +$2.0821040632; pre-RMSPE 0.0961250735; rank 1/43; p 0.0232558140; parent verdict `no_protocol_defined_signal`; family verdict `signal_family_adjusted`; consequence/later/difference = 3.7348812436/0.9588013755/2.7760798681 | `analysis/uhip_decomposition_results.json:inferential_channels.mass_change`
- F42 | Joint-fit disregard | effect +$0.5574919410; pre-RMSPE 2.1828123950; rank 34/43; p 0.7906976744; both verdicts non-signal; consequence/later/difference = 3.6827249924/1.6382526886/2.0444723039 | `analysis/uhip_decomposition_results.json:inferential_channels.disregard`
- F43 | Joint-fit defect-or-mass-change | effect +$2.7577596683; pre-RMSPE 0.1980894632; rank 1/43; p 0.0232558140; parent verdict `no_protocol_defined_signal`; family verdict `signal_family_adjusted`; consequence/later/difference = 4.9857966909/1.2224257052/3.7633709857 | `analysis/uhip_decomposition_results.json:inferential_channels.defect_or_mass_change`
- F44 | Joint-fit descriptive effects | defect +0.9067594528; arithmetic +0.3091722060; user +0.2738612257; entry +0.6557585398; recertification observed zero/no fit | `analysis/uhip_decomposition_results.json:descriptive_channels`
- F45 | Joint-fit donor weights | CT 0.073687; DC 0.056907; MD 0.130548; MI 0.132114; OH 0.306058; SD 0.300686 | `analysis/uhip_decomposition_results.json:primary_specification.donor_weights`
- F46 | Donor-fit design finding | same client outcome: parent +3.964/p 0.233/rank 10/43; joint-fit +5.637/p 0.023/rank 1/43; parent fit dominant WV 0.358, MI 0.354, CT 0.193; joint fit dominant OH 0.306, SD 0.301, MI 0.132, MD 0.131 | `analysis/UHIP_DECOMPOSITION_DEVIATIONS.md:40-54`; exact values: `analysis/riky_event_study_results.json:units.RI`; `analysis/uhip_decomposition_results.json`
- F47 | Decomposition parent-rule consequence | mass-change and defect-or-mass-change p-values below 0.10; no parent signal because joint-fit client p below 0.10 | `analysis/UHIP_DECOMPOSITION_DEVIATIONS.md:56-65`
- F48 | Strict weighted dollars FY2016/FY2017 | $404,871.50/$6,915,111.64; FY2017 overlap duplicate credit $759,868.20 across 7 cases | `analysis/uhip_decomposition_results.json:overlap_accounting[4:6]`
- F49 | Strict-channel overlap FY2017/18/19 | overlap cases 7/4/2; duplicate credit $759,868.20/$593,218.52/$187,891.02 | `analysis/uhip_decomposition_results.json:overlap_accounting[5:8]`
- F50 | RI internal element layer | strict-coded cases: 15 FY2012–15; 116 FY2017–19; comparable-code inventory 43 codes; pre-absent {213,225}; post-absent {212,222}; case-presence counting | `analysis/uhip_decomposition_results.json:element_mix`; `analysis/UHIP_DECOMPOSITION_DEVIATIONS.md:6-14`
- F51 | RI post element leaders | code 364: 63/116 = 54.31%; 331: 54/116 = 46.55%; 363: 46/116 = 39.66%; 333: 26/116 = 22.41%; overlapping case-presence shares | `analysis/uhip_decomposition_results.json:element_mix.windows.fy2017_2019.codes`
- F52 | Certification vintage | pre-go-live 39 cases, $5,710,151.19, 34.4311%; on/after 77, $10,874,154.55, 65.5689%; unclassifiable 0 | `analysis/uhip_decomposition_results.json:certification_vintage_split.groups`
- F53 | Certification-vintage method ceiling | `YRMONTH - LASTCERT`; `CERTMTH` not used; recorded vintage, not observed conversion status | `analysis/UHIP_DECOMPOSITION_DEVIATIONS.md:16-30`; `analysis/uhip_decomposition_results.json:certification_vintage_split`
- F54 | Fixed-donor protocol | parent three-outcome fit held fixed across channels; expected parent placebo reproduction +3.964, p 0.233, rank 10/43; both estimators required | `origin/fixed-donor-protocol:analysis/FIXED_DONOR_PROTOCOL.md:13-38,63-69`
- F55 | PROVISIONAL — fixed-donor results | no `analysis/fixed_donor_decomposition_results.json` on `origin/fixed-donor-protocol` at extraction; numerical channel results unavailable | `[UNSOURCED]` result; branch tree checked 2026-08-16

# Story beats

- RI | UHIP / Unified Health Infrastructure Project; later RIBridges | Deloitte | 2016-09 month-precision statewide cutover | one-year delay from July 2015 plan; ~15,000 application backlog peak; $37,343,809.68 FNS bill; Sep 2016–Dec 2019 | confidence `verified_multi_source` | https://transparency.ri.gov/uhip/ ; https://www.wpri.com/target-12/we-are-very-sorry-deloitte-apologizes-to-ri-about-uhip/ ; https://turnto10.com/news/local/rhode-island-department-of-human-services-appeals-federal-government-snap-overpayments-37-million-dollars-uhip-ribridges-usda-food-and-nutrition-service ; https://www.rimonthly.com/unified-health-infrastructure-project/ | `analysis/system_migrations.json:events[0]`
- KY | Benefind | Deloitte | 2016-02-29 | integrated SNAP/Medicaid platform; ~$101.5M; ~25,000 erroneous cancellation notices; ~50,000-case backlog; recertification extension 6→12 months | FNS billing: `[NEEDS CITATION: Kentucky FNS billing record, if any]` | confidence `verified_multi_source` | https://www.lpm.org/news/2016-07-21/state-officials-say-theyre-still-fixing-benefind ; https://nkytribune.com/2016/04/one-stop-shop-benefind-isnt-causes-loss-of-benefits-and-confusion-for-thousands-of-kentuckians/ ; https://www.wkyufm.org/politics/2016-04-28/state-dedicates-workers-to-cut-benefind-backlog | `analysis/system_migrations.json:events[1]`
- OR | ONE Eligibility expansion to SNAP/other programs | vendor `[NEEDS CITATION: Oregon ONE vendor]` | 2021-02 | origin in Oregon Health Plan eligibility; expansion to other benefit programs | documented launch problems `[NEEDS CITATION: Oregon ONE launch problems]`; FNS billing `[NEEDS CITATION: Oregon FNS billing record, if any]` | confidence `verified_single_source` | https://www.oregon.gov/odhs/agency/pages/oep-one-system.aspx | `analysis/system_migrations.json:events[3]`
- GA registry context | Georgia Gateway | vendor `[NEEDS CITATION]` | 2017-02-06 Henry County pilot; statewide completion `[NEEDS CITATION]` | https://dhs.georgia.gov/document/document/georgia-gateway-integrated-eligibility-system/download ; https://dhs.georgia.gov/georgia-gateway | `analysis/system_migrations.json:events[2]`
- NC registry context | NC FAST FNS module | vendor `[NEEDS CITATION]` | county rollout 2012-05–2013-03; July 2013 technical failure; >1-month slowdown; backlog | https://www.wral.com/nc-fast-rollout-continues-amid-myriad-of-challenges/13864953/ ; https://webservices.ncleg.gov/ViewDocSiteFile/19790 | `analysis/system_migrations.json:events[4]`
- FL registry context | ACCESS modernization | vendor/date `[NEEDS CITATION]`; ~$205M; reported start 2022; ~30-year-old mainframe | https://www.pew.org/en/research-and-analysis/articles/2026/01/14/as-snap-changes-shift-food-assistance-costs-states-face-new-choices | `analysis/system_migrations.json:events[5]`
- NM registry context | ASPEN | vendor/date/problems/billing `[NEEDS CITATION]`; mid-2010s replacement `[UNSOURCED]` | `analysis/system_migrations.json:events[6]`
- IN registry context | FSSA modernization | IBM | 2007–09 modernization/cancellation/litigation `[UNSOURCED]`; exact go-live `[NEEDS CITATION]` | `analysis/system_migrations.json:events[7]`
- CO registry context | CBMS | 2004 go-live/trouble `[UNSOURCED]`; vendor/date/billing `[NEEDS CITATION]` | `analysis/system_migrations.json:events[8]`

# Quotes

- None cataloged; third-party verbatim extraction not required by committed artifacts.

# Arguments

1. P1: RI satisfies the frozen unit-level signal rule; Kentucky and Oregon do not. | F15, F20, F24
2. P2: pooled RI/KY satisfies the frozen pooled rule; pooled inference does not replace unit-level verdicts. | F23; `analysis/RIKY_EVENT_STUDY_PROTOCOL.md:99-102,121-131`
3. P3: parent-design placebo status depends on the outcome set sharing the donor fit. | F40, F46
4. P4: joint-fit mass-change and defect-or-mass-change estimates have low channel p-values but fail the parent rule because the run-level client placebo fires. | F41, F43, F47
5. P5: mass-change code 19 carries the largest inferential portion of the joint-fit strict-channel rise; disregard does not differ detectably from its donor under the same run. | F41–F43
6. P6: consequence-window concentration is independently aligned with the RI billing window; alignment remains descriptive and verdict-inert. | F18–F19
7. P7: a Kentucky non-signal cannot encode implementation success. | F20; launch-problem registry beat
8. P8: Oregon’s fired placebo blocks causal attribution under the frozen rule. | F24
9. P9: cross-year strict-code inventory supports FY2012 start; semantic stability remains bounded. | F31–F33
10. P10: element and certification layers characterize RI composition only; neither supplies a comparison-unit estimate. | F50–F53
11. P11: fixed-real thresholding removes changing nominal QC tolerance from outcome construction. | F5–F7
12. P12: event estimates and adoption accounting scenarios share a coded outcome class; neither validates the other. | `paper/index.qmd:1019-1025`; `paper/FACTS.md:R3`

# Structural notes

- Title lock | What a system replacement does to measured error: three SNAP eligibility-system migrations in the quality-control record
- Estimand lock | "bundled system replacement as implemented"
- Forbidden causal objects | never "the effect of a rules engine"; never "the effect of software"
- Channel lock | channels = QC coding-practice classification
- Consequence-window lock | consequence-window check = descriptive and verdict-inert
- Decomposition estimator lock | joint-fit and fixed-donor both reported; reproduction check as bridge; neither estimator privileged
- Fixed-donor availability | PROVISIONAL protocol only until branch result artifact exists
- Introduction | question; three events; estimand; verdict triplet; RI design sensitivity; no state performance ranking
- QC record | active-case universe; weights; AMTERR/RAWBEN/STATUS; fixed-real threshold; strict and client code maps; coding-semantic ceiling
- Events | registry dates/confidence; vendors; documented launch facts; URLs; unsupported vendor/problem/billing fields marked
- Design | synthetic weights; joint fit; post-minus-pre gap; permutation-in-space; plus-one rule; frozen protocols; transition and pandemic specifications; conditional donor pools
- Results | RI, Kentucky, Oregon separately; exact effects/p/ranks/pre-RMSPE; pooled statistic separately; sensitivities flat
- RI decomposition | gate; channels; overlaps; joint-fit results; fired placebo; family and parent verdicts; fixed-donor result pending/provisional
- RI internal layers | element case-presence composition; certification-vintage arithmetic; no comparison; no conversion-status label
- Limitations | one treated unit/two treated units; 35/43 permutation denominators; thin channel cells; coder-classification ceiling; semantic drift; donor-fit dependence; pandemic partial file; registry incompleteness
- Simulation-paper relation | one paragraph maximum; forward cite causal paper from adoption scenarios; back cite adoption accounting from causal paper; shared cause-class identity only; no validation claim
- Conclusion | estimand-bounded findings; signal/non-signals; measurement/design finding; no policy position
- Required disclosure | protocols frozen before estimation; branch-only provisional protocol; result absence; FY2021 handling; post-treatment-conditioned Oregon donor exclusions; whole-case overlapping credit; no adoption gate
