"""Exercise packaging and installation in disposable, network-free trees."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def cowork_placeholder():
    """A compliant hand-authored Cowork card for hermetic fixtures.

    Used only when the committed integrations/cowork/SKILL.md has not landed
    yet, so acceptance tests stay independent of that file's deploy state.
    """
    body = ("Quick full path connector browser baggage included fee required "
            "unverified range cookies decline duration 20:00:00 per direction "
            "retrieved timestamp currency conversion consent purchase CAPTCHA "
            "self-transfer risk research")
    count = len(body.split())
    tail = " ".join(["fare"] * (1700 - count))
    return ("---\nname: flight-fare-research\n"
            "description: Use when researching flights.\n---\n"
            + body + " " + tail + "\n")


@pytest.fixture
def project(tmp_path):
    repo = tmp_path / "repo with spaces"
    shutil.copytree(ROOT / "scripts", repo / "scripts")
    shutil.copytree(ROOT / "skill", repo / "skill")
    shutil.copytree(ROOT / "integrations", repo / "integrations")
    cowork = repo / "integrations/cowork/SKILL.md"
    if not cowork.is_file():
        cowork.parent.mkdir(parents=True, exist_ok=True)
        cowork.write_text(cowork_placeholder())
    return repo


def run_script(project, name, *args):
    return subprocess.run(
        [sys.executable, str(project / "scripts" / name), *args],
        cwd=project.parent, capture_output=True, text=True,
    )


@pytest.mark.parametrize("script", ["package.py", "validate.py"])
def test_missing_skill_entrypoint_fails_without_changing_copies(project, script):
    (project / "skill/SKILL.md").unlink()
    target = project / "integrations/claude-code/skills/flight-fare-research/SKILL.md"
    before = target.read_bytes()
    result = run_script(project, script)
    assert result.returncode != 0
    assert "SKILL.md" in result.stderr
    assert target.read_bytes() == before


def test_validator_rejects_matching_trees_without_skill_entrypoint(project):
    for entrypoint in project.rglob("SKILL.md"):
        entrypoint.unlink()
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode != 0
    assert "SKILL.md" in result.stderr


def tree_bytes(path):
    return {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}


def test_package_is_repeatable_and_removes_stale_files(project):
    target = project / "integrations/claude-code/skills/flight-fare-research"
    (target / "stale.txt").write_text("stale")
    for _ in range(2):
        result = run_script(project, "package.py")
        assert result.returncode == 0, result.stderr
        assert tree_bytes(target) == tree_bytes(project / "skill")
        result = run_script(project, "validate.py", "--strict")
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mutation,diagnostic", [
    ("missing", "missing file"), ("extra", "extra file"), ("changed", "SHA-256 mismatch"),
])
def test_validator_reports_copy_drift(project, mutation, diagnostic):
    target = project / "integrations/claude-code/skills/flight-fare-research"
    if mutation == "missing":
        (target / "SKILL.md").unlink()
    elif mutation == "extra":
        (target / "extra.txt").write_text("extra")
    else:
        (target / "SKILL.md").write_text("changed")
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 1
    assert diagnostic in result.stderr


def test_strict_validation_requires_hand_authored_artifacts(project):
    (project / "integrations/codex/AGENTS.md").unlink()
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 1
    assert "hand-authored artifact is missing" in result.stderr


@pytest.mark.parametrize("override", [False, True])
def test_hermes_install_is_repeatable_and_preserves_other_skills(project, tmp_path, override):
    home = tmp_path / "home"
    target = tmp_path / "custom skills" if override else home / ".hermes/skills"
    other = target / "other-skill/SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("keep me")
    destination = target / "flight-fare-research"
    destination.mkdir()
    (destination / "stale.txt").write_text("remove me")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("HERMES_SKILLS_DIR", "HERMES_HOME", "HERMES_SKILL_DIR_CATEGORY")
    }
    env["HOME"] = str(home)
    if override:
        env["HERMES_SKILLS_DIR"] = str(target)
    for _ in range(2):
        result = subprocess.run(
            ["bash", str(project / "integrations/hermes/install.sh")],
            cwd=tmp_path, env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert tree_bytes(destination) == tree_bytes(project / "skill")
        assert other.read_text() == "keep me"


def test_ci_installs_pytest_before_running_tests():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text()
    install = "python3 -m pip install pytest"
    assert install in workflow
    assert workflow.index(install) < workflow.index("python3 -m pytest")


def test_ci_secret_scan_fails_closed_on_grep_error():
    """The secret scan must report CLEAN only on a no-match (exit 1).

    A grep error (exit 2) must fail CI, never be treated as an empty scan, and
    the scanner must exclude only its own workflow file rather than wholesale
    .github (so it cannot self-match its regexp literals or skip real content).
    """
    workflow = (ROOT / ".github/workflows/validate.yml").read_text()
    assert "grep -RInE" in workflow
    # no-match is the ONLY clean path...
    assert 'if [ "$rc" -eq 1 ]; then' in workflow
    # ...a match fails CI...
    assert 'rc" -eq 0 ]; then' in workflow
    # ...and a grep error also fails CI (scan unverified, never "clean").
    assert "cannot confirm the tree is clean" in workflow
    # self-match avoidance: exclude only this workflow file, not whole .github.
    assert "--exclude=validate.yml" in workflow
    assert "--exclude-dir=.github" not in workflow
