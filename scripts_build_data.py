"""Build app/public/data.json: per-state case arrays for in-browser Monte Carlo."""
import json
from pathlib import Path

from snap_qc_sim import LEVERS, load_cases, load_official_rates

QC = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
PER = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/snap-fy24QC-PER.pdf"
VERIFIED = {"CO": 856, "NY": 847, "CA": 883, "AZ": 922, "GA": 945, "MD": 722, "TX": 906}
LEVER_KEYS = ["smd", "ssed", "heat_and_eat", "bbce_resources"]

cases_by_state = load_cases(QC)
official = load_official_rates(PER)
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
    out[state] = {
        "official": official[state],
        "issuance": round(sum(c.weight * c.issuance for c in cases)),
        "n": len(cases),
        "verified": VERIFIED.get(state),
        "w": w, "iss": iss, "err": err, "hits": hits,
    }
path = Path("app/public/data.json")
path.parent.mkdir(parents=True, exist_ok=True)
json.dump({"levers": LEVER_KEYS, "states": out}, open(path, "w"), separators=(",", ":"))
print(f"{path}: {path.stat().st_size/1e6:.1f}MB, {len(out)} states")
