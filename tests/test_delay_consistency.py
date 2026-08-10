"""The app's delay test must agree with the movement analysis roster.

7 U.S.C. 2013(a)(2)(B)(iii): a year whose payment error rate times 1.5
reaches 20% delays the state's first billed year. The app applies the test
in JS (delayMet); analysis/fy2025_movement.py applies it in Python. Both
consume the same published FY2025 rates, so the implied FY2025 delay roster
must match exactly.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_fy2025_delay_roster_matches_movement_artifact():
    data = json.loads((ROOT / "app/public/data.json").read_text())
    movement = json.loads((ROOT / "analysis/fy2025_movement.json").read_text())

    app_roster = sorted(
        code
        for code, st in data["states"].items()
        if st["official_fy2025"] * 1.5 >= 20
    )
    assert app_roster == sorted(movement["aggregates"]["delay_fy2025_states"])


def test_app_js_encodes_the_statutory_test():
    js = (ROOT / "app/public/app.js").read_text()
    assert "const delayMet = (rate) => rate * 1.5 >= 20;" in js
    assert "DELAY_THRESHOLD = 20 / 1.5" in js
    # The FY2029 bill keys to the FY2026 draw and zeroes when it crosses.
    assert re.search(r"bill29 \+= crossed \? 0 :", js)
