## Citation Review — snap-qc-sim paper

Files: `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/index.qmd`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/references.bib`, `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/FACTS.md`

### Recommendation: Minor Revisions

No misattributions, no anachronisms, no fabricated references. Every bibliography entry exists and its metadata is correct or near-correct; the statutory and regulatory citations are exact down to the clause level. The required fixes are: six missing `url` fields, one bib entry that is never cited inline (so Quarto will silently drop it), one scope patch on the "regression-adjusted" claim, and — the only substantive item — two FACTS.md-declared artifacts that are not committed to the repository despite the paper's claim that every quantitative fact maps to a committed artifact.

### Per-reference verdicts

| Reference | Verdict | Detail |
|---|---|---|
| `duan1983smearing` | OK — add URL | Verified: JASA 78(383): 605–610, 1983. Correctly attached to the out-of-fold smear retransformation. Add `url = {https://doi.org/10.1080/01621459.1983.10478017}` |
| `koenker1978quantile` | OK — add URL | Econometrica 46(1): 33–50, 1978 — canonical, correct. Correctly attached to quantile loss. Add `url = {https://doi.org/10.2307/1913643}` |
| `efron1979bootstrap` | OK — add URL | Annals of Statistics 7(1): 1–26, 1979 — canonical, correct. Correctly attached to the observed-resample mode. Add `url = {https://doi.org/10.1214/aos/1176344552}` |
| `pedregosa2011sklearn` | FIX — never cited | Metadata correct (JMLR 12: 2825–2830, 2011), but zero inline citations, so Quarto omits it from the rendered bibliography. It should be cited: `analysis/train_error_model.py` imports `sklearn.ensemble.HistGradientBoostingClassifier` (verified), so cite at the first classifier mention in @sec-model. Add `url = {https://jmlr.org/papers/v12/pedregosa11a.html}` |
| `merigoux2021catala` | OK — add URL, pagination nit | Verified: Proc. ACM Program. Lang. 5(ICFP), 2021, DOI 10.1145/3473582. Canonical ACM form is Article 77 (77:1–77:29); `pages = {1--29}` is the common export and acceptable. Add `url = {https://doi.org/10.1145/3473582}` |
| `oecd2020cracking` | OK — add URL | Verified: Mohun & Roberts, OECD Working Papers on Public Governance No. 42, Oct 2020, produced by OPSI — institution field is defensible. Add `url = {https://doi.org/10.1787/3afe6ba5-en}` |
| `fns2024per` | OK — strengthen | URL `fns.usda.gov/snap/qc/per` is real (fetch timed out; page confirmed via search). Year 2025 confirmed — official PDF dated June 30, 2025. I verified every state rate the paper uses against the official PDF: CO 9.97 (7.91 over + 2.06 under, matching FACTS D1 exactly), ND 7.91, WA 6.06, KS 9.98, NV 5.94, NY 14.09 (→14.1), AK 24.66 (→24.7), US 10.93. The PDF's footnote 1 also confirms the $56 FY2024 tolerance and the $37 FY2014 base. Suggest adding the durable document link in a `note`: `https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-fy24QC-PER.pdf` |
| `fns2024techdoc` | OK | `snapqcdata.net/datafiles` is live and hosts the FY2024 file and FY-2024-Tech-Doc.pdf; title matches the series; year 2025 correct. Optional: credit Mathematica as preparer (the site is Mathematica-run) alongside FNS |
| `giannella_snapqc` | OK — pin a version | At-risk `@misc` audited in full: repo exists (created 2026-03-16 — year 2026 correct); owner login `giannella` is Eric Giannella, Georgetown Better Government Lab (GitHub profile verified); `benmolin` is a real contributor (5 commits) so the two-author attribution is appropriate; the tree contains both claimed components — `1_data_munging_and_raw_variable_reconstruction_for_using_public_qc_data.R` (the pre-edit reconstruction solver) and `additional_data/snap_state_options_*.csv` + `snap_state_options_pipeline.R` (the policy-option registries). The repo was pushed again on 2026-08-07, after the paper date: cite a pinned commit or archived release (Zenodo/Software Heritage), since "adapted to fiscal 2024" claims depend on a specific version |
| 7 U.S.C. 2013(a)(2) (inline, ×3) | OK | Verified against law.cornell.edu: tiers 0/5/10/15 at <6 / 6–<8 / 8–<10 / ≥10 beginning FY2028 in (B)(i); FY2025-or-FY2026 election then third-preceding-year in (B)(ii); the footnote's (B)(iii) cite for the ×1.5 ≥ 20% delay to FY2029/FY2030 is exactly right. FACTS A1–A3 confirmed |
| 7 C.F.R. 275.11(b) (inline, ×2) | OK | Verified against the eCFR: standard active 300 / 300+0.042(N−10,000) / cap 2,400; alternative 300 / 300+0.0153(N−12,941) / cap 1,020; negative 150 / 0.144 / 800 and 150 / 0.1224 / 680. FACTS A4 matches the regulation formula-for-formula, including the non-obvious 0.0153 slope and 12,941 offset. Paper text (300 floor, 0.042 slope, 2,400 cap, reduced cap 1,020) all correct |

Repository-existence claims in Reproducibility also verified: `TheAxiomFoundation/axiom-oracles` and `TheAxiomFoundation/rulespec-us` both exist and are public.

### Artifact audit (unverifiable-as-committed — fix before publication)

FACTS.md's preamble states "Artifacts live in this repository unless noted," and the paper's Reproducibility section promises a committed fact catalog mapping "every quantitative claim... to its artifact." Two rows fail that promise:

- **D4 (Layer-3 replay: 246/283 = 86.9%, 37-case residual — an abstract headline number).** Declared artifacts "amterr lab ANALYSIS layer 3; reconstruct_co_fy2024.R" do not exist in the repo: no `.R` files anywhere, no `amterr*` files, and no committed artifact anywhere under `paper/snapshot/` containing 246, 283, or 86.9.
- **D2 (Layer-1 cause-code dollars: $8.2M/$11.9M Colorado; $320M/$1.5B/$8.1B national).** Same missing "amterr lab ANALYSIS" source; no committed JSON contains the cause-class breakdown.

By contrast, Layer 2 (D3) is fully auditable: I reconciled `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/snapshot/labs/phase_a_classification.json` by hand — classes sum to 305 cases and $112.58M/yr, with pure-math 3.25%, system-caused 6.63%, mixed 4.16%, other-input 85.95%, matching the paper's 3.3/6.6/4.2/86.0 exactly. The simulation rows (F1–F4) have committed snapshots (`mc_results_by_state.json`, `tier_noise_monte_carlo.json`), and the model rows (E1–E9) have `analysis/model_results.json`, `hurdle_results.json`, `distributional_results.json`, `FINDINGS.md` — all present.

I am not calling D2/D4 fabricated — the surrounding infrastructure is demonstrably real, the external solver exists, and every adjacent artifact I could check reconciled to the digit. But as committed, the abstract's 86.9% cannot be audited from the repository, which is precisely the failure mode a hostile reviewer would seize on. Fix: commit the Layer-1/Layer-3 outputs and `reconstruct_co_fy2024.R` (e.g., under `paper/snapshot/labs/`), or mark those FACTS rows as external with a retrievable location. D1's `snap-fy24QC-PER.pdf` is external but fine — it is the official FNS document (contents verified above); add its URL to the row.

### Missing citations

1. **"Regression-adjusted" (§sec-qc).** "The official state rate is a regression-adjusted combination of over- and underpayment rates [@fns2024per]" — the cited PER document confirms over+under composition but says nothing about regression adjustment. Support the regression clause with `fns2024techdoc` (its section on why database-derived rates differ from official rates) or an FNS methodology source; otherwise the paper's own official-vs-file-derived contrast (9.97 vs 8.88) rests on an unsourced mechanism.
2. **OBBBA itself.** The opening sentence names the Act with no citation. Add Pub. L. No. 119-21 (2025) at first mention alongside the U.S.C. cite.
3. **Rules-as-code breadth.** Two citations is thin for the validation-problem framing, and the single closest prior work is absent: Mérigoux, Monat & Protzenko, "A modern compiler for the French tax code" (CC '21, DOI 10.1145/3446804.3446850), which validates an independent encoding against the tax authority's own test cases — the direct precedent for "administrative data as oracle." Given the paper's novelty claim ("the best available oracle"), omitting it is a genuine exposure. Optional additions: NZ "Better Rules" (2018) for the government-practice side.
4. **Scope of the sentence carrying the two RaC cites.** "Unit tests encode the encoder's own reading; cross-model comparisons inherit both models' assumptions [@merigoux2021catala; @oecd2020cracking]" — neither source states that two-part thesis; it is the authors' (correct) synthesis. Reposition the bracket as background ("the validation problem is discussed in...") or the claim reads as sourced when it is original.
5. **Threshold series.** "$38 in 2017" (and FACTS A6's 38/37/37/48/54/56 series) cites only "FNS QC guidance" with no retrievable reference; $56/FY2024 and $37/FY2014 are now covered by the PER PDF footnote, but the 2017 value should cite the FY2017 memo or techdoc (FNS threshold memos exist on usda.gov guidance-documents).
6. **Methods (optional).** Friedman (2001) for gradient boosting and Zadrozny & Elkan (2002) for isotonic calibration; plus the mandatory inline cite of `pedregosa2011sklearn` noted above.

### Minor issues

1. FACTS A4's source cell contains a dangling placeholder: "FY2024 technical documentation pp. (formulas restated)" — page numbers never filled in.
2. FACTS A2 cites "(B)(i)–(ii)" for the rate-keying rules; both the election and third-preceding-year rules live in (B)(ii) alone. Tighten to (B)(ii).
3. FACTS internal inconsistency: prohibition G says "Cross-state correlation 0.535 ⇒ r²≈0.29" while E5 and the paper report 0.906 (factored). If 0.535 is the unfactored correlation, say so; as written the fact catalog contradicts itself.
4. FACTS A5 ("all states elected the reduced schedule") is pinned to techdoc lines ~894–895 — specific and plausible but not independently verified here; keep the line-level pin.
5. `giannella_snapqc` bib title is the citer's descriptive title rather than the repo's own description ("code and data for modeling SNAP payment errors") — acceptable for software, but consider matching, and add the pinned-commit note from the verdict table.
6. Statute/regulation references are inline-only. Given §sec-roadmap's own argument that these provisions "can be... cited by simulators," consider bib entries for 7 U.S.C. 2013 and 7 C.F.R. 275.11 with law.cornell.edu or eCFR URLs.

### Verified citations

- 9 of 9 bibliography entries verified to exist with correct author/venue/volume/pages/year; 8 cited inline (12 inline instances), 1 uncited (`pedregosa2011sklearn`).
- 5 statutory/regulatory inline citations verified to the clause level against law.cornell.edu.
- 7 state rates + national rate + tolerance threshold verified against the official FNS FY2024 PER document.
- 3 at-risk `@misc` entries put through the full verification protocol (URL fetch, repo tree, contributor and identity checks) — all real.

### Summary

Citation hygiene here is far above baseline: the legal cites are correct at a level most law-review pieces don't reach ((B)(iii) is genuinely the delay clause; the 0.0153/12,941 reduced-schedule formula matches the CFR exactly), the classic-methods attributions are all correct, and the one at-risk software citation survives a full audit including author identity and file-tree contents. The two real defects are the uncommitted Layer-1/Layer-3 artifacts behind the abstract's 86.9% headline — an auditability gap the paper's own reproducibility standard makes unacceptable — and the never-cited scikit-learn entry. Both are afternoon fixes.

Sources: [Cornell LII 7 U.S.C. 2013](https://www.law.cornell.edu/uscode/text/7/2013), [Cornell LII 7 C.F.R. 275.11](https://www.law.cornell.edu/cfr/text/7/275.11), [FNS FY2024 payment error rates PDF](https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-fy24QC-PER.pdf), [FNS newsroom release](https://www.fns.usda.gov/newsroom/fns-0003.25), [SNAP QC data files](https://snapqcdata.net/datafiles), [Duan 1983 at Taylor & Francis](https://www.tandfonline.com/doi/abs/10.1080/01621459.1983.10478017), [Catala at ACM DL](https://dl.acm.org/doi/10.1145/3473582), [Catala arXiv](https://arxiv.org/abs/2103.03198), [OECD Cracking the Code](https://www.oecd.org/en/publications/2020/10/dechiffrer-le-code_d56cab77.html), [giannella/snap_qc](https://github.com/giannella/snap_qc)