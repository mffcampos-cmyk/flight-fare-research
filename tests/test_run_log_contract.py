import json
import pytest
from tests.run_log_helpers import run_log, contract, cli, write_json

POS = {"allowed": True, "rail_ok": True, "overnight_ok": False}

def test_valid_contract_has_no_errors():
    assert run_log.validate_contract(contract()) == []

@pytest.mark.parametrize("field", ["run_id", "scope", "trip_type", "currency", "origins",
                                   "destinations", "dates", "cabins", "bags", "travelers"])
def test_missing_required_field_is_reported(field):
    c = contract(); del c[field]
    assert any(field in e for e in run_log.validate_contract(c))

def test_adults_must_be_at_least_one():
    assert any("adults" in e for e in run_log.validate_contract(
        contract(travelers={"adults": 0, "children_ages": [], "infants": 0})))

def test_checked_bags_required():
    assert any("checked_per_person" in e for e in run_log.validate_contract(contract(bags={})))

@pytest.mark.parametrize("over", [{"scope": "medium"}, {"trip_type": "multi"},
                                  {"cabins": ["coach"]}, {"hacks": ["hidden_city"]},
                                  {"max_duration": {"value": "20h", "strict": True}},
                                  {"run_id": "Bad Id"}])
def test_invalid_values_are_reported(over):
    assert run_log.validate_contract(contract(**over)) != []

def test_rolling_dates_expand_to_matched_pairs():
    pairs = run_log.expand_dates({"rolling": {"first_outbound": "2026-03-05",
                                              "last_outbound": "2026-03-10", "trip_days": 10}}, "return")
    assert pairs == [["2026-03-05", "2026-03-15"], ["2026-03-06", "2026-03-16"],
                     ["2026-03-07", "2026-03-17"], ["2026-03-08", "2026-03-18"],
                     ["2026-03-09", "2026-03-19"], ["2026-03-10", "2026-03-20"]]

def test_rolling_dates_cross_year_boundary():
    assert run_log.expand_dates({"rolling": {"first_outbound": "2026-12-28",
                                             "last_outbound": "2026-12-29", "trip_days": 7}}, "return") == \
        [["2026-12-28", "2027-01-04"], ["2026-12-29", "2027-01-05"]]

def test_cartesian_requires_confirmation():
    c = contract(dates={"cartesian": {"outbound_from": "2026-11-05", "outbound_to": "2026-11-06",
                                      "return_from": "2026-11-12", "return_to": "2026-11-13"}})
    assert any("confirmed" in e for e in run_log.validate_contract(c))

def test_cartesian_expands_every_pair_when_confirmed():
    assert run_log.expand_dates({"cartesian": {"outbound_from": "2026-11-05", "outbound_to": "2026-11-06",
                                               "return_from": "2026-11-12", "return_to": "2026-11-13",
                                               "confirmed": True}}, "return") == \
        [["2026-11-05", "2026-11-12"], ["2026-11-05", "2026-11-13"],
         ["2026-11-06", "2026-11-12"], ["2026-11-06", "2026-11-13"]]

def test_cartesian_drops_returns_before_outbound():
    assert run_log.expand_dates({"cartesian": {"outbound_from": "2026-11-10", "outbound_to": "2026-11-12",
                                               "return_from": "2026-11-11", "return_to": "2026-11-11",
                                               "confirmed": True}}, "return") == \
        [["2026-11-10", "2026-11-11"], ["2026-11-11", "2026-11-11"]]

def test_one_way_dates_have_no_return():
    assert run_log.expand_dates({"outbound": ["2026-11-05"]}, "one_way") == [["2026-11-05", None]]

def test_quick_cells():
    cells = run_log.build_cells(contract())
    assert [c["id"] for c in cells] == ["economy/baseline/AAA-ZZZ/2026-11-05_2026-11-12",
                                        "economy/hack/nearby_origin", "economy/crosscheck", "economy/reprice"]
    assert cells[1]["auto"] == {"as": "na", "reason": "positioning not allowed"}

def test_quick_nearby_origin_needs_airports():
    cells = run_log.build_cells(contract(positioning=POS))
    assert cells[1]["auto"] == {"as": "na", "reason": "no nearby origins given"}
    cells = run_log.build_cells(contract(positioning=POS, nearby_origins=["BBB"]))
    assert cells[1]["auto"] is None

def test_full_cells_cover_pairs_origins_cabins_and_default_hacks():
    c = contract(scope="full", origins=["AAA", "CCC"], cabins=["economy", "business"],
                 dates={"rolling": {"first_outbound": "2026-11-05", "last_outbound": "2026-11-07", "trip_days": 7}},
                 alt_destinations=["YYY"], nearby_origins=["BBB"], positioning=POS)
    ids = [x["id"] for x in run_log.build_cells(c)]
    assert sum("/baseline/" in i for i in ids) == 3 * 2 * 2
    assert [i for i in ids if i.startswith("economy/hack/")] == [
        "economy/hack/split", "economy/hack/open_jaw", "economy/hack/nearby_origin", "economy/hack/alt_destination"]

def test_stopover_cell_only_when_requested():
    ids = [x["id"] for x in run_log.build_cells(contract(scope="full", hacks=["split", "stopover"]))]
    assert "economy/hack/stopover" in ids and "economy/hack/open_jaw" not in ids

def test_forbidden_hacks_auto_resolved_na():
    c = contract(scope="full", trip_type="one_way", dates={"outbound": ["2026-11-05"]})
    auto = {x["id"]: x["auto"] for x in run_log.build_cells(c)}
    assert auto["economy/baseline/AAA-ZZZ/2026-11-05"] is None
    assert auto["economy/hack/split"] == {"as": "na", "reason": "one-way trip"}
    assert auto["economy/hack/open_jaw"] == {"as": "na", "reason": "one-way trip"}
    assert auto["economy/hack/alt_destination"] == {"as": "na", "reason": "no alternative destinations"}

def test_init_writes_contract_and_empty_log(tmp_path):
    r = cli("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    assert r.returncode == 0, r.stderr
    d = tmp_path / "runs" / "t1"
    saved = json.loads((d / "contract.json").read_text())
    assert saved["date_pairs"] == [["2026-11-05", "2026-11-12"]] and len(saved["cells"]) == 4
    assert (d / "rows.jsonl").read_text() == ""

def test_init_fills_defaults(tmp_path):
    c = {k: v for k, v in contract(scope="full").items()
         if k not in ("nearby_origins", "alt_destinations", "max_duration", "positioning",
                      "self_transfer_ok", "event", "assumptions")}
    assert cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs").returncode == 0
    saved = json.loads((tmp_path / "runs" / "t1" / "contract.json").read_text())
    assert saved["max_duration"] is None and saved["positioning"]["allowed"] is False
    assert saved["self_transfer_ok"] is False
    assert saved["hacks"] == ["split", "open_jaw", "nearby_origin", "alt_destination"]

def test_init_rejects_invalid_contract(tmp_path):
    c = contract(); del c["cabins"]
    r = cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs")
    assert r.returncode == 2 and "cabins" in r.stderr
    assert not (tmp_path / "runs" / "t1").exists()

def test_init_refuses_existing_run(tmp_path):
    args = ("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    assert cli(*args).returncode == 0
    r = cli(*args)
    assert r.returncode == 2 and "exists" in r.stderr

def test_runs_root_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("FFR_RUNS", str(tmp_path / "a"))
    assert run_log.runs_root() == str(tmp_path / "a")
    monkeypatch.delenv("FFR_RUNS")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "x"))
    assert run_log.runs_root() == str(tmp_path / "x" / "flight-fare-research" / "runs")
    monkeypatch.delenv("XDG_STATE_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    assert run_log.runs_root() == str(tmp_path / "h" / ".local" / "state" / "flight-fare-research" / "runs")

def test_open_jaw_needs_another_airport():
    def auto(c):
        return {x["id"]: x["auto"] for x in run_log.build_cells(c)}["economy/hack/open_jaw"]
    assert auto(contract(scope="full")) == {"as": "na", "reason": "no other airport to open the jaw"}
    assert auto(contract(scope="full", nearby_origins=["BBB"])) == \
        {"as": "na", "reason": "no other airport to open the jaw"}
    assert auto(contract(scope="full", alt_destinations=["YYY"])) is None
    assert auto(contract(scope="full", nearby_origins=["BBB"], positioning=POS)) is None
