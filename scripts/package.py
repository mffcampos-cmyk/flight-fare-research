#!/usr/bin/env python3
"""Copy the canonical skill into each supported host integration."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SKILL = ROOT / "skill"
DESTINATIONS = (
    ROOT / "integrations" / "codex" / ".agents" / "skills" / "flight-fare-research",
    ROOT / "integrations" / "claude-code" / "skills" / "flight-fare-research",
)


def file_count(directory: Path) -> int:
    return sum(1 for path in directory.rglob("*") if path.is_file())


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
            shutil.copytree(CANONICAL_SKILL, destination)
            print(f"Copied {source_count} file(s): {CANONICAL_SKILL} -> {destination}")
    except (OSError, shutil.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
