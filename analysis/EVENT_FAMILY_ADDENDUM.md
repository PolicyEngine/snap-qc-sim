# Event-family multiplicity addendum

Status: frozen 2026-08-16, before any manuscript text was written
against it. Sibling of `RIKY_EVENT_STUDY_PROTOCOL.md` and
`EVENT_STUDY_PROTOCOL.md`; changes no estimate, no rule, no verdict.
It states how the three unit-level event tests relate as a family and
pre-registers what the migrations paper reports about that family.

## The family

Three treated units carry unit-level verdicts under the same rule
(strict permutation p < 0.10 and client placebo p ≥ 0.10): Rhode
Island and Kentucky against 42 placebo donors (smallest attainable
p = 1/43 = 0.0233), Oregon against 34 (smallest p = 1/35 = 0.0286).
The parent protocols apply the rule per unit and pre-name a pooled
Rhode Island–Kentucky statistic; neither applies a familywise
correction across units. This addendum makes the family explicit and
fixes the reporting.

## Fixed quantities (arithmetic on committed ranks; no re-estimation)

1. **Familywise floor probability.** Under the null that each unit's
   strict rank is uniform over its permutation set and the three units
   are independent, the probability that at least one of the three
   unit-level tests returns its smallest attainable p (rank 1) is
   1 − (42/43)(42/43)(34/35) = 0.0732. The paper reports this number as
   the design's own false-positive load for "any rank-1 unit among
   three."
2. **Bonferroni threshold across the three unit tests:** 0.10/3 =
   0.0333. Rhode Island's committed strict p (1/43 = 0.0233) lies below
   it; Kentucky (13/43 = 0.302) and Oregon (25/35 = 0.714) lie above.
   The paper reports Rhode Island's verdict under the unit rule AND
   whether it clears the Bonferroni threshold, in that order, and
   states that the unit rule is the frozen verdict.
3. **Resolution statement.** Because Rhode Island sits at its floor,
   the design distinguishes "p = 0.0233" from "the most extreme of 43"
   only through the placebo condition and the pre-named window profile;
   the paper says so.
4. **Pooled statistic.** The Rhode Island–Kentucky pooled test
   (p = 0.0930) aggregates two units into one statistic; it is not a
   familywise correction and the paper does not present it as one.

## What this addendum does not do

It does not change any committed verdict, re-rank any unit, alter the
placebo rule, or add tests. It adds a family-level disclosure and a
Bonferroni comparison computed from committed ranks. Independence
across the three tests is an assumption stated for the floor
probability, not a claim about the data.

## Language

Unit verdicts stay in the protocols' words. The family disclosure uses
"familywise," "attainable floor," and "Bonferroni threshold" and makes
no claim beyond the arithmetic above.
