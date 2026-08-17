# Referee round 4 — round-diff findings

Target: `migrations-rev2` at `a9a168c450aeed8c4b0d282c5773b505ba921b3a`, inspected only with `git show`/read-only Git commands.

## Findings

1. **Major — CONFIRMED — disposition 6 is only partially applied: the adjusted p appears in four places, not the specified three, and the fourth passage contradicts itself.** The required placements landed: abstract, “a **post-results** Bonferroni comparison ... gives an adjusted p of **0.070**” (`paper-causal/index.qmd:8`); full design statement, “**3 × 1/43 = 0.070**” (`:114`); and RI-results pointer, “it is **0.070 (design section)**” (`:139`). But limitations repeats “Rhode Island adjusted p **0.070**” and then says the arithmetic “**appears once, in the design section**” (`:267`). Thus the correction was copied rather than confined; `0.070` occurs four times. The conclusion correctly carries only “p = 0.023, rank 1 of 43” (`:285`).

2. **Major — CONFIRMED — disposition 5 does not state the required six-test boundary at the requested numerical precision.** The design says, “a threshold of **0.10/6 = 0.017**, below every floor ... (**1/43 and 1/35**)” (`paper-causal/index.qmd:116–118`). The requested auditable comparison is `0.10/6 = 0.0167 < 1/43 = 0.0233` and `1/35 = 0.0286`. The ordering is correct, but the decimal equalities/floors are absent and `0.10/6 = 0.017` is only a rounded display, not the specified equality. The family-boundary rationale did land: channel tests “condition on Rhode Island's signal and ask a second question” and carry a frozen three-way adjustment (`:118–121`).

3. **Minor — CONFIRMED — disposition 2 removed the bad resolution sentence but did not satisfy the round-4 zero-occurrence check.** The old claim was deleted from RI results, but “at this design's **resolution**” remains in the Kentucky interpretation (`paper-causal/index.qmd:160`). Counts in the manuscript: `0.073` 0; `false-positive load` 0; `resolution` 1; `clears` 0. This is a partial application under the explicit round-4 criterion, not a renamed version of the withdrawn RI claim.

4. **Minor — CONFIRMED — the rewritten family paragraph violates the active-voice lock.** VOICE.md requires “Active voice, always” and treats be-verb complements as passive (`paper-causal/VOICE.md:20–22`). The rewrite uses the reduced passive “A family disclosure **declared after the results** ... reports” (`paper-causal/index.qmd:110–112`). This finding identifies the violation only; no rewrite is proposed.

5. **Minor — CONFIRMED — the rewritten family paragraph exceeds the voice bible's sentence ceiling.** VOICE.md sets “About twenty words” as the ceiling (`paper-causal/VOICE.md:23–27`). The opening sentence spans lines 106–109 and is about 38 words; the six-test sentence spans lines 116–121 and is about 56 words. Both carry multiple independent claims. This finding identifies the violation only; no rewrite is proposed.

## Eight-disposition verification

1. **0.0732/FWER error — partially landed only under the stricter lexical check.** The erroneous paragraph is removed. The manuscript now says dependence prevents a product of unit probabilities from describing the joint rate (`paper-causal/index.qmd:121–123`). `0.073` and “false-positive load” occur nowhere. Finding 3 records the separate surviving “resolution.”

2. **Resolution statement — substantive fix landed; lexical criterion failed.** RI now says only “The strict p sits at the floor a 42-donor pool allows” (`paper-causal/index.qmd:139`); the placebo remains a separate verdict gate in the design (`:104`). The unrelated Kentucky use at `:160` remains.

3. **Post-results timing — landed.** Every citation/reference to the disclosure carries timing: abstract “post-results” (`:8`); design “declared after the results” (`:110–111`); artifacts “post-results reporting commitment” (`:251–254`); limitations “declared after the results” (`:267`). The manuscript says the parent protocols do not correct across units (`:106–109`) and says there was “no pre-registered familywise correction” (`:267`); no sentence implies family-rule pre-registration.

4. **Dependence disclosure — landed.** “Rhode Island and Kentucky share one donor pool and panel, and Oregon's pool overlaps both” and “no product ... describes ... joint false-positive rate” (`:121–123`). Bonferroni is identified as valid under any dependence (`:112–114`).

5. **Family boundary — partially landed.** The substantive three-unit/three-channel boundary is present (`:106–121`), but Finding 2 records the missing exact decimals.

6. **Adjusted-p emphasis — partially landed.** The abstract, design, RI pointer, and conclusion follow the intended hierarchy, but limitations creates an unrequested fourth `0.070` occurrence (Finding 1). “clears” occurs nowhere.

7. **Voice rewrite — partially landed.** The former “false-positive load,” “appear beside,” and overloaded RI-results sentence are gone. Findings 4–5 identify active-voice and sentence-length violations in their replacement.

8. **Rounds 1–2 and companion language — landed for the requested locks.** The manuscript retains the estimand lock, “bundled system replacement as implemented” (`:8`, `:98`, `:289`); RI's placebo “does not fire” (`:8`, `:139`, `:285`); registry-defined donors (`:8`, `:38`, `:289`); “Both estimators are reported and neither is privileged” (`:8`) and “the paper privileges neither” (`:205`, `:289`); one `signal` and two `no_protocol_defined_signal` verdicts (`:285`); and the billed-window wording, “the pre-named ... window inside the September 2016 to December 2019 interval” (`:8`, `:285`). No regression was found in these locks.

## Frozen-sibling correction check

The original addendum is unchanged across `a9a168c^` and `a9a168c`: both Git blob IDs are `aeb7e7ad29adef59194707036e5f584ef4e477ca`, and both file SHA-256 values are `c642447b8235cfc31954159a97d62c656c0e15e9a997da7bd600c6c31d2dd588`. The new sibling `analysis/EVENT_FAMILY_ADDENDUM_CORRECTION.md` records that the addendum stays byte-frozen (`:3–7`) and withdraws its pre-registration wording (`:11–18`). The frozen-sibling handling is correct.
