# FY2025 frozen-pipeline confirmation

This harness freezes the exact code, registries, training years, model settings,
metric definitions, and committed FY2024 reference values used by the SNAP QC
scoring pipeline. Before scoring, it appends the supplied public-use file's
SHA-256 and byte size to the manifest. It then refuses to proceed if any frozen
analysis module or feature registry has drifted.

## Publication-day command

From the repository root, with the published file named
`qc_pub_fy2025.sav`, run exactly once:

```bash
UV_CACHE_DIR=/private/tmp/snap-qc-uv-cache uv run --frozen --extra analysis \
  python -m analysis.fy2025_confirmation /path/to/qc_pub_fy2025.sav
```

The command writes `analysis/fy2025_confirmation_results.json`. Each FY2025
metric appears beside its committed FY2024 reference and the hash of the full
manifest—including the recorded FY2025 input hash—under which scoring ran.

To prove today that the harness reproduces the committed results through the
same path:

```bash
UV_CACHE_DIR=/private/tmp/snap-qc-uv-cache uv run --frozen --extra analysis \
  python -m analysis.fy2025_confirmation --dry-run \
  ~/.cache/axiom-oracles/snap_qc_repo/qc_data/qc_pub_fy2024.sav
```

## Frozen interpretation

Confirmation means one prospective comparison of the frozen pipeline on the
FY2025 public-use file. There is no re-tuning, feature change, threshold change,
or second attempt after seeing FY2025 outcomes. The manifest fixes the FY2025
payment-error tolerance at $57, expects 18 `SLFEMP` person slots, and carries
the frozen FY2024 SMD and BBCE registry cells forward. A schema mismatch fails
closed instead of being repaired during the run.

The output confirms or fails to confirm out-of-year performance for the
classifier AUC and PR-AUC, hurdle stages, factored equal-state dollar-rate MAE,
nine magnitude-coverage gaps, and sign AUC. It does not establish causality,
validate unmeasured populations, or license model selection on FY2025. Any
investigation, alternative specification, registry refresh, or correction made
after opening the FY2025 outcomes must be labeled post-hoc and kept separate
from this one-shot confirmation.
