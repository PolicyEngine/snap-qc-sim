"""QC Monte Carlo: measured-rate distributions under audit-volume and policy levers.

v1 per DESIGN.md. Error process from the FY2024 public file; sampling layer
centered on official FY2024 PERs; levers suppress finding-element categories.
"""
from __future__ import annotations

import csv, json, re, subprocess
from collections import defaultdict
import numpy as np

QC = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/qc_pub_fy2024.csv"
PER_PDF = "/Users/maxghenis/.cache/axiom-oracles/snap-qc/snap-fy24QC-PER.pdf"
THRESHOLD = 56.0
TIERS = [(6.0, 0), (8.0, 5), (10.0, 10), (float("inf"), 15)]

# Lever -> QC finding ELEMENT codes it suppresses.
LEVERS = {
    "smd": {365},                       # standard medical deduction sized right
    "ssed": {312},                      # standard self-employment deduction
    "heat_and_eat": {364},              # SUA entitlement (elderly/disabled arm approximated as full 364)
    "bbce_resources": {211, 212, 213, 221, 222, 224, 225},
}

FIPS = {"1":"AL","2":"AK","4":"AZ","5":"AR","6":"CA","8":"CO","9":"CT","10":"DE","11":"DC",
        "12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS",
        "21":"KY","22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS",
        "29":"MO","30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY",
        "37":"NC","38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC",
        "46":"SD","47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV",
        "55":"WI","56":"WY","66":"GU","78":"VI"}
NAME = {"ALABAMA":"AL","ALASKA":"AK","ARIZONA":"AZ","ARKANSAS":"AR","CALIFORNIA":"CA","COLORADO":"CO",
        "CONNECTICUT":"CT","DELAWARE":"DE","DIST. OF COLUMBIA":"DC","DISTRICT OF COLUMBIA":"DC",
        "FLORIDA":"FL","GEORGIA":"GA","GUAM":"GU","HAWAII":"HI","IDAHO":"ID","ILLINOIS":"IL",
        "INDIANA":"IN","IOWA":"IA","KANSAS":"KS","KENTUCKY":"KY","LOUISIANA":"LA","MAINE":"ME",
        "MARYLAND":"MD","MASSACHUSETTS":"MA","MICHIGAN":"MI","MINNESOTA":"MN","MISSISSIPPI":"MS",
        "MISSOURI":"MO","MONTANA":"MT","NEBRASKA":"NE","NEVADA":"NV","NEW HAMPSHIRE":"NH",
        "NEW JERSEY":"NJ","NEW MEXICO":"NM","NEW YORK":"NY","NORTH CAROLINA":"NC","NORTH DAKOTA":"ND",
        "OHIO":"OH","OKLAHOMA":"OK","OREGON":"OR","PENNSYLVANIA":"PA","RHODE ISLAND":"RI",
        "SOUTH CAROLINA":"SC","SOUTH DAKOTA":"SD","TENNESSEE":"TN","TEXAS":"TX","UTAH":"UT",
        "VERMONT":"VT","VIRGIN ISLANDS":"VI","VIRGINIA":"VA","WASHINGTON":"WA","WEST VIRGINIA":"WV",
        "WISCONSIN":"WI","WYOMING":"WY"}


def _num(v):
    v = (v or "").strip()
    return None if not v or v == "." else float(v)


def load_official():
    txt = subprocess.run(["pdftotext", "-layout", PER_PDF, "-"], capture_output=True, text=True).stdout
    out = {}
    for line in txt.splitlines():
        m = re.match(r"\s*([A-Z][A-Z .]+?)\s{2,}([\d.]+)\s{2,}([\d.]+)\s{2,}([\d.]+)\s*$", line)
        if m and m.group(1).strip() in NAME:
            out[NAME[m.group(1).strip()]] = float(m.group(4))
    return out


def load_cases():
    """Per state: weight, issuance, counted error dollars, finding elements."""
    by_state = defaultdict(list)
    with open(QC) as f:
        for row in csv.DictReader(f):
            ab = FIPS.get((row.get("STATE") or "").strip())
            if ab is None:
                continue
            rawben = _num(row.get("RAWBEN"))
            if rawben is None:
                continue
            w = _num(row.get("HWGT")) or 0.0
            fsben = _num(row.get("FSBEN"))
            amterr = _num(row.get("AMTERR")) or 0.0
            counted = (
                (row.get("STATUS") or "").strip() in ("2", "3")
                and fsben is not None and abs(rawben - fsben) > THRESHOLD
            )
            elements = set()
            for i in range(1, 10):
                e = _num(row.get(f"ELEMENT{i}"))
                if e is not None:
                    elements.add(int(e))
            by_state[ab].append((w, rawben, amterr if counted else 0.0, frozenset(elements)))
    return by_state


def lever_error(err, elements, suppressed, effectiveness):
    """Suppressed error dollars for a case under a lever set.

    Single-attribution approximation: a case's counted error is scaled by the
    share of its finding elements that survive; a case whose findings are all
    suppressed drops out at `effectiveness`.
    """
    if err == 0 or not elements:
        return err
    hit = len(elements & suppressed) / len(elements)
    return err * (1 - effectiveness * hit)


def simulate(cases, official_rate, *, n=None, extra_audits=0, suppressed=frozenset(),
             effectiveness=1.0, draws=10_000, rng=None):
    rng = rng or np.random.default_rng(11)
    w = np.array([c[0] for c in cases])
    iss = np.array([c[1] for c in cases])
    err0 = np.array([c[2] for c in cases])
    err = np.array([lever_error(c[2], c[3], suppressed, effectiveness) for c in cases])
    n_cases = len(cases)
    point0 = 100 * (w * err0).sum() / (w * iss).sum()
    point1 = 100 * (w * err).sum() / (w * iss).sum()
    level = official_rate + (point1 - point0)          # official level, lever-shifted
    m = n if n is not None else n_cases
    m = int(round(m + extra_audits))
    idx = rng.integers(0, n_cases, size=(draws, m))
    We = (w * err)[idx].sum(axis=1)
    Wi = (w * iss)[idx].sum(axis=1)
    boots = 100 * We / Wi
    # Resampling at size m already carries the audit-volume variance effect:
    # SD scales ~ 1/sqrt(m). Center the distribution at the lever-shifted
    # official level.
    centered = level + (boots - point1)
    return centered


def tier_of(rate):
    for cut, share in TIERS:
        if rate < cut:
            return share
    return 15


def summarize(rates, issuance):
    shares = np.array([tier_of(r) for r in rates], dtype=float)
    return {
        "mean_rate": float(rates.mean()),
        "sd": float(rates.std()),
        "p_tier": {str(s): float((shares == s).mean()) for s in (0, 5, 10, 15)},
        "e_share_pct": float(shares.mean()),
        "e_cost_share_usd": float((shares / 100 * issuance).mean()),
        "p95_cost_share_usd": float(np.percentile(shares / 100 * issuance, 95)),
    }
