# Exemplar: introduction (calibration sample — match this register)

Three states replaced the computer systems that determine SNAP
eligibility and benefits, and each replacement left a mark, or failed
to, in a record built for another purpose. Every month, state reviewers
re-work a sample of active SNAP cases from scratch, record every dollar
the state paid in error, and code why. Those quality-control files are
public back to fiscal 2012. They carry the outcome a migration should
move if it moves anything — error dollars the reviewers attribute to
the computing apparatus — and they carry it for every state, every
year, under one federal definition. This paper uses them as an
outcome panel and asks what three eligibility-system replacements did
to measured error.

The events are Rhode Island's UHIP launch in September 2016,
Kentucky's Benefind launch on February 29, 2016, and Oregon's ONE
expansion to SNAP in February 2021. Each is estimated against a
synthetic control built from states that never migrated, with
inference by permutation across those states and a decision rule
frozen before estimation. The estimand throughout is the bundled system
replacement as implemented — software, process, and staffing together.
It is never the effect of software, and never the effect of a rules
engine.

Rhode Island's computing-apparatus error dollars rise \$2.90 per
weighted case-month against its synthetic donor (permutation p =
0.023), the client-caused placebo stays flat, and the rise concentrates
in fiscal 2017 through 2019, the years for which the Food and Nutrition
Service later billed the state \$37.3 million for overpayments. The
billing record played no part in the estimate; the alignment is a
descriptive check the protocol names as verdict-inert. Kentucky shows
no protocol-defined signal (−\$0.58, p = 0.30) despite a launch the
press documented as troubled, and the design refuses Oregon outright:
its client-caused placebo fires inside the pandemic window, so nothing
can be attributed. One signal, one null, one refusal, each the frozen
rule's own verdict.

The Rhode Island signal then decomposes. The reviewers' cause codes
distinguish a system that computed wrong from workers who could not
drive it from information that reached the agency and died in a queue,
and a second frozen protocol estimates each channel. The rise sits in
computer-generated mass-change error — batch actions computed wrong at
scale — at \$2.14 per case-month under the parent's own synthetic Rhode
Island (p = 0.023, first of 43 placebo states, and still a signal after
adjusting for the three channels tested), while information-disregarded
error does not move against its donor. Worker error and data-entry
error are small in every specification. Two-thirds of the post-launch
computing-apparatus dollars sit on cases certified after the go-live,
and the affected budget elements shift toward the shelter deduction the
system computes. This describes how the QC record classified UHIP's
failures; the reviewer's choice among codes is part of the measurement.

The decomposition also surfaced a property of the design worth stating
first rather than last. The inherited estimator fits donor weights
jointly across every outcome in a run, so adding eight channel outcomes
moved the synthetic Rhode Island and, with it, the client placebo — from
p = 0.233 to p = 0.023 on identical data. A fixed-donor estimator that
fits the weights once, on the parent's three outcomes, and holds them
for every channel reproduces the parent's placebo exactly and returns
the mass-change signal. Both estimators appear side by side; the
reproduction check is the bridge between them, and neither is
privileged.

What follows is the record, the design, the three verdicts, the
decomposition under both estimators, and the limits: one treated unit
per event, permutation denominators of 35 and 43, cause-code cells
that thin to single digits, and a coder's classification standing
between the file and the machine.
