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
    no_cache = shutil.ignore_patterns("__pycache__", "*.pyc")  # a stray cache on the dev machine is not the skill
    shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=no_cache)
    shutil.copytree(ROOT / "skill", repo / "skill", ignore=no_cache)
    shutil.copytree(ROOT / "integrations", repo / "integrations", ignore=no_cache)
    shutil.copy(ROOT / "CHANGELOG.md", repo / "CHANGELOG.md")
    return repo


def run_script(project, name, *args):
    return subprocess.run(
        [sys.executable, str(project / "scripts" / name), *args],
        cwd=project.parent, capture_output=True, text=True,
    )


@pytest.mark.parametrize("script", ["package.py", "validate.py"])
def test_missing_skill_entrypoint_fails(project, script):
    (project / "skill/SKILL.md").unlink()
    result = run_script(project, script)
    assert result.returncode != 0
    assert "SKILL.md" in result.stderr
    assert not (project / "dist").exists()


def tree_bytes(path):
    return {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}


CLAUDE_SKILL = "dist/claude-code/skills/flight-fare-research"
CODEX_SKILL = "dist/codex/.agents/skills/flight-fare-research"


def test_package_builds_dist_trees_and_zip(project):
    result = run_script(project, "package.py")
    assert result.returncode == 0, result.stderr
    assert (project / "dist/claude-code/.claude-plugin/plugin.json").is_file()
    assert (project / CLAUDE_SKILL / "SKILL.md").is_file()
    assert (project / "dist/codex/AGENTS.md").is_file()
    assert (project / CODEX_SKILL / "scripts/run_log.py").is_file()
    assert tree_bytes(project / CLAUDE_SKILL) == tree_bytes(project / "skill")
    assert tree_bytes(project / CODEX_SKILL) == tree_bytes(project / "skill")
    names = zipfile.ZipFile(project / "dist/flight-fare-research-cowork.zip").namelist()
    assert names and all(n.startswith("flight-fare-research/") for n in names)


def test_package_is_repeatable_and_removes_stale_files(project):
    assert run_script(project, "package.py").returncode == 0
    stale = project / CLAUDE_SKILL / "stale.txt"
    stale.write_text("stale")
    result = run_script(project, "package.py")
    assert result.returncode == 0, result.stderr
    assert not stale.exists()
    assert run_script(project, "validate.py", "--strict").returncode == 0


def test_validate_passes_without_dist_and_fails_on_stale_dist(project):
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 0, result.stderr
    assert run_script(project, "package.py").returncode == 0
    (project / "skill/references/intake.md").write_text("changed\n")
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode != 0
    assert "dist" in result.stderr


def test_strict_validation_requires_hand_authored_artifacts(project):
    (project / "integrations/codex/AGENTS.md").unlink()
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 1
    assert "hand-authored artifact is missing" in result.stderr


def test_library_modules_are_not_run_with_help(project):
    (project / "skill/scripts/ffr_lib.py").write_text("X = 1\n")
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 0, result.stderr


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


def test_ci_installs_dev_requirements_and_uploads_dist():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text()
    assert "pip install -r requirements-dev.txt" in workflow
    assert workflow.index("requirements-dev.txt") < workflow.index("python3 -m pytest")
    assert "dist/flight-fare-research-cowork.zip" in workflow and "actions/upload-artifact@v4" in workflow
    assert "flight-fare-research-dist" in workflow
    assert "packaging drift" not in workflow
    assert "pytest>=8,<10" in (ROOT / "requirements-dev.txt").read_text()
    assert not (ROOT / "integrations/claude-code/skills").exists()
    assert not (ROOT / "integrations/codex/.agents").exists()


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
