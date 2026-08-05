"""All-state scenario table: baseline, +500 audits, all levers at 50%/100%.

Usage:
    uv run python examples/all_states.py QC_CSV PER_PDF [--draws N]

Writes results_by_state.json next to this script and prints a summary table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from snap_qc_sim import LEVERS, load_cases, load_official_rates, simulate, summarize

ALL_LEVERS = frozenset().union(*LEVERS.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("qc_csv")
    ap.add_argument("per_pdf")
    ap.add_argument("--draws", type=int, default=100_000)
    args = ap.parse_args()

    cases_by_state = load_cases(args.qc_csv)
    official = load_official_rates(args.per_pdf)
    out: dict[str, dict] = {}
    print(
        f"{'state':<6}{'official':>8}{'E$ base':>9} | "
        f"{'dE$ +500 audits':>15} | {'dE$ levers 50%':>14}{'dE$ 100%':>9}"
    )
    for state in sorted(cases_by_state):
        if state not in official:
            continue
        cases = cases_by_state[state]
        issuance = sum(c.weight * c.issuance for c in cases)

        def scenario(
            seed: int = 11,
            *,
            _cases=cases,
            _rate=official[state],
            _issuance=issuance,
            **kw,
        ) -> dict:
            rates = simulate(
                _cases,
                _rate,
                rng=np.random.default_rng(seed),
                draws=args.draws,
                **kw,
            )
            return summarize(rates, _issuance)

        base = scenario()
        audits = scenario(extra_audits=500)
        lev50 = scenario(suppressed=ALL_LEVERS, effectiveness=0.5)
        lev100 = scenario(suppressed=ALL_LEVERS, effectiveness=1.0)
        out[state] = {
            "official_rate": official[state],
            "issuance": issuance,
            "base": base,
            "audits_500": audits,
            "levers_50": lev50,
            "levers_100": lev100,
        }
        d_aud = base["expected_cost_share"] - audits["expected_cost_share"]
        d_l50 = base["expected_cost_share"] - lev50["expected_cost_share"]
        d_l100 = base["expected_cost_share"] - lev100["expected_cost_share"]
        print(
            f"{state:<6}{official[state]:>7.2f}%"
            f"{base['expected_cost_share'] / 1e6:>8.0f}M |"
            f"{d_aud / 1e6:>+14.1f}M |"
            f"{d_l50 / 1e6:>+13.1f}M{d_l100 / 1e6:>+8.1f}M"
        )

    path = Path(__file__).with_name("results_by_state.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
