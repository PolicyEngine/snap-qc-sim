"""Before/after screenshots and a per-state chart sweep for PR #100.

Runs in GitHub Actions only (headless Chromium on ubuntu). Serves
origin/main's app/public as "before" and the PR head's as "after".
"""

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
SITES = {"before": "http://127.0.0.1:8001", "after": "http://127.0.0.1:8002"}
PATH = "/us/snap-payment-error-simulator/"
SIZES = {"desktop": (1280, 900, 1), "phone": (390, 844, 2)}
# The chart sweep adds the widths where tier labels used to collide.
SWEEP_SIZES = {**SIZES, "small-tablet": (600, 900, 1), "tablet": (768, 1024, 1)}
# The analyst artifacts load when the tools open; wait until the targeted
# review panel has left its loading line.
ANALYST_READY = (
    "(() => { const t = document.getElementById('interventions-live').textContent;"
    " return t.length > 0 && !t.startsWith('Loading'); })()"
)

CHECK = """() => {
  const res = [];
  for (const svg of document.querySelectorAll('#answer-strip svg, #fy2027-body svg, #adoption-body svg, #hist svg, #tiers svg')) {
    const id = svg.closest('[id]').id, vb = svg.viewBox.baseVal;
    const t = [...svg.querySelectorAll('text')].map((e) => { const b = e.getBBox(); return {s: e.textContent, x0: b.x, x1: b.x + b.width, y0: b.y, y1: b.y + b.height}; });
    t.filter((b) => b.x0 < -0.5 || b.x1 > vb.width + 0.5).forEach((b) => res.push(id + ' clipped: ' + b.s));
    for (let i = 0; i < t.length; i++) for (let j = i + 1; j < t.length; j++) {
      const a = t[i], b = t[j];
      if (a.x0 < b.x1 - 1 && b.x0 < a.x1 - 1 && a.y0 < b.y1 - 1 && b.y0 < a.y1 - 1) res.push(id + ' overlap: ' + a.s + ' | ' + b.s);
    }
  }
  const row = document.querySelector('#nat-table tbody tr.current');
  const cells = row ? [...row.querySelectorAll('td')].map((c) => c.textContent.trim()) : null;
  const links = [...document.querySelectorAll('.pe-shell-links a')].filter((a) => a.offsetParent !== null).length;
  return {res, links, overflowX: document.documentElement.scrollWidth - innerWidth, points: document.getElementById('answer-points').innerText, lead: document.getElementById('answer-lead').innerText, cells};
}"""


def settle(page):
    page.wait_for_function("!document.getElementById('nat-note') || document.getElementById('nat-note').textContent === ''", timeout=180_000)
    page.wait_for_timeout(400)


def money(s):
    """'$159 million' / '$1.27 billion' / '$159M' / '$1.27B' -> dollars."""
    m = re.search(r"\$([\d.]+)\s*(million|billion|M|B)", s)
    return float(m.group(1)) * (1e9 if m.group(2) in ("billion", "B") else 1e6)


def chance_matches(answer, table):
    # The table's short form rounds as the answer does and never shows 0% or 100%.
    short = {"less than 1%": "<1%", "more than 99%": ">99%"}
    return table == short.get(answer, answer) and table not in ("0%", "100%")


with sync_playwright() as p:
    browser = p.chromium.launch()
    for site, base in SITES.items():
        for size, (w, h, dsf) in SIZES.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf, color_scheme="light")
            page = ctx.new_page()
            page.goto(base + PATH + "?state=CO", wait_until="networkidle")
            settle(page)
            page.screenshot(path=str(OUT / f"{site}-{size}-fold.png"))
            page.screenshot(path=str(OUT / f"{site}-{size}-full.png"), full_page=True)
            if site == "after":
                page.evaluate("document.getElementById('analyst').open = true")
                page.wait_for_function(ANALYST_READY, timeout=120_000)
                page.wait_for_timeout(800)
                page.screenshot(path=str(OUT / f"{site}-{size}-analyst-full.png"), full_page=True)
            ctx.close()

    # Dark mode, after only, first screen.
    for size, (w, h, dsf) in SIZES.items():
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf, color_scheme="dark")
        page = ctx.new_page()
        page.goto(SITES["after"] + PATH + "?state=CO", wait_until="networkidle")
        settle(page)
        page.screenshot(path=str(OUT / f"after-{size}-dark-fold.png"))
        ctx.close()

    # Sweep every jurisdiction at each width with the analyst tools open.
    report = {}
    for size, (w, h, _) in SWEEP_SIZES.items():
        ctx = browser.new_context(viewport={"width": w, "height": h})
        page = ctx.new_page()
        page.goto(SITES["after"] + PATH + "?state=CO", wait_until="networkidle")
        settle(page)
        page.evaluate("document.getElementById('analyst').open = true")
        page.wait_for_function(ANALYST_READY, timeout=120_000)
        page.wait_for_timeout(500)
        codes = page.eval_on_selector_all("#state option", "os => os.map(o => o.value)")
        problems, mismatches = {}, {}
        compared = {"tier_chance": 0, "bill": 0, "bill_fy29": 0}
        for code in codes:
            page.select_option("#state", code)
            page.wait_for_function(f"new URLSearchParams(location.search).get('state') === '{code}' && document.getElementById('answer-lead').innerText.length > 0")
            page.wait_for_timeout(120)
            r = page.evaluate(CHECK)
            issues = list(r["res"])
            if r["overflowX"] > 0:
                issues.append(f"page overflows horizontally by {r['overflowX']}px")
            if r["links"] == 0:
                issues.append("header links hidden")
            if issues:
                problems[code] = issues
            # Differential: the answer and the table row run the same baseline
            # simulation, so their tier chance and expected bill must agree.
            cells = r["cells"]
            diffs = []
            if not cells:
                diffs.append("no highlighted table row")
            else:
                m = re.search(r"lands in a different tier (less than 1%|more than 99%|\d+%) of the time", r["points"])
                if m:
                    compared["tier_chance"] += 1
                if m and not chance_matches(m.group(1), cells[3]):
                    diffs.append(f"tier chance: answer {m.group(1)} vs table {cells[3]}")
                b = re.search(r"expected FY 2028 bill is (\$[\d.]+ (?:million|billion))", r["points"])
                if b and "FY29" not in cells[4]:
                    compared["bill"] += 1
                    a, t = money(b.group(1)), money(cells[4])
                    # Each side rounds to its own display precision.
                    tol = (0.5e6 if b.group(1).endswith("million") else 5e6) + (
                        0.5e6 if cells[4].endswith("M") else 5e6
                    )
                    if abs(a - t) > tol:
                        diffs.append(f"bill: answer {b.group(1)} vs table {cells[4]}")
                # Delayed states: the row carries the FY 2029 bill.
                b29 = re.search(
                    r"expected FY 2029 bill is (\$0|under \$1 million|\$[\d.]+ (?:million|billion)) a year", r["points"]
                )
                if "FY29" in cells[4]:
                    if not b29:
                        diffs.append("delayed row but no FY 2029 bill in the answer")
                    else:
                        compared["bill_fy29"] += 1
                        w = b29.group(1)
                        a = 0.0 if w == "$0" else 0.25e6 if w.startswith("under") else money(w)
                        t = money(cells[4])
                        tol = (0.5e6 if w.endswith("million") or w == "$0" else 5e6) + (
                            0.5e6 if "M" in cells[4] else 5e6
                        )
                        if abs(a - t) > tol:
                            diffs.append(f"FY29 bill: answer {b29.group(1)} vs table {cells[4]}")
            if diffs:
                mismatches[code] = diffs
        # A regex that stops matching the copy would skip every comparison.
        if not all(compared.values()):
            mismatches["_sweep"] = [f"no comparisons ran: {compared}"]
        report[size] = {
            "states": len(codes),
            "comparisons": compared,
            "layout_problems": problems,
            "answer_table_mismatches": mismatches,
        }
        ctx.close()
    (OUT / "sweep.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    browser.close()
