"""Generate the boundary-state measured-rate figure for the manuscript.

Reads the FY2024 QC CSV and official PER PDF via snap_qc_sim's own loader
(official error gate, CASE == 1) and draws Colorado's simulated measured-rate
distribution with cost-share tier bands. Deterministic: seed 11, 100,000
draws. Output: co_measured_rate.svg alongside this script.

Usage: uv run --frozen --extra analysis python paper/generate_figures.py \
    <qc_csv> <per_pdf>
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snap_qc_sim import load_cases, load_official_rates, simulate

DRAWS = 100_000
SEED = 11
TIERS = [(0, 6, "0%"), (6, 8, "5%"), (8, 10, "10%"), (10, 16, "15%")]
BAND = ["#F0F9FF", "#E0F2FE", "#BAE6FD", "#7DD3FC"]

def main(qc_csv: str, per_pdf: str) -> None:
    cases = load_cases(qc_csv)["CO"]
    official = load_official_rates(per_pdf)["CO"]
    rng = np.random.default_rng(SEED)
    rates = simulate(cases, official, draws=DRAWS, rng=rng)
    fig, ax = plt.subplots(figsize=(7.0, 3.4), dpi=150)
    lo, hi = 6.5, 13.5
    for (a, b, label), color in zip(TIERS, BAND):
        if b <= lo or a >= hi:
            continue
        ax.axvspan(max(a, lo), min(b, hi), color=color, zorder=0)
        ax.text((max(a, lo) + min(b, hi)) / 2, 0.97, f"{label} share",
                ha="center", va="top", transform=ax.get_xaxis_transform(),
                fontsize=8, color="#475569")
    ax.hist(rates, bins=80, range=(lo, hi), density=True,
            color="#0284C7", alpha=0.85, zorder=2)
    ax.axvline(official, color="#0F172A", lw=1.2, ls="--", zorder=3)
    ax.text(official + 0.06, 0.82, f"official {official:.2f}%",
            transform=ax.get_xaxis_transform(), fontsize=8, color="#0F172A")
    below = float(np.mean(np.asarray(rates) < 10.0))
    ax.set_xlim(lo, hi)
    ax.set_xlabel("simulated measured payment error rate (%)")
    ax.set_ylabel("density")
    ax.set_title(
        f"Colorado: {DRAWS:,} resampled QC-style measurements "
        f"(P(below the 10% boundary) = {below:.0%})",
        fontsize=9, loc="left")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    out = Path(__file__).parent / "figures"
    out.mkdir(exist_ok=True)
    fig.savefig(out / "co_measured_rate.svg")
    print(f"wrote {out / 'co_measured_rate.svg'}; P(below 10%) = {below:.4f}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
