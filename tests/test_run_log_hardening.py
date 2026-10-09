"""Regression tests for the 2.0 final-review findings (run_log.py)."""
import json
import subprocess
import sys

import pytest

from tests.run_log_helpers import SCRIPT, run_log, contract, row, ticket, direction, records, cli, write_json

POS = {"allowed": True, "rail_ok": True, "overnight_ok": False}


def full(**over):
    c = contract(scope="full", hacks=["split"], **over)
    c["date_pairs"] = run_log.expand_dates(c["dates"], c["trip_type"])
    c["cells"] = run_log.build_cells(c)
    return c


def quick(**over):
    c = contract(**over)
    c["date_pairs"] = run_log.expand_dates(c["dates"], c["trip_type"])
    c["cells"] = run_log.build_cells(c)
    return c


def attempt(outcome="blocked", family="edreams", **over):
    a = {"source": family, "family": family, "engine": "t", "outcome": outcome, "url": "https://e.test",
         "retrieved_at": "2026-10-08T10:00:00+00:00", "cabin": "economy", "hack": None, "origin": "AAA",
         "destination": "ZZZ", "outbound_date": "2026-11-05", "return_date": "2026-11-12"}
    a.update(over)
    return a


@pytest.fixture
def run(tmp_path):
    assert cli("init", "--contract", write_json(tmp_path / "c.json", contract()),
               "--runs-root", tmp_path / "runs").returncode == 0
    return tmp_path / "runs" / "t1"


# Critical 1: leads in another currency without fx are not comparable --------------

SEK_LEAD = dict(hack="split", currency="SEK", tickets=[ticket(price=2100.0, quote_state="list")])


def test_foreign_currency_lead_without_fx_is_never_pruned():
    lead = run_log.rank(contract(), records(row(), row(**SEK_LEAD)))["economy"]["leads"][0]
    assert lead["pruned"] is False


def test_foreign_currency_lead_keeps_hack_open_and_warns():
    result = run_log.check(full(), records(row(), row(**SEK_LEAD), attempt()))
    assert {"cell": "economy/hack/split", "why": "unresolved lead(s): r2"} in result["open"]
    assert "economy: lead r2 is priced in SEK without fx; not comparable with best qualified (400.00 CHF)" \
        in result["warn"]


def test_rank_text_shows_lead_currency(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", row(**SEK_LEAD)))
    assert "LB 2100.00 SEK" in cli("rank", "--run", run).stdout


# Important 1: nested fields validated; unexpected data never tracebacks ------------

@pytest.mark.parametrize("dirs", [
    [direction("out", stops="1 stop"), direction("ret")],
    ["out", "ret"],
    [dict(direction("out"), dir="outbound"), direction("ret")],
    [direction("out", airport_change="no"), direction("ret")],
    [direction("out", duration="3h"), direction("ret")],
])
def test_bad_directions_are_refused(dirs):
    assert run_log.validate_row(row(directions=dirs), contract()) != []


@pytest.mark.parametrize("over", [
    {"positioning": True},
    {"travelers": {"adults": 1, "children_ages": 7, "infants": 0}},
    {"travelers": {"adults": 1, "children_ages": [], "infants": "1"}},
    {"nearby_origins": "BBB"},
    {"self_transfer_ok": "no"},
    {"bags": {"checked_per_person": 1, "cabin_per_person": "yes"}},
])
def test_bad_optional_contract_fields_are_refused(over):
    assert run_log.validate_contract(contract(**over)) != []


def test_hand_edited_bad_row_exits_2_without_traceback(run):
    bad = dict(row(directions=[direction("out", stops="1 stop"), direction("ret")]), type="row", id="r1")
    (run / "rows.jsonl").write_text(json.dumps(bad) + "\n")
    r = cli("check", "--run", run)
    assert r.returncode == 2 and "Traceback" not in r.stderr


# Important 2: the run used is explicit; concurrent adds get unique ids -------------

def test_commands_report_the_run_they_used(run):
    r = cli("check", env={"FFR_RUNS": str(run.parent)})
    assert f"run: {run}" in r.stderr


def test_default_run_is_the_most_recently_used(tmp_path):
    runs = tmp_path / "runs"
    for rid in ("aaa", "bbb"):
        assert cli("init", "--contract", write_json(tmp_path / f"{rid}.json", contract(run_id=rid)),
                   "--runs-root", runs).returncode == 0
    cli("add", "--run", runs / "aaa", "--row", write_json(tmp_path / "r.json", row()))
    assert f"run: {runs / 'aaa'}" in cli("check", env={"FFR_RUNS": str(runs)}).stderr


def test_concurrent_adds_get_unique_ids(run, tmp_path):
    f = write_json(tmp_path / "r.json", row())
    procs = [subprocess.Popen([sys.executable, str(SCRIPT), "add", "--run", str(run), "--row", str(f)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(8)]
    for p in procs:
        p.wait()
    ids = [json.loads(line)["id"] for line in (run / "rows.jsonl").read_text().splitlines()]
    assert len(ids) == 8 and len(set(ids)) == 8


# Important 3: rows outside the contract are refused, with a hint for hacks ---------

@pytest.mark.parametrize("over,word", [
    ({"outbound_date": "2026-11-06"}, "dates"),
    ({"cabin": "business"}, "cabin"),
    ({"origin": "CCC"}, "origin"),
    ({"destination": "YYY"}, "destination"),
])
def test_add_refuses_rows_outside_the_contract(run, tmp_path, over, word):
    r = cli("add", "--run", run, "--row", write_json(tmp_path / "r.json", row(**over)))
    assert r.returncode == 2 and word in r.stderr and (run / "rows.jsonl").read_text() == ""


def test_split_recorded_as_a_one_way_row_gets_the_combination_hint(run, tmp_path):
    one_way = row(hack="split", return_date=None, directions=[direction("out")])
    r = cli("add", "--run", run, "--row", write_json(tmp_path / "r.json", one_way))
    assert r.returncode == 2 and "one row per combination" in r.stderr


# Important 4: resolve is guarded; blocked-only runs warn ---------------------------

def test_no_fare_needs_an_executed_search(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", attempt()))
    cell = "economy/baseline/AAA-ZZZ/2026-11-05_2026-11-12"
    r = cli("resolve", cell, "--as", "no_fare", "--reason", "x", "--run", run)
    assert r.returncode == 2 and "no_fare" in r.stderr
    cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", attempt(outcome="empty", family="google")))
    assert cli("resolve", cell, "--as", "no_fare", "--reason", "x", "--run", run).returncode == 0


def test_none_qualify_only_on_reprice_with_candidates(run, tmp_path):
    assert cli("resolve", "economy/reprice", "--as", "none_qualify", "--reason", "x", "--run", run).returncode == 2
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row(tickets=[ticket(quote_state="list")])))
    assert cli("resolve", "economy/crosscheck", "--as", "none_qualify", "--reason", "x", "--run", run).returncode == 2
    assert cli("resolve", "economy/reprice", "--as", "none_qualify", "--reason", "x", "--run", run).returncode == 0


def test_warns_when_no_family_returned_results():
    assert "economy: no source family returned results" in run_log.check(quick(), records(attempt()))["warn"]


def test_warns_when_cabin_has_leads_but_no_qualified_option():
    recs = records(row(tickets=[ticket(quote_state="list")])) + [
        {"type": "resolve", "cell": "economy/reprice", "as": "none_qualify", "reason": "x"}]
    assert "economy: no qualified option; 1 lead(s) unverified" in run_log.check(quick(), recs)["warn"]


# Important 5: requested comparisons never vanish -----------------------------------

def test_quick_scope_refuses_other_hacks():
    assert any("quick" in e for e in run_log.validate_contract(contract(hacks=["split"])))


def test_open_jaw_applies_with_several_primary_airports():
    cells = {c["id"]: c["auto"] for c in run_log.build_cells(contract(scope="full", destinations=["ZZZ", "YYY"]))}
    assert cells["economy/hack/open_jaw"] is None


def test_open_jaw_row_may_leave_from_a_nearby_origin():
    c = contract(scope="full", nearby_origins=["BBB"], positioning=POS)
    status, reasons = run_log.row_status(dict(row(hack="open_jaw", origin="BBB"), id="r1"), c, set())
    assert "origin not in contract" not in reasons


# Important 7: cabin bags are part of the contract and the gates --------------------

def test_cabin_bag_requested_keeps_unverified_rows_leads():
    c = contract(bags={"checked_per_person": 1, "cabin_per_person": 1})
    assert "cabin bag unverified" in run_log.row_status(dict(row(), id="r1"), c, set())[1]
    t = ticket(cabin_bag="fee_required", cabin_bag_fee=None)
    assert "cabin bag fee unknown" in run_log.row_status(dict(row(tickets=[t]), id="r1"), c, set())[1]


def test_cabin_bag_fee_is_in_the_all_in_total():
    c = contract(bags={"checked_per_person": 1, "cabin_per_person": 1})
    r = row(tickets=[ticket(cabin_bag="fee_required", cabin_bag_fee=30.0)])
    assert run_log.row_status(dict(r, id="r1"), c, set())[0] == "qualified"
    assert run_log.all_in(r, c) == 430.0


def test_no_cabin_bag_requested_ignores_cabin_bag_state():
    assert run_log.row_status(dict(row(), id="r1"), contract(), set())[0] == "qualified"


# Found by the post-fix scenario 03 run: a reprice that supersedes an aggregator row
# must not erase the aggregator's family from the cross-check.

def test_superseded_rows_still_count_as_attempted_families():
    google_list = row(tickets=[ticket(quote_state="list", baggage="unverified")])
    swiss_reprice = row(source="swiss-direct", family="swiss", supersedes="r1",
                        tickets=[ticket(price=868.4, quote_state="repriced")])
    result = run_log.check(quick(), records(google_list, swiss_reprice))
    assert result["complete"] is True
    assert not any("only one source family" in w for w in result["warn"])
