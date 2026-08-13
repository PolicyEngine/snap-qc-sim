# Coverage-repair protocol

## Purpose and frozen baseline

This experiment tests whether a training-only post-hoc calibration can repair
the under-dispersion of the shipped distributional GBM. The GBM hurdle,
quantile-regressor hyperparameters, feature set, physical cap, error threshold,
and sign model remain frozen. No FY2024 outcome, weight, state label, or metric
may enter fitting or mechanism selection.

The evaluation target is the same frozen distributional design used by the
committed artifact: GBM and hurdle components are trained on FY2017--FY2019 and
FY2022, state dollar factors are fitted on FY2023, and FY2024 is evaluated once.
The repair calibrators alone use cross-fitted predictions from all five
training years (FY2017--FY2019 and FY2022--FY2023). This distinction preserves
the existing FY2023 dollar-factor validation while allowing every non-FY2024
year to inform dispersion calibration.

## Cross-fitting and common prediction representation

For each held-out training year in ascending order, fit the frozen nine-GBM
magnitude stack and its tail on the other four training years, then predict the
held-out year. Concatenate only held-out deviators, in year and source-row
order. Thus every calibration observation is predicted by models that did not
train on it. Fits use the repository's fixed model random state and HWGT sample
weights. The final FY2024 base prediction is the existing frozen-through-FY2022
fit; FY2024 is never used to fit a repair.

All mechanisms operate on log absolute deviation. A requested level between
the nine fitted levels is evaluated by linear interpolation between adjacent
log-quantiles. Below q05, interpolate linearly between `log(0.5)` at level zero
and q05. Above q99, use the repository's attached exponential log-tail,
`q99 - tail_scale * log((1 - u) / 0.01)`. Enforce the existing 0.5-dollar floor
and row-wise monotonicity after transformation.

## Candidate mechanisms

All three pre-registered candidates will be implemented and compared.

### `conformal_remap`

For each of the nine source levels, compute HWGT-weighted empirical coverage on
the pooled leave-one-year-out predictions. Add endpoints `(source level,
coverage) = (0, 0)` and `(1, 1)`, monotonize empirical coverage with a
cumulative maximum, and invert this piecewise-linear calibration curve at each
of the nine nominal target levels. If repeated coverage values occur, retain
the largest source level before inversion. The resulting nine source levels
form one global monotone nominal-level remap. Apply that remap to every row.
This is a cross-fitted split-conformal quantile-level calibration: every score
is held out by fiscal year, and the calibration mapping is fitted only after
the held-out predictions are pooled.

### `spread_inflation`

For a scalar factor `s`, retain each row's predicted median `m` and transform
every requested log-quantile `q` to `m + s * (q - m)`. Fit `s` separately for
each state on that state's pooled leave-one-year-out deviators. Also fit a
global fallback on all pooled deviators; a state absent from calibration data
uses that global factor. Search the inclusive deterministic grid from `0.500`
through `3.000` in steps of `0.001`. The fitting loss is the unweighted mean
over the nine levels of the absolute HWGT-weighted signed coverage gap in
percentage points, using the metric below. Ties within `1e-12` select the
smallest factor.

### `both`

Apply `conformal_remap` first. Then fit and apply state/global spread factors by
the identical grid, loss, fallback, and tie rule, using the remapped cross-fit
predictions as the spread-fitting input.

## Exact evaluation metrics

The implementation must call the repository metric functions rather than
re-derive variants.

- **Coverage at each level:** restrict to `deviates == 1`; compare
  `log(abs(D)) <= predicted log-quantile`; take the HWGT-weighted mean; and set
  `gap_pp = 100 * (coverage - nominal level)`. This is exactly
  `weighted_quantile_coverage` in
  `analysis/distributional_deviation_model.py:426-454`, including its Kish
  effective n and strict `abs(gap_pp) > 3` flag.
- **PRIMARY, FY2024 mean absolute coverage gap:** the unweighted arithmetic
  mean across the nine configured levels of `abs(gap_pp)`, exactly as computed
  in `analysis/qrf_benchmark.py:293-312` (especially lines 294-299). Lower is
  better.
- **Factored equal-state dollar-rate MAE:** compute state predicted and observed
  dollar rates through the existing capped expected-dollar route; fit the
  existing empirical-Bayes state dollar factors on FY2023 and apply them to
  FY2024; then take the equal-jurisdiction weighted mean of
  `abs(pred_rate - obs_rate)`. The factor timing and summary call are fixed in
  `analysis/distributional_deviation_model.py:780-870`; the equal-jurisdiction
  weights are ones and MAE is the repository weighted mean in
  `analysis/hurdle_deviation_model.py:734-783` (especially lines 745-771).
- **Sign/classifier AUC:** FY2024 among deviators, HWGT-weighted
  `roc_auc_score(y, p, sample_weight=w)`, exactly
  `analysis/hurdle_deviation_model.py:265-268` and reported through
  `analysis/hurdle_deviation_model.py:291-322`. Repairs do not touch the sign
  or hurdle predictions, so both raw and calibrated sign AUC must be copied
  unchanged from the frozen baseline and exact equality asserted.
- **PIT diagnostics:** call `weighted_pit_summary` from
  `analysis/distributional_deviation_model.py:592-639`. Report its weighted
  mean, mean gap from 0.5, weighted CvM integral, effective-n-scaled CvM, Kish
  reference z, n, and effective n for the baseline and every mechanism. PIT is
  diagnostic only and is not a selection guard.

The committed baseline guard values are factored equal-state dollar-rate MAE
`0.9311800033868244` percentage points and raw/calibrated sign AUC
`0.6993960587007345`/`0.6997568121541028`, read from the current committed
`analysis/distributional_results.json`. Regeneration must additionally prove
that its baseline reproduces these values within `1e-10` for MAE and exactly
for the untouched AUC values before judging candidates.

## Decision rule: `minimum_guarded_primary_with_materiality`

For each mechanism, the guards pass only when:

1. its factored equal-state dollar-rate MAE is no more than `0.05` percentage
   points above `0.9311800033868244` (therefore at most
   `0.9811800033868244`); and
2. its raw and calibrated sign AUC equal the frozen baseline values exactly.

Among guard-passing mechanisms, select the one with the smallest FY2024 mean
absolute coverage gap. Exact primary ties within `1e-12` are resolved in the
fixed order `conformal_remap`, `spread_inflation`, `both`. A repair is material
only if it reduces PRIMARY by at least **0.25 percentage points** relative to
the regenerated frozen baseline. If no candidate passes the guards and clears
that materiality threshold, the verdict is **RETAIN BASELINE**. Otherwise the
verdict names the selected repair mechanism. PIT diagnostics never break ties
or override this rule.

## Artifact, provenance, and determinism

`analysis/coverage_repair_results.json` will contain the literal decision rule
above, frozen baseline, every candidate's per-level aggregate and per-state
FY2024 coverage gaps, PRIMARY, guards, PIT diagnostics, fitted remap/factors,
and the mechanically derived verdict. It will record SHA-256 hashes for all six
SAVs; `standard_medical_deductions.csv`, `state_bbce.csv`, and
`medicare_part_b_premiums.csv`; every imported analysis module that determines
assembly, prediction, metrics, or the repair; and the committed baseline JSON.

The runner executes the deterministic core twice in one invocation and refuses
to write unless canonical sorted compact strict-JSON SHA-256 hashes match.
Runtime measurements are excluded. The output is pretty-printed with sorted
keys, UTF-8, Unix newlines, and no NaN values. Tests lock schema, committed
artifact SHA, embedded-rule/verdict consistency, winner guards, untouched AUC,
and raw-source regeneration. Following the repository pattern, regeneration
tests skip when any private raw source is absent.

The experiment writes no app export, wrapper, paper, `model_data.json`, or
`model_scenarios.json`. If a repair wins, refreshing export/app artifacts is a
separate later pass with its own gates.

## Adoption decision — written after results, labeled as such

The mechanical verdict (USE `conformal_remap`: mean absolute gap
4.644pp to 4.082pp, guards passing) stands as the committed record.
Adoption downstream is declined, for two reasons the pre-registered
rule did not guard:

1. **Per-level pathology.** The remap improves the upper tail (q99
   −3.55pp to −0.35pp) by collapsing the lower one: q05 coverage falls
   from 4.6% to 0.02% (gap −0.38pp to −4.98pp), adding over-3pp flags
   at q05 and q10 where the baseline was clean. A mean-absolute
   criterion allows trading a uniform small miss for tail collapse; a
   v2 protocol needs per-level guards.
2. **The failure is location, not dispersion.** Every mechanism leaves
   all nine gaps negative, and the baseline's worst misses sit at the
   middle levels (q50–q90 near −7pp) with small tail gaps. Coverage
   below nominal at every level means the predicted quantiles sit
   systematically low — a shifted predictive distribution, consistent
   with the documented cross-state level underprediction. Post-hoc
   dispersion surgery redistributes that miss; it cannot clear it.

Consequence: no export, app, or paper artifact consumes any repair
mechanism. The named next experiment is location repair on the
quantile path (state-level calibration of predicted quantile levels,
or a training-objective change), for which partner-state
administrative data remains the strongest unlock.
