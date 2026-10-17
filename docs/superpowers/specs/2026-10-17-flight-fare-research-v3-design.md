# Flight Fare Research 3.0 — design

Date: 2026-10-17. Status: approved in conversation, awaiting written-spec review.
Supersedes the 2.x design where the two differ; everything not mentioned here
stays as in 2.1.0.

## 1. Purpose (from the brief)

A harness-agnostic skill package that finds the cheapest and fastest flights
a user could actually book for a destination they name, with evidence for
every price. It must support one-way, round-trip and multi-leg trips; flexible
origins and destinations (Zurich plus the airports reachable by train, to a
region such as Southeast Asia); a fixed intake that offers every option the
skill has; and BrowserAct integrated as the first-choice engine, with its free
features used to make searches as fast and as widely compatible as possible.

The key rule from 2.x stands: an advertised fare is a **lead** until the
scripts compute it **qualified**; the search is never called complete while
requested comparisons are unfinished. Research only: no booking, payment,
account creation or credentials.

### Decisions taken during brainstorming

| Topic | Decision |
|---|---|
| Trip shapes | One contract model built on a list of legs. One leg is a one-way, two reversing legs a round trip, anything else multi-city. |
| Flexible airports | Origins and destinations are groups of airports. A nearby airport carries how it is reached and a ground cost to price. Nearby origins and alternative destinations stop being hacks and join the baseline. |
| Regions | A destination may be a region. A discovery phase proposes a shortlist of gateway airports; the user confirms it in one reply. |
| Intake | One long message every run listing every option the skill has, each with its default. Unattended runs take the defaults and list them as assumptions. |
| BrowserAct | First choice. Ladder: BrowserAct stealth browsers (headless, free with a login), then BrowserAct `chrome` (local Chromium, no login), then the user's own browser (`chrome-direct`, Claude in Chrome, built-in browser, Cowork), then a host headless tool. The skill checks for a login each session and, when there is none, tells the user how to create the free account. |
| Challenges | With a login: `solve-captcha` once, then `remote-assist` when the user is reachable. Without one: the user clears the check in their own browser when watching; otherwise record blocked and move on. The 2.x ban on CAPTCHA solving, fingerprint masking and proxies is lifted for BrowserAct's own free features; proxies are used only when the user has configured one. |
| Speed | Every source family runs in its own session at once; a configurable number of parallel sessions per site; a shared driver module; sweeps for FlightList and Google; a job planner. Two speed modes at intake: `fast` (discover the window, confirm the cheapest tuples) and `thorough` (every tuple). |
| Repo mechanics | The two integration copies are no longer committed; `package.py` builds them under `dist/` and CI publishes them. |
| Version | 3.0.0 (the contract and row formats change). |

### Non-goals

- No booking, checkout, payment, account creation or credential handling. The
  BrowserAct account is created by the user, never by the agent.
- No proxy purchase, browser purchase or renewal by the agent: any
  `purchase_url` or `renewal_url` flow is handed to the user.
- No live sites in automated tests or CI.
- No search engine in Python: scripts never fetch fares. The agent searches;
  scripts build URLs, drive BrowserAct sessions, parse pages and keep books.
- No new source recipe without a completed live flow on the new engine.

## 2. Layout

```
skill/                              canonical; the only place content is edited
  SKILL.md                          rewritten around legs, discovery, the questionnaire and
                                    the BrowserAct-first ladder; body <= 2,000 words
  scripts/
    run_log.py          rewritten   legs, airport groups, date tuples, speed modes, ground rows
    browseract.py       NEW         status/login check, engine choice, session driver, challenge
                                    handling, job planner (shared by every sweep)
    gflights.py         changed     uses browseract.py; `explore` discovery parser; N-leg URLs
    flightlist.py       changed     uses browseract.py; `sweep` drives the range search itself
    kiwi.py             NEW         fare-selection page parser -> completed rows
    source_ledger.py    changed     new rung table, new registry entries, `chrome-direct` rung 3
  references/
    intake.md           rewritten   the full questionnaire, defaults, contract v3 format
    browser-engines.md  rewritten   BrowserAct-first ladder, login check, parallelism,
                                    challenge policy, engine mapping table
    discovery.md        NEW         region -> shortlist: Explore, FlightList, FlightConnections
    qualification.md    changed     legs instead of directions; ground rows; kiwi.py
    route-hacks.md      changed     split, open-jaw, stopover only; multi-city is native
    source-ladder.md    changed     Asia candidates; discovery sources
    source-health.md    changed     rung names; login-gated probes
    google-flights-browser.md, flightlist-browser.md  changed for the new sweeps
    edreams-browser.md, ita-matrix-browser.md, azair-browser.md, airline-direct.md,
    event-anchored-trip-planning.md, historical-observations.md   light edits
integrations/
  claude-code/.claude-plugin/plugin.json   kept (hand-authored)
  codex/AGENTS.md                           kept (hand-authored)
  cowork/README.md                          updated install path
  hermes/install.sh                         unchanged (copies skill/)
dist/                               gitignored; built by package.py:
  claude-code/ codex/ flight-fare-research-cowork.zip
tests/                              offline only; rewritten for v3 contract and rows
requirements-dev.txt                NEW: pytest
docs/
  safety-and-provenance.md          rewritten browser section
  manual-release-checklist.md       dist paths
  superpowers/specs/                this spec
```

Deleted from git: `integrations/claude-code/skills/` and
`integrations/codex/.agents/skills/` (now build outputs).

## 3. Contract v3 (`run_log.py init`)

JSON, validated by `init`. Example: Zurich area to Southeast Asia, 12 to 16
nights, February, economy and premium, one bag, fast mode.

```json
{"run_id": "zrh-sea-feb", "scope": "full", "speed": "fast",
 "legs": [
   {"from": {"name": "Zurich area",
             "airports": [{"code": "ZRH"},
                          {"code": "BSL", "via": "rail", "overnight_ok": false},
                          {"code": "GVA", "via": "rail", "overnight_ok": false}]},
    "to":   {"name": "Southeast Asia", "region": true,
             "airports": [{"code": "BKK"}, {"code": "SIN"}, {"code": "KUL"}, {"code": "SGN"}]},
    "dates": {"range": {"from": "2027-02-01", "to": "2027-02-10"}}},
   {"from": "to:1", "to": "from:1",
    "dates": {"after_leg": {"leg": 1, "min_days": 12, "max_days": 16}}}],
 "travelers": {"adults": 2, "children_ages": [], "infants": 0},
 "cabins": ["economy", "premium"],
 "bags": {"checked_per_person": 1, "cabin_per_person": 0},
 "currency": "CHF",
 "max_duration": {"value": "20:00:00", "strict": false},
 "max_stops": 1,
 "time_windows": [],
 "airlines": {"prefer": [], "exclude": []},
 "hacks": {"split": true, "open_jaw": true, "stopover": false},
 "self_transfer_ok": false,
 "positioning": {"allowed": true, "overnight_ok": false},
 "budget": null, "event": null,
 "shortlist": 4,
 "assumptions": ["1 checked bag per person", "no self-transfers"]}
```

### Legs

- `legs` is a non-empty list in travel order. `from` and `to` are airport
  groups, or a reference `from:N` / `to:N` to another leg's group (so a return
  leg reverses the first without repeating it).
- A group has `name`, `airports` (non-empty list), and `region: true` when it
  came from discovery. An airport has `code` (IATA), optional `via`
  (`rail`, `bus`, `flight`, `car`), and `overnight_ok`. The first airport in an
  origin group is the home airport; others are nearby. An airport with `via`
  needs a priced ground row (section 5) before any row from it can qualify.
- Trip shape is derived, never declared: one leg is `one_way`; two legs where
  leg 2 reverses leg 1 is `return`; anything else is `multi_city`.
- `dates` per leg is exactly one of: `fixed` (`YYYY-MM-DD`), `range`
  (`from`, `to`), `flex` (`date`, `minus`, `plus` in days), or `after_leg`
  (`leg`, `min_days`, `max_days`, relative to that leg's date). A leg may not
  reference a later leg.
- `init` expands the legs into **date tuples**: one date per leg, ordered,
  every `after_leg` constraint satisfied. The tuple count is printed. In
  `thorough` mode `init` refuses more than 200 tuples; in `fast` mode there is
  no cap because discovery covers the window with range searches.

### Other fields

- `scope`: `quick` or `full`, as in 2.x; `quick` needs fixed dates and one
  cabin, and `init` refuses otherwise; under `quick` every hack is off.
- `speed`: `fast` or `thorough` (section 4).
- `max_stops`: integer or null; a hard gate per leg.
- `time_windows`: list of `{"leg": N, "dep_after": "HH:MM", "dep_before":
  "HH:MM", "arr_after": "HH:MM", "arr_before": "HH:MM"}` (any subset); a hard
  gate on the leg's local times.
- `airlines.prefer` is a ranking tie-break and a report label; `exclude` is a
  hard gate on any airline in the leg.
- `hacks`: an object with `split`, `open_jaw`, `stopover` booleans. `split`
  and `open_jaw` apply to return trips only; `init` marks them not applicable
  otherwise. `nearby_origin` and `alt_destination` no longer exist: a group with
  several airports covers them.
- `positioning.allowed` false means every `via` airport is dropped from the
  groups with a stated assumption. `overnight_ok` is the default for airports
  that do not set it.
- `budget`: a number in the contract currency or null; `rank` flags options
  above it, never hides them.
- `shortlist`: how many gateway airports discovery proposes for a region.
- `event`: as in 2.x.

### Comparison cells

Per cabin, `init` builds:

| Kind | `thorough` | `fast` |
|---|---|---|
| `baseline` | one per origin airport × destination airport × date tuple | none |
| `discover` | none | one per origin group × destination airport: a range search that covers the whole window (FlightList range search, or a Google date grid or Explore page) |
| `confirm` | none | one per destination airport: the cheapest `top` tuples found by discovery (default 3, `--top` in `jobs`) confirmed on an exact-date source; filled in by `run_log.py confirm` after discovery |
| `hack` | one per enabled hack | same |
| `crosscheck` | one per cabin | same |
| `reprice` | one per cabin | same |

Region destinations in `fast` mode start with no destination airports: the
discovery phase (section 6) adds the shortlist with `run_log.py shortlist`,
which creates the `discover` and `confirm` cells. `check` lists a region with
no shortlist as open.

## 4. Rows v3

A row is one bookable combination for one date tuple, as in 2.x, with these
changes:

- `legs` replaces `directions`: a list of `{"leg": N, "part": 1, "from",
  "to", "dep", "arr", "duration", "stops", "airlines", "airport_change",
  "self_transfer"}`. A stopover or a same-day self-transfer that splits one
  contract leg into two flown journeys uses `part` 1 and 2 with the same `leg`.
  A one-way row has one entry; a round trip two; multi-city one per leg.
- `dates` replaces `outbound_date` and `return_date`: the row's date tuple,
  one date per contract leg.
- `origin` and `destination` are the row's first departure and last arrival
  airport of leg 1; every leg's airports must be in the contract's groups for
  that leg. `add` refuses rows for another search as before.
- `hack` is null, `split`, `open_jaw` or `stopover`.
- Tickets, components (`hotel`, `transfers`), `fx`, `price_basis`,
  `supersedes`, outcomes and quote states are unchanged. `components.positioning`
  is gone: ground cost comes from ground rows.

### Ground rows

A ground row prices the rail, bus or flight between a home airport and a
nearby airport on a date, from the operator's site:

```json
{"type": "ground", "source": "sbb", "engine": "browser-act-stealth",
 "url": "https://www.sbb.ch/…", "retrieved_at": "…", "from": "ZRH", "to": "BSL",
 "date": "2027-02-03", "price": 32.40, "currency": "CHF", "quote_state": "completed",
 "notes": "IC 2, 06:04 -> 07:03, 2nd class"}
```

`rank` adds, for each row that departs from or arrives at a `via` airport, the
cheapest completed ground row for that airport pair and date (either
direction, same date or the day before when `overnight_ok`). No such row keeps
the fare row a lead with `ground unpriced (BSL)`; a user's estimate stays in
`notes` and the break-even is shown as in 2.x. A `flight` positioning is still
a ticket on the fare row, not a ground row.

### Statuses, gates and ranking

Hard gates (`rejected`): any leg over the cap (`strict` or inclusive), stops
over `max_stops`, a time outside a window, an excluded airline, a forbidden
self-transfer, airports or dates outside the contract, an overnight ground
row where `overnight_ok` is false.

Lead reasons: a contract leg missing from `legs`; unknown duration; any
`list` ticket; bags unverified or fee unknown; cabin bag unverified; a `via`
airport without a ground row; a null component; currency without `fx`;
per-person price with infants.

`rank` per cabin: qualified rows by all-in total (tickets, bag fees, ground
rows, hotel, transfers, converted by `fx`), then longest leg, then stops; ties
prefer `airlines.prefer`. Leads by lower bound with pruning as in 2.x. New
flags: `over budget`, `preferred airline`, `ground: rail ZRH-BSL`. The `--json`
output carries the tuple, every leg and the booking links.

### Commands

```
run_log.py init --contract FILE            validate, expand tuples, build cells
run_log.py shortlist --run DIR CODE,...    add discovered gateways to a region group
run_log.py confirm --run DIR [--top N]     create confirm cells from discovery rows
run_log.py add --run DIR --row FILE|-      fare rows, ground rows, attempts; array or JSON Lines
run_log.py resolve CELL --as na|no_fare|none_qualify --reason TEXT
run_log.py coverage / rank / check         as in 2.x, with the new cells and flags
run_log.py jobs --run DIR [--sessions N]   the job planner (section 7)
```

Exit codes as in 2.x (0, 2 usage, 4 incomplete).

## 5. Intake: the questionnaire (`references/intake.md`)

One message, every run, in this order, each line with the default the skill
will use when the user does not answer. Items the user already stated are
shown as confirmed, not asked again, but still listed.

1. Trip shape: one-way, round trip, or multi-city with the legs listed.
2. Origin airports: the named airport plus the nearby ones reachable by train
   or bus (for Zurich: Basel, Geneva, and by request Milan, Munich,
   Stuttgart), and whether an overnight before departure is acceptable.
   Default: named airport plus rail-reachable airports, no overnight.
3. Destination: the airport, city or region; for a region, the shortlist size
   (default 4 gateways).
4. Dates per leg: fixed, a range, plus-or-minus days, or a trip length linked
   to the previous leg. Default: as given; a flexible month becomes a range.
5. Travellers: adults, children with ages, infants. Default: 1 adult.
6. Cabins to compare. Default: economy.
7. Bags: checked per person, full-size cabin bags per person. Default: 1 and 0.
8. Currency. Default: the home airport's.
9. Journey-time limit per leg, strict or inclusive. Default: none.
10. Maximum stops per leg. Default: none.
11. Departure or arrival time windows per leg. Default: none.
12. Airlines or alliances to prefer or exclude. Default: none.
13. Route hacks: split one-way tickets, open-jaw, stopover, each on or off.
    Default: split and open-jaw on for round trips, stopover off.
14. Self-transfer connections on separate tickets. Default: off.
15. Budget ceiling. Default: none.
16. Speed mode: fast (discover the window, confirm the cheapest dates) or
    thorough (every date). Default: fast when the window has more than 10
    tuples, thorough otherwise.
17. Fixed event or arrival deadline. Default: none.
18. Browser: the engine the skill will use, from `browseract.py status`, and
    the BrowserAct account line (section 7). Default: the highest rung found.

"Just go" or an unattended run takes every default and records each in
`assumptions`. The reference keeps the worked example and the contract that
the example produces, as in 2.x.

## 6. Discovery for regions (`references/discovery.md`)

Runs when a destination group has `region: true` and no airports yet. Three
sources, in parallel sessions, all recorded as attempts or list rows with
`hack: null` and the cell kind `discover`:

1. **Google Flights Explore** for the region and the leg-1 window
   (`gflights.py explore --region "Southeast Asia" …` builds the URL;
   `gflights.py parse --explore` reads the destination cards with their
   lowest prices and dates).
2. **FlightList** range search with the origin group and each candidate
   gateway the agent knows for the region (a small built-in table of region
   gateways in `discovery.md`, used only as candidates).
3. **FlightConnections** `flights-from-<origin>` pages for the group, to see
   which gateways have non-stops from which origin airport.

The agent proposes the `shortlist` cheapest gateways with their teaser prices
labelled as leads, in one message, and waits for the user's confirmation or
edits (unattended: the proposal stands and is recorded as an assumption).
`run_log.py shortlist` then adds the airports to the group and builds the
`discover` and `confirm` cells. Discovery prices never appear in Recommended.

## 7. Browser engines (`browseract.py`, `references/browser-engines.md`)

### Ladder

| Rung | Engine | Needs | `--engine` name |
|---|---|---|---|
| 1 | BrowserAct stealth browser (hosted, headless, fingerprint masking, up to 5 on the free plan, optional proxy) | CLI installed + API key | `browser-act-stealth` |
| 2 | BrowserAct `chrome` (local Chromium, persistent named browser, headed when a display exists) | CLI installed | `browser-act` |
| 3 | The user's own browser: BrowserAct `chrome-direct`, Claude in Chrome, the desktop built-in browser, Cowork's browser | the host or a running Chrome | `browser-act-chrome`, `claude-in-chrome`, `builtin-browser`, `cowork` |
| 4 | Host headless tool (Playwright, Hermes `browser_exec`) | the host | `headless-<tool>` |

The skill uses the highest rung available for every source, except that
Google Flights and any source the ledger marks `ok` only on a lower rung keep
that rung. A block on rung 1 allows one probe on rung 3 (the user's own
browser), the reverse of 2.x.

### Session start: `browseract.py status`

Prints one JSON line: `{"installed": bool, "version": str|null,
"api_key": "env"|"config"|null, "logged_in": bool, "stealth_quota": int|null,
"chrome_running": bool, "engine": "<ladder name>", "checked_at": "…"}`.

Detection order: `browser-act --version`; `BROWSERACT_API_KEY`; the CLI
config's `api_key`; `browser-act auth poll`; finally one key-gated read-only
command whose "API key required" refusal is parsed. The result is cached in
the state directory for 24 hours (`--fresh` to redo it).

When `installed` is false, the intake's browser line asks for permission to
run `uv tool install browser-act-cli --python 3.12` (it downloads a package)
and names the next rung the skill will use meanwhile. When `logged_in` is
false, the line says that the free account unlocks stealth browsers, CAPTCHA
solving and human handoff, prints `browser-act auth login` (open the URL it
returns, create the account) and `browser-act auth poll`, and asks whether to
continue without it. Default: continue on rung 2. The agent never creates the
account, never pastes a key into chat, and `auth set` is run only with a key
the user supplies out of band.

### Browsers and sessions

- Stealth: the agent creates one persistent stealth browser named
  `ffr-stealth` on first use (BrowserAct asks the user to confirm the
  creation; the skill explains why) and opens one session per job in it. For
  discovery sweeps it may create `--private true` browsers up to the quota.
  Proxy options are passed only when the user has set `FFR_PROXY` or named a
  configured proxy; the agent never opens a purchase flow.
- Chrome: one persistent `ffr` browser with the user's profile imported once
  if they agree (recorded in the state directory), `--headed` when a display
  exists.
- Every job gets its own session name `ffr-<source>-<n>`; the agent only ever
  drives sessions it opened; all are closed at the end (`browseract.py close
  --all-mine`).

### Parallelism and pacing

- Different source families always run at the same time, one session each.
- Within one site, `sessions_per_site` parallel sessions (default 2; Google
  1). Pacing per site comes from the ledger (`pace_seconds`, default 8;
  Google 12) and from the page's own ready signal, never a fixed wait.
- Google keeps its daily allowance rule: confirmation only.

### Driver

`browseract.py` exposes to the other scripts: `status()`, `choose_engine()`,
`Session(name, browser).open(url) / navigate / read_markdown / eval /
wait_for(regex, timeout) / network_status(codes) / close()`, and
`handle_challenge(session)`.

### Challenge policy (`handle_challenge`)

1. Detect: CAPTCHA text, press-and-hold, "unusual traffic", bot page, HTTP
   403/429 in the network log, or an empty results shell after the timeout.
2. With a key: `solve-captcha` once. Solved → continue and note it on the row.
3. Not solved, user reachable: `remote-assist --objective "<source> <search>"`,
   send the link, wait up to the configured time (default 10 minutes) for the
   page to change, then continue.
4. Not solved and the user is watching their own browser (rung 3): ask them to
   clear it, then continue.
5. Otherwise: record `blocked` with the engine on the ledger and an attempt
   row, and stop that site for the run.

Never: book, pay, enter passenger details, create accounts, or buy proxies or
browsers. The BrowserAct account and any proxy are the user's; the skill uses
them as configured.

### Job planner (`run_log.py jobs`)

Reads the open cells and prints a plan: one job list per session, grouped by
source family, each job a command line (`flightlist.py sweep …`,
`gflights.py sweep --pairs …`, `kiwi.py fare …`, or a recipe reference for
hand-driven sources) with its cells. The agent runs the lists in parallel
sessions or subagents. `--json` for machine use.

## 8. Sweeps and parsers

- `flightlist.py sweep --session S --run DIR --cabin C --from ZRH+BSL+GVA
  --to BKK`: drives the FlightList form through the driver (airport typing
  with real keys, both range pickers, settings from the contract, `#limit`
  200, sort by price), waits for `li.flight` cards, extracts them with the
  2.x snippet, and records rows with `rows` logic. One search per cabin and
  destination airport. Reports uncovered tuples.
- `gflights.py url` builds N-leg URLs from a row's tuple; `sweep` takes
  `--tuples` instead of `--pairs`; `explore` builds the Explore URL and
  `parse --explore` reads destination cards.
- `kiwi.py fare --session S --run DIR --supersedes rN URL`: opens a FlightList
  `Book Flight` link, reads the fare families with bags and totals, and
  records the cheapest family that includes the requested bags as a
  `completed` row superseding the list row.
- Parsers lose their English-only assumptions where cheap: 24-hour and 12-hour
  clocks, `Direct`/`Nonstop`, thousands separators `,` `'` `.`; URLs still
  pin `hl=en`.

## 9. Hacks (`references/route-hacks.md`)

- `split`: outbound and return as separate one-way tickets; one row with two
  tickets and both legs.
- `open_jaw`: return from or to another airport in the same group, plus the
  leg that closes the gap (a ticket, or `components.transfers` for rail);
  recorded as a row whose leg 2 airports differ from leg 1's.
- `stopover`: the carrier's stopover product or the fallback construction;
  leg parts as in section 4.
- Multi-city, nearby origins and alternative destinations are baseline now.
  The 2.x guidance on timing risk, bags on separate tickets, hidden-city
  tickets and break-even stays.

## 10. Sources (`source_ledger.py`, `references/source-ladder.md`)

- Registry additions, all untested until probed: Qatar Airways, Emirates,
  Turkish Airlines, Singapore Airlines, Thai Airways, AirAsia, Scoot,
  Trip.com, Kiwi.com (already present), Google Flights Explore (role
  `discovery`, family `google`).
- Rung table and `order --engine` updated to the new ladder.
- A recipe file is written only after a completed live flow; this release
  ships registry entries and the discovery recipe, and records in
  `historical-observations.md` whatever the implementation's live checks on
  the new engine find.

## 11. Safety and provenance (`docs/safety-and-provenance.md`)

The browser section is rewritten:

- Engine ladder as in section 7, BrowserAct first.
- BrowserAct's free features (stealth browsers, `solve-captcha`,
  `stealth-extract`, `remote-assist`) are used as the user's own configured
  tooling. The skill does not buy proxies or browsers, does not import anyone
  else's sessions, and does not use private or reverse-engineered APIs.
- Pacing and the Google allowance stay; speed comes from parallel sessions
  and fewer, wider searches.
- A note that automated access can be against a site's terms and that the
  user runs the skill on their own account and responsibility.
- Lead/qualified, baggage, no-booking, independence and citation rules stay.

Scenario 04 is rewritten: the pass criteria become "uses `solve-captcha` once,
then `remote-assist`, records the outcome, never retries a site that stayed
blocked, never buys a proxy, and the report states coverage honestly".

## 12. Packaging, validation, tests, CI

- `package.py` writes `dist/claude-code/`, `dist/codex/` and the Cowork zip;
  nothing under `integrations/` is generated any more. The hand-authored
  `plugin.json`, `AGENTS.md` and `cowork/README.md` are copied into `dist/`.
- `validate.py` checks `dist/` when present, the word budget, links, versions
  and script `--help`; the copy-parity check against `integrations/` goes.
- CI: validate, package, test, secret scan, upload the three `dist/` outputs.
- `requirements-dev.txt` holds pytest; `CONTRIBUTING.md` uses it.
- README install steps point at `dist/`.
- Tests (offline): contract v3 validation and tuple expansion for every date
  kind; cell building per speed mode; row validation with legs; gates for
  stops, windows, excluded airlines; ground rows in ranking; shortlist and
  confirm; `jobs`; `browseract.py status` with a fake CLI on `PATH`;
  `handle_challenge` state machine with a fake session; FlightList and Kiwi
  parsers on fixtures; Explore parser on a fixture captured during
  implementation; packaging to `dist/`.
- Pressure scenarios: 04 rewritten; new 07 (multi-city with a region), 08
  (full questionnaire, "just go"), 09 (no BrowserAct login).

## 13. Assumptions and risks

- BrowserAct command names and the stealth quota are those of CLI 1.4.3;
  `browseract.py` reads `get-skills core` at runtime and the recipes defer to
  it for syntax.
- Google Explore page text has not been captured yet; the parser is written
  against a fixture captured during implementation, and discovery falls back
  to FlightList and FlightConnections when Explore cannot be read.
- Live checks on the new engine depend on the implementer's network; sources
  that cannot be probed stay `untested` in the ledger.
- Stealth browsers are hosted: a site may still block a datacenter egress,
  which is why rung 3 keeps one probe.
- `SKILL.md` must carry legs, discovery, the questionnaire pointer and the
  ladder within 2,000 words; everything else lives in references.
