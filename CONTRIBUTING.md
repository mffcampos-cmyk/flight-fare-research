# Contributing

## Canonical content

Edit `skill/` only for skill content. It is the canonical Agent Skills tree;
the Codex and Claude Code copies under `integrations/` and the Cowork zip in
`dist/` are generated and must not be edited directly.

## Regenerate host packages

```bash
python3 scripts/package.py
```

This refreshes both copies and builds `dist/flight-fare-research-cowork.zip`
(not committed). Commit the regenerated copies with the canonical change.

## Validate and test

```bash
python3 scripts/validate.py --strict
python3 -m venv .venv
.venv/bin/python -m pip install 'pytest>=8,<10'
.venv/bin/python -m pytest tests/ -v
```

`validate.py` checks copy parity, internal references, the `SKILL.md` word
budget (2,000), version agreement, that every bundled script answers `--help`, and the Cowork zip.
The scripts and validator use only the Python standard library.

## Changing skill behaviour

Before changing `SKILL.md` or a reference a scenario touches, run the pressure
scenarios in `tests/scenarios/` against the current skill, make the change,
then run them again and record both results (see `tests/scenarios/README.md`).
These need a model and are not part of CI.

Do not add credentials, cookies, browser profiles, personal itinerary data,
booking tokens, or run and ledger files. Keep live flight research out of
automated tests.
