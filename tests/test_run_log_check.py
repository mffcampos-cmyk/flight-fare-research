import pytest
from tests.run_log_helpers import run_log, contract, row, ticket, direction, records, cli, write_json

BASE = "economy/baseline/AAA-ZZZ/2026-11-05_2026-11-12"

def full(**over):
    c = contract(scope="full", hacks=["split"], **over)
    c["date_pairs"] = run_log.expand_dates(c["dates"], c["trip_type"]); c["cells"] = run_log.build_cells(c)
    return c

def quick():
    c = contract()
    c["date_pairs"] = run_log.expand_dates(c["dates"], c["trip_type"]); c["cells"] = run_log.build_cells(c)
    return c

def blocked(family="edreams"):
    return {"source": family, "family": family, "engine": "t", "outcome": "blocked", "url": "https://e.test",
            "retrieved_at": "2026-10-08T10:00:00+00:00", "cabin": "economy", "hack": None, "origin": "AAA",
            "destination": "ZZZ", "outbound_date": "2026-11-05", "return_date": "2026-11-12"}

def open_items(c, recs):
    return {o["cell"]: o["why"] for o in run_log.check(c, recs)["open"]}

def test_nothing_attempted():
    assert open_items(quick(), []) == {BASE: "not attempted", "economy/crosscheck": "0 source families attempted",
                                       "economy/reprice": "no qualified option"}

def test_blocked_only_cell_stays_open():
    assert open_items(quick(), records(blocked()))[BASE] == "only blocked/empty/error attempts"

def test_complete_quick_run_with_single_family_warning():
    result = run_log.check(quick(), records(row(), blocked()))
    assert result["complete"] is True and result["open"] == []
    assert result["warn"] == ["economy: only one source family returned results (google)"]
    assert {"cell": "economy/hack/nearby_origin", "why": "na: positioning not allowed"} in result["resolved"]

def test_warns_about_cheaper_unqualified_leads():
    recs = records(row(), row(family="edreams", source="edreams", tickets=[ticket(price=250.0, quote_state="list")]))
    result = run_log.check(quick(), recs)
    assert result["complete"] is True
    assert result["warn"] == ["economy: lead r2 may beat best qualified (LB 250.00 < 400.00)"]

def test_hack_cell_open_while_lead_could_win():
    recs = records(row(), row(hack="split", tickets=[ticket(price=300.0, quote_state="list")]), blocked())
    assert open_items(full(), recs) == {"economy/hack/split": "unresolved lead(s): r2"}

@pytest.mark.parametrize("hack_row", [
    row(hack="split", tickets=[ticket(price=420.0, quote_state="list")]),
    row(hack="split", directions=[direction("out", duration="23:00:00"), direction("ret")]),
    row(hack="split", tickets=[ticket(price=380.0)]),
])
def test_hack_cell_done_when_pruned_rejected_or_qualified(hack_row):
    assert open_items(full(), records(row(), hack_row, blocked())) == {}

def test_resolve_record_closes_cell():
    recs = records(row(), blocked()) + [{"type": "resolve", "cell": "economy/hack/split",
                                         "as": "no_fare", "reason": "no published fare returned"}]
    result = run_log.check(full(), recs)
    assert result["complete"] is True
    assert {"cell": "economy/hack/split", "why": "no_fare: no published fare returned"} in result["resolved"]

@pytest.fixture
def run(tmp_path):
    cli("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    return tmp_path / "runs" / "t1"

def test_end_to_end_quick_run(run, tmp_path):
    first = cli("check", "--run", run)
    assert first.returncode == 4 and first.stdout.startswith("INCOMPLETE: 3 open item(s)")
    assert "1/4 cells closed" in cli("coverage", "--run", run).stdout
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", blocked()))
    done = cli("check", "--run", run)
    assert done.returncode == 0 and done.stdout.startswith("COMPLETE")

def test_resolve_unknown_cell_is_usage_error(run):
    r = cli("resolve", "economy/hack/teleport", "--as", "na", "--reason", "x", "--run", run)
    assert r.returncode == 2

def test_resolve_appends_record(run, tmp_path):
    over_cap = row(directions=[direction("out", duration="21:00:00"), direction("ret")])
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", over_cap))
    assert cli("resolve", "economy/reprice", "--as", "none_qualify", "--reason", "all over cap", "--run", run).returncode == 0
    assert "RESOLVED  economy/reprice  none_qualify: all over cap" in cli("check", "--run", run).stdout

@pytest.mark.parametrize("cmd", [("check",), ("coverage",), ("rank",), ("add", "--row", "-")])
def test_commands_without_any_run_point_to_init(tmp_path, cmd):
    r = cli(*cmd, env={"FFR_RUNS": str(tmp_path / "empty")}, input="{}")
    assert r.returncode == 2 and "init" in r.stderr and "Traceback" not in r.stderr

def test_truncated_last_line_is_ignored_and_trimmed(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    with open(run / "rows.jsonl", "a") as f:
        f.write('{"type": "row", "id": "r2", "sou')
    assert len(run_log.load_run(str(run))[1]) == 1
    assert cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", row())).stdout.startswith("r2 ")
    assert len(run_log.load_run(str(run))[1]) == 2

def test_corrupt_middle_line_is_an_error(run):
    (run / "rows.jsonl").write_text('{broken\n{"type": "resolve", "cell": "economy/reprice", "as": "na", "reason": "x"}\n')
    assert cli("check", "--run", run).returncode == 2
