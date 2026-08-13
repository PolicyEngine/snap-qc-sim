# Location-repair protocol

## Purpose and frozen baseline

This experiment tests whether training-only additive calibration of the predicted
log-magnitude quantile path repairs the frozen distributional GBM's FY2024
undercoverage. It follows the coverage-repair adoption diagnostic: all nine
baseline coverage gaps are negative, with the largest misses around q50--q90,
so the pre-registered intervention moves quantile locations rather than changing
their spread.

The nine GBMs, attached tail, feature set, random state, hurdle and sign stages,
physical deviation cap, 0.5-dollar magnitude floor, and state dollar-factor
method remain frozen. No FY2024 outcome, weight, state label, or metric may enter
fitting or mechanism selection. The shipped base model remains trained on
FY2017--FY2019 and FY2022, FY2023 continues to fit dollar factors, and FY2024 is
evaluated once.

## Cross-fitting and fitting objective

The repair calibrators use the same pooled leave-one-year-out predictions as the
coverage-repair experiment. For each held-out year in FY2017--FY2019 and
FY2022--FY2023, fit the frozen nine-GBM magnitude stack and tail on the other four
years, predict the held-out year, retain deviators, and concatenate folds in
ascending year and source-row order. Every calibration target is therefore
predicted by a model that did not train on it. Fits use HWGT weights.

For an observed deviator and quantile level, define the location residual as
`log(abs(D)) - predicted_log_quantile`. A common shift is fitted on the inclusive
grid from `-2.000` through `2.000` log dollars in steps of `0.001`. Its loss is
the unweighted mean over the nine levels of the absolute HWGT-weighted signed
coverage gap in percentage points after adding the shift. Ties within `1e-12`
select the smallest absolute shift and then the smaller signed shift. Reaching a
grid endpoint is recorded and makes that fitted shift ineligible, because it
would show that the pre-registered search failed to bracket the optimum.

For a level-specific offset at nominal level `u`, use the smallest sorted
location residual whose cumulative positive HWGT weight reaches at least `u` of
total weight. This left-continuous weighted empirical quantile matches the
coverage metric's inclusive `<=` convention. No FY2024 information is used.

## Candidate mechanisms

All three candidates are fitted only on the pooled cross-fitted training rows.

### `global_shift`

Fit one common grid-searched additive shift and add it to every predicted
log-quantile for every case and state.

### `state_shift`

Fit the global shift above as a fallback. A state receives its own grid-searched
shift only when its pooled calibration subset has both at least 100 unweighted
deviators and Kish effective sample size at least 100. States failing either
threshold, or absent from a target frame, use the global fallback. Record each
state's counts, effective sample size, selected shift, loss, endpoint status,
and fallback decision.

### `level_profile`

Fit one additive offset at each of the nine nominal levels using the weighted
empirical residual quantile rule above and add that profile to every case. Before
the existing pipeline floor and cap logic is applied, detect every row whose raw
shifted vector decreases at an adjacent level and repair that row by equal-weight
least-squares isotonic projection onto a nondecreasing vector. Record repair
counts separately for pooled calibration predictions, FY2023, and FY2024. Then
pass the projected vectors through the pipeline's existing monotone/floor helper;
expected dollars use the existing physical-cap route. No new clamp is introduced.

## Metrics

The implementation calls repository functions rather than re-deriving metric
variants.

- Per-level coverage is `weighted_quantile_coverage`: among deviators, compare
  `log(abs(D)) <= predicted log-quantile`, take the HWGT-weighted mean, and
  report `gap_pp = 100 * (coverage - nominal)`, Kish effective n, and the strict
  `abs(gap_pp) > 3` flag.
- PRIMARY is the unweighted mean across the nine levels of `abs(gap_pp)` on
  FY2024. Lower is better.
- Factored equal-state dollar-rate MAE uses the existing capped expected-dollar
  route, fits the existing empirical-Bayes factors on FY2023, applies them to
  FY2024, and uses the repository equal-jurisdiction summary.
- The frozen hurdle probabilities and all frozen sign outputs are copied without
  modification. The implementation asserts exact equality of the hurdle
  probability vector before and after each repair. Raw and calibrated FY2024
  sign AUC remain exactly `0.6993960587007345` and `0.6997568121541028`.
- PIT diagnostics call `weighted_pit_summary` and report weighted mean, mean gap
  from 0.5, weighted CvM integral, effective-n-scaled CvM, Kish reference z, n,
  and effective n. PIT is diagnostic only.

The committed baseline factored equal-state dollar-rate MAE is
`0.9311800033868244` percentage points. Regeneration must reproduce it within
`1e-10` and reproduce the untouched AUC values exactly before candidates are
judged.

## Decision rule: `minimum_guarded_primary_with_materiality_and_level_guards`

A mechanism is eligible only if every guard passes:

1. At every evaluated level, its absolute FY2024 coverage gap is no more than
   `0.5` percentage points above the baseline absolute gap.
2. At every level whose baseline absolute gap is at most `3` percentage points,
   the mechanism's absolute gap is also at most `3` percentage points, so it
   creates no new strict over-3pp flag.
3. Its q05 weighted coverage is at least half the baseline q05 weighted
   coverage.
4. Its factored equal-state dollar-rate MAE is no more than `0.05` percentage
   points above `0.9311800033868244`, hence at most `0.9811800033868244`.
5. Its hurdle probability vector is exactly unchanged, and raw and calibrated
   sign AUC equal the frozen values exactly.
6. Every grid-searched fit used by the mechanism is bracketed rather than at a
   grid endpoint.

Among eligible mechanisms, choose the smallest PRIMARY. Exact ties within
`1e-12` follow the fixed order `global_shift`, `state_shift`, `level_profile`.
The pre-named material-improvement threshold is a reduction of at least **0.25
percentage points** from the regenerated baseline PRIMARY. If no mechanism is
eligible and material, the verdict is **RETAIN BASELINE**. PIT never breaks a
tie or overrides a guard.

## Artifact, provenance, and determinism

`analysis/location_repair_results.json` contains the literal embedded decision
rule, regenerated baseline, per-mechanism aggregate and per-state coverage at
all nine levels, PRIMARY, every aggregate and per-level guard result, PIT,
fitted shifts/profile, isotonic repair counts, and mechanically derived verdict.
It records SHA-256 hashes for all six SAVs; the three auxiliary CSVs; every
imported analysis module that determines assembly, prediction, metrics, or
repair; this protocol; and the committed baseline JSON.

The runner executes its deterministic core twice and refuses to write unless
the sorted compact strict-JSON SHA-256 hashes match. Runtime measurements are
excluded. The artifact is sorted, pretty-printed UTF-8 strict JSON with Unix
newlines. Tests lock schema, artifact SHA, embedded-rule/verdict consistency,
winner satisfaction of every guard, untouched hurdle/sign metrics, determinism,
and raw-source regeneration. Regeneration is skipped when any private raw source
is unavailable; always-run tests stay artifact-only and fast.

The experiment changes no app, export, paper, or wrapper artifact. Adoption is
a separate decision even if a mechanism wins. If none clears the threshold
under all per-level guards, the report must say so directly and distinguish a
remaining correctable location pattern from evidence that richer features or
data are needed.
