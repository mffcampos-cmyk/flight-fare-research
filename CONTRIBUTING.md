# Contributing

## Canonical content

Edit `skill/` only for skill content. It is the canonical Agent Skills tree; generated host packages must not be edited directly.

## Regenerate host packages

After changing `skill/`, regenerate the Codex and Claude Code copies:

```bash
python3 scripts/package.py
```

Commit the regenerated files with the canonical change.

## Validate

Run the static validator before submitting changes:

```bash
python3 scripts/validate.py --strict
```

Install test dependencies into an isolated environment, then run the tests
(the packaging and validation scripts themselves use only the standard library):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'pytest>=8,<10'
.venv/bin/python -m pytest tests/ -v
```

Do not add credentials, cookies, browser profiles, personal itinerary data, or booking tokens. Keep live flight research out of automated validation.
