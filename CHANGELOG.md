# Changelog

## [1.1.0]

- Source health check: `skill/scripts/source_ledger.py` (standard library only) records one fixed canary search per core source (`ok`, `partial`, `blocked`, `empty`, `error`), flags stale or untested sources (> 7 days), and prints the ladder order for the run. The ledger is local runtime state outside the skill tree and is never committed. Runbook: `skill/references/source-health.md`. Pattern adapted from Agent-Reach's `doctor`.
- `source-ladder.md` no longer keeps a hand-written status table; it points to the ledger. Dated observations stay in `historical-observations.md`.
- Upper-bound pruning for route hacks: skip slow airline-direct repricing when a candidate's lowest possible all-in total already reaches the best qualified fare. Encoded as `tests/rules.py::prune_by_lower_bound` with tests.
- Lead-discovery tiers (`skill/references/lead-discovery.md`): keyless web search fan-out, Jina Reader for official policy pages, an optional Perplexity fast/default tier when a key is already configured, and community posts as historical reports only (no cookies or proxies).
- Browser engine: browser-act preferred, host browser tool fallback when the CLI is absent.
- Variable trip lengths: separate outbound and return date ranges no longer imply approval of every Cartesian pairing; confirm or pin a target length first.
- First ledger canary (2026-10-03, headless Chromium): Google Flights, TAP direct and ITA Matrix ok; eDreams partial; FlightList error (see `docs/source-support-matrix.md`).
- Cowork card: pruning rule and lead-discovery guidance (no script).

## [1.0.0]

- General-purpose airfare research for Hermes, Codex, Claude Code and Cowork.
- Quick/full workflows, connector discovery, baggage qualification and final checks.
- FlightList exact-airport/date verification, eDreams date handling and airline fare-family recipes.
- Standalone Cowork card; reproducible modular packages and static validation.
- Search settings supplied per request; no embedded personal travel profile.
