"""Lock the state-first front page: section order, copy tied to artifacts,
retired jargon, and the pure formatting helpers in app.js."""

import json
import math
import re
import shutil
import subprocess
from itertools import pairwise
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "app" / "public"
INDEX = PUBLIC / "index.html"
APP = PUBLIC / "app.js"
MOVEMENT = ROOT / "analysis" / "fy2025_movement.json"
FY27 = PUBLIC / "fy2027_data.json"


def _app_text() -> str:
    """app.js with comments removed, so locks apply to what readers see."""
    src = re.sub(r"/\*.*?\*/", "", APP.read_text(), flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def test_answer_leads_then_table_then_fy2027_then_analyst() -> None:
    html = INDEX.read_text()
    order = [
        html.index('<section class="answer" id="answer"'),
        html.index('<section class="chart-card" id="national">'),
        html.index('<section class="chart-card" id="fy2027">'),
        html.index('<details class="analyst" id="analyst">'),
    ]
    assert order == sorted(order)


def test_research_controls_sit_inside_the_collapsed_analyst_section() -> None:
    html = INDEX.read_text()
    match = re.search(
        r'<details class="analyst" id="analyst">(.*?)</details>', html, re.DOTALL
    )
    assert match, "analyst section missing"
    assert "<details class=\"analyst\" id=\"analyst\" open" not in html
    inner = match.group(1)
    for control in (
        'id="interventions"',  # targeted review
        'id="lever-smd"',  # the model scenario
        'id="lever-engine-cut"',
        'id="engine-mode"',
        'id="lever-drift"',  # the drift band
        'id="adoption"',  # rules-engine adoption panel
        'id="audits"',
    ):
        assert control in inner, control


def test_colorado_is_the_default_state() -> None:
    assert 'sel.value = "CO"' in APP.read_text()


def test_tier_change_copy_matches_movement_artifact() -> None:
    agg = json.loads(MOVEMENT.read_bytes())["aggregates"]
    flips = agg["tier_flip_count"]
    flipped = {f.split()[0] for f in agg["tier_flips"]}
    beyond = set(agg["beyond_two_year_noise_95_states"])
    inside = len(flipped - beyond)
    assert (flips, inside, len(beyond), len(beyond & flipped)) == (18, 11, 10, 7)
    js, html = _app_text(), INDEX.read_text()
    assert (
        f"{flips} jurisdictions changed tiers, and {inside} of those {flips} "
        "changes sit inside the two-year sampling-noise band."
    ) in js
    assert (
        f"{flips} of {agg['jurisdictions']} jurisdictions changed cost-share tiers"
    ) in html
    assert (
        f"{inside} of those {flips} changes sit inside the two-year "
        "sampling-noise 95% band"
    ) in html
    assert "Ten jurisdictions moved beyond the band, seven of them changing tiers" in html
    # The retired framing contrasted 18 with 10, two counts of different things.
    assert "only 10 moved" not in js + html


def test_drift_label_matches_the_drift_the_app_draws() -> None:
    tau = json.loads(FY27.read_bytes())["drift_tau_pp"]["robust"]
    assert f"{tau:.2f}" == "1.07"
    assert "Add year-to-year drift (1.07 points)" in INDEX.read_text()
    assert "a 1.07-point standard deviation" in _app_text()


def test_fy2026_is_past_tense() -> None:
    text = INDEX.read_text() + _app_text()
    assert "being measured through September 30, 2026" not in text
    assert "FY 2026's sample period ended September 30, 2026" in text


def test_fy2027_parameters_are_the_published_values() -> None:
    """The FY 2027 panel quotes FNA's August 21, 2026 COLA notice and the
    tolerance computed from the published June 2026 Thrifty Food Plan cost,
    and flags the repricing as provisional while its artifact still carries
    the pre-publication projection."""
    helpers = _run_helpers(
        [["FY27_MAX_4P_PUBLISHED"], ["FY27_TFP_JUNE_2026"], ["FY27_TOLERANCE_PUBLISHED"]]
    )
    max4, tfp, tol = helpers
    assert max4 == 1023 and tfp == 1023.2
    # floor(37 × June TFP / 632.30), 7 USC 2025(c)(1)(A)(ii); the FY 2026
    # threshold in the artifact (58, from June 2025's $994.40) checks the rule.
    assert tol == math.floor(37 * tfp / 632.30) == 59
    fy27 = json.loads(FY27.read_bytes())
    assert math.floor(37 * float(fy27["thresholds"]["2026"]["reference_family_monthly_cost"]) / 632.30) == 58
    js = _app_text()
    assert "Under OBBBA §10101, FY 2027 maximum allotments index by June-to-June CPI-U" not in js
    assert "until FNA's official notice" not in js
    assert "hardens when USDA publishes" not in js
    if fy27["fy2027_max_allotment_4p_48dc"]["dollars"] != max4:
        assert "so this range is provisional until it is rerun on the published values" in js


@pytest.mark.parametrize(
    "phrase",
    [
        "τ",
        "oracle bound",
        "persistence-anchored",
        "deviation-carry",
        "file-rate delta",
        "stage by stage",
    ],
)
def test_retired_jargon_is_absent_from_reader_copy(phrase: str) -> None:
    text = (INDEX.read_text() + _app_text()).lower()
    assert phrase.lower() not in text


def test_no_certification_claim_in_reader_copy() -> None:
    # "certified" survives only as the provenance payload's key name.
    text = INDEX.read_text() + _app_text()
    assert not re.search(r"(?<![.\w])certifi", text, re.IGNORECASE)


def test_axiom_parity_copy_says_eligibility_is_untested() -> None:
    html, js = INDEX.read_text(), _app_text()
    assert "eligibility is untested" in html
    assert "leaves eligibility untested" in html
    assert js.count("eligibility untested") >= 3  # table mark, engine panel, CTA


def test_file_rate_is_defined_where_the_analyst_tools_begin() -> None:
    html = INDEX.read_text()
    analyst = html.index('<details class="analyst" id="analyst">')
    definition = html.index(
        "the <strong>file rate</strong> is the error rate computed directly from "
        "the public QC case file"
    )
    assert analyst < definition
    # No earlier mention: the definition is the term's first appearance.
    assert html.lower().index("file rate") == definition + len("the <strong>")


# ---- Pure helpers, executed in node --------------------------------------
#
# The prelude of app.js (everything before the first `let DATA`) declares
# constants and pure functions only; node evaluates it and returns each
# helper's output for a batch of inputs.

HELPERS = (
    "fmtWords",
    "fmtChance",
    "quantile",
    "tickStep",
    "textW",
    "edgeLabel",
    "FY27_MAX_4P_PUBLISHED",
    "FY27_TFP_JUNE_2026",
    "FY27_TOLERANCE_PUBLISHED",
)


def _run_helpers(calls: list[list]) -> list:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    src = APP.read_text()
    prelude = src[: src.index("let DATA = null;")]
    harness = (
        "globalThis.window = {};\n"
        + prelude
        + f"\nconst H = {{{', '.join(HELPERS)}}};\n"
        + "const calls = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
        + "const call = ([f, ...a]) => (typeof H[f] === 'function' ? H[f](...a) : H[f]);\n"
        + "process.stdout.write(JSON.stringify(calls.map(call)));\n"
    )
    out = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(calls),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def _parse_words(s: str) -> float:
    if s == "$0":
        return 0.0
    m = re.fullmatch(r"\$(\d+(?:\.\d+)?) (million|billion)", s)
    assert m, s
    return float(m.group(1)) * (1e6 if m.group(2) == "million" else 1e9)


@settings(max_examples=5, deadline=None)
@given(
    st.lists(
        st.one_of(
            st.floats(0, 5e9, allow_nan=False),
            st.sampled_from([0.0, 1.0, 0.49e6, 0.5e6, 999.4e6, 999.5e6, 999.6e6, 1e9]),
        ),
        min_size=50,
        max_size=200,
    )
)
def test_fmt_words_never_prints_a_thousand_million(values: list[float]) -> None:
    for v, s in zip(values, _run_helpers([["fmtWords", v] for v in values])):
        if s == "under $1 million":
            assert 0 < v < 0.5e6
            continue
        assert "1000 million" not in s
        parsed = _parse_words(s)
        tol = 0.5e6 if s.endswith("million") or s == "$0" else 0.005e9
        assert abs(parsed - v) <= tol + 1e-6 * v, (v, s)
        if s.endswith("million"):
            assert 1 <= parsed / 1e6 <= 999


@settings(max_examples=5, deadline=None)
@given(
    st.lists(
        st.one_of(
            st.floats(0, 1, allow_nan=False),
            st.sampled_from([0.0, 0.0049, 0.005, 0.5, 0.9949, 0.995, 0.9951, 1.0]),
        ),
        min_size=50,
        max_size=200,
    )
)
def test_fmt_chance_never_claims_certainty(ps: list[float]) -> None:
    for p, s in zip(ps, _run_helpers([["fmtChance", p] for p in ps])):
        if s == "less than 1%":
            assert p < 0.005 + 1e-12
        elif s == "more than 99%":
            assert p >= 0.995 - 1e-12
        else:
            k = int(s.rstrip("%"))
            assert 1 <= k <= 99 and abs(k - 100 * p) <= 0.5 + 1e-9, (p, s)


@settings(max_examples=5, deadline=None)
@given(
    st.lists(st.floats(-50, 50, allow_nan=False), min_size=1, max_size=60),
    st.lists(st.floats(0, 1, allow_nan=False), min_size=2, max_size=12),
)
def test_quantile_is_bounded_and_monotone(draws: list[float], qs: list[float]) -> None:
    qs = sorted(qs)
    out = _run_helpers([["quantile", draws, q] for q in qs])
    assert all(min(draws) <= v <= max(draws) for v in out)
    assert all(a <= b + 1e-12 for a, b in pairwise(out))


@settings(max_examples=5, deadline=None)
@given(
    st.lists(
        st.tuples(st.floats(1, 40), st.floats(120, 1400)), min_size=20, max_size=80
    )
)
def test_tick_step_keeps_labels_apart(cases: list[tuple[float, float]]) -> None:
    steps = _run_helpers([["tickStep", span, px] for span, px in cases])
    for (span, px), d in zip(cases, steps):
        assert d in (1, 2, 4, 5, 10)
        fits = [c for c in (1, 2, 4, 5, 10) if px * c / span >= 30]
        # The smallest step that keeps ticks 30px apart, or the widest one.
        assert d == (fits[0] if fits else 10)


@settings(max_examples=5, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.floats(0, 1400),
            st.text(alphabet="FY0123456789.% official", min_size=1, max_size=24),
            st.floats(300, 1400),
        ),
        min_size=20,
        max_size=80,
    )
)
def test_edge_label_stays_inside_the_right_edge(
    cases: list[tuple[float, str, float]],
) -> None:
    cases = [(x, s, w) for x, s, w in cases if x <= w]
    if not cases:
        return
    calls = [["edgeLabel", x, s, 10, w] for x, s, w in cases]
    widths = _run_helpers([["textW", s, 10] for _, s, _ in cases])
    for (x, _s, w), tw, attrs in zip(cases, widths, _run_helpers(calls)):
        if 'text-anchor="end"' in attrs:
            assert float(re.search(r'x="([^"]+)"', attrs).group(1)) == pytest.approx(x - 4)
        else:
            assert x + 4 + tw <= w - 2
