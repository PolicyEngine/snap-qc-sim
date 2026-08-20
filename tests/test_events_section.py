"""Lock the simulator's event-study section to the committed artifacts."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "app" / "public" / "index.html"
RIKY = ROOT / "analysis" / "riky_event_study_results.json"
OREGON = ROOT / "analysis" / "event_study_results.json"
MIGRATIONS = ROOT / "analysis" / "system_migrations.json"


def _events_html() -> str:
    html = INDEX.read_text()
    match = re.search(
        r'<section class="chart-card" id="events">.*?</section>', html, re.DOTALL
    )
    assert match, "events section missing from index.html"
    return match.group(0)


def test_events_section_numbers_match_artifacts() -> None:
    html = _events_html()
    riky = json.loads(RIKY.read_bytes())
    ri = riky["units"]["RI"]
    ky = riky["units"]["KY"]
    ri_effect = ri["specifications"]["primary_exclude_fy2016_drop_fy2021"]["outcomes"][
        "strict_computing_dollars_per_case_month"
    ]["effect"]
    ky_effect = ky["specifications"]["primary_exclude_fy2016_drop_fy2021"]["outcomes"][
        "strict_computing_dollars_per_case_month"
    ]["effect"]
    assert f"${ri_effect:.2f}" == "$2.90" and "$2.90" in html
    assert f"${abs(ky_effect):.2f}" == "$0.58" and "$0.58" in html
    assert f"{ri['decision']['strict_p_value']:.3f}" == "0.023" and "p = 0.023" in html
    assert f"{ky['decision']['strict_p_value']:.2f}" == "0.30" and "p = 0.30" in html
    pooled = riky["pooled"]["decision"]["strict_p_value"]
    assert f"{pooled:.3f}" == "0.093" and "p = 0.093" in html
    assert riky["units"]["RI"]["decision"]["verdict"] == "signal"
    assert riky["units"]["KY"]["decision"]["verdict"] == "no_protocol_defined_signal"
    oregon = json.loads(OREGON.read_bytes())
    assert oregon["decision"]["verdict"] == "no_protocol_defined_signal"
    assert oregon["decision"]["client_placebo_p_value"] < 0.10
    billed = json.dumps(json.loads(MIGRATIONS.read_bytes()))
    assert "37,343,809" in billed and "$37.3M" in html


def test_events_section_language_discipline() -> None:
    html = _events_html()
    assert "bundled system replacements as implemented" in html
    assert "the effect of a rules engine" in html  # inside the never-quote
    assert "verdict-inert" in html
    assert "causal" not in html.lower()


def test_interventions_section_copy_and_language_discipline() -> None:
    html = INDEX.read_text()
    match = re.search(
        r'<section class="chart-card" id="interventions">.*?</section>',
        html,
        re.DOTALL,
    )
    assert match, "interventions section missing from index.html"
    section = match.group(0)
    assert "Targeted review scenarios" in section
    assert (
        "Cut counted error dollars by a chosen amount inside a targeted group of "
        "cases, and see what the measured rate, the tier odds, and the expected "
        "bill do. An accounting construction: it prices the arithmetic of a "
        "smaller error pool, not any claim about how a state achieves it."
    ) in section
    assert "Oracle ranks by each case's actual recorded error" in section
    assert "If the cut persists, FY 2028–30" in section
    assert "Sustained-intervention construction: the same rate delta applied" in section
    assert "causal" not in section.lower()
