# Round-5 red-team referee report

## Recommendation

**Major revision.** The four blockers in the methodology report are publication-stopping. This report stresses failure modes in the revision’s claims and controls.

## R1 — “One shot” is a social instruction, not a harness invariant

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “one command and one shot, with no re-tuning” (`paper/index.qmd:438-440`); P3 says “Publication day = one command, one shot” (`paper/FACTS.md:176`).
- **Evidence:** `run()` always calls `record_input`, scores, and writes `results_path` with `write_bytes` (`analysis/fy2025_confirmation.py:322-357`). Re-running with the same input hash is allowed because `record_input` rejects only a different hash for the same filename (`analysis/fy2025_confirmation.py:186-198`). No existence check, run nonce, append-only ledger, or refusal to overwrite the results exists. Tests cover drift and a dry run, not repeat-run refusal (`tests/test_fy2025_confirmation.py:78-99`).
- **Assessment:** the documentation tells the operator to run once (`analysis/FY2025_CONFIRMATION.md:9-17,32-47`), but the executable does not enforce it. A repeat silently overwrites the claimed one-shot output.

## R2 — The harness mutates the input record before checking frozen-code drift

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “runner refuses drifted modules (fail-closed)” (`paper/FACTS.md:176`); the methods say anything after opening outcomes is post-hoc (`paper/index.qmd:438-440`).
- **Evidence:** `run()` executes `manifest = record_input(...)` and only then `verify_freeze(manifest)` (`analysis/fy2025_confirmation.py:329-332`). `record_input` writes the manifest to disk (`analysis/fy2025_confirmation.py:186-198`). The documentation also states it “appends ... SHA-256 ... [then] refuses” drift (`analysis/FY2025_CONFIRMATION.md:3-7`).
- **Assessment:** on a drifted checkout, a forbidden run still changes the purported freeze record before refusing to score. This is not a pure fail-closed transaction and weakens the evidentiary chain.

## R3 — Bound rhetoric fails under the paper’s own counterexample

- **Status:** CONFIRMED
- **Severity:** blocker
- **Passage and evidence:** the manuscript calls strict/broad “the bound’s two ends” (`paper/index.qmd:812-820`) and immediately documents nonmonotonic New York and Georgia billing (`paper/index.qmd:829-839`; `tests/test_adoption_numbers.py:145-166`).
- **Assessment:** because the mapping from removed error dollars to bills has discontinuities and delay zeros, an intermediate class can leave the purported interval. Report two scenarios, not an identified range.

## R4 — “Engine adoption” at national scale risks category substitution

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** heading “Pricing engine adoption through the formula,” followed by “for each jurisdiction” (`paper/index.qmd:787-795`) and all-53 totals (`paper/index.qmd:818-820`).
- **Evidence:** exact engine parity exists in seven states only (`paper/FACTS.md:31`), while the all-53 scenario zeroes cases based on QC cause codes (`paper/FACTS.md:147-150`). The broad class includes policy misapplication “an engine removes only where it drives the determination end to end” (`paper/index.qmd:813-816`).
- **Assessment:** cause-code suppression is not evidence that a verified engine could be adopted nationally or would eliminate each coded dollar. The paper calls it noncausal, but the section title and national prose still imply an implemented intervention.

## R5 — Repricing uncertainty is framed as an “honest” interval without probabilistic or identification content

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “The two conventions bracket ... The band, not either endpoint, is the honest projection” (`paper/index.qmd:876-885`).
- **Evidence:** the two conventions are fixed-dollar and proportional-to-benefit carries (`paper/index.qmd:876-880`); no argument establishes that the unknown data-generating carry lies between them. The FY2027 artifacts are external to this repository (N1, `paper/FACTS.md:156`) and label parameters estimates pending the official COLA.
- **Assessment:** two plausible conventions form a sensitivity pair, not a confidence interval, identified set, or guaranteed bracket. “Honest” is both normative and methodologically stronger than the evidence.

## R6 — Stale publication-state prose can mislead readers about what is observed

- **Status:** CONFIRMED
- **Severity:** blocker
- **Passage and evidence:** the paper says June CPI has not published (`paper/index.qmd:859-860`), while the consumed local source is the July 14 BLS June-2026 release and the extraction uses June CPI-U 333.952 (`snap-fy27-margins/params/sources/official/cpi_07142026.htm:553-558`; `.../fy2027_projection_inputs_web_extract.json:3-8`).
- **Assessment:** distinguish observed June CPI, pending official FNA COLA tables, and pending June TFP. Otherwise readers cannot tell which uncertainty is data availability, administrative publication, or rounding convention.

