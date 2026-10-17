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
