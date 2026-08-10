# Feature registries

## State BBCE

`state_bbce.csv` is a compact model-year extract of the USDA Food and
Nutrition Service SNAP State Options reports. The official report landing page
is <https://www.fns.usda.gov/snap/waivers/state-options-report>. FY2024 uses
the 16th edition, whose information is current as of October 1, 2023:
<https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-16th-state-options-report-june24.pdf>.

The source extraction was
`snap_state_options_all_years.csv` from the public `giannella/snap_qc` data
pipeline, SHA-256
`3f3f035c7ded13996e43b1a43e7ec0e4a742bb17522d1f730edb0990aafe08cb`.
The execution sandbox exposed the official PDF through its parsed-text reader
but blocked a raw-byte download, so the official PDF's SHA-256 is unavailable
and that source-pin gate remains unmet. The extracted-panel hash above and the
vendored `state_bbce.csv` hash in `model_results.json` are reproducibility
fallbacks; neither is represented as the PDF's hash.
The mapping is:

- FY2017: 13th edition, status as of October 1, 2016.
- FY2018: 14th edition, status as of October 1, 2017.
- FY2019: 14th-edition status carried forward because FNS published no newer
  edition until 2023.
- FY2022: 15th-edition status as of October 1, 2022, used as an end-of-FY proxy.
- FY2023: 15th edition, status as of October 1, 2022.
- FY2024: 16th edition, status as of October 1, 2023.

The carried/proxy years are disclosed model inputs, not inferred case-level
registries. `CAT_ELIG` cannot uniquely recover BBCE adoption because its codes
also cover other forms of categorical eligibility.

## Medicare Part B

`medicare_part_b_premiums.csv` records exact standard monthly premiums by
calendar year and an official Centers for Medicare & Medicaid Services source
for every calendar year present in the analysis samples. Fiscal-year QC files
are mapped by their `YRMONTH` calendar year, not by fiscal-year label.
