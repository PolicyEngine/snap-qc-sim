# Round-5 methodology referee report

## Recommendation

**Major revision; four blockers.** This report evaluates the revision exactly as reviewed on 2026-08-13. The reviewed manuscript and `FACTS.md` were working-tree files atop commit `5e8b0ba`; quantitative evidence below is taken from committed artifacts unless explicitly identified as an external local workspace. No anticipated maintainer fix changes the finding recorded here.

## M1 — The $7.6B and $6.9B results are scenarios, not ordered bounds

- **Status:** CONFIRMED
- **Severity:** blocker
- **Manuscript passage:** “the strict and broad classes are the bound's two ends” and “expected FY2028 bills move from $7.67B a year to $7.57B under the strict bound and $6.94B under the broad one” (`paper/index.qmd:812-820`). The abstract likewise says bills move “to between $7.6B and $6.9B” (`paper/index.qmd:31-35`). `FACTS.md` calls the classes “bounds” (`paper/FACTS.md:148-150`).
- **Evidence:** `tests/test_adoption_numbers.py:125-131` proves only that strict case flags are nested inside broad flags. The same test suite proves billing is nonmonotone: New York’s broad removals increase expected FY2028 billing from about $629.9M to $1,020.8M (`tests/test_adoption_numbers.py:145-155`), while Georgia’s removals increase FY2029 billing (`tests/test_adoption_numbers.py:158-166`). The manuscript itself concedes “The formula does not price error reduction monotonically” (`paper/index.qmd:829-839`).
- **Assessment:** nested removals order case-level error suppression, not the election/delay/tier billing functional. Therefore there is no theorem that any intermediate coding convention produces a national total between $7.574B and $6.941B. These are two defined accounting scenarios. Calling them endpoints, bounds, a bracket, or “between” is unsupported.

## M2 — Exact component-target value is inconsistent

- **Status:** CONFIRMED
- **Severity:** blocker
- **Manuscript passage:** `FACTS.md` O3 says “file-computable 7.22334” (`paper/FACTS.md:168`).
- **Evidence:** `analysis/component_targets.json` records `national_weighted_summary.file_side.total_pct` as `7.22339927` (single-line JSON; key near the end of the file). Its serialized components are 5.73021904 + 1.49318023 = 7.22339927. Command: `python3 -c 'import json; d=json.load(open("analysis/component_targets.json")); print(d["wedge_decomposition"]["national_weighted_summary"]["file_side"])'`.
- **Assessment:** `7.22334` is not a rounding of `7.22339927` at five decimal places (which is `7.22340`). This is a fact-catalog/artifact contradiction.

## M3 — “Protocol committed before results” needs the actual evidence location

- **Status:** CONFIRMED
- **Severity:** blocker
- **Manuscript passage:** “Two pre-registered repair experiments, each with its protocol committed before results” (`paper/index.qmd:515-516`); P1 says “protocol committed before results; PR #53” (`paper/FACTS.md:174`), and P2 calls the location protocol “pre-registered” (`paper/FACTS.md:175`).
- **Evidence:** main’s squash commits contain protocol and results together: `git show --name-only d272fd9` lists both `analysis/COVERAGE_REPAIR_PROTOCOL.md` and `analysis/coverage_repair_results.json`; `git show --name-only 5e8b0ba` lists both `analysis/LOCATION_REPAIR_PROTOCOL.md` and `analysis/location_repair_results.json`. No `refs/pull/53/head` or `refs/pull/55/head` exists in this local clone (`git show-ref | rg 'refs/pull/(53|55)/head'` returns nothing). However, reachable fetched topic branches do retain ordering: `origin/coverage-repair` contains `e73ce28` (protocol) before `4a5e4af` (results), and `origin/location-repair` contains `9eec8e7` (protocol) before `3827f04` (results); both ancestor tests return success. Thus ordering evidence lives in the reachable remote-tracking topic branches, not main and not locally available GitHub pull refs.
- **Assessment:** the substantive ordering is locally corroborated, but the unqualified manuscript/fact-catalog formulation points readers toward squash commits/PR numbers without saying where the auditable chronology survives. An archival preregistration claim must identify the topic-branch commit pairs (and ideally immutable hosted refs).

## M4 — The $1,029 estimate’s stated reason is stale

- **Status:** CONFIRMED
- **Severity:** blocker
- **Manuscript passage:** “$1,029 (an estimate until the June 2026 index publishes)” (`paper/index.qmd:857-860`); N3 repeats “ESTIMATE until the June 2026 CPI publishes” (`paper/FACTS.md:158`).
- **Evidence:** the local repricing workspace consumed June CPI. `/Users/maxghenis/PolicyEngine/snap-fy27-margins/params/sources/official/cpi_07142026.htm:553-558` identifies the July 14, 2026 BLS release, “CONSUMER PRICE INDEX - JUNE 2026”; its SHA-256 is `3d423a283011885482980ab7ad83efa05b4b1106a216686e8f0f3aebc53e7831`, pinned in `params/sources/official_hashes.json:34-38` and `params/manifest.json:44-47`. The extracted input is June 2026 all-items CPI-U `333.952` (`params/sources/fy2027_projection_inputs_web_extract.json:3-8`), and the projected parameter payload states the remaining hardener is the official FY2027 USDA/FNA COLA memorandum (`params/fy2027_params_projected.json:4-8`). Separately, the repository’s QC-threshold artifact says its archive ended at May and uses May TFP $1,018.20 (`analysis/fy2027_parameters.json:7,49-50`); the external extraction likewise labels $1,018.20 the latest reference-family monthly cost (`.../fy2027_projection_inputs_web_extract.json:291`).
- **Assessment:** $1,029 may remain an estimate pending FNA’s official FY2027 COLA notice and final rounding, but not pending publication of June CPI. The $59 threshold remains pending for a different reason: USDA’s June 2026 Thrifty Food Plan cost. The revision conflates those publication states.

## M5 — “Location, not width” exceeds what was tested

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “every mechanism leaves all nine gaps negative, so the failure is location, not width” (`paper/index.qmd:521-524`); P1 repeats this diagnostic (`paper/FACTS.md:174`).
- **Evidence:** the coverage experiment evaluated the finite mechanisms encoded in `analysis/coverage_repair.py`; its result artifact serializes those candidates and all-negative gaps. The later location experiment found a global shift that improved all levels but left substantial negative residual gaps (`paper/index.qmd:523-535`; `paper/FACTS.md:175`).
- **Assessment:** failure of the tested dispersion repairs supports “among tested mechanisms, a location repair was favored,” not identification that width is not part of the underlying misspecification. The retained one-sided residual after shifting reinforces the need for scoped language.

## M6 — National billing claims outrun the seven-state verification scope

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “across seven states” (`paper/index.qmd:19-24,103-105`) versus “for each jurisdiction” and “Summed over all 53 jurisdictions” (`paper/index.qmd:791-818`).
- **Evidence:** C1 enumerates only CO, NY, CA, AZ, GA, MD, and TX as exact oracle suites (`paper/FACTS.md:31`). M1/M2 export adoption flags and billing for all 53 (`paper/FACTS.md:147-149`).
- **Assessment:** the national scenario is an all-jurisdiction QC cause-code accounting exercise, not a nationwide adoption result for a nationwide verified engine. The text should not allow “engine adoption” to inherit the seven-state verification claim outside those states.

## M7 — The wedge is not merely a federal re-review layer

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “the official rate exceeds the file-computable rate by a federal re-review layer” (`paper/index.qmd:796-799`).
- **Evidence:** the manuscript elsewhere defines the same gap as “federal re-review integration plus the ineligible-case error the file never records” (`paper/index.qmd:622-624`). O1 and the independent test say the same (`paper/FACTS.md:166`; `tests/test_adoption_numbers.py:105-110`). O3 says the two are not separately identified (`paper/FACTS.md:168`).
- **Assessment:** the adoption section abbreviates a composite, unidentified wedge as one component. That changes the interpretation of what is held fixed.

## M8 — National totals lack a national test assertion

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “$7.671B/yr baseline → $7.574B strict / $6.941B broad” (`paper/FACTS.md:148`), sourced in part to `tests/test_adoption_numbers.py`.
- **Evidence:** that test file asserts subset structure, wedge statistics, and CO/NY/GA goldens (`tests/test_adoption_numbers.py:105-166`), but contains no assertion for 7.671, 7.574, or 6.941 (`rg -n '7\.671|7\.574|6\.941' tests/test_adoption_numbers.py` returns no match).
- **Assessment:** the cited “independent Python mirror” does not lock the headline aggregate. State exemplars cannot substitute for an aggregate regression assertion.

