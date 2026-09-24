"""Resolve references in the whole canonical tree, not only its entrypoint."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate import validate_internal_links


def test_dangling_backtick_reference_in_reference_file(tmp_path):
    (tmp_path / "SKILL.md").write_text("See `references/guide.md`.\n")
    (tmp_path / "references").mkdir()
    (tmp_path / "references/guide.md").write_text("See `references/missing.md`.\n")
    errors = validate_internal_links(tmp_path)
    assert len(errors) == 1
    assert "references/guide.md:1" in errors[0]
    assert "references/missing.md" in errors[0]


def test_sibling_reference_from_reference_file(tmp_path):
    (tmp_path / "SKILL.md").write_text("See `references/guide.md`.\n")
    (tmp_path / "references").mkdir()
    (tmp_path / "references/guide.md").write_text("See `other.md`.\n")
    (tmp_path / "references/other.md").write_text("Details.\n")
    assert validate_internal_links(tmp_path) == []


def test_root_relative_backtick_reference_from_reference_file(tmp_path):
    (tmp_path / "SKILL.md").write_text("See `references/guide.md`.\n")
    (tmp_path / "references").mkdir()
    (tmp_path / "references/guide.md").write_text("See `SKILL.md`.\n")
    assert validate_internal_links(tmp_path) == []
