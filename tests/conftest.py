"""Shared fixtures: a fake browser-act CLI on PATH (the real one is never run in tests)."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests" / "fake_browser_act.py"


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target = bin_dir / "browser-act"
    target.write_text(f"#!{sys.executable}\nimport runpy, sys\nsys.argv[0] = 'browser-act'\n"
                      f"runpy.run_path({str(FAKE)!r}, run_name='__main__')\n")
    target.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FFR_STATE", str(tmp_path / "state"))
    monkeypatch.delenv("BROWSERACT_API_KEY", raising=False)
    monkeypatch.delenv("FAKE_BA_CHROME_RUNNING", raising=False)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_BA_LOG", str(log))
    monkeypatch.setenv("FAKE_BA_COUNTER", str(tmp_path / "counter"))
    monkeypatch.setenv("FAKE_BA_SCENARIO", "nokey")

    def scenario(name, pages=()):
        monkeypatch.setenv("FAKE_BA_SCENARIO", name)
        monkeypatch.setenv("FAKE_BA_PAGES", ",".join(str(p) for p in pages))
        (tmp_path / "counter").write_text("0")

    def calls():
        return log.read_text().splitlines() if log.exists() else []

    return SimpleNamespace(scenario=scenario, calls=calls, state=tmp_path / "state", tmp=tmp_path)
