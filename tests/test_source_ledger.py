"""Contract tests for skill/scripts/source_ledger.py (no network, no live sites).

The ledger is runtime state: it must live outside the skill tree so installed or
read-only skill copies never change and raw probe evidence stays local.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "source_ledger.py"
CORE = ("google-flights", "flightlist", "edreams", "tap-direct", "ita-matrix")


def run(*args, env_extra=None, ledger=None):
    env = {k: v for k, v in os.environ.items() if k not in ("FFR_LEDGER", "XDG_STATE_HOME")}
    env.update(env_extra or {})
    cmd = [sys.executable, str(SCRIPT)]
    if ledger is not None:
        cmd += ["--ledger", str(ledger)]
    p = subprocess.run(cmd + list(args), capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr


@pytest.fixture
def ledger(tmp_path):
    return tmp_path / "status.json"


def record_all_ok(ledger):
    for sid in CORE:
        rc, _, err = run("record", sid, "ok", "--evidence", "canary", "--results", "5", ledger=ledger)
        assert rc == 0, err


def test_canary_contract_is_fixed():
    rc, out, _ = run("canary", "--today", "2026-10-03")
    assert rc == 0
    c = json.loads(out)
    assert (c["origin"], c["destination"]) == ("ZRH", "LIS")
    assert (c["depart"], c["return"]) == ("2026-11-02", "2026-11-09")
    assert (c["adults"], c["cabin"], c["currency"]) == (1, "economy", "CHF")


def test_default_ledger_uses_xdg_state_home_not_skill_tree(tmp_path):
    rc, _, _ = run("status", env_extra={"XDG_STATE_HOME": str(tmp_path), "HOME": str(tmp_path)})
    assert rc == 3
    assert (tmp_path / "flight-fare-research" / "source-status.json").is_file()
    assert not (ROOT / "skill" / "assets").exists()


def test_default_ledger_falls_back_to_home_local_state(tmp_path):
    run("status", env_extra={"HOME": str(tmp_path)})
    assert (tmp_path / ".local" / "state" / "flight-fare-research" / "source-status.json").is_file()


def test_ffr_ledger_env_overrides_default(tmp_path):
    target = tmp_path / "custom.json"
    run("status", env_extra={"FFR_LEDGER": str(target), "HOME": str(tmp_path)})
    assert target.is_file()


def test_missing_ledger_is_seeded_and_stale(ledger):
    rc, out, _ = run("status", ledger=ledger)
    assert rc == 3
    assert ledger.is_file()
    assert "google-flights" in out


def test_corrupt_ledger_reseeds(ledger):
    ledger.write_text("{not json")
    rc, _, err = run("status", ledger=ledger)
    assert rc == 3
    assert "reseed" in err.lower()


def test_ok_requires_result_count(ledger):
    rc, _, err = run("record", "edreams", "ok", "--evidence", "x", ledger=ledger)
    assert rc == 2
    assert "--results" in err


def test_unknown_source_is_rejected(ledger):
    rc, _, _ = run("record", "nope", "blocked", "--evidence", "x", ledger=ledger)
    assert rc == 2


def test_fresh_after_all_core_sources_recorded(ledger):
    record_all_ok(ledger)
    rc, out, _ = run("status", ledger=ledger)
    assert rc == 0, out


def test_blocked_core_source_is_fresh_but_ordered_out(ledger):
    record_all_ok(ledger)
    run("record", "ita-matrix", "blocked", "--evidence", "results shell empty", ledger=ledger)
    assert run("status", ledger=ledger)[0] == 0
    order = json.loads(run("order", "--json", ledger=ledger)[1])
    assert [s["id"] for s in order["use"]][:2] == ["flightlist", "google-flights"]
    assert "ita-matrix" in [s["id"] for s in order["avoid"]]


def test_record_older_than_max_age_is_stale(ledger):
    record_all_ok(ledger)
    data = json.loads(ledger.read_text())
    data["sources"]["edreams"]["checked_at"] = (
        datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    ledger.write_text(json.dumps(data))
    rc, out, _ = run("status", ledger=ledger)
    assert rc == 3
    assert "edreams" in out


def test_history_is_capped(ledger):
    for i in range(8):
        run("record", "azair", "partial", "--evidence", f"r{i}", ledger=ledger)
    assert len(json.loads(ledger.read_text())["sources"]["azair"]["history"]) == 5


CANDIDATES = {"lastminute", "gotogate", "aviasales", "opodo", "momondo", "trip-com", "expedia",
              "swiss-direct", "lufthansa-direct", "easyjet-direct", "ryanair-direct", "vueling-direct",
              "iberia-direct", "klm-direct", "airfrance-direct", "british-airways-direct", "turkish-direct",
              "icelandair-direct", "qatar-direct", "sbb", "trainline", "omio", "flightconnections"}

def test_record_stores_engine(ledger):
    run("record", "edreams", "blocked", "--evidence", "x", "--engine", "headless-playwright", ledger=ledger)
    src = json.loads(ledger.read_text())["sources"]["edreams"]
    assert src["engine"] == "headless-playwright" and src["history"][0]["engine"] == "headless-playwright"
    assert "headless-playwright" in run("status", ledger=ledger)[1]

def test_order_json_includes_engine(ledger):
    run("record", "edreams", "ok", "--results", "3", "--evidence", "x", "--engine", "claude-in-chrome", ledger=ledger)
    use = json.loads(run("order", "--json", ledger=ledger)[1])["use"]
    assert next(s for s in use if s["id"] == "edreams")["engine"] == "claude-in-chrome"

def test_add_registers_new_source(ledger):
    rc, _, err = run("record", "condor-direct", "ok", "--results", "3", "--evidence", "x", "--add",
                     "--name", "Condor", "--role", "airline", "--family", "condor",
                     "--url", "https://www.condor.com/", ledger=ledger)
    assert rc == 0, err
    src = json.loads(ledger.read_text())["sources"]["condor-direct"]
    assert (src["name"], src["role"], src["family"], src["core"], src["state"]) == \
        ("Condor", "airline", "condor", False, "ok")

def test_add_requires_name_role_family(ledger):
    assert run("record", "x-direct", "ok", "--results", "1", "--evidence", "x", "--add",
               "--name", "X", "--role", "airline", ledger=ledger)[0] == 2

def test_add_refuses_existing_id(ledger):
    rc, _, err = run("record", "edreams", "ok", "--results", "1", "--evidence", "x", "--add",
                     "--name", "E", "--role", "ota", "--family", "edreams", ledger=ledger)
    assert rc == 2 and "already" in err

def test_candidates_registered_untested(ledger):
    order = json.loads(run("order", "--json", ledger=ledger)[1])
    assert CANDIDATES <= {u["id"] for u in order["untested"]}

def test_candidate_families_and_roles(ledger):
    run("status", ledger=ledger)
    src = json.loads(ledger.read_text())["sources"]
    assert src["opodo"]["family"] == "edreams" and src["momondo"]["family"] == "kayak"
    assert src["sbb"]["role"] == "positioning" and src["flightconnections"]["role"] == "routes"

def test_naive_timestamp_treated_as_utc(ledger):
    run("status", ledger=ledger)
    data = json.loads(ledger.read_text())
    data["sources"]["edreams"]["checked_at"] = "2026-10-01T12:00:00"
    ledger.write_text(json.dumps(data))
    rc, _, err = run("status", ledger=ledger)
    assert rc in (0, 3) and "Traceback" not in err
