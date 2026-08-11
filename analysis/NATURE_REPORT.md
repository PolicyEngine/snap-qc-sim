# FY2024 finding-nature tabulation report

- Date: 2026-08-11
- Branch: `nature-classes`
- Base commit: `c57597d43c82615aeda23553e18dcc2a330eb778` (local cached `origin/main`)
- Requested destination fallback: this file is the workspace-safe fallback for `/Users/maxghenis/PolicyEngine/NATURE_REPORT.md`, which is outside the writable sandbox.

## Outcome

`analysis/cause_shares.py` now produces a deterministic Layer 2 finding-nature tabulation for Colorado, every one of the 53 jurisdictions, and the national total. `analysis/cause_shares.json` is schema v2. Every existing artifact value remains unchanged except the required schema identifier/version and generator hash; the new semantics, provenance, and row results are additive.

The archived Colorado table is reproduced exactly, but the requested primary rule does not reproduce it. The reason is substantive: the archived lab used the six-code `broad_rules_engine` set `{10, 17, 19, 20, 21, 22}`, while the existing serialized `agency_or_system` class requested for this task contains codes `{10, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25}`. The artifact therefore reports both, without substituting one for the other:

- `primary_agency_or_system`: the requested rule, used for both deviation and official-error conventions.
- `lab_legacy_broad_rules_engine`: a clearly labeled regression cross-check that reproduces the archived Colorado table.

## Field semantics and implemented rule

The prompt's nature-code list was labeled as `E_FINDG` values, but that is not the FY2024 public-file schema. The detailed-field inventory identifies `E_FINDGi` as error finding, `ELEMENTi` as variance element, `NATUREi` as nature of variance, and `AGENCYi` as agency/client responsibility (`techdoc.txt:L6179-L6234`). The detailed codebook then defines:

- `E_FINDG1-E_FINDG9` only as variance impact: 2 overissuance, 3 underissuance, and 4 ineligible (`techdoc.txt:L12090-L12130`). No requested nature code belongs in this field.
- `ELEMENT1-ELEMENT9` as the affected program element, including code 520, arithmetic computation (`techdoc.txt:L12132-L12145`, `techdoc.txt:L12444-L12454`).
- `NATURE1-NATURE9` as the nature of each variance (`techdoc.txt:L12486-L12508`). Codes 36, 42, 43, 52, 53, 54, 56, 57, 64, 65, 75, 79, 80, and 98 and their labels appear at `techdoc.txt:L12600-L12760`; code 123, income incorrectly prorated, appears at `techdoc.txt:L12788-L12798`.
- `AGENCY1-AGENCY9` as the primary cause of each same-suffix variance (`techdoc.txt:L11816-L11838`). The labels underlying the existing `agency_or_system` analysis mapping—codes 10, 12, and 14 through 25—appear at `techdoc.txt:L11882-L11960`.

The implemented primary slot rule is therefore:

1. A finding slot is populated when `ELEMENTi` is nonmissing, matching the archived lab's `(ELEMENTi, NATUREi, AGENCYi)` finding tuples.
2. A populated slot is computational when `NATUREi` is one of `{36, 42, 43, 54, 64, 65, 75, 79, 80, 98, 123}`, or `ELEMENTi == 520`.
3. `NATUREi` in `{52, 53, 56, 57}` is computational only when the paired `AGENCYi` belongs to the existing `agency_or_system` class. A system cause in another slot does not make the deduction finding computational.
4. `pure_math` means every populated finding is computational. `mixed` means some but not all are computational. `input_system_caused` means none is computational and at least one populated slot has a system-side cause. `input_other` is the remainder, including cases with no populated finding.

The case universe is `CASE == 1`, documented as included in the error-rate calculation (`techdoc.txt:L6348-L6377`). The deviation convention uses `STATUS in {2,3}` and `AMTERR > 0`; status codes 2 and 3 are overissuance and underissuance (`techdoc.txt:L6766-L6794`). The official-error convention additionally applies the FY2024 `$56` threshold already used by Layer 1. `AMTERR` is the identified benefit-error amount (`techdoc.txt:L9484-L9501`), and dollars are `HWGT * AMTERR`; `HWGT` is the monthly sample weight (`techdoc.txt:L7358-L7377`).

## Colorado regression against the lab

The legacy cross-check reproduces the archived Layer 2 table over 305 deviation cases and `$112,575,220.49` in weighted deviation dollars:

| Class | Archived cases | Recomputed cases | Archived dollars | Recomputed dollars | Recomputed share | Result |
|---|---:|---:|---:|---:|---:|---|
| `pure_math` | 13 | 13 | `$3.66M` | `$3,662,840.51` | 3.2537% | Exact underlying anchor |
| `input_system_caused` | 19 | 19 | `$7.47M` | `$7,468,437.90` | 6.6342% | Exact underlying anchor |
| `mixed` | 13 | 13 | `$4.68M` | `$4,683,116.80` | 4.1600% | Exact underlying anchor |
| `input_other` | 260 | 260 | `$96.8M` | `$96,760,825.27` | 85.9522% | Exact underlying anchor |

The archived manuscript percentages are one-decimal displays: 3.3%, 6.6%, 4.2%, and 86.0%. The committed-data test locks the case counts, cent values, and full serialized shares above.

The requested broader primary rule changes Colorado materially because deduction findings paired with codes 12 and 14-16 or 18 and agency-caused noncomputation findings paired with codes 12 and 14-16, 18, or 23-25 now count as system-side:

| Convention and class | Cases | Dollars | Share |
|---|---:|---:|---:|
| Deviation — `pure_math` | 40 | `$15,295,781.89` | 13.5872% |
| Deviation — `input_system_caused` | 56 | `$35,031,092.45` | 31.1179% |
| Deviation — `mixed` | 29 | `$18,032,500.75` | 16.0182% |
| Deviation — `input_other` | 180 | `$44,215,845.40` | 39.2767% |
| Official error — `pure_math` | 21 | `$13,395,063.37` | 14.2360% |
| Official error — `input_system_caused` | 35 | `$33,069,620.07` | 35.1458% |
| Official error — `mixed` | 17 | `$16,901,966.88` | 17.9631% |
| Official error — `input_other` | 37 | `$30,726,141.70` | 32.6551% |

The official-error denominator is 110 cases and `$94,092,792.02`.

## National results

The requested primary rule yields the following national results across all 53 jurisdictions:

| Convention and class | Cases | Dollars | Share |
|---|---:|---:|---:|
| Deviation — `pure_math` | 2,526 | `$968,347,020.00` | 11.9065% |
| Deviation — `input_system_caused` | 3,130 | `$2,380,768,103.94` | 29.2731% |
| Deviation — `mixed` | 1,492 | `$984,704,322.81` | 12.1076% |
| Deviation — `input_other` | 10,683 | `$3,799,137,328.18` | 46.7129% |
| Official error — `pure_math` | 1,108 | `$821,751,204.93` | 12.4690% |
| Official error — `input_system_caused` | 1,543 | `$2,158,507,246.76` | 32.7524% |
| Official error — `mixed` | 771 | `$871,313,060.98` | 13.2210% |
| Official error — `input_other` | 2,006 | `$2,738,802,628.10` | 41.5576% |

The deviation denominator is 17,831 cases and `$8,132,956,774.93`. The official-error denominator is 5,428 cases and `$6,590,374,140.76`.

For comparison, the legacy-lab rule on the national deviation denominator produces 1,207 `pure_math` cases and `$377,287,921.21` (4.6390%); 1,657 `input_system_caused` cases and `$905,494,223.82` (11.1336%); 803 `mixed` cases and `$530,592,553.25` (6.5240%); and 14,164 `input_other` cases and `$6,319,582,076.64` (77.7034%).

## Determinism and gates

| Gate | Result |
|---|---|
| Generator run twice | Pass |
| Byte-identical second run | Pass, SHA-256 `c5b16617b982ce6e00f70142652cd2bcc9fc145a33ad7fce341de84b8eff61bb` both times |
| Existing artifact keys byte-stable where untouched | Pass; recursive comparison against `origin/main` after removing only intentional additions/changes |
| `UV_CACHE_DIR=/private/tmp/snap-qc-uv-cache uv run --frozen --extra dev --extra analysis pytest -q` | Pass, 163 tests |
| `UV_CACHE_DIR=/private/tmp/snap-qc-uv-cache uv run --frozen --extra dev --extra analysis ruff check analysis tests` | Pass |
| Files under `paper/` or `app/` changed | None |

## Disclosed deviations and limitations

- The requested `agency_or_system` definition and the archived lab definition are not the same. The primary results honor the requested existing class; the exact lab anchors are retained only under the explicitly named legacy rule. No anchor was forced and no cause set was silently substituted.
- The current pinned SAV has 44,800 `CASE == 1` records, 17,831 positive deviation cases, and `$8.133B` in deviation dollars. The archived `native_decomposition.json` reports 44,891 cases, 17,836 deviation cases, and `$8.136B`. Colorado is unchanged and reproduces exactly; the national legacy result is computed from the current committed pipeline input rather than copied from the older snapshot.
- Nationally, 41 positive-deviation cases have no populated `ELEMENTi` finding (11 under the official-error convention). The stated remainder rule places them in `input_other`; the artifact exposes these counts in diagnostics.
- `git fetch origin` was attempted first but failed because the environment could not resolve `github.com`. Local `main` and cached `origin/main` both resolved to `c57597d43c82615aeda23553e18dcc2a330eb778`, and the branch was created from that cached remote-tracking ref.
- The repository checkout contains no `CLAUDE.md`; `/Users/maxghenis/PolicyEngine/CLAUDE.md` was read and followed.
