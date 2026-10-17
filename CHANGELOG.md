# Changelog

## [3.0.0]

A new contract, BrowserAct first, and the host packages built instead of committed.

- **Legs.** The contract is a list of legs with airport groups: one-way, round trip and multi-city in one model; a nearby airport carries how it is reached (`"via": "rail"`) and needs a priced **ground row** before a fare row from it can qualify. Dates per leg: fixed, a range, plus-or-minus days, or a trip length linked to an earlier leg; `init` expands them into date tuples. Nearby origins, alternative destinations and multi-city are baseline now; the hacks are `split`, `open_jaw` and `stopover`, each on or off at intake. New gates: `max_stops`, time windows, excluded airlines; new flags: budget, preferred airline, overnight before departure.
- **Regions and discovery.** A destination may be a region; `references/discovery.md` turns it into a shortlist of gateways from FlightList range sweeps, Google Flights Explore and FlightConnections, proposed to the user as leads, then `run_log.py shortlist`.
- **Speed modes.** `fast` (one range search per destination, then `run_log.py confirm` picks the cheapest tuples for exact-date confirmation) or `thorough` (every tuple, capped at 200).
- **The questionnaire.** Intake sends all 18 options every run, each with its default; "just go" turns them into listed assumptions.
- **BrowserAct first.** New `scripts/browseract.py`: login check (`status`, cached 24 h, tells the user how to create the free account, never creates it), engine ladder (stealth browser, local Chromium, the user's own browser, host headless), a shared session driver, and the challenge policy (`solve-captcha` once, then `remote-assist`, then the user's own hands, else blocked). The 2.x ban on CAPTCHA solving, fingerprint masking and proxies is lifted for BrowserAct's own free features; the agent still never buys proxies or browsers, books, or handles credentials (`docs/safety-and-provenance.md`).
- **Sweeps and the planner.** `flightlist.py sweep` drives the whole range search; `gflights.py sweep` takes `--tuples`, N-leg URLs and the challenge policy; new `kiwi.py fare` reprices a FlightList card on the Kiwi fare page; `run_log.py jobs` prints one job list per parallel session; `source_ledger.py` carries the new rungs, pacing per source and the Asia candidates (Qatar, Emirates, Turkish, Singapore, Thai, AirAsia, Scoot, Trip.com, Google Explore).
- **run_log.py** is now storage plus CLI on `ffr_contract.py` and `ffr_rows.py`; `add` takes fare rows, ground rows and attempts in one array; new `shortlist`, `confirm` and `jobs` commands.
- **Packaging.** `integrations/claude-code/skills/` and `integrations/codex/.agents/` are no longer committed: `package.py` builds `dist/claude-code/`, `dist/codex/` and the Cowork zip; CI uploads them; `requirements-dev.txt` holds pytest.
- **Tests and scenarios.** The run_log tests are rewritten for v3; `browseract.py` is tested against a fake CLI on `PATH`; scenario 04 is rewritten for the new challenge policy; new scenarios 07 (region, multi-city), 08 (full questionnaire, "just go") and 09 (no BrowserAct login).
- **Known gaps.** No Google Explore page text could be captured (the datacenter probe got the "unusual traffic" check), so `gflights.py parse --explore` reports only `challenge` or `unavailable` and the cards are read by hand; the Kiwi fare-page fixture is synthetic and labelled; the Asia airline sites are registry entries without recipes until a live flow completes.

## [2.1.0]

Everything here comes from a live test run (ZRH–GIG, 25 date pairs, four cabins, every route hack, BrowserAct `chrome`, 2026-10-08/09).

- **Speed.**
  - New `scripts/flightlist.py`: one FlightList date-range search (200 itineraries across 15 of 25 pairs in 23 s) becomes rows for every pair it covers, both directions included, and it lists the pairs it did not cover.
  - New `scripts/gflights.py`: exact Google Flights URLs for every cabin, one-way, multi-city and several airports at once (the `?q=` link failed for premium and first), a results-page parser, and an unattended BrowserAct sweep. The sweep waits for the first priced card instead of a fixed delay, checks that the page repeats the cabin and dates, and stops at a challenge.
  - SKILL.md has a fast path: discover with FlightList, confirm the cheapest pairs on Google, reprice in a parallel session. Different sites now run in parallel sessions or subagents; one search at a time per site remains.
- **run_log.py.**
  - `add` takes a JSON array or JSON Lines, all or nothing.
  - `rank` shows dates, legs, sellers and booking links, and `--top N` limits the leads shown.
  - `check` groups "may beat best qualified" warnings into one line per cabin (the test run produced 126 lines).
  - Seller wording such as TAP's `Mixed Cabin` is flagged as a mixed cabin.
- **Recipes.**
  - Google Flights: always-present "Loading results" text; section headings; daily search allowance (HTTP 429 → `google.com/sorry` after about 90 searches in 24 h); booking page hidden by location.
  - FlightList: range search, extraction snippet, and the Kiwi fare page as a qualification path. A FlightList "with bag" price matched neither Kiwi fare family.
  - eDreams: German labels and the checkout summary.
  - ITA Matrix: exact cabin labels and currency.
  - TAP: long-haul fare panels, the "from" price below the cheapest family, a stopover kept in browser storage, the Portugal Stopover tool.
  - Air France and KLM: silent 403, detected through the network log.
  - SWISS and GOL findings.
- **Route hacks.**
  - How to record positioning flights (as tickets) versus rail (a component).
  - Same-day self-transfer timing against the duration cap.
  - Stopover legs and Google multi-city open jaws.
  - New table of sellers that show bags and the total before passenger details (`qualification.md`).
- **Dated observations** for the run in `historical-observations.md`.

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
