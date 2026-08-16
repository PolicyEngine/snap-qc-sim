# Methodology referee report — round 2

Scope: `paper-causal/index.qmd` at `ee2ba43`, checked against the four frozen protocols and the requested committed artifacts (the three branch artifacts and the fixed-donor snapshot are byte-identical to `main@4aafd06`).

## Findings

1. **blocker — PLAUSIBLE — The abstract's “flat client-caused placebo” is not supported by the artifact at that precision or in ordinary language.** Line 8 calls the Rhode Island client placebo “flat,” but `analysis/riky_event_study_results.json:.units.RI.specifications.primary_exclude_fy2016_drop_fy2021.outcomes.client_dollars_per_case_month.effect` is **+$3.9642021849522484 per case-month**. Its p-value is 0.232558 and it does not fire the frozen rule; neither fact makes the estimated movement flat. This prominent unsupported numerical characterization survived round 1.

2. **blocker — PLAUSIBLE — The donor-population correction remains incomplete in the conclusion.** Line 267 ends with “a named donor set of states with no recorded migration.” Unlike the abstract (“in a public event registry”) and introduction (“in the paper's event registry”), this formulation can be read as a verified migration history. The protocols establish only no dated or candidate entry in `system_migrations.json`, whose gaps the paper acknowledges. Because the donor definition bears directly on identification, the missing registry qualifier is more than cosmetic.

3. **minor — CONFIRMED — The manuscript changes the protocol's literal verdict spelling in one design-definition sentence.** Line 105 defines the fallback as “no protocol-defined signal,” while both protocols and artifacts use `no_protocol_defined_signal`. The manuscript applies the machine verdict correctly elsewhere, so this is a local terminology drift rather than a misclassified result.

## Changed-passage verification

- **Abstract (line 8):** RI +$2.90/p=0.023; joint-fit mass change +$2.08; fixed donor +$2.14; both p=0.023 and rank 1/43; joint client p=0.023; worker and entry below the count gate all match the artifact keys. The word “flat” is the exception above.
- **Rewritten introduction (lines 22–61):** no quantitative estimate appears. The formal unit verdicts are correct: RI `signal`; KY and OR `no_protocol_defined_signal`. Joint fitting versus fixed donor is described correctly.
- **Artifacts section (lines 210–241):** filenames, generators, test files, commit, environment command, SHA prefixes `ffbf63b1…` and `80dad3c0…`, raw-cache dependence, skip behavior, and value-not-byte regeneration match the repository.
- **Conclusion (lines 263–267):** every displayed effect, p-value, rank, billing amount, and verdict matches its artifact at the shown precision. The donor qualifier is the exception above.

## Protocol checks passed

Joint nonnegative unit-sum fitting; scaling by donor-state pretreatment SD; post-mean gap minus pre-mean gap; refitting pseudo-treated states; absolute ranking; ties against signal; plus-one p-values; denominators 43 and 35; FY2016 transition handling; FY2021 pandemic handling; Oregon's four-pre/eight-post split; and Oregon's registry and delay-roster exclusions all match the protocols. Formal uses of `signal`, `no_protocol_defined_signal`, and `signal_family_adjusted` match the artifacts. The consequence-window profiles remain explicitly descriptive and verdict-inert.
