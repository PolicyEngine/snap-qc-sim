# amterr lab: rerunning it

This directory holds the Colorado FY2024 error-case lab described in
`ANALYSIS.md`. It has three stages:

1. `reconstruct_co_fy2024.R` (R) reconstructs each error case's pre-correction
   inputs and writes `co_fy2024_reconstruction.csv` and
   `fy2024_reconstruction_national.csv`.
2. `amterr_replay.py` (Python, inside an axiom-oracles checkout) runs the Axiom
   rules engine on those inputs and writes `amterr_replay_results.json`.
3. `audit_claims.py` (Python, this repository) recomputes every figure in
   `ANALYSIS.md` into `claims_audit.json`. It also regenerates
   `native_decomposition.json` and `../phase_a_classification.json` from the
   May 2026 posting and checks them against the committed copies.

Stage 3 needs only this repository and the QC files. Stages 1 and 2 need the
pinned external checkouts below.

## Pins

The lab ran on 2026-07-11; the replay output is stamped 23:36Z. The commits
below were the main-branch heads at that time. On 2026-10-03, reruns at these
pins reproduced `co_fy2024_reconstruction.csv`,
`fy2024_reconstruction_national.csv` and `amterr_replay_results.json` byte
for byte.

| Component | Pin |
|---|---|
| giannella/snap_qc | `741e10bf75c36a9ce8ac20f922b5eec3d4539dc2` |
| snap_qc `qc_data/qc_pub_fy2024.sav` | sha256 `ab6420fa359ab9bcc280a21b9ba7b11172c79c6f7a661718bc6e318f97723fbb` (carries the May 2026 posting's weights) |
| TheAxiomFoundation/axiom-oracles | `d34aa6fa04287387e0dab6912d128ef746c7b6b2` (merge of #268) |
| TheAxiomFoundation/rulespec-us | `b53ce208771085030939db4b9691762506b6bca2` (#826) |
| TheAxiomFoundation/axiom-rules-engine | `de0efdc73b469132ee268e1c832e8f7148b91431` (#102) |
| Engine release binary | sha256 `bb8ec23689697a5417b74c38196c0488e002e4ee6fe3b33faabb39005e6e5eee`, built from that commit with `cargo build --release --offline` (see `../../cert/CERT_REPORT.md`) |
| FY2024 QC CSV, May 2026 posting | zip `https://snapqcdata.net/sites/default/files/2026-05/qcfy2024_csv.zip` (sha256 `0f3230a4318307d3088382546095eebfde03e781da6f65c9eac7f077bd4263f4`); member `qc_pub_fy2024.csv` sha256 `45193eb7370463ab3067d71da23a580fec34a5460341e4e750dda0be061e1aa9` |
| FY2024 QC CSV, August 2026 posting | zip `https://snapqcdata.net/sites/default/files/2026-08/qcfy2024_csv.zip` (sha256 `b8b29b8593f78aa51c48332c47d2d92fa5bbecf5346570acb45e26f2d9ebd2b5`); member sha256 `e871a8e9caca0be72e2003b09bdf71e1d020984b52289d2b74c4c6b88c4f793b` |
| R | 4.3.0 with haven 2.5.5, dplyr 1.1.2, tidyr 1.3.0 |

The binary that ran on 2026-07-11 was not recorded. The 2026-10-03 rerun used
the 2026-08-06 build of the same commit, attested in `CERT_REPORT.md`. Its
output matched byte for byte under CPython 3.14 (free-threaded) and 3.13.

The two postings differ only in HWGT, FYWGT, HWGT_OLD and FYWGT_OLD. The
replay reads weights only for its `weight` field. Run against the August
posting, it changes that field in 90 of 283 rows and nothing else.

## Commands

Set these once (example paths):

```bash
export REPO=$PWD                                  # this repository's root
export LAB=$REPO/paper/snapshot/labs/amterr
export WORK=$HOME/amterr-rerun                    # any scratch directory
mkdir -p $WORK
```

### Stage 3: audit (this repository only)

Download both postings, unzip each into its own directory, and check the CSV
hashes above. Then:

```bash
SNAP_QC_CSV_MAY2026=$WORK/may2026/qc_pub_fy2024.csv \
SNAP_QC_CSV_AUG2026=$WORK/aug2026/qc_pub_fy2024.csv \
uv run --extra analysis python $LAB/audit_claims.py --check
```

`--check` exits 1 if the regenerated audit differs from `claims_audit.json`;
drop it to rewrite the file. The script refuses a CSV whose hash does not
match its posting. `tests/test_amterr_lab.py` runs the same regeneration
when both CSVs are present at the default paths (`~/.cache/axiom-oracles/`)
or at the paths in those variables, and skips it otherwise.

### Stage 1: reconstruction (R, about 70 s)

```bash
git clone https://github.com/giannella/snap_qc $WORK/snap_qc
git -C $WORK/snap_qc checkout 741e10bf75c36a9ce8ac20f922b5eec3d4539dc2
shasum -a 256 $WORK/snap_qc/qc_data/qc_pub_fy2024.sav
mkdir -p $WORK/recon
SNAP_QC_REPO=$WORK/snap_qc AMTERR_LAB_DIR=$WORK/recon Rscript $LAB/reconstruct_co_fy2024.R
cmp $WORK/recon/co_fy2024_reconstruction.csv $LAB/co_fy2024_reconstruction.csv
cmp $WORK/recon/fy2024_reconstruction_national.csv $LAB/fy2024_reconstruction_national.csv
```

The script prints `wrote 283 CO error rows; 15902 national error rows` and
`CO error cases within $5: 246 of 283`. Without `AMTERR_LAB_DIR` it writes
next to itself.

### Stage 2: engine replay

Build the engine at its pin, then check out the harness and the rules. The
2026-10-03 rerun used the attested binary in the table; a fresh build on
another machine may differ in sha256, so compare the replay output, which is
what the pins have to reproduce.

```bash
git clone https://github.com/TheAxiomFoundation/axiom-rules-engine $WORK/engine
git -C $WORK/engine checkout de0efdc73b469132ee268e1c832e8f7148b91431
(cd $WORK/engine && cargo build --release)
export BIN=$WORK/engine/target/release/axiom-rules-engine

git clone https://github.com/TheAxiomFoundation/axiom-oracles $WORK/axiom-oracles
git -C $WORK/axiom-oracles checkout d34aa6fa04287387e0dab6912d128ef746c7b6b2
git clone https://github.com/TheAxiomFoundation/rulespec-us $WORK/rulespec-us
git -C $WORK/rulespec-us checkout b53ce208771085030939db4b9691762506b6bca2
mkdir -p $WORK/replay && cp $LAB/co_fy2024_reconstruction.csv $WORK/replay/
```

The harness's QC loader hash-checks only a zip it downloads. A CSV it finds
in `AXIOM_SNAP_QC_DATA_DIR` or `~/.cache/axiom-oracles/snap-qc/` is used
unchecked, so point it at a directory holding the May 2026 posting's CSV and
check that file's hash first:

```bash
shasum -a 256 $WORK/may2026/qc_pub_fy2024.csv
cd $WORK/axiom-oracles && uv sync --frozen
cd $WORK/axiom-oracles && \
  AXIOM_SNAP_QC_DATA_DIR=$WORK/may2026 \
  AXIOM_SNAP_QC_RULESPEC_ROOT=$WORK/rulespec-us \
  AXIOM_SNAP_QC_AXIOM_BINARY=$BIN \
  AMTERR_LAB_DIR=$WORK/replay \
  uv run --frozen python $LAB/amterr_replay.py
cmp $WORK/replay/amterr_replay_results.json $LAB/amterr_replay_results.json
```

The script prints `engine(original) vs RAWBEN <=$5: 246/283 (86.9%)` and
`solver within $5: 246/283; engine agrees (<=$5) on 246 of those`. Without
`AMTERR_LAB_DIR` it reads and writes next to itself.
