"""gflights.py: Google Flights URL builder, page parser and BrowserAct sweep.

URL literals are ones Google Flights accepted in the 2026-10-08 live run; page fixtures are
trimmed copies of pages read in that run (tests/fixtures/gflights)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.run_log_helpers import ROOT, contract, cli, write_json

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import gflights  # noqa: E402

GF = ROOT / "skill" / "scripts" / "gflights.py"
FIX = Path(__file__).parent / "fixtures" / "gflights"
BASE = "https://www.google.com/travel/flights/search?tfs="
NEARBY = "BSL+GVA+MXP+MUC+FRA"
CHALLENGE = "Our systems have detected unusual traffic from your computer network.\n"


def page(name):
    return (FIX / f"{name}.md").read_text(encoding="utf-8")


# URL builder ------------------------------------------------------------------------

@pytest.mark.parametrize("cabin,legs,tfs", [
    ("economy", ["ZRH-GIG@2026-12-22"], "Gh4SCjIwMjYtMTItMjJqBwgBEgNaUkhyBwgBEgNHSUdAAUgBmAEC"),
    ("business", ["GIG-ZRH@2027-01-11"], "Gh4SCjIwMjctMDEtMTFqBwgBEgNHSUdyBwgBEgNaUkhAAUgDmAEC"),
    ("premium", ["ZRH-GIG@2026-12-22", "GIG-ZRH@2027-01-12"],
     "Gh4SCjIwMjYtMTItMjJqBwgBEgNaUkhyBwgBEgNHSUcaHhIKMjAyNy0wMS0xMmoHCAESA0dJR3IHCAESA1pSSEABSAKYAQE"),
    ("first", ["ZRH-GIG@2026-12-22", "GIG-ZRH@2027-01-12"],
     "Gh4SCjIwMjYtMTItMjJqBwgBEgNaUkhyBwgBEgNHSUcaHhIKMjAyNy0wMS0xMmoHCAESA0dJR3IHCAESA1pSSEABSASYAQE"),
    ("economy", ["ZRH-GIG@2026-12-22", "GRU-ZRH@2027-01-12"],
     "Gh4SCjIwMjYtMTItMjJqBwgBEgNaUkhyBwgBEgNHSUcaHhIKMjAyNy0wMS0xMmoHCAESA0dSVXIHCAESA1pSSEABSAGYAQM"),
    ("economy", [f"{NEARBY}-GIG@2026-12-22", f"GIG-{NEARBY}@2027-01-12"],
     "GkISCjIwMjYtMTItMjJqBwgBEgNCU0xqBwgBEgNHVkFqBwgBEgNNWFBqBwgBEgNNVUNqBwgBEgNGUkFyBwgBEgNHSUcaQhIKMjAyNy0wMS0xMm"
     "oHCAESA0dJR3IHCAESA0JTTHIHCAESA0dWQXIHCAESA01YUHIHCAESA01VQ3IHCAESA0ZSQUABSAGYAQE"),
])
def test_url_matches_urls_google_accepted(cabin, legs, tfs):
    assert gflights.url(cabin, legs) == f"{BASE}{tfs}&curr=CHF&hl=en"


def test_url_encodes_each_traveller():
    import base64
    tfs = gflights.url("economy", ["ZRH-GIG@2026-12-22"], adults=2, children=1, infants=1).split("tfs=")[1].split("&")[0]
    raw = base64.urlsafe_b64decode(tfs + "=" * (-len(tfs) % 4))
    # field 8 (traveller) once per person: 1 adult, 2 child, 4 infant on lap; then cabin 1, one-way 2
    assert raw.endswith(b"\x40\x01\x40\x01\x40\x02\x40\x04\x48\x01\x98\x01\x02")


@pytest.mark.parametrize("cabin,legs", [
    ("economy", ["ZRH-GIG-2026-12-22"]),
    ("economy", ["ZRH-GIG@2026-13-40"]),
    ("economy", ["ZR-GIG@2026-12-22"]),
    ("coach", ["ZRH-GIG@2026-12-22"]),
    ("economy", []),
])
def test_url_refuses_bad_input(cabin, legs):
    with pytest.raises(ValueError):
        gflights.url(cabin, legs)


# page parser ------------------------------------------------------------------------

def test_parse_round_trip_page():
    out = gflights.parse(page("roundtrip_premium"), "2026-12-22")
    assert (out["state"], out["cabin"], out["departing"], out["returning"]) == \
        ("results", "premium", "2026-12-22", "2027-01-12")
    first = out["cards"][0]
    assert {k: first[k] for k in ("price", "currency", "dep", "arr", "duration", "stops", "airlines", "from",
                                  "to", "layovers", "cabin_label", "section")} == {
        "price": 2324.0, "currency": "CHF", "dep": "2026-12-22T06:30:00", "arr": "2026-12-22T18:30:00",
        "duration": "16:00:00", "stops": 1, "airlines": "Air France", "from": "ZRH", "to": "GIG",
        "layovers": ["CDG"], "cabin_label": "Economy + Premium Economy", "section": "Top departing flights"}
    overnight = out["cards"][2]
    assert (overnight["dep"], overnight["arr"], overnight["duration"], overnight["layovers"]) == \
        ("2026-12-22T19:50:00", "2026-12-23T06:10:00", "14:20:00", ["FRA"])


def test_parse_drops_the_duplicate_rendering():
    text = page("roundtrip_premium")
    assert len(gflights.parse(text + text, "2026-12-22")["cards"]) == len(gflights.parse(text, "2026-12-22")["cards"])


def test_parse_one_way_page():
    out = gflights.parse(page("oneway"), "2026-12-22")
    assert (out["cabin"], out["departing"], out["returning"]) == ("economy", "2026-12-22", None)
    assert out["cards"][0]["price"] == 948.0


def test_parse_multi_city_page_has_cards_but_no_track_line():
    out = gflights.parse(page("multicity"), "2026-12-22")
    assert out["departing"] is None and out["cards"][0]["price"] == 1497.0
    assert out["cards"][0]["section"] == "Top flights to Rio de Janeiro"
    assert {c["dep"][:10] for c in out["cards"]} == {"2026-12-22"}


def test_parse_multi_airport_page_reports_each_origin():
    cards = gflights.parse(page("multiairport"), "2026-12-22")["cards"]
    assert [(c["from"], c["airlines"], c["duration"]) for c in cards[:2]] == \
        [("MUC", "Air France", "15:25:00"), ("GVA", "KLM", "15:30:00")]


def test_parse_return_list_splits_the_operator():
    first = gflights.parse(page("return_list"), "2027-01-12")["cards"][0]
    assert {k: first[k] for k in ("dep", "arr", "duration", "stops", "airlines", "operated_by", "from", "to")} == {
        "dep": "2027-01-12T21:35:00", "arr": "2027-01-13T10:15:00", "duration": "09:40:00", "stops": 0,
        "airlines": "Gol", "operated_by": "Wamos for Gol", "from": "GIG", "to": "LIS"}


def test_january_cards_after_a_december_anchor_fall_in_the_next_year():
    first = gflights.parse(page("return_list"), "2026-12-22")["cards"][0]
    assert (first["dep"], first["arr"]) == ("2027-01-12T21:35:00", "2027-01-13T10:15:00")


@pytest.mark.parametrize("text,state", [
    (CHALLENGE, "challenge"),
    ("Flights\nRound trip\nNo results returned.\n", "empty"),
    ("Find Cheap Flights Worldwide & Book Your Ticket - Google Flights\nLoading results\n", "loading"),
])
def test_parse_page_states(text, state):
    out = gflights.parse(text, "2026-12-22")
    assert out["state"] == state and out["cards"] == []


# sweep (browser injected) -----------------------------------------------------------

class FakePage:
    """Stands in for the browser: each open() serves the next queued page texts in order."""

    def __init__(self, *texts_per_search):
        self.queue = [list(t) for t in texts_per_search]
        self.opened = []
        self.current = []

    def open(self, url):
        self.opened.append(url)
        self.current = self.queue.pop(0)

    def read(self):
        return self.current.pop(0) if len(self.current) > 1 else self.current[0]


@pytest.fixture
def run(tmp_path):
    c = contract(run_id="g1", origins=["ZRH"], destinations=["GIG"], cabins=["premium"],
                 dates={"pairs": [["2026-12-22", "2027-01-12"]]})
    assert cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs").returncode == 0
    return tmp_path / "runs" / "g1"


def saved(run):
    return [json.loads(line) for line in (run / "rows.jsonl").read_text().splitlines()]


def no_sleep(_seconds):
    pass


def test_sweep_records_the_cheapest_cards_as_list_leads(run):
    fake = FakePage([page("roundtrip_premium")])
    summary = gflights.sweep(str(run), fake, cabins=["premium"], sleep=no_sleep)
    rows = saved(run)
    assert summary["searches"] == 1 and summary["stopped"] is None
    assert [r["tickets"][0]["price"] for r in rows] == [2275.0, 2324.0, 2324.0, 2427.0]
    assert {r["tickets"][0]["quote_state"] for r in rows} == {"list"}
    assert [len(r["directions"]) for r in rows] == [1, 1, 1, 1]
    assert rows[1]["cabin_label"] == "Economy + Premium Economy" and rows[1]["url"] == fake.opened[0]
    rank = json.loads(cli("rank", "--run", run, "--json").stdout)["premium"]["leads"]
    assert [lead["id"] for lead in rank] == ["r2", "r3", "r4"]  # r1 is over the 20h cap: rejected


def test_sweep_waits_for_results_before_reading(run):
    fake = FakePage(["Google Flights\nLoading results\n", page("roundtrip_premium")])
    gflights.sweep(str(run), fake, cabins=["premium"], sleep=no_sleep)
    assert len(saved(run)) == 4


def test_sweep_stops_at_the_first_challenge(tmp_path):
    c = contract(run_id="g2", origins=["ZRH"], destinations=["GIG"], cabins=["premium"],
                 dates={"pairs": [["2026-12-22", "2027-01-12"], ["2026-12-22", "2027-01-13"]]})
    cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs")
    run = tmp_path / "runs" / "g2"
    fake = FakePage([CHALLENGE], [page("roundtrip_premium")])
    summary = gflights.sweep(str(run), fake, cabins=["premium"], sleep=no_sleep)
    assert summary["stopped"] == "challenge" and len(fake.opened) == 1
    assert [r["outcome"] for r in saved(run)] == ["blocked"]


def test_sweep_records_an_error_when_the_page_shows_another_search(tmp_path):
    c = contract(run_id="g3", origins=["ZRH"], destinations=["GIG"], cabins=["premium"],
                 dates={"pairs": [["2026-12-21", "2027-01-12"]]})
    cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs")
    run = tmp_path / "runs" / "g3"
    gflights.sweep(str(run), FakePage([page("roundtrip_premium")]), cabins=["premium"], sleep=no_sleep)
    rows = saved(run)
    assert [r["outcome"] for r in rows] == ["error"] and "2026-12-22" in rows[0]["notes"]


# command line -----------------------------------------------------------------------

def test_cli_url_and_parse():
    r = subprocess.run([sys.executable, "-B", str(GF), "url", "--cabin", "economy", "ZRH-GIG@2026-12-22"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert r.stdout.strip() == f"{BASE}Gh4SCjIwMjYtMTItMjJqBwgBEgNaUkhyBwgBEgNHSUdAAUgBmAEC&curr=CHF&hl=en"
    r = subprocess.run([sys.executable, "-B", str(GF), "parse", "--anchor", "2026-12-22", str(FIX / "oneway.md")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["cards"][0]["price"] == 948.0


def test_cli_bad_leg_exits_2():
    r = subprocess.run([sys.executable, "-B", str(GF), "url", "--cabin", "economy", "ZRH@2026-12-22"],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_cli_sweep_needs_a_session_the_agent_opened(tmp_path):
    # no default session name: an agent must not drive the user's session by accident
    r = subprocess.run([sys.executable, "-B", str(GF), "sweep", "--run", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 2 and "--session" in r.stderr
