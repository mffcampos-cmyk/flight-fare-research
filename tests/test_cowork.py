"""Contract tests for the hand-authored, single-file Cowork variant."""
from pathlib import Path
import sys

import pytest

from tests.test_packaging import project, run_script

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate

COWORK = Path("integrations/cowork/SKILL.md")


def standalone_text(words=1600):
    """Synthetic prose for structural checks; never represented as live fares."""
    header = "---\nname: flight-fare-research\ndescription: Use when researching flights.\n---\n"
    body = "Quick full connector browser baggage included fee required unverified range airline cookies decline duration 20:00:00 per direction retrieved timestamp currency conversion consent purchase CAPTCHA self-transfer risk."
    return header + body + " research" * (words - len(body.split()))


def test_cowork_word_count_is_bounded(tmp_path):
    entry = tmp_path / "SKILL.md"
    for words in (1499, 1500, 2000, 2378, 2600, 2601):
        entry.write_text(standalone_text(words))
        errors = validate.validate_cowork(entry)
        assert any("word count" in error for error in errors) == (words < 1500 or words > 2600)



@pytest.mark.parametrize("dependency", [
    "Load `references/source-ladder.md` first.",
    "Load the browser-act skill first.",
    "Call js() before reading results.",
    "Use cdp(\"Input.insertText\").",
    "Load grounded-citations first.",
    "Read [details](../../skill/SKILL.md).",
])
def test_cowork_rejects_external_skill_and_tool_dependencies(tmp_path, dependency):
    entry = tmp_path / "SKILL.md"
    entry.write_text(standalone_text() + "\n" + dependency)
    assert any("standalone" in error for error in validate.validate_cowork(entry))


def test_cowork_rejects_reference_directory(tmp_path):
    entry = tmp_path / "SKILL.md"
    entry.write_text(standalone_text())
    (tmp_path / "references").mkdir()
    assert any("standalone" in error for error in validate.validate_cowork(entry))


def test_cowork_content_errors_fail_even_in_non_strict_mode(project):
    # Wiring: when the card is present but non-compliant, lint runs in BOTH
    # modes, so a too-short card cannot ride the optional PENDING status.
    card = project / COWORK
    card.write_text("---\nname: flight-fare-research\ndescription: d\n---\nshort\n")
    result = run_script(project, "validate.py")
    assert result.returncode == 1
    assert "word count" in result.stderr


def test_cowork_is_optional_until_present_but_required_in_strict_mode(project):
    (project / COWORK).unlink(missing_ok=True)
    assert run_script(project, "package.py").returncode == 0
    result = run_script(project, "validate.py")
    assert result.returncode == 0, result.stderr
    assert "PENDING" in result.stdout and "cowork/SKILL.md" in result.stdout
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 1
    assert "cowork/SKILL.md" in result.stderr
