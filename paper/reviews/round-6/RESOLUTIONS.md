# Round-6 resolutions (maintainer adjudication, 2026-08-14)

Every finding verified against the tree before disposition.

1. **BLOCKER, bib malformed — CONFIRMED, fixed.** Stray `}` at the old
   line 228 (residue of deleting the undated Osnes entry) and a
   duplicate `crs2018errors` block removed; `dellavigna2020forecasting`
   was indeed absent and is now added with Crossref-verified authorship
   — DellaVigna, Otis & Vivalt, AEA P&P 110:75–79 (2020), not
   DellaVigna–Pope (the LITERATURE.md anchor row's authorship was also
   corrected). Net: nine unique verified entries plus GAO-07-422T.
2. **BLOCKER, 2002 Farm Bill narrative exceeded the anchor table —
   CONFIRMED, resolved by verification rather than retreat.**
   GAO-07-422T (testimony, 2007-01-31) was read in full text (govinfo)
   after the review snapshot: pre-2002 sanctions hit states above the
   national average (about half of states each year); the 2002 redesign
   required 95% statistical probability of exceeding 105% of the
   national average for two consecutive years. The sentence now carries
   that citation, and the section gains the load-bearing corollary the
   source supports: the 2002 rule priced sampling uncertainty into
   liability; the 2025 tiers price point estimates. The anchor was
   promoted into analysis/LITERATURE.md the same day.
3. **BLOCKER, causal-confirmation overreach in @sec-events —
   CONFIRMED, rewritten.** "Causally moved" and "independently fixes"
   removed everywhere (paper, FACTS R3, analysis/QUASI_EXPERIMENTS.md).
   The consequence-window profile is now described as what the frozen
   protocol says it is: a descriptive consistency check, designated
   verdict-inert (`changes_verdict: false` is asserted in the test
   suite), confirming neither the accounting convention nor the
   estimate.
4. **MAJOR, "validation suite" / KY "went better" — CONFIRMED,
   rewritten.** The registry documents Kentucky's troubled launch
   (~25,000 erroneous cancellation notices, ~50,000-case backlog), so
   the null was never evidence of a smooth migration. The paragraph now
   says exactly that: the three verdicts span signal/null/refusal, and
   a null under this design is the absence of a protocol-defined
   signal, producible by power, donor fit, or offsetting changes.
5. **MAJOR, FY2021 handling undisclosed — CONFIRMED, fixed.** The
   setup paragraph now states the primary specification drops
   pandemic-partial fiscal 2021 from the post-period, retains fiscal
   2020, and reports both pandemic-handling variants as sensitivities
   (matching RIKY_EVENT_STUDY_PROTOCOL.md).
6. **MAJOR, DOJ wording — CONFIRMED, fixed.** Settlements are framed
   as resolving allegations; the $67M+ aggregate now cites its own
   release (doj2021snapqc, the Tennessee announcement's cumulative
   figure) alongside CRS R45147; the uncited "2008–2013" span was
   dropped. A mispointed cross-reference in the same paragraph (the
   strategic-response design target pointed at @sec-events) was
   corrected to the fiscal 2026 pre-registration in @sec-fy2025.
7. **MAJOR, quoted numbers not test-locked — CONFIRMED, fixed.**
   tests/test_riky_event_study.py gains
   test_committed_riky_artifact_locks_paper_quoted_numbers: per-unit
   and pooled p-values and placebos, the pooled effect, and the full
   consequence-window profile (4.950 / 1.483 / 3.468, verdict-inert
   flag). The Oregon artifact was already locked at the byte level
   (full-file SHA-256), which pins its quoted values.
8. **MINOR, duplicate FACTS section Q — CONFIRMED, fixed.** The
   revision-8 section is now R (R1–R4); Q remains the fiscal 2026
   pre-registration.
9. **MINOR, numbers/rounding faithful; prior-round resolutions intact;
   date and wrapper correct — no action.**
10. **MINOR, round count — applied at archival.** With this round
    archived, all four "five rounds" occurrences become six.

Post-resolution verification: quarto render clean; fast pytest tier
green locally; CI re-run on the resolution commit gates the merge.
