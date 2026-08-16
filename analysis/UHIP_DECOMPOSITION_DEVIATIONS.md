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

## Maintainer note after estimation: the client placebo depends on the joint donor fit

Recorded 2026-08-16 by the maintainer, after reading the results; the
protocol was not edited.

The parent Rhode Island study reported a client-placebo permutation p of
0.233 (effect +3.96, rank 10 of 43). This decomposition, on the same
placebo outcome, same donor pool, same specification, reports p = 0.023
(effect +5.64, rank 1 of 43). The difference is not an estimation
error: the inherited design fits donor weights jointly across every
outcome in the run, scaled by donor pretreatment dispersion, and this
run carries eight channel outcomes plus the placebo where the parent
carried strict, total, and client. The synthetic Rhode Island moved
(parent: WV 0.36, MI 0.35, CT 0.19; here: OH 0.31, SD 0.30, MI 0.13,
MD 0.13), and the client gap moved with it.

Consequences, stated as the protocol's own rules dictate:

- Under the parent reporting rule the two channels with p = 0.023
  (mass_change; defect_or_mass_change) do NOT earn `signal`, because
  the client placebo p is below 0.10 in this run. The verdict fields
  say so and are correct.
- The parent study's published verdicts are unchanged (this protocol
  says nothing here changes them), but the parent design has a
  documented sensitivity: placebo status is a function of which
  outcomes share the donor fit. That is a finding about the design,
  worth carrying into the causal paper's methods and into any future
  protocol (candidate fix, NOT applied here: fit donor weights on a
  fixed outcome set — for example strict + total + client — and hold
  them for every channel, so the placebo is estimated once and
  channels vary only the outcome). Whether the parent's own placebo
  survives a placebo-only or strict-only donor fit is an open
  sensitivity to run under a new frozen protocol, not a post-hoc edit
  to either.
- Nothing above changes the descriptive fact the raw counts and the
  channel paths show: Rhode Island's strict computing-apparatus
  dollars rise from about $0.4M (FY2016) to $6.9M (FY2017), and
  mass_change (code 19) carries most of that rise, with disregard
  (code 12) flat against its donor.
