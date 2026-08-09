"""FY2024 → FY2025 official-rate movement against simulated sampling noise.

The fiscal 2025 official payment error rates published 2026-06-24 are the
first of the two rates a state may elect for its FY2028 cost share. This
script asks, per state: did the official rate move more than the sampling
noise this simulator attributes to a QC-sized sample? Movements within
noise are what the paper's tier-lottery thesis predicts; movements beyond
it are evidence of process change (or methodology change) between years.

Deterministic: fixed seed, committed inputs. Outputs
``analysis/fy2025_movement.json`` and ``analysis/FY2025_MOVEMENT.md``.
The z convention is disclosed in the artifact: the denominator is the
FY2024-anchored sampling SD only; both years carry sampling noise, so a
two-year-noise 95% band under independence is |z| > 1.96 * sqrt(2) = 2.77.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from snap_qc_sim import load_cases, simulate

DATA_JSON = REPO_ROOT / "app" / "public" / "data.json"
OUT_JSON = REPO_ROOT / "analysis" / "fy2025_movement.json"
OUT_MD = REPO_ROOT / "analysis" / "FY2025_MOVEMENT.md"
QC_CSV = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
FY25_PDF_SHA256 = "ae3fc57f2398cea36e9c1322f9f2208a39a7045a4524d259bd1ac22e890c754e"

SEED = 11
DRAWS = 4000
# FY2028 cost-share tiers, 7 U.S.C. 2013(a)(2): hand-transcribed pending the
# encoded schedule (rulespec-us 275.11/2013(a)(2) lane).
TIER_CUTS = ((6.0, 0), (8.0, 5), (10.0, 10), (math.inf, 15))
TWO_YEAR_Z = 1.96 * math.sqrt(2)


def tier_share(rate: float) -> int:
    """Return the FY2028 cost-share percentage for a payment error rate."""
    if not math.isfinite(rate) or rate < 0:
        raise ValueError(f"rate must be finite and nonnegative: {rate}")
    for cut, share in TIER_CUTS:
        if rate < cut:
            return share
    raise AssertionError("unreachable")


def delay_applies(rate: float) -> bool:
    """7 U.S.C. 2013(a)(2)(B)(iii): delayed start when rate x 1.5 reaches 20%."""
    if not math.isfinite(rate) or rate < 0:
        raise ValueError(f"rate must be finite and nonnegative: {rate}")
    return rate * 1.5 >= 20.0


def movement_row(
    state: str, fy2024: float, fy2025: float, sd_fy2024_pp: float
) -> dict[str, object]:
    """One state's movement record; pure given the three inputs."""
    delta = fy2025 - fy2024
    z = delta / sd_fy2024_pp if sd_fy2024_pp > 0 else math.inf * math.copysign(1, delta)
    return {
        "state": state,
        "fy2024": fy2024,
        "fy2025": fy2025,
        "delta_pp": round(delta, 4),
        "sampling_sd_fy2024_pp": round(sd_fy2024_pp, 4),
        "z_vs_fy2024_sampling_sd": round(z, 4),
        "beyond_two_year_noise_95": bool(abs(z) > TWO_YEAR_Z),
        "tier_fy2024": tier_share(fy2024),
        "tier_fy2025": tier_share(fy2025),
        "tier_changed": tier_share(fy2024) != tier_share(fy2025),
        "delay_fy2024": delay_applies(fy2024),
        "delay_fy2025": delay_applies(fy2025),
    }


def build() -> dict[str, object]:
    data = json.loads(DATA_JSON.read_text())
    cases_by_state = load_cases(QC_CSV)
    rows = []
    for state in sorted(data["states"]):
        st = data["states"][state]
        cases = cases_by_state[state]
        draws = simulate(
            cases,
            st["official"],
            draws=DRAWS,
            rng=np.random.default_rng(SEED),
        )
        rows.append(
            movement_row(
                state, st["official"], st["official_fy2025"], float(np.std(draws))
            )
        )
    deltas = np.array([r["delta_pp"] for r in rows], dtype=float)
    beyond = [r["state"] for r in rows if r["beyond_two_year_noise_95"]]
    flips = [
        f"{r['state']} {r['tier_fy2024']}%->{r['tier_fy2025']}%"
        for r in rows
        if r["tier_changed"]
    ]
    delay24 = [r["state"] for r in rows if r["delay_fy2024"]]
    delay25 = [r["state"] for r in rows if r["delay_fy2025"]]
    return {
        "definitions": {
            "delta_pp": "FY2025 official minus FY2024 official, percentage points",
            "sampling_sd_fy2024_pp": (
                "SD of the simulator's FY2024-anchored measured-rate draws "
                f"({DRAWS} draws, seed {SEED}, observed resample, unclipped)"
            ),
            "z_convention": (
                "denominator is FY2024 sampling SD only; both years carry "
                "sampling noise, so the two-year 95% band under independence "
                f"and equal SDs is |z| > {TWO_YEAR_Z:.2f}"
            ),
            "delay_rule": "7 USC 2013(a)(2)(B)(iii): published rate x 1.5 >= 20",
            "tiers": "0/5/10/15% shares at <6, 6-8, 8-10, >=10",
        },
        "provenance": {
            "fy2024_source": "app/public/data.json officials (FNS FY2024 PER)",
            "fy2025_source": f"FNA FY2025 PER pdf sha256 {FY25_PDF_SHA256}",
            "generator": "analysis/fy2025_movement.py",
        },
        "national": data["national"],
        "aggregates": {
            "jurisdictions": len(rows),
            "mean_abs_delta_pp": round(float(np.mean(np.abs(deltas))), 4),
            "persistence_mae_pp": round(float(np.mean(np.abs(deltas))), 4),
            "median_abs_z": round(
                float(
                    np.median(
                        [abs(r["z_vs_fy2024_sampling_sd"]) for r in rows]
                    )
                ),
                4,
            ),
            "beyond_two_year_noise_95_count": len(beyond),
            "beyond_two_year_noise_95_states": beyond,
            "tier_flip_count": len(flips),
            "tier_flips": flips,
            "delay_fy2024_states": delay24,
            "delay_fy2025_states": delay25,
            "delay_dropped": sorted(set(delay24) - set(delay25)),
            "delay_added": sorted(set(delay25) - set(delay24)),
        },
        "states": rows,
    }


def render_markdown(result: dict[str, object]) -> str:
    agg = result["aggregates"]
    lines = [
        "<!-- Generated by analysis/fy2025_movement.py; do not edit manually. -->",
        "",
        "# FY2024 to FY2025 official-rate movement",
        "",
        (
            f"National: {result['national']['fy2024']}% (FY2024) to "
            f"{result['national']['fy2025']}% (FY2025). Mean absolute state "
            f"movement {agg['mean_abs_delta_pp']}pp; median |z| against the "
            f"FY2024-anchored sampling SD {agg['median_abs_z']}; "
            f"{agg['beyond_two_year_noise_95_count']} of {agg['jurisdictions']} "
            f"jurisdictions moved beyond the two-year sampling-noise 95% band "
            f"(|z| > {TWO_YEAR_Z:.2f})."
        ),
        "",
        (
            f"Tier changes at the published point rates: {agg['tier_flip_count']} "
            f"({', '.join(agg['tier_flips']) or 'none'})."
        ),
        "",
        (
            f"Delay clause (rate x 1.5 >= 20): {len(agg['delay_fy2024_states'])} "
            f"jurisdictions at FY2024 rates, {len(agg['delay_fy2025_states'])} at "
            f"FY2025 rates; dropped {', '.join(agg['delay_dropped']) or 'none'}; "
            f"added {', '.join(agg['delay_added']) or 'none'}."
        ),
        "",
        "| State | FY2024 | FY2025 | Delta (pp) | Sampling SD (pp) | z | Tier 24 | Tier 25 | Delay 25 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in result["states"]:
        lines.append(
            f"| {r['state']} | {r['fy2024']:.2f} | {r['fy2025']:.2f} "
            f"| {r['delta_pp']:+.2f} | {r['sampling_sd_fy2024_pp']:.2f} "
            f"| {r['z_vs_fy2024_sampling_sd']:+.2f} | {r['tier_fy2024']}% "
            f"| {r['tier_fy2025']}% | {'yes' if r['delay_fy2025'] else ''} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    result = build()
    OUT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    OUT_MD.write_text(render_markdown(result))
    digest = hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()
    print(f"wrote {OUT_JSON} (sha256 {digest[:16]}...)")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
