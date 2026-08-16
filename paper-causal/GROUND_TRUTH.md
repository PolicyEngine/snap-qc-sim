# Current reality

| Item | Value | Confidence | Trace |
|---|---|---|---|
| RI event | UHIP; 2016-09; Deloitte | High / verified multi-source | `analysis/system_migrations.json:events[0]` |
| KY event | Benefind; 2016-02-29; Deloitte | High / verified multi-source | `analysis/system_migrations.json:events[1]` |
| OR event | ONE Eligibility SNAP expansion; 2021-02; vendor unsupported | Medium / verified single-source | `analysis/system_migrations.json:events[3]` |
| RI primary | +2.896764 strict; p 0.023256; client p 0.232558; signal | High / committed result | `analysis/riky_event_study_results.json:units.RI` |
| KY primary | −0.584303 strict; p 0.302326; client p 0.116279; no protocol-defined signal | High / committed result | `analysis/riky_event_study_results.json:units.KY` |
| OR primary | −0.199724 strict; p 0.714286; client p 0.028571; no protocol-defined signal | High / committed result | `analysis/event_study_results.json:decision`; `.specifications.primary_drop_fy2021` |
| Pooled RI/KY | +1.156231 strict; p 0.093023; client p 1.0; signal | High / committed result | `analysis/riky_event_study_results.json:pooled` |
| RI bill | $37,343,809.68; Sep 2016–Dec 2019 | High / registry multi-source | `analysis/system_migrations.json:events[0].notes` |
| Parent RI donor fit | CT/DC/MI/VT/WV; dominant WV/MI | High / committed result | `analysis/riky_event_study_results.json:units.RI.specifications.primary_exclude_fy2016_drop_fy2021.donor_weights` |
| Joint decomposition donor fit | CT/DC/MD/MI/OH/SD; dominant OH/SD | High / committed result | `analysis/uhip_decomposition_results.json:primary_specification.donor_weights` |
| Joint-fit placebo | +5.637221; p 0.023256 | High / committed result | `analysis/uhip_decomposition_results.json:client_placebo` |
| Fixed-donor protocol | frozen 2026-08-16; parent fit held fixed | High / branch protocol | `origin/fixed-donor-protocol:analysis/FIXED_DONOR_PROTOCOL.md` |
| Fixed-donor results | absent from `origin/fixed-donor-protocol` | High / branch-tree check 2026-08-16 | `[NEEDS CITATION: fixed-donor result artifact]` |
| RI/KY threshold | 68.3138496651 FY2024 dollars | High / committed result | `analysis/riky_event_study_results.json:outcome_definitions` |
| Oregon threshold | 56 FY2024 dollars | High / committed result | `analysis/event_study_results.json:outcome_definitions` |
| Strict code class | 17 programming; 19 mass-change; 20 arithmetic | High / committed code map | `analysis/cause_shares.json:cause_codes` |
| Client superclass | 1,2,3,4,7; analytic, not codebook binary | High / committed code map | `analysis/cause_shares.json:class_semantics.client_or_fact` |
| FY2020 | 27,112-row reconciled combined file | High / audit | `analysis/coding_consistency.json:pandemic_file_handling.fy2020` |
| FY2021 | 9,832-row pandemic-partial file | High / audit | `analysis/coding_consistency.json:pandemic_file_handling.fy2021` |

# Hard prohibitions

- No causal language beyond "bundled system replacement as implemented".
- No "effect of a rules engine".
- No "effect of software".
- No design advice.
- No state-shaming.
- No policy positions.
- No review-process narration in paper body.
- No "prototype" framing.
- No defensive framing.
- No conversion-status claim from certification vintage.
- No confirmation/validation claim from consequence-window alignment.
- No interpretation of `no_protocol_defined_signal` as implementation success.
- No joint-fit channel `signal` when client placebo p < 0.10.
- No fixed-donor numerical claim until committed result artifact exists.

# Allowed bib keys

- `nrc1987rethinking` | verified anchor + bib key | `analysis/LITERATURE.md:36`; `paper/references.bib`
- `gao1984liability` | verified anchor + bib key | `analysis/LITERATURE.md:51`; `paper/references.bib`
- `dellavigna2018predicting` | verified anchor + bib key | `analysis/LITERATURE.md:38`; `paper/references.bib`
- `dellavigna2020forecasting` | verified anchor + bib key | `analysis/LITERATURE.md:39`; `paper/references.bib`
- `gao2007errors` | verified anchor + bib key | `analysis/LITERATURE.md:40`; `paper/references.bib`
- `homonoff2021recertification` | verified anchor + bib key | `analysis/LITERATURE.md:47`; `paper/references.bib`
- `abadie2021using` | verified anchor + bib key | `analysis/LITERATURE.md:48`; `paper/references.bib`
- `abadie2010synthetic` | verified anchor + bib key | `analysis/LITERATURE.md:49`; `paper/references.bib`
- `doj2019texas` | verified anchor + bib key | `analysis/LITERATURE.md:52`; `paper/references.bib`
- `doj2021snapqc` | verified DOJ settlement cluster; existing bib key | `analysis/LITERATURE.md:52`; `paper/references.bib`
- `crs2018errors` | verified CRS R45147 anchor; existing bib key | `analysis/LITERATURE.md:53`; `paper/references.bib`
- Existing bib keys without verified-anchor status: prohibited for causal paper unless separately verified.
- Verified anchors without existing bib keys: Goldstein–Spiegelhalter 1996; Peeters–Widlak 2018; Peeters–Widlak 2023; Press–Tanur 1991; Lawsky 2017; Coding the Code 2022; Florida/Louisiana/Tennessee/consultant DOJ records. Add bib entries before citation.

# Needs citation

- [NEEDS CITATION: Oregon ONE vendor]
- [NEEDS CITATION: Oregon ONE documented launch problems]
- [NEEDS CITATION: Oregon FNS billing record, if any]
- [NEEDS CITATION: Kentucky FNS billing record, if any]
- [NEEDS CITATION: Georgia Gateway vendor and statewide completion date]
- [NEEDS CITATION: NM ASPEN date, vendor, launch record, problems, billing]
- [NEEDS CITATION: IN modernization exact go-live and primary public record]
- [NEEDS CITATION: CO CBMS exact go-live, vendor, problems, billing]
- [NEEDS CITATION: fixed-donor decomposition results]
- [NEEDS CITATION: direct third-party quotation; none cataloged]
- [NEEDS CITATION: interpretation of RI element codes; labels not extracted]
