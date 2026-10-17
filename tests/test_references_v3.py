"""The references and SKILL.md carry the 3.0 vocabulary and nothing of the 2.x one."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill"
REF = SKILL / "references"


def text(name):
    return (REF / name).read_text(encoding="utf-8")


INTAKE_ITEMS = ["Trip shape", "Origin airports", "Destination", "Dates per leg", "Travellers", "Cabins", "Bags",
                "Currency", "Journey-time limit", "Maximum stops", "time windows", "Airlines", "Route hacks",
                "Self-transfer", "Budget", "Speed mode", "Fixed event", "Browser"]


def test_intake_has_the_full_questionnaire_and_contract_v3():
    t = text("intake.md")
    for item in INTAKE_ITEMS:
        assert item.lower() in t.lower(), item
    assert len(re.findall(r"^(?:> )?\d{1,2}\. \*\*", t, re.M)) >= 18
    for token in ("speed", "shortlist", "after_leg", "\"legs\"", "\"via\": \"rail\"", "run_log.py init",
                  "run_log.py shortlist", "run_log.py confirm", "browseract.py status"):
        assert token in t, token


def test_browser_engines_describes_the_browseract_first_ladder():
    t = text("browser-engines.md")
    for token in ("browser-act-stealth", "auth login", "auth poll", "solve-captcha", "remote-assist",
                  "close --all-mine", "browseract.py status", "chrome-direct", "sessions_per_site", "ffr-"):
        assert token in t, token
    assert t.index("browser-act-stealth") < t.index("claude-in-chrome")


def test_discovery_reference_exists_and_names_the_commands():
    t = text("discovery.md")
    for token in ("run_log.py shortlist", "flightlist.py sweep", "gflights.py explore", "FlightConnections",
                  "BKK", "SIN", "KUL", "leads", "run_log.py confirm"):
        assert token in t, token


def test_qualification_uses_legs_and_ground_rows():
    t = text("qualification.md")
    for token in ("\"legs\"", "\"leg\": 1", "\"dates\"", "\"kind\": \"ground\"", "kiwi.py fare", "leg 2 not selected",
                  "ground unpriced"):
        assert token in t, token


def test_route_hacks_has_three_hacks_and_native_multicity():
    t = text("route-hacks.md")
    assert "`split`" in t and "`open_jaw`" in t and "`stopover`" in t and "multi-city" in t.lower()
    assert "\"part\": 2" in t


def test_recipes_and_ladder_point_at_the_new_scripts():
    assert "gflights.py sweep" in text("google-flights-browser.md") and "--tuples" in text("google-flights-browser.md")
    assert "flightlist.py sweep" in text("flightlist-browser.md")
    assert "google-explore" in text("source-ladder.md") and "discovery.md" in text("source-ladder.md")
    assert "browser-act-stealth" in text("source-health.md")


@pytest.mark.parametrize("token", ["nearby_origin", "alt_destination", "`directions`", "\"directions\"",
                                   "outbound_date", "return_date", "trip_type", "--pairs", "rail_ok",
                                   "browser-act-support.md", "lead-discovery.md"])
def test_no_2x_vocabulary_anywhere_in_the_skill(token):
    hits = [p.relative_to(SKILL).as_posix() for p in SKILL.rglob("*.md") if token in p.read_text(encoding="utf-8")]
    assert hits == [], f"{token} still in {hits}"


# SKILL.md 3.0.0 and the scenarios ------------------------------------------------------

def test_skill_md_carries_the_v3_workflow():
    t = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"^version: 3\.0\.0$", t, re.M)
    for token in ("browseract.py status", "references/discovery.md", "run_log.py jobs", "references/intake.md",
                  "run_log.py shortlist", "run_log.py confirm", "kiwi.py fare", "flightlist.py sweep",
                  "gflights.py sweep", "browser-act-stealth", "solve-captcha", "remote-assist", "multi-city",
                  "ground row", "Complete", "Incomplete:"):
        assert token in t, token
    for phase in ("## 0. Browser", "## 1. Intake", "## 2. Discovery", "## 3. Collect", "## 4. Route hacks",
                  "## 5. Qualify", "## 6. Cross-check and report"):
        assert phase in t, phase


def test_scenarios_for_v3_exist_with_pass_criteria():
    for name in ("04-unattended-captcha.md", "07-multicity-region.md", "08-full-questionnaire-just-go.md",
                 "09-no-browseract-login.md"):
        t = (ROOT / "tests" / "scenarios" / name).read_text(encoding="utf-8")
        assert "## Pass criteria" in t and "## Prompt" in t, name
    t = (ROOT / "tests" / "scenarios" / "04-unattended-captcha.md").read_text(encoding="utf-8")
    assert "solve-captcha" in t and "remote-assist" in t and "never buys" in t


def test_versions_agree_on_3_0_0():
    import json
    assert json.loads((ROOT / "integrations/claude-code/.claude-plugin/plugin.json").read_text())["version"] == "3.0.0"
    assert (ROOT / "CHANGELOG.md").read_text().split("\n")[2].startswith("## [3.0.0]")
    assert "browser-act-stealth" in (ROOT / "docs/safety-and-provenance.md").read_text()
