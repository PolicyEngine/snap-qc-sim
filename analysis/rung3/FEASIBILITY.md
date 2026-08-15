# Rung-3 feasibility read

## Executive finding

Rung 3 is **JOIN for the survey spine and state-year context, DERIVATION/ENGINE COMPUTATION for the statutory benefit chain, and IMPUTATION for the QC operational layer**. It is not a join-only exercise. Microcosm supplies state, SPM-unit links, calibrated weights, household composition, income primitives, some medical/child-care/housing inputs, and an imputed SNAP take-up flag. It does not carry certification timing, expedited-service status, actual-utility/SUA treatment, or QC adjudication records. Several deduction inputs are only proxies or engine-derived values, not observed QC deductions.

The central unit mismatch matters: Microcosm's SNAP modeling grain is the CPS Supplemental Poverty Measure (SPM) unit, falling back to household only when an SPM identifier is unavailable (`packages/microcosm-frame/src/microcosm/frame/units.py:120-145`, `packages/microcosm-frame/src/microcosm/frame/units.py:210-252`). Its own test notes that an actual SNAP unit can be a subset of an SPM unit (`packages/microcosm-build/tests/test_us_fiscal_targets.py:1209-1213`). Therefore even apparently present size and income fields are not an exact record-level QC join.

The detailed machine-readable inventory is in `gap_table.json`. “PRESENT” below and in that file means the cited Microcosm field is actually built; it does not mean identical to the QC administrative concept.

## Scope and revisions

This read used Microcosm `b420d4ed07a389ffc8fbe0efc4a23add2d7946e9` and the local `main` checkouts of `snap-qc-sim` and `snap-fy27-margins`. No repository was modified. Microcosm defines the frame as typed entity tables, links, and weights (`DESIGN.md:44-75`), and reserves calibrated-weight production to its calibration layer (`DESIGN.md:107-115`). The consumer defines rung 3 as a Colorado-first Microcosm × benefit-engine × error-model prototype, calibrated to official components and checked against FY2024→25 movement (`analysis/MICROSIM_ROADMAP.md:83-101`).

## Universe and weights

### Unit, source, and vintage

The US build starts from pooled raw Census CPS ASEC files and constructs a unit frame (`packages/microcosm-build/src/microcosm/build/us_runtime/asec_pool.py:1-8`). It assigns native `SPM_ID` membership and falls back to household membership where needed (`packages/microcosm-frame/src/microcosm/frame/units.py:120-145`, `packages/microcosm-frame/src/microcosm/frame/units.py:210-252`). The wider production design stacks ASEC and ACS spines, samples whole households, and assembles them before fitted operators (`DESIGN.md:117-144`); housing values such as rent are fitted from ACS donors rather than observed on the ASEC SNAP unit (`packages/microcosm-build/src/microcosm/build/us_runtime/housing_inputs.py:1-20`, `packages/microcosm-build/src/microcosm/build/us_runtime/housing_inputs.py:275-400`). Reported SNAP comes from CPS `SPM_SNAPSUB` and is aggregated to the SPM unit (`packages/microcosm-build/src/microcosm/build/us_runtime/cps_carried.py:41-48`, `packages/microcosm-build/src/microcosm/build/us_runtime/cps_carried.py:306-327`).

The exact pooled survey-year list for the pinned release is **UNKNOWN** from a locally materialized release artifact: no downloaded Microcosm dataset/manifest was present. The builder anchors its design weights to a target ASEC year and scales `HSUP_WGT` by 0.01 (`packages/microcosm-build/src/microcosm/build/us_runtime/asec_pool.py:38-40`, `packages/microcosm-build/src/microcosm/build/us_runtime/asec_pool.py:78-155`, `packages/microcosm-build/src/microcosm/build/us_runtime/asec_pool.py:384-408`). A release manifest or successful local release build would resolve the exact source years.

### Colorado record count

The number of unweighted Colorado Microcosm SNAP/SPM units is **UNKNOWN**. Source code alone does not determine the realized row count, and no pinned built dataset was available locally. It should be reported as two counts when the artifact is available: Colorado SPM units and Colorado units with `takes_up_snap=true`; conflating those would confuse the survey frame with modeled participation. The take-up stage explicitly works at SPM grain and uses engine eligibility, state, reported SNAP, and weight (`packages/microcosm-build/src/microcosm/build/us_runtime/snap_state_take_up.py:101-170`).

### Calibration targets

Microcosm creates a state SNAP target table from FY2024 FNS average-monthly household facts (`tools/build_us_fiscal_refresh_release.py:3442-3485`). It computes a state take-up rate as the FNS household target divided by weighted eligible SPM units, then assigns reported recipients plus calibrated draws (`packages/microcosm-build/src/microcosm/build/us_runtime/snap_state_take_up.py:186-211`, `packages/microcosm-build/src/microcosm/build/us_runtime/snap_state_take_up.py:225-305`). Thus a per-state caseload target exists.

The broader fiscal target surface contains both SNAP dollars and household caseload, but at different grains: the parity manifest identifies CBO SNAP dollars and FNS state household caseload (`tools/build_us_target_parity_manifest.py:179-194`). Microcosm explicitly prohibits treating survey benefit amounts as calibration targets while allowing administrative benefit targets (`DESIGN.md:270-285`). The evidence read therefore supports **state caseload calibration plus a broader/national SNAP-dollar constraint**, not state issuance calibration. Exact Colorado target dollars are not shown.

The local FY2024 QC file has 856 Colorado sampled cases. With `CASE==1`, its monthly-sample weight sums to 3,663,355.009 case-months, or **305,279.584 average monthly cases**. `sum(HWGT × RAWBEN)` is **$1,267,963,387.75 annualized issuance**, and the weighted mean monthly benefit is **$346.12**. The loader's participating-case, raw-benefit, weight, and status semantics are explicit (`snap_qc_sim/data.py:74-111`); the modeling code describes `HWGT` as a monthly-sample weight (`analysis/cause_shares.py:302-305`).

The ratio of the Microcosm Colorado target to QC caseload is **UNKNOWN**, because the actual target value is not embedded in the checked-out source or a local release artifact. Resolve it by reading the Colorado row of the materialized FY2024 FNS target table and divide by 305,279.584. A state issuance ratio is not applicable because no state issuance calibration target was demonstrated.

## Aging and forward weights

Microcosm's target-aging module ages **calibration target dollar leaves**, not individual survey records. Its documented factor policy is: AGI, wages, net capital gains, qualified dividends, and net business income use matching CBO series; observed SOI years chain actual SOI growth and projected years chain CBO growth; other eligible dollar leaves fall back to AGI; count targets are not aged; and unavailable leaves remain unaged (`packages/microcosm-build/src/microcosm/build/us_runtime/target_aging.py:29-53`, `packages/microcosm-build/src/microcosm/build/us_runtime/target_aging.py:90-179`, `packages/microcosm-build/src/microcosm/build/us_runtime/target_aging.py:430-455`). No read code demonstrated a general record-level uprating of earned income, unearned income, rent, utilities, medical costs, dependent care, or child support.

At this revision, **Microcosm does not produce FY2026 or FY2027 SNAP-unit weights as a shipped mechanism demonstrated by the read source**. Future weights would require compiling a future target surface and rerunning calibration; source support for target aging is not itself proof that those releases exist. Consequently Microcosm does not, today, replace the margins project's C1→C4 pipeline.

The margins pipeline does the following:

1. C1 constructs forward caseload, issuance, and composition margins from administrative actuals against a CY2024 baseline (`snap-fy27-margins/README.md:12-15`).
2. C3 reweights every FY2024 QC case for FY2026 and FY2027, anchoring case-month levels and three case shares plus five age shares; it emits `new_weight` and `ratio=new_weight/HWGT` (`snap-fy27-margins/reweight/build_reweight.py:1734-1746`, `snap-fy27-margins/reweight/build_reweight.py:2007-2017`, `snap-fy27-margins/reweight/write_parquet.py:7-34`).
3. C4 uses published FY2026 and estimated FY2027 SNAP parameters to reprice the same QC records (`snap-fy27-margins/reprice/build_reprice.py:449-463`, `snap-fy27-margins/reprice/build_reprice.py:643-717`).

What C1→C4 does that Microcosm does not: retain the QC case universe and its adjudicated deductions; impose explicit FY2026/27 administrative caseload/composition paths; produce per-QC-case future weights; and use an audited standalone SNAP chain with published/projected parameter files. What Microcosm does that C1→C4 does not: construct a general-purpose household/SPM population, model eligibility and take-up, fit missing survey variables, and jointly calibrate a broad fiscal target surface (`DESIGN.md:117-144`, `packages/microcosm-build/src/microcosm/build/us_runtime/snap_state_take_up.py:225-305`).

Policy parameters can age when an engine is evaluated for the requested period; they are not survey uprating. Microcosm's adapter materializes engine variables for a specified period (`packages/microcosm-frame/src/microcosm/frame/adapters/policyengine_us.py:726-768`). Whether every SNAP rule needed for the seven-state chain is encoded for FY2026/27 in the selected engine version remains **UNKNOWN until a parity run is made**.

## Engine hookup

The repository-level interface rule is unambiguous: use `policyengine.py` as the interface to current models, and put net-new models in `rulespec-*` (`/Users/maxghenis/PolicyEngine/CLAUDE.md:3-20`). Microcosm's design describes a `RulesEngine` protocol with a PolicyEngine-US adapter today and rulespec-us as future (`DESIGN.md:78-94`).

The concrete current general interface is `PolicyEngineUSLatest` in policyengine.py (`/Users/maxghenis/PolicyEngine/policyengine.py/src/policyengine/tax_benefit_models/us/model.py:39-45`), invoked through the package's `Simulation` path (`/Users/maxghenis/PolicyEngine/policyengine.py/src/policyengine/core/simulation.py:20-45`, `/Users/maxghenis/PolicyEngine/policyengine.py/src/policyengine/core/simulation.py:130-149`). Its US model constructs PolicyEngine-US `Microsimulation` objects (`/Users/maxghenis/PolicyEngine/policyengine.py/src/policyengine/tax_benefit_models/us/model.py:140-199`). Microcosm's internal adapter can materialize requested variables into the frame (`packages/microcosm-frame/src/microcosm/frame/adapters/policyengine_us.py:726-768`).

Version status is awkward: Microcosm's lock resolves `policyengine-us==1.764.6` (`uv.lock:1362-1375`) when its US extra is installed, while the local policyengine.py checkout declares package version 4.18.8 and `policyengine-us==1.752.2` (`/Users/maxghenis/PolicyEngine/policyengine.py/pyproject.toml:6-7`, `/Users/maxghenis/PolicyEngine/policyengine.py/pyproject.toml:48`). Neither was installed in the inspected Microcosm environment. Therefore the executable adapter/version for this prototype is **UNKNOWN until an environment is selected and locked**; the repository lock versions are not evidence of the active runtime.

The seven-state-verified chain currently lives in QC replay code, not in rulespec-us: it consumes household size, earned and unearned income, medical, dependent-care and child-support deductions, rent, utility allowance, homeless-deduction claim, and elderly/disabled status (`snap-fy27-margins/reprice/build_reprice.py:643-717`, `snap-fy27-margins/reprice/build_reprice.py:774-788`). `FSGRINC`, `FSERNDED`, `FSSTDDED`, `FSSLTDED`, `FSNETINC`, `BENMAX`, and `FSBEN` are comparison/intermediate outputs, not inputs (`snap-fy27-margins/reprice/build_reprice.py:791-818`). `BENFIX`, `RAWBEN`, and their adjudicated gap are also not engine inputs.

Recommended hookup finding, not implementation: form an SPM-unit input table from Microcosm, impute the missing chain inputs, call the verified `calculate_case` chain as the parity oracle, and independently run the policyengine.py `Simulation` interface. Do not call PolicyEngine-US directly in new consumer code. Promote the policyengine.py route only after exact seven-state parity. No local rulespec-us implementation was found.

## Calibration semantics

The error model loads participating cases, defines signed deviation as `RAWBEN-BENFIX`, and builds the formula context from `FSBEN` (`analysis/train_error_model.py:1-13`, `analysis/train_error_model.py:295-342`). The target builder emits official state-year overpayment, underpayment, and total **rates**, plus FY2024→25 wedges (`analysis/build_component_targets.py:138-183`, `analysis/build_component_targets.py:243-269`). Colorado is 7.91% over / 2.06% under / 9.97% total in FY2024 and 8.52% / 1.57% / 10.09% in FY2025 (`analysis/component_targets.json:1`).

Calibration therefore requires state as an input/context field and the simulated error direction as a **model output**: positive deviation/overpayment, negative deviation/underpayment, and zero/no error. `component_targets.json` has no separate ineligible-case component target. “Component sums” must be constructed as weighted modeled dollars by direction and normalized consistently to the official rate definition; the JSON itself supplies rates, not dollar sums.

## Feature lift and sequencing

The augmented model's leading reported importances are `net_share_of_gross` (0.0539), `ben_rel_max` (0.0262), `deductions_per_member` (0.00916), then certification and BBCE features (`analysis/model_results.json:1`). The feature report says the additive blocks provide modest aggregate lift and documents the certification, BBCE, and Medicare constructions (`analysis/FEATURES_REPORT.md:8-14`, `analysis/FEATURES_REPORT.md:49-77`, `analysis/FEATURES_REPORT.md:79-154`). This ordering makes engine completeness and deduction composition higher priority than certification despite the roadmap's operational emphasis.

Sequenced work, with every duration explicitly an **estimate**:

1. **Unit contract and engine parity — estimate: 3–5 lane-days.** Freeze SPM-unit membership, period, state, and weight semantics; map present inputs; compare the replay oracle with policyengine.py for the seven verified states. This exposes whether “derivable” values are definition-compatible.
2. **Shelter/utility and deduction composition — estimate: 7–12 lane-days.** Rent is fitted, but utility/SUA treatment is absent; medical, dependent-care, and child-support need QC-definition-compatible values. This unlocks deductions per member, deduction count, utility actuals, net share, and benefit-position features—the highest-lift cluster.
3. **Certification timing — estimate: 4–7 lane-days.** Impute `CERTMTH` and `LASTCERT` jointly, constrained by state/program recertification rules and QC distributions. Do not independently sample the two fields.
4. **Expedited service and categorical eligibility — estimate: 3–6 lane-days.** Model `EXPEDSER`; derive BBCE from a versioned state-year registry; separately model case-level categorical eligibility if retained. BBCE itself is a trivial state-year join, but its interaction features depend on reliable earnings/children.
5. **Medical documentation and self-employment detail — estimate: 3–6 lane-days.** Medical primitives exist, but QC allowable/documentation concepts do not; self-employment record count is only approximately derivable from persons.
6. **Error outcome generation and calibration — estimate: 5–9 lane-days.** Generate direction and magnitude, then calibrate weighted over/under rates to official components and validate the FY2024→25 Colorado wedge. Do not impute `BENFIX`, `RAWBEN`, or `STATUS` as ordinary covariates; they are labels/outputs.
7. **Future-year population path — estimate: 6–12 lane-days.** Either port C1/C3 margins onto Microcosm units or compile, audit, and calibrate explicit FY2026/27 Microcosm targets. Target aging alone is insufficient.

Total, allowing overlap but not pretending away parity work: **estimate: 24–45 lane-days** for a defensible Colorado prototype.

## Verdict by cluster

| Cluster | Verdict | Reason |
|---|---|---|
| State, period, survey weight, basic demographics | JOIN/DERIVE | State and age are present; SPM membership and calibrated weights exist, but the unit differs from the QC assistance unit. |
| Earned/unearned income and benefit-chain intermediates | DERIVE/COMPUTE | Survey income primitives feed the engine. `FSBEN`, `BENMAX`, `FSGRINC`, `FSNETINC`, and statutory deductions are outputs, not carried attributes. |
| Rent and basic expense primitives | DERIVE | Rent is fitted from ACS; medical and child-care primitives exist. Exact QC definitions require validation. |
| Utility/SUA, homeless claim, deduction composition | IMPUTE | The actual-utility flag and QC-grade deduction components are not demonstrated. |
| Certification, expedited service | IMPUTE | No Microcosm fields were found. |
| BBCE | JOIN | State-year registry join; not a household imputation. Case categorical eligibility is distinct and absent. |
| `RAWBEN`, `BENFIX`, `AMTERR`, `STATUS`, element findings | MODEL OUTPUT/TRAINING ONLY | These are QC adjudication outcomes; the engine should compute formula benefits, and the error layer should generate deviations/direction. |
| FY2026/27 weights | NEW CALIBRATION/REWEIGHTING | No pinned Microcosm future-weight product was demonstrated. |

Bottom line: **the Colorado prototype is feasible, but it is an imputation-and-parity project built on a joinable survey spine—not a straightforward join.**
