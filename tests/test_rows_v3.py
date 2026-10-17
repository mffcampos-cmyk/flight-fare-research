"""ffr_rows: v3 row validation, hard gates, lead reasons, ground rows (spec section 4)."""
import sys

import pytest

from tests.run_log_helpers import ROOT, contract_v3, group, leg, row_v3, leg_entry, ticket, ground

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import ffr_contract  # noqa: E402
import ffr_rows  # noqa: E402


def norm(c=None):
    c = c or contract_v3()
    assert ffr_contract.validate_contract(c) == []
    return ffr_contract.normalize_contract(c)


def status(r, c=None, superseded=(), grounds=()):
    return ffr_rows.row_status(dict(r, id="r1"), norm(c), set(superseded), list(grounds))


def nearby_contract(**over):
    c = contract_v3(**over)
    c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    return c


def basel_row(**over):
    return row_v3(origin="BSL", legs=[leg_entry(1, **{"from": "BSL"}), leg_entry(2, to="BSL")], **over)


# statuses ---------------------------------------------------------------------------

def test_complete_row_is_qualified():
    assert status(row_v3()) == ("qualified", [])


def test_populated_row_needs_every_contract_leg_or_is_a_lead():
    assert status(row_v3(legs=[leg_entry(1)])) == ("lead", ["leg 2 not selected"])
    assert status(row_v3(legs=[leg_entry(2)])) == ("lead", ["leg 1 not selected"])


def test_superseded_and_attempt_statuses():
    assert status(row_v3(), superseded={"r1"}) == ("superseded", [])
    attempt = {"source": "x", "family": "x", "engine": "t", "outcome": "blocked",
               "url": "https://e.test", "retrieved_at": "2027-01-08T10:00:00+00:00", "cabin": "economy"}
    assert status(attempt) == ("attempt", [])


@pytest.mark.parametrize("over,reason", [
    ({"tickets": [ticket(quote_state="list")]}, "list fare not repriced"),
    ({"tickets": [ticket(baggage="unverified")]}, "baggage unverified"),
    ({"tickets": [ticket(baggage="fee_required", bag_fee=None)]}, "bag fee unknown"),
    ({"components": {"hotel": None}}, "hotel unpriced"),
    ({"currency": "EUR"}, "currency differs; no fx recorded"),
    ({"legs": [leg_entry(1, duration=None), leg_entry(2)]}, "duration unknown (leg 1)"),
])
def test_lead_reasons(over, reason):
    s, reasons = status(row_v3(**over))
    assert s == "lead" and reason in reasons


def test_cabin_bag_reasons_only_when_requested():
    c = contract_v3(bags={"checked_per_person": 1, "cabin_per_person": 1})
    assert "cabin bag unverified" in status(row_v3(), c)[1]
    assert "cabin bag fee unknown" in status(row_v3(tickets=[ticket(cabin_bag="fee_required")]), c)[1]
    assert status(row_v3(tickets=[ticket(cabin_bag="included")]), c)[0] == "qualified"
    assert status(row_v3())[0] == "qualified"


def test_infants_with_per_person_price_is_lead():
    c = contract_v3(travelers={"adults": 1, "children_ages": [], "infants": 1})
    assert "per-person price with infants; record the total" in status(row_v3(price_basis="per_person"), c)[1]


def test_unverified_bag_qualifies_when_no_checked_bags_requested():
    c = contract_v3(bags={"checked_per_person": 0})
    assert status(row_v3(tickets=[ticket(baggage="unverified")]), c)[0] == "qualified"


def test_multi_ticket_rows_need_every_ticket_qualified():
    assert "list fare not repriced" in status(row_v3(tickets=[ticket(), ticket(quote_state="list")]))[1]


# hard gates -------------------------------------------------------------------------

def test_strict_cap_rejects_exactly_20h_inclusive_accepts():
    r = row_v3(legs=[leg_entry(1, duration="20:00:00"), leg_entry(2)])
    strict = contract_v3(max_duration={"value": "20:00:00", "strict": True})
    assert status(r, strict) == ("rejected", ["leg 1 duration 20:00:00 breaks strict cap 20:00:00"])
    assert status(r)[0] == "qualified"
    assert status(row_v3(legs=[leg_entry(1, duration="30:00:00"), leg_entry(2)]), contract_v3(max_duration=None))[0] == "qualified"


def test_cap_applies_per_leg_part():
    legs = [leg_entry(1, part=1, to="LIS", arr="2027-02-03T09:05:00", duration="02:55:00"),
            leg_entry(1, part=2, **{"from": "LIS"}, dep="2027-02-06T10:00:00", arr="2027-02-06T19:00:00", duration="12:00:00"),
            leg_entry(2)]
    assert status(row_v3(legs=legs, hack="stopover"), contract_v3(hacks={"stopover": True}))[0] == "qualified"
    legs[1]["duration"] = "21:00:00"
    s, reasons = status(row_v3(legs=legs, hack="stopover"), contract_v3(hacks={"stopover": True}))
    assert s == "rejected" and "leg 1 part 2 duration 21:00:00 breaks inclusive cap 20:00:00" in reasons


@pytest.mark.parametrize("over,reason", [
    ({"stops": 2}, "leg 1 stops 2 over max 1"),
    ({"dep": "2027-02-03T05:10:00"}, "leg 1 departs 05:10 before 06:00"),
    ({"arr": "2027-02-03T23:30:00"}, "leg 1 arrives 23:30 after 22:00"),
    ({"airlines": ["FR"]}, "leg 1 airline FR excluded"),
    ({"self_transfer": True}, "self-transfer not allowed"),
])
def test_hard_gates_stops_windows_excluded_airlines(over, reason):
    c = contract_v3(max_stops=1, time_windows=[{"leg": 1, "dep_after": "06:00", "arr_before": "22:00"}],
                    airlines={"prefer": [], "exclude": ["FR"]})
    s, reasons = status(row_v3(legs=[leg_entry(1, **over), leg_entry(2)]), c)
    assert s == "rejected" and reason in reasons


@pytest.mark.parametrize("over,reason", [
    ({"cabin": "business"}, "cabin not requested"),
    ({"dates": ["2027-02-04", "2027-02-17"]}, "dates not in contract"),
    ({"origin": "CCC", "legs": [leg_entry(1, **{"from": "CCC"}), leg_entry(2)]}, "leg 1: origin CCC not in contract"),
    ({"legs": [leg_entry(1, to="YYY"), leg_entry(2)]}, "leg 1: destination YYY not in contract"),
])
def test_contract_mismatch_is_rejected_and_refused_by_validate(over, reason):
    s, reasons = status(row_v3(**over))
    assert s == "rejected" and reason in reasons
    assert any(reason in e for e in ffr_rows.validate_row(row_v3(**over), norm()))


def test_multi_city_row_matches_each_leg_group():
    c = contract_v3(); c["legs"] = [leg("ZRH", "BKK", {"fixed": "2027-02-03"}), leg("BKK", "SIN", {"fixed": "2027-02-10"}),
                                    leg("SIN", "ZRH", {"fixed": "2027-02-17"})]
    legs = [leg_entry(1, to="BKK"), leg_entry(1, leg=2, **{"from": "BKK"}, to="SIN", dep="2027-02-10T08:00:00", arr="2027-02-10T11:00:00"),
            leg_entry(2, leg=3, **{"from": "SIN"}, to="ZRH")]
    r = row_v3(destination="BKK", dates=["2027-02-03", "2027-02-10", "2027-02-17"], legs=legs)
    assert status(r, c) == ("qualified", [])
    legs[1]["to"] = "KUL"
    assert any("leg 2: destination KUL not in contract" in e for e in ffr_rows.validate_row(r, norm(c)))


def test_rejection_beats_lead():
    r = row_v3(tickets=[ticket(quote_state="list")], legs=[leg_entry(1, duration="21:00:00"), leg_entry(2)])
    assert status(r) == ("rejected", ["leg 1 duration 21:00:00 breaks inclusive cap 20:00:00"])


# ground rows ------------------------------------------------------------------------

def test_via_airport_without_ground_row_is_a_lead():
    assert "ground unpriced (BSL)" in status(basel_row(), nearby_contract())[1]
    both = [ground(), ground(date="2027-02-17", **{"from": "BSL", "to": "ZRH"})]
    assert status(basel_row(), nearby_contract(), grounds=both)[0] == "qualified"


def test_ground_row_matches_either_direction_and_only_its_date():
    both = [ground(**{"from": "BSL", "to": "ZRH"}), ground(date="2027-02-17")]
    assert status(basel_row(), nearby_contract(), grounds=both)[0] == "qualified"
    wrong_day = [ground(date="2027-02-04"), ground(date="2027-02-17")]
    assert "ground unpriced (BSL)" in status(basel_row(), nearby_contract(), grounds=wrong_day)[1]


def test_ground_row_the_day_before_needs_overnight_ok():
    before = [ground(date="2027-02-02"), ground(date="2027-02-17")]
    assert "ground unpriced (BSL)" in status(basel_row(), nearby_contract(), grounds=before)[1]
    c = nearby_contract(); c["legs"][0]["from"]["airports"][1]["overnight_ok"] = True
    assert status(basel_row(), c, grounds=before)[0] == "qualified"
    chosen = ffr_rows.ground_for(basel_row(), norm(c), before)
    assert chosen["BSL"][0]["date"] == "2027-02-02" and chosen["BSL"][1]["date"] == "2027-02-17"


def test_ground_rows_must_be_completed_to_count():
    listed = [ground(quote_state="list"), ground(date="2027-02-17")]
    assert "ground unpriced (BSL)" in status(basel_row(), nearby_contract(), grounds=listed)[1]


def test_home_airport_row_needs_no_ground_row():
    assert status(row_v3(), nearby_contract())[0] == "qualified"


def test_ground_row_validation():
    assert ffr_rows.validate_ground(ground(), norm(nearby_contract())) == []
    assert any("price" in e for e in ffr_rows.validate_ground(ground(price=None), norm(nearby_contract())))
    assert any("quote_state" in e for e in ffr_rows.validate_ground(ground(quote_state="final"), norm(nearby_contract())))
    assert any("ZRH-QQQ" in e for e in ffr_rows.validate_ground(ground(to="QQQ"), norm(nearby_contract())))
    assert any("date" in e for e in ffr_rows.validate_ground(ground(date="2027-2-3"), norm(nearby_contract())))


# validation and cell ids ------------------------------------------------------------

def test_validate_row_accepts_complete_row():
    assert ffr_rows.validate_row(row_v3(), norm()) == []


@pytest.mark.parametrize("field", ["source", "family", "engine", "url", "retrieved_at", "cabin", "tickets", "legs", "dates"])
def test_validate_row_requires_fields(field):
    r = row_v3(); del r[field]
    assert any(field in e for e in ffr_rows.validate_row(r, norm()))


def test_retrieved_at_needs_timezone():
    assert any("timezone" in e for e in ffr_rows.validate_row(row_v3(retrieved_at="2027-01-08T14:03:00"), norm()))


@pytest.mark.parametrize("price", ["CHF 203.85", "1'234.50", True, -1])
def test_price_must_be_non_negative_number(price):
    assert any("price" in e for e in ffr_rows.validate_row(row_v3(tickets=[ticket(price=price)]), norm()))


@pytest.mark.parametrize("over", [{"tickets": [ticket(baggage="maybe")]}, {"tickets": [ticket(quote_state="final")]},
                                  {"hack": "nearby_origin"}, {"outcome": "teaser"}, {"price_basis": "each"},
                                  {"phase": "guess"}, {"legs": [leg_entry(1, leg=0), leg_entry(2)]},
                                  {"legs": [leg_entry(1, part=0), leg_entry(2)]}])
def test_unknown_enum_values_rejected(over):
    assert ffr_rows.validate_row(row_v3(**over), norm()) != []


def test_attempt_row_needs_no_tickets_but_a_requested_cabin():
    attempt = {"source": "x", "family": "x", "engine": "t", "outcome": "blocked", "url": "https://e.test",
               "retrieved_at": "2027-01-08T10:00:00+00:00", "cabin": "economy"}
    assert ffr_rows.validate_row(attempt, norm()) == []
    assert ffr_rows.validate_row(dict(attempt, cabin="first"), norm()) != []


def test_phase_defaults_to_exact_and_cell_ids_follow_speed():
    fast = norm(contract_v3(speed="fast"))
    assert ffr_rows.row_cell_id(row_v3(phase="discover"), fast) == "economy/discover/ZZZ"
    r = row_v3(); del r["phase"]
    assert ffr_rows.row_cell_id(r, fast) == "economy/confirm/ZZZ"
    assert ffr_rows.row_cell_id(row_v3(), norm()) == "economy/baseline/ZRH-ZZZ/2027-02-03_2027-02-17"
    assert ffr_rows.row_cell_id(row_v3(hack="split"), norm()) == "economy/hack/split"
