# Referee round 4 — summary

**Disposition: corrections only partially landed.** Five findings: two **major CONFIRMED** and three **minor CONFIRMED**. No blocker was found, and no finding is merely plausible.

The two major findings are: (1) adjusted p `0.070` appears four times rather than only in the abstract, design, and RI-results pointer; limitations repeats it while claiming the arithmetic appears once; and (2) the six-test comparison is rounded as `0.10/6 = 0.017` with bare fractional floors rather than the required `0.0167 < 0.0233` and `0.0286` display.

The minor findings are: the explicit zero-occurrence check fails because “resolution” remains once in Kentucky; and the rewritten family paragraph retains one reduced passive and two sentences substantially beyond VOICE.md's approximate twenty-word ceiling. Findings only are supplied; no rewrites.

The substantive methodology otherwise checks out. `0.073`, “false-positive load,” and “clears” occur nowhere. Every disclosure citation states “post-results” or “declared after the results”; no sentence presents the family rule as pre-registered. Dependence, Bonferroni validity, `3/43 = 0.070`, Holm stopping at KY (`0.302` versus `0.05`), family rationale, and all three unit verdicts agree with the committed JSON artifacts. The requested rounds 1–2 locks did not regress.

The erroneous addendum was handled through a sibling correction, not an edit. `analysis/EVENT_FAMILY_ADDENDUM.md` has the same blob before and after `a9a168c` and retains SHA-256 `c642447b8235cfc31954159a97d62c656c0e15e9a997da7bd600c6c31d2dd588`.

See `round-diff.md` for all eight disposition checks and line-cited voice findings; see `methodology.md` for artifact and arithmetic verification.
