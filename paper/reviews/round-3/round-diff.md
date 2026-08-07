# Round 3 — round-diff review (alignment-pass @ 084c6bb)

Reviewer: round-diff (adversarial subagent), 2026-08-07. Archived verbatim.

---

## Round-Diff Review — round 3 (alignment-pass @ 084c6bb)

Audit basis: HEAD moved mid-audit — commit 084c6bb ("Align paper, docs, and pipeline provenance with the model-primary release") landed at 14:16 while I was reviewing; it is byte-identical to the working tree I audited plus a deterministic pipeline rerun (`analysis/FINDINGS.md` and `analysis/distributional_results.json` each changed in exactly one provenance string, nothing numeric — itself evidence the byte-stability claim holds). All findings below are against 084c6bb. Tests: 111 passed at HEAD.

### Prior findings audit

**The round-3 claimed fix (the caller's brief):**

| # | Finding | Claimed fix | Actually fixed? | Evidence |
|---|---------|-------------|-----------------|----------|
| 1 | Stale validation claim: "within 3 points at seven of nine levels", tail 0.4674 (E3) | Replace with post-#13 values and disclose | **Yes — regenerated AND disclosed, not relabeled or silent** | Values genuinely moved with the refit: tail `scale_log` 0.271294 (`analysis/distributional_results.json` .magnitude_distribution.tail_fit), `coverage_flags_over_3pp = 7` (2 of 9 within 3pp), all nine gaps −0.2478…−7.4442, worst q.75 −6.890 / q.90 −7.444 — matching `paper/index.qmd:404-406` ("only two of nine… −0.2 to −7.4… worst at the 75th–90th percentiles") and `paper/FACTS.md:53` exactly. Disclosure exists in both required places: manuscript parenthetical `paper/index.qmd:409-412` ("An earlier version of this section described… seven of nine levels within 3 points… the fact catalog records the change") and the FACTS E3 SUPERSEDES note quoting the old claim verbatim ("within 3pp at 7 of 9, tail 0.4674"). The narrative also correctly reports the fix made coverage *worse*, running against the paper's convenience — the opposite of a cover-up. |

**Round-2 findings (round2-redteam, round2-methodology, round2-rounddiff regressions):**

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| 2 | FCA sentence wrong ($32M/six states, mis-cited) | **Yes** | `paper/index.qmd:148-150`: "&gt;$67 million… eight states over 2017–2021 [@doj2021snapqc]"; FACTS H1 added with the 8-state list; `doj2021snapqc`/`crs2018errors` in references.bib |
| 3 | Banned FSBEN gate in `snap_qc_sim/data.py`; data.json = 44,891 full file; headline artifact generator-less | **Yes — regenerated** | `snap_qc_sim/data.py:84-102`: CASE==1 filter, `AMTERR &gt; threshold` official gate, zero-weight drop; `app/public/data.json` sums 44,800, CO n=856; `paper/snapshot/labs/results_by_state_corrected.provenance.json` names generator (`examples/all_states.py` at d2e3972, seed 11, input SHA-256); `mc_tool.py` updated to the official gate |
| 4 | Exclusion taxonomy garbled (SSI cash-out/MFIP/missing fields) | **Yes** | `paper/index.qmd:193-196` + tbl-verify caption: "All exclusions are SSI-CAP… standardized-benefit units" |
| 5 | Abstract misstates model→simulator arc; "6,081 of 6,194 in-scope"; "fixed… errata" | **Yes** | Abstract now: simulator "resampling each state's own QC cases"; "all 6,081 in-scope cases of the 6,194-case official universe"; "surfaced and fixed two defects in the encodings and surfaced errata" (`paper/index.qmd:19-28`) |
| 6 | "Fact catalog maps every claim" false (missing rows) | **Yes** | FACTS H1–H8 added (FCA, MD 13.64/4.79, 1,037/406, 13.33/13.34 + ten jurisdictions, 50→25%, §10103, 110/195 split, 78.4/91.4) |
| 7 | 110/195 threshold split unreported; 78.4% vs 86.9% headline | **Yes** | Abstract quotes 78.4%/91.4%; `paper/index.qmd:284-330` reports 305=110+195, $18.5M/16%, 7.42% official-gate file rate, 21.6% upper bound, 33 ≤$5 cases — all match H7/H8 and the artifacts |
| 8 | "If anything, understated" signed the total with one component | **Yes (softened option)** | `paper/index.qmd:138-144`: between-component variance argument given, i.i.d. countervailing direction named, "likely, though not certainly, understated". Bracketing run still not performed (carried, disclosed) |
| 9 | 13.33% boundary arithmetic | **Yes** | `paper/index.qmd:46-47` "above 13.33% (13.34% at the published two-decimal precision)"; FACTS H4 |
| 10 | tbl-validate 0.51 mixed-pair cell | **Yes** | Table prints 0.52; artifact frozen equal-weight corr 0.5176; E5 now names both configurations and which one the manuscript quotes |
| 11 | README has no reproduction commands (round2-rounddiff regression 1) | **Partial** | README "Reproducing the paper" section exists with commands — but see finding R3 below: the `scripts_build_data.py` command as documented cannot work |
| 12 | No interpreter pin (regression 4) | **Yes** | `.python-version` committed; README cites it; manuscript `paper/index.qmd:642-644` |
| 13 | "Per-case outputs for all three layers" overclaim (regression 2) | **Yes** | Now "the complete per-case replay output (283 rows), the layer-1 and layer-2 classification outputs" (`paper/index.qmd:646-648`) |
| 14 | $43M vs $43.8M rounding residue | **Yes** | "(California by $44M)" `paper/index.qmd:529`; artifact delta $43.8M |
| 15 | Kane hospital-report-cards scope | **Yes** | Hospital clause removed; "school accountability ratings" only (`paper/index.qmd:502-503`) |
| 16 | giannella bib unpinned; C4 errata link | **Yes** | `references.bib`: "Commit 9b77be6, accessed 2026-08-07"; FACTS C4 now cites ANALYSIS.md + axiom.org report page |
| 17 | ANALYSIS.md lists uncommitted national CSV (regression 8) | **Yes** | `paper/snapshot/labs/amterr/fy2024_reconstruction_national.csv` now committed |
| 18 | Zero figures | **Yes (minimally)** | fig-co added; caption's 52%/48% split verified from the snapshot (0.52351/0.47649) |
| 19 | B3 83.65% vs artifact 83.64% | **Half** | Manuscript prints 83.64% ✓; `paper/FACTS.md:24` still says 83.65% (artifact: 0.836447) |
| 20 | τ²-estimation sentence; factor-uncertainty propagation; hurdle product statement; $1.255B vs $1.268B issuance label; negative-draw clip | **Not addressed / disclosure-only** | `paper/index.qmd:439-446` still omits τ² method; hurdle composition (`389-391`) still doesn't state stage-2 is conditional-on-deviators with the official probability as the product; issuance-base wobble unlabeled; `snap_qc_sim/simulate.py:80` documents consumer-side clipping only. All carried round-2 minors |

### Relabel-without-regenerate findings (CRITICAL)

**R1 — MAJOR. The revision leaves two stale sibling validation claims of the exact class it declares "all corrected here."**
- `paper/index.qmd:389`: "a sign model (calibrated AUC 0.700)". The current artifact has no such number: `analysis/distributional_results.json` sign.fy2024_among_deviators.auc_calibrated = **0.6861** (training OOF 0.6659); the repo's own generated `analysis/FINDINGS.md:140` prints 0.6861. 0.700 is the **pre-#13** artifact's value (0.69958 — verified via `git show 60c0ec2^:analysis/distributional_results.json`). It went stale in the *same event* (#13 refit) as the coverage claim this revision fixes, sits 15 lines above the fixed passage, and round2-methodology's receipt (line 18) proves it matched at round 2 — i.e., it staled silently afterward. `paper/FACTS.md:54` (E4) likewise still asserts 0.6996 with `distributional_results.json` as source; the cited artifact does not contain it.
- `paper/FACTS.md:56` (E6): "NY model mean 11.02% vs bootstrap 14.10%; CO 8.62 vs 9.98" — all four numbers are pre-#13 (present in `60c0ec2^`'s artifact, absent from the current one). The current pipeline doesn't even produce those quantities: the measured-rate block now anchors model mean to the official rate (FINDINGS.md:286, NY 14.090 = 14.090), and the level-gap disclosure moved to ratio form — NY raw model/observed **0.508**, CO **0.692** (FINDINGS.md:224, 194), i.e., the underprediction is now *more* severe than the quoted numbers say. This row was **edited in this very pass** (its conclusion tail was rewritten to describe the deployed gate) while its stale numeric core was retained — the description-fix pattern. It also still cites a nonexistent artifact key, `simulation_validation` (actual: `measured_rate_simulation`).
- Consequence: `paper/index.qmd:110-112` ("a validation claim that had gone stale against the corrected model pipeline, all corrected here") is **false as written** — one stale validation claim was corrected; two siblings from the same staleness event were not.

**R2 — MAJOR. The published render was never re-rendered: the deployed copy still contains the defect this revision exists to fix.**
`app/public/paper/index.html` (git-tracked, served at snap-qc-sim.vercel.app/paper/) line 396 still reads "within 3 points of nominal at seven of nine levels… (−0.3 to −3.5 points)… the simulator's model-based mode is disabled pending those fixes", and line 523 "the deployed model-based simulator mode is disabled" — while the same deployment's `app.js` now *serves* the model scenario. The render also carries "eleven adversarial reviews" (×3) and the old roadmap section. `app/public/paper/index.pdf` is likewise stale. Commit 084c6bb fixed the source (`paper/index.qmd`) without regenerating the tracked, published render — fix-not-propagated; if shipped as-is, the public artifact retains the stale claim and newly contradicts its own app.

### Regressions introduced

**R3 — MINOR. README reproduction command cannot work as documented.** README step 3 says `python scripts_build_data.py "$SNAP_QC_CSV" "$SNAP_QC_PER"`, but `scripts_build_data.py` accepts no argv and reads hardcoded paths (`scripts_build_data.py:8-9`: `/Users/maxghenis/.cache/axiom-oracles/snap-qc/…`; no `sys`, no `os.environ`). The arguments are silently ignored and the command fails off the author's machine. (`examples/all_states.py` does use argparse and is fine.) This is the residue of round-2's "answered by asserting the fix" pattern — the README section was added, but one of its commands is inoperative.

**R4 — MAJOR (internal inconsistency from a partial fix). Review count updated in one place, stale in three.** `paper/index.qmd:107` now says "three rounds of adversarial review," but line 631 says "eleven adversarial reviews," lines 648-649 "the eleven adversarial review reports under `paper/reviews/`," and line 663 "eleven independent reviews." `paper/reviews/` contains **15** archived reports (12 in round-1 including EDITORIAL.md, 3 in round-2), with round-3 adding more. The Disclosure's mitigation claim and the Availability section's file count are both factually wrong, and the paper now disagrees with itself about its own review history.

### Unresolved prior findings

- The two stale validation claims of R1 (sign AUC; E6 NY/CO numbers) — the direct siblings of the item this round fixed.
- FACTS-side residue: B3 83.65% (row 19 above); E9 "46 tests" (suite is 111) and its 2026-08-06 date, which predates the #13–#17 artifacts it now implicitly vouches for; the "five analysis-pipeline artifacts" of `paper/index.qmd:104` are never enumerated (`analysis/run_all.py:55-62` writes seven outputs; `qrf_benchmark_results.json` is produced by a separate script).
- Carried round-2 minors: τ² estimation sentence, factor-uncertainty propagation, hurdle product statement, issuance-base label, design-based SE bracketing (disclosed, not done).
- E5's source pointer "hurdle_results.json state_calibration" — no such key exists (values live under `calibration.fy2023_fit_factor_validation` and top-level `calibration_*`); values themselves verify exactly.

### New findings

- **NIT**: FACTS I5 / MODEL_SCENARIOS.md "25 of 53 CIs span zero": strict count is **24**; the 25th is IN, whose exported `ci_hi` is exactly 0.0 after 6-decimal rounding (`[-0.009323, 0.0]`). State the convention or say 24.
- **NIT**: `paper/index.qmd:410` "the pre-correction pipeline's coverage" — terminology collision: FACTS G reserves "pre-correction pipeline" for the pre-#7 banned pipeline, but the superseded 7-of-9 figure came from the corrected #7–#8 pipeline before the #13 refit. FACTS E3 says this precisely ("pre-#13"); the manuscript wording invites misattribution.
- **NIT**: FACTS I4 "decision rule fixed in the protocol commit before results" is unverifiable from main's squashed history (PR #15 landed protocol and results in one commit, ec5eed4); the artifact embeds `primary_rule` and the verdict follows it, but the temporal claim rests on PR-internal history.

### Verification detail for the caller's task list (all against committed artifacts at 084c6bb)

| Claim | Artifact value | Match? |
|---|---|---|
| Tail scale 0.2713 / "0.271" | scale_log 0.2712936 | ✓ |
| Coverage 2-of-9, gaps −0.25…−7.44, q.75 −6.89 / q.90 −7.44 | flags=7; −0.2478, −1.7052, −3.8539, −6.0953, −6.8902, −7.4442, −5.2685, −4.4675, −3.4122 | ✓ |
| QRF 4.0968/4.3761; 0.9512/0.9279; max 8.61/7.44; 229s/23s; both PIT; retain GBM; SHA 817d5925 ×2 | mean_absolute_gap 4.09680/4.37609; dollar_factored_equal_state_mae 0.951171/0.927881 (primary gate, GBM wins); max 8.6077/7.4442; runtime 228.8/23.5s; PIT mean-gap and CvM both GBM; `recommendation: retain_gbm`; core SHA reproduced | ✓ |
| CO SMD −$1.6M/−$1.85M/−$2.2M; CIs span zero 2 of 3; +$7.1M reverse; 53 flips; −$1.46→$0; 856 | −1,554,523 / −1,849,325 / −2,202,452; floor CI [−3.79M,+0.64M] and point [−4.06M,+0.33M] span zero, ceiling [−3.22M,−1.29M] doesn't; direction_reversed delta +7,120,882; med_doc flips 53/53/53; floor per-case-month −1.4618, ceiling 0.0; 856 cases | ✓ |
| Scenarios: 7 gated, [0.7,1.4], sha pin, deltas −0.111…+0.145, CO −0.0335 CI [−0.0773,+0.0044], refs −0.0727/−0.0433 inside | `level_ratio_gate.flagged_states` = AK,HI,ID,MN,SD,VI,WY; bounds [0.7,1.4]; base_model.sha256 = 412fc8c2… (= model_data export hash); delta_pp min VI −0.110683 / max WI +0.145339; CO baseline_to_patch −0.033515, CI = negated [−0.004383,+0.077315] → [−0.0773,+0.0044]; ceiling direct −0.072679 and hurdle-crossing −0.043266 both inside | ✓ (span-zero count nit above) |
| Duan 1.173; $183/$189; AUC 0.761→0.767; precision 47.8% @ 13.4% | smear 1.172514; 183.35/189.30; 0.760891→0.766626 (+0.005736/+0.003048); 0.477608, prevalence 13.39% | ✓ |
| Sign AUC 0.700 | **0.6861 / 0.6659 — MISMATCH** (see R1) | ✗ |
| tbl-validate 1.81/1.65/0.885/0.785/0.52/0.90 | frozen unfactored 1.8097/1.6466, corr 0.5176; factored 0.8851/0.7847, corr 0.9057 | ✓ |
| $609M/$1,310M; boundary table; audit deltas | Summed from `results_by_state_corrected.json`: 609M/1310M exact; ND 49.5→50/WA 48.3→48/CO 48.6→49/KS 46.8→47/NV 46.0→46 with all E[cost]/SD cells exact; MO +3.9/TN +3.7/IN +3.3/CA −30.3/PA −13.1/TX −13.1; CA SD −43.8→"$44M"; CO step $63.4M | ✓ |
| Abstract (6,081/6,194/113; 36,486 cells; 78.4/91.4; 46–50%) | tbl-verify rows sum exactly; 6,081×6=36,486; H8; boundary artifact | ✓ |
| App claims (Task 4) | One SMD lever only (`app/public/index.html:51-54`); SHA-256 pin verified at load (`app/public/app.js:314-320`); legacy accounting params explicitly ignored, levers removed (`app.js:266-268`); gate disables with ratio shown (`app.js:497-505`); "not a causal estimate" (`app.js:511`, `index.html:101`); observed resample = no-scenario engine. No overstatement: paper/FACTS say only *policy* lever, and the audit-volume slider is a measurement lever | ✓ |
| Reviews untouched (Task 5) | `git diff origin/main -- paper/reviews/` empty; `git log --diff-filter=M -- paper/reviews/` empty — no review file ever modified after archiving | ✓ |

### Verdict

**Major Revisions — narrowly.** The defect the caller asked about is genuinely fixed: values regenerated (0.4674→0.2713, 7-of-9→2-of-9, with the fix making the model look *worse*), disclosed in both the manuscript and a FACTS supersession note, reviews archived untouched, tests green, and round 2's majors are substantially and verifiably resolved. What blocks acceptance is that the fix was applied to one instance of a three-instance staleness event: the sign-AUC (index.qmd:389, FACTS E4) and E6's NY/CO numbers staled in the same #13 refit and remain, making "all corrected here" (index.qmd:112) false; the published render `app/public/paper/index.html`/`.pdf` still ships the pre-fix text and now contradicts the live app; and the "eleven reviews" count survives in three places against the new "three rounds." All are hours of work: fix E4/E6 + line 389 from the current artifacts (0.686; NY ratio 0.508 / CO 0.692), re-render `app/public/paper/`, sweep "eleven," and pick up the FACTS residue (B3 83.65%, E9's 46 tests, the E5/E6 pointer names, the 24-vs-25 convention, the `scripts_build_data.py` argv gap).

Key files: `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/index.qmd` (389, 107-112, 631, 648-649, 663), `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/FACTS.md` (24, 53-56, 59), `/Users/maxghenis/PolicyEngine/snap-qc-sim/app/public/paper/index.html` (396, 523), `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/distributional_results.json`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/FINDINGS.md` (140, 194, 224, 286), `/Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/counterfactual_co_smd.json`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/app/public/model_scenarios.json`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/app/public/app.js`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/snapshot/labs/results_by_state_corrected.json` (+ `.provenance.json`), `/Users/maxghenis/PolicyEngine/snap-qc-sim/scripts_build_data.py` (8-9).
