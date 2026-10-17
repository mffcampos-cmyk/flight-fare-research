"""browseract.py: login check, engine ladder, session driver, challenge policy (spec section 7).

Every test drives tests/fake_browser_act.py installed as `browser-act` on PATH; the real CLI is never run."""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from tests.run_log_helpers import ROOT

sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import browseract  # noqa: E402

SCRIPT = ROOT / "skill" / "scripts" / "browseract.py"


def page(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


# status -------------------------------------------------------------------------------

def test_status_cli_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "nothing"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    s = browseract.status(state_dir=tmp_path / "state", fresh=True)
    assert s["installed"] is False and s["logged_in"] is False and s["api_key"] is None
    assert s["engine"] == "headless"
    assert browseract.choose_engine(s, ["claude-in-chrome"]) == "claude-in-chrome"


def test_status_no_key_reports_login_hint(fake_cli):
    s = browseract.status(state_dir=fake_cli.state, fresh=True)
    assert s["installed"] is True and s["version"] == "1.4.3"
    assert s["api_key"] is None and s["logged_in"] is False and s["engine"] == "browser-act"
    assert s["chrome_running"] is False
    assert any("auth poll" in c for c in fake_cli.calls())


def test_status_key_from_env(fake_cli, monkeypatch):
    monkeypatch.setenv("BROWSERACT_API_KEY", "ba-test-key")
    s = browseract.status(state_dir=fake_cli.state, fresh=True)
    assert s["api_key"] == "env" and s["logged_in"] is True and s["engine"] == "browser-act-stealth"
    assert not any("auth poll" in c for c in fake_cli.calls())
    assert "ba-test-key" not in json.dumps(s)


def test_status_key_from_config_file(fake_cli, monkeypatch):
    cfg = fake_cli.tmp / "home" / ".config" / "browser-act" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"api_key": "ba-file-key"}))
    s = browseract.status(state_dir=fake_cli.state, fresh=True)
    assert s["api_key"] == "config" and s["logged_in"] is True


def test_status_registered_without_local_key_counts_as_logged_in(fake_cli):
    fake_cli.scenario("key")
    s = browseract.status(state_dir=fake_cli.state, fresh=True)
    assert s["api_key"] == "cli" and s["logged_in"] is True and s["engine"] == "browser-act-stealth"


def test_status_detects_running_chrome(fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_BA_CHROME_RUNNING", "1")
    assert browseract.status(state_dir=fake_cli.state, fresh=True)["chrome_running"] is True


def test_status_cache_used_within_24h_and_ignored_after(fake_cli):
    first = browseract.status(state_dir=fake_cli.state, fresh=True)
    n = len(fake_cli.calls())
    again = browseract.status(state_dir=fake_cli.state)
    assert again == first and len(fake_cli.calls()) == n
    later = datetime.now(timezone.utc) + timedelta(hours=25)
    browseract.status(state_dir=fake_cli.state, now=later)
    assert len(fake_cli.calls()) > n


def test_choose_engine_ladder():
    installed = {"installed": True, "logged_in": True, "chrome_running": True}
    assert browseract.choose_engine(installed, ["claude-in-chrome"]) == "browser-act-stealth"
    assert browseract.choose_engine(dict(installed, logged_in=False), ["claude-in-chrome"]) == "browser-act"
    absent = {"installed": False, "logged_in": False, "chrome_running": False}
    assert browseract.choose_engine(absent, ["cowork", "builtin-browser", "claude-in-chrome"]) == "claude-in-chrome"
    assert browseract.choose_engine(absent, ["cowork", "builtin-browser"]) == "builtin-browser"
    assert browseract.choose_engine(absent, ["cowork"]) == "cowork"
    assert browseract.choose_engine(absent, []) == "headless"
    assert browseract.ENGINE_RUNG["browser-act-stealth"] == 1 and browseract.ENGINE_RUNG["browser-act-chrome"] == 3


# sessions -----------------------------------------------------------------------------

def test_session_wait_for_polls_until_pattern(fake_cli):
    loading = page(fake_cli.tmp, "loading.md", "Loading results\n")
    results = page(fake_cli.tmp, "results.md", "### Top departing flights\n* CHF 400\n")
    fake_cli.scenario("key", pages=[loading, loading, results])
    s = browseract.Session("ffr-test-1", browser="b-chrome")
    s.open("https://example.test/")
    slept = []
    text = s.wait_for(r"### Top departing flights", timeout=10, poll=1, sleep=slept.append)
    assert text and "CHF 400" in text and slept == [1, 1]
    assert any("--session ffr-test-1 browser open b-chrome https://example.test/" in c for c in fake_cli.calls())


def test_session_wait_for_times_out(fake_cli):
    loading = page(fake_cli.tmp, "loading.md", "Loading results\n")
    fake_cli.scenario("key", pages=[loading])
    s = browseract.Session("ffr-test-1")
    assert s.wait_for(r"priced", timeout=3, poll=1, sleep=lambda n: None) is None


def test_session_refuses_names_without_the_skill_prefix():
    with pytest.raises(browseract.UsageError, match="ffr-"):
        browseract.Session("ffr")


def test_is_challenge_detects_text_and_network_blocks():
    assert browseract.is_challenge("Our systems have detected unusual traffic", [])
    assert browseract.is_challenge("Just a moment... verifying you are not a bot", [])
    assert browseract.is_challenge("fine page", [{"status": 403, "url": "https://x/gql"}])
    assert not browseract.is_challenge("### Top departing flights", [])


# challenge policy ------------------------------------------------------------------

def test_handle_challenge_solve_once_then_remote_assist(fake_cli):
    fake_cli.scenario("challenge")
    s = browseract.Session("ffr-test-1")
    notes = []
    out = browseract.handle_challenge(s, logged_in=True, user_reachable=True, notify=notes.append,
                                      wait_for_change=lambda session, timeout: True)
    assert out == "assisted"
    assert sum("solve-captcha" in c for c in fake_cli.calls()) == 1
    assert any("https://assist.example/abc" in n for n in notes)


def test_handle_challenge_solved(fake_cli):
    fake_cli.scenario("solved")
    out = browseract.handle_challenge(browseract.Session("ffr-test-1"), logged_in=True, user_reachable=False)
    assert out == "solved" and not any("remote-assist" in c for c in fake_cli.calls())


def test_handle_challenge_assist_times_out_to_blocked(fake_cli):
    fake_cli.scenario("challenge")
    out = browseract.handle_challenge(browseract.Session("ffr-test-1"), logged_in=True, user_reachable=True,
                                      notify=lambda m: None, wait_for_change=lambda session, timeout: False)
    assert out == "blocked"


def test_handle_challenge_without_key_and_user_is_blocked(fake_cli):
    fake_cli.scenario("nokey")
    out = browseract.handle_challenge(browseract.Session("ffr-test-1"), logged_in=False, user_reachable=False)
    assert out == "blocked" and not any("solve-captcha" in c for c in fake_cli.calls())


def test_handle_challenge_user_watching_own_browser(fake_cli):
    fake_cli.scenario("nokey")
    notes = []
    out = browseract.handle_challenge(browseract.Session("ffr-test-1"), logged_in=False, user_reachable=True,
                                      engine="browser-act-chrome", notify=notes.append,
                                      wait_for_change=lambda session, timeout: True)
    assert out == "user" and notes and "clear" in notes[0].lower()
    assert not any("solve-captcha" in c for c in fake_cli.calls())


def test_close_all_mine_only_closes_ffr_sessions(fake_cli):
    assert browseract.close_all_mine() == ["ffr-google-1", "ffr-kiwi-1"]
    closed = [c for c in fake_cli.calls() if c.startswith("session close")]
    assert closed == ["session close ffr-google-1", "session close ffr-kiwi-1"]


# cli ----------------------------------------------------------------------------------

def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_cli_status_json_and_engine(fake_cli, monkeypatch):
    monkeypatch.setenv("FFR_STATE", str(fake_cli.state))
    r = run_cli("status", "--fresh", "--json")
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout)
    assert s["installed"] is True and s["logged_in"] is False and s["engine"] == "browser-act"
    r = run_cli("engine", "--host-tools", "claude-in-chrome")
    assert r.stdout.strip() == "browser-act"
    r = run_cli("status")
    assert "not logged in" in r.stdout and "browser-act auth login" in r.stdout


def test_cli_close_all_mine(fake_cli):
    r = run_cli("close", "--all-mine")
    assert r.returncode == 0 and "ffr-google-1" in r.stdout


# review fixes: the stealth browser is used when it is the engine; hung CLI calls -------

def test_default_browser_follows_the_engine():
    assert browseract.default_browser("browser-act-stealth") == "ffr-stealth"
    assert browseract.default_browser("browser-act") == "ffr"
    assert browseract.Session("ffr-x-1", engine="browser-act-stealth").browser == "ffr-stealth"
    assert browseract.Session("ffr-x-1", browser="mine", engine="browser-act-stealth").browser == "mine"


def test_hung_cli_call_is_a_usage_error_not_a_traceback():
    def hangs(args, **kw):
        raise subprocess.TimeoutExpired(cmd=args, timeout=120)
    with pytest.raises(browseract.UsageError, match="timed out"):
        browseract.Session("ffr-x-1", runner=hangs).read_markdown()
    with pytest.raises(browseract.UsageError, match="timed out"):
        browseract.Session("ffr-x-1", runner=hangs).solve_captcha()
