# Round-3 resolutions (maintainer adjudication, 2026-08-16)

Reviewer: gpt-5.6-sol, small-N synthetic control + multiple testing
brief; four reports + summary archived unedited. All numbers verified.
The three blockers were the maintainer's own multiplicity text, written
that afternoon; all confirmed on inspection.

1. **Blocker — 0.0732 is not the verdict's familywise error rate.**
   CONFIRMED. It is P(≥1 strict rank-1) under independent uniform
   ranks; it ignores the placebo gate and the p < 0.10 rejection rule,
   and independence fails by design (RI/KY share a pool and panel;
   Oregon overlaps). Removed from the manuscript entirely; the
   addendum's error is recorded in `EVENT_FAMILY_ADDENDUM_CORRECTION.md`
   (the addendum itself stays byte-frozen).
2. **Blocker — the "resolution statement" is wrong.** CONFIRMED. Rank
   1/43 is "most extreme of 43"; the placebo is a separate gate, not
   a refinement, and the window profile is verdict-inert. Sentence
   dropped everywhere.
3. **Blocker (plausible) — post-results choice laundered as
   pre-registration.** CONFIRMED in the addendum's own word
   "pre-registers." Withdrawn in the correction; the manuscript now
   says "declared after the results and before this manuscript" where
   it cites the disclosure, and limitations names the post-results
   timing.
4. **Major — dependence disclosure.** Adopted: the design paragraph
   states the shared pool/panel and overlap and that no product of
   unit probabilities describes the joint false-positive rate;
   Bonferroni is stated as valid under any dependence.
5. **Major — family boundary undefended.** Adopted: the paragraph
   explains why the confirmatory family is the three unit tests (one
   question, one rule; the channel tests condition on RI's signal, ask
   a second question, and carry their own frozen three-way adjustment)
   and reports that a six-test family's threshold (0.017) lies below
   both attainable floors, so the reader can apply it and see nothing
   clears.
6. **Major — "clears" overemphasized.** Adopted: "clears" appears
   nowhere; the paper reports the ADJUSTED p (0.070; Holm identical)
   once in the design section, once in RI's results as a pointer, and
   as a parenthetical in the abstract with "post-results" stated; the
   conclusion carries only rank 1 of 43.
7. **Major — voice violations in the changed prose.** Adopted: every
   flagged sentence was replaced in the rewrite (the passive
   independence assumption, the "false-positive load" naming, the
   "appear beside" carrier, the overloaded results sentence, the
   limitations repeat).
8. **Minor — round-2 fixes hold; companion citation clean.** No action.
