"""ffr_rows ranking: all-in with ground rows, pruning, flags, tie-breaks (spec section 4)."""
import sys

from tests.run_log_helpers import ROOT, contract_v3, group, row_v3, leg_entry, ticket, ground, records_v3

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import ffr_contract  # noqa: E402
import ffr_rows  # noqa: E402


def norm(c=None):
    c = c or contract_v3()
    assert ffr_contract.validate_contract(c) == []
    return ffr_contract.normalize_contract(c)


def nearby_contract(**over):
    c = contract_v3(**over)
    c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    return c


def basel_row(**over):
    return row_v3(origin="BSL", legs=[leg_entry(1, **{"from": "BSL"}), leg_entry(2, to="BSL")], **over)


BOTH_WAYS = [ground(), ground(date="2027-02-17", **{"from": "BSL", "to": "ZRH"}, price=30.0)]


def test_all_in_adds_ground_rows_both_ways():
    assert ffr_rows.all_in(basel_row(), norm(nearby_contract()), BOTH_WAYS) == 462.4


def test_all_in_sums_tickets_bags_components_and_fx():
    c = norm(contract_v3(travelers={"adults": 2, "children_ages": [], "infants": 0},
                         bags={"checked_per_person": 1, "cabin_per_person": 1}))
    r = row_v3(price_basis="per_person",
               tickets=[ticket(price=200.0, baggage="fee_required", bag_fee=60.0, cabin_bag="fee_required", cabin_bag_fee=30.0)],
               components={"hotel": 90.0, "transfers": 10.0})
    assert ffr_rows.all_in(r, c, []) == 590.0
    r = row_v3(currency="EUR", fx={"rate": 0.95, "date": "2027-01-08", "source": "ECB"})
    assert ffr_rows.all_in(r, norm(), []) == 380.0


def test_lower_bound_counts_missing_ground_and_unknowns_as_zero_and_prunes():
    c = norm(nearby_contract())
    lead = basel_row(tickets=[ticket(price=300.0, quote_state="list", baggage="unverified")], components={"hotel": None})
    assert ffr_rows.lower_bound(lead, c, []) == 300.0
    assert ffr_rows.lower_bound(lead, c, BOTH_WAYS) == 362.4
    out = ffr_rows.rank(c, records_v3(row_v3(), basel_row(tickets=[ticket(price=400.0, quote_state="list")])))["economy"]
    assert out["best"] == 400.0 and out["leads"][0]["pruned"] is True


def test_qualified_ranked_by_all_in_then_longest_leg_then_stops():
    a = row_v3(tickets=[ticket(price=500.0)])
    b = row_v3(legs=[leg_entry(1, duration="10:00:00"), leg_entry(2)])
    c = row_v3()
    out = ffr_rows.rank(norm(), records_v3(a, b, c))["economy"]
    assert [q["id"] for q in out["qualified"]] == ["r3", "r2", "r1"] and out["best"] == 400.0


def test_rank_tie_breaks_prefer_airline_and_flags_it():
    c = norm(contract_v3(airlines={"prefer": ["LX"], "exclude": []}))
    plain = row_v3()
    preferred = row_v3(legs=[leg_entry(1, airlines=["LX"]), leg_entry(2, airlines=["LX"])])
    out = ffr_rows.rank(c, records_v3(plain, preferred))["economy"]
    assert [q["id"] for q in out["qualified"]] == ["r2", "r1"]
    assert "preferred airline" in out["qualified"][0]["flags"]


def test_over_budget_is_flagged_not_hidden():
    out = ffr_rows.rank(norm(contract_v3(budget=300)), records_v3(row_v3()))["economy"]
    assert out["qualified"][0]["id"] == "r1" and "over budget" in out["qualified"][0]["flags"]


def test_ground_and_overnight_flags():
    c = nearby_contract(); c["legs"][0]["from"]["airports"][1]["overnight_ok"] = True
    grounds = [ground(date="2027-02-02"), ground(date="2027-02-17", **{"from": "BSL", "to": "ZRH"})]
    flags = ffr_rows.risk_flags(basel_row(), norm(c), grounds)
    assert "ground: rail ZRH-BSL" in flags and "overnight before departure" in flags


def test_risk_flags_ported():
    r = row_v3(cabin_label="Economy + Premium Economy", tickets=[ticket(), ticket()],
               legs=[leg_entry(1, airport_change=True, stops=2), leg_entry(2)], components={"hotel": 90.0})
    assert ffr_rows.risk_flags(r, norm(), []) == ["mixed cabin: Economy + Premium Economy", "airport change",
                                                   "separate tickets", "2+ stops", "hotel"]
    assert "mixed cabin: Economy Prime (TAP: Mixed Cabin)" in ffr_rows.risk_flags(row_v3(cabin_label="Economy Prime (TAP: Mixed Cabin)"), norm(), [])
    late = leg_entry(1, dep="2027-02-03T23:30:00", arr="2027-02-04T01:10:00", duration="02:40:00")
    assert "next-day arrival" in ffr_rows.risk_flags(row_v3(legs=[late, leg_entry(2)]), norm(), [])
    assert "next-day arrival" not in ffr_rows.risk_flags(row_v3(), norm(), [])
    assert "self-transfer" in ffr_rows.risk_flags(row_v3(legs=[leg_entry(1, self_transfer=True), leg_entry(2)]),
                                                  norm(contract_v3(self_transfer_ok=True)), [])


def test_pruned_lead_readmitted_when_best_superseded():
    lead = row_v3(tickets=[ticket(price=450.0, quote_state="list")])
    assert ffr_rows.rank(norm(), records_v3(row_v3(), lead))["economy"]["leads"][0]["pruned"] is True
    recs = records_v3(row_v3(), lead, row_v3(supersedes="r1", tickets=[ticket(price=500.0)]))
    out = ffr_rows.rank(norm(), recs)["economy"]
    assert out["best"] == 500.0 and out["leads"][0]["pruned"] is False


def test_foreign_currency_lead_without_fx_is_never_pruned():
    sek = row_v3(hack="split", currency="SEK", tickets=[ticket(price=2100.0, quote_state="list")])
    lead = ffr_rows.rank(norm(contract_v3(hacks={"split": True})), records_v3(row_v3(), sek))["economy"]["leads"][0]
    assert lead["pruned"] is False and lead["comparable"] is False and lead["currency"] == "SEK"


def test_rejected_rows_are_excluded_and_cabin_filter_works():
    out = ffr_rows.rank(norm(), records_v3(row_v3(legs=[leg_entry(1, duration="22:00:00"), leg_entry(2)])))
    assert out["economy"]["qualified"] == [] and out["economy"]["leads"] == []
    c = norm(contract_v3(cabins=["economy", "business"]))
    assert list(ffr_rows.rank(c, records_v3(row_v3(), row_v3(cabin="business")), cabin="business")) == ["business"]


def test_evaluate_carries_cell_ground_and_public_fields():
    c = norm(nearby_contract())
    e = ffr_rows.evaluate(c, records_v3(basel_row(), *BOTH_WAYS))[0]
    assert e["cell"] == "economy/baseline/BSL-ZZZ/2027-02-03_2027-02-17" and e["status"] == "qualified"
    assert e["all_in"] == 462.4 and e["ground"] == {"BSL": ["g1", "g2"]}
    public = ffr_rows.public_entry(e)
    assert public["dates"] == ["2027-02-03", "2027-02-17"] and public["legs"][0]["leg"] == 1
    assert public["booking_urls"] == ["https://example.test/book"] and "row" not in public
