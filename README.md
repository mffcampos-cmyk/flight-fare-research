# Flight Fare Research

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An agent skill for finding the best flight you could actually book, not just
the lowest advertised fare. It compares exact dates, the cabins you asked for,
baggage, journey time and route hacks, and keeps evidence for every price it
recommends.

It is an agent workflow with browser recipes, not a flight-search engine. The
agent does the searching in a browser; small Python scripts keep the books and
speed up the two biggest sources. It never books flights or handles payments.

## The key rule

An advertised fare or a partly priced route hack is a **lead**, not a
recommendation. A price becomes **qualified** only when both directions are
selected, each direction is within the journey-time limit, baggage is resolved
for the bags requested, every all-in part (positioning, hotel, transfers) is
priced, and the seller has repriced it. Anything unresolved is labelled next to
its price, and the search is never called complete while requested comparisons
are unfinished.

## How it works

1. **Intake.** One message asks for anything missing, each item with a default:
   dates or trip length, airports, travellers, cabins, bags, currency, journey-
   time limit, and how much positioning or self-transfer risk is acceptable.
2. **Scope.** A quick search for simple fixed-date trips; a full search for
   flexible dates, long haul, several cabins or route hacks.
3. **Collect.** Connectors or browser sources, search settings verified on the
   page, every observation saved as it is read, coverage checked by the script.
4. **Route hacks.** Split one-ways, open-jaw/multi-city, nearby departure
   airports, alternative arrival airports and stopovers, priced all-in with
   positioning, bags and unavoidable hotel or transfer costs.
5. **Qualify.** Both directions, the duration cap per direction, mixed-cabin
   labels kept, baggage verified per ticket, repriced with the airline or seller.
6. **Cross-check and report.** Independent source families, ranking by
   qualified all-in price and practicality, local times, risks, retrieval
   timestamps and booking links, and a final `Complete` or `Incomplete:` line.

## The scripts (Python 3, standard library only)

- `skill/scripts/run_log.py`: one run's contract, observation rows, computed
  lead/qualified status, ranking with pruning, coverage, and `check` (exit 0
  when complete, 4 while comparisons are open). Runs are stored under
  `$FFR_RUNS`, else `$XDG_STATE_HOME/flight-fare-research/runs`, else
  `~/.local/state/flight-fare-research/runs`.
- `skill/scripts/source_ledger.py`: which sources work on which browser engine,
  from a fixed canary search. Stored under `$FFR_LEDGER` or the same state
  directory. Never commit either file: both hold raw local evidence.
- `skill/scripts/gflights.py`: exact Google Flights search URLs for any cabin,
  one-way, multi-city or several airports at once; a results-page parser; and
  an unattended sweep through a BrowserAct session that verifies each page and
  records list-fare rows.
- `skill/scripts/flightlist.py`: turns one FlightList date-range search into
  rows for every date pair it covers, so a flexible window is discovered in one
  search instead of one per pair.

## Browsers and bot walls

The skill prefers the browser least likely to be blocked: the user's own
(Claude in Chrome, the Claude desktop built-in browser, Cowork's browser), then
a persistent [browser-act](https://docs.browseract.com/) browser, then a
headless one. It paces searches like a person. When a site challenges it, the
user can clear the check in their own browser if they are watching; otherwise
the source is recorded as blocked and the search moves on. It never solves
CAPTCHAs, rotates proxies, changes fingerprints or imports anyone else's
sessions. See `skill/references/browser-engines.md`.

### Optional: BrowserAct (no login needed)

[BrowserAct](https://github.com/browser-act/skills) adds a local browser CLI
that can drive your own Chrome (`chrome-direct`) or a persistent Chromium
(`chrome`). Both modes are free without an account.

```bash
# 1. the entry skill (Claude Code shown; other agents use their skills folder)
git clone --depth 1 https://github.com/browser-act/skills /tmp/browser-act-skills
mkdir -p ~/.claude/skills && cp -R /tmp/browser-act-skills/browser-act ~/.claude/skills/
# 2. the CLI
uv tool install browser-act-cli --python 3.12
browser-act --version
```

The flight skill then runs `browser-act get-skills core` at the start of each
session and asks before creating any browser. It does not use BrowserAct's
login-only features (stealth browsers, `stealth-extract`, `solve-captcha`,
`remote-assist`, proxies).

## Install

The canonical skill is `skill/`. Host packages are generated from it with
`python3 scripts/package.py` and checked with `python3 scripts/validate.py --strict`.

- **Claude Code:** `claude --plugin-dir integrations/claude-code`
- **Codex:** `cd integrations/codex && codex` (or copy
  `integrations/codex/.agents/skills/flight-fare-research/` into your project's
  `.agents/skills/`)
- **Hermes:** `integrations/hermes/install.sh`
- **Cowork:** run `python3 scripts/package.py` and upload
  `dist/flight-fare-research-cowork.zip` (also published as a CI artifact). See
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
- [2.0 design](docs/superpowers/specs/2026-10-08-flight-fare-research-v2-design.md)

## License

MIT. See [LICENSE](LICENSE).
