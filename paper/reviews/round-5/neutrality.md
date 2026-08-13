# Round-5 neutrality and style referee report

## Recommendation

**Major revision for tone and scope.** The manuscript generally discloses limitations, but several advocacy/editorial formulations are inappropriate in a technical referee record and sometimes overstate identification.

## N1 — “States can still shape” implies agency and efficacy not established here

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “Fiscal 2027 is the first measurement year states can still shape” (`paper/index.qmd:851-855`).
- **Evidence:** the paper’s simulator holds the error process fixed and identifies sampling effects, not causal effects of state action (`paper/index.qmd:965-972`).
- **Assessment:** replace with a neutral administrative statement about which measurement year determines which bill and when sampling plans are submitted. “Shape” suggests controllability and invites strategic interpretation beyond the analysis.

## N2 — “Honest projection” is normative and overclaims the two-convention range

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “The band, not either endpoint, is the honest projection” (`paper/index.qmd:883-885`).
- **Evidence:** only two deviation-carry conventions are evaluated (`paper/index.qmd:876-880`), with no proof they bound the truth.
- **Assessment:** call it a two-convention sensitivity range. “Honest” imputes dishonesty to point reporting and substitutes rhetoric for a coverage/identification claim.

## N3 — “Fabricating” is accusatory

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “fabricating a repriced rate without a verified computation would defeat the paper's premise” (`paper/index.qmd:886-888`).
- **Evidence:** the actual limitation is that only seven states have verified encodings (`paper/FACTS.md:31`).
- **Assessment:** use “the paper does not report repriced rates where the computation has not been verified.” That states scope without alleging fabrication.

## N4 — “Sharpest instrument” is promotional and unsupported

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “partner-state administrative records are the sharpest instrument against it” (`paper/index.qmd:531-535`).
- **Evidence:** the experiment tests coverage and location repair mechanisms, not a comparative study of future data sources (`paper/index.qmd:515-535`).
- **Assessment:** say administrative records are a proposed next source for diagnosing residual misspecification. “Sharpest” has no evaluated comparator.

## N5 — Review-history narration occupies the scientific body

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** introduction: “been through four rounds of adversarial review” (`paper/index.qmd:127-134`); model body: “An adversarial round forced...” and detailed repair-round narration (`paper/index.qmd:503-535`); simulator body: “an adversarial review found...” (`paper/index.qmd:611-617`); conclusion and disclosure repeat the four rounds (`paper/index.qmd:974-985,1010-1020`).
- **Evidence:** the review archive already exists under `paper/reviews/`.
- **Assessment:** retain methodological facts (protocol, tested variants, correction) but remove process-branding and reviewer-story narration from the introduction, results, conclusion, and disclosure. Put review provenance once in data/code availability or an appendix.

## N6 — “Seventeen reports” is stale

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “the seventeen adversarial review reports and round-1 editorial synthesis” (`paper/index.qmd:999-1001`).
- **Evidence:** `find paper/reviews -maxdepth 2 -type f` yields 21 files total: 20 non-editorial archive files plus `round-1/EDITORIAL.md`. Even excluding the three round-4 reports would not reconcile the present archive description. The same manuscript separately says four rounds are archived (`paper/index.qmd:984-985,1019-1020`).
- **Assessment:** use a generated count or omit the number. The present count understates the archive and undermines a paragraph devoted to reproducibility.

