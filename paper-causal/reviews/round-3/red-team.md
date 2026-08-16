# Red-team review

Line citations refer to `paper-causal/index.qmd` at `7c16ad2`.

## Findings

1. **blocker — CONFIRMED — Family disclosure can be read as strengthening RI rather than bounding it.** Hostile-referee text: line 8, “at the floor a 42-donor pool allows and below a three-event Bonferroni threshold of 0.033”; line 134, “the strict p of 0.023 also clears”; line 279, “below the three-event Bonferroni threshold.” The repeated positive placement turns an after-results multiplicity calculation into an abstract-and-conclusion credential. The later phrase “without gaining resolution” (line 261) does not undo that emphasis.

2. **blocker — PLAUSIBLE — Post-hoc adjustment can be read as preregistration.** Hostile-referee text: lines 106–108, “a frozen addendum ... fixes what the paper reports”; artifacts lines 246–248, “event-family multiplicity disclosure”; plus the addendum's own “pre-registers” claim. Since the addendum was committed after parent results existed, “frozen” without that timing invites the inference that the three-test family and Bonferroni comparison were specified before seeing results.

3. **minor — CONFIRMED — The pooled p = 0.093 is not presented as a corrected family test.** Lines 108–111 explicitly say the pooled statistic aggregates two units rather than correcting the family. Elsewhere the paper keeps its pooled verdict separate. A hostile reading is possible only by ignoring the explicit disclaimer; no adverse finding beyond noting that the protection holds.

4. **blocker — CONFIRMED — The “resolution” sentence is internally vulnerable.** Hostile-referee text at line 134 says the design distinguishes a floor p from “the most extreme of 43” through a placebo and a “pre-named window profile.” Rank 1/43 already means most extreme of 43, and line 138 calls that profile descriptive and verdict-inert. This reads as attaching two favorable ancillary facts to make a coarse p-value look more resolved.

5. **minor — CONFIRMED — No regression of the estimand lock.** Lines 40–43 and 283 retain “bundled system replacement as implemented,” and the paper continues to reject software/rules-engine interpretations. No adverse finding.

6. **minor — CONFIRMED — No regression of “does not fire.”** Lines 8 and 134 retain “the client-caused placebo does not fire (p = 0.233)” rather than “flat.” No adverse finding.

7. **minor — CONFIRMED — No regression of registry-defined donor qualification.** Lines 37–39 define donors through the paper's registry, and line 283 retains “no migration recorded in the paper's event registry.” No adverse finding.

8. **minor — CONFIRMED — No regression of estimator neutrality.** Lines 8 and 283 state that both estimators are reported and neither is privileged; the reproduction check remains explicit. No adverse finding.

9. **minor — CONFIRMED — No regression of verdict taxonomy.** The manuscript retains `signal` and `no_protocol_defined_signal`, keeps total rate verdict-inert, and states that the pooled verdict does not replace unit verdicts. No adverse finding.

