# UHIP decomposition deviations and data-forced choices

The frozen protocol was not edited. No estimator, outcome-universe, threshold,
donor-pool, inference, sensitivity, or reporting-rule deviation was made.

## Element inventory and counting

“Present in both windows” is operationalized from
`analysis/coding_consistency.json` as the intersection of the union of annual
observed-code inventories in FY2012–15 and the corresponding union in
FY2017–19. Within the selected Rhode Island strict-coded cases, an element is
counted once per case if it appears in any `ELEMENT1`–`ELEMENT9` slot. This
case-presence convention avoids counting a repeated code twice within one
case; shares use strict-coded cases in the window as the denominator.

## Certification vintage

The FY2017 technical documentation defines `CERTMTH` as the number of months
in the current certification or recertification period and `LASTCERT` as the
constructed number of months since the last SNAP certification. The repository
loader in `snap_qc_sim/data.py` does not expose either field. The audited
FY2017–19 SAV files contain numeric `YRMONTH`, `CERTMTH`, and `LASTCERT` values.

The split reconstructs recorded certification month by subtracting the
integer-valued `LASTCERT` from the sampled `YRMONTH`, then compares that month
with September 2016. `CERTMTH` cannot itself date certification and is not used
in the subtraction. All selected cases were classifiable. This supports a
clean split by recorded certification vintage, but not a direct indicator of
whether a case was technically converted; the artifact and memo therefore do
not label the groups as observed conversion status.

## Floating-point overlap residuals

Overlap dollars are reported as the sum of the three channel-dollar totals
minus union strict dollars. In years without overlapping cases, independent
floating-point summation can leave residuals near zero (below $0.000000001).
They are retained in the JSON rather than post-hoc rounded; the generated memo
rounds dollar accounting to cents.
