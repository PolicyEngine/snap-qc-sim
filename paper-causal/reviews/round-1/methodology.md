# Methodology referee findings

Scope: `paper-causal/index.qmd` at `5cf9345`, checked against the four frozen protocols and the requested committed JSON artifacts. The three branch artifacts are byte-identical to `main@4aafd06`; `paper-causal/_fixed_donor_results.readonly.json` is byte-identical to `main@4aafd06:analysis/fixed_donor_decomposition_results.json`.

## Findings

1. **blocker — CONFIRMED — The manuscript calls the donor states “never-migrated,” but the design establishes only that the registry does not list a dated or candidate migration.** This occurs in the abstract (line 8), introduction (line 37), and conclusion (line 260). Both event protocols define pools by absence from `analysis/system_migrations.json`; they do not establish that every donor never migrated. Line 248 concedes that a missed migration remains in the pool. The stronger label is therefore unsupported and directly overstates the comparison design.

2. **blocker — CONFIRMED — The abstract assigns an inferential conclusion to descriptive channels.** Line 8 says “information-disregarded, worker, and data-entry error do not separate from the donor.” Only information-disregarded clears the count gate and receives permutation inference. Worker/user and data-entry are descriptive under `UHIP_DECOMPOSITION_PROTOCOL.md`; their artifacts contain effect sizes but no p-values or verdicts. “Do not separate” is not supported for those channels.

3. **blocker — CONFIRMED — The billed-period alignment is stated as an exact fiscal-year match when it is not.** Lines 8, 47–50, 150, and 256 say FY2017–19 are “the fiscal years” or “the years” FNS billed. `system_migrations.json` gives September 2016 through December 2019. That interval touches FY2016 and FY2020 as well as fully covering FY2017–19. The protocol did pre-name FY2017–19 and marks the profile descriptive and verdict-inert, but the artifact does not support the manuscript’s exact calendar equivalence.

4. **major — CONFIRMED — Informal “null” and “refusal” labels blur the frozen verdict vocabulary.** Lines 54, 83, and 256 summarize “one signal, one null, and one refusal/three verdicts.” Both Kentucky and Oregon artifacts actually return `no_protocol_defined_signal`; “refusal” describes why Oregon fails the rule, while “null” can be read as an evidentiary null. The body later supplies the exact verdicts and limitations, but the headline taxonomy is not the protocol taxonomy.

5. **major — CONFIRMED — “Signal under both estimators” obscures the joint-fit parent-rule verdict.** Lines 258 and 260 call the mass-change result the “same mass-change signal” under both. The joint-fit artifact returns `no_protocol_defined_signal` under the parent rule and `signal_family_adjusted`; the fixed-donor artifact returns both `signal` and `signal_family_adjusted`. Line 212 and Table 7 disclose the distinction correctly, but the conclusion collapses it.

6. **major — PLAUSIBLE — The decomposition language sometimes moves from QC classification to mechanism.** Lines 58–62 say the codes distinguish “a system that computed wrong,” workers unable to drive it, information dying in a queue, and “batch actions computed wrong at scale.” The artifact establishes reviewers’ code choices, not those operational facts. Lines 69–70 and 204 correctly impose the coding-practice ceiling, so the risk is localized but quotable.

## Verified without finding

- All reported effects, RMSPEs, donor weights, ranks, p-values, case counts, weighted-dollar totals, overlap amounts, sensitivity estimates, and internal-layer shares match their stated artifact keys at the displayed precision.
- The manuscript accurately states joint nonnegative unit-sum fitting, donor-preperiod-SD scaling, post-minus-pre gap aggregation, absolute permutation ranking, ties against signal, the plus-one rule, and denominators 43/35.
- FY2016 and FY2021 treatment, Oregon’s four/eight-month split, and Oregon’s registry and delay-roster exclusions match the protocols.
- Table 7 applies `signal`, `no_protocol_defined_signal`, and `signal_family_adjusted` correctly. The fixed-donor reproduction check matches effect, p-value, rank, and denominator exactly.
