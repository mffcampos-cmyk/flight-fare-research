#!/usr/bin/env python3
"""BrowserAct driver for the flight-fare-research skill (stdlib only).

Wraps the `browser-act` CLI so every sweep shares one login check, one engine
choice, one session driver and one challenge policy. It never creates the
BrowserAct account, never prints an API key, never buys proxies or browsers.

  browseract.py status [--fresh] [--json]   installed? key? which engine? (cached 24 h)
  browseract.py engine [--host-tools a,b]   the highest rung available
  browseract.py close --all-mine            close every session named ffr-*

Engine ladder (references/browser-engines.md): browser-act-stealth (rung 1,
needs a key), browser-act (rung 2, local Chromium), the user's own browser
(rung 3: browser-act-chrome, claude-in-chrome, builtin-browser, cowork), then
a host headless tool (rung 4).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.dont_write_bytecode = True  # never leave __pycache__ inside the skill folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffr_contract import UsageError  # noqa: E402

ENGINES = ("browser-act-stealth", "browser-act", "browser-act-chrome", "claude-in-chrome", "builtin-browser",
           "cowork", "headless")
ENGINE_RUNG = {"browser-act-stealth": 1, "browser-act": 2, "browser-act-chrome": 3, "claude-in-chrome": 3,
               "builtin-browser": 3, "cowork": 3, "headless": 4}
OWN_BROWSER_ENGINES = ("browser-act-chrome", "claude-in-chrome", "builtin-browser", "cowork")
SESSION_PREFIX = "ffr-"
CACHE_HOURS = 24
STEALTH_FREE_QUOTA = 5
CHALLENGE = re.compile(r"unusual traffic|/sorry/|captcha|not a robot|are you a (?:robot|human)|access denied|"
                       r"press and hold|press-and-hold|verify you are human|just a moment|bot or not|"
                       r"was ist ein bot|bot oder mensch", re.I)
URL = re.compile(r"https?://\S+")
SIGNUP_HINT = ("BrowserAct account: not logged in. The free account unlocks stealth browsers, CAPTCHA solving "
               "and human handoff. Run `browser-act auth login`, open the URL it prints to create the account, "
               "then `browser-act auth poll`. Continuing on the local `chrome` browser meanwhile.")
INSTALL_HINT = ("BrowserAct CLI: not installed. With your OK I run `uv tool install browser-act-cli --python 3.12` "
                "(it downloads a package); until then the next rung of the ladder is used.")


def state_dir() -> str:
    if os.environ.get("FFR_STATE"):
        return os.environ["FFR_STATE"]
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(state, "flight-fare-research")


# --------------------------------------------------------------------------- cli wrapper

def binary() -> str | None:
    found = shutil.which("browser-act")
    if found:
        return found
    fallback = os.path.expanduser("~/.local/bin/browser-act")
    return fallback if os.path.exists(fallback) else None


def run_cli(args: list[str], *, timeout: int = 120, input: str | None = None) -> subprocess.CompletedProcess:
    """Run the browser-act CLI; raises UsageError when it is not installed or hangs."""
    path = binary()
    if not path:
        raise UsageError("browser-act CLI not found; see references/browser-engines.md")
    try:
        return subprocess.run([path, *args], capture_output=True, text=True, timeout=timeout, input=input)
    except subprocess.TimeoutExpired:
        raise UsageError(f"browser-act {' '.join(args[:3])} timed out after {timeout} s")
    except subprocess.SubprocessError as exc:
        raise UsageError(f"browser-act {' '.join(args[:3])} failed to run: {exc}")


def default_browser(engine: str | None) -> str:
    """The BrowserAct browser a session opens on: the stealth one on rung 1, the local one otherwise."""
    return "ffr-stealth" if engine == "browser-act-stealth" else "ffr"


# --------------------------------------------------------------------------- status

def _config_has_key(env) -> bool:
    home = env.get("HOME") or os.path.expanduser("~")
    candidates = [env.get("BROWSERACT_CONFIG")] if env.get("BROWSERACT_CONFIG") else []
    candidates += [os.path.join(home, ".config", "browser-act", "config.json"),
                   os.path.join(home, ".browser-act", "config.json")]
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("api_key"):
            return True
    return False


def _cache_path(directory: str | os.PathLike) -> str:
    return os.path.join(str(directory), "browseract-status.json")


def status(*, fresh: bool = False, runner=run_cli, env=None, state_dir: str | os.PathLike | None = None,
           now: datetime | None = None, host_tools: list[str] | None = None) -> dict:
    """Installed? logged in? which engine? One JSON-able dict, cached for 24 hours."""
    env = os.environ if env is None else env
    directory = str(state_dir or globals()["state_dir"]())
    now = now or datetime.now(timezone.utc)
    if not fresh:
        try:
            with open(_cache_path(directory), encoding="utf-8") as handle:
                cached = json.load(handle)
            checked = datetime.fromisoformat(cached["checked_at"])
            if now - checked < timedelta(hours=CACHE_HOURS):
                return cached
        except (OSError, ValueError, KeyError, TypeError):
            pass
    out = {"installed": False, "version": None, "api_key": None, "logged_in": False, "stealth_quota": None,
           "chrome_running": False, "engine": "headless", "checked_at": now.isoformat(timespec="seconds")}
    try:
        version = runner(["--version"])
    except UsageError:
        version = None
    if version is not None and version.returncode == 0:
        out["installed"] = True
        match = re.search(r"(\d+\.\d+\.\d+)", version.stdout)
        out["version"] = match.group(1) if match else version.stdout.strip() or None
        if env.get("BROWSERACT_API_KEY"):
            out["api_key"] = "env"
        elif _config_has_key(env):
            out["api_key"] = "config"
        else:
            poll = runner(["auth", "poll"])
            if poll.returncode == 0 and "registered" in poll.stdout.lower() and "not registered" not in poll.stdout.lower():
                out["api_key"] = "cli"
            else:
                probe = runner(["browser", "list", "--type", "stealth"])
                if probe.returncode == 0 and "api key" not in (probe.stdout + probe.stderr).lower():
                    out["api_key"] = "cli"
        out["logged_in"] = out["api_key"] is not None
        if out["logged_in"]:
            out["stealth_quota"] = STEALTH_FREE_QUOTA
        listing = runner(["browser", "list"])
        if listing.returncode == 0:
            try:
                browsers = json.loads(listing.stdout)
            except ValueError:
                browsers = []
            out["chrome_running"] = any(isinstance(b, dict) and b.get("type") == "chrome-direct" for b in browsers)
    out["engine"] = choose_engine(out, host_tools or [])
    try:
        os.makedirs(directory, exist_ok=True)
        with open(_cache_path(directory), "w", encoding="utf-8") as handle:
            json.dump(out, handle, indent=2)
    except OSError:
        pass
    return out


def choose_engine(state: dict, host_tools: list[str]) -> str:
    """The highest rung of the ladder this host offers."""
    if state.get("installed"):
        return "browser-act-stealth" if state.get("logged_in") else "browser-act"
    for engine in ("claude-in-chrome", "builtin-browser", "cowork"):
        if engine in host_tools:
            return engine
    return "headless"


def status_lines(state: dict) -> list[str]:
    """The intake message's browser lines."""
    lines = [f"Browser engine: {state['engine']} (rung {ENGINE_RUNG.get(state['engine'], 4)})"]
    if not state["installed"]:
        lines.append(INSTALL_HINT)
    elif state["logged_in"]:
        lines.append(f"BrowserAct account: logged in (key from {state['api_key']}); human handoff via remote-assist "
                     "is available on a challenge.")
    else:
        lines.append(SIGNUP_HINT)
    return lines


# --------------------------------------------------------------------------- sessions

class Session:
    """One BrowserAct session the agent opened itself. Names start with ffr-."""

    def __init__(self, name: str, browser: str | None = None, *, engine: str | None = None, runner=run_cli):
        if not name.startswith(SESSION_PREFIX) or name == SESSION_PREFIX:
            raise UsageError(f"session names start with {SESSION_PREFIX}<source>-<n>; never drive a session you did not open")
        self.name = name
        self.browser = browser or default_browser(engine)
        self.runner = runner

    def _call(self, args: list[str]) -> subprocess.CompletedProcess:
        try:
            return self.runner(args)
        except subprocess.TimeoutExpired:
            raise UsageError(f"browser-act {' '.join(args[2:4])} timed out (session {self.name})")
        except subprocess.SubprocessError as exc:
            raise UsageError(f"browser-act {' '.join(args[2:4])} failed to run: {exc}")

    def run(self, *args: str) -> str:
        result = self._call(["--session", self.name, *args])
        if result.returncode != 0:
            raise UsageError(f"browser-act {args[0]} failed: {(result.stderr or result.stdout).strip()[:300]}")
        return result.stdout

    def open(self, url: str, headed: bool = False) -> None:
        self.run("browser", "open", self.browser, url, *(["--headed"] if headed else []))

    def navigate(self, url: str) -> None:
        self.run("navigate", url)

    def read_markdown(self) -> str:
        return self.run("get", "markdown")

    def eval(self, js: str) -> str:
        return self.run("eval", js)

    def wait_for(self, pattern: str, *, timeout: float = 45, poll: float = 1.5, sleep=time.sleep) -> str | None:
        """The page text once `pattern` appears in it, or None after `timeout` seconds."""
        regex = re.compile(pattern, re.I | re.M)
        waited = 0.0
        text = self.read_markdown()
        while not regex.search(text):
            if waited >= timeout:
                return None
            sleep(poll)
            waited += poll
            text = self.read_markdown()
        return text

    def network_status(self, codes=("403", "429")) -> list[dict]:
        hits = []
        for code in codes:
            out = self.run("network", "requests", "--status", str(code))
            try:
                items = json.loads(out)
            except ValueError:
                items = [{"status": int(code), "url": line.strip()} for line in out.splitlines() if line.strip()]
            hits.extend(i if isinstance(i, dict) else {"status": int(code), "url": str(i)} for i in items)
        return hits

    def solve_captcha(self) -> bool:
        result = self._call(["--session", self.name, "solve-captcha"])
        return result.returncode == 0 and "solved=true" in result.stdout.lower()

    def remote_assist(self, objective: str) -> str | None:
        result = self._call(["--session", self.name, "remote-assist", "--objective", objective])
        match = URL.search(result.stdout)
        return match.group(0) if result.returncode == 0 and match else None

    def close(self) -> None:
        self._call(["session", "close", self.name])


def is_challenge(text: str, network: list[dict]) -> bool:
    if CHALLENGE.search(text[:8000]):
        return True
    return any(int(h.get("status") or 0) in (403, 429) for h in network)


def _wait_for_change(session: Session, timeout: float, poll: float = 10, sleep=time.sleep) -> bool:
    """True once the page no longer looks like a challenge."""
    waited = 0.0
    while waited < timeout:
        sleep(poll)
        waited += poll
        if not is_challenge(session.read_markdown(), []):
            return True
    return False


def handle_challenge(session: Session, *, logged_in: bool, user_reachable: bool, engine: str | None = None,
                     objective: str = "clear the site's check so the search can continue", notify=print,
                     wait_for_change=None, timeout: float = 600) -> str:
    """The challenge policy: solve once, hand off to a reachable human, else record blocked.

    Returns solved, assisted, user or blocked."""
    wait = wait_for_change or _wait_for_change
    if logged_in:
        if session.solve_captcha():
            return "solved"
        if user_reachable:
            url = session.remote_assist(objective)
            if url:
                notify(f"A site check needs a human. Open {url} on any device, complete it, and I continue in "
                       f"session {session.name}.")
                if wait(session, timeout):
                    return "assisted"
    if user_reachable and engine in OWN_BROWSER_ENGINES:
        notify(f"A site check appeared in your browser (session {session.name}). Please clear it; I continue "
               "when the page changes.")
        if wait(session, timeout):
            return "user"
    return "blocked"


def close_all_mine(runner=run_cli) -> list[str]:
    """Close every session named ffr-*; never another agent's."""
    listing = runner(["session", "list"])
    try:
        sessions = json.loads(listing.stdout)
    except ValueError:
        sessions = [{"name": line.split()[0]} for line in listing.stdout.splitlines() if line.strip()]
    closed = []
    for s in sessions:
        name = s.get("name") if isinstance(s, dict) else str(s)
        if name and name.startswith(SESSION_PREFIX):
            runner(["session", "close", name])
            closed.append(name)
    return closed


# --------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status", help="installed, logged in, engine (cached 24 h)")
    p.add_argument("--fresh", action="store_true", help="ignore the cached result")
    p.add_argument("--json", action="store_true")
    p.add_argument("--host-tools", default="", help="comma-separated host browser tools present")
    p = sub.add_parser("engine", help="print the highest rung available")
    p.add_argument("--host-tools", default="", help="comma-separated: claude-in-chrome,builtin-browser,cowork")
    p.add_argument("--fresh", action="store_true")
    p = sub.add_parser("close", help="close sessions")
    p.add_argument("--all-mine", action="store_true", required=True, help="every session named ffr-*")
    args = parser.parse_args(argv)
    try:
        tools = [t for t in getattr(args, "host_tools", "").split(",") if t]
        if args.cmd == "status":
            state = status(fresh=args.fresh, host_tools=tools)
            if args.json:
                print(json.dumps(state, indent=2))
            else:
                for line in status_lines(state):
                    print(line)
        elif args.cmd == "engine":
            print(choose_engine(status(fresh=args.fresh, host_tools=tools), tools))
        else:
            closed = close_all_mine()
            print("closed: " + (", ".join(closed) or "none"))
    except (UsageError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
