"""Exercise packaging and installation in disposable, network-free trees."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    repo = tmp_path / "repo with spaces"
    shutil.copytree(ROOT / "scripts", repo / "scripts")
    shutil.copytree(ROOT / "skill", repo / "skill")
    shutil.copytree(ROOT / "integrations", repo / "integrations")
    shutil.copy(ROOT / "CHANGELOG.md", repo / "CHANGELOG.md")
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


def test_package_builds_deterministic_cowork_zip(project):
    assert run_script(project, "package.py").returncode == 0
    z = project / "dist/flight-fare-research-cowork.zip"
    first = z.read_bytes()
    assert run_script(project, "package.py").returncode == 0
    assert z.read_bytes() == first
    names = zipfile.ZipFile(z).namelist()
    assert names == sorted(names) and "flight-fare-research/SKILL.md" in names
    assert "flight-fare-research/scripts/run_log.py" in names
    assert {n.split("/", 1)[1] for n in names} == {str(p) for p in tree_bytes(project / "skill")}


def test_ci_installs_pinned_pytest_and_uploads_zip():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text()
    assert "python3 -m pip install 'pytest>=8,<10'" in workflow
    assert workflow.index("pip install 'pytest") < workflow.index("python3 -m pytest")
    assert "dist/flight-fare-research-cowork.zip" in workflow and "actions/upload-artifact@v4" in workflow


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
