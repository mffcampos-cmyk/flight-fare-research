"""run_log.py v3 CLI: init, shortlist, confirm, add (fare, ground, attempt), resolve, coverage, rank, check, jobs."""
import json
import subprocess
import sys

import pytest

from tests.run_log_helpers import (ROOT, SCRIPT, contract_v3, group, leg, row_v3, leg_entry, ticket, ground,
                                   cli, write_json)

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import run_log  # noqa: E402

BASE = "economy/baseline/ZRH-ZZZ/2027-02-03_2027-02-17"


def attempt(outcome="blocked", family="edreams", **over):
    a = {"source": family, "family": family, "engine": "t", "outcome": outcome, "url": "https://e.test",
         "retrieved_at": "2027-01-08T10:00:00+00:00", "cabin": "economy", "hack": None,
         "origin": "ZRH", "destination": "ZZZ", "dates": ["2027-02-03", "2027-02-17"]}
    a.update(over)
    return a


def init(tmp_path, c=None, run_id="t3"):
    r = cli("init", "--contract", write_json(tmp_path / f"{run_id}.json", c or contract_v3(run_id=run_id)),
            "--runs-root", tmp_path / "runs")
    assert r.returncode == 0, r.stderr
    return tmp_path / "runs" / run_id, r.stdout


@pytest.fixture
def run(tmp_path):
    return init(tmp_path)[0]


def saved(run):
    return [json.loads(line) for line in (run / "rows.jsonl").read_text().splitlines()]


def region_contract():
    c = contract_v3(speed="fast", run_id="sea")
    c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    c["legs"][0]["to"] = {"name": "SE Asia", "region": True, "airports": []}
    return c


# init -------------------------------------------------------------------------------

def test_init_reports_tuples_and_cells(tmp_path):
    run, out = init(tmp_path)
    assert out.splitlines()[0] == str(run)
    assert "1 date tuple(s), 3 comparison cell(s), 0 not applicable" in out
    saved_contract = json.loads((run / "contract.json").read_text())
    assert saved_contract["shape"] == "return" and saved_contract["date_tuples"] == [["2027-02-03", "2027-02-17"]]


def test_init_reports_region_awaiting_shortlist(tmp_path):
    run, out = init(tmp_path, region_contract(), "sea")
    assert "1 region group(s) awaiting a shortlist" in out and "run_log.py shortlist" in out


def test_init_rejects_invalid_contract_and_existing_run(tmp_path):
    bad = contract_v3(); bad["legs"][1]["dates"] = {"fixed": "2027-02-01"}
    r = cli("init", "--contract", write_json(tmp_path / "bad.json", bad), "--runs-root", tmp_path / "runs")
    assert r.returncode == 2 and "leg 2" in r.stderr
    init(tmp_path)
    r = cli("init", "--contract", write_json(tmp_path / "t3.json", contract_v3()), "--runs-root", tmp_path / "runs")
    assert r.returncode == 2 and "already exists" in r.stderr


# shortlist and confirm --------------------------------------------------------------

def test_shortlist_then_coverage_shows_discover_cells(tmp_path):
    run, _ = init(tmp_path, region_contract(), "sea")
    assert "economy/discover  rows=0  region 'SE Asia' has no shortlist" in cli("coverage", "--run", run).stdout
    r = cli("shortlist", "--run", run, "BKK,SIN")
    assert r.returncode == 0 and "BKK, SIN" in r.stdout
    cov = cli("coverage", "--run", run).stdout
    assert "open     economy/discover/BKK" in cov and "open     economy/confirm/SIN" in cov
    assert json.loads((run / "contract.json").read_text())["legs"][1]["from"]["airports"][0]["code"] == "BKK"
    assert saved(run)[-1]["type"] == "contract" and saved(run)[-1]["shortlist"] == ["BKK", "SIN"]
    assert cli("shortlist", "--run", run, "KUL").returncode == 2


def test_confirm_fills_tuples_from_discover_rows(tmp_path):
    c = contract_v3(speed="fast"); c["legs"][0]["dates"] = {"range": {"from": "2027-02-01", "to": "2027-02-03"}}
    c["legs"][1]["dates"] = {"after_leg": {"leg": 1, "min_days": 14, "max_days": 14}}
    run, _ = init(tmp_path, c)
    assert cli("confirm", "--run", run).returncode == 2
    rows = [row_v3(phase="discover", source="flightlist", family="kiwi", dates=[f"2027-02-0{d}", f"2027-02-{d + 14}"],
                   tickets=[ticket(price=p, quote_state="list", baggage="unverified")],
                   legs=[leg_entry(1, dep=f"2027-02-0{d}T07:10:00", arr=f"2027-02-0{d}T09:05:00"),
                         leg_entry(2, dep=f"2027-02-{d + 14}T18:00:00", arr=f"2027-02-{d + 14}T22:00:00")])
            for d, p in ((1, 500.0), (2, 300.0), (3, 400.0))]
    assert cli("add", "--run", run, "--row", "-", input=json.dumps(rows)).returncode == 0
    r = cli("confirm", "--run", run, "--top", "2")
    assert r.returncode == 0 and "economy/confirm/ZZZ: 2027-02-02_2027-02-16, 2027-02-03_2027-02-17" in r.stdout
    cov = cli("coverage", "--run", run).stdout
    assert "done     economy/discover/ZZZ" in cov
    assert "open     economy/confirm/ZZZ  rows=0  tuples without an exact-date result: 2027-02-02_2027-02-16, 2027-02-03_2027-02-17" in cov


# add ----------------------------------------------------------------------------------

def test_add_accepts_fare_ground_and_attempt_rows_in_one_array(tmp_path):
    c = contract_v3(); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    run, _ = init(tmp_path, c)
    basel = row_v3(origin="BSL", legs=[leg_entry(1, **{"from": "BSL"}), leg_entry(2, to="BSL")])
    r = cli("add", "--run", run, "--row", "-", input=json.dumps([basel, ground(), attempt()]))
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["r1 lead: ground unpriced (BSL)", "g1 completed ZRH-BSL 2027-02-03 32.40 CHF",
                                     "r2 attempt"]
    assert [x["id"] for x in saved(run)] == ["r1", "g1", "r2"]
    r = cli("add", "--run", run, "--row", "-", input=json.dumps(ground(date="2027-02-17", **{"from": "BSL", "to": "ZRH"})))
    assert r.stdout.startswith("g2 completed BSL-ZRH")
    assert json.loads(cli("rank", "--run", run, "--json").stdout)["economy"]["best"] == 464.8


def test_add_refuses_whole_batch_when_one_row_is_invalid(run):
    bad = row_v3(legs=[leg_entry(1, stops="1 stop"), leg_entry(2)])
    r = cli("add", "--run", run, "--row", "-", input=json.dumps([row_v3(), bad, ground(to="QQQ")]))
    assert r.returncode == 2 and "row 2" in r.stderr and "row 3" in r.stderr
    assert (run / "rows.jsonl").read_text() == ""


def test_add_reads_json_lines_and_reports_reasons(run):
    text = json.dumps(row_v3()) + "\n" + json.dumps(row_v3(tickets=[ticket(quote_state="list")])) + "\n"
    r = cli("add", "--run", run, "--row", "-", input=text)
    assert r.returncode == 0 and r.stdout.splitlines() == ["r1 qualified", "r2 lead: list fare not repriced"]


@pytest.mark.parametrize("over,word", [
    ({"dates": ["2027-02-04", "2027-02-17"]}, "dates"), ({"cabin": "business"}, "cabin"),
    ({"origin": "CCC", "legs": [leg_entry(1, **{"from": "CCC"}), leg_entry(2)]}, "origin"),
    ({"supersedes": "r9"}, "r9"), ({"retrieved_at": "2027-01-08T14:03:00"}, "timezone"),
])
def test_add_refuses_rows_outside_the_contract(run, tmp_path, over, word):
    r = cli("add", "--run", run, "--row", write_json(tmp_path / "r.json", row_v3(**over)))
    assert r.returncode == 2 and word in r.stderr and (run / "rows.jsonl").read_text() == ""


# resolve, coverage, check --------------------------------------------------------------

def test_check_exit_codes_and_coverage(run, tmp_path):
    first = cli("check", "--run", run)
    assert first.returncode == 4 and first.stdout.startswith("INCOMPLETE: 3 open item(s)")
    assert "0/3 cells closed" in cli("coverage", "--run", run).stdout
    cli("add", "--run", run, "--row", "-", input=json.dumps([row_v3(), attempt()]))
    done = cli("check", "--run", run)
    assert done.returncode == 0 and done.stdout.startswith("COMPLETE")
    assert "WARN      economy: only one source family returned results (google)" in done.stdout


def test_resolve_is_guarded_and_appends_record(run, tmp_path):
    assert cli("resolve", "economy/hack/teleport", "--as", "na", "--reason", "x", "--run", run).returncode == 2
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", attempt()))
    r = cli("resolve", BASE, "--as", "no_fare", "--reason", "x", "--run", run)
    assert r.returncode == 2 and "no_fare" in r.stderr
    cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", attempt(outcome="empty", family="google")))
    assert cli("resolve", BASE, "--as", "no_fare", "--reason", "x", "--run", run).returncode == 0
    assert cli("resolve", "economy/reprice", "--as", "none_qualify", "--reason", "x", "--run", run).returncode == 2
    cli("add", "--run", run, "--row", write_json(tmp_path / "c.json", row_v3(tickets=[ticket(quote_state="list")])))
    assert cli("resolve", "economy/reprice", "--as", "none_qualify", "--reason", "all over cap", "--run", run).returncode == 0
    assert "RESOLVED  economy/reprice  none_qualify: all over cap" in cli("check", "--run", run).stdout


# rank ---------------------------------------------------------------------------------

def test_rank_text_shows_tuple_legs_seller_and_pruning(run, tmp_path):
    cli("add", "--run", run, "--row", "-", input=json.dumps([
        row_v3(), row_v3(tickets=[ticket(price=420.0, quote_state="list")]),
        row_v3(currency="SEK", tickets=[ticket(price=2100.0, quote_state="list")])]))
    text = cli("rank", "--run", run).stdout
    assert "1. r1 400.00 google-flights ZRH-ZZZ 2027-02-03/2027-02-17" in text
    assert "leg 1 2027-02-03 07:10 -> 2027-02-03 09:05  02:55  0 stops  XX" in text
    assert "seller: XX  book: https://example.test/book" in text
    assert "pruned: LB 420.00 >= best 400.00" in text and "LB 2100.00 SEK" in text
    assert "(+" not in cli("rank", "--run", run, "--top", "2").stdout
    assert "(+1 more leads)" in cli("rank", "--run", run, "--top", "1").stdout


def test_rank_json_carries_trip_details(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row_v3()))
    entry = json.loads(cli("rank", "--run", run, "--json").stdout)["economy"]["qualified"][0]
    assert (entry["origin"], entry["destination"], entry["dates"]) == ("ZRH", "ZZZ", ["2027-02-03", "2027-02-17"])
    assert entry["providers"] == ["XX"] and entry["legs"][0]["leg"] == 1 and entry["legs"][0]["duration"] == "02:55:00"


# jobs ---------------------------------------------------------------------------------

def test_jobs_plans_flightlist_sweeps_google_confirmation_and_kiwi_reprice(tmp_path):
    run, _ = init(tmp_path, region_contract(), "sea")
    cli("shortlist", "--run", run, "BKK,SIN")
    jobs = json.loads(cli("jobs", "--run", run, "--json").stdout)
    sessions = {j["session"]: j for j in jobs}
    assert {"ffr-flightlist-1", "ffr-flightlist-2"} <= set(sessions)
    fl = sessions["ffr-flightlist-1"]
    assert fl["source"] == "flightlist" and fl["family"] == "kiwi"
    assert "flightlist.py sweep --session ffr-flightlist-1 --run " in fl["commands"][0]
    assert "--cabin economy --from ZRH+BSL --to BKK" in fl["commands"][0] and "economy/discover/BKK" in fl["cells"]
    confirm = [j for j in jobs if j["source"] == "run_log"]
    assert confirm and "run_log.py confirm --run" in confirm[0]["commands"][0]
    text = cli("jobs", "--run", run).stdout
    assert "ffr-flightlist-1" in text and "references/source-ladder.md" in text


def test_jobs_google_runs_in_one_session_and_reprice_uses_kiwi_urls(tmp_path):
    c = contract_v3(speed="fast")
    run, _ = init(tmp_path, c)
    cli("add", "--run", run, "--row", "-", input=json.dumps([
        row_v3(phase="discover", source="flightlist", family="kiwi",
               tickets=[ticket(price=300.0, quote_state="list", baggage="unverified",
                               booking_url="https://www.kiwi.com/en/booking/fare-selection/abc")])]))
    cli("confirm", "--run", run)
    jobs = json.loads(cli("jobs", "--run", run, "--json").stdout)
    google = [j for j in jobs if j["source"] == "google-flights"]
    assert len(google) == 1 and google[0]["session"] == "ffr-google-1"
    assert "gflights.py sweep --session ffr-google-1 --run" in google[0]["commands"][0]
    assert "--cabins economy --origin ZRH --destination ZZZ --tuples 2027-02-03_2027-02-17" in google[0]["commands"][0]
    kiwi = [j for j in jobs if j["source"] == "kiwi"]
    assert kiwi and "kiwi.py fare --session ffr-kiwi-1 --run" in kiwi[0]["commands"][0]
    assert "--supersedes r1 https://www.kiwi.com/en/booking/fare-selection/abc" in kiwi[0]["commands"][0]


def test_jobs_thorough_baseline_goes_to_google_with_tuples(run):
    jobs = json.loads(cli("jobs", "--run", run, "--json").stdout)
    google = [j for j in jobs if j["source"] == "google-flights"][0]
    assert "--tuples 2027-02-03_2027-02-17" in google["commands"][0] and BASE in google["cells"]


# storage hardening (ported) --------------------------------------------------------------

def test_commands_report_the_run_they_used_and_default_to_most_recent(tmp_path):
    runs = tmp_path / "runs"
    for rid in ("aaa", "bbb"):
        init(tmp_path, contract_v3(run_id=rid), rid)
    cli("add", "--run", runs / "aaa", "--row", write_json(tmp_path / "r.json", row_v3()))
    assert f"run: {runs / 'aaa'}" in cli("check", env={"FFR_RUNS": str(runs)}).stderr


@pytest.mark.parametrize("cmd", [("check",), ("coverage",), ("rank",), ("add", "--row", "-"), ("jobs",)])
def test_commands_without_any_run_point_to_init(tmp_path, cmd):
    r = cli(*cmd, env={"FFR_RUNS": str(tmp_path / "empty")}, input="{}")
    assert r.returncode == 2 and "init" in r.stderr and "Traceback" not in r.stderr


def test_truncated_last_line_is_ignored_and_trimmed(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row_v3()))
    with open(run / "rows.jsonl", "a") as f:
        f.write('{"type": "row", "id": "r2", "sou')
    assert len(run_log.load_run(str(run))[1]) == 1
    assert cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", row_v3())).stdout.startswith("r2 ")
    assert len(run_log.load_run(str(run))[1]) == 2


def test_corrupt_middle_line_and_bad_hand_edited_row_exit_2(run):
    (run / "rows.jsonl").write_text('{broken\n{"type": "resolve", "cell": "economy/reprice", "as": "na", "reason": "x"}\n')
    assert cli("check", "--run", run).returncode == 2
    bad = dict(row_v3(legs=[leg_entry(1, stops="1 stop"), leg_entry(2)]), type="row", id="r1")
    (run / "rows.jsonl").write_text(json.dumps(bad) + "\n")
    r = cli("check", "--run", run)
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_concurrent_adds_get_unique_ids(run, tmp_path):
    f = write_json(tmp_path / "r.json", row_v3())
    procs = [subprocess.Popen([sys.executable, str(SCRIPT), "add", "--run", str(run), "--row", str(f)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(8)]
    for p in procs:
        p.wait()
    ids = [json.loads(line)["id"] for line in (run / "rows.jsonl").read_text().splitlines()]
    assert len(ids) == 8 and len(set(ids)) == 8


# review fixes: jobs per origin, no FlightList for multi-city --------------------------

def test_jobs_google_commands_carry_the_origin_per_baseline_cell(tmp_path):
    c = contract_v3(); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    run, _ = init(tmp_path, c)
    jobs = json.loads(cli("jobs", "--run", run, "--json").stdout)
    google = [j for j in jobs if j["source"] == "google-flights"][0]
    assert any("--origin ZRH --destination ZZZ" in cmd for cmd in google["commands"])
    assert any("--origin BSL --destination ZZZ" in cmd for cmd in google["commands"])
    assert "economy/baseline/BSL-ZZZ/2027-02-03_2027-02-17" in google["cells"]


def test_jobs_confirm_command_searches_every_origin_at_once(tmp_path):
    c = contract_v3(speed="fast"); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    run, _ = init(tmp_path, c)
    cli("add", "--run", run, "--row", "-", input=json.dumps([row_v3(phase="discover", source="flightlist", family="kiwi",
                                                                   tickets=[ticket(price=300.0, quote_state="list", baggage="unverified")])]))
    cli("confirm", "--run", run)
    google = [j for j in json.loads(cli("jobs", "--run", run, "--json").stdout) if j["source"] == "google-flights"][0]
    assert "--origin ZRH+BSL --destination ZZZ --tuples 2027-02-03_2027-02-17" in google["commands"][0]


def test_jobs_multi_city_gets_no_flightlist_sweep(tmp_path):
    c = contract_v3(speed="fast")
    c["legs"] = [leg("ZRH", "BKK", {"fixed": "2027-02-03"}), leg("BKK", "SIN", {"fixed": "2027-02-10"}),
                 leg("SIN", "ZRH", {"fixed": "2027-02-17"})]
    run, _ = init(tmp_path, c)
    jobs = json.loads(cli("jobs", "--run", run, "--json").stdout)
    assert not [j for j in jobs if j["source"] == "flightlist"]
    discover = [j for j in jobs if "economy/discover/BKK" in j["cells"]]
    assert discover and "multi-city" in discover[0]["commands"][0]
