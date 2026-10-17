"""ffr_rows cell states, check and confirm picks (spec sections 3 and 4)."""
import sys

import pytest

from tests.run_log_helpers import ROOT, contract_v3, group, row_v3, leg_entry, ticket, records_v3

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import ffr_contract  # noqa: E402
import ffr_rows  # noqa: E402

BASE = "economy/baseline/ZRH-ZZZ/2027-02-03_2027-02-17"


def prepared(c=None):
    c = c or contract_v3()
    assert ffr_contract.validate_contract(c) == []
    n = ffr_contract.normalize_contract(c)
    n["date_tuples"] = ffr_contract.expand_tuples(n)
    n["cells"] = ffr_contract.build_cells(n)
    return n


def attempt(outcome="blocked", family="edreams", **over):
    a = {"source": family, "family": family, "engine": "t", "outcome": outcome, "url": "https://e.test",
         "retrieved_at": "2027-01-08T10:00:00+00:00", "cabin": "economy", "hack": None, "origin": "ZRH",
         "destination": "ZZZ", "dates": ["2027-02-03", "2027-02-17"]}
    a.update(over)
    return a


def lead(price, **over):
    return row_v3(family="edreams", source="edreams", tickets=[ticket(price=price, quote_state="list")], **over)


def open_items(c, recs):
    return {o["cell"]: o["why"] for o in ffr_rows.check(c, recs)["open"]}


def states(c, recs):
    return {s["id"]: s for s in ffr_rows.cell_states(c, recs)}


# thorough mode ---------------------------------------------------------------------

def test_nothing_attempted():
    assert open_items(prepared(), []) == {BASE: "not attempted", "economy/crosscheck": "0 source families attempted",
                                          "economy/reprice": "no qualified option"}


def test_blocked_only_cell_stays_open():
    assert open_items(prepared(), records_v3(attempt()))[BASE] == "only blocked/empty/error attempts"


def test_complete_run_with_single_family_warning_and_auto_resolutions():
    c = prepared(contract_v3(hacks={"split": True, "open_jaw": True, "stopover": False}))
    result = ffr_rows.check(c, records_v3(row_v3(), attempt()) + [
        {"type": "resolve", "cell": "economy/hack/split", "as": "no_fare", "reason": "no published fare returned"}])
    assert result["complete"] is True and result["open"] == []
    assert result["warn"] == ["economy: only one source family returned results (google)"]
    assert {"cell": "economy/hack/open_jaw", "why": "na: no other airport to open the jaw"} in result["resolved"]
    assert {"cell": "economy/hack/split", "why": "no_fare: no published fare returned"} in result["resolved"]


def test_hack_cell_open_while_lead_could_win_and_done_when_pruned_rejected_or_qualified():
    c = prepared(contract_v3(hacks={"split": True}))
    recs = records_v3(row_v3(), row_v3(hack="split", tickets=[ticket(price=300.0, quote_state="list")]), attempt())
    assert open_items(c, recs) == {"economy/hack/split": "unresolved lead(s): r2"}
    for hack_row in (row_v3(hack="split", tickets=[ticket(price=420.0, quote_state="list")]),
                     row_v3(hack="split", legs=[leg_entry(1, duration="23:00:00"), leg_entry(2)]),
                     row_v3(hack="split", tickets=[ticket(price=380.0)])):
        assert open_items(c, records_v3(row_v3(), hack_row, attempt())) == {}


def test_foreign_currency_lead_keeps_hack_open_and_warns():
    c = prepared(contract_v3(hacks={"split": True}))
    sek = row_v3(hack="split", currency="SEK", tickets=[ticket(price=2100.0, quote_state="list")])
    result = ffr_rows.check(c, records_v3(row_v3(), sek, attempt()))
    assert {"cell": "economy/hack/split", "why": "unresolved lead(s): r2"} in result["open"]
    assert "economy: lead r2 is priced in SEK without fx; not comparable with best qualified (400.00 CHF)" in result["warn"]


def test_check_warnings_ported():
    c = prepared()
    assert ffr_rows.check(c, records_v3(row_v3(), lead(250.0)))["warn"] == [
        "economy: 1 lead may beat best qualified 400.00 CHF; cheapest: r2 LB 250.00"]
    recs = records_v3(row_v3(), lead(250.0), lead(200.0), lead(260.0), lead(390.0), lead(300.0))
    assert ffr_rows.check(c, recs)["warn"] == [
        "economy: 5 leads may beat best qualified 400.00 CHF; cheapest: r3 LB 200.00, r2 LB 250.00, r4 LB 260.00 (+2 more)"]
    assert "economy: no source family returned results" in ffr_rows.check(c, records_v3(attempt()))["warn"]
    recs = records_v3(row_v3(tickets=[ticket(quote_state="list")])) + [
        {"type": "resolve", "cell": "economy/reprice", "as": "none_qualify", "reason": "x"}]
    assert "economy: no qualified option; 1 lead(s) unverified" in ffr_rows.check(c, recs)["warn"]


def test_superseded_rows_still_count_as_attempted_families():
    google_list = row_v3(tickets=[ticket(quote_state="list", baggage="unverified")])
    swiss = row_v3(source="swiss-direct", family="swiss", supersedes="r1", tickets=[ticket(price=868.4, quote_state="repriced")])
    result = ffr_rows.check(prepared(), records_v3(google_list, swiss))
    assert result["complete"] is True and not any("only one source family" in w for w in result["warn"])


def test_resolve_guard():
    c = prepared(contract_v3(hacks={"split": True}))
    cells = {x["id"]: x for x in c["cells"]}
    assert "executed search" in ffr_rows.resolve_guard(cells[BASE], "no_fare", c, records_v3(attempt()))
    assert ffr_rows.resolve_guard(cells[BASE], "no_fare", c, records_v3(attempt(outcome="empty"))) is None
    assert "reprice" in ffr_rows.resolve_guard(cells["economy/crosscheck"], "none_qualify", c, [])
    assert "candidate" in ffr_rows.resolve_guard(cells["economy/reprice"], "none_qualify", c, [])
    assert ffr_rows.resolve_guard(cells["economy/reprice"], "none_qualify", c, records_v3(lead(300.0))) is None
    assert ffr_rows.resolve_guard(cells["economy/hack/split"], "na", c, []) is None


# fast mode -------------------------------------------------------------------------

def test_confirm_cell_without_tuples_is_open_and_discover_closes_on_discover_rows():
    c = prepared(contract_v3(speed="fast"))
    s = states(c, records_v3(row_v3(phase="discover")))
    assert s["economy/discover/ZZZ"]["state"] == "done"
    assert s["economy/confirm/ZZZ"]["state"] == "open" and "run_log.py confirm" in s["economy/confirm/ZZZ"]["why"]
    assert states(c, [])["economy/discover/ZZZ"]["why"] == "not attempted"


def test_confirm_cell_closes_only_on_exact_rows_for_its_tuples():
    c = ffr_contract.fill_confirm_cells(prepared(contract_v3(speed="fast")), {"economy/ZZZ": [["2027-02-03", "2027-02-17"]]})
    s = states(c, records_v3(row_v3(phase="discover")))
    assert s["economy/confirm/ZZZ"]["state"] == "open" and "2027-02-03_2027-02-17" in s["economy/confirm/ZZZ"]["why"]
    s = states(c, records_v3(row_v3(phase="discover"), row_v3()))
    assert s["economy/confirm/ZZZ"]["state"] == "done"


def test_region_without_shortlist_keeps_check_incomplete():
    c = contract_v3(speed="fast"); c["legs"][0]["to"] = {"name": "SE Asia", "region": True, "airports": []}
    result = ffr_rows.check(prepared(c), [])
    assert {"cell": "economy/discover", "why": "region 'SE Asia' has no shortlist: run run_log.py shortlist"} in result["open"]


def test_pick_confirm_tuples_takes_cheapest_within_cap_per_destination():
    c = contract_v3(speed="fast"); c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-02-05"}}
    c["legs"][1]["dates"] = {"after_leg": {"leg": 1, "min_days": 14, "max_days": 14}}
    c = prepared(c)

    def disc(day, price, **over):
        return row_v3(phase="discover", source="flightlist", family="kiwi", dates=[f"2027-02-0{day}", f"2027-02-{day + 14}"],
                      tickets=[ticket(price=price, quote_state="list", baggage="unverified")],
                      legs=[leg_entry(1, dep=f"2027-02-0{day}T07:10:00", arr=f"2027-02-0{day}T09:05:00", **over),
                            leg_entry(2, dep=f"2027-02-{day + 14}T18:00:00", arr=f"2027-02-{day + 14}T22:00:00")])

    recs = records_v3(disc(1, 500.0), disc(2, 300.0), disc(3, 100.0, duration="25:00:00"), disc(4, 400.0), disc(5, 350.0))
    picks = ffr_rows.pick_confirm_tuples(c, recs, top=2)
    assert picks == {"economy/ZZZ": [["2027-02-02", "2027-02-16"], ["2027-02-05", "2027-02-19"]]}
    assert ffr_rows.pick_confirm_tuples(c, [], top=2) == {}
