# Correction to the event-family addendum

Recorded 2026-08-16, the same day, after adversarial review of the
manuscript passages written against `EVENT_FAMILY_ADDENDUM.md`
(sha c642447b…). The addendum stays byte-frozen; this file states what
it got wrong and what the paper reports instead. No estimate, rule, or
verdict changes.

## Timing, stated plainly

The addendum froze AFTER the three parent unit results and the
decomposition existed. It is a post-results reporting commitment, not
a pre-registration. Its sentence "pre-registers what the migrations
paper reports" is withdrawn as wording; the paper says "declared after
the results, before the manuscript text" wherever it cites the family
disclosure. Nothing about the family logic was fixed before the parent
protocols returned their verdicts, and the paper must not read as if
it were.

## Corrections

1. **The 0.0732 quantity is not the verdict's familywise error rate.**
   It is P(at least one strict rank-1 among three units) under
   independent uniform ranks. The frozen verdict also requires the
   client placebo not to fire (p ≥ 0.10), which that number ignores,
   and the verdict rejects at p < 0.10, not at rank 1. Retained ONLY
   as what it is — the chance that at least one of three floor
   results appears by rank alone — and labeled so. Independence is
   further wrong as a description of the design: Rhode Island and
   Kentucky share one donor pool and one panel, and Oregon's pool
   overlaps both. The number is an upper-bound illustration under an
   assumption the design violates, and the paper says exactly that or
   omits it.
2. **The "resolution statement" is withdrawn.** Rank 1 of 43 IS "the
   most extreme of 43"; the strict test carries no finer information.
   The client-placebo condition is a separate gate on the verdict, not
   a refinement of the strict p, and the pre-named window profile is
   verdict-inert by protocol and cannot sharpen anything. The paper
   drops the sentence.
3. **Bonferroni across three unit tests, correctly stated.** Under
   arbitrary dependence Bonferroni is valid: Rhode Island's adjusted
   strict p is 3 × (1/43) = 0.0698, below 0.10; Holm gives the same
   rejection for Rhode Island and stops at Kentucky (0.302 vs 0.05).
   The paper reports the ADJUSTED p (0.0698), not "clears the
   threshold," and reports it once — in the design section as the
   family disclosure — rather than in the abstract, results,
   limitations, and conclusion.
4. **The family boundary.** The decomposition's three channel tests
   already carry their own family adjustment (0.10/3, frozen in
   UHIP_DECOMPOSITION_PROTOCOL.md before that estimation). The
   confirmatory event family is the three unit tests because they
   answer one question (did the migration move the strict class) with
   one rule; the channel tests condition on Rhode Island's signal and
   ask a second question (which coded channel). A six-test Bonferroni
   (0.10/6 = 0.0167) is below both attainable floors (1/43 = 0.0233,
   1/35 = 0.0286), so no result in the paper could clear it by
   construction; the paper states this so the reader can apply the
   stricter family if they judge the two questions one.

## What the paper reports (fixed)

In the design section, once: the three unit tests form a family with
no pre-registered familywise correction; declared after the results,
Bonferroni-adjusted strict p for Rhode Island is 0.0698 (Holm
identical), Kentucky's and Oregon's exceed 1; a six-test family
including the decomposition channels has a threshold below every
attainable floor; the pooled test aggregates and does not correct. In
limitations, one sentence naming the uncorrected family and the
post-results timing. Nowhere else.
