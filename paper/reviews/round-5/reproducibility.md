# Round-5 reproducibility referee report

## Recommendation

**Major revision.** The core repository artifacts are unusually inspectable, but the new FY2027 and preregistration claims are not self-contained as archived.

## P1 — FY2027 repricing and self-oracle evidence is outside the reviewed repository

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “all required calibration gates pass ... with the repricing authorized by a self-oracle gate” (`paper/index.qmd:865-873`). N1 sources those claims to `snap-fy27-margins/reweight/reweight_summary.json` and `snap-fy27-margins/reprice/self_oracle_gate.json` (`paper/FACTS.md:156`).
- **Evidence:** `rg --files` in `snap-qc-sim` finds neither path. They exist only at `/Users/maxghenis/PolicyEngine/snap-fy27-margins/...`, outside the repository under review. The committed app payload contains derived results and provenance hashes (`app/public/fy2027_data.json:8-21`) but not the complete source workspace/gates.
- **Assessment:** a reader cloning the paper repository cannot inspect or rerun the key authorization and reweighting evidence. Hash references do not supply missing bytes, code, data, or commands.

## P2 — National adoption headline numbers are not regression-locked

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** M2 attributes $7.671B/$7.574B/$6.941B to the app and independent Python test (`paper/FACTS.md:148`).
- **Evidence:** `tests/test_adoption_numbers.py:105-166` contains no aggregate assertion. Command: `rg -n '7\.671|7\.574|6\.941' tests/test_adoption_numbers.py` produces no output. It locks only wedge statistics and CO/NY/GA.
- **Assessment:** add a deterministic aggregate assertion over all 53 or stop citing the test as confirmation of that headline.

## P3 — The “one-shot” result can be overwritten

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “one command and one shot” (`paper/index.qmd:438-440`; `paper/FACTS.md:176`).
- **Evidence:** `analysis/fy2025_confirmation.py:322-357` overwrites `analysis/fy2025_confirmation_results.json`; identical input is accepted (`analysis/fy2025_confirmation.py:186-198`). No test asserts refusal on a second non-dry run.
- **Assessment:** the archive cannot prove how many runs occurred. An immutable first-run record, refusal on existing results, and explicit override producing a separately labeled file are needed for the claimed control.

## P4 — Input provenance is written before drift validation

- **Status:** CONFIRMED
- **Severity:** major
- **Manuscript passage:** “runner refuses drifted modules (fail-closed)” (`paper/FACTS.md:176`).
- **Evidence:** ordering is `record_input` then `verify_freeze` (`analysis/fy2025_confirmation.py:329-332`); `record_input` writes bytes (`analysis/fy2025_confirmation.py:186-198`).
- **Assessment:** verify all frozen dependencies and validate the input path/schema before committing the input record, or write atomically only after every preflight passes.

## P5 — Protocol chronology is recoverable only from topic-branch history in this clone

- **Status:** CONFIRMED
- **Severity:** blocker
- **Manuscript passage:** “protocol committed before results” (`paper/index.qmd:515-516`; `paper/FACTS.md:174-175`).
- **Evidence:** main squash commits `d272fd9` and `5e8b0ba` each add protocol and results together. Local `refs/pull/53/head` and `refs/pull/55/head` are absent. Chronology survives in reachable `origin/coverage-repair` (`e73ce28` → `4a5e4af`) and `origin/location-repair` (`9eec8e7` → `3827f04`).
- **Assessment:** cite those exact commit pairs and preserve them in durable refs. “PR #53/#55” alone is not the locally inspectable evidence.

## P6 — Reviewed source state is not a single committed revision

- **Status:** CONFIRMED
- **Severity:** minor
- **Manuscript passage:** the archive describes a public repository and committed artifacts (`paper/index.qmd:127-134,990-1008`).
- **Evidence:** at review, `git status --short --branch` reports `paper-r7...origin/main`, with modified `paper/index.qmd`, `paper/FACTS.md`, and rendered paper files plus untracked reports. HEAD is `5e8b0ba`.
- **Assessment:** this referee record is correctly about the working revision as reviewed, but publication should identify a commit containing the exact manuscript and fact catalog so line anchors and rendered output are durable.

## Commands used

All repository inspection was read-only. Principal commands were `rg -n`, `nl -ba`, `git show`, `git log --all`, `git show-ref`, `git merge-base --is-ancestor`, `sha256sum`, and Python JSON reads. No source repository file was changed and no network access was used.

