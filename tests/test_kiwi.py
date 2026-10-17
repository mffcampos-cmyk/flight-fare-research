"""kiwi.py: the Kiwi.com fare-selection page to a completed row (spec section 8).

The fixture is synthetic (labelled in the file): modelled on the families and amounts seen on 2026-10-09."""
import json
import subprocess
import sys
from pathlib import Path

from tests.run_log_helpers import ROOT, contract_v3, leg, row_v3, leg_entry, ticket, cli, write_json

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import kiwi  # noqa: E402

KW = ROOT / "skill" / "scripts" / "kiwi.py"
FIX = Path(__file__).parent / "fixtures" / "kiwi" / "fare_selection.md"
URL = "https://www.kiwi.com/en/booking/fare-selection/abc123"


def page():
    return FIX.read_text(encoding="utf-8")


def test_parse_fares_reads_families_prices_and_bags():
    fares = kiwi.parse_fares(page())
    assert [(f["family"], f["price"], f["currency"], f["checked_bag"], f["cabin_bag"]) for f in fares] == [
        ("Light", 1555.26, "CHF", False, True), ("Standard", 1923.08, "CHF", True, True), ("Flex", 2131.25, "CHF", True, True)]


def test_parse_fares_returns_nothing_for_a_challenge_or_shell():
    assert kiwi.parse_fares("Are you a robot?\n") == []
    assert kiwi.parse_fares("# Choose your fare\nLoading\n") == []


def test_pick_family_cheapest_with_bag_when_bags_requested():
    fares = kiwi.parse_fares(page())
    assert kiwi.pick_family(fares, 1)["family"] == "Standard"
    assert kiwi.pick_family(fares, 0)["family"] == "Light"
    assert kiwi.pick_family([f for f in fares if not f["checked_bag"]], 1) is None


def list_row():
    return dict(row_v3(source="flightlist", family="kiwi", phase="discover",
                       tickets=[ticket(price=1750.91, quote_state="list", baggage="unverified", provider="Kiwi.com (via FlightList)",
                                       booking_url=URL)]), id="r1", type="row")


def test_completed_row_supersedes_and_keeps_legs():
    fare = kiwi.pick_family(kiwi.parse_fares(page()), 1)
    row = kiwi.completed_row(list_row(), fare, URL, "browser-act-stealth")
    assert row["supersedes"] == "r1" and row["source"] == "kiwi" and row["family"] == "kiwi"
    assert row["engine"] == "browser-act-stealth" and row["url"] == URL and row["phase"] == "exact"
    assert row["legs"] == list_row()["legs"] and row["dates"] == ["2027-02-03", "2027-02-17"]
    t = row["tickets"][0]
    assert (t["price"], t["quote_state"], t["provider"], t["baggage"], t["bag_fee"], t["booking_url"]) == \
        (1923.08, "completed", "Kiwi.com", "included", None, URL)
    assert "Standard" in row["notes"] and row["currency"] == "CHF"
    assert "retrieved_at" in row and row["retrieved_at"] != list_row()["retrieved_at"]
    light = kiwi.completed_row(list_row(), kiwi.parse_fares(page())[0], URL, "t")
    assert light["tickets"][0]["baggage"] == "fee_required" and light["tickets"][0]["bag_fee"] is None


def test_cli_fare_adds_completed_row(tmp_path, fake_cli):
    r = cli("init", "--contract", write_json(tmp_path / "c.json", contract_v3()), "--runs-root", tmp_path / "runs")
    assert r.returncode == 0, r.stderr
    run = tmp_path / "runs" / "t3"
    assert cli("add", "--run", run, "--row", "-", input=json.dumps(
        {k: v for k, v in list_row().items() if k not in ("id", "type")})).returncode == 0
    fake_cli.scenario("key", pages=[FIX])
    r = subprocess.run([sys.executable, "-B", str(KW), "fare", "--session", "ffr-kiwi-1", "--run", str(run),
                        "--supersedes", "r1", URL], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "r2 qualified" in r.stdout
    ranked = json.loads(cli("rank", "--run", run, "--json").stdout)["economy"]
    assert ranked["best"] == 1923.08 and ranked["qualified"][0]["id"] == "r2"
    assert any("navigate " + URL in c for c in fake_cli.calls())


def test_cli_fare_refuses_unknown_row_and_user_session(tmp_path, fake_cli):
    r = subprocess.run([sys.executable, "-B", str(KW), "fare", "--session", "ffr", "--run", str(tmp_path),
                        "--supersedes", "r1", URL], capture_output=True, text=True)
    assert r.returncode == 2 and "ffr-" in r.stderr
    cli("init", "--contract", write_json(tmp_path / "c.json", contract_v3()), "--runs-root", tmp_path / "runs")
    fake_cli.scenario("key", pages=[FIX])
    r = subprocess.run([sys.executable, "-B", str(KW), "fare", "--session", "ffr-kiwi-1",
                        "--run", str(tmp_path / "runs" / "t3"), "--supersedes", "r9", URL], capture_output=True, text=True)
    assert r.returncode == 2 and "r9" in r.stderr
