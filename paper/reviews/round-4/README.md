# Round 4 — the fiscal 2025 revision (2026-08-09)

Two referees reviewed the revision-4 delta only (the fiscal 2025
realization section, the FY2027 threshold estimate, the FNA rename, the
updated delay footnote, and the feature-round paragraph), with
instructions to verify every number against the committed artifacts.
Reports are archived verbatim below, as received.

- `methodology.md` — methodology reviewer. Two blocking findings
  (the false pre-registration ordering; sibling passages and
  @tbl-validate stranded at pre-feature-round artifact values),
  seven minor, four nits. All applied.
- `red-team.md` — adversarial reviewer. Verdict "major revisions" on
  the same timeline blocker; independently reproduced the movement
  artifact byte-for-byte in a clean clone, hash-matched the official
  FY2025 PER PDF and diffed all 106 state rates, recomputed the FY2027
  threshold in exact fractions, and reimplemented the app's election
  engine (52.5% / $31M confirmed). One minor statutory-overstatement
  finding (the delay footnote's unconditional "first bill in FY2029"),
  applied.

The fixes landed in the same revision: the fiscal 2025 check is framed
as input independence (this repository postdates the June 24, 2026
publication — FACTS row J9), all superseded model figures were
refreshed to the current artifacts with supersession notes, and the
fact catalog gained the J-series.
