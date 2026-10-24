# snap-qc-sim

**Interactive tool: https://snap-qc-sim.vercel.app** — pick a state, adjust
audit volume and simplification options, watch the measured-rate
distribution and the cost-share bill respond. States whose encoded benefit
computation is verified case-by-case against the FY 2024 QC file (CO, NY,
CA, AZ, GA, MD, TX — every replayable review exact; exclusions are
enumerated program-structure classes) carry a verification badge.

Monte Carlo simulation of SNAP payment error rates: given a state's USDA
Quality Control sample, simulate the distribution of its **measured** payment
error rate — and therefore its 7 USC 2013(a)(2) cost-share tier and dollars —
under two kinds of state choice:

- **audit volume**: the QC sample size (states may voluntarily review more
  cases than the federal minimum);
- **policy simplification options** that standardize away whole error
  categories: the standard medical deduction, standard self-employment
  deduction, heat-and-eat, and broad-based categorical eligibility.

Beginning FY 2028, a state's payment error rate sets its share of SNAP
benefit costs (0% below a 6% rate, 5% from 6–8, 10% from 8–10, 15% at or
above 10), keyed initially to its FY 2025 or FY 2026 rate. Small rate
movements near a boundary are therefore worth roughly 5% of a state's annual
issuance — tens of millions of dollars for mid-sized states — and sampling
noise alone materially affects tier assignment.

## What v0.1 finds (FY 2024 file, all 53 jurisdictions)

- **Tier assignment is noisy.** Several states' tiers are near coin flips
  under QC sampling variation (Colorado: official FY 2024 rate 9.97%, 0.03
  points below the 10% rate where the 15% cost share begins, with a
  ±0.9-point sampling SD; its FY 2025 rate, 10.09%, is above it).
- **Simplification options carry large expected values** where they can move
  a state across a boundary: about $609M/yr in combined expected state
  cost-share reduction nationally at 50% category-suppression effectiveness
  (reproducible via `examples/all_states.py`).
- **The audit-volume effect is two-sided.** More audits shrink variance
  around the state's underlying rate: that lowers expected cost share for
  states just below a boundary and raises it for states just above one,
  while reducing the variance of the bill in both cases.

Numbers above are FY 2024-sample estimates with the caveats below; treat
them as illustrative magnitudes, not forecasts.

## Method

The state's QC public-use sample supplies the error process (which cases
carry errors above the official threshold, their dollar sizes, and their
finding-element categories). Scenarios re-draw QC-style samples of the
chosen size and recompute the weighted measured rate, centered on the
official published rate. Policy levers suppress the error contribution of
the element categories they standardize away, at a chosen effectiveness.

```python
from snap_qc_sim import load_cases, load_official_rates, simulate, summarize, LEVERS

cases = load_cases("qc_pub_fy2024.csv")["CO"]
official = load_official_rates("snap-fy24QC-PER.pdf")["CO"]
rates = simulate(cases, official, extra_audits=500,
                 suppressed=LEVERS["smd"], effectiveness=0.5)
summarize(rates, issuance=1.27e9)
```

Data: the [SNAP QC public-use files](https://snapqcdata.net/datafiles) and
FNS's published payment error rate tables.

## Caveats

- Lever *effectiveness* is a scenario dial, not a causal estimate;
  states adopt options endogenously and standardization suppresses
  categories only partially in practice.
- The underlying error process is held fixed: no behavioral response and no
  corrective-feedback channel from auditing more cases.
- Case bootstrap approximates the stratified monthly QC design; official
  rates embed FNS adjustments (federal re-review integration and related
  corrections, per the FY 2024 technical documentation) that this model
  applies only as a level.
- Element attribution is single-shot (a case's error is split evenly across
  its finding elements).
- The QC sample is designed for national estimates; within-state dollar
  levels carry wide uncertainty. Shares and comparative statics are more
  robust than levels.

## Roadmap

The lever mechanism in v0.1 is an accounting bound. The v2 design —
a case-level error model trained on policy-affected intermediate
variables (documentation and verification burdens) that the rules engine
recomputes under alternative policies — is specified in
[docs/v2-error-model.md](docs/v2-error-model.md).

- Caseload-based v2: state caseloads from calibrated survey microdata aged
  to FY 2026–28, benefits repriced under changed rules by
  [PolicyEngine](https://github.com/PolicyEngine/policyengine-us) /
  [Axiom](https://github.com/TheAxiomFoundation/rulespec-us) rules
  (so options change benefits, not only error categories), with
  characteristic-based error models.
- Record-realism scoring of QC households against calibrated microdata.
- Stratified sampling design; per-lever empirical effectiveness estimates.

Grew out of open collaboration with Eric Giannella's
[snap_qc](https://github.com/giannella/snap_qc) error-modeling work and Ben
Molin's [SNAP Screener QC analysis](https://www.snapscreener.com/blog/qc-data).

## License

Apache-2.0

## Reproducing the paper

1. Clone the QC data repository (training files are tracked there) and
   fetch the FY 2024 CSV and official rate table:

   ```bash
   git clone https://github.com/giannella/snap_qc ~/snap_qc
   export SNAP_QC_SAV_DIR=~/snap_qc/qc_data
   # FY 2024 public-use CSV and PER PDF from https://snapqcdata.net/datafiles
   # and https://www.fns.usda.gov/snap/qc/per
   export SNAP_QC_CSV=/path/to/qc_pub_fy2024.csv
   export SNAP_QC_PER=/path/to/snap-fy24QC-PER.pdf
   ```

2. Run the deterministic analysis pipeline (Python 3.14, pinned in
   `.python-version`; ~15–20 minutes; two runs are byte-identical):

   ```bash
   uv run --frozen --extra analysis python analysis/run_all.py
   ```

3. Rebuild the app data and the paper's simulation artifact
   (`pdftotext` from poppler required):

   ```bash
   uv run --frozen --extra analysis python scripts_build_data.py "$SNAP_QC_CSV" "$SNAP_QC_PER"
   uv run --frozen --extra analysis python examples/all_states.py "$SNAP_QC_CSV" "$SNAP_QC_PER"
   ```

4. Tests and manuscript:

   ```bash
   uv run --frozen --extra dev --extra analysis pytest -q
   cd paper && quarto render index.qmd
   ```

## Replication package for the migrations paper

The migrations paper (`paper-causal/`, served at
[/paper-migrations](https://policyengine.org/us/snap-payment-error-simulator/paper-migrations/))
develops in this repository; journals get a scoped citation object instead
of the whole monorepo. Export it from any tag or commit:

```bash
uv run python scripts/export_replication_package.py --ref v20260817 --verify
```

This extracts exactly the files the paper's reproduction section names —
manuscript, figures and generator, estimation scripts, frozen protocols,
committed artifacts, and the value-lock tests — from the pinned ref via
`git archive`, writes a `MANIFEST.json` of SHA-256 hashes, and produces a
deterministic zip under `dist/` (same ref, same bytes). `--verify` runs
the value-lock tests inside the exported package.

## Deploying

The site is the Vercel project `snap-qc-sim` (team `policy-engine`). It
has no git integration: production changes only when someone uploads
`app/public` from a checkout, and policyengine.org serves the same
deployment at
[/us/snap-payment-error-simulator](https://www.policyengine.org/us/snap-payment-error-simulator).
Deploy from an up-to-date `main` after the PR that changes the site or
either paper merges.

1. **Start from a clean `main`.** Use a fresh worktree so nothing
   unmerged ships:

   ```bash
   git fetch origin
   git worktree add --detach ../snap-qc-sim-deploy origin/main
   cd ../snap-qc-sim-deploy
   ```

2. **Render both papers and sync their assets** (Quarto 1.9.36). Each
   paper's HTML loads styles and scripts from a gitignored folder
   (`site_libs/` for the working paper, `index_files/` for the migrations
   paper), so a fresh checkout has neither and would serve both papers
   unstyled. The renders are deterministic: on a clean `main` they
   reproduce the committed HTML byte for byte, so `git status` should show
   no tracked changes afterwards.

   ```bash
   (cd paper && quarto render index.qmd)
   cp paper/out/index.html paper/out/index.pdf app/public/paper/web/
   rsync -a --delete paper/out/site_libs/ app/public/paper/web/site_libs/
   (cd paper-causal && quarto render index.qmd)
   cp paper-causal/index.html paper-causal/index.pdf app/public/paper-migrations/web/
   rsync -a --delete paper-causal/index_files/ app/public/paper-migrations/web/index_files/
   rm paper-causal/index.html paper-causal/index.pdf
   git status --short
   ```

3. **Deploy from `app/public`, never from `app/`.** `app/public/vercel.json`
   holds the rewrites that serve the site and both papers under
   `/us/snap-payment-error-simulator`, plus the `/paper/index.pdf` alias.
   The project's root directory is `.`, so a deploy from `app/` makes
   `app/` the root, where there is no `vercel.json`. That deploy 404s the
   policyengine.org path (it did on 2026-10-24). `.vercel/` is gitignored,
   so link each new checkout once:

   ```bash
   cd app/public
   vercel link --yes --project snap-qc-sim --scope policy-engine
   vercel deploy --prod
   ```

4. **Verify both hosts.** Every page should return 200, and
   `/vercel.json` should return 404:

   ```bash
   for url in \
     https://snap-qc-sim.vercel.app/ \
     https://snap-qc-sim.vercel.app/paper/ \
     https://snap-qc-sim.vercel.app/paper/web/index.pdf \
     https://snap-qc-sim.vercel.app/paper-migrations/ \
     https://www.policyengine.org/us/snap-payment-error-simulator \
     https://www.policyengine.org/us/snap-payment-error-simulator/paper \
     https://www.policyengine.org/us/snap-payment-error-simulator/paper-migrations/ \
     https://snap-qc-sim.vercel.app/vercel.json; do
     curl -s -o /dev/null -w "%{http_code} $url\n" "$url"
   done
   ```

   Then open `/paper` on policyengine.org and check that the manuscript is
   styled and shows the revision and date in `app/public/paper/index.html`.
   When `app.js` or another site asset changes, bump `ASSET_V` in
   `app/public/app.js` and the matching `app.js?v=` in
   `app/public/index.html` in the PR, so browsers drop the cached copy.
