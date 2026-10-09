"""2.1 changes found by the ZRH-GIG live test run: batch add, readable rank, grouped warnings."""
import json

import pytest

from tests.run_log_helpers import run_log, contract, row, ticket, direction, records, cli, write_json


@pytest.fixture
def run(tmp_path):
    assert cli("init", "--contract", write_json(tmp_path / "c.json", contract()),
               "--runs-root", tmp_path / "runs").returncode == 0
    return tmp_path / "runs" / "t1"


def saved(run):
    return [json.loads(line) for line in (run / "rows.jsonl").read_text().splitlines()]


# batch add: a sweep records dozens of observations in one call ---------------------

def test_add_accepts_a_json_array(run):
    lead = row(tickets=[ticket(price=300.0, quote_state="list")])
    r = cli("add", "--run", run, "--row", "-", input=json.dumps([row(), lead]))
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["r1 qualified", "r2 lead: list fare not repriced"]
    assert [x["id"] for x in saved(run)] == ["r1", "r2"]


def test_add_accepts_json_lines(run):
    text = json.dumps(row()) + "\n" + json.dumps(row(cabin_label="Economy Light")) + "\n"
    r = cli("add", "--run", run, "--row", "-", input=text)
    assert r.returncode == 0 and len(saved(run)) == 2


def test_batch_add_saves_nothing_when_one_row_is_invalid(run):
    bad = row(directions=[direction("out", stops="1 stop"), direction("ret")])
    r = cli("add", "--run", run, "--row", "-", input=json.dumps([row(), bad]))
    assert r.returncode == 2 and "row 2" in r.stderr
    assert (run / "rows.jsonl").read_text() == ""


# check: one grouped warning per cabin instead of one line per cheaper lead ---------

def lead(price, **over):
    return row(family="edreams", source="edreams", tickets=[ticket(price=price, quote_state="list")], **over)


def test_one_cheaper_lead_gives_one_warning():
    result = run_log.check(contract(), records(row(), lead(250.0)))
    assert result["warn"] == ["economy: 1 lead may beat best qualified 400.00 CHF; cheapest: r2 LB 250.00"]


def test_cheaper_leads_are_grouped_cheapest_first():
    recs = records(row(), lead(250.0), lead(200.0), lead(260.0), lead(390.0), lead(300.0))
    assert run_log.check(contract(), recs)["warn"] == [
        "economy: 5 leads may beat best qualified 400.00 CHF; "
        "cheapest: r3 LB 200.00, r2 LB 250.00, r4 LB 260.00 (+2 more)"]


# mixed cabin worded by the seller (TAP: "Mixed Cabin") is still flagged ------------

def test_mixed_cabin_flag_from_seller_wording():
    r = row(cabin_label="Economy Prime (TAP: Mixed Cabin)")
    assert "mixed cabin: Economy Prime (TAP: Mixed Cabin)" in run_log.risk_flags(r, contract())


# rank shows what the report needs: dates, legs, seller, booking link --------------

def test_rank_json_carries_trip_details(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    entry = json.loads(cli("rank", "--run", run, "--json").stdout)["economy"]["qualified"][0]
    assert (entry["origin"], entry["destination"]) == ("AAA", "ZZZ")
    assert (entry["outbound_date"], entry["return_date"]) == ("2026-11-05", "2026-11-12")
    assert entry["providers"] == ["XX"]
    assert entry["legs"][0] == {"dir": "out", "from": "AAA", "to": "ZZZ", "dep": "2026-11-05T07:10:00",
                                "arr": "2026-11-05T09:05:00", "duration": "02:55:00", "stops": 0,
                                "airlines": ["XX"]}


def test_rank_text_shows_dates_legs_and_seller(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    text = cli("rank", "--run", run).stdout
    assert "AAA-ZZZ 2026-11-05/2026-11-12" in text
    assert "out 2026-11-05 07:10 -> 2026-11-05 09:05  02:55  0 stops  XX" in text
    assert "seller: XX  book: https://example.test/book" in text


def test_rank_top_limits_leads_listed(run, tmp_path):
    rows = [row()] + [lead(500.0 + n) for n in range(4)]
    cli("add", "--run", run, "--row", "-", input=json.dumps(rows))
    text = cli("rank", "--run", run, "--top", "2").stdout
    assert "r2 LB 500.00" in text and "r3 LB 501.00" in text and "r4 LB" not in text
    assert "(+2 more leads)" in text
