import json
from tests.run_log_helpers import run_log, contract, row, ticket, direction, records, cli, write_json

def test_qualified_ranked_by_all_in_then_duration():
    a = row(tickets=[ticket(price=500.0)])
    b = row(directions=[direction("out", duration="10:00:00"), direction("ret")])
    c = row()
    out = run_log.rank(contract(), records(a, b, c))["economy"]
    assert [q["id"] for q in out["qualified"]] == ["r3", "r2", "r1"] and out["best"] == 400.0

def test_leads_listed_with_reasons_and_bound():
    lead = run_log.rank(contract(), records(row(tickets=[ticket(price=300.0, quote_state="list")])))["economy"]["leads"][0]
    assert (lead["id"], lead["lower_bound"], lead["reasons"], lead["pruned"]) == \
        ("r1", 300.0, ["list fare not repriced"], False)

def test_lead_pruned_when_bound_reaches_best():
    recs = records(row(), row(hack="open_jaw", tickets=[ticket(price=420.0, quote_state="list")]),
                   row(hack="split", tickets=[ticket(price=400.0, quote_state="list")]))
    leads = {l["id"]: l["pruned"] for l in run_log.rank(contract(), recs)["economy"]["leads"]}
    assert leads == {"r2": True, "r3": True}

def test_pruned_lead_readmitted_when_best_superseded():
    lead = row(tickets=[ticket(price=450.0, quote_state="list")])
    assert run_log.rank(contract(), records(row(), lead))["economy"]["leads"][0]["pruned"] is True
    recs = records(row(), lead, row(supersedes="r1", tickets=[ticket(price=500.0)]))
    out = run_log.rank(contract(), recs)["economy"]
    assert out["best"] == 500.0 and out["leads"][0]["pruned"] is False

def test_rejected_rows_are_excluded():
    out = run_log.rank(contract(), records(row(directions=[direction("out", duration="22:00:00"), direction("ret")])))
    assert out["economy"]["qualified"] == [] and out["economy"]["leads"] == []

def test_rank_filters_by_cabin():
    c = contract(cabins=["economy", "business"])
    assert list(run_log.rank(c, records(row(), row(cabin="business")), cabin="business")) == ["business"]

def test_risk_flags():
    c = contract(positioning={"allowed": True, "rail_ok": True, "overnight_ok": True})
    r = row(cabin_label="Economy + Premium Economy", tickets=[ticket(), ticket()],
            directions=[direction("out", airport_change=True, stops=2), direction("ret")],
            components={"positioning": 45.0, "hotel": 90.0})
    assert run_log.risk_flags(r, c) == ["mixed cabin: Economy + Premium Economy", "airport change",
                                        "separate tickets", "2+ stops", "positioning", "hotel"]

def test_next_day_flag_uses_dates_not_clock_times():
    late = direction("out", dep="2026-11-05T23:30:00", arr="2026-11-06T01:10:00", duration="02:40:00")
    assert "next-day arrival" in run_log.risk_flags(row(directions=[late, direction("ret")]), contract())
    assert "next-day arrival" not in run_log.risk_flags(row(), contract())

def test_rank_cli_text_and_json(tmp_path):
    cli("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    run = tmp_path / "runs" / "t1"
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    cli("add", "--run", run, "--row", write_json(tmp_path / "b.json",
        row(hack="open_jaw", tickets=[ticket(price=420.0, quote_state="list")])))
    text = cli("rank", "--run", run)
    assert text.returncode == 0 and "pruned: LB 420.00 >= best 400.00" in text.stdout
    assert json.loads(cli("rank", "--run", run, "--json").stdout)["economy"]["best"] == 400.0
