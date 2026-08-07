## Neutrality Review

**Manuscript:** `/Users/maxghenis/PolicyEngine/snap-qc-sim/paper/index.qmd`

### Recommendation: Major Revisions (narrowly triggered — all fixes are sentence-level; the paper's structure and caveat discipline are otherwise close to exemplary)

### Overall assessment

The paper is unusually disciplined for work this close to a live political fight. It never recommends a position on OBBBA cost sharing, never advises states on the FY2025/26 election, explicitly labels its policy numbers "accounting bounds, not causal estimates," fences behavioral and agency responses into limitations, and deflates its own product's reach (verified computation addresses only 3–13% of error dollars). Two passages, however, cross the line my rubric treats as automatic: one unmeasured comparison ("worth more than most feasible policy improvements") and one one-sided intervention framing (the $606M simplification figure with no acknowledgment that the options themselves change benefits and program cost). Both are fixable with a sentence each.

### Major issues (must fix)

**1. Unmeasured comparison and feasibility claim — §sec-simulate, lines 359–361**

> "The formula prices a noisy estimate as if it were the truth; near a boundary, sampling noise is worth more than most feasible policy improvements."

The second clause compares a modeled quantity (tier-flip probability from sampling noise) against an unmodeled one ("most feasible policy improvements"). The paper never models the distribution of achievable error-rate changes, so "feasible" is a feasibility judgment with no artifact behind it — exactly the "per unit of political effort" genre. The first clause is a defensible structural description (the statute maps the point estimate to a tier with no uncertainty adjustment) delivered with a rhetorical edge that an OBBBA critic could quote as PolicyEngine's verdict on the design. Proposed neutral rewrite of the pair:

> "The formula maps the point estimate to a tier with no adjustment for sampling uncertainty; near a boundary, tier assignment therefore turns as much on the sampling draw as on the underlying rate."

(If a comparison to policy is wanted, anchor it to the paper's own numbers, e.g., Colorado's $33M sampling standard deviation versus a specific accounting-bound delta computed in the same section — both sides modeled.)

**2. One-sided framing of the simplification options — §sec-simulate, lines 376–388**

> "…is worth roughly $606M per year nationally in expected cost share at 50% effectiveness, and $1.31B at 100%."

The "accounting bounds, not causal estimates" caveat is excellent, but it addresses only whether the error reduction would materialize — not the omitted cost side. The four options named (standard medical deduction, standard self-employment deduction, heat-and-eat, BBCE) are contested policy: they change benefit amounts, eligibility, and program cost, none of which the bound models. As written, "worth roughly $606M" is quotable as PolicyEngine pricing the case *for* these options. Two changes: (a) replace value language — "the error dollars attached to those elements correspond to roughly $606M per year in expected cost share at 50% effectiveness…"; (b) add one scoping sentence, e.g.:

> "These bounds speak only to measured error and cost share; the options themselves change benefit amounts, eligibility, and program cost, none of which is modeled here."

Relatedly, lines 386–388 — "Deep-in-tier states get little from marginal simplification (New York at 14.1% and Alaska at 24.7% need larger moves); boundary states get the most" — reads as strategy guidance to states. Neutral rewrite: "The expected cost-share effect of a marginal reduction in measured error is near zero for states deep within a tier (New York, 14.1%; Alaska, 24.7%) and largest for states near a boundary."

### Minor issues

1. **"variance was a lottery ticket" (line 369).** The finding (expected cost share rises with sample size for above-boundary states) is fully modeled and legitimate; the metaphor imputes gambling to states and is the quotable part. Suggest: "…and *hurts* states just above one, for whom the chance of a below-boundary draw had positive expected value (California −$29.5M…)."

2. **"below-boundary states are rewarded for measuring more precisely; above-boundary states are rewarded for preserving noise" (lines 372–374).** Both sides are modeled, so this is a supported comparative — but "rewarded for preserving noise" reads as motive attribution and is quotable either as "OBBBA pays states to stay ignorant" or as a prediction states will game sampling. Suggest the expected-value formulation: "The formula thus embeds an asymmetry: expected cost share falls with additional sample volume for states just below a boundary and rises for states just above one." Also add an inline scope pointer to this paragraph — "(holding the underlying error process fixed; see @sec-limitations)" — since the corrective-feedback caveat currently lives only in Limitations, and note that the expected-savings figures are gross of the cost of conducting additional reviews.

3. **"risk-averse states may rationally buy audits even against their expectation" (lines 370–371).** Properly hedged and decision-theoretic; acceptable. Folding in the review-cost caveat above would fully fence it.

4. **"rewired the incentives" (line 34).** Adjudication requested: I read this as legitimate — it asserts that incentives changed (true: the rate now carries direct fiscal consequences) without valence about whether the change is good. Keep, or if maximal caution is wanted: "attached direct fiscal consequences to a statistic…"

5. **"tier lotteries" (line 441, Conclusion).** Defensible — "lottery" describes a computed 47–49% flip probability, and the numbers appear in the paper. Acceptable as-is; a maximally neutral alternative is "…whose noise the new formula converts into substantially random tier assignment for boundary states."

6. **"the encoding target the cost-sharing formula itself deserves" (line 409).** "Deserves" is a soft recommendation (of the authors' own technical agenda, not a policy position). Suggest: "The cost-sharing formula is itself an encodable target: the QC sampling formulas…"

7. **"The distinction determines what different interventions can plausibly buy" (line 74).** "Plausibly" is doing unearned work. Suggest: "The distinction bounds what different classes of intervention can address."

8. **Heading "A residue that is not ours" (line 169).** Mildly defensive tone toward the issuing side. Suggest: "A residue attributable to issuance." (The attribution logic itself is sound — it is definitional given exact reviewer-side parity.)

9. **"Verification at administrative scale is not a compute problem" (lines 204–205).** Slight generalization from one workload; the extrapolation is shown, so this is minor. Suggest: "For this workload, verification at administrative scale is not compute-bound."

10. **Abstract, "how the errors that remain should be measured, modeled, and simulated" (lines 16–17).** Methodological rather than policy normativity; acceptable. "Can be" would be strictly neutral.

### On the specific sweep items

- **Advocacy drift:** No "states should" / "Congress should" sentences anywhere; no advice on the base-year election; no suggestion FNS or Congress change anything. The only prescriptive residue is methodological (items 6, 10) and the strategy-flavored phrasing in Major 2 / Minors 1–2.
- **Speculation beyond model scope:** Well fenced. Limitations explicitly exclude behavioral responses of agencies and households, the corrective-feedback channel, and cross-measurement-regime transport, and flag the anchoring choice. The one inline gap is the audit-volume paragraph (Minor 2).
- **Claims about other parties:** Handled well. FNS errata are stated factually and minimally ("internal inconsistencies… reported upstream"); state-level discrepancies are quantified rather than characterized, and the Layer-3 result (86.9% correct arithmetic on wrong facts) is largely exculpatory of state computation. Colorado is framed as a worked example, not a target. "The oracle audits its own paperwork" is a quip about the method, not a dig; fine.
- **Staffer-quotability:** After fixing Majors 1–2 and Minors 1–2, the remaining quotable lines ("coin flip," "$63M per tier step," "information failure, not calculation failure") are all findings with the supporting numbers in the same sentence or paragraph — quotable, but as results, which is the correct exposure for a nonpartisan publisher.

### Strengths

1. **Explicit epistemic labeling.** "We label these *accounting bounds*, not causal estimates… an upper-bound identity, not a behavioral prediction" is exactly the right fence, and the cross-reference to the adoption contrasts as "the reason for the caution" makes it substantive rather than perfunctory.
2. **Reporting against interest.** The paper features a validation failure (New York underprediction), reports that its earlier Kentucky estimate (−5.3 points) "dissolved" under correction, states that burden intermediates "add little discrimination," and bounds its own product's direct reach at 3–13% of error dollars. This is the opposite of advocacy hype.
3. **Agnosticism where the data are agnostic.** "administration, omitted policy, model error — the data do not identify" and "adoption is endogenous… nothing here identifies causal effects" are model-scope honesty of the kind most papers only gesture at.
4. **Symmetric treatment of the audit-volume lever.** The two-sided expected-value result (helps below-boundary, hurts above-boundary, reduces variance for both) is presented with numbers on both sides — the framing needs tightening (Minors 1–2), but the analysis itself is evenhanded.
5. **Genuine limitations section** that restates every major scope boundary (parity scope, solver filters, thresholded label, transport gap, fixed error process) rather than boilerplate.

### Required revisions before resubmission

1. Rewrite lines 359–361 per Major 1: delete or anchor the "most feasible policy improvements" comparison; neutralize "prices a noisy estimate as if it were the truth" to the structural statement.
2. In the simplification paragraph (lines 376–388): replace "is worth roughly $606M" with correspondence language, add the unmodeled-costs sentence, and depersonalize "get little / get the most / need larger moves."
3. In the audit-volume paragraph (lines 362–374): replace "variance was a lottery ticket" and "rewarded for preserving noise" with expected-value phrasing, and add the inline "(holding the error process fixed…)" pointer plus the gross-of-review-costs note.
4. Optional but recommended: Minors 6–9 (deserves/plausibly/residue heading/compute claim).

With revisions 1–3, I would recommend Accept: the paper would then contain no sentence I can construct a partisan quote from that is not simply a quantified finding.