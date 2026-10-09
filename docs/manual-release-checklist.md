# Release checklist

1. Bump the version in `skill/SKILL.md`, `integrations/claude-code/.claude-plugin/plugin.json`
   and the top `CHANGELOG.md` heading together (`validate.py` checks they agree).
2. Run `python3 scripts/package.py`; commit the regenerated copies; require no
   drift (`git diff --exit-code -- skill integrations`).
3. Run `python3 scripts/validate.py --strict` (copies, links, versions, scripts,
   `SKILL.md` word budget, Cowork zip).
4. Run `python3 -m pytest tests/ -q`.
5. Re-run the pressure scenarios in `tests/scenarios/` against the release
   candidate and record the results in each file.
6. Check tracked files and the Cowork zip for identifying information,
   credentials, session handles and booking tokens.
7. Confirm CI is green on the release commit and download the
   `flight-fare-research-cowork` artifact.
8. State browser validation accurately: static tests and scenarios are not a
   live replay. For a live test, verify exact routes, dates, travellers and
   cabins, both directions, the current quote and bag state, source URL and
   retrieval time; never book.
9. Publish only at the repository owner's request.
