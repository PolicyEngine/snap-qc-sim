# Round-5 revision-difference referee report

## Scope

This report reviews the revision-7 additions and changed claims as they appear in the working manuscript reviewed on 2026-08-13, atop `5e8b0ba`. The new material is concentrated in `FACTS.md` P1-P3 and the manuscript’s repair-experiment, FY2025 confirmation, adoption, wedge, and FY2027 passages. Earlier claims were rechecked where the revision newly relies on them.

## RD1 — Repair experiments add useful evidence but overstate diagnosis and chronology

- **Status:** CONFIRMED
- **Severity:** blocker for chronology; major for interpretation
- **New passage:** “Two pre-registered repair experiments, each with its protocol committed before results” and “failure is location, not width” (`paper/index.qmd:515-535`; `paper/FACTS.md:174-175`).
- **Evidence:** squash commits `d272fd9` and `5e8b0ba` co-locate protocols/results. Topic branches preserve protocol-first pairs `e73ce28→4a5e4af` and `9eec8e7→3827f04`; local pull refs do not exist. The experiments evaluate specified candidate mechanisms, not every possible dispersion misspecification.
- **Diff assessment:** revision 7 improves transparency by reporting failed mechanisms and per-level guards. It must cite the branch commit pairs and scope the “location” conclusion to tested repairs.

## RD2 — The FY2025 confirmation harness adds a prospective scaffold but not one-shot enforcement

- **Status:** CONFIRMED
- **Severity:** major
- **New passage:** “one command and one shot” (`paper/index.qmd:438-440`; `paper/FACTS.md:176`).
- **Evidence:** the runner overwrites results and permits identical-input reruns (`analysis/fy2025_confirmation.py:186-198,322-357`). It records input before drift checking (`analysis/fy2025_confirmation.py:329-332`).
- **Diff assessment:** hash closure, fixed hyperparameters, metric references, and drift refusal are material improvements. The archival language nonetheless claims controls the executable does not provide.

## RD3 — The new component registry contains an exact-number transcription error

- **Status:** CONFIRMED
- **Severity:** blocker
- **New passage:** O3 reports `7.22334%` (`paper/FACTS.md:168`).
- **Evidence:** committed `analysis/component_targets.json` reports `7.22339927%`; components sum to that value.
- **Diff assessment:** correct the catalog to `7.22339927` or appropriately rounded `7.22340`.

## RD4 — The adoption revision’s strongest headline is mislabeled as a bound and incompletely tested

- **Status:** CONFIRMED
- **Severity:** blocker for bounds; major for test coverage
- **New passage:** $7.67B to $7.57B/$6.94B “strict and broad” bounds (`paper/index.qmd:812-820`; `paper/FACTS.md:148-150`).
- **Evidence:** billing nonmonotonicity is explicitly demonstrated (`paper/index.qmd:829-839`; `tests/test_adoption_numbers.py:145-166`). The independent mirror does not assert the three national sums.
- **Diff assessment:** present these as two accounting scenarios and add an aggregate lock. Preserve the useful New York/Georgia counterexamples because they explain why “bounds” fail.

## RD5 — FY2027 additions rely on an external workspace and contain stale input-status prose

- **Status:** CONFIRMED
- **Severity:** blocker for $1,029 framing; major for reproducibility
- **New passage:** FY2027 projection/self-oracle description (`paper/index.qmd:851-888`; `paper/FACTS.md:156-158`).
- **Evidence:** source gates reside in `/Users/maxghenis/PolicyEngine/snap-fy27-margins`, not `snap-qc-sim`. That workspace consumed June CPI-U from BLS’s July 14 release (`cpi_07142026.htm:553-558`; extraction JSON `:3-8`), so “until the June CPI publishes” is stale. The actual remaining hardener for $1,029 is FNA’s official FY2027 COLA schedule; the $59 threshold separately awaits June TFP, with only May $1,018.20 locally available (`analysis/fy2027_parameters.json:7,49-50`).
- **Diff assessment:** archive the workspace inputs/gates or publish a durable external artifact, and separate the two pending official publications.

## RD6 — Review-process narration and count drift expanded rather than receded

- **Status:** CONFIRMED
- **Severity:** major
- **Passage:** repeated “four rounds of adversarial review” (`paper/index.qmd:133-134,984-985,1019-1020`) and “seventeen” reports (`paper/index.qmd:999-1001`).
- **Evidence:** current archive has 21 files: 20 reports/readmes plus one editorial synthesis.
- **Diff assessment:** consolidate process history into availability material and remove the stale hard-coded count.

## Overall round-diff judgment

Revision 7 adds genuinely valuable diagnostic and prospective infrastructure, but it also converts procedural aspirations into stronger claims than the artifacts support. The correction burden is concentrated and auditable: relabel scenarios, fix O3, cite actual branch chronology, distinguish published CPI from pending FNA/TFP inputs, enforce or soften “one shot,” archive FY2027 evidence, and neutralize process rhetoric.

