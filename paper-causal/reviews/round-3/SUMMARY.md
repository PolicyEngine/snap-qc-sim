# Referee round 3 summary

**Recommendation: request changes.** The committed ranks, denominators, Bonferroni arithmetic, pooled p-value, and other changed numbers all verify. The revision nevertheless has two confirmed methodological blockers and one plausible disclosure blocker.

## Findings

1. **blocker — CONFIRMED — 0.0732 is not the familywise false-positive rate of the protocol verdict.** It is the probability of at least one strict rank-1 result under independent uniform ranks. It ignores the client-placebo gate and does not evaluate rejection at p < 0.10.

2. **blocker — CONFIRMED — The resolution claim is wrong.** Rank 1/43 and “most extreme of 43” are the same strict-test information. The placebo is a separate verdict gate; the pre-named window profile is explicitly descriptive and verdict-inert and cannot refine p-value resolution.

3. **blocker — PLAUSIBLE — The manuscript can launder a post-results multiplicity choice as preregistration.** It repeatedly calls the addendum “frozen” and foregrounds threshold crossing without stating that the family and reporting rule froze after parent results existed. The addendum's word “pre-registers” is especially problematic.

4. **major — CONFIRMED — The independence benchmark lacks the key dependence disclosure.** RI and KY share the same donor pool and years, and Oregon overlaps many donors. The 0.0732 product is not design-based under those dependencies. Bonferroni remains valid under arbitrary dependence; Holm gives the same RI rejection here.

5. **major — CONFIRMED — The family boundary is undefended.** Three channel tests form a separately adjusted family in the frozen decomposition protocol. The paper must explain why the confirmatory family is three unit tests rather than all six tests, or apply a six-test rule (whose 0.0167 cutoff no observed floor p clears).

6. **major — CONFIRMED — “Clears” is technically true but overemphasized.** RI's Bonferroni-adjusted p is 3/43 = 0.0698; it does not create evidence finer than rank 1/43. Repetition in the abstract, results, limitations, and conclusion makes a post-results comparison read as stronger confirmation.

7. **minor — CONFIRMED — Round-2 fixes hold.** The estimand lock, “does not fire,” registry-defined donors, estimator neutrality, consequence-window caveat, and verdict taxonomy remain intact; the companion citation now resolves.

8. **major — CONFIRMED — Changed prose introduces voice violations.** Passive/be-complement assumptions, placement narration, and “the design” as an unsupported rhetorical carrier conflict with `VOICE.md`.

Detailed evidence appears in `methodology.md`, `red-team.md`, `round-diff.md`, and `language.md`.
