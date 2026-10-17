# Cowork

Cowork uses the same skill as every other host, packaged as a zip.

## Build

```bash
python3 scripts/package.py
```

This builds every host package under `dist/`, including
`dist/flight-fare-research-cowork.zip`. CI also builds it and publishes it as the
`flight-fare-research-cowork` workflow artifact. The zip holds one top-level
folder, `flight-fare-research/`, with `SKILL.md`, `references/` and `scripts/`.

## Install

Upload `dist/flight-fare-research-cowork.zip` as a custom skill in Cowork. Replace
any older single-file "Flight Fare Research" card; the two must not coexist.

## Requirements and assumption

The skill runs standard-library Python scripts (`scripts/run_log.py`,
`scripts/browseract.py`, `scripts/source_ledger.py` and the sweeps) to save
results, drive BrowserAct and check completeness. This assumes your Cowork
environment can run bundled scripts. If it cannot, the skill still works as
written guidance, but the agent cannot run `run_log.py check`, so every report
must state that coverage was checked by hand and that the search is not
verified complete.

In Cowork the agent uses BrowserAct when its CLI is installed on the machine,
and Cowork's built-in browser otherwise (rung 3 of the ladder in
`references/browser-engines.md`). Research only: it never books or pays.
