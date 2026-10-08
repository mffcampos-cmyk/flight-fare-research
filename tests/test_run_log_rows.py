import json
import pytest
from tests.run_log_helpers import run_log, contract, row, ticket, direction, cli, write_json

POS = {"allowed": True, "rail_ok": True, "overnight_ok": False}

def status(r, c=None, superseded=()):
    return run_log.row_status(dict(r, id="r1"), c or contract(), set(superseded))

def test_complete_row_is_qualified():
    assert status(row()) == ("qualified", [])

def test_strict_cap_rejects_exactly_20h():
    r = row(directions=[direction("out", duration="20:00:00"), direction("ret")])
    assert status(r) == ("rejected", ["out duration 20:00:00 breaks strict cap 20:00:00"])

def test_strict_cap_passes_one_second_under():
    assert status(row(directions=[direction("out", duration="19:59:59"), direction("ret")]))[0] == "qualified"

def test_inclusive_cap_accepts_exactly_20h():
    c = contract(max_duration={"value": "20:00:00", "strict": False})
    assert status(row(directions=[direction("out", duration="20:00:00"), direction("ret")]), c)[0] == "qualified"

def test_no_cap_when_max_duration_null():
    c = contract(max_duration=None)
    assert status(row(directions=[direction("out", duration="30:00:00"), direction("ret")]), c)[0] == "qualified"

@pytest.mark.parametrize("over,reason", [
    ({"directions": [direction("out")]}, "return not selected"),
    ({"directions": [direction("ret")]}, "outbound not selected"),
    ({"tickets": [ticket(quote_state="list")]}, "list fare not repriced"),
    ({"tickets": [ticket(baggage="unverified")]}, "baggage unverified"),
    ({"tickets": [ticket(baggage="fee_required", bag_fee=None)]}, "bag fee unknown"),
    ({"components": {"hotel": None}}, "hotel unpriced"),
    ({"currency": "EUR"}, "currency differs; no fx recorded"),
    ({"directions": [direction("out", duration=None), direction("ret")]}, "duration unknown (out)"),
])
def test_lead_reasons(over, reason):
    s, reasons = status(row(**over))
    assert s == "lead" and reason in reasons

def test_infants_with_per_person_price_is_lead():
    c = contract(travelers={"adults": 1, "children_ages": [], "infants": 1})
    assert "per-person price with infants; record the total" in status(row(price_basis="per_person"), c)[1]

def test_unverified_bag_qualifies_when_no_checked_bags_requested():
    c = contract(bags={"checked_per_person": 0})
    assert status(row(tickets=[ticket(baggage="unverified")]), c)[0] == "qualified"

def test_fee_required_with_known_fee_qualifies():
    r = row(tickets=[ticket(baggage="fee_required", bag_fee=60.0)])
    assert status(r)[0] == "qualified"
    assert run_log.all_in(r, contract()) == 460.0

@pytest.mark.parametrize("over,cover,reason", [
    ({"directions": [direction("out", self_transfer=True), direction("ret")]}, {}, "self-transfer not allowed"),
    ({"cabin": "business"}, {}, "cabin not requested"),
    ({"outbound_date": "2026-11-06"}, {}, "dates not in contract"),
    ({"origin": "CCC"}, {}, "origin not in contract"),
    ({"destination": "YYY"}, {}, "destination not in contract"),
    ({"hack": "nearby_origin", "origin": "BBB"}, {"nearby_origins": ["BBB"]}, "positioning not allowed"),
    ({"components": {"positioning": 45.0}}, {}, "positioning not allowed"),
    ({"positioning_overnight": True}, {"positioning": POS}, "overnight positioning not allowed"),
])
def test_rejections(over, cover, reason):
    s, reasons = status(row(**over), contract(**cover))
    assert s == "rejected" and reason in reasons

def test_rejection_beats_lead():
    r = row(tickets=[ticket(quote_state="list")],
            directions=[direction("out", duration="21:00:00"), direction("ret")])
    assert status(r) == ("rejected", ["out duration 21:00:00 breaks strict cap 20:00:00"])

def test_superseded_and_attempt_statuses():
    assert status(row(), superseded={"r1"}) == ("superseded", [])
    assert status({"source": "x", "family": "x", "engine": "t", "outcome": "blocked",
                   "url": "https://e.test", "retrieved_at": "2026-10-08T10:00:00+00:00",
                   "cabin": "economy"}) == ("attempt", [])

def test_multi_ticket_rows_need_every_ticket_qualified():
    assert "list fare not repriced" in status(row(tickets=[ticket(), ticket(quote_state="list")]))[1]
    assert "baggage unverified" in status(row(tickets=[ticket(), ticket(baggage="unverified")]))[1]

def test_all_in_sums_parts():
    c = contract(travelers={"adults": 2, "children_ages": [], "infants": 0}, positioning=POS)
    r = row(price_basis="per_person", tickets=[ticket(price=200.0, baggage="fee_required", bag_fee=60.0)],
            components={"positioning": 45.0, "hotel": 90.0})
    assert run_log.all_in(r, c) == 595.0

def test_all_in_applies_fx():
    r = row(currency="EUR", fx={"rate": 0.95, "date": "2026-10-08", "source": "ECB"})
    assert status(r)[0] == "qualified" and run_log.all_in(r, contract()) == 380.0

def test_lower_bound_counts_unknowns_as_zero():
    c = contract(positioning=POS)
    r = row(tickets=[ticket(price=300.0, quote_state="list", baggage="unverified")], components={"positioning": None})
    assert run_log.lower_bound(r, c) == 300.0
    assert run_log.lower_bound(dict(r, components={"positioning": 45.0}), c) == 345.0

def test_row_cell_id():
    assert run_log.row_cell_id(row()) == "economy/baseline/AAA-ZZZ/2026-11-05_2026-11-12"
    assert run_log.row_cell_id(row(hack="split")) == "economy/hack/split"

def test_validate_row_accepts_complete_row():
    assert run_log.validate_row(row(), contract()) == []

@pytest.mark.parametrize("field", ["source", "family", "engine", "url", "retrieved_at", "cabin", "tickets"])
def test_validate_row_requires_fields(field):
    r = row(); del r[field]
    assert any(field in e for e in run_log.validate_row(r, contract()))

def test_retrieved_at_needs_timezone():
    assert any("timezone" in e for e in run_log.validate_row(row(retrieved_at="2026-10-08T14:03:00"), contract()))

@pytest.mark.parametrize("price", ["CHF 203.85", "1'234.50", True, -1])
def test_price_must_be_non_negative_number(price):
    assert any("price" in e for e in run_log.validate_row(row(tickets=[ticket(price=price)]), contract()))

@pytest.mark.parametrize("over", [{"tickets": [ticket(baggage="maybe")]}, {"tickets": [ticket(quote_state="final")]},
                                  {"hack": "hidden_city"}, {"outcome": "teaser"}, {"price_basis": "each"}])
def test_unknown_enum_values_rejected(over):
    assert run_log.validate_row(row(**over), contract()) != []

def test_attempt_row_needs_no_tickets():
    attempt = {"source": "x", "family": "x", "engine": "t", "outcome": "blocked", "url": "https://e.test",
               "retrieved_at": "2026-10-08T10:00:00+00:00", "cabin": "economy"}
    assert run_log.validate_row(attempt, contract()) == []

@pytest.fixture
def run_dir(tmp_path):
    assert cli("init", "--contract", write_json(tmp_path / "c.json", contract()),
               "--runs-root", tmp_path / "runs").returncode == 0
    return tmp_path / "runs" / "t1"

def test_add_appends_and_reports_status(run_dir, tmp_path):
    f = write_json(tmp_path / "r.json", row())
    first, second = cli("add", "--run", run_dir, "--row", f), cli("add", "--run", run_dir, "--row", f)
    assert first.returncode == 0 and first.stdout.startswith("r1 qualified")
    assert second.stdout.startswith("r2 qualified")
    assert len((run_dir / "rows.jsonl").read_text().splitlines()) == 2

def test_add_reads_stdin_and_reports_reasons(run_dir):
    r = cli("add", "--run", run_dir, "--row", "-", input=json.dumps(row(tickets=[ticket(quote_state="list")])))
    assert r.returncode == 0 and r.stdout.startswith("r1 lead: list fare not repriced")

def test_add_invalid_row_appends_nothing(run_dir, tmp_path):
    r = cli("add", "--run", run_dir, "--row", write_json(tmp_path / "r.json", row(retrieved_at="2026-10-08T14:03:00")))
    assert r.returncode == 2 and (run_dir / "rows.jsonl").read_text() == ""

def test_add_supersedes_must_reference_existing_row(run_dir, tmp_path):
    r = cli("add", "--run", run_dir, "--row", write_json(tmp_path / "r.json", row(supersedes="r9")))
    assert r.returncode == 2 and "r9" in r.stderr
