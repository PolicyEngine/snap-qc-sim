# Engine-leg attestation manifests (Colorado FY2024 SMD counterfactual)

These five `manifest.json` files are byte-identical copies of the round-1/1b
engine-run manifests whose SHA-256 pins are committed in
`analysis/COUNTERFACTUAL.md` (table "Round-1b input"). They were copied here
after re-hashing each file against its pin (all five match; verified
2026-08-07, and independently re-verified by the round-3 red-team review,
which also confirmed the load-bearing fields: the baseline manifest's
`certified_original_bridge_regression_guard` at 856 matches / 0 mismatches,
and the floor manifest's `baseline_invariance_check` at 856 cases /
0 divergences / byte-identical ×2).

Layout mirrors the run tree:

- `baseline/manifest.json` — certified-path regression guard (856/856) and
  raw-facts leg diagnostics (845/856 agree; 11 divergences: 10 categorical
  200%-FPL cases lacking public TANF facts at −$23, 1 utility-allowance tier
  conflict at +$22)
- `smd-off/manifest.json` — SMD-off run envelope
- `smd-off/{floor,point,ceiling}/manifest.json` — the three censoring
  variants for the 46 medical-expense records censored at exactly $165

The full `cases.jsonl` outputs remain external (their SHA-256 pins are in the
same COUNTERFACTUAL.md table); these manifests carry the attestations the
manuscript and fact catalog rows I1–I2 rely on. Toolchain pins inside each
manifest: engine `de0efdc73b46`, RuleSpec `b53ce2087710`, harness
`d30566266932`, nominal engine period `2026-01` with the FY2024 overlay.
