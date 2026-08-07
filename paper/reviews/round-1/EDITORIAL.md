# Round-1 editorial synthesis

Eleven adversarial reviews: seven manuscript referees (red-team, methodology,
domain, citations, neutrality, stylistic, reproducibility) and four code/artifact
auditors (statistical red-team, JS↔Python fidelity, claims sweep, certification
skeptic). Reports in this directory. Reproducibility referee pending; this
synthesis will be amended when it lands.

## Editorial decision: major revisions

No reviewer found fabrication. Every checkable number reproduced — several
referees independently recomputed headline results from raw data to the digit
(Layer 1–2 decomposition, official rates, sampling formulas, cert arithmetic,
draw-path semantics bitwise). The revisions required are about scope,
direction-of-effect prose errors, domain completeness, register, and two
statistical defects in the shipped model mode. Production actions were taken
immediately; the manuscript revision follows this worklist.

## Actions already taken (production, before revision)

1. Observed-mode data gate corrected to the official error definition
   (`AMTERR > threshold`, `CASE == 1`, positive weights) — the audit-banned
   FSBEN gate had survived in the v1 loader (claims row 12; methodology M3;
   fidelity F5). data.json rebuilt; national accounting bounds move
   $606M→$609M at 50%.
2. Model-based mode disabled in production pending statistical fixes
   (stats red-team verdict: unsound as shipped — tail fitted at q90 but
   attached at q99 where its own mean-excess ≈ 0.26 vs fitted 0.467;
   level-gap coupling r=0.90 into tier probabilities). URL param ignored;
   UI hidden; docs state the honest status.
3. Verification copy corrected everywhere (app badge, tooltip, README):
   "benefit computation verified — N of M replayable reviews" with exclusions
   named; the false "every case" universal removed (claims rows 1–4).
4. Dual-issuance render bug fixed (fidelity F4); monotonization replaced with
   assert-at-load (F3); stale simulator-integration denials fixed in docs and
   the FINDINGS generator (claims rows 5–9; stats F7).
5. Cert report corrected (37 not 36 overlay replacements) and annotated with
   its independent byte-identical reproduction (cert skeptic).

## Cross-cutting revision themes (manuscript)

T1 — Parity target and universe (red-team M1–M2; domain M2; abstract+3 sections).
State plainly: the compared benefit is FSBEN, the QC Minimodel's software
recomputation, on a file whose editing process enforces the asserted identities
and reconciles inputs to within $5; several intermediates are supplied from the
file; the in-scope universe is 6,081 of 6,194 CASE==1 cases (113 documented
program-structure exclusions: SSI-CAP/MFIP standardized-benefit units,
missing-field rows). Drop "adjudicated by the agency's own reviewers" and
"reviewer arithmetic" for the parity legs; reviewer-adjudicated fields
(RAWBEN/BENFIX/AMTERR/STATUS) belong to the decomposition sections. Reframe
the contribution accordingly: admin-grade benefit-computation parity against
the agency's own computation chain — still the tool that caught two encoding
defects — with the cross-model character acknowledged, not disparaged.

T2 — Direction errors vs artifacts (methodology M1–M2; red-team M4).
Coverage misses are UNDER-coverage (−3.47/−3.25pp; quantiles too low; model
understates mid-upper magnitudes — coherent with the NY gap and $183<$189).
The SMD cross-section is reversed and its cells misdescribed: 2.60% is
claimants in non-SMD states (med_doc_required=1); 2.97% is the mixed 0-cell.
Report the one-sided pattern (all nine gaps negative) as systematic, not
"7 of 9 pass."

T3 — PUF truncation (domain M1). The public file excludes ineligible-finding
cases (whose entire benefit scores as error) and full-overissuance cases —
truncating the top of the error distribution. Name this in sec-qc; decompose
or caveat the 8.88-vs-9.97 gap; add the direction-of-bias note to every
sampling-SD claim (true flip risk larger); scope the 86.9% to partial-error
cases among eligible units and argue (not assume) the conclusion's survival.

T4 — Regenerated numbers (methodology M3 minor-4; red-team M5). All F1–F4
figures re-derived from the corrected loader and quoted from the committed
regenerated artifact (examples/results_by_state.json → snapshot): boundary
probabilities, CO expectation/SD, audit-volume dollars, $609M/$1,310M bounds.
FACTS F-rows updated to cite the regenerated snapshot.

T5 — Model-mode status (stats red-team; methodology M5–M6). The manuscript
describes the model-based mode as implemented and disabled pending: tail refit
at attachment depth with diagnostics and a physical bound, per-state factors,
53-state dollar-rate validation, seed-stable validation of the shipped
bootstrap+redraw configuration, cross-case dependence limitation stated.
Until the fix round lands, the paper's simulator section leads with observed
mode and reports the model mode's validation gaps as findings.

T6 — Uncommitted artifacts (citations; red-team M3). Commit to
paper/snapshot/labs/: the Layer-1/Layer-3 outputs behind D2/D4 (case-level,
like phase_a_classification.json), reconstruct_co_fy2024.R, scrubbed of any
non-public references; pin the giannella/snap_qc commit; cite sklearn inline;
add Mérigoux-Monat-Protzenko CC'21 (the direct precedent), Pub. L. 119-21,
regression-adjustment support, threshold-series source, DOIs throughout;
reposition the two-cite validation-problem bracket as background.

T7 — Neutrality rewrites (neutrality M1–M2, minors 1–2, 6–9). Replace the
unmeasured "worth more than most feasible policy improvements"; add the
unmodeled-costs scoping sentence to the lever bounds; expected-value phrasing
for the audit-volume asymmetry with the inline fixed-process pointer and
review-cost note; depersonalize state "strategy" phrasings; the listed
wording substitutions.

T8 — Architecture and register (stylistic). Add: decomposition table,
state-verification table, validation table (coverage + calibration 2×2),
boundary-state table, and one figure (simulated boundary-state distribution
with tier cutoffs; calibration scatter optional). Formal model specification
with equations (hurdle, quantile set, tail, smear, EB shrinkage formula).
Excise the process memoir (audit narration ×3 → target-validation facts and a
sensitivity note); compress certification to two sentences + appendix;
roadmap → one discussion paragraph; kill taglines and the closing flourish;
"we"→"I" or resolve authorship; expand acronyms; §§ symbols; unify $1.268B;
retitle Reproducibility → Data and code availability; disclosure statement on
the PolicyEngine↔harness relationship.

T9 — Domain additions (domain M3–M6, minors). One paragraph: negative-case
system and the one-sided pricing (front-door shifting; underpayments inside
the PER — MD 13.64 includes 4.79 under). One paragraph: the 2009–2016 QC
integrity episode ($32M+ FCA settlements, unpublished FY2015–16 rates, FNS
anti-bias guidance) — why training starts FY2017, and why FY2025–27 labels
are endogenous to the new stakes. Delay clause: mechanical per-year test
(13.33% threshold; ~10 jurisdictions at FY2024 rates), not "the keyed rate."
Heat-and-eat: OBBBA §10103 restricted the LIHEAP-HCSUA to elderly/disabled
households — the lever's channel was narrowed by the same statute; say so.
The reduced-schedule no-dispute condition as a live incentive finding.
"305 recorded deviations" not "payment errors"; coder-discretion caveat on
Layer 1 with code lists; SMD cost-neutrality bundling (HCSUA offsets);
"probability sample" not "stratified"; audit-cost economics (review unit cost;
admin match 50→25% FY2027); domain bibliography (FNS 310-1, CRS, FRAC, DOJ
materials, implementation memoranda).

T10 — Methods additions (methodology minors). Matched frozen pairs
(1.81/1.65 → 0.885/0.785); both correlations (0.507 unfactored, 0.906
factored); case-vs-dollar units in the synthesis sentence; sub-$56 findings
in the decomposition universe stated; AUC raw/calibrated consistency;
negative-rate clipping note; rearrangement cite (Chernozhukov, Fernández-Val
& Galichon 2010); SD-column labels; sign-model justification or roadmap;
precision-SE hedge; n+extra disposition assumption; FY2024 development-reuse
sentence + frozen-pipeline FY2025 commitment; design-based SE discussion
(re-review variance component, month-stratified bootstrap) as bracketing or
stated assumption.

## Sequencing

1. Production PR (claims-fixes) — in flight.
2. Snapshot regeneration + artifact commits (T4, T6).
3. Manuscript revision against T1–T10.
4. Re-render; FACTS.md updated in the same commit (rows C1–C2, D2, D4, E3,
   E6–E8, F1–F4, G).
5. Round-2 re-review: red-team + methodology + domain minimum, fresh eyes.
6. Model-mode fix round (Sol) proceeds in parallel; its results enter the
   paper only after its own gate.
