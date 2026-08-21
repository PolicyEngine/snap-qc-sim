"""Build app/public/data.json: per-state case arrays for in-browser Monte Carlo.

Usage: python scripts_build_data.py [QC_CSV] [PER_PDF] [PER_FY2025_PDF]
Positional arguments default to the author's cache paths so existing
invocations keep working; pass explicit paths to reproduce elsewhere.
"""

import base64
import csv
import json
import sys
from pathlib import Path

from snap_qc_sim import LEVERS, load_cases, load_official_rates

QC = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
PER = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/snap-fy24QC-PER.pdf"
PER25 = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/snap-qcfy25-per.pdf"
VERIFIED = {"CO": 856, "NY": 847, "CA": 883, "AZ": 922, "GA": 945, "MD": 722, "TX": 906}
LEVER_KEYS = ["smd", "ssed", "heat_and_eat", "bbce_resources"]

if len(sys.argv) > 4:
    raise SystemExit(
        "usage: python scripts_build_data.py [QC_CSV] [PER_PDF] [PER_FY2025_PDF]"
    )
qc_path = sys.argv[1] if len(sys.argv) > 1 else QC
per_path = sys.argv[2] if len(sys.argv) > 2 else PER
per25_path = sys.argv[3] if len(sys.argv) > 3 else PER25

cases_by_state = load_cases(qc_path)


def _num(value: str | None) -> float | None:
    value = (value or "").strip()
    if not value or value == ".":
        return None
    return float(value)


def _self_employment_by_state(path: str) -> dict[str, list[bool]]:
    """Mirror load_cases' universe and row order for a compact client bitset."""
    from snap_qc_sim.data import FIPS

    flags: dict[str, list[bool]] = {}
    with open(path) as source:
        for row in csv.DictReader(source):
            state = FIPS.get((row.get("STATE") or "").strip())
            if state is None:
                continue
            case_flag = _num(row.get("CASE"))
            if case_flag is not None and case_flag != 1:
                continue
            if _num(row.get("RAWBEN")) is None or (_num(row.get("HWGT")) or 0) <= 0:
                continue
            person = any(
                (_num(row.get(f"SLFEMP{i}")) or 0) > 0 for i in range(1, 19)
            )
            flag = person or (_num(row.get("FSSLFEMP")) or 0) > 0
            flags.setdefault(state, []).append(flag)
    return flags


def _pack_bits(flags: list[bool]) -> str:
    packed = bytearray((len(flags) + 7) // 8)
    for i, flag in enumerate(flags):
        if flag:
            packed[i // 8] |= 1 << (i % 8)
    return base64.b64encode(packed).decode("ascii")


self_employment_by_state = _self_employment_by_state(qc_path)
official = load_official_rates(per_path, include_national=True)
official_fy2025 = load_official_rates(per25_path, include_national=True)
missing_fy2025 = sorted(set(official) - set(official_fy2025) - {"US"})
if missing_fy2025:
    raise SystemExit(f"FY2025 table is missing jurisdictions: {missing_fy2025}")
out = {}
for state, cases in sorted(cases_by_state.items()):
    if state not in official:
        continue
    w, iss, err, hits = [], [], [], []
    for c in cases:
        w.append(round(c.weight, 2))
        iss.append(round(c.issuance))
        err.append(round(c.error))
        if c.error > 0 and c.elements:
            tot = len(c.elements)
            hits.append([tot] + [len(c.elements & LEVERS[k]) for k in LEVER_KEYS])
        else:
            hits.append(0)
    self_emp = self_employment_by_state.get(state, [])
    if len(self_emp) != len(cases):
        raise SystemExit(f"{state}: self-employment flags do not align with cases")
    out[state] = {
        "official": official[state],
        "official_fy2025": official_fy2025[state],
        "issuance": round(sum(c.weight * c.issuance for c in cases)),
        "n": len(cases),
        "verified": VERIFIED.get(state),
        "w": w,
        "iss": iss,
        "err": err,
        "hits": hits,
        "self_emp": _pack_bits(self_emp),
    }
path = Path("app/public/data.json")
path.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "levers": LEVER_KEYS,
    "self_emp_encoding": "base64, little-endian bits within each byte",
    "national": {"fy2024": official.get("US"), "fy2025": official_fy2025.get("US")},
    "states": out,
}
with path.open("w", encoding="utf-8") as output:
    json.dump(payload, output, separators=(",", ":"))
print(f"{path}: {path.stat().st_size / 1e6:.1f}MB, {len(out)} states")
