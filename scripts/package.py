#!/usr/bin/env python3
"""Copy the canonical skill into each host integration and build the Cowork zip."""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SKILL = ROOT / "skill"
DESTINATIONS = (
    ROOT / "integrations" / "codex" / ".agents" / "skills" / "flight-fare-research",
    ROOT / "integrations" / "claude-code" / "skills" / "flight-fare-research",
)
COWORK_ZIP = ROOT / "dist" / "flight-fare-research-cowork.zip"
SKILL_NAME = "flight-fare-research"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def is_packaged(path: Path, root: Path) -> bool:
    """True for files that belong in a package (no bytecode caches)."""
    rel = path.relative_to(root)
    return path.is_file() and "__pycache__" not in rel.parts and path.suffix != ".pyc"


def packaged_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*") if is_packaged(p, directory))


def file_count(directory: Path) -> int:
    return len(packaged_files(directory))


def build_cowork_zip(src: Path, dest: Path) -> Path:
    """Write a deterministic zip of the skill with a top-level skill folder."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in packaged_files(src):
            rel = path.relative_to(src).as_posix()
            info = zipfile.ZipInfo(f"{SKILL_NAME}/{rel}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if rel.startswith("scripts/") and rel.endswith(".py") else 0o644
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, path.read_bytes())
    tmp.replace(dest)
    return dest


def main() -> int:
    try:
        if not CANONICAL_SKILL.is_dir():
            print(f"error: canonical skill directory is missing: {CANONICAL_SKILL}", file=sys.stderr)
            return 1

        if not (CANONICAL_SKILL / "SKILL.md").is_file():
            print(f"error: canonical SKILL.md is missing: {CANONICAL_SKILL}", file=sys.stderr)
            return 1

        source_count = file_count(CANONICAL_SKILL)
        for destination in DESTINATIONS:
            if destination.exists() or destination.is_symlink():
                if destination.is_dir() and not destination.is_symlink():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(CANONICAL_SKILL, destination, ignore=IGNORE)
            print(f"Copied {source_count} file(s): {CANONICAL_SKILL} -> {destination}")
        build_cowork_zip(CANONICAL_SKILL, COWORK_ZIP)
        print(f"Built Cowork zip: {COWORK_ZIP}")
    except (OSError, shutil.Error, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
