All verification complete. Compiling the report.

## Reproducibility Review

### Recommendation: Minor Revisions

The computational core of this paper is among the strongest I have refereed: I independently reran the entire analysis pipeline from a clean clone and reproduced **all five committed artifacts byte-for-byte**, every result JSON carries a provenance block (input SHA-256s, package versions, seeds, thresholds), the manuscript renders from a clean checkout in seconds, and the fact catalog resolved 15+ of the ~18 rows I traced end-to-end. The required revisions are specific and bounded: two decomposition artifacts backing abstract-level claims are not in the repository, one validation sentence inverts the direction its own artifact records, one headline count ("every case") overstates scope by 1.8%, two of five F1 percentages match no committed artifact, and the data-acquisition path is undocumented for a stranger. If the missing decomposition artifacts cannot be committed, this escalates to Major Revisions, because the paper's own stated bar ("every quantitative claim ... traces to a row here; every row names its artifact") is what they breach.

### Verification actually performed

| Check | Result |
|---|---|
| `uv run --frozen --extra dev --extra analysis pytest -q` | **46 passed in 1.67s** (matches FACTS E9's "46 tests"); same command runs in CI plus ruff |
| Full pipeline rerun, clean clone, `uv run --frozen --python 3.14 --extra analysis python analysis/run_all.py` (~15–20 min single-threaded) | **model_results.json, hurdle_results.json, distributional_results.json, FINDINGS.md, app/public/model_data.json all byte-identical to committed** — a third independent byte-identical reproduction |
| `render_findings()` on committed JSONs vs committed FINDINGS.md | Byte-identical — prose/JSON coupling holds |
| `quarto render` from clean checkout (Quarto 1.9.36) | HTML + PDF in 6.5s; no missing assets; no escaped-dot/`{{`/`&lt;table&gt;` artifacts (no math spans at all); no unresolved `@sec-`/citation refs; all 8 cited bib keys present |
| Committed `app/public/data.json` SHA-256 | `718fb4ec…` — exactly matches the input hash recorded in distributional_results.json provenance |
| Committed model_data.json size | 3,248,934 bytes — exactly matches the export block's `model_data_raw_bytes` |
| External refs: axiom-oracles PRs #244/#268/#269, rulespec-us #826, commits `b53ce208` (rulespec-us), `d3056626` (axiom-oracles), `de0efdc7` (axiom-rules-engine) | All resolve in public repos; `b53ce208` is indeed the whole-dollar-rounding encode the paper describes |
| giannella/snap_qc data | The six training `.sav` files and `standard_medical_deductions.csv` are **git-tracked in that public repo** (verified `git ls-files`); local copies hash-match the committed provenance |
| Raw-file recomputation | D1 (305 cases, $112.6M, 8.88%, $1.268B issuance), D2's $8.1B national denominator ($8.13B computed), B1 (44,891/44,800), D3 shares (3.3/6.6/4.2/86.0 from phase_a_classification.json) all verify |
| F2/F3/F4 vs paper/snapshot/labs/mc_results_by_state.json | Exact: CO $156.4M/$32.8M/$63.4M step; CA −29.5/PA −13.3/TX −13.2/MO +4.0/TN +3.7/IN +3.3, CA SD 43.0; levers $606.4M/$1,306M |

### Data provenance audit

| Data input | Source claimed | Verification | Verdict |
|---|---|---|---|
| qc_pub_fy2017–19, 2022–24.sav + SMD registry | snapqcdata.net via giannella/snap_qc | Tracked in public repo; SHA-256s recorded in all three result JSONs; local files hash-match | Verified (location convention undocumented — see Minor 4) |
| qc_pub_fy2024.csv, snap-fy24QC-PER.pdf | snapqcdata.net / FNS URLs (constants in snap_qc_sim/data.py) | CSV hash recorded in CERT_REPORT (`45193eb7…`); PER parse yields CO 9.97 = paper's official rate | Verified (hardcoded `/Users/maxghenis/` paths — see Minor 4) |
| paper/snapshot/labs/*.json | This repo (frozen) | F2–F4 resolve exactly; F1 partially; **no generator scripts, seeds, or provenance metadata** | Partially verifiable |
| "amterr lab ANALYSIS", reconstruct_co_fy2024.R | FACTS D2/D4 | **Not in the repository or any named public location** | Unverifiable as committed |

### Major issues

1. **The abstract's 86.9% replay result (D4) and the Layer-1 cause-code splits (D2) have no committed artifact.** FACTS D4 cites "amterr lab ANALYSIS layer 3; reconstruct_co_fy2024.R" and D2 cites "amterr lab ANALYSIS layer 1" — neither exists in this repo, in paper/snapshot/, nor in giannella/snap_qc. I could independently verify D2's denominator ($8.13B national weighted error dollars) and everything in D1/D3 (phase_a_classification.json even carries per-case rows), which makes the missing pieces conspicuous: the 246/283 partition, the 37-case residual, and the $8.2M/$11.9M/$320M/$1.5B cause-code splits are currently take-our-word-for-it numbers in a paper whose method is that no number should be. Smallest fix: commit the amterr lab's layer-1 and layer-3 outputs (a JSON like phase_a's, with case IDs) and the FY2024-adapted reconstruction script under paper/snapshot/labs/.

2. **The quantile-coverage sentence inverts the direction its own artifact records.** analysis/distributional_deviation_model.py:325–326 defines coverage as weighted P(observed ≤ predicted) and gap = coverage − nominal; the committed values at q75/q90 are **−3.47pp and −3.25pp** (71.5% at nominal 75%) — under-coverage, predicted quantiles too low, i.e. the model *understates* mid-upper magnitudes. paper/index.qmd (§sec-model, Validation) says the two levels "over-cover by 3.5 and 3.3 points — the model slightly overstates mid-upper magnitudes." Both directional words contradict FACTS E3's own "−3.5pp, −3.3pp". One-sentence fix, but it is a validation-finding sign error.

3. **"Every fiscal 2024 QC case in those states: 6,081 cases" overstates coverage.** The FY2024 file contains 6,194 CASE==1 cases in the seven states (NY 885, AZ 925, MD 745, TX 955 vs the suites' 847/922/722/906; CO 856, CA 883, GA 945 are complete). The 113 exclusions (1.8%) are principled and well-documented *externally* (axiom-oracles' comparisons/ny-snap-qc.yaml says "847 in-scope"; the playbook's §4 documents QcExclusionLog and the SSI-CAP scope rule), but the paper's text — which discloses the intermediates bridge scrupulously in §sec-oracle-scope — never discloses the case-scope rule. "All 6,081 in-scope cases match" is true; "every ... case" is not. State the in-scope universe and the exclusion count/reason in one sentence.

### Minor issues

1. **F1's Colorado and Nevada tier-flip probabilities match no committed artifact.** Paper and FACTS claim CO 47%, NV 47%; tier_noise_monte_carlo.json gives 48.0%/45.8%, mc_results_by_state.json gives 48.5%/45.9%, and my fresh 100k-draw reruns of the named pipeline (two seeds) give 48.4–48.5%/45.5–45.6%. ND/WA/KS check out within MC noise. Immaterial to the "nearly even odds" claim, but the catalog promises exact traceability; refresh the two numbers from the committed artifact.

2. **The snapshot lab JSONs have no reproducibility path.** Unlike the main pipeline (seeded, provenanced, byte-stable), the three labs' generator scripts are not in the repo, `simulate()` is unseeded by default, and the frozen JSONs carry no seed/draws/input-hash metadata. Freezing outputs is legitimate, but commit the generating scripts (with seeds) or add a provenance stanza to each JSON.

3. **The engine repository is never named.** The paper cites "engine commit `de0efdc7`" and the Reproducibility section lists only TheAxiomFoundation/{axiom-oracles, rulespec-us}; the commit actually lives in public **TheAxiomFoundation/axiom-rules-engine** (I verified it resolves there). Add the repo name; likewise C4's "reported upstream" errata claim needs a concrete issue/PR link — I could not locate it by search, and the cited axiom.org report page does not mention it.

4. **Data acquisition is undiscoverable for a stranger.** Nothing in the README or docs says: clone giannella/snap_qc to `~/.cache/axiom-oracles/snap_qc_repo` (analysis/train_error_model.py:33–37), place the FY2024 CSV/PER PDF at the literal `/Users/maxghenis/.cache/axiom-oracles/snap-qc/` paths hardcoded in scripts_build_data.py:7–8, install `pdftotext` (poppler) for load_official_rates, or run `analysis/run_all.py` at all (its docstring is the only place the command appears). The snap_qc_sim/data.py module docstring advertises a `download()` function that does not exist. Smallest fix: a "Reproducing the paper" README section (five commands: clone data repo, download two files, run_all, pytest, quarto render) plus env-var or CLI overrides for the two hardcoded paths.

5. **The interpreter is not pinned.** Byte-identity was achieved on Python 3.14.4 (recorded in provenance) but `requires-python >=3.11` and there is no `.python-version`; a 3.11 replicator will get different bytes with no explanation. Also, byte-identity is same-machine/same-arch scope — worth one caveat word in the footnote. And model_results.json's provenance leaks the absolute `smd_registry` path `/Users/maxghenis/.cache/...` into a committed artifact.

6. **The v0.1 app loader still gates counted errors on |RAWBEN − FSBEN| > threshold** (snap_qc_sim/data.py:90–94) — the very FSBEN-as-target choice §sec-model reports as caught and corrected in the model pipeline. Against the official STATUS∈{2,3} & AMTERR>$56 definition, CO gets 112 vs 110 cases and $92.8M vs $94.1M (~1.4% of error dollars); the simulator's spread and lever attributions inherit this. Small, but reconcile the loader or document the divergence in the app's method notes.

7. **Stale docs contradict the shipped app.** docs/v2-error-model.md ("the live simulator does not consume that export yet"; status table "Simulator integration ... Not implemented") and the FINDINGS interpretation boundary ("or integration with the live simulator") predate PR #9, which shipped the model-based mode the paper describes. FACTS G's guardrail also cites "cross-state correlation 0.535" — no committed value matches (0.507/0.458 unfactored; 0.518/0.459 frozen).

8. **Render tidiness.** The manuscript project renders FACTS.md and snapshot/cert/CERT_REPORT.md as additional inputs (producing FACTS-preview.html etc.) and leaves an untracked, un-gitignored `paper/site_libs/`. Consider scoping `render:` to index.qmd and gitignoring site_libs.

### Strengths

- **The determinism claim is real.** Thread-count pinning before numpy import, fixed seeds throughout, staged atomic artifact replacement, uv.lock, and provenance blocks — and it survived my independent clean-clone rerun byte-for-byte on all five artifacts, including the 3.2MB browser export.
- **The fact-catalog discipline mostly works.** B1–B3, E1–E9, F2–F4, D1, D3 all resolved to committed artifacts at stated precision; several (D1, D2's denominator, B1) I re-derived from the raw public file independently.
- **CERT_REPORT.md is a model certification artifact**: commit pins, binary and per-file overlay hashes, timing with de-amortized extrapolation, honest deviations section, and an adversarial-audit addendum that corrected its own prose (36→37 replacements) and scoped what the evidence JSON does and does not store.
- **Tests are synthetic guards that run without microdata** (46 tests, <2s, in CI) and encode the paper's hard-won lessons: the AMTERR-not-benefit-difference label, stage-2 nesting, inner-OOF calibration, staging semantics, export schema.
- **The app states its own limits** — anchoring choice, accounting-bound levers, model-mode scope — exactly as the paper claims it does.
- The external verification chain is public end-to-end: both PRs fixing the encodings, the 814/847→847/847 New York history corroborating the rounding-defect story, and the playbook documenting exclusions per-reason.

### What a replicator can do today / cannot

**Can, with zero setup:** run the test suite; render the manuscript (HTML+PDF); check F2–F4, E1–E9, B1–B3, D3 against committed artifacts; run the app locally from committed data.json/model_data.json; verify data integrity by hash once data is obtained.

**Can, with reverse-engineering:** rerun the full pipeline to byte-identity (they must discover the `~/.cache/axiom-oracles/snap_qc_repo` convention from source and choose Python 3.14).

**Cannot:** reproduce D2's cause-code splits or D4's 86.9% replay (artifacts and script absent); regenerate the three snapshot lab JSONs (scripts and seeds absent); regenerate data.json without editing hardcoded paths; locate the engine repo or the FNS errata report from the paper alone.

**Smallest closing set:** commit the amterr-lab layer-1/layer-3 outputs + reconstruction script; commit the three lab generator scripts with seeds; fix the coverage sentence, the "every case" sentence, and F1's two stale percentages; add a five-command "Reproducing the paper" README section with the data paths made overridable; name axiom-rules-engine and link the errata issue; pin Python 3.14.

Key file references: /Users/maxghenis/PolicyEngine/snap-qc-sim/paper/index.qmd (coverage sentence §sec-model; "every ... case" §sec-oracle), /Users/maxghenis/PolicyEngine/snap-qc-sim/paper/FACTS.md (rows D2, D4, F1, G), /Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/distributional_deviation_model.py:325 (coverage definition), /Users/maxghenis/PolicyEngine/snap-qc-sim/snap_qc_sim/data.py:90 (FSBEN gate; phantom `download()` docstring), /Users/maxghenis/PolicyEngine/snap-qc-sim/scripts_build_data.py:7 (hardcoded paths), /Users/maxghenis/PolicyEngine/snap-qc-sim/analysis/train_error_model.py:33 (undocumented cache convention).