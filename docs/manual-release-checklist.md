# Release checklist

1. Run `python3 scripts/validate.py --strict` against the committed tree.
2. Run `python3 scripts/package.py`; require no generated-file drift.
3. Run `python3 -m pytest tests/ -q`.
4. Check tracked files and release assets for identifying information, profiles,
   credentials, session handles and booking tokens.
5. Verify public GitHub Actions, branch/tag commit and asset checksums.
6. State browser validation accurately: static tests are not a live replay.
   For a live test, verify exact routes/dates/travelers/cabins, both directions,
   current quote and bag state, source URL and retrieval time; never book.
7. Publish only at the repository owner's request.

## Initial public release scope

The initial release includes static regression tests and browser recipes informed
by prior observations. No new independent live-browser replay is claimed for
this release. Historical smoke-test fixtures are not current fare guarantees.
