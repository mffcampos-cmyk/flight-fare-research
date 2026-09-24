#!/usr/bin/env python3
"""Validate generated host skill copies against the canonical skill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _hash import sha256_file

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SKILL = ROOT / "skill"
GENERATED_TARGETS = (
    ROOT / "integrations" / "codex" / ".agents" / "skills" / "flight-fare-research",
    ROOT / "integrations" / "claude-code" / "skills" / "flight-fare-research",
)
# Cowork is intentionally hand-authored and must never enter GENERATED_TARGETS.
COWORK_SKILL = ROOT / "integrations" / "cowork" / "SKILL.md"
HAND_AUTHORED_ARTIFACTS = (
    COWORK_SKILL,
    ROOT / "integrations" / "codex" / "AGENTS.md",
    ROOT / "integrations" / "claude-code" / ".claude-plugin" / "plugin.json",
)


def parse_frontmatter(text):
    """Minimal scalar-only frontmatter parser returning (keys, errors)."""
    errors = []
    if not text.startswith("---\n"):
        return {}, ["frontmatter: missing opening --- delimiter"]
    body = text.split("\n", 1)[1]
    if "\n---" not in body:
        return {}, ["frontmatter: missing closing --- delimiter"]
    lines = body.split("\n---\n", 1)[0].splitlines()
    out = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Nested YAML (indented keys/lists under a parent key) is valid; skip it.
        # Only top-level scalar keys are validated here.
        if line.startswith((" ", "\t")):
            continue
        if ":" not in line:
            errors.append("frontmatter: unsupported or malformed line: %r" % line)
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in out:
            errors.append("frontmatter: duplicate key: %s" % key)
        out[key] = value.strip().strip("'\"")
    return out, errors


def first_delimited_block(text):
    """Return the substring of the first ---delimited block, or empty."""
    if not text.startswith("---\n"):
        return ""
    body = text.split("\n", 1)[1]
    if "\n---" not in body:
        return ""
    return "---\n" + body.split("\n---\n", 1)[0] + "\n---\n"


def _backtick_refs(line):
    """Yield whitespace-free backtick tokens that end in a supported md ext."""
    out = []
    for depth, part in enumerate(line.split("`")):
        if depth % 2 == 1 and part.endswith(".md") and not part.startswith(" "):
            out.append(part)
    return out


def validate_internal_links(skill_root):
    """Resolve backtick references against the skill root.

    Root-qualified tokens such as `references/foo.md` resolve from the skill
    root. Bare filenames may also resolve beside the referring document.
    """
    errors = []
    if not (skill_root / "SKILL.md").is_file():
        return ["SKILL.md: missing entrypoint"]
    for entry in sorted(skill_root.rglob("*.md")):
        relative = entry.relative_to(skill_root)
        try:
            text = entry.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append("%s: %s" % (relative, exc))
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for token in _backtick_refs(line):
                if (skill_root / token).is_file():
                    continue
                if "/" not in token and (entry.parent / token).is_file():
                    continue
                errors.append(
                    "%s:%d: reference %r does not resolve under %s"
                    % (relative, line_no, token, skill_root.name)
                )
    return errors


def validate_cowork(entry):
    """Lint the standalone variant, never compare it to canonical bytes.

    It must stay a single self-contained file: no sibling markdown to pull in
    (no `references/`), and no external skills or browser-act-centric tools
    (`js()` / `cdp()` / `grounded-citations` / `browser-act`) or paths into a
    host tree. Body word count is bounded to keep it a trimmed card.
    """
    text = entry.read_text(encoding="utf-8")
    body = text[len(first_delimited_block(text)):]
    errors = []
    count = len(body.split())
    if not 1500 <= count <= 2600:
        errors.append("Cowork: body word count %d is outside 1500–2600" % count)

    if (entry.parent / "references").is_dir():
        errors.append("Cowork: must be standalone; `references/` sibling present")

    banned = [
        "`references/", "../", "../../",
        "browser-act",
        "grounded-citations",
        "js()",
        "cdp(",
    ]
    for phrase in banned:
        if phrase in body:
            errors.append(
                "Cowork: standalone violation, external dependency: %r" % phrase
            )
    return errors


def validate_plugin_schema(plugin_path):
    """Check essential Claude plugin.json fields using only stdlib json."""
    import json

    if not plugin_path.is_file():
        return []
    try:
        data = json.loads(plugin_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return ["plugin.json: invalid JSON: %s" % exc]
    if not isinstance(data, dict):
        return ["plugin.json: top-level value must be a JSON object"]
    if "name" not in data:
        return ["plugin.json: missing required key: name"]
    if not isinstance(data.get("description"), str) or not data["description"]:
        return ["plugin.json: description must be a non-empty string"]
    if "version" not in data:
        return ["plugin.json: missing required key: version"]
    version = data["version"]
    if not isinstance(version, str):
        return ["plugin.json: version must be a string"]
    parts = version.split(".")
    if len(parts) != 3 or any(not p.isdigit() for p in parts):
        return ["plugin.json: version %r is not semver X.Y.Z" % version]
    return []



def file_map(directory):
    return {
        path.relative_to(directory): sha256_file(path)
        for path in directory.rglob("*")
        if path.is_file()
    }


def validate_target(canonical, target):
    if not target.is_dir():
        return ["missing generated target: %s" % target]

    actual = file_map(target)
    errors = []
    missing = sorted(set(canonical) - set(actual))
    extra = sorted(set(actual) - set(canonical))
    changed = sorted(
        path for path in set(canonical) & set(actual) if canonical[path] != actual[path]
    )
    errors.extend("%s: missing file: %s" % (target, path) for path in missing)
    errors.extend("%s: extra file: %s" % (target, path) for path in extra)
    errors.extend("%s: SHA-256 mismatch: %s" % (target, path) for path in changed)
    if not errors:
        print("OK: %s (%d file(s) match canonical)" % (target, len(canonical)))
    return errors



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when planned hand-authored integration artifacts are absent",
    )
    args = parser.parse_args()

    try:
        if not CANONICAL_SKILL.is_dir():
            print("error: canonical skill directory is missing: %s" % CANONICAL_SKILL, file=sys.stderr)
            return 1

        if not (CANONICAL_SKILL / "SKILL.md").is_file():
            print("error: canonical SKILL.md is missing: %s" % CANONICAL_SKILL, file=sys.stderr)
            return 1

        canonical = file_map(CANONICAL_SKILL)
        errors = [
            error
            for target in GENERATED_TARGETS
            for error in validate_target(canonical, target)
        ]

        skill_md = (CANONICAL_SKILL / "SKILL.md").read_text(encoding="utf-8")
        frontmatter, fm_errors = parse_frontmatter(first_delimited_block(skill_md))
        errors.extend(fm_errors)
        if not fm_errors:
            expected_name = GENERATED_TARGETS[0].name
            if "name" not in frontmatter:
                errors.append("SKILL.md frontmatter: missing required key: name")
            elif frontmatter["name"] != expected_name:
                errors.append(
                    "SKILL.md frontmatter: name %r != canonical dir %r"
                    % (frontmatter["name"], expected_name)
                )
            desc = frontmatter.get("description", "").strip()
            empty_scalars = ("[]", "{}", "null", "~", "false")
            if "description" not in frontmatter:
                errors.append("SKILL.md frontmatter: missing required key: description")
            elif not desc or desc in empty_scalars:
                errors.append("SKILL.md frontmatter: description must be a non-empty scalar string")
            elif len(desc) > 1024:
                errors.append(
                    "SKILL.md frontmatter: description too long (%d > 1024 chars)" % len(desc)
                )

        errors.extend(validate_internal_links(CANONICAL_SKILL))
        errors.extend(
            validate_plugin_schema(ROOT / "integrations/claude-code/.claude-plugin/plugin.json")
        )

        for artifact in HAND_AUTHORED_ARTIFACTS:
            if artifact.is_file():
                print("OK: hand-authored artifact present: %s" % artifact)
                if artifact == COWORK_SKILL:
                    for error in validate_cowork(artifact):
                        errors.append(error)
            elif args.strict:
                errors.append("planned hand-authored artifact is missing: %s" % artifact)
            else:
                print("PENDING: planned hand-authored artifact is missing: %s" % artifact)

        for error in errors:
            print("error: %s" % error, file=sys.stderr)
        return 1 if errors else 0
    except OSError as error:
        print("error: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
