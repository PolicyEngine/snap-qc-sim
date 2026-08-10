"""The deploy cache-buster: index.html's script version must match app.js's."""

import re
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "app" / "public"


def test_index_script_version_matches_app_constant():
    html = (PUBLIC / "index.html").read_text()
    js = (PUBLIC / "app.js").read_text()
    html_v = re.search(r'src="app\.js\?v=([A-Za-z0-9._-]+)"', html)
    js_v = re.search(r'const ASSET_V = "([A-Za-z0-9._-]+)"', js)
    assert html_v, "index.html must load app.js with a ?v= cache-buster"
    assert js_v, "app.js must define ASSET_V"
    assert html_v.group(1) == js_v.group(1)


def test_all_data_fetches_are_versioned():
    js = (PUBLIC / "app.js").read_text()
    for name in ("data.json", "model_data.json", "model_scenarios.json"):
        assert f'fetch("{name}?v=" + ASSET_V)' in js, f"{name} fetch must carry ASSET_V"
        assert f'fetch("{name}")' not in js, f"unversioned {name} fetch remains"
