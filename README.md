# Flight Fare Research

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An agent skill for finding the best flight you could actually book, not just
the lowest advertised fare. One-way, round trip or multi-city; Zurich plus
the airports you can reach by train; a city, or a whole region such as
Southeast Asia. It compares exact dates, the cabins you asked for, baggage,
journey time and route hacks, and keeps evidence for every price it
recommends.

It is an agent workflow with browser recipes, not a flight-search engine. The
agent does the searching in a browser, BrowserAct first; small Python scripts
keep the books, drive the sweeps and check completeness. It never books
flights or handles payments.

## The key rule

An advertised fare or a partly priced route hack is a **lead**, not a
recommendation. A price becomes **qualified** only when every leg is
selected, each leg is within the journey-time limit, baggage is resolved for
the bags requested, every all-in part (the train to a nearby airport, hotel,
transfers) is priced, and the seller has repriced it. Anything unresolved is
labelled next to its price, and the search is never called complete while
requested comparisons are unfinished.

## How it works

0. **Browser.** `browseract.py status` finds the engine: a BrowserAct stealth
   browser (free login), BrowserAct's local Chromium, the user's own browser,
   or a headless tool. No login yet? It tells the user the two commands and
   carries on.
1. **Intake.** One message with all 18 options and their defaults: legs and
   trip shape, origin airports with the rail-reachable ones, destination or
   region, dates per leg, travellers, cabins, bags, currency, journey-time
   limit, stops, time windows, airlines, route hacks, self-transfer, budget,
   speed mode, fixed event, browser.
2. **Discovery.** A region becomes a shortlist of gateway airports from
   FlightList range sweeps, Google Flights Explore and FlightConnections,
   proposed as leads for the user to confirm.
3. **Collect.** `run_log.py jobs` plans one parallel session per source
   family; FlightList sweeps discover the window, Google confirms the
   cheapest dates, every observation is saved as it is read.
4. **Route hacks.** Split one-ways, open-jaw and stopovers, priced all-in
   with ground rows for nearby airports, bags and unavoidable nights.
5. **Qualify.** Every leg, the gates, mixed-cabin labels, baggage per ticket,
   repriced with the seller (the Kiwi fare page in one command).
6. **Cross-check and report.** Independent source families, ranking by
   qualified all-in price and practicality, local times, risks, retrieval
   timestamps and booking links, and a final `Complete` or `Incomplete:` line.

## The scripts (Python 3, standard library only)

- `skill/scripts/run_log.py`: one run's contract (legs, airport groups, date
  tuples), observation rows (fare, ground, attempt), computed lead/qualified
  status, ranking with pruning, coverage, the parallel job plan, and `check`
  (exit 0 when complete, 4 while comparisons are open). The rules live in
  `ffr_contract.py` and `ffr_rows.py`. Runs are stored under `$FFR_RUNS`, else
  `$XDG_STATE_HOME/flight-fare-research/runs`, else
  `~/.local/state/flight-fare-research/runs`.
- `skill/scripts/browseract.py`: the BrowserAct login check, engine choice,
  session driver and challenge policy shared by every sweep.
- `skill/scripts/flightlist.py`: an unattended FlightList range search per
  origin airport, and the card-to-row converter.
- `skill/scripts/gflights.py`: exact Google Flights URLs for any cabin and any
  number of legs, a results-page parser, an unattended confirmation sweep, and
  the Explore steps for a region.
- `skill/scripts/kiwi.py`: the Kiwi fare page behind a FlightList card, read
  into a completed row.
- `skill/scripts/source_ledger.py`: which sources work on which browser engine,
  at what pace. Never commit the run or ledger files: both hold raw local
  evidence.

## Browsers and bot walls

BrowserAct first: its stealth browsers (up to five on the free account) are
built for sites that block automation, its local Chromium keeps a persistent
profile, and both run many sessions at once. The user's own browser (Claude
in Chrome, the desktop built-in browser, Cowork, BrowserAct `chrome-direct`)
is the fallback, then a headless tool. Every source family runs in its own
session in parallel; each site keeps its own pace, and Google keeps its daily
allowance for confirmation. On a challenge the skill runs `solve-captcha`
once, then hands the page to a human through `remote-assist`, then asks a
user watching their own browser, and otherwise records the source as blocked.
It never buys proxies or browsers, never imports anyone else's sessions, and
never books. See `skill/references/browser-engines.md` and
[Safety and provenance](docs/safety-and-provenance.md).

### BrowserAct setup

```bash
# 1. the entry skill (Claude Code shown; other agents use their skills folder)
git clone --depth 1 https://github.com/browser-act/skills /tmp/browser-act-skills
mkdir -p ~/.claude/skills && cp -R /tmp/browser-act-skills/browser-act ~/.claude/skills/
# 2. the CLI
uv tool install browser-act-cli --python 3.12
browser-act --version
# 3. optional, unlocks stealth browsers, solve-captcha and remote-assist (free account)
browser-act auth login     # open the URL it prints, create the account
browser-act auth poll
```

The skill checks all of this itself at the start of each session
(`browseract.py status`) and tells the user what is missing; it never creates
the account for them.

## Install

The canonical skill is `skill/`. Build the host packages once with
`python3 scripts/package.py` (they land under `dist/`, which is never
committed; CI publishes the same build as the `flight-fare-research-dist` and
`flight-fare-research-cowork` artifacts).

- **Claude Code:** `claude --plugin-dir dist/claude-code`
- **Codex:** `cd dist/codex && codex` (or copy
  `dist/codex/.agents/skills/flight-fare-research/` into your project's
  `.agents/skills/`)
- **Hermes:** `integrations/hermes/install.sh` (copies `skill/` directly)
- **Cowork:** upload `dist/flight-fare-research-cowork.zip`. See
  `integrations/cowork/README.md`.

## Capability boundary

Research only: no booking, checkout, payment, account creation or stored
credentials, and no guarantee that an observed price still holds. Details in
[Safety and provenance](docs/safety-and-provenance.md).

## Documentation

- [Safety and provenance](docs/safety-and-provenance.md): evidence rules, statuses, browser and challenge policy.
- [Release checklist](docs/manual-release-checklist.md)
- [Dated source observations](skill/references/historical-observations.md)
- [Pressure scenarios](tests/scenarios/README.md): manual behaviour tests for the skill.
- [3.0 design](docs/superpowers/specs/2026-10-17-flight-fare-research-v3-design.md)
- [2.0 design](docs/superpowers/specs/2026-10-08-flight-fare-research-v2-design.md)

## License

MIT. See [LICENSE](LICENSE).
