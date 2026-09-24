"""Acceptance checks exercise the CLI on isolated, regenerated fixtures."""
import json
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
    plugin.write_text('{"name": "flight-fare-research",'
                      ' "description": "desc", "version": "1.2.3"}')
    result = validate(project)
    assert result.returncode == 0, result.stderr
