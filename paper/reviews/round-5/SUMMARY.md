# Round-5 referee summary

## Editorial recommendation

**Major revision; do not accept until four blockers are resolved.** All 13 supplied findings were re-verified and retained. No supplied finding was refuted. No additional blocker was found; one additional minor archival-state finding is recorded in `reproducibility.md`.

## Blockers

1. **Scenario totals mislabeled as bounds/bracket — CONFIRMED.** The paper’s own New York and Georgia examples prove billing is nonmonotone. Nested strict/broad case removals do not order the cost functional. Anchors: `paper/index.qmd:31-35,812-839`; `tests/test_adoption_numbers.py:125-166`.
2. **O3 exact value mismatch — CONFIRMED.** `FACTS.md` says 7.22334%; the artifact says 7.22339927%, which rounds to 7.22340 at five decimals. Anchors: `paper/FACTS.md:168`; `analysis/component_targets.json` key `wedge_decomposition.national_weighted_summary.file_side.total_pct`.
3. **Protocol chronology is not in squash-merged main — CONFIRMED.** `d272fd9` and `5e8b0ba` each contain protocol and results. No local `refs/pull/53/head` or `/55/head` exists. Ordering does survive in reachable topic branches: `e73ce28→4a5e4af` and `9eec8e7→3827f04`. Anchors: `paper/index.qmd:515-516`; `paper/FACTS.md:174-175`.
4. **$1,029 publication-state framing is stale — CONFIRMED.** June 2026 CPI-U was published July 14 and consumed locally. $1,029 remains provisional pending the official FY2027 FNA COLA schedule; $59 separately awaits USDA’s June TFP cost (only May $1,018.20 was consumed). Anchors: `paper/index.qmd:857-863`; `paper/FACTS.md:158`; external `snap-fy27-margins/params/sources/official/cpi_07142026.htm:553-558`; `analysis/fy2027_parameters.json:7,49-50`.

## Majors

5. **One-shot execution is not enforced — CONFIRMED.** Repeat identical-input runs overwrite results. `analysis/fy2025_confirmation.py:186-198,322-357`.
6. **Input hash is recorded before drift check — CONFIRMED.** The manifest mutates before refusal. `analysis/fy2025_confirmation.py:329-332`.
7. **FY2027/self-oracle evidence is external — CONFIRMED.** N1 cites files absent from `snap-qc-sim`. `paper/FACTS.md:156`.
8. **National sums are not asserted in the cited test — CONFIRMED.** No 7.671/7.574/6.941 assertion exists in `tests/test_adoption_numbers.py`.
9. **Wedge mislabeled as federal re-review alone — CONFIRMED.** It also includes ineligible-case error and is not separately identified. `paper/index.qmd:622-639,796-802`; `paper/FACTS.md:166-168`.
10. **“Location, not width” exceeds tested mechanisms — CONFIRMED.** `paper/index.qmd:521-535`; `paper/FACTS.md:174-175`.
11. **Nationwide adoption language exceeds seven-state verification — CONFIRMED.** `paper/index.qmd:19-24,787-820`; `paper/FACTS.md:31,147-150`.
12. **Review-history narration and stale count — CONFIRMED.** Process narration appears at `paper/index.qmd:127-134,503-535,611-617,974-985,1010-1020`; “seventeen” is at `:999-1001`, while the archive contains 21 files (20 excluding the editorial synthesis).
13. **Neutrality phrasing — CONFIRMED.** “states can still shape” (`:853`), “honest projection” (`:884`), “fabricating” (`:887`), and “sharpest instrument” (`:534-535`) should be replaced with descriptive language.

## Minor

- **Reviewed source is not a single commit — CONFIRMED.** The manuscript and FACTS files were modified working-tree content atop `5e8b0ba`. The final archival revision should identify a commit containing the exact reviewed text.

## Report map

- `methodology.md`: quantitative identification, scope, and artifact contradictions.
- `red-team.md`: executable-control and interpretation failure modes.
- `reproducibility.md`: self-containment, test locks, chronology, and source state.
- `neutrality.md`: advocacy language and review-history narration.
- `round-diff.md`: revision-7-specific assessment.

## Review conditions

Repository `/Users/maxghenis/PolicyEngine/snap-qc-sim` was inspected read-only. No repository files, refs, commits, or branches were changed, and nothing was pushed. Reports were written only to `/Users/maxghenis/.cache/axiom-oracles/snap-fy27/round5/`.
