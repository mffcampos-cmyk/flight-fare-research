"""ffr_contract: legs, airport groups, date tuples (spec section 3)."""
import sys

import pytest

from tests.run_log_helpers import ROOT, contract_v3, group, leg

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import ffr_contract  # noqa: E402


def norm(c):
    errors = ffr_contract.validate_contract(c)
    assert errors == [], errors
    return ffr_contract.normalize_contract(c)


def tuples(c):
    return ffr_contract.expand_tuples(norm(c))


def errors_of(c):
    return "\n".join(ffr_contract.validate_contract(c))


# shape and groups ----------------------------------------------------------------

def test_shape_is_derived():
    assert ffr_contract.trip_shape([leg("ZRH", "BKK", {"fixed": "2027-02-03"})]) == "one_way"
    assert ffr_contract.trip_shape(contract_v3()["legs"]) == "return"
    three = [leg("ZRH", "BKK", {"fixed": "2027-02-03"}), leg("BKK", "SIN", {"fixed": "2027-02-10"}),
             leg("SIN", "ZRH", {"fixed": "2027-02-17"})]
    assert ffr_contract.trip_shape(three) == "multi_city"


def test_group_reference_resolves_and_reverses():
    c = norm(contract_v3())
    assert c["shape"] == "return"
    assert c["legs"][1]["from"]["airports"][0]["code"] == "ZZZ"
    assert c["legs"][1]["to"]["airports"][0]["code"] == "ZRH"
    assert ffr_contract.home_airport(c["legs"][0]["from"]) == "ZRH"


def test_group_reference_to_a_later_or_missing_leg_is_refused():
    c = contract_v3(); c["legs"][0]["from"] = "to:2"
    assert "leg 1" in errors_of(c) and "to:2" in errors_of(c)


def test_via_airport_is_normalized_with_defaults():
    c = contract_v3(); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    n = norm(c)
    assert n["legs"][0]["from"]["airports"][1] == {"code": "BSL", "via": "rail", "overnight_ok": False}
    assert ffr_contract.airports(n["legs"][0]["from"]) == ["ZRH", "BSL"]
    assert set(ffr_contract.via_airports(n)) == {"BSL"}


def test_via_airport_dropped_when_positioning_not_allowed():
    c = contract_v3(positioning={"allowed": False, "overnight_ok": False})
    c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    n = norm(c)
    assert ffr_contract.airports(n["legs"][0]["from"]) == ["ZRH"]
    assert ffr_contract.airports(n["legs"][1]["to"]) == ["ZRH"]
    assert any("BSL" in a for a in n["assumptions"])


def test_airport_codes_and_via_are_validated():
    c = contract_v3(); c["legs"][0]["to"] = group("zzz")
    assert "leg 1" in errors_of(c) and "zzz" in errors_of(c)
    c = contract_v3(); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "boat"})
    assert "via" in errors_of(c)


# dates and tuples ----------------------------------------------------------------

def test_fixed_dates_give_one_tuple():
    assert tuples(contract_v3()) == [["2027-02-03", "2027-02-17"]]


@pytest.mark.parametrize("dates,count,first", [
    ({"range": {"from": "2027-02-01", "to": "2027-02-03"}}, 3, ["2027-02-01", "2027-02-15"]),
    ({"flex": {"date": "2027-02-02", "minus": 1, "plus": 1}}, 3, ["2027-02-01", "2027-02-15"]),
])
def test_tuples_from_range_and_flex_with_linked_return(dates, count, first):
    c = contract_v3(); c["legs"][0]["dates"] = dates
    c["legs"][1]["dates"] = {"after_leg": {"leg": 1, "min_days": 14, "max_days": 14}}
    result = tuples(c)
    assert result[0] == first and len(result) == count


def test_after_leg_range_multiplies_tuples():
    c = contract_v3(); c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-02-02"}}
    c["legs"][1]["dates"] = {"after_leg": {"leg": 1, "min_days": 12, "max_days": 13}}
    assert tuples(c) == [["2027-02-01", "2027-02-13"], ["2027-02-01", "2027-02-14"],
                         ["2027-02-02", "2027-02-14"], ["2027-02-02", "2027-02-15"]]


def test_tuple_dates_must_not_go_backwards():
    c = contract_v3(); c["legs"][1]["dates"] = {"fixed": "2027-02-01"}
    assert "leg 2" in errors_of(c) and "before leg 1" in errors_of(c)


def test_mixed_ranges_drop_backwards_combinations_silently():
    c = contract_v3(); c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-02-03"}}
    c["legs"][1]["dates"] = {"range": {"from": "2027-02-02", "to": "2027-02-03"}}
    assert tuples(c) == [["2027-02-01", "2027-02-02"], ["2027-02-01", "2027-02-03"],
                         ["2027-02-02", "2027-02-02"], ["2027-02-02", "2027-02-03"],
                         ["2027-02-03", "2027-02-03"]]


def test_after_leg_may_not_reference_a_later_leg():
    c = contract_v3(); c["legs"][0]["dates"] = {"after_leg": {"leg": 2, "min_days": 1, "max_days": 1}}
    assert "leg 1" in errors_of(c) and "after_leg" in errors_of(c)


def test_date_kind_must_be_exactly_one():
    c = contract_v3(); c["legs"][0]["dates"] = {"fixed": "2027-02-03", "range": {"from": "2027-02-01", "to": "2027-02-03"}}
    assert "exactly one" in errors_of(c)
    c = contract_v3(); c["legs"][0]["dates"] = {"flex": {"date": "2027-02-03", "minus": -1, "plus": 0}}
    assert "flex" in errors_of(c)


def test_thorough_refuses_more_than_200_tuples():
    c = contract_v3(); c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-03-31"}}
    c["legs"][1]["dates"] = {"after_leg": {"leg": 1, "min_days": 10, "max_days": 20}}
    assert "200" in errors_of(c) and "thorough" in errors_of(c)


def test_fast_mode_has_no_tuple_cap():
    c = contract_v3(speed="fast"); c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-03-31"}}
    c["legs"][1]["dates"] = {"after_leg": {"leg": 1, "min_days": 10, "max_days": 20}}
    assert errors_of(c) == "" and len(tuples(c)) == 59 * 11


# scope, speed, regions, other fields ----------------------------------------------

def test_quick_scope_rules():
    c = contract_v3(scope="quick"); c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-02-03"}}
    assert "quick" in errors_of(c)
    c = contract_v3(scope="quick", cabins=["economy", "business"])
    assert "quick" in errors_of(c)
    c = contract_v3(scope="quick", hacks={"split": True, "open_jaw": True, "stopover": True})
    assert norm(c)["hacks"] == {"split": False, "open_jaw": False, "stopover": False}


def test_region_group_without_airports_needs_fast_mode():
    c = contract_v3(); c["legs"][0]["to"] = {"name": "SE Asia", "region": True, "airports": []}
    assert "region" in errors_of(c) and "fast" in errors_of(c)
    c = contract_v3(speed="fast"); c["legs"][0]["to"] = {"name": "SE Asia", "region": True, "airports": []}
    n = norm(c)
    assert n["legs"][0]["to"]["region"] is True and ffr_contract.airports(n["legs"][1]["from"]) == []
    assert ffr_contract.expand_tuples(n) == [["2027-02-03", "2027-02-17"]]


def test_defaults_are_filled():
    c = {k: v for k, v in contract_v3().items()
         if k not in ("speed", "max_stops", "time_windows", "airlines", "hacks", "budget", "shortlist",
                      "event", "assumptions", "positioning", "self_transfer_ok", "max_duration")}
    n = norm(c)
    assert n["speed"] == "thorough" and n["max_stops"] is None and n["time_windows"] == []
    assert n["airlines"] == {"prefer": [], "exclude": []} and n["budget"] is None
    assert n["hacks"] == {"split": True, "open_jaw": True, "stopover": False}
    assert n["shortlist"] == 4 and n["positioning"] == {"allowed": True, "overnight_ok": False}
    assert n["self_transfer_ok"] is False and n["max_duration"] is None


def test_speed_default_follows_the_tuple_count():
    c = contract_v3(); del c["speed"]
    c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-02-11"}}
    assert norm(c)["speed"] == "fast"


def test_requested_hacks_are_kept_for_one_way_so_init_can_mark_them_na():
    c = contract_v3(hacks={"split": True, "open_jaw": True, "stopover": False})
    c["legs"] = [leg("ZRH", "BKK", {"fixed": "2027-02-03"})]
    n = norm(c)
    assert n["shape"] == "one_way" and n["hacks"] == {"split": True, "open_jaw": True, "stopover": False}


@pytest.mark.parametrize("field,value,fragment", [
    ("max_stops", -1, "max_stops"), ("time_windows", [{"leg": 9}], "leg 9"),
    ("time_windows", [{"leg": 1, "dep_after": "6am"}], "HH:MM"),
    ("airlines", {"prefer": "LX"}, "airlines"), ("airlines", {"exclude": ["fr"]}, "airlines"),
    ("budget", "cheap", "budget"), ("hacks", {"split": "yes"}, "hacks"), ("shortlist", 0, "shortlist"),
    ("speed", "quick", "speed"), ("legs", [], "legs"), ("cabins", ["coach"], "cabins"),
    ("positioning", {"allowed": "yes"}, "positioning"),
])
def test_field_validation(field, value, fragment):
    assert fragment in errors_of(contract_v3(**{field: value}))


def test_usage_error_lives_here():
    assert issubclass(ffr_contract.UsageError, Exception)
