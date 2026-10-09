"""flightlist.py: FlightList date-range results (card text) to run_log rows.

The fixture holds six cards from one live range search (2026-10-09): ZRH-GIG, departures
18-22 Dec, returns 10-14 Jan, CHF, one checked bag, sorted by price."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.run_log_helpers import ROOT, contract, cli, write_json

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


@pytest.fixture
def run(tmp_path):
    c = contract(run_id="fl1", origins=["ZRH"], destinations=["GIG"],
                 dates={"pairs": [["2026-12-22", "2027-01-12"], ["2026-12-21", "2027-01-14"],
                                  ["2026-12-19", "2027-01-11"], ["2026-12-18", "2027-01-10"]]},
                 max_duration={"value": "20:00:00", "strict": False}, self_transfer_ok=True)
    assert cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs").returncode == 0
    return tmp_path / "runs" / "fl1"


def test_rows_keep_the_cheapest_card_per_pair_and_a_cheaper_over_cap_one(run):
    r = subprocess.run([sys.executable, "-B", str(FL), "rows", "--run", str(run), str(CARDS)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert [(x["outbound_date"], x["tickets"][0]["price"]) for x in rows] == [  # the run's pair order
        ("2026-12-19", 2886.0), ("2026-12-21", 1831.46), ("2026-12-21", 2205.0), ("2026-12-22", 1750.91)]
    assert "no card for 2026-12-18_2027-01-10" in r.stderr
    added = cli("add", "--run", run, "--row", "-", input=r.stdout)
    assert added.returncode == 0
    assert [line.split()[1].rstrip(":") for line in added.stdout.splitlines()] == \
        ["lead", "rejected", "lead", "lead"]  # 1831.46 is 50h05 out


def test_rows_are_list_fares_with_both_directions(run):
    rows = json.loads(subprocess.run([sys.executable, "-B", str(FL), "rows", "--run", str(run), str(CARDS)],
                                     capture_output=True, text=True).stdout)
    first = next(x for x in rows if x["outbound_date"] == "2026-12-22")
    assert (first["source"], first["family"], first["return_date"]) == ("flightlist", "kiwi", "2027-01-12")
    assert first["tickets"][0]["quote_state"] == "list" and first["tickets"][0]["baggage"] == "unverified"
    assert [d["dir"] for d in first["directions"]] == ["out", "ret"]


def test_overnight_last_segment_arrives_the_next_day():
    out = flightlist.parse_card(cards()[3])["directions"][0]  # TAP ZRH-LIS, then GOL LIS 23:30 -> GIG 06:30
    assert (out["dep"], out["arr"], out["duration"]) == ("2026-12-21T18:00:00", "2026-12-22T06:30:00", "16:30:00")
