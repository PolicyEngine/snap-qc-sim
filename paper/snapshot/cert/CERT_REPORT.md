# CO SNAP QC certification: CERTIFIED

The candidate historical pin pair is **CERTIFIED** as a reproducible Colorado FY2024 SNAP QC simulation toolchain under the pinned current-main harness. The full zero-tolerance replay produced 856/856 exact benefit matches and 5,136/5,136 exact asserted cells, with no mismatches, missing values, engine errors, or exclusions.

This is certification evidence only. It is not an oracle report, and nothing was committed.

## Pins and artifacts

| Component | Commit / checksum |
|---|---|
| Engine commit | `de0efdc73b469132ee268e1c832e8f7148b91431` |
| Engine release binary | `cargo-target/release/axiom-rules-engine` |
| Engine binary SHA-256 | `bb8ec23689697a5417b74c38196c0488e002e4ee6fe3b33faabb39005e6e5eee` |
| RuleSpec-US commit | `b53ce208771085030939db4b9691762506b6bca2` |
| Harness commit | `d30566266932dbd0b6f62e69dcea8ca3c8801690` |
| Local QC CSV | `/Users/maxghenis/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv` |
| Local QC CSV SHA-256 | `45193eb7370463ab3067d71da23a580fec34a5460341e4e750dda0be061e1aa9` |
| Harness-pinned source archive SHA-256 | `0f3230a4318307d3088382546095eebfde03e781da6f65c9eac7f077bd4263f4` |
| Overlay spec SHA-256 | `0590adf05d940dacf36120db178333dd2275b15fc0d86a7a778ce92f515cb617` |
| Standalone compiled artifact SHA-256 | `06feea26d33a344b78be025613fd142a175b69ceb6d795e0b1d3000950e91f95` |
| Saved one-case evidence SHA-256 | `a72bfeecf8f44ee0ca707c03e9c43f33951445374762fc8ed113183f8e0fff21` |
| Saved full-run evidence SHA-256 | `045bc22ed0291f9761c3bd7d7c79920dd053bf58728ea9795d2fbe0a9bea7676` |

The three worktrees were clean, detached, and exactly at these commits before execution. They remained clean afterward.

## Engine and compatibility mechanism

The engine was built from the pinned `engine/` checkout with:

```text
CARGO_TARGET_DIR=../cargo-target cargo build --release --offline
```

The harness was pointed at that exact binary through `AXIOM_SNAP_QC_AXIOM_BINARY`. The environment fallback is implemented at `axiom-oracles/axiom_oracles/bridges/snap_qc_compare.py:1064-1068`. The overlay becomes the sole RuleSpec root through `AXIOM_RULESPEC_REPO_ROOTS` at `snap_qc_compare.py:1092-1100`, and the composition is compiled once before chunked evaluation at `snap_qc_compare.py:1145-1164`.

This engine predates the canonical-path hard cut. The modern probe failed as expected with `unknown compile argument '--rulespec-root'`; `axiom-oracles/axiom_oracles/engine_compat.py:153-177` recognized that legacy marker and retried bare `compile`, using the overlay root supplied through `AXIOM_RULESPEC_REPO_ROOTS`. The successful standalone compiled artifact is 732,874 bytes.

## Overlay provenance

Overlay: `us-co-snap-fy2024`, materialized from the pinned RuleSpec-US checkout at `overlay-materialized/rulespec-us/`. It made 37 module-ID replacements across 16 files and applied four asserted patches in one additional file:

- heating/cooling SUA: 594 → 560
- basic SUA: 377 → 356
- one-utility SUA: 71 → 67
- telephone SUA: 97 → 91

Every changed-file SHA-256 recorded by `OverlaySpec`:

| Changed file | SHA-256 |
|---|---|
| `us/statutes/7/2017/a.yaml` | `772f90b2817a0c5f421d90288cf2e76b490fccf06b4c4ce7731350eb9de61da9` |
| `us/regulations/7-cfr/273/8.yaml` | `2eb57902785375c837abb8d7a1b7326c20926b1cedd93463c64bbc0ca8981aee` |
| `us/regulations/7-cfr/273/9.yaml` | `9ce1454e8d41621559d88ac8bff912e7fcf6618a54c9c48feb9de621de2baf36` |
| `us/regulations/7-cfr/273/10.yaml` | `b30b75666b34a4c625c480b6a243340c40994e37d5cc9334142c9fd3723ddf78` |
| `us-co/regulations/10-ccr-2506-1/4.206.yaml` | `34485b43cd50936ffe4fbeb09bd8f90ffac106694b91fb394aea2458161fa6e8` |
| `us-co/regulations/10-ccr-2506-1/4.207.2.yaml` | `48a5c480c9b1e12dbf4ddf5ed23f45fcafd66070a49f857ac74cd00777919151` |
| `us-co/regulations/10-ccr-2506-1/4.207.3.yaml` | `2a9ded5c9c76845879f3076f6958eff585577244fdbdfcb01d8409115c37dc17` |
| `us-co/regulations/10-ccr-2506-1/4.305.2.yaml` | `eb9a0afe85c76bf6f38603e96003fb7c5fc9c019524200740c5eb1fec9d296ae` |
| `us-co/regulations/10-ccr-2506-1/4.401.yaml` | `305d3af1498ec8248d49d11828723a6c76742d0c9832f8d9152770f4aede2ca0` |
| `us-co/regulations/10-ccr-2506-1/4.401.1.yaml` | `d8c502cbdc420acaf4d8cb4dc5540e77243259e2827e582bd05ba1e1e5517394` |
| `us-co/regulations/10-ccr-2506-1/4.401.2.yaml` | `e078346cb009c129ed00c730d51cc9da6df920b89308c855589bc5fa2bd0025f` |
| `us-co/regulations/10-ccr-2506-1/4.407.1.yaml` | `908bcc422eb419b8c79e590579dacb5d36c1349fd917478d8e63d8f74fce7e46` |
| `us-co/regulations/10-ccr-2506-1/4.407.3.yaml` | `58dd5c645252c39eeaaa2075384479af6f9dab941e44ecc2759eff8bc7b68a67` |
| `us-co/regulations/10-ccr-2506-1/4.407.31.yaml` | `d373620707c58558261814f99709c40b1d9c423c0df2b1202e96e1702ff92131` |
| `us-co/regulations/10-ccr-2506-1/4.408.yaml` | `2da03ac3e36421501f90d938f62f56bdd39e871891f35eec192866971dc33b68` |
| `us-co/regulations/10-ccr-2506-1/4.408.2.yaml` | `4117a54e621d393bdfd98d7919d47ae896551397a0a188703356e832077cc04e` |
| `us-co/policies/cdhs/snap/fy-2026-benefit-calculation.yaml` | `1aeb049a959ce990408ff793927162417b1677dbaa699156da6460c1ba9cea96` |

The harness evaluated the FY2024 parameter overlay at nominal period `2026-01`, as documented by its provenance, because the regulation/manual chain at this historical pin is snapshot-dated `2025-10-01`.

## Results

The suite ran with benefit tolerance 0 and stage tolerance 0.

| Asserted value | Exact matches |
|---|---:|
| Gross income | 856/856 |
| Standard deduction | 856/856 |
| Shelter deduction | 856/856 |
| Net income | 856/856 |
| Maximum allotment | 856/856 |
| Benefit | 856/856 |
| **All asserted cells** | **5,136/5,136** |

Additional counts: 0 benefit mismatches, 0 stage-cell mismatches, 0 missing-left cells, 0 missing-right cells, 0 missing-both cells, 0 error cases, 0 engine errors, and 0 excluded Colorado records. All 856 loaded records were evaluated.

The one-case sanity run used case `2024-202310-33270` and matched these QC/Axiom values exactly: gross income 934, standard deduction 198, shelter deduction 392, net income 344, maximum allotment 291, and benefit 187.

## Timing and memory calibration

Host: macOS 26.5.1 (`Darwin 25.5.0`, arm64); Python 3.13.9; Cargo/Rust 1.94.1.

| Measurement | Result |
|---|---:|
| Offline release build wall | 18.75 s |
| Standalone harness compile wall | 0.66 s |
| One-case end-to-end wall | 2.70 s |
| Full 856-case harness wall, internal monotonic clock | 3.727721459 s |
| Full 856-case outer `/usr/bin/time` wall | 3.80 s |
| Observed end-to-end throughput | 229.630891 cases/s |
| Observed end-to-end time per case | 0.004354815 s (4.354815 ms) |
| Peak harness RSS fallback (`RUSAGE_SELF`) | 296,189,952 bytes (282.469 MiB) |
| Peak child-process RSS fallback (`RUSAGE_CHILDREN`) | 135,806,976 bytes (129.516 MiB) |

The full-run wall includes CSV loading, overlay materialization, one compile, mapping, two `run-compiled` batches (500 and 356 cases), and comparison/report assembly.

### Extrapolation with state compiles amortized

For compile-aware extrapolation, the observed CO run is de-amortized into a compile term and a case-evaluation term:

```text
evaluation rate = 856 / (3.727721459 - 0.66) = 279.034460 cases/s
total seconds = case-evaluations / 279.034460 + compile count × 0.66
```

This reconstructs the observed CO end-to-end rate after one state compile. Compile-count assumptions are one compile per state-period composition: 7 for the currently encoded seven-state QC scope (whose committed case counts sum exactly to 6,081), 12 for the 12-state tier, 50 for one nationwide period, 100 for two nationwide periods, and 250 for five nationwide periods.

| Scope tier | Case-evaluations | Compile assumption | Evaluation seconds | Compile seconds | Total seconds | Total minutes |
|---|---:|---:|---:|---:|---:|---:|
| Current seven-state QC scope | 6,081 | 7 | 21.793 | 4.620 | **26.413** | 0.440 |
| Twelve-state scope | 10,593 | 12 | 37.963 | 7.920 | **45.883** | 0.765 |
| Nationwide, one period | 44,800 | 50 | 160.554 | 33.000 | **193.554** | 3.226 |
| Nationwide, two periods | 89,600 | 100 | 321.107 | 66.000 | **387.107** | 6.452 |
| Nationwide, five periods | 224,000 | 250 | 802.768 | 165.000 | **967.768** | 16.129 |

These are linear timing projections from this host and binary, not benchmark guarantees. They assume the CO case mix, two engine batches per roughly 856-case state, no concurrent state execution, and no additional I/O contention.

## Deviations and limitations

1. Generated Cargo output was redirected to workdir-level `cargo-target/` with `CARGO_TARGET_DIR` instead of writing `engine/target/`, to honor the instruction not to modify the staged checkout. The build still ran with `engine/` as its working directory and used `--release --offline` exactly as requested.
2. `uv run --offline` could not initialize its default cache because the managed sandbox denied a metadata write to `~/.cache/uv/sdists-v9/.git`. No network was attempted. The run instead used the cached Python 3.13.9 interpreter and cached unpacked PyYAML 6.0.3 directly, with the pinned harness source on `PYTHONPATH`. The documented `run_snap_qc_comparison` bridge was invoked directly rather than `scripts/run_comparison.py`, avoiding writes to dashboard/report paths inside the checkout; comparison semantics and parameters were unchanged.
3. `/usr/bin/time -l` was used for the build and full run, but this sandbox denies its terminal `sysctl kern.clockrate` call. Cargo and the full harness both completed successfully and wrote their artifacts before `/usr/bin/time` returned status 1. BSD `time` printed wall/user/sys times but omitted its extended RSS fields, so peak RSS was captured in the same full-run process with Python `resource.getrusage` instead. The reported 282.469 MiB is therefore a same-run fallback, not a value emitted by `/usr/bin/time -l`.
4. The stable provenance overlay at `overlay-materialized/` was created explicitly under the workdir. The harness's own one-case and full-run overlays used its normal temporary scratch directories and were removed automatically. No source file in any staged worktree was edited.
## Independent verification (2026-08-06, adversarial audit)

A second, independent auditor rebuilt the engine from the pinned checkout to a
byte-identical binary (SHA-256 match) and reran the full comparison with the
same pins, producing a byte-identical FULL_RUN.json — the 856/856 and
5,136/5,136 figures are reproduced, not merely attested. Two precision notes
from that audit: (1) the original prose said 36 module-ID replacements; the
recorded OverlaySpec provenance sums to 37 (corrected above); (2) the
5,136-cell claim rests on six per-concept counters (each comparison_count 856,
mismatch 0, tolerance 0) plus byte-identical reproduction — the evidence JSON
does not store six per-case stage values (per-case rows record matched status
only). Remaining external dependency: the local QC CSV's authenticity against
the pinned upstream archive (0f3230a4…) is not checkable offline; the CSV used
hash-matches the harness pin's expected input and drove the identical rerun.
