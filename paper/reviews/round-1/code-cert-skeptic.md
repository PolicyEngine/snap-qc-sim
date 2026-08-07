# Adversarial audit: /Users/maxghenis/.cache/axiom-oracles/v2b/CERT_REPORT.md

## 1. Hash recomputation

| Item | Result | Evidence |
|---|---|---|
| Engine binary | **VERIFIED** | `shasum -a 256 cert-probe/cargo-target/release/axiom-rules-engine` = `bb8ec236…5eee`, exact match |
| QC CSV | **VERIFIED** | `shasum -a 256 /Users/maxghenis/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv` = `45193eb7…1aa9`, exact match |
| One-case evidence | **VERIFIED** | `cert-probe/ONE_CASE.json` = `a72bfeec…ff21`, exact match |
| Full-run evidence | **VERIFIED** | `cert-probe/FULL_RUN.json` = `045bc22e…7676`, exact match |
| Standalone compiled artifact | **VERIFIED** | `cert-probe/co-fy2024.compiled.json` = `06feea26…1f95`; size 732,874 bytes as stated |
| Overlay spec | **VERIFIED** | `0590adf0…b617` = SHA-256 of `cert-probe/axiom-oracles/axiom_oracles/bridges/overlays/us-co-snap-fy2024.yaml` in the pinned harness worktree |
| Harness-pinned source archive | **VERIFIED as pin / UNVERIFIABLE as content** | Pin exists at `cert-probe/axiom-oracles/axiom_oracles/populations/snap_qc.py:192-193` (`qcfy2024_csv.zip`, sha `0f3230a4…63f4`). The zip itself is not on disk, so archive-content↔SHA cannot be checked locally |
| Overlay-materialized spot-checks (5 of 17) | **VERIFIED** | `us/statutes/7/2017/a.yaml`, `us/regulations/7-cfr/273/9.yaml`, `us-co/…/4.207.2.yaml`, `us-co/…/4.407.31.yaml`, `us-co/policies/cdhs/snap/fy-2026-benefit-calculation.yaml` under `cert-probe/overlay-materialized/rulespec-us/` all hash to the report's values |

## 2. Worktrees — VERIFIED
`git -C … rev-parse HEAD`: engine `de0efdc7…`, rulespec-us `b53ce208…`, axiom-oracles `d3056626…`; `status --porcelain` empty for all three; all three detached (`symbolic-ref -q HEAD` fails). "Clean **before** execution" is historical and per se unverifiable, but moot — see the rerun below.

## 3. Full-run evidence contents — VERIFIED, with one precision caveat
Independently extracted from `FULL_RUN.json`: `case_count` 856; 856 unique case_ids, all `matched: true`; `summary.match_count` 856, `mismatch_count` 0, `errors: []`, exclusions 0 of 856 loaded. Six aggregates, each `comparison_count` 856, `mismatch_count` 0, `missing_left/right/both` 0, `match_rate` 100, and `left_weighted_sum == right_weighted_sum` exactly. 6 × 856 = 5,136 exactly; tolerance 0 is recorded on each of the 6 concepts.
**Caveat:** the evidence does **not** store six per-case stage values — per-case rows are only `{case_id, matched, stage: null, weight, yrmonth}` and `summary.stages` is `[]`. The 5,136-cell claim rests on the six per-concept counters. This would have been a weakness, except: **I reran the full comparison myself** (same documented bridge, same pins, `sample_size=None, tolerance=0, stage_tolerance=0`) and the output is **byte-identical** to `FULL_RUN.json` (`diff` clean; my wall 4.25 s). The 856/856 and 5,136/5,136 figures are therefore locally reproduced, not merely attested. One-case values also verified: each ONE_CASE aggregate's `left_weighted_sum/weight` and `right_weighted_sum/weight` equal exactly 934/198/392/344/291/187 for case `2024-202310-33270`.

## 4. Timing arithmetic — VERIFIED
856/(3.727721459−0.66) = 279.03445975… → 279.034460 ✓. 856/3.727721459 = 229.63089099… → 229.630891 ✓. 3.727721459/856 = 0.004354814788… → 0.004354815 ✓. All five extrapolation rows recompute exactly (eval, compile, total, minutes to the printed 3 decimals; e.g. 6081/279.03446=21.793, +7×0.66=26.413; 224000/279.03446=802.768, +165.000=967.768). 3.727721459 correctly rounds the logged tool output `"wall_seconds": 3.72772145899944` (err.log:3914); outer `3.80 real` at :3916; `real 0.66` at :3464; `real 2.70` at :3717; `18.75 real` at :2532. Seven-state committed counts (dashboard/public/data/axiom-snapqc-{az,ca,co,ga,md,ny,tx}-snap.json): 922+883+856+945+722+847+906 = **6,081 exactly**, as claimed.

## 5. Mechanism claims — VERIFIED (code read + behavior tested)
- `snap_qc_compare.py:1064-1068`: `axiom_binary = os.environ.get("AXIOM_SNAP_QC_AXIOM_BINARY")` fallback, as stated.
- `:1092-1100`: mkdtemp overlay, `build_overlay`, then line 1100 `env["AXIOM_RULESPEC_REPO_ROOTS"] = str(build.overlay_root)` — sole root, with the union-vs-shadow comment, as stated.
- `:1145-1164`: one `compile_program` then chunked `run` (`CHUNK_SIZE = 500` at :111 → batches of 500+356 for 856), as stated.
- `engine_compat.py:153-177`: probes with `--rulespec-root`, legacy markers include `"unknown compile argument"`, retries bare `compile`, as stated.
- **Behavior test on the pinned binary itself:** `axiom-rules-engine compile --program … --rulespec-root …` → `unknown compile argument `--rulespec-root`` — the exact marker the report claims. (`compile-composed` → `unknown command`, also a recognized legacy marker.)
- **Rebuild test:** rebuilt from the pinned `engine/` checkout with `CARGO_TARGET_DIR=<fresh> cargo build --release --offline` → byte-identical binary hash `bb8ec236…5eee`. The binary↔commit linkage is proven, not assumed.

## 6. Mismatch and unverifiable items

**MISMATCH (one, report-text): "36 module-ID replacements across 16 files."** The recorded OverlaySpec provenance in `FULL_RUN.json`, `ONE_CASE.json`, and my byte-identical rerun sums `rewrite_counts` to **37** across 16 files (the 17th file, `4.407.31.yaml`, is patches-only — that part is correct, as are all four SUA patches 594→560, 377→356, 71→67, 97→91). No tool output in the transcript ever printed 36; it is an author arithmetic error in the prose. It does not affect parity or pinning — all 17 file SHAs match — but the report misstates its own evidence and should say 37.

**UNVERIFIABLE locally (not false):**
- QC zip content ↔ `0f3230a4…` (zip absent; pin verified in harness source; the CSV actually used hash-matches and drove my identical rerun). Authenticity of the QC data against snapqcdata.net is not locally checkable.
- Pre-execution worktree cleanliness (historical; current-state clean + identical rerun makes it immaterial).
- The wall/RSS figures as *measurements* (they appear as genuine tool output in the transcript — err.log:3800-3801 for RSS 296,189,952/135,806,976 — but a transcript is the probe's own record; my rerun's 4.25 s is consistent). Host facts check out: macOS 26.5.1 (`sw_vers`), cargo 1.94.1, Python 3.13.9.
- Extrapolation-table case counts beyond 6,081 (44,800 etc.) — assumptions, and labeled as such.

## 7. Deviations assessment — none undermines certification
(1) `CARGO_TARGET_DIR` redirect: I reproduced the identical binary with the same redirect pattern; harmless. (2) Direct `run_snap_qc_comparison` invocation instead of `scripts/run_comparison.py`: my byte-identical rerun used the same direct bridge; semantics demonstrably unchanged. (3) `/usr/bin/time -l` status 1 from denied `sysctl kern.clockrate` (err.log:2533) with `getrusage` RSS fallback: affects only how memory was captured; memory is calibration, not certification. (4) Stable overlay copy under the workdir: its file hashes match the evidence provenance and the worktrees are clean.

## Verdict

**The CERTIFIED claim stands.** Engine `de0efdc7` × rulespec-us `b53ce208` under harness `d3056626` reproduces CO FY2024 SNAP QC parity at zero tolerance: I independently rebuilt the engine to a byte-identical binary and independently reran the full comparison to a byte-identical `FULL_RUN.json` — 856/856 benefits and 6×856 = 5,136/5,136 asserted cells, zero mismatches/missing/errors/exclusions. Timing arithmetic is internally exact and consistent with logged tool output; ~230 cases/s end-to-end is supported.

**One blocker-class finding before this report ships anywhere:** correct "36 module-ID replacements" to **37** (evidence-recorded value). Secondary wording fix worth making: the stage-cell claim rests on per-concept counters plus reproducibility, not on six stored per-case stage values — the report's "5,136/5,136 exact asserted cells" is true but the evidence file's `summary.stages` is empty and per-case `stage` is null, so a reader auditing the JSON alone will not find per-case cell values. Remaining external dependency: authenticity of the local QC CSV against the pinned upstream zip (`0f3230a4…`) cannot be confirmed offline.