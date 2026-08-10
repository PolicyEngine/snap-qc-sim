# FY2027 feature round report: certification cadence, BBCE, and Medicare premium bands

- Date: 2026-08-09
- Branch: `eric-ben-features`
- Base commit: `900199db293bf4120d0ed711d18f4bbec724e7ee` (the task-start `origin/main`)
- Protocol: train on FY2017–19 and FY2022–23; evaluate once on FY2024; `CASE == 1`; no feature-family selection against FY2024.

## Outcome

The three requested feature families are implemented as 17 additive features and feed the official-error classifier, both hurdle classification stages, the hurdle magnitude model, and every distributional model through the shared `INTERMEDIATES` list. The full pipeline regenerated all seven requested artifacts twice. All seven files were byte-identical on the second run.

The additive classifier result is modest and positive on the unchanged protocol: weighted FY2024 ROC AUC is `0.767947` versus the committed burden baseline `0.766626` (`+0.001321`), and PR-AUC is `0.358093` versus `0.355304` (`+0.002788`). Precision at a 5% weighted review budget rises from `0.477608` to `0.481660` (`+0.4052pp`). The burden-only refit reproduces the committed baseline exactly on all three metrics.

This is an additive-feature comparison on the same train/evaluation split. It is not a causal estimate, a policy-effect estimate, or a claim that every family contributes positive standalone lift. No family was dropped or selected after seeing FY2024.

Gate status:

| Gate | Result |
|---|---|
| Field semantics checked against the FY2024 technical documentation | Pass |
| All 17 features wired through classifier, hurdle, and distributional lists | Pass |
| SMD scenario predicate unchanged | Pass |
| Full pipeline run twice | Pass |
| Byte-identical rerun | Pass, 7/7 files |
| CI-exact pytest | Pass, 149 tests |
| CI-exact Ruff | Pass |
| App source changes | None; only the two explicitly requested generated JSON artifacts changed |
| Independent code/test/semantics review | Pass; no blocking findings remain |
| Official FNS PDF raw-byte SHA-256 | **Closed post-lane**: `96b1e5c5b2b59cd15429f8d71d696254da75950f12358d492c0f8be23272c25c`, downloaded and cover-verified outside the sandbox 2026-08-09 |
| Requested `fable` session | Lane substituted six independent review passes; a cross-model fable review of the feature builders, band predicates, and boundary logic ran at gate time and passed |
| Requested external report destination | **Unavailable**; sandbox-safe repository report used |

## Source pins and audit inputs

| Input | SHA-256 |
|---|---|
| FY2024 QC technical documentation, `techdoc.txt` | `619fe3fc31ac3f69ab3e6bb19b75c6595966bd3b8f062149e7195fd1caa9ee21` |
| FY2024 public CSV used for independent audit, `qc_pub_fy2024.csv` | `45193eb7370463ab3067d71da23a580fec34a5460341e4e750dda0be061e1aa9` |
| FY2024 SAV used by the trained pipeline | `ab6420fa359ab9bcc280a21b9ba7b11172c79c6f7a661718bc6e318f97723fbb` |
| Extracted State Options panel, `snap_state_options_all_years.csv` | `3f3f035c7ded13996e43b1a43e7ec0e4a742bb17522d1f730edb0990aafe08cb` |
| Vendored BBCE registry, `analysis/data/state_bbce.csv` | `47c0255266f8fd62c6408697fc53b465c49f19004de8bf99c5c7d4f1def70b22` |
| Vendored Part B registry, `analysis/data/medicare_part_b_premiums.csv` | `b8f192092823e5158737fe412c63a1cad19c768d040fe5b5bc2aa229afb00afa` |
| Existing SMD registry | `83cc6023471474cc82bb45648b1cd39530379ea60f4194f8582ee45a1eb404ca` |

The model artifact pins every SAV used in training: FY2017 `18e0c7f9b42c26a1c70652d43e461ce0086bdf6749ed7534778bf8f0f5b71ea9`, FY2018 `02fcbb4ea4116a162f89e56efc930d1716371a29e0196c551ffd96da72b71e82`, FY2019 `0d8302b672529feb87b160d12297fe1adda1703eec0e3a4558f57e278ce12846`, FY2022 `c795aac12ea67937af3242593280fbc8dd3eb70938f56b7a7badbfd71ac74f5d`, FY2023 `9a1028e180028905e55edf3d72f028bc7740acfbc66cad1ccf935c6bb3fd2257`, and FY2024 as listed above.

The public CSV was used to independently audit FY2024 semantics and counts; the fitted pipeline continues to use the existing SAV inputs. The exact package versions, source hashes, threshold map, and random seed are serialized in `analysis/model_results.json`.

## F1 — certification cadence

### Verified semantics

The prompt's tentative description of `CERTMTH` as months into certification is not the file's actual definition. The codebook calls `CERTMTH` “MONTHS IN CERTIFICATION PERIOD” and defines it as the number of months in the current certification or recertification period (`techdoc.txt:L6420-L6437`). `LASTCERT`, not `CERTMTH`, is the constructed “MONTHS SINCE LAST SNAP CERTIFICATION” field (`techdoc.txt:L6504-L6514`). Accordingly:

- `months_since_cert = LASTCERT`.
- `cert_period_months = CERTMTH`.
- A timing row is structurally valid only when `CERTMTH > 0` and `0 <= LASTCERT < CERTMTH`.
- `near_recert = 1` for the final two months: `CERTMTH - 2 <= LASTCERT < CERTMTH`.
- `near_recert_elderly_or_disabled` is the requested interaction. `FSNELDER` counts participating adults age 60 or older (`techdoc.txt:L7202-L7218`), while `FSNDIS` counts participating people age 59 or younger defined as disabled (`techdoc.txt:L7114-L7131`).

The public-use file collapses missing data to one `.` representation (`techdoc.txt:L4787-L4791`). The restricted conventions are `-1` through `-6` (`techdoc.txt:L4797-L4843`), including `CERTMTH = -5/.D` when a unit participates in a month in which it is not certified (`techdoc.txt:L4832-L4837`; also `L1898-L1899`). The builder therefore treats public NaN and every negative restricted sentinel as missing, with separate source-missing and structural-inconsistency flags.

### Registry decision

No state-level elderly-cadence registry was built. The cited 24–48 month passages are case-identification rules for specific SSI-CAP projects: New Jersey 24 months; Arizona, Kentucky, and Virginia 36; Louisiana 36 or 39; NYSNIP 48 with a 24-month interim contact; and NYSCAP 36 (`techdoc.txt:L2918-L2942`). They do not define a general statewide elderly certification policy. Turning them into a state-wide registry would mislabel ordinary elderly cases, so F1 remains case-level.

### FY2024 coverage

Among 44,800 evaluation cases:

- `CERTMTH` is missing in 3 cases and `LASTCERT` in 28; the union of source-missing timing rows is 31.
- 623 observed rows have structurally inconsistent timing, principally `LASTCERT >= CERTMTH`.
- 44,146 rows have valid source values and timing; 6,148 are in the final two months (`13.9265%` unweighted among valid timing rows).
- The all-case weighted `near_recert` rate is `12.6737%`.
- Among cases with a positive period length, `27.7123%` have periods of at least 24 months; the corresponding elderly-or-disabled case-level rate is `54.4461%`. This is descriptive support for longer case-level cadences, not a state registry.

Implemented F1 model columns: `months_since_cert`, `months_since_cert_missing`, `cert_period_months`, `cert_period_months_missing`, `cert_timing_inconsistent`, `near_recert`, `near_recert_missing`, and `near_recert_elderly_or_disabled`.

## F2 — BBCE

### How `CAT_ELIG` enters

At the base commit, `CAT_ELIG` existed in the QC source but was absent from `REQUIRED_COLS`, discarded by `load_year`, and explicitly prohibited from the hurdle feature list. This round loads it only for a registry cross-check; it is still excluded from every model feature list.

That exclusion is semantic, not accidental. `CAT_ELIG=1` is traditional SSI/TANF cash/general-assistance categorical eligibility; code 2 includes BBCE conferred through noncash TANF/MOE; and code 3 includes both recoded pure cash-public-assistance units and cases meeting state BBCE criteria (`techdoc.txt:L6379-L6418`). Codes 2 and 3 therefore do not uniquely identify state BBCE adoption.

The FY2024 cross-check illustrates the problem:

- Registered BBCE states contain 37,485 QC cases, but only 26,214 have `CAT_ELIG` 2 or 3; the weighted rate is `68.0362%`.
- Non-BBCE states contain 7,315 cases, including 194 with `CAT_ELIG` 2 or 3; the weighted rate is `2.0011%`.
- Registry status and `CAT_ELIG` are complete for all FY2024 cases.

### State registry

The official sources are the [FNS State Options landing page](https://www.fns.usda.gov/snap/waivers/state-options-report) and the [16th-edition State Options Report](https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-16th-state-options-report-june24.pdf). The report says its 53-agency information is current as of October 1, 2023 and derives from FFY2024 State Plans of Operation (report p.5; PDF p.7). Its BBCE profile is report p.24 (PDF p.26).

The FY2024 registry has 44 adopting agencies. The nine nonadopters are `AK`, `AR`, `KS`, `MS`, `MO`, `SD`, `TN`, `UT`, and `WY`. A committed-data test locks both this exact complement and the historical adoption counts.

Historical mapping is explicit rather than silently interpolated:

| Model FY | Report edition/snapshot | Adopters | Limitation |
|---:|---|---:|---|
| 2017 | 13th, 2016-10-01 | 42 | Report snapshot |
| 2018 | 14th, 2017-10-01 | 42 | Report snapshot |
| 2019 | 14th, 2017-10-01 | 42 | Carried forward; no intervening edition |
| 2022 | 15th, 2022-10-01 | 44 | End-of-FY proxy one day after FY2022 ended |
| 2023 | 15th, 2022-10-01 | 44 | Report snapshot |
| 2024 | 16th, 2023-10-01 | 44 | Report snapshot |

FY2019 and FY2022 are temporal proxies and should be treated as a measurement-error/sensitivity limitation, not exact within-year adoption dates.

Implemented F2 model columns: `state_bbce`, `state_bbce_missing`, and interactions with the existing `elderly_or_disabled`, `has_earnings`, and `children` household indicators. `FSEARN` is the unit's earned-income field (`techdoc.txt:L7844-L7860`), and `FSNKID` counts participating children under age 18 (`techdoc.txt:L7286-L7300`).

### Raw-PDF SHA exception (closed at gate time)

The lane's sandbox exposed parsed official-PDF text while blocking raw-byte download, so it landed with `official_pdf_sha256` intentionally `null` and the extracted-panel and vendored-registry SHAs as disclosed fallback pins. The gate reviewer closed the exception on 2026-08-09: the raw PDF was downloaded outside the sandbox, its cover page verified as the USDA FNS 2024 16th-edition State Options Report, and its SHA-256 (`96b1e5c5b2b59cd15429f8d71d696254da75950f12358d492c0f8be23272c25c`) pinned in `train_error_model.py`, from which it flows into `model_results.json` provenance.

## F3 — Medicare Part B premium bands (Ben Molin)

### Verified semantics and sources

`YRMONTH` is a six-digit sample year/month field; FY2024 ranges from 202310 through 202409 (`techdoc.txt:L6835-L6853`). It therefore selects the calendar-year premium rather than assigning one premium to the whole fiscal year.

The official CMS sources record a standard Part B premium of [$164.90 for CY2023](https://www.cms.gov/newsroom/fact-sheets/2023-medicare-parts-b-premiums-and-deductibles-2023-medicare-part-d-income-related-monthly) and [$174.70 for CY2024](https://www.cms.gov/newsroom/fact-sheets/2024-medicare-parts-b-premiums-and-deductibles). The vendored registry covers every sampled calendar year: 2016, 2017, 2018, 2019, 2021, 2022, 2023, and 2024, with an official CMS URL for each. Its loader rejects fractional years, duplicate years, nonofficial source URLs, and missing sample-year coverage.

The band population is elderly households, defined as `FSNELDER > 0`; disabled-only households are deliberately excluded. `FSNELDER` is the count of participating adults age 60 or older (`techdoc.txt:L7202-L7218`).

`FSMEDEXP` is not gross medical expense: it is allowable expense in excess of $35 for elderly people or people with disabilities (`techdoc.txt:L9029-L9045`). For a positive claim, the builder reconstructs gross expense as `FSMEDEXP + 35` before comparison with the published premium. Zero does not reveal a gross amount within the first $35 and is therefore outside the band-applicable population.

The model features are:

- `premium_only`: reconstructed expense within `±$5`, inclusive, of the sample-month premium.
- `just_above_premium`: signed distance in `(+$5, +$50]`; exact `+$5` remains in `premium_only` so the indicators do not overlap.
- `medical_expense_distance_to_premium`: absolute dollar distance for applicable elderly claims.
- `part_b_premium_missing`: missing/unmapped calendar-premium flag.

### FY2024 coverage and Colorado overlap

All-case premium references are 11,003 cases at `$164.90` (October–December 2023) and 33,797 at `$174.70` (January–September 2024). These reference counts describe the full FY2024 evaluation file, not just band-applicable cases.

Among 2,054 elderly households with a positive reported excess medical expense:

- `premium_only`: 739 cases (`35.9786%`), weighted population `4,641,534.03`.
- `just_above_premium`: 595 cases (`28.9679%`), weighted population `3,398,127.03`.

The techdoc says SMD states standardize deductions for eligible elderly/disabled units with medical expenses above $35 and at or below a state threshold, and `MED_DED_DEMO` flags eligible households with positive countable medical expense (`techdoc.txt:L3213-L3227`). Its codebook defines `MED_DED_DEMO` as a 0/1 SMD-eligibility indicator (`techdoc.txt:L6535-L6561`). The FY2024 parameter table gives Colorado a `$200` gross threshold and `$165` deduction (`techdoc.txt:L37253-L37288`). This creates the requested censored-at-$165 QC class, operationalized as Colorado, `MED_DED_DEMO=1`, and `FSMEDEXP=165`.

There are 46 such FY2024 cases; 36 are elderly and 10 are disabled-only. Correctly restoring the $35 floor maps all 36 elderly cases to `$200` gross expense:

- `premium_only` overlap: `0/46` overall and `0/36` elderly.
- `just_above_premium` overlap: `36/46` overall (`78.2609%`) and `36/36` elderly (`100%`).
- Under the feature's same elderly-only applicability restriction, a deliberately naive comparison of literal `FSMEDEXP` with the premium would falsely classify `6/36` elderly cases (`16.6667%`; the serialized artifact reports that numerator as `6/46`, or `13.0435%`, against the full censored-class denominator). If both the `$35` reconstruction and the elderly-only restriction were ignored, the all-class literal overlap would be `10/46` (`21.7391%`: 6 elderly and 4 disabled-only).

This is why the gross-scale reconstruction matters: the Colorado standard is in Ben's `+$5` to `+$50` zone after reconstruction, not in the premium-only band.

## Pipeline integration and counterfactual discipline

The shared lists now contain 18 original burden intermediates plus 17 additive features. The classifier reports three specifications: covariates, frozen-definition burden-only, and burden plus all additive features. `model_results.json` is schema v3 and exposes `with_additive_features` explicitly; the legacy `with_intermediates` name remains an alias for the complete v3 intermediate set. `with_burden_intermediates` preserves the old comparison contract.

`analysis/hurdle_deviation_model.py` assembles the BBCE and Part B registries once and passes them into every year's feature build. Its `_feature_columns` consumes the expanded `INTERMEDIATES`, so the new columns enter stage 1, stage 2, and magnitude. The distributional pipeline inherits the same feature list for sign, nine quantiles, tail diagnostics, direct-crossing comparisons, and current/opposite-policy predictions.

The SMD scenario predicate is untouched. The base and regenerated `lever_definitions.smd` objects are byte-equivalent after canonical JSON extraction:

```text
feature: med_doc_required
policy_off_feature_rule: FSMEDEXP > 35 and elderly_or_disabled
policy_on_feature_value: 0
```

The scenario export adapter now reads the burden-only classifier row when describing the historical `+0.006` burden lift, preventing the additive result from silently changing that interpretation. The scenario itself still flips only `med_doc_required`.

There are no app source changes. The only `app/` changes are the two generated artifacts explicitly requested in the task: `app/public/model_data.json` and `app/public/model_scenarios.json`.

## Model results

### Official-error classifier

Train n is 217,656; FY2024 evaluation n is 44,800. Weighted evaluation prevalence is `13.39%`.

| Specification | ROC AUC | PR-AUC | Precision at 5% weighted budget |
|---|---:|---:|---:|
| Covariates + formula anchor | 0.760891 | 0.352256 | 0.476291 |
| Committed/refit burden baseline | 0.766626 | 0.355304 | 0.477608 |
| Burden + F1/F2/F3 | 0.767947 | 0.358093 | 0.481660 |
| Additive delta vs committed burden | **+0.001321** | **+0.002788** | **+0.004052** |

The refit burden-minus-committed deltas are exactly zero, so the comparison is not confounded by a changed split, seed, package set, or burden specification.

All additive-feature FY2024 weighted ROC-AUC permutation importances are reported below. Values near zero or below zero are retained rather than filtered:

| Family | Feature | Mean AUC decrease |
|---|---|---:|
| F1 | `cert_period_months` | +0.001931 |
| F1 | `months_since_cert` | +0.001335 |
| F1 | `cert_period_months_missing` | 0.000000 |
| F1 | `months_since_cert_missing` | 0.000000 |
| F1 | `near_recert_missing` | 0.000000 |
| F1 | `near_recert_elderly_or_disabled` | -0.000019 |
| F1 | `near_recert` | -0.000050 |
| F1 | `cert_timing_inconsistent` | -0.000074 |
| F2 | `state_bbce` | +0.001555 |
| F2 | `state_bbce_has_earnings` | +0.001320 |
| F2 | `state_bbce_children` | +0.000723 |
| F2 | `state_bbce_missing` | 0.000000 |
| F2 | `state_bbce_elderly_or_disabled` | -0.000063 |
| F3 | `premium_only` | 0.000000 |
| F3 | `part_b_premium_missing` | 0.000000 |
| F3 | `just_above_premium` | -0.000038 |
| F3 | `medical_expense_distance_to_premium` | -0.000053 |

Individual permutation importances are conditional predictive diagnostics with correlated features; they are not family ablations. In particular, the Part B indicators add essentially no isolated FY2024 classifier importance even though they are retained as requested.

### Hurdle discrimination

| FY2024 stage | Committed AUC | New AUC | Delta | Committed PR-AUC | New PR-AUC | Delta |
|---|---:|---:|---:|---:|---:|---:|
| Stage 1 raw | 0.835617 | 0.839738 | +0.004121 | 0.737311 | 0.748826 | +0.011515 |
| Stage 1 calibrated | 0.835483 | 0.839551 | +0.004067 | 0.730379 | 0.742935 | +0.012556 |
| Stage 2 raw | 0.723322 | 0.725410 | +0.002088 | 0.578422 | 0.582124 | +0.003702 |
| Stage 2 calibrated | 0.721820 | 0.724742 | +0.002922 | 0.565109 | 0.568257 | +0.003147 |

### State-rate calibration

The headline hurdle calibration remains unfactored FY2024. Frozen-factor rows train through FY2022, estimate factors out of sample on FY2023, and apply them unchanged to FY2024.

| Hurdle calibration | New slope | New intercept | Committed→new MAE | New RMSE | Committed→new correlation |
|---|---:|---:|---:|---:|---:|
| Unfactored, equal jurisdiction | 0.967 | +0.128pp | 1.827→1.714pp | 2.143pp | 0.507→0.567 |
| Unfactored, issuance weighted | 0.784 | +2.025pp | 1.454→1.355pp | 1.787pp | 0.458→0.500 |
| Frozen factor-adjusted, equal jurisdiction | 0.917 | +0.817pp | 0.885→0.875pp | 1.150pp | 0.906→0.909 |
| Frozen factor-adjusted, issuance weighted | 0.852 | +1.463pp | 0.785→0.808pp | 1.049pp | 0.878→0.886 |

The final factor-adjusted issuance-weighted MAE is slightly worse (`+0.0236pp`) even though correlation improves; this regression is retained rather than omitted.

For the frozen distributional dollar-rate validation:

| Dollar-rate calibration | New slope | New intercept | Committed→new MAE | New RMSE | Committed→new correlation |
|---|---:|---:|---:|---:|---:|
| Raw, equal jurisdiction | 1.223 | +0.203pp | 2.020→2.036pp | 2.612pp | 0.463→0.502 |
| Factor-adjusted, equal jurisdiction | 0.916 | +0.902pp | 0.928→0.931pp | 1.211pp | 0.901→0.903 |
| Raw, issuance weighted | 0.981 | +2.228pp | 2.282→2.361pp | 2.738pp | 0.410→0.447 |
| Factor-adjusted, issuance weighted | 0.856 | +1.543pp | 0.834→0.872pp | 1.131pp | 0.875→0.877 |

All four distributional MAEs worsen slightly while all four correlations improve. National observed/raw/factor-adjusted dollar rates are `7.223% / 5.092% / 6.638%`, versus the committed `7.223% / 5.207% / 6.717%`. Seven level-ratio gates remain flagged: `AK`, `HI`, `ID`, `MN`, `SD`, `VI`, and `WY`.

### Distributional coverage

Coverage uses 17,828 FY2024 deviators (Kish effective n `6,679.405`). Negative gap means undercoverage.

| Quantile | Committed gap | New coverage | New gap | >3pp |
|---:|---:|---:|---:|:---:|
| 0.050 | -0.25pp | 4.62% | -0.38pp | No |
| 0.100 | -1.71pp | 8.33% | -1.67pp | No |
| 0.250 | -3.85pp | 20.67% | -4.33pp | Yes |
| 0.500 | -6.10pp | 42.89% | -7.11pp | Yes |
| 0.750 | -6.89pp | 67.70% | -7.30pp | Yes |
| 0.900 | -7.44pp | 82.73% | -7.27pp | Yes |
| 0.950 | -5.27pp | 89.23% | -5.77pp | Yes |
| 0.975 | -4.47pp | 93.08% | -4.42pp | Yes |
| 0.990 | -3.41pp | 95.45% | -3.55pp | Yes |

All nine gaps remain negative and seven remain above 3pp. Mean absolute gap worsens from `4.3761pp` to `4.6438pp`; maximum absolute gap improves from `7.4442pp` to `7.3007pp`. The coverage result is therefore mixed-to-worse despite the classifier and hurdle discrimination gains.

## Artifact roll

| Artifact | Committed SHA-256 | New SHA-256 |
|---|---|---|
| `analysis/model_results.json` | `13fb3435fc270e3f14ac68bb4ccf43bcd63b10a4e651e8c7b1a3533848da2c4e` | `85a9581fade6eb84ba0d82ca7f5d7622d337e9af1ac0d8db5dc252778c552d57` |
| `analysis/hurdle_results.json` | `5dfc5a0ce201f471710ee8a6ae577b1a9dfd66eaaf83930fcec2e62e8293b567` | `6c7d0151fcf44ef6d0b2532ff987136a93721382192be1d64eba0d4813ab4d24` |
| `analysis/distributional_results.json` | `63dd70b6a541f9ed24c3d4e8beb2770ea50b8f2af653cb46e70aa3109330f2ad` | `f7ab8b1b41c01cdd142970086668112411cae799febd1d68773879daf9f48e12` |
| `analysis/FINDINGS.md` | `960ccb34f9d0f5edcaed068f5971784717e732ef0c6ae227b85b5a3a61d5a5f1` | `ffaf2854d06ad52b9e2f29ca82405dd52463ca028d718be625c58dec572d8186` |
| `app/public/model_data.json` | `412fc8c2b31f8b039ac844dd60e8e9e75a6fe6f831e8dd9cfdcaa1521b9da190` | `a39a926fae79eabf353f33b1cafb0ade8f5f31e307168b8c0c45eadbda65bfe6` |
| `app/public/model_scenarios.json` | `d6d3eafd372e63a4a91ef094a579b948c8886420fdef8f4ebd98e2e36a93e2a0` | `bf994ba1d145960943882243ed79c578c759be3d25795e653874e885863c19ce` |
| `analysis/MODEL_SCENARIOS.md` | `5aaa486dc08e0b159f7cad6aba1eaa2b6fd0aff3420d2cbff146729732e1aee6` | `1a1dee25b3cbc3ae9f0ad4d58a88dd13f44613dc43f3fde8761cd6d990e762ea` |

### Post-gate artifact refresh

Pinning the official-PDF SHA in `train_error_model.py` at gate time changed provenance metadata only. A full-pipeline rerun confirmed every other byte identical: `hurdle_results.json`, `FINDINGS.md`, `model_data.json`, and `MODEL_SCENARIOS.md` matched the "New" column above exactly, while three files moved solely through hash flow-through — `model_results.json` (the two provenance fields; now `47ed1afb587cc214d0edaecc92705eea54bcc9218fec06a12d7db7988ab96c59`), `model_scenarios.json` (its embedded `model_results` canonical hash; now `f68c7dc7f253ab419977b5c865559df200fcca69441922adfc1ea43f95ac88db`), and `distributional_results.json` (a gzip-size diagnostic, 50,000→49,997 bytes; now `47a41fa79ae281fbb6625ed42cad3cc1aa16bd4b4f5c03c17e5b9a4c0b0d7c58`). The app's `base_model.sha256` pin still equals the unchanged `model_data.json` hash. A deep JSON diff of all three changed files showed exactly four leaf differences, none numeric.

## Tests and deterministic gate

New synthetic guards cover:

- certification final-two-month boundaries, `LASTCERT == CERTMTH` inconsistency, restricted negative sentinels, and public NaN;
- BBCE full 53-agency coverage, binary values, historical counts, and the exact FY2024 nine-state nonadopter set;
- Part B exact calendar values, official CMS URLs, complete sample-year coverage, fractional-year rejection, FY2023/FY2024 selection, `$35` reconstruction, `±$5` and `(+ $5, + $50]` boundaries, missing month, and disabled-only exclusion;
- Colorado overlap for both premium bands;
- feature-list propagation and continued `CAT_ELIG` exclusion;
- scenario-export compatibility with the burden-only `+0.006` interpretation;
- generated-findings rendering of all three classifier specifications.

Commands and results:

```text
UV_CACHE_DIR=/private/tmp/snap-qc-uv-cache uv run --frozen --extra dev --extra analysis pytest -q
149 passed in 2.78s

UV_CACHE_DIR=/private/tmp/snap-qc-uv-cache uv run --frozen --extra dev --extra analysis ruff check snap_qc_sim analysis tests scripts_build_model_data.py scripts_build_model_scenarios.py
All checks passed!
```

The exact full-pipeline command was run twice:

```text
UV_CACHE_DIR=/private/tmp/snap-qc-uv-cache uv run --frozen --extra analysis python analysis/run_all.py
```

After the first run, all seven artifacts were copied to an isolated temporary directory. After the second complete run, `cmp -s` passed for every pair and the seven SHA-256 values matched the “New” column above: `BYTE_IDENTICAL=7/7`.

## Review and landing notes

No `fable` executable or in-repository fable integration was available (`command -v fable` returned no path). In its place, six independent read-only review passes covered the techdoc, public sources, pipeline wiring, feature semantics, test/export compatibility, and the final diff. Review findings that were fixed before landing included:

- restricting F3 to elderly households rather than disabled-only households;
- reporting the `just_above_premium` Colorado overlap and both denominators;
- preserving the burden-only scenario diagnostic after expanding `INTERMEDIATES`;
- adding public-NaN, disabled-only, exact-registry, findings-renderer, and scenario-adapter tests;
- bumping classifier results to schema v3 with an explicit additive-model key;
- rejecting incomplete or fractional-year Part B registries.

The final code review found no blocking correctness or wiring issue and approved landing subject to CI, determinism, and explicit disclosure of the FNS raw-PDF SHA exception. CI and determinism passed. Three task-process constraints remain disclosed rather than silently treated as passes: the raw official-PDF SHA could not be computed, `fable` was unavailable, and the requested external report destinations were not writable. None changes the model bytes, but each is an unmet or substituted process requirement.

The requested report destinations are outside this execution sandbox's writable roots. This report is therefore stored at the workspace-safe fallback `snap-qc-sim/FEATURES_REPORT.md` and committed with the feature round.
