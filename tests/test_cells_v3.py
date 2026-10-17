"""ffr_contract cells: baseline/discover/confirm/hack per speed mode, shortlist, confirm."""
import sys

import pytest

from tests.run_log_helpers import ROOT, contract_v3, group, leg

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import ffr_contract  # noqa: E402


def cells(c):
    assert ffr_contract.validate_contract(c) == []
    return ffr_contract.build_cells(ffr_contract.normalize_contract(c))


def ids(c):
    return [x["id"] for x in cells(c)]


def test_thorough_cells_per_origin_destination_tuple():
    c = contract_v3(); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    got = ids(c)
    assert "economy/baseline/ZRH-ZZZ/2027-02-03_2027-02-17" in got
    assert "economy/baseline/BSL-ZZZ/2027-02-03_2027-02-17" in got
    assert got[-2:] == ["economy/crosscheck", "economy/reprice"]
    base = [x for x in cells(c) if x["kind"] == "baseline"][0]
    assert base["origin"] == "ZRH" and base["destination"] == "ZZZ" and base["dates"] == ["2027-02-03", "2027-02-17"]
    assert base["cabin"] == "economy" and base["auto"] is None


def test_multi_city_baseline_uses_leg1_origin_and_destination():
    c = contract_v3(); c["legs"] = [leg("ZRH", "BKK", {"fixed": "2027-02-03"}), leg("BKK", "SIN", {"fixed": "2027-02-10"}),
                                    leg("SIN", "ZRH", {"fixed": "2027-02-17"})]
    assert "economy/baseline/ZRH-BKK/2027-02-03_2027-02-10_2027-02-17" in ids(c)


def test_fast_cells_are_discover_and_confirm_per_destination():
    c = contract_v3(speed="fast"); c["legs"][0]["to"] = group("BKK", "SIN")
    got = cells(c)
    kinds = {(x["kind"], x.get("destination")) for x in got}
    assert ("discover", "BKK") in kinds and ("confirm", "SIN") in kinds and ("baseline", None) not in kinds
    assert [x for x in got if x["id"] == "economy/confirm/BKK"][0]["tuples"] == []
    assert all(x["kind"] != "baseline" for x in got)


def test_hack_cells_follow_the_hacks_object_and_trip_shape():
    c = contract_v3(hacks={"split": True, "open_jaw": True, "stopover": False})
    got = {x["id"]: x for x in cells(c)}
    assert got["economy/hack/split"]["auto"] is None and "economy/hack/stopover" not in got
    c["legs"] = [leg("ZRH", "BKK", {"fixed": "2027-02-03"})]
    got = {x["id"]: x for x in cells(c)}
    assert got["economy/hack/split"]["auto"] == {"as": "na", "reason": "one-way trip"}
    c = contract_v3(hacks={"split": False, "open_jaw": True, "stopover": True})
    got = {x["id"]: x for x in cells(c)}
    assert "economy/hack/split" not in got and got["economy/hack/stopover"]["auto"] is None
    assert got["economy/hack/open_jaw"]["auto"] == {"as": "na", "reason": "no other airport to open the jaw"}


def test_open_jaw_applies_with_a_second_airport_on_either_end():
    c = contract_v3(hacks={"split": False, "open_jaw": True, "stopover": False})
    c["legs"][0]["to"] = group("ZZZ", "YYY")
    assert {x["id"]: x for x in cells(c)}["economy/hack/open_jaw"]["auto"] is None


def test_cells_per_cabin():
    c = contract_v3(cabins=["economy", "business"])
    got = ids(c)
    assert "business/baseline/ZRH-ZZZ/2027-02-03_2027-02-17" in got and "business/reprice" in got


def test_region_group_yields_no_cells_until_shortlist():
    c = contract_v3(speed="fast"); c["legs"][0]["to"] = {"name": "SE Asia", "region": True, "airports": []}
    n = ffr_contract.normalize_contract(c)
    assert ffr_contract.region_groups(n) == [(0, "to")]
    assert not [x for x in ffr_contract.build_cells(n) if x["kind"] in ("discover", "confirm")]
    s = ffr_contract.apply_shortlist(n, ["BKK", "SIN"])
    assert ffr_contract.airports(s["legs"][0]["to"]) == ["BKK", "SIN"]
    assert ffr_contract.airports(s["legs"][1]["from"]) == ["BKK", "SIN"]
    assert ffr_contract.region_groups(s) == []
    assert "economy/discover/SIN" in [x["id"] for x in s["cells"]]
    assert s["date_tuples"] == [["2027-02-03", "2027-02-17"]]


def test_apply_shortlist_refuses_bad_or_duplicate_codes():
    c = contract_v3(speed="fast"); c["legs"][0]["to"] = {"name": "SE Asia", "region": True, "airports": []}
    n = ffr_contract.normalize_contract(c)
    with pytest.raises(ValueError, match="bkk"):
        ffr_contract.apply_shortlist(n, ["bkk"])
    s = ffr_contract.apply_shortlist(n, ["BKK"])
    with pytest.raises(ValueError, match="already"):
        ffr_contract.apply_shortlist(s, ["BKK"])
    with pytest.raises(ValueError, match="no region group"):
        ffr_contract.apply_shortlist(ffr_contract.normalize_contract(contract_v3()), ["BKK"])


def test_fill_confirm_cells():
    c = contract_v3(speed="fast")
    n = ffr_contract.normalize_contract(c)
    n["cells"] = ffr_contract.build_cells(n)
    f = ffr_contract.fill_confirm_cells(n, {"economy/ZZZ": [["2027-02-03", "2027-02-17"]]})
    assert [x for x in f["cells"] if x["id"] == "economy/confirm/ZZZ"][0]["tuples"] == [["2027-02-03", "2027-02-17"]]
    with pytest.raises(ValueError, match="economy/QQQ"):
        ffr_contract.fill_confirm_cells(n, {"economy/QQQ": []})
