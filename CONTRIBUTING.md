# Contributing

## Canonical content

Edit `skill/` only for skill content. It is the canonical Agent Skills tree.
The host packages (`dist/claude-code/`, `dist/codex/` and
`dist/flight-fare-research-cowork.zip`) are build outputs: never committed,
never edited. The hand-authored host files under `integrations/` (the Claude
plugin manifest, the Codex `AGENTS.md`, the Cowork and Hermes notes) are
committed and copied into `dist/` by the build.

## Build host packages

```bash
python3 scripts/package.py
```

## Validate and test

```bash
python3 scripts/validate.py --strict
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -v
```

`validate.py` checks internal references, the `SKILL.md` word budget (2,000),
version agreement, that every bundled command script answers `--help`, and,
when `dist/` has been built, that it matches the canonical skill.
The scripts and validator use only the Python standard library.

## Changing skill behaviour

Before changing `SKILL.md` or a reference a scenario touches, run the pressure
scenarios in `tests/scenarios/` against the current skill, make the change,
then run them again and record both results (see `tests/scenarios/README.md`).
These need a model and are not part of CI.

Do not add credentials, cookies, browser profiles, personal itinerary data,
booking tokens, or run and ledger files. Keep live flight research out of
automated tests.
