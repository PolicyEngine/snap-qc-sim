"""snap-qc-sim: Monte Carlo simulation of SNAP payment error rates.

Simulates the distribution of a state's measured SNAP payment error rate —
and therefore its 7 USC 2013(a)(2) cost-share tier and dollars — under two
kinds of state choice:

* quality-control audit volume (sample size), and
* policy simplification options that suppress whole error categories
  (standard medical deduction, standard self-employment deduction,
  heat-and-eat, broad-based categorical eligibility).

Data: the USDA FNS SNAP Quality Control public-use file and the official
published payment error rates. See README for method and caveats.
"""

from .data import QcCase, load_cases, load_official_rates
from .simulate import LEVERS, TIERS, lever_error, simulate, summarize, tier_of

__all__ = [
    "LEVERS",
    "TIERS",
    "QcCase",
    "lever_error",
    "load_cases",
    "load_official_rates",
    "simulate",
    "summarize",
    "tier_of",
]
