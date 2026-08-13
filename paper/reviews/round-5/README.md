# Round 5 — adversarial review of revisions 6-7

Reviewed: the working tree of branch `paper-r7` (revisions 6 through 7:
the engine-adoption section, the fiscal 2027 section, the wedge and
component-decomposition paragraphs, the model-repair and confirmation-
harness additions, and FACTS sections M-P). Reports are archived
unedited; referees wrote against the tree as reviewed, so line anchors
predate the resolutions below.

## Resolutions (final revision-7 text)

1. Bounds → scenarios everywhere: the strict/broad pair is described as
   two accounting scenarios under nested code sets, with the
   nonmonotonicity stated as the reason intermediates need not land
   between them (abstract, §adoption, FACTS M2, app copy).
2. FACTS O3 corrected to 7.22340.
3. Protocol-chronology evidence: main's squash merges collapse the
   two-commit ordering; the manuscript now cites the pull-request refs
   (#53, #55), where the ordering was verified via the GitHub API
   (e73ce28→4a5e4af; 9eec8e7→3827f04). The referees' local check
   correctly notes those refs are not fetched by default.
4. $1,029 framing corrected: computed from the published June 2026
   CPI-U (captured July 14 release); pending item is FNA's official
   FY2027 notice. The $59 threshold separately awaits the June TFP
   cost, as already stated.
5. Harness hardened: the freeze check now runs before the manifest
   mutates, and an existing results file refuses overwrite (one-shot
   discipline in code, not just prose); manuscript wording states the
   commitment/enforcement boundary.
6. See 5.
7. External-evidence status stated: the repricing workspace is archived
   (github.com/PolicyEngine/snap-fy27-margins) with SHA-256s recorded
   in the committed fy2027 payload (FACTS N1).
8. National sums now artifact-locked: analysis/adoption_national.json
   (all-53 per-state values, byte-regeneration test) with sums asserted
   against the quoted figures in CI.
9. Wedge named as re-review integration plus ineligible-case error at
   every mention (§adoption, FACTS M2, app copy).
10. "Location, not width" scoped to tested mechanisms ("behaves as
    location rather than width under every tested mechanism").
11. Verification-scope clause added to §adoption (coding covers 53;
    verification covers seven; the other 46 price the coding).
12. The revision-6 review-narration sentence was cut; the review count
    is stated as five rounds. Descriptions of the archive in the
    availability and disclosure sections remain — describing the
    archive is those sections' function.
13. Neutrality phrasings replaced with descriptive language ("still
    open to policy and sampling-plan choices", "the projection this
    method supports", "an unsupported number, so none is shown",
    "the strongest available data").
Minor: the final archival text is the revision-7 merge commit; these
reports reviewed the pre-resolution working tree, as is standard.
