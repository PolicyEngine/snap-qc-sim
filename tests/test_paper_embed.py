"""The embedded paper view stays consistent with the manuscript it frames.

Pattern (from PolicyBench's /paper page): /paper/ is a shelled wrapper —
site nav, paper header, action links, a versioned sandboxed iframe of the
raw manuscript at /paper/web/, and a back-to-top footer. The raw Quarto
render syncs to app/public/paper/web/, never to /paper/ itself.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "app/public/paper"


def test_wrapper_embeds_versioned_manuscript():
    html = (PAPER / "index.html").read_text()
    srcs = re.findall(r'<iframe src="(web/index\.html\?v=[^"]+)"', html)
    assert len(srcs) == 1, "exactly one embedded manuscript iframe"
    version = srcs[0].split("?v=")[1]
    # Every standalone-manuscript link carries the same version.
    for href in re.findall(r'href="(web/index\.html[^"]*)"', html):
        assert href.endswith(f"?v={version}"), href
    assert 'sandbox="allow-same-origin' in html


def test_manuscript_and_pdf_exist_under_web():
    assert (PAPER / "web/index.html").exists()
    assert (PAPER / "web/index.pdf").exists()
    # The wrapper is the only index at /paper/ — the raw render must not
    # overwrite it.
    wrapper = (PAPER / "index.html").read_text()
    assert "pe-shell-header" in wrapper


def test_old_pdf_path_still_serves():
    rewrites = (ROOT / "app/public/vercel.json").read_text()
    assert '"/paper/index.pdf"' in rewrites
    assert '"/paper/web/index.pdf"' in rewrites
