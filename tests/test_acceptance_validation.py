"""Acceptance checks exercise the CLI on isolated, regenerated fixtures."""
import json
import zipfile

import pytest
from tests.test_packaging import project, run_script


def validate(project):
    result = run_script(project, "package.py")
    assert result.returncode == 0, result.stderr
    return run_script(project, "validate.py", "--strict")


@pytest.mark.parametrize("frontmatter", [
    "", "---\nname: flight-fare-research\n",
    "---\nname: Wrong_Name\ndescription: valid\n---\n",
    "---\nname: flight-fare-research\n---\n",
    "---\nname: flight-fare-research\ndescription: ''\n---\n",
    "---\nname: flight-fare-research\ndescription: []\n---\n",
    "---\nname: flight-fare-research\nname: duplicate\ndescription: valid\n---\n",
    "---\nname: flight-fare-research\ndescription: " + "x" * 1025 + "\n---\n",
])
def test_invalid_frontmatter_fails_even_when_copies_match(project, frontmatter):
    (project / "skill/SKILL.md").write_text(frontmatter + "# Body\n")
    result = validate(project)
    assert result.returncode == 1
    assert "frontmatter" in result.stderr


def test_valid_canonical_structure(project):
    result = validate(project)
    assert result.returncode == 0, result.stderr


def test_reference_from_skill_points_outside_skill_root(project):
    # bare `references/...` written from the SKILL.md resolves against the skill
    # root, so a dangling internal link must fail even when copies match.
    sk = project / "skill/SKILL.md"
    text = sk.read_text()
    text = text.replace("`references/source-ladder.md`", "`references/nope-not-here.md`")
    (sk).write_text(text)
    result = validate(project)
    assert result.returncode == 1
    assert "does not resolve" in result.stderr


def test_reference_in_reference_file_resolves_relative_to_skill_root(project):
    # a `references/foo.md` mention from within a reference file still resolves
    # against the skill root, matching the canonical-backtick semantics.
    ref = project / "skill/references/azair-browser.md"
    ref.write_text(ref.read_text() + "\nSee `references/source-ladder.md`.\n")
    result = validate(project)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("body", [
    "{}",
    '{"name": "x"}',
    '{"name": "x", "description": "d"}',
    '{"name": "x", "description": "d", "version": "1"}',
    '{"name": "x", "description": "d", "version": "1.2.3a"}',
    '{"name": "x", "description": "d", "version": 3}',
    'not json at all',
    '{"description": "d", "version": "1.2.3"}',
])
def test_invalid_claude_plugin_schema_fails(project, body):
    plugin = project / "integrations/claude-code/.claude-plugin/plugin.json"
    plugin.write_text(body)
    result = validate(project)
    assert result.returncode == 1
    assert "plugin.json" in result.stderr


def test_valid_claude_plugin_schema_passes(project):
    plugin = project / "integrations/claude-code/.claude-plugin/plugin.json"
    import re
    version = re.search(r"^version: (\S+)$", (project / "skill/SKILL.md").read_text(), re.M).group(1)
    plugin.write_text(json.dumps({"name": "flight-fare-research", "description": "desc", "version": version}))
    result = validate(project)
    assert result.returncode == 0, result.stderr


def test_version_mismatch_fails(project):
    plugin = project / "integrations/claude-code/.claude-plugin/plugin.json"
    data = json.loads(plugin.read_text()); data["version"] = "9.9.9"
    plugin.write_text(json.dumps(data))
    result = validate(project)
    assert result.returncode == 1 and "version" in result.stderr and "9.9.9" in result.stderr


def test_broken_script_fails(project):
    (project / "skill/scripts/run_log.py").write_text("def broken(:\n")
    result = validate(project)
    assert result.returncode == 1 and "run_log.py" in result.stderr


def test_zip_drift_fails(project):
    assert run_script(project, "package.py").returncode == 0
    for base in ("skill", "integrations/codex/.agents/skills/flight-fare-research",
                 "integrations/claude-code/skills/flight-fare-research"):
        (project / base / "references/azair-browser.md").write_text("changed")
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 1 and "zip" in result.stderr


def test_bytecode_is_never_packaged(project):
    (project / "skill/scripts/__pycache__").mkdir()
    (project / "skill/scripts/__pycache__/run_log.cpython-313.pyc").write_bytes(b"x")
    assert run_script(project, "package.py").returncode == 0
    names = zipfile.ZipFile(project / "dist/flight-fare-research-cowork.zip").namelist()
    assert not any("__pycache__" in n for n in names)
    assert not (project / "integrations/claude-code/skills/flight-fare-research/scripts/__pycache__").exists()
    assert run_script(project, "validate.py", "--strict").returncode == 0


def test_skill_body_word_budget(project):
    sk = project / "skill/SKILL.md"
    sk.write_text(sk.read_text() + "\n" + "word " * 2001)
    result = validate(project)
    assert result.returncode == 1 and "word budget" in result.stderr
