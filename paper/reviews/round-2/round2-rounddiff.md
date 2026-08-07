All verification legs are complete. Here is the report.

---

## Round-Diff Review: round-1 resolution audit (paper branch @ 27e1b09)

Verification method: every number recomputed from committed artifacts (not prose); the corrected simulation artifact reproduced computationally under both candidate error gates; amterr replay artifact counted row-by-row; all greps against `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/index.qmd`; render and test suite executed.

### Prior findings audit

#### referee-redteam.md

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| M1 | "Every fiscal 2024 QC case" false (6,081 vs 6,194) | **RESOLVED** | Abstract now "6,081 of 6,194 in-scope... (113 documented exclusions)"; body index.qmd:177-185; new `@tbl-verify` (index.qmd:190-203) per-state counts match the reviewer's file counts exactly (NY 847/885, TX 906/955, MD 722/745, AZ 922/925; 113 total). `grep "every case"` = 0 hits. |
| M2 | Parity target misdescribed; scope caveat incomplete; abstract violates FACTS G | **RESOLVED body / PARTIAL abstract** | sec-oracle-scope (index.qmd:205-263) now states the FSBEN/Minimodel target, the $5 consistency-editing cascade, passing-default eligibility screens, the cross-model kinship ("closer in kind to the cross-model comparisons this method extends"), and moves RAWBEN/BENFIX to sec-decompose. "reviewer arithmetic" and "adjudicated by" = 0 hits. **Abstract**: carries the edited-chain scope ("the file's benefit-computation chain") and the universe scope, but not C2's supplied-intermediates clause — under a strict reading of FACTS G ("parity claims always carry the C2 scope caveat") the abstract is still short a clause (~5 words, e.g. "from file-recorded intermediates"). |
| M3 | 86.9% replay has no committed artifact | **RESOLVED** | `paper/snapshot/labs/amterr/amterr_replay_results.json`: 283 rows; I counted 246 `within5`, 37 residual (86.9%/13.1%), and `solver_within5 == within5` on 283/283 rows — the partition-identity claim verifies. `reconstruct_co_fy2024.R`, `amterr_replay.py`, `ANALYSIS.md`, `co_fy2024_reconstruction.csv` (283 rows), `native_decomposition.json` all committed at 27e1b09. FACTS D2/D4 re-pointed. Caveat: see New defect 2. |
| M4 | Coverage direction sign-flipped | **RESOLVED** | index.qmd:368-373: "all nine gaps are negative (−0.3 to −3.5 points): systematic *under*-coverage... understates mid-upper magnitudes, coherent with the $183-versus-$189 comparison." Matches FACTS E3 and `distributional_results.json`. |
| M5 | Boundary flip percentages untraceable (CO/NV) | **RESOLVED — regenerated, not relabeled** | Recomputed from `paper/snapshot/labs/results_by_state_corrected.json`: ND 49.54→50%, WA 48.34→48%, CO 48.59→49%, KS 46.77→47%, NV 46.00→46% — all match `@tbl-boundary` and FACTS F1 exactly. Gate test (below) confirms the artifact was genuinely regenerated under the official gate. |
| minors | hundreds-of-millions abstract claim; 13.1% units; matched MAE pairs; CA "near zero"; 5,136 double-count; cert 37 | RESOLVED | Abstract rewritten; "13.1% case share" (index.qmd:310); tbl-validate uses matched frozen 1.81/1.65→0.885/0.785; "California +0.11... but −1.40 on the stable denominator" (index.qmd:410-411); "5,136 cells including the 856 benefit cells" (index.qmd:257); CERT_REPORT.md:40 says 37. |
| minor | Abstract implies techdoc errata were "fixed" | **UNRESOLVED (carried over)** | New abstract: "a process that surfaced and fixed two defects in the encodings and errata in the federal technical documentation" — "fixed" still grammatically governs "errata". Body is correct ("reported upstream", index.qmd:246-247). |

#### referee-methodology.md

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| M1 | Coverage direction + one-sided pattern unreported | **RESOLVED** (PIT histogram not added — the paper has zero figures) | index.qmd:368-373; consequence stated in limitations (index.qmd:530-534). |
| M2 | SMD cross-section reversed, cells misdescribed | **RESOLVED** | index.qmd:400-407: 2.60% = claimants in states *without* an SMD (doc required); 2.97% = "mixed comparison cell (standard-deduction-state claimants pooled with below-floor claimants everywhere)"; "runs *against* a simple burden-increases-error reading". Matches FACTS E7 and `model_results.json` cell assignment. |
| M3 | Deployed simulator built on banned FSBEN gate, wrong universe | **RESOLVED in production and in the quoted numbers; stale copies remain on the paper branch** | Production: origin/main d2e3972 (PR #10) — corrected loader (`CASE==1`, weight>0, `AMTERR>threshold`) and rebuilt `app/public/data.json` (sums 44,800; CO 110 error cases/$94.1M). Manuscript: F1-F4 all quote `results_by_state_corrected.json`. **Gate test**: I reproduced the committed artifact from the raw QC CSV with mc_tool's own simulate() — exact match (5-decimal p_tier, 4-decimal SD, CO/ND/NV) under the official gate, mismatch under the FSBEN gate. Genuine regenerate, not a relabel. But see New defect 3 (the committed generator is the stale one). |
| M4 | Observed mode ignores re-review adjustment variance and sampling design; no design-based SE bracketing | **PARTIAL** | Disclosed inline (index.qmd:429-433: "i.i.d. approximation... federal re-review adjustment enters only as a fixed level") and in limitations (index.qmd:535-540). No bracketing run, no reconciliation against FNS variance machinery. Consistent with editorial T5's disclosure-first plan, but the referee's demand for a bracketing analysis is unmet. |
| M5 | Cross-case independence; anchoring corrects mean not spread | **RESOLVED for this paper** | Model mode disabled and "this paper quotes it nowhere" (index.qmd:376-378); FACTS E6 updated; simulation results all observed-mode. |
| M6 | Tail fit internally inconsistent, no diagnostics | **RESOLVED by disclosure + disable** | index.qmd:373-378 reports the finding as a finding; the fix round is external to this paper. |
| M7 | FY2024 is development-reused | **RESOLVED** | index.qmd:330-332 + limitations; frozen-pipeline FY2025 confirmation committed. |
| minors | matched pairs, both correlations, units, sub-$56, precision hedge, rearrangement cite | RESOLVED | tbl-validate (0.51/0.91); "includes deviations below the official threshold" (index.qmd:270); "carries no design-based standard error" (index.qmd:353-354); `@chernozhukov2010rearrange` cited (index.qmd:363). |

#### referee-domain.md

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| M1 | PUF truncation never named | **RESOLVED** | index.qmd:119-130 (1,037 ineligible + 406 full-overissuance, "truncated at the top", 8.88-vs-9.97 link, tier-noise "if anything, understated"); decompose universe scoped (index.qmd:272-274, 312-316 — the ineligibility inference argued, labeled not-directly-computed); simulate (430-431); limitations (523-525); conclusion scoped to "among eligible cases". |
| M2 | Parity = Mathematica's edited chain | **RESOLVED** | Same evidence as redteam M2. Nit: the six stages are named in words, not file-variable names. |
| M3 | Negative cases; one-sided pricing | **RESOLVED** | "Only active cases are priced" (index.qmd:143-149, front-door shifting); MD 13.64/4.79 underpayment beat (index.qmd:112-115). |
| M4 | QC integrity history missing | **RESOLVED structurally; one number needs verification** | index.qmd:132-141: FCA settlements, anti-bias guidance, unpublished FY2015-16, trains-from-2017 rationale, FY2025-27 endogeneity, cites `@crs2024snap`. But "more than $32 million... from six states": the round-1 review's own evidence lists **seven** state settlements (TX, FL, TN, MS, VA, WI, AK) totaling ≈$61M. See New defect 6. |
| M5 | Delay clause drift | **RESOLVED** | index.qmd:42-45 + footnote 49-53: mechanical per-year test, election-independent, 13.33% threshold, ~ten jurisdictions. Matches FACTS A3. |
| M6 | Heat-and-eat vs OBBBA §10103 | **RESOLVED** | index.qmd:489-493: "that lever's fiscal 2024 error mix overstates its remaining reach." |
| minors | probability sample; no-dispute election; 305 relabel; anchoring description; BENFIX origin; coder-discretion caveat; SMD bundling; admin-match cut | RESOLVED | index.qmd:56; 151-158 (+474-475 tie-in); 269-271; 426-427 vs FACTS E6 reconciled; 108-109; tbl-decompose caption w/ `@fns310handbook`; 415-418; 462-464. |
| minor 11 | Domain bibliography (FNS 310-1, CRS, FRAC, DOJ, memoranda) | **PARTIAL** | FNS 310 and CRS added; FRAC, DOJ materials, USDA implementation memorandum not added. |

#### referee-neutrality.md

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| M1 | "worth more than most feasible policy improvements" | **RESOLVED** | index.qmd:440-442 — verbatim the reviewer's proposed structural rewrite. |
| M2 | "$606M is worth" one-sided framing | **RESOLVED** | "corresponds to roughly $609M ($1,310M)" (index.qmd:484-486); unmodeled-costs sentence (487-489); depersonalized boundary sentence (493-495). |
| minors 1-3, 5-9 | lottery ticket; preserving noise; review-cost note; tier lotteries; deserves; residue heading; compute problem | **RESOLVED** | Expected-value phrasings (index.qmd:466-475); inline "(holding the error process fixed (@sec-limitations...))" + gross-of-review-costs + admin-match (459-464); `grep -i lottery` = 0; "an encodable target" (511); "residue attributable to state issuance systems" (79, 248); "not compute-bound for this workload" (261-262); conclusion "near-even-odds tier assignment" (553-554). |

#### referee-citations.md

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| D2/D4 uncommitted artifacts | **RESOLVED** | Verified above; D2's $8.19M/7.3%, $11.87M/10.5%, $320M/3.9%, $1.50B/18.4% all recomputed from `native_decomposition.json`. |
| pedregosa never cited | **RESOLVED** | index.qmd:329. All 15 bib keys cited inline; rendered bibliography contains all 15 `ref-` ids. |
| Missing cites: CC'21, Pub. L. 119-21, rearrangement, bracket reposition | **RESOLVED** | `@merigoux2021compiler` (index.qmd:166-169, positioned as the closest precedent); Pub. L. No. 119-21 (38); `@chernozhukov2010rearrange` (363); validation-problem bracket now background phrasing (163-167). |
| "Regression-adjusted" unsourced | **RESOLVED by removal** | `grep regression` = 0 in index.qmd; mechanism now "adjustments including federal re-review integration" (60-61). FACTS D1 retains the term (catalog-internal, fine). |
| Threshold-series source | **RESOLVED by removal + statute** | Paper now cites 7 U.S.C. § 2025(c) for the $37 base (110-111); the uncited $38/2017 value dropped from the paper. FACTS A6 still carries the series on "FNS QC guidance" (catalog-internal residue). |
| URLs/DOIs; FACTS A4/A2/G fixes | **RESOLVED** | Every bib entry has `url`; A4 placeholder gone; A2 = (B)(ii); G = 0.51/0.91. |
| giannella pin (commit/release) | **UNRESOLVED** | `references.bib` giannella_snapqc still unpinned; no commit hash or archived release. |
| C4 errata issue link | **UNRESOLVED** | FACTS C4 still cites an unlocatable "issue thread". |

#### referee-stylistic.md

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| M1 | Zero tables, zero figures | **PARTIAL** | Four tables added and rendering (tbl-verify, tbl-decompose, tbl-validate, tbl-boundary — 4 `<table>` in out/index.html). **Zero figures** — the editorial-committed boundary-distribution figure was not added; the paper still delegates its "vivid" central point to the website. |
| M2 | Process memoir / release-note register | **PARTIAL** | Cert section compressed, commit hashes out of body, `[^audit]` footnote deleted, Kentucky reframed as sensitivity caution, roadmap compressed. But adversarial-review self-narration now appears in five places (intro 97-103, model 373-378, simulate 427-429, conclusion 554-557, disclosure), and the conclusion retains "part of the method rather than an ornament to it" — the same self-assessment the reviewer explicitly asked cut from `[^audit]`, relocated rather than removed. |
| M3 | Literature engagement | **RESOLVED (substantially)** | Kane-Staiger, Herd-Moynihan, CRS, CC'21, FNS 310 added and cited at the right points. GAO/OIG and OpenFisca still absent. |
| M4 | Overreaching taglines | **RESOLVED** | All four named lapses cut or scoped; earned summaries kept; aphorism sweep clean. |
| M5 | Analytic-framing gaps | **RESOLVED (mostly)** | Global-rule-fixes + post-correction reuse (249-253); binomial SE on 86.9% (300); units flagged; Layer-2 universe in table; EB formula displayed (393-395). Full display-equation model spec still light (hurdle is prose + inline math). |
| M6 | "We" in solo-authored paper | **RESOLVED** | `grep` for we/our/ours = 0; "All errors are my own." |
| minors | § symbols; $1.268B; retitle; disclosure; closing flourish; acronyms | Mostly RESOLVED | §§ present; single $1.268B; "Data and code availability"; Disclosure section present (also answering minor 20); flourish cut. Still open: ROC AUC and USDA never expanded; "oracle" never explicitly defined as a term of art; bib access dates absent. |

#### referee-reproducibility.md

| # | Finding | Actually fixed? | Evidence |
|---|---------|-----------------|----------|
| M1 | D2/D4 artifacts missing | **RESOLVED** | As above. |
| M2 | Coverage sign | **RESOLVED** | As above. |
| M3 | Every-case overstatement | **RESOLVED** | As above. |
| minor 1 | F1 stale CO/NV percentages | **RESOLVED** | Regenerated and traceable (recomputed exactly). |
| minor 2 | Lab JSONs lack generators/provenance | **PARTIAL, with a new inconsistency** | `mc_tool.py` and the amterr scripts are now committed — but mc_tool.py is the stale-gate version (New defect 3), the corrected artifact has no provenance stanza, and the amterr scripts hardcode `/Users/maxghenis/...` paths (only `SNAP_QC_REPO` is overridable; `out_dir` and the replay `LAB` path are not, despite the commit message "path made overridable"). |
| minor 3 | Engine repo unnamed; errata link | **PARTIAL** | axiom-rules-engine named (index.qmd:573-574); errata still "issue thread". |
| minor 4 | Data acquisition undocumented | **UNRESOLVED → new false claim** | README.md unchanged (no reproduction section); see New defect 1. |
| minor 5 | Interpreter not pinned | **UNRESOLVED → new false claim** | `requires-python = ">=3.11"`, no `.python-version`; see New defect 4. |
| minor 6 | v0.1 app loader FSBEN gate | **RESOLVED on main** (d2e3972); paper-branch copies stale but merge-benign (the paper branch never touched them, so merging preserves main's fix). |
| minor 7 | Stale docs/FINDINGS | **RESOLVED on main** (docs/v2-error-model.md and FINDINGS.md:171 regenerated with correct status); paper-branch copies stale, same merge-benign logic. |
| minor 8 | Render tidiness | **RESOLVED** | .gitignore covers `paper/out/`, `site_libs/`, `FACTS-preview.html`. |

### Relabel-without-regenerate findings

**None at the headline level — the two highest-risk items pass the regenerate test decisively:**
- `results_by_state_corrected.json` reproduces exactly (5-decimal p_tier, 4-decimal SD) under the official gate (CASE==1, AMTERR>56) and does not under the FSBEN gate; values genuinely moved (ND 49→50, CO 47→49, NV 47→46, CA −29.5→−30.3, $606→$609M) and every quoted figure matches the new artifact.
- The 86.9% is now backed by a 283-row per-case artifact whose counts I verified independently.

**One small relabel residue:** CA SD reduction "by $43M" (index.qmd:470; FACTS F3) — the superseded artifact gave $43.0M; the corrected artifact gives $43.8M, which rounds to $44M. The citation moved to the new artifact; the number kept the old rounding.

### Regressions introduced (new defects)

1. **False availability claim — README.** "Reproduction commands are in the repository README" (index.qmd:576-577). `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/README.md` has no reproduction section, no run commands, no data-path documentation. The reproducibility referee's Minor 4 was answered by asserting the fix rather than making it.
2. **False artifact claim — "per-case outputs for all three layers."** Stated twice (index.qmd:302-303, 567-569). Layer 3 is per-case (283 rows). Layer 1 (`native_decomposition.json`) is US/CO aggregates only. Layer 2 (`phase_a_classification.json`) carries per-case rows only for the 13 pure_math + 19 input_system_caused cases, not the 260 input_other or 13 mixed. The aggregates fully verify D2/D3's numbers, so the fix is real — the sentence overclaims it.
3. **Committed generator contradicts its artifact.** `paper/snapshot/labs/mc_tool.py` (added by the revision commit as the "mc generator") still implements the banned gate (`STATUS∈{2,3} AND |RAWBEN−FSBEN|>56`, no CASE filter) and reproduces the *superseded* `mc_results_by_state.json`, not `results_by_state_corrected.json` (both directions verified computationally). The corrected artifact — which FACTS F1 annotates "(official error gate, CASE==1)", correctly — has no committed generator and no provenance stanza. A round-2 reviewer running the committed script will get gate-A numbers and cry foul.
4. **False pin claim.** "byte-for-byte on the pinned interpreter" (index.qmd:565-566): no `.python-version`, `requires-python = ">=3.11"` in both pyproject.toml and uv.lock. The provenance blocks *record* 3.14.4; nothing *pins* it.
5. **Settlement count/total unverified and likely wrong.** "more than $32 million in False Claims Act settlements from six states" (index.qmd:134-136). The round-1 domain review's own list is seven states (TX $15M+, FL $17.5M, TN $6.85M, MS $5M, VA $7.15M, WI $6.99M, AK $2.5M ≈ $61M). ">$32M" is literally true but roughly half the documented total; "six" matches no list I can construct. Pin both to the CRS text or the DOJ releases (congress.gov and justice.gov refused my fetches; needs a check from a browser lane).
6. **Abstract wording (two carried/new nits).** (a) "6,081 of 6,194 in-scope fiscal 2024 cases" attaches "in-scope" to 6,194, inviting a 98.2%-match misreading; the body/table are correct — say "all 6,081 in-scope cases of the 6,194-case official universe". (b) "surfaced and fixed two defects... and errata" still implies the errata were fixed (round-1 redteam minor, unfixed).
7. **Citation scope.** "documented for school ratings and hospital report cards [@kane2002volatility]" (index.qmd:442-445): Kane-Staiger 2002 JEP is school accountability; the hospital-report-card literature is uncited. Add a hospital cite or drop the clause.
8. **Committed doc points at a missing file.** `paper/snapshot/labs/amterr/ANALYSIS.md:166` lists `fy2024_reconstruction_national.csv` (15,902 rows) as an artifact; it is not committed (paper doesn't cite it; the ANALYSIS.md does).

### Unresolved prior findings (not new, not fixed)

- Methodology M4's bracketing analysis / design-based SE reconciliation (disclosure only).
- The committed figure (editorial T8) — the paper still has zero figures.
- giannella_snapqc bib entry unpinned; FACTS C4 errata "issue thread" unlinked.
- ROC AUC / USDA unexpanded; "oracle" never explicitly defined; conclusion retains the "part of the method" self-assessment stylistic asked to cut.
- FRAC/DOJ/USDA-memo domain bibliography additions (editorial T9) not made.

### Render and tests

- `quarto render index.qmd --to html`: **succeeds** (`paper/out/index.html`); zero unresolved `@sec-`/citation refs; 4 tables render; all 15 references render; inline math (`\(P(|D|>0.5)\)`, EB formula) renders correctly; no currency/math-mode mangling (every currency `$` is digit-adjacent and cannot close a math span).
- `uv run --frozen --extra dev --extra analysis pytest -q`: **46 passed** (matches FACTS E9).

### Verdict

**Needs one more (small) fix pass before round-2 fresh review.** The substance of round 1 is genuinely resolved — every major direction error, scope error, artifact gap, and neutrality item checks out against regenerated, committed artifacts, verified here by independent recomputation rather than by reading the diff. What remains is a cluster of self-inflicted claim-vs-artifact mismatches in the availability/reproducibility layer (README commands, "per-case all three layers", "pinned interpreter", the stale-gate mc_tool.py, the $43M rounding) plus the six-states/$32M verification, the missing figure, and the abstract's last five words of G-compliance. These are hours of work, but they are precisely the "the paper's own standard" items a fresh adversarial round would open with; fixing them first will keep round 2 focused on substance.

Key files: `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/index.qmd`, `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/FACTS.md`, `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/snapshot/labs/results_by_state_corrected.json`, `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/snapshot/labs/mc_tool.py`, `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/snapshot/labs/amterr/amterr_replay_results.json`, `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/paper/snapshot/labs/amterr/native_decomposition.json`, `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/README.md`, `/Users/maxghenis/PolicyEngine/_worktrees/snap-qc-paper/snap_qc_sim/data.py` (paper-branch copy stale; corrected on origin/main at d2e3972).