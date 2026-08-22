"""Lock the cause-coded computation-error lever's data and copy.

The lever scales each case's error dollars by its share of agency-coded
findings in {17, 19, 20} (computer programming, computer-generated mass
change, arithmetic computation), times a chosen effectiveness. These
locks pin the payload's per-case counts, the hint's quoted national
share, and a Python mirror of the client arithmetic.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "public" / "data.json"
INDEX = ROOT / "app" / "public" / "index.html"
APP_JS = ROOT / "app" / "public" / "app.js"


@pytest.fixture(scope="module")
def states() -> dict:
    return json.loads(DATA.read_text())["states"]


def test_agency_findings_domains(states) -> None:
    for code, st in states.items():
        pairs = st["agency_findings"]
        assert len(pairs) == st["n"], code
        for pair in pairs:
            if pair == 0:
                continue
            n, strict = pair
            assert 1 <= n <= 9, (code, pair)
            assert 0 <= strict <= n, (code, pair)


def test_payload_documents_the_encoding() -> None:
    payload = json.loads(DATA.read_text())
    doc = payload["agency_findings_encoding"]
    assert "17/19/20" in doc


def test_hint_quotes_the_recomputed_national_share(states) -> None:
    num = den = 0.0
    for st in states.values():
        for w, err, pair in zip(st["w"], st["err"], st["agency_findings"], strict=True):
            if err and pair:
                num += w * err * (pair[1] / pair[0])
            den += w * err
    share = 100 * num / den
    quoted = re.search(
        r"([\d.]+)% of counted error dollars nationally", INDEX.read_text()
    )
    assert quoted, "hint does not quote the national share"
    assert float(quoted.group(1)) == pytest.approx(share, abs=0.05)


def test_python_mirror_of_the_client_arithmetic(states) -> None:
    """Full-effectiveness Colorado delta, mirroring engineCutErr + pointRate."""
    co = states["CO"]

    def point(errs: list[float]) -> float:
        weighted_err = sum(w * e for w, e in zip(co["w"], errs, strict=True))
        weighted_iss = sum(w * i for w, i in zip(co["w"], co["iss"], strict=True))
        return 100 * weighted_err / weighted_iss

    cut = [
        err * (1 - (pair[1] / pair[0] if pair else 0.0))
        for err, pair in zip(co["err"], co["agency_findings"], strict=True)
    ]
    delta = point(cut) - point(co["err"])
    assert delta == pytest.approx(-0.2376, abs=5e-4)


def test_lever_copy_and_wiring_present() -> None:
    index = INDEX.read_text()
    assert "Cut computation-caused errors" in index
    for code in ("(17)", "(19)", "(20)", "(18)", "(21)"):
        assert code in index
    js = APP_JS.read_text()
    assert "engineCutErr" in js
    assert "lever-engine-cut" in js
    section = re.search(
        r'<div class="control levers">\s*<span class="label">Rules-engine'
        r" scenario.*?</div>\s*</div>",
        index,
        re.DOTALL,
    )
    assert section and "causal" not in section.group(0).lower()
