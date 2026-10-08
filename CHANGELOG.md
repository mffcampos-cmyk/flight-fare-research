# Changelog

## [2.0.0]

- **Key rule enforced by a script.** New `skill/scripts/run_log.py` (standard library only) stores the search contract, saves every observation as it is read, computes each row's status (`qualified`, `lead` with reasons, `rejected`, `superseded`, `attempt`), ranks qualified options by all-in total with lower-bound pruning, and `check` exits 0 only when every requested comparison is finished (4 otherwise).
- **Intake first.** One message asks for missing dates or trip length, airports, travellers, cabins, bags, currency, journey-time limit and positioning/self-transfer tolerance, each with a default; unattended runs record defaults as assumptions.
- **Browser ladder and challenge policy.** The user's own browser first (Claude in Chrome, built-in browser, Cowork), then a persistent browser-act browser, then headless; human pacing; challenges handed to a watching user or recorded as blocked. No CAPTCHA solving, proxy/TLS rotation, fingerprint changes or session import.
- **Restructured skill.** `SKILL.md` rewritten (under 2,000 words, enforced) around six phases; new references `intake.md`, `browser-engines.md` (replaces `browser-act-support.md`), `qualification.md`, `route-hacks.md` (absorbs `lead-discovery.md`); recipes made host-neutral.
- **Source ledger.** `--engine` recorded per state, `--add` for ad-hoc sources, `positioning` and `routes` roles, 23 untested expansion candidates (OTAs, airline sites, stopover programmes, rail sellers, route maps); naive timestamps no longer crash it.
- **Cowork** now gets the full skill as `dist/flight-fare-research-cowork.zip`, built by `package.py` and uploaded by CI; the hand-maintained card is gone.
- **Run log hardening (final review):** leads in another currency without `fx` are never pruned and are flagged; `add` refuses rows for a different search and malformed legs, with a one-row-per-combination hint for hacks; `resolve` is guarded (`no_fare` needs an executed search, `none_qualify` a priced candidate); warnings for cabins with no results or only leads; every command reports the run it used, `add` and `resolve` lock the run, and unexpected data exits 2 instead of a traceback; quick scope refuses other hacks; open-jaw counts every airport; full-size cabin bags (`bags.cabin_per_person`, ticket `cabin_bag`); `source_ledger.py order --engine` turns lower-rung failures into one allowed re-probe.
- **Validation:** version agreement, script `--help` checks, Cowork zip parity, `SKILL.md` word budget, bytecode never packaged.
- **Tests:** the test-only `tests/rules.py` is replaced by tests of the shipped `run_log.py`; pressure scenarios with recorded baseline and after results in `tests/scenarios/`.
- Removed: `integrations/cowork/SKILL.md`, `docs/feedback-review.md`, `docs/cowork-v1.8-review.md`, `docs/source-support-matrix.md` (dated rows moved to `historical-observations.md`).

## [1.1.1]

- FlightList recipe: easyAutocomplete only reacts to keyup events with a real `keyCode`. Synthetic key events without one look like a dead autocomplete.
- eDreams recipe: Swiss-German consent decline is the `Weiter ohne Zustimmung` link; itinerary cards may render only after the "show more results" button.
- Headed re-probe (2026-10-03): FlightList and eDreams ok. The v1.1.0 headless `error`/`partial` states were recipe gaps, not headless blocks. Matrix, `source-health.md` and `historical-observations.md` corrected.

## [1.1.0]

- Source health check: `skill/scripts/source_ledger.py` (standard library only) records one fixed canary search per core source (`ok`, `partial`, `blocked`, `empty`, `error`), flags stale or untested sources (> 7 days), and prints the ladder order for the run. The ledger is local runtime state outside the skill tree and is never committed. Runbook: `skill/references/source-health.md`. Pattern adapted from Agent-Reach's `doctor`.
- `source-ladder.md` no longer keeps a hand-written status table; it points to the ledger. Dated observations stay in `historical-observations.md`.
- Upper-bound pruning for route hacks: skip slow airline-direct repricing when a candidate's lowest possible all-in total already reaches the best qualified fare. Encoded as `tests/rules.py::prune_by_lower_bound` with tests.
- Lead-discovery tiers (`skill/references/lead-discovery.md`): keyless web search fan-out, Jina Reader for official policy pages, an optional Perplexity fast/default tier when a key is already configured, and community posts as historical reports only (no cookies or proxies).
- Browser engine: browser-act preferred, host browser tool fallback when the CLI is absent.
- Variable trip lengths: separate outbound and return date ranges no longer imply approval of every Cartesian pairing; confirm or pin a target length first.
- First ledger canary (2026-10-03, headless Chromium): Google Flights, TAP direct and ITA Matrix ok; eDreams partial and FlightList error, later corrected in 1.1.1.
- Cowork card: pruning rule and lead-discovery guidance (no script).

## [1.0.0]

- General-purpose airfare research for Hermes, Codex, Claude Code and Cowork.
- Quick/full workflows, connector discovery, baggage qualification and final checks.
- FlightList exact-airport/date verification, eDreams date handling and airline fare-family recipes.
- Standalone Cowork card; reproducible modular packages and static validation.
- Search settings supplied per request; no embedded personal travel profile.
