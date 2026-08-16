"""Lock the migrations-paper wrapper to its rendered manuscript and routes."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "app" / "public" / "paper-migrations" / "index.html"
WEB = ROOT / "app" / "public" / "paper-migrations" / "web"
VERCEL = ROOT / "app" / "public" / "vercel.json"
QMD = ROOT / "paper-causal" / "index.qmd"


def test_wrapper_frames_versioned_manuscript() -> None:
    html = WRAPPER.read_text()
    versions = set(re.findall(r"web/index\.html\?v=([A-Za-z0-9-]+)", html))
    assert len(versions) == 1, versions
    assert "Revision 1 · 2026-08-16" in html
    assert (WEB / "index.html").is_file() and (WEB / "index.pdf").is_file()
    assert "three SNAP eligibility-system migrations" in html


def test_rendered_manuscript_matches_source_title_and_verdicts() -> None:
    rendered = (WEB / "index.html").read_text()
    source = QMD.read_text()
    assert "What a system replacement does to measured error" in rendered
    for phrase in (
        "bundled system replacement as implemented",
        "no_protocol_defined_signal",
        "signal_family_adjusted",
        "verdict-inert",
    ):
        assert phrase in source and phrase in rendered, phrase


def test_vercel_routes_the_migrations_paper() -> None:
    rewrites = json.loads(VERCEL.read_text())["rewrites"]
    sources = {r["source"] for r in rewrites}
    assert "/us/snap-payment-error-simulator/paper-migrations/" in sources
    assert "/us/snap-payment-error-simulator/paper-migrations/:rest*" in sources


def test_events_section_links_the_migrations_paper() -> None:
    index = (ROOT / "app" / "public" / "index.html").read_text()
    section = re.search(
        r'<section class="chart-card" id="events">.*?</section>', index, re.DOTALL
    )
    assert section and 'href="paper-migrations/"' in section.group(0)
