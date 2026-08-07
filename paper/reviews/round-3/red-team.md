# Round 3 — red-team review (revision-3 changed regions)

Reviewer: red-team (adversarial subagent), 2026-08-07. Archived verbatim.

---

## Red-Team Review

Repo: `/Users/maxghenis/PolicyEngine/snap-qc-sim`, branch `alignment-pass` (working tree = origin/main dee3ff4 + uncommitted alignment edits). Scope: revision-3 changes only. Verification method: every number below checked against committed artifacts; raw-file counts recomputed independently from the pinned QC CSV (SHA-256 verified `45193eb7…`); external hash pins re-hashed; live deployment fetched and byte-compared.

### Verdict: Major Revisions

### Headline finding
**FACTS E6 is a relabel-without-regenerate carrying superseded numbers and citing a nonexistent artifact key.** The row was revised this round (`paper/FACTS.md:56`) but keeps pre-#13 values — "NY model mean 11.02% vs bootstrap 14.10%; CO 8.62 vs 9.98" — that exist in **no current committed artifact**. The cited source, `distributional_results.json simulation_validation`, does not exist: the key is `measured_rate_simulation` (0 grep hits for `simulation_validation`; 0 hits for `11.02`/`8.62` in the current JSON). In the post-#13 artifact the model process is anchored to the official rate by construction (CO model mean 9.97 = official; NY 14.09 = official), so the quoted comparison is not derivable from the cited file at all — it derives only from the superseded artifact at commit e81dad7 (`measured_rate_simulation` rows: CO model 8.6204 vs observed 9.9759; NY 11.0218 vs 14.0989 — exact match to E6). The current pipeline's raw-level metric (`raw_model_to_observed_ratio`: CO 0.692, NY 0.508) implies a substantially *larger* raw gap than the stale numbers convey, so E6 understates the current defect. This sits directly under the section header retitled this round to "corrected pipeline: PRs #7–#8 **as refit by #13**" (`paper/FACTS.md:47`), and one row above E3, which was scrupulously superseded — making E6's silent carryover the exact failure mode E3's supersession note was written to prevent. Severity: **MAJOR**.

### Verification attacks

**Core claim verification (paper/index.qmd changed regions).**

| Claim | Source cited | Independent verification | Verdict |
|-------|--------------|--------------------------|---------|
| Coverage within 3pp at only 2 of 9 levels (index.qmd:404-405) | distributional_results.json | `coverage_flags_over_3pp = 7` → 2 within; per-row flags confirm (q.05, q.10 only) | VERIFIED |
| All nine gaps negative, −0.2 to −7.4pp (index.qmd:406) | same | `all_nine_negative: true`; gaps −0.2478 to −7.4442 | VERIFIED |
| Worst at 75th–90th percentiles (index.qmd:406-407) | same | q.90 −7.444, q.75 −6.890 are the two worst | VERIFIED |
| Tail refit at attachment depth, log scale 0.271 (index.qmd:401-402) | same | `scale_log 0.27129`, fit cutoff q.99 = attachment q.99 | VERIFIED |
| Physical caps; frozen FY2023-fit factors (index.qmd:402-403) | same | `physical_cap.rule = max(BENMAX, abs(RAWBEN−BENFIX))`; export config "frozen-through-FY2022 … FY2023-fit dollar factors" | VERIFIED |
| Earlier version claimed 7-of-9 within 3pp; tail 0.4674 (index.qmd:409-411; FACTS.md:53) | git history | Pre-#13 artifact (e81dad7): flags=2 → 7 within; gaps −0.30..−3.47; scale 0.46745 | VERIFIED |
| QRF mean abs coverage 4.10 vs 4.38; worse max gap (index.qmd:415-417) | qrf_benchmark_results.json | 4.0968 vs 4.3761; max 8.6077 vs 7.4442 | VERIFIED |
| QRF degrades PIT (index.qmd:418) | same | mean gap 0.0667 vs 0.0544; CvM 33.87 vs 21.63; both gates favor GBM | VERIFIED |
| QRF loses factored state comparison 0.951 vs 0.928 (index.qmd:419-420) | same | 0.95117 vs 0.92788 (dollar-rate route) — but see minor finding 7 | VERIFIED |
| Decision rule fixed in protocol code before results (index.qmd:413-414; FACTS I4) | protocol commit | origin/qrf-benchmark: rule at `qrf_benchmark.py:1326` and verdict logic in 3e1b347 (12:29); results added in child commit 1d06262 (12:46); diff between them touches only markdown rendering | VERIFIED (via un-squashed branch only; see nit 11) |
| Simulator serves model in exactly one place; hash-pinned export; 7 jurisdictions outside [0.7,1.4] disabled (index.qmd:420-426) | app.js, model_scenarios.json | `included_levers=["smd"]`; sole lever checkbox `index.html:53`; pin `412fc8c2…` matches distributional export `encoded_sha256` and is verified at load (`app.js:314-320`); `level_ratio_gate.flagged_states` = 7 (AK,HI,ID,MN,SD,VI,WY); gating at `app.js:459-505`; live site byte-identical to repo (app.js sha `6d8531da…`, model_scenarios.json sha `d6d3eafd…`) | VERIFIED |
| 46 records censored at exactly $165 (index.qmd:568-569; FACTS I1) | counterfactual_co_smd.json | In committed JSON assumption statements AND independently recomputed from raw pinned CSV: CO CASE==1 = 856; FSMEDEXP==165 = 46; MED_DED_DEMO==1 = 53; both = 46 | VERIFIED |
| SMD-off bounds −$1.46 to $0 per case-month (index.qmd:569-570) | COUNTERFACTUAL.md | Floor −1.4618 / point −1.0131 / ceiling 0.00, committed | VERIFIED |
| Model-implied −$1.6M to −$2.2M/yr; CIs span zero in 2 of 3 (index.qmd:571-574) | counterfactual_co_smd.json | −1.5545M / −1.849M / −2.202M; floor [−3.786,+0.641] and point [−4.057,+0.328] span zero, ceiling [−3.221,−1.289] doesn't | VERIFIED (−$1.6M for −$1.5545M is correct 1-dp rounding; nit 8) |
| Accounting-reverse +$7.1M (index.qmd:574-575) | same | `direction_reversed_smd_off_level_reference.expected_cost_share_delta = 7,120,882` | VERIFIED (see nit 9 on "same flip") |
| Chain never consumes CO SMD rule; reproduces all 856 exactly; adapter exact baseline invariance on 856 (index.qmd:561-567; FACTS I1/I2) | axiom-oracles artifacts (external) | **Not in any committed artifact.** Locally: all 9 cached files hash-match the COUNTERFACTUAL.md:56-66 pins; baseline manifest `certified_original_bridge_regression_guard` match 856/mismatch 0; floor manifest `baseline_invariance_check` case_count 856, divergence_count 0, byte_identical ×2 | CORROBORATED LOCALLY, UNVERIFIABLE FROM REPO (major finding 4) |
| I3 53 flipped cases; 10k bootstrap | counterfactual_co_smd.json | `med_doc_required_0_to_1_cases = 53` all variants; draws 10000 seed 202408; independent raw-file count 53 | VERIFIED |
| I5 deltas −0.111..+0.145pp; 25/53 CIs span zero; machine-readable exclusions; FY2024-registry validation; hash pin | model_scenarios.json | Recomputed from export: min VI −0.1107, max WI +0.1453; 25/53 span zero; `lever_definitions` carries per-lever exclusion reasons; registry assertion at `scripts_build_model_scenarios.py:152`; pin present | VERIFIED |
| I6 reconciliation (−0.0335, CI [−0.0773,+0.0044]; refs −0.0727/−0.0433 inside; 53=53; FY2022 vs FY2023 freeze) | MODEL_SCENARIOS.md § Colorado reconciliation + export `validation.co_smd` | All values match (`exported_not_minus_adopted_ci = [−0.077315, +0.004383]`); both reference points inside; note artifact records `exact_case_mask_verified: false` (count match only, which is all I6 claims) | VERIFIED |
| I7 deployed-app claims | app.js | CI displayed with draw count (`app.js:507-511`); "not a causal estimate" label; gated states show ratio (`app.js:501-503`); accounting levers removed (`app.js:266-268`); live site byte-matches repo | VERIFIED |

**Self-citation / unverifiable-source audit.**

| Citation | Type | Audit artifact found? | Values reproduce? | Verdict |
|----------|------|----------------------|-------------------|---------|
| FACTS E6 → "distributional_results.json simulation_validation" | committed artifact, wrong key | Key does not exist; values absent from current artifact | Only from superseded e81dad7 artifact | **STALE RELABEL — MAJOR** |
| FACTS I1/I2 → "axiom-oracles counterfactual artifacts" / "engine round-1b artifacts (hashed manifests)" | external, author-provenanced | Not committed; SHA-256 pins committed (COUNTERFACTUAL.md:56-66) | Yes, against local cache whose hashes match all 9 pins | **UNCOMMITTED ATTESTATION — MAJOR** (not fabrication; commit the ~21–31KB manifests) |
| FACTS I4 "reproduced across independent processes" | provenance claim | `qrf_benchmark.py:1420`: both repetitions are a for-loop in one process; no committed cross-process record | Determinism ×2 same-process reproduces; "independent processes" does not | **OVERSTATED — MINOR** |
| index.qmd:107-108 "three rounds … archived unedited in the repository" | repo-contents claim | `paper/reviews/` contains round-1 and round-2 only; the 2026-08-06 statistical review referenced at index.qmd:397-398 is archived nowhere | n/a | **CURRENTLY FALSE — MAJOR** (finding 3) |

**Cross-revision checks.**

| Change | Relabel or regenerate? | Values consistent across revisions? | Verdict |
|--------|------------------------|-------------------------------------|---------|
| E3 coverage claim (7-of-9 → 2-of-9, tail 0.4674 → 0.2713) | Regenerated (PR #13) with explicit supersession note | New values match current artifact; old values match old artifact | CLEAN — model correction done right |
| E6 NY/CO simulated-rate numbers | **Relabeled** (trailing text changed, source key renamed in prose, values untouched) | Values match only the pre-#13 artifact | **FAIL** (headline finding) |
| Boundary/counterfactual join after #13 | Regenerated (counterfactual-join commit "Regenerate counterfactual join on post-tail-refit main"; deltas unchanged for a stated mechanistic reason — crossing deltas derive from classifier stages, not the tail) | Yes | CLEAN |
| Generator prose strings (browser status) in distributional_deviation_model.py / run_all.py | Code edited, artifacts **not** regenerated in this tree | Committed FINDINGS.md:309 and distributional_results.json `export.browser_consumer_status` still say "model consumer remains disabled … app.js is unchanged" | **FAIL — MAJOR** (finding 2) |

### Falsification attempt on headline claim
Target: "weighted quantile coverage … within 3 points of nominal at only two of nine levels, all nine gaps negative (−0.2 to −7.4 points)" (index.qmd:404-406). I attacked it three ways. (1) Artifact consistency: values match `distributional_results.json`, `FINDINGS.md:146-153`, and the independently generated `qrf_benchmark_results.json` GBM path, whose equivalence check against the checked-in baseline passed at max delta 1.11e-16 across 41 metrics (QRF_BENCHMARK.md:21). (2) Internal arithmetic: every row satisfies coverage = nominal + gap; constant Kish effective n 6679.4 across levels is correct for a shared weight vector. (3) Mechanism attack: I asked why *central* levels deteriorated after a "tail refit" — and found the real driver: training deviators dropped 79,919 → 62,984 between revisions (FY2023 removed from magnitude training to fit factors out of sample), so the 7-of-9 → 2-of-9 comparison spans a training-window change, not only the three listed fixes. That is an interpretation gap (nit 10), not an error in the number. **I could not construct an argument that the corrected coverage claim is wrong; each component verified independently.** The revision's numerical core is solid — notably, the 46/$165, 53-flip, and 856 counts reproduce exactly from the pinned raw file, and the deployed site byte-matches the repo.

### Other damaging findings
- **MAJOR (blocking, mechanical): committed artifacts contradict the manuscript's deployment claims.** `analysis/FINDINGS.md:309` ("The hidden browser model consumer remains disabled and `app.js` is unchanged") and `analysis/distributional_results.json` `export.browser_consumer_status` ("model mode remains disabled … app.js is unchanged") directly contradict index.qmd:420-426, FACTS G/I7, and the live app. The alignment diff fixes the generator strings (`analysis/distributional_deviation_model.py:1570-1577`, `analysis/run_all.py:751-757`) but the regenerated artifacts are not in the tree (regen in flight at `analysis/.run-all-foj3r3fj/`). Until they land, the intro's byte-for-byte determinism claim (index.qmd:103-106) and FACTS E9 are false at this tree: a clean-room rerun necessarily produces different FINDINGS.md/distributional_results.json than committed. Do not merge revision 3 without the regenerated artifacts.
- **MAJOR: "three rounds of adversarial review — archived unedited in the repository" (index.qmd:107-108).** Two rounds are archived. Additionally, the attributed finding "a validation claim that had gone stale against the corrected model pipeline" (index.qmd:110-111) is not a finding of any archived review: round-2 verified the old coverage numbers as then-correct (`paper/reviews/round-2/round2-rounddiff.md`, M4), and the staleness was created by the authors' own PR #13 and corrected by this alignment pass. The sentence becomes true only if the round-3 archive — including whichever review actually surfaced the staleness — lands in the same PR; fix by archiving round 3 with this merge or reattributing the finding.
- **MAJOR: FACTS I1/I2's load-bearing attestations are not committed** (detailed in audit table above): the regression-guard 856/856 and the adapter invariance (856 cases, divergence 0, byte-identical ×2) live only in `~/.cache/axiom-oracles/v2b/cert-probe/simulations/fy2024/us-co/*/manifest.json`. The repo commits their hashes, and my local re-hash of all nine files matches every pin, with contents supporting the claims — so this is a verifiability gap, not fabrication; committing the five small manifests closes it.

### Findings below your threshold
- FACTS I4 "reproduced across independent processes": same-process repetitions only (`qrf_benchmark.py:1420`); reword or commit a second-process run record. (MINOR)
- Raw-facts engine leg has 11/856 benefit divergences (10 at −$23, 1 at +$22; baseline manifest diagnostics), disclosed only in the JSON field `feature_construction.baseline_anchor_reason`; the roadmap's "the pieces now run end to end" (index.qmd:559-560) plus I1's "raw-facts run" sourcing invite the wrong inference that the raw-facts leg reproduces all 856 exactly — only the supplied-intermediates certified chain does. One clause in prose would fix it. (MINOR)
- Two unlabeled "factored equal-state MAE" figures 11 lines apart — 0.928 (benchmark, distributional dollar-rate route, index.qmd:419-420) vs 0.885 (tbl-validate, hurdle case-rate route, index.qmd:430) — both correct, apparent contradiction unexplained. (MINOR)
- "roughly −$1.6M" for a −$1.5545M floor: correct at one decimal, but the flattering direction of the rounding is noticeable. (NIT)
- "the accounting-reverse bound for the same flip" (index.qmd:574-575): the +$7.121M figure is a constructed sign reversal of the v1 adoption lever's level shift ("not an existing one-sided lever output" per the committed artifact), i.e., same policy flip, different case mechanism; the adjacent "two mechanisms answer different questions" sentence mostly covers this. (NIT)
- The 7-of-9 → 2-of-9 coverage deterioration partly reflects the training-window freeze (79,919 → 62,984 training deviators), folded into "freezing fiscal-2023-fit state dollar factors" without saying the model now trains on less data. (NIT)
- The decision-rule provenance is evidenced only by the un-squashed `origin/qrf-benchmark` branch (protocol 3e1b347 → results 1d06262); main's squash destroys it — protect that branch or record the protocol commit hash in QRF_BENCHMARK.md. (NIT)
- Intro's unchanged clause "all five analysis-pipeline artifacts" (index.qmd:104-105) now sits over a pipeline managing seven outputs (`analysis/run_all.py:55-62`), and the clean-room reproduction it references is dated 2026-08-06, pre-#13; the count and the rerun date both want refreshing. (NIT)

Key files: `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/index.qmd`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/FACTS.md`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/distributional_results.json`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/FINDINGS.md`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/qrf_benchmark_results.json`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/counterfactual_co_smd.json`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/COUNTERFACTUAL.md`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/app/public/app.js`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/app/public/model_scenarios.json`.

---

## Editorial resolution note (author, appended at archive time)

Finding 2 (committed artifacts contradicting deployment claims) was resolved by
commit 084c6bb, which landed the regenerated FINDINGS.md and
distributional_results.json minutes after this reviewer snapshotted the tree —
the "regen in flight" staging directory it observed was that run. The remaining
MAJORs (E6 stale relabel, round-3 archive, engine-leg manifests) and the minors
are addressed in the revision-3 fix pass recorded in the same PR.
