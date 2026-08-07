# QRF benchmark against the shipped GBM quantiles

Retain the shipped GBM: QRF loses factor-adjusted equal-state dollar-rate MAE by 0.023290 pp.

## Headline head-to-head

Lower is better for every numeric row.

| Gate | GBM | QRF | QRF − GBM | Winner |
|---|---:|---:|---:|:---|
| Mean absolute coverage gap (pp) | 4.3761 | 4.0968 | -0.2793 | QRF |
| Absolute PIT mean gap | 0.0544 | 0.0667 | 0.0123 | GBM |
| PIT effective-n-scaled CvM | 21.6300 | 33.8696 | 12.2397 | GBM |
| Raw equal-state dollar MAE (pp) | 2.0200 | 2.0236 | 0.0036 | GBM |
| Raw issuance-weighted dollar MAE (pp) | 2.2820 | 2.2832 | 0.0012 | GBM |
| FY2023-factored equal-state dollar MAE (pp) | 0.9279 | 0.9512 | 0.0233 | GBM |
| FY2023-factored issuance-weighted dollar MAE (pp) | 0.8336 | 0.8682 | 0.0346 | GBM |

## Shipped-GBM equivalence check

The benchmark's GBM path is compared numerically with the checked-in `analysis/distributional_results.json` baseline. Passed: **true**; maximum absolute delta across 41 checked metrics: 1.11e-16.

## FY2024 weighted conditional-quantile coverage

Coverage uses HWGT among deviators. Signed gaps are observed coverage minus the nominal level, in percentage points.

| Quantile | GBM coverage | GBM gap (pp) | QRF coverage | QRF gap (pp) | QRF − GBM absolute-gap (pp) | Winner |
|---:|---:|---:|---:|---:|---:|:---|
| 0.050 | 4.75% | -0.248 | 5.20% | +0.197 | -0.051 | QRF |
| 0.100 | 8.29% | -1.705 | 7.55% | -2.452 | +0.747 | GBM |
| 0.250 | 21.15% | -3.854 | 19.61% | -5.388 | +1.534 | GBM |
| 0.500 | 43.90% | -6.095 | 41.94% | -8.061 | +1.965 | GBM |
| 0.750 | 68.11% | -6.890 | 66.39% | -8.608 | +1.718 | GBM |
| 0.900 | 82.56% | -7.444 | 85.40% | -4.604 | -2.840 | QRF |
| 0.950 | 89.73% | -5.268 | 91.55% | -3.450 | -1.818 | QRF |
| 0.975 | 93.03% | -4.467 | 94.62% | -2.880 | -1.587 | QRF |
| 0.990 | 95.59% | -3.412 | 97.77% | -1.231 | -2.181 | QRF |

GBM: mean absolute gap 4.376 pp; max 7.444 pp; 9 negative and 0 positive signed gaps.

QRF: mean absolute gap 4.097 pp; max 8.608 pp; 8 negative and 1 positive signed gaps.

## Seed-averaged simulated standard deviations

Each entry averages 8 seeds × 4,000 draws. Both estimators use the same random streams; each seed is centered at the official rate and floored at zero.

| State | Observed bootstrap SD (pp) | GBM SD (pp) | GBM abs gap | QRF SD (pp) | QRF abs gap | QRF − GBM abs-gap (pp) | Winner |
|:---|---:|---:|---:|---:|---:|---:|:---|
| CO | 0.9046 | 0.7537 | 0.1510 | 0.7660 | 0.1387 | -0.0123 | QRF |
| CA | 0.8267 | 0.8887 | 0.0620 | 0.9132 | 0.0865 | +0.0245 | GBM |
| NY | 0.9347 | 0.7442 | 0.1905 | 0.7460 | 0.1887 | -0.0018 | QRF |
| TX | 0.6485 | 0.5109 | 0.1376 | 0.5503 | 0.0982 | -0.0394 | QRF |

## Runtime and export implications

Run time is observational, alternates estimator order across repetitions, and is excluded from the deterministic core hash. Both runs constrain OpenMP/BLAS and QRF to one thread. Model-object size is excluded: only the identically shaped exported per-case vectors matter to the shipped consumer.

| Metric | GBM | QRF | QRF − GBM | Winner |
|---|---:|---:|---:|:---|
| Median magnitude fit + FY2023/FY2024 prediction (s) | 23.472 | 228.757 | +205.285 | GBM |
| Export raw bytes | 3,124,050 | 3,111,665 | -12,385 | QRF |
| Export gzip bytes | 740,796 | 597,829 | -142,967 | QRF |

Both exports use schema 2 with vector shape [44800, 9].

## Binary validity gates

| Gate | GBM | QRF | Winner |
|---|:---:|:---:|:---|
| Tail finite-variance gate | Pass | Pass | Tie |
| Exact two-repetition determinism | Pass | Pass | Tie |

## Method caveats

- **Weights:** Both estimators receive HWGT at fit. GBM weights its quantile losses. QRF sample weights affect split/impurity fitting, but sklearn's bootstrap and quantile-forest's one-sample leaf retention remain uniform; final leaf-frequency aggregation does not directly reuse the HWGT magnitudes.

- **Missing features:** GBM uses native missing-value routing. QRF uses unweighted training-deviator median imputation; every OOF tail fold learns its unweighted imputer only on that fold's training rows.

- **Monotonicity:** QRF predicts all nine levels jointly and is monotone by construction. GBM fits levels independently. Both pass through the shipped 0.5-dollar floor and row-wise sorting safeguard.

- **Tail:** Each estimator separately fits the same q99 OOF-median log-residual mean-excess tail and attaches it above its own q99. GBM scale is 0.2713; QRF scale is 0.2361. Both must pass the point-scale <0.45 and upper-95 <0.5 finite-variance gate.

- **Caps and calibration:** Both use the same per-case physical cap. FY2023 state factors are refit separately for each frozen estimator before FY2024 evaluation.

## Determinism

Exact deterministic-core SHA-256 match across 2 repetitions: **true**. Hash: `817d5925b850de46bb3b0c28627f9fda7b698996a505f717fef98a0284c24e0d`. Timings are not part of this hash.

## Recommendation

Retain the shipped GBM: QRF loses factor-adjusted equal-state dollar-rate MAE by 0.023290 pp.

Relative to GBM, QRF changes the mean absolute coverage gap by -0.279 pp and factor-adjusted equal-state MAE by +0.023 pp; negative is better. The PIT gates favor GBM on absolute mean gap and GBM on effective-n-scaled CvM.

The decision rule is fixed in advance: switch only if QRF ties or wins both mean absolute FY2024 coverage gap and factor-adjusted equal-state FY2024 dollar-rate MAE.
