"""flightlist.py: FlightList date-range results (card text) to run_log rows.

The fixture holds six cards from one live range search (2026-10-09): ZRH-GIG, departures
18-22 Dec, returns 10-14 Jan, CHF, one checked bag, sorted by price."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.run_log_helpers import ROOT, contract_v3, leg, group, cli, write_json

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import flightlist  # noqa: E402

FL = ROOT / "skill" / "scripts" / "flightlist.py"
CARDS = Path(__file__).parent / "fixtures" / "flightlist" / "range_cards.json"


def cards():
    return json.loads(CARDS.read_text(encoding="utf-8"))


def test_card_reads_both_directions_from_the_segment_details():
    card = flightlist.parse_card(cards()[0])
    assert (card["price"], card["currency"]) == (1750.91, "CHF")
    out, ret = card["directions"]
    assert {k: out[k] for k in ("from", "to", "dep", "arr", "duration", "stops", "airlines", "flights")} == {
        "from": "ZRH", "to": "GIG", "dep": "2026-12-22T06:50:00", "arr": "2026-12-22T18:40:00",
        "duration": "15:50:00", "stops": 1, "airlines": ["KLM Royal Dutch Airlines"], "flights": ["KL 1916", "KL 705"]}
    assert {k: ret[k] for k in ("from", "to", "dep", "arr", "duration", "flights")} == {
        "from": "GIG", "to": "ZRH", "dep": "2027-01-12T20:45:00", "arr": "2027-01-13T16:45:00",
        "duration": "16:00:00", "flights": ["KL 706", "KL 1923"]}


def test_unrelated_carriers_are_flagged_as_a_possible_self_transfer():
    out = flightlist.parse_card(cards()[2])["directions"][0]
    assert out["airlines"][:2] == ["easyJet", "Wizz Air Malta"] and out["mixed_carriers"] is True
    assert flightlist.parse_card(cards()[0])["directions"][0]["mixed_carriers"] is False


def test_airport_change_between_segments_is_detected():
    text = cards()[2]["text"].replace("from Rome (FCO)", "from Rome (CIA)")
    assert flightlist.parse_card({"price": "1831.46", "text": text})["directions"][0]["airport_change"] is True
    assert flightlist.parse_card(cards()[2])["directions"][0]["airport_change"] is False


def fl_contract(**over):
    """The fixture's window as a v3 contract: out 18-22 Dec, trip length 21-24 days (20 tuples)."""
    c = contract_v3(run_id="fl1", max_duration={"value": "20:00:00", "strict": False}, self_transfer_ok=True, **over)
    c["legs"] = [leg("ZRH", "GIG", {"range": {"from": "2026-12-18", "to": "2026-12-22"}}),
                 leg("to:1", "from:1", {"after_leg": {"leg": 1, "min_days": 21, "max_days": 24}})]
    return c


@pytest.fixture
def run(tmp_path):
    r = cli("init", "--contract", write_json(tmp_path / "c.json", fl_contract()), "--runs-root", tmp_path / "runs")
    assert r.returncode == 0, r.stderr
    return tmp_path / "runs" / "fl1"


def rows_cli(run, *extra):
    return subprocess.run([sys.executable, "-B", str(FL), "rows", "--run", str(run), *extra, str(CARDS)],
                          capture_output=True, text=True)


def test_rows_keep_the_cheapest_card_per_tuple_and_a_cheaper_over_cap_one(run):
    r = rows_cli(run)
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert [(x["dates"][0], x["tickets"][0]["price"]) for x in rows] == [  # the run's tuple order
        ("2026-12-19", 2886.0), ("2026-12-21", 1831.46), ("2026-12-21", 2205.0), ("2026-12-22", 1750.91)]
    assert "no card for 2026-12-18_2027-01-10" in r.stderr and "4 rows for 3 date tuple(s)" in r.stderr
    added = cli("add", "--run", run, "--row", "-", input=r.stdout)
    assert added.returncode == 0, added.stderr
    assert [line.split()[1].rstrip(":") for line in added.stdout.splitlines()] == \
        ["lead", "rejected", "lead", "lead"]  # 1831.46 is 50h05 out


def test_rows_are_discover_list_fares_with_both_legs(run):
    rows = json.loads(rows_cli(run).stdout)
    first = next(x for x in rows if x["dates"][0] == "2026-12-22")
    assert (first["source"], first["family"], first["phase"], first["dates"]) == \
        ("flightlist", "kiwi", "discover", ["2026-12-22", "2027-01-12"])
    assert (first["origin"], first["destination"]) == ("ZRH", "GIG")
    assert first["tickets"][0]["quote_state"] == "list" and first["tickets"][0]["baggage"] == "unverified"
    assert [(l["leg"], l["part"], l["from"], l["to"]) for l in first["legs"]] == [(1, 1, "ZRH", "GIG"), (2, 1, "GIG", "ZRH")]
    assert first["cabin"] == "economy" and first["engine"] == "browser"
    rows = json.loads(rows_cli(run, "--phase", "exact", "--engine", "browser-act-stealth").stdout)
    assert rows[0]["phase"] == "exact" and rows[0]["engine"] == "browser-act-stealth"


def test_parse_accepts_24h_clocks_nonstop_and_apostrophe_thousands():
    text = ("CHF1'234.50 06:50 - 18:40 Tue Dec 22nd 2026 15h 50m Zürich (ZRH) → Rio de Janeiro (GIG) Nonstop "
            "20:45 - 16:45 Tue Jan 12th 2027 16h 0m Rio de Janeiro (GIG) → Zürich (ZRH) Direct "
            "Tue Dec 22nd 2026 Example Air · EX 1 Depart at 06:50 from Zürich (ZRH) Fly for 11h 50m "
            "Arrive at 18:40 in Rio de Janeiro (GIG) Stay in Rio de Janeiro for 21 nights "
            "Tue Jan 12th 2027 Example Air · EX 2 Depart at 20:45 from Rio de Janeiro (GIG) Fly for 16h 0m "
            "Arrive at 16:45 in Zürich (ZRH)")
    card = flightlist.parse_card({"price": "CHF1'234.50", "text": text})
    assert card["price"] == 1234.5 and card["directions"][0]["stops"] == 0 and card["directions"][1]["stops"] == 0
    assert card["directions"][0]["dep"] == "2026-12-22T06:50:00" and card["directions"][1]["arr"] == "2027-01-13T16:45:00"


# sweep (session injected) -------------------------------------------------------------

class FakeSession:
    """Records every call; answers eval() the way the FlightList page would after each step."""

    def __init__(self, cards_json, blocked=False):
        self.cards_json = cards_json
        self.blocked = blocked
        self.calls = []
        self.name = "ffr-flightlist-1"

    def navigate(self, url):
        self.calls.append(("navigate", url))

    def run(self, *args):
        self.calls.append(("run",) + args)
        return "ok"

    def read_markdown(self):
        return "Are you a robot?" if self.blocked else "FlightList\n"

    def eval(self, js):
        self.calls.append(("eval", js))
        if "#from-data" in js:
            return "airport:ZRH"
        if "#to-data" in js:
            return "airport:GIG"
        if "startDate" in js and "endDate" in js:
            return "2026-12-18|2026-12-22|2027-01-08|2027-01-15"
        if "li.flight" in js and "JSON.stringify" in js:
            return self.cards_json
        if "li.flight" in js:
            return "6"
        return "ok"


def test_sweep_drives_form_and_records_rows(run):
    fake = FakeSession(CARDS.read_text(encoding="utf-8"))
    summary = flightlist.sweep(str(run), fake, cabin="economy", origins=["ZRH"], destination="GIG",
                               sleep=lambda n: None, engine="browser-act-stealth")
    assert summary["searches"] == 1 and summary["rows"] == 4 and summary["stopped"] is None
    assert summary["missing"][0] == "2026-12-18_2027-01-08" and len(summary["missing"]) == 17
    kinds = [c[0] if c[0] != "run" else c[1] for c in fake.calls]
    assert kinds[0] == "navigate" and fake.calls[0][1] == "https://www.flightlist.io/"
    assert fake.calls[1][:3] == ("run", "input", "--selector") and "ZRH" in fake.calls[1]
    text = " ".join(str(c) for c in fake.calls)
    assert text.index("#from-data") < text.index("#to") < text.index("#to-data") < text.index("setStartDate")
    assert text.index("setStartDate") < text.index("#checkedbags") < text.index("#submit") < text.index("JSON.stringify")
    assert "new Date(2026, 11, 18)" in text and "new Date(2027, 0, 8)" in text and "new Date(2027, 0, 15)" in text
    assert "'#class'" in text or '"#class"' in text or "#class" in text
    rows = [json.loads(line) for line in (run / "rows.jsonl").read_text().splitlines()]
    assert len(rows) == 4 and rows[0]["engine"] == "browser-act-stealth" and rows[0]["phase"] == "discover"


def test_sweep_one_search_per_origin_airport(run):
    fake = FakeSession(CARDS.read_text(encoding="utf-8"))
    summary = flightlist.sweep(str(run), fake, cabin="economy", origins=["ZRH", "BSL"], destination="GIG",
                               sleep=lambda n: None)
    assert summary["searches"] == 2 and [c for c in fake.calls if c[0] == "navigate"] == [("navigate", "https://www.flightlist.io/")] * 2


def test_sweep_stops_on_a_challenge(run):
    fake = FakeSession(CARDS.read_text(encoding="utf-8"), blocked=True)
    summary = flightlist.sweep(str(run), fake, cabin="economy", origins=["ZRH"], destination="GIG",
                               sleep=lambda n: None, on_challenge=lambda s: "blocked")
    assert summary["stopped"] == "challenge" and summary["rows"] == 0
    rows = [json.loads(line) for line in (run / "rows.jsonl").read_text().splitlines()]
    assert rows[0]["outcome"] == "blocked" and rows[0]["source"] == "flightlist"


def test_cli_sweep_needs_a_session_the_agent_opened(tmp_path):
    r = subprocess.run([sys.executable, "-B", str(FL), "sweep", "--run", str(tmp_path), "--cabin", "economy",
                        "--from", "ZRH", "--to", "GIG"], capture_output=True, text=True)
    assert r.returncode == 2 and "--session" in r.stderr


def test_overnight_last_segment_arrives_the_next_day():
    out = flightlist.parse_card(cards()[3])["directions"][0]  # TAP ZRH-LIS, then GOL LIS 23:30 -> GIG 06:30
    assert (out["dep"], out["arr"], out["duration"]) == ("2026-12-21T18:00:00", "2026-12-22T06:30:00", "16:30:00")


# review fix: one-way cards and contracts --------------------------------------------

ONE_WAY = ("CHF948 6:50am - 6:40pm Tue Dec 22nd 2026 15h 50m Zürich (ZRH) → Rio de Janeiro (GIG) 1 Stop "
           "Tue Dec 22nd 2026 KLM Royal Dutch Airlines · KL 1916 Depart at 6:50am from Zürich (ZRH) Fly for 1h 35m "
           "Arrive at 8:25am in Amsterdam (AMS) Layover in Amsterdam for 2h 15m Tue Dec 22nd 2026 KLM Royal Dutch Airlines "
           "· KL 705 Depart at 10:40am from Amsterdam (AMS) Fly for 12h 0m Arrive at 6:40pm in Rio de Janeiro (GIG)")


def test_parse_card_reads_a_one_way_card():
    card = flightlist.parse_card({"price": "CHF948", "text": ONE_WAY, "book": None})
    assert card["price"] == 948.0 and len(card["directions"]) == 1
    assert card["directions"][0]["flights"] == ["KL 1916", "KL 705"] and card["directions"][0]["arr"] == "2026-12-22T18:40:00"


def test_rows_for_one_way_contract_emit_one_leg(tmp_path):
    c = contract_v3(run_id="ow"); c["legs"] = [leg("ZRH", "GIG", {"range": {"from": "2026-12-21", "to": "2026-12-23"}})]
    r = cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs")
    assert r.returncode == 0, r.stderr
    run = tmp_path / "runs" / "ow"
    cards = write_json(tmp_path / "cards.json", [{"price": "CHF948", "text": ONE_WAY, "book": None}])
    r = subprocess.run([sys.executable, "-B", str(FL), "rows", "--run", str(run), str(cards)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert len(rows) == 1 and rows[0]["dates"] == ["2026-12-22"] and [l["leg"] for l in rows[0]["legs"]] == [1]
    assert "no card for 2026-12-21" in r.stderr
    assert cli("add", "--run", run, "--row", "-", input=r.stdout).returncode == 0
