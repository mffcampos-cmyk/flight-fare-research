# Flight Fare Research 2.0 — design

Date: 2026-10-08. Status: approved in conversation, awaiting written-spec review.

## 1. Purpose (from the brief)

Find the best genuinely usable flight options, not just the lowest advertised
fare. Compare exact dates, requested cabins, baggage, journey time and route
hacks, with evidence for every shortlisted price.

It is an agent workflow with browser recipes, not a flight-search engine. The
agent performs the searches. The scripts only keep books: `source_ledger.py`
tracks source health and `run_log.py` tracks one run's evidence. Nothing books
flights or handles payments.

**Key rule.** An advertised fare or a partially priced hack is a *lead*, not a
verified recommendation. Unresolved baggage, return journey or positioning
cost is labelled explicitly. The search is never called complete while
requested comparisons remain unfinished.

### Decisions taken during brainstorming

| Topic | Decision |
|---|---|
| Overall approach | Restructure in place (approach A). `skill/` stays canonical; host copies stay generated. |
| Coverage tooling | New stdlib script `run_log.py`. `source_ledger.py` stays health-only. `tests/rules.py` logic moves into the shipped script. |
| Cowork | Drop the hand-authored card. `package.py` builds a zip of the full skill for Cowork upload. |
| Browsers in use | browser-act managed (stealth/headless) browser, Claude in Chrome / built-in browser, and unattended runs. |
| Anti-blocking | Real-user browser first, persistent profiles, polite pacing, human handoff only when attended. No CAPTCHA solving, proxy/TLS rotation or fingerprint changes enabled by the skill. |
| Source expansion | After the refactor, probe new candidate sources live from this environment (network to be opened by the user) with headless Chromium. |
| Version | 2.0.0 (behaviour and interfaces change). |

### Non-goals

- No booking, checkout, payment, account creation or credential handling.
- No live sites in automated tests or CI.
- No automated CAPTCHA solving, proxy or TLS rotation, fingerprint spoofing,
  session import, or private-API reverse engineering.
- No search engine in Python: scripts never fetch fares.

## 2. Layout

```
skill/                              canonical; the only place content is edited
  SKILL.md                          rewritten; body <= 2,000 words
  scripts/
    run_log.py          NEW         run evidence: contract, rows, coverage, gates, rank, check
    source_ledger.py    changed     source health (+ engine, ad-hoc sources, new candidates)
  references/
    intake.md           NEW         intake questions, defaults, contract format, scope choice
    browser-engines.md  NEW         engine ladder, pacing, challenge handling, per-tool notes
                                    (replaces browser-act-support.md)
    qualification.md    NEW         directions, cap, cabins, bag states, repricing, currency
    route-hacks.md      NEW         hack matrix, all-in, break-even, stopovers, pruning,
                                    lead discovery (absorbs lead-discovery.md)
    source-ladder.md    trimmed     connectors, quick/full ladder, independence test, APIs
    source-health.md    changed     ledger runbook + expansion probe runbook
    event-anchored-trip-planning.md kept (light edits)
    historical-observations.md      single dated archive (absorbs docs/source-support-matrix.md)
    google-flights-browser.md, flightlist-browser.md, edreams-browser.md,
    ita-matrix-browser.md, azair-browser.md, airline-direct.md
                                    per-source recipes, host-neutral
integrations/
  claude-code/  codex/              generated copies (mechanism unchanged)
  hermes/install.sh                 unchanged
  cowork/README.md      NEW         how to upload the built zip
dist/flight-fare-research-cowork.zip  built by package.py; gitignored; CI artifact
tests/                              offline only; rules.py and its tests replaced
docs/
  safety-and-provenance.md          updated
  manual-release-checklist.md       updated
  release-evidence/2026-09-23.json  kept (historical)
  superpowers/specs/                this spec
```

Deleted: `integrations/cowork/SKILL.md`, `skill/references/browser-act-support.md`,
`skill/references/lead-discovery.md`, `docs/feedback-review.md`,
`docs/cowork-v1.8-review.md`, `docs/source-support-matrix.md`, `tests/rules.py`,
`tests/test_static_validation.py`, `tests/test_pruning.py`, `tests/test_cowork.py`,
`tests/fixtures/observations.json`.

## 3. SKILL.md workflow

Frontmatter description:

> Use when the user wants flight prices found, compared or verified: cheapest
> or best flights, fixed or flexible dates, cabin comparisons, checked-bag
> costs, nearby-airport, split-ticket, open-jaw or stopover route hacks, or
> flights around a fixed event. Research only; never books.

The key rule sits at the top. The body lists six phases; each points to its
reference and to the `run_log.py` command that records it.

1. **Intake.** One message asking only for what is missing, each with a
   proposed default: route and acceptable airports; dates (fixed, or a flexible
   range plus trip length); passengers including child ages; cabins; checked
   and cabin bags per person; currency; per-direction duration cap and whether
   it is strict; positioning tolerance (nearby airports, rail, extra cost or
   time, overnight); whether self-transfer or separate tickets are acceptable;
   any fixed event or arrival deadline. Unattended runs fall back to stated
   defaults and list them as assumptions. `run_log.py init` writes the contract.
2. **Scope.** Quick for fixed dates, one cabin, short/medium haul and no hack
   request. Full otherwise (flexible dates, long-haul, several cabins, route
   hacks, stopover or fixed event). Scope and permissions determine the
   expected comparisons.
3. **Collect.** Full path: source-health gate first. Choose the engine per the
   ladder. Follow the source recipe, verify the page repeats the exact search
   settings, and `run_log.py add` after every observation, including blocked
   and empty attempts. Run `coverage` before leaving the phase.
4. **Hacks.** Test the applicable hacks: split one-ways, open-jaw/multi-city,
   nearby departure airports, alternative destination airports, stopovers.
   Record every cost component; an unpriced component keeps the row a lead.
   Use `rank` for pruning.
5. **Qualify.** Select both directions, enforce the cap per direction, keep
   mixed-cabin labels, verify baggage per ticket, reprice with the airline or
   booking provider. A repriced row supersedes the list row, which stays as a
   labelled stale observation.
6. **Cross-check and report.** Attempt at least two independent source
   families. Rank with `rank`. The report has local times, risks, retrieval
   timestamps and booking links, a separate "Leads (not verified)" section, and
   ends with `Complete`, or `Incomplete:` plus the open items from `check`.

### Browser engines and blocking

Ladder (the engine is recorded on every row and ledger probe):

1. The user's real browser: Claude in Chrome, the desktop built-in browser, or
   Cowork's browser.
2. browser-act with one persistent named browser reused across runs (consent
   and cookies kept), headed when a display exists.
3. The host's headless browser tool.

A block on a lower rung does not prove a block on a higher rung; the source may
get one probe on the higher-rung engine.

Polite automation: one site at a time per session, no parallel tabs on one
site, deep links over repeated form submits, human-scale pacing between
searches, a per-site search budget per run, decline cookies once and reuse the
session, and prefer sources the ledger marks `ok` for this engine.

Challenge handling: unattended, record `blocked` with the engine and move on.
Attended and in the user's own visible browser, the agent may ask the user to
complete the check, then continue.

Not done: enabling or tuning CAPTCHA solving, proxy/TLS rotation or fingerprint
changes; importing others' sessions; reverse-engineering private APIs. If the
host's browser-act setup already runs its stealth browser, the skill uses that
browser as configured, never turns those features on, and never uses them to
retry a blocked source.

## 4. `run_log.py`

Python standard library only; no network. Run directory:
`$FFR_RUNS/<run-id>/`, else `$XDG_STATE_HOME/flight-fare-research/runs/<run-id>/`,
else `~/.local/state/flight-fare-research/runs/<run-id>/`. Every command takes
`--run DIR`; the default is the most recently modified run directory.

Files: `contract.json` (written by `init`) and `rows.jsonl` (append-only;
records of type `row` or `resolve`).

### Contract

```json
{
  "run_id": "zrh-lis-nov",
  "scope": "full",
  "trip_type": "return",
  "travelers": {"adults": 2, "children_ages": [7], "infants": 0},
  "currency": "CHF",
  "origins": ["ZRH"],
  "nearby_origins": ["BSL", "GVA"],
  "destinations": ["LIS"],
  "alt_destinations": ["OPO"],
  "dates": {"rolling": {"first_outbound": "2026-11-05", "last_outbound": "2026-11-08", "trip_days": 7}},
  "cabins": ["economy", "premium"],
  "bags": {"checked_per_person": 1},
  "max_duration": {"value": "20:00:00", "strict": true},
  "positioning": {"allowed": true, "rail_ok": true, "overnight_ok": false},
  "self_transfer_ok": false,
  "hacks": ["split", "open_jaw", "nearby_origin", "alt_destination"],
  "event": null,
  "assumptions": ["economy assumed because no cabin was given"]
}
```

- `dates` is one of `pairs` (explicit `[out, ret]` list), `rolling`
  (`first_outbound`, `last_outbound`, `trip_days`), or `cartesian`
  (`outbound_from/to`, `return_from/to`, `confirmed: true` required).
  One-way contracts use `outbound` dates only.
- Required: `scope`, `trip_type`, `travelers.adults >= 1`, `currency`,
  `origins`, `destinations`, `dates`, `cabins`, `bags.checked_per_person`.
  Missing or invalid fields exit 2 with a list, which forces intake to finish.
- Defaults: `max_duration` null (no cap), `positioning.allowed` false,
  `self_transfer_ok` false, `hacks` = the four non-stopover hacks on the full
  path (`stopover` only when requested), `nearby_origin` only on the quick path.

### Expected comparisons (cells)

`init` expands dates and writes the cell list into the contract:

| Cell id | Quick | Full | Done when |
|---|---|---|---|
| `<cabin>/baseline/<O>-<D>/<out>_<ret>` per date pair x home origin x destination | yes | yes | at least one populated row, or resolved |
| `<cabin>/hack/<hack>` per permitted hack | `nearby_origin` only | each hack | a qualified row, or every populated row is rejected or pruned, or resolved |
| `<cabin>/crosscheck` | yes | yes | rows (any outcome) from at least 2 source families |
| `<cabin>/reprice` | yes | yes | a qualified row in that cabin, or resolved `none_qualify` |

Hacks the contract forbids are auto-resolved `na` with the reason (for example
`nearby_origin` when positioning is not allowed or no nearby origins were
given; `split` and `open_jaw` on one-way trips; `alt_destination` without
alternative destinations).

A cell whose only rows are blocked, empty or error attempts stays open.

### Row

```json
{
  "source": "google-flights", "family": "google", "engine": "claude-in-chrome",
  "outcome": "populated",
  "url": "https://...", "retrieved_at": "2026-10-08T14:03:00+02:00",
  "cabin": "economy", "cabin_label": "Economy",
  "hack": null,
  "origin": "ZRH", "destination": "LIS",
  "outbound_date": "2026-11-05", "return_date": "2026-11-12",
  "currency": "CHF", "fx": null, "price_basis": "total",
  "tickets": [
    {"price": 407.70, "quote_state": "completed", "provider": "TAP",
     "baggage": "included", "bag_fee": null, "booking_url": "https://..."}
  ],
  "directions": [
    {"dir": "out", "from": "ZRH", "to": "LIS", "dep": "2026-11-05T07:10:00",
     "arr": "2026-11-05T09:05:00", "duration": "02:55:00", "stops": 0,
     "airlines": ["TP"], "airport_change": false, "self_transfer": false}
  ],
  "components": {"positioning": null, "hotel": null, "transfers": null},
  "positioning_overnight": false,
  "supersedes": null,
  "notes": ""
}
```

- `outcome` is `populated` (default) or `blocked`, `empty`, `error`. Attempt
  rows need only source, family, engine, outcome, url, retrieved_at, cabin and
  the cell-identifying fields.
- `quote_state`: `list`, `completed`, `repriced`. `baggage`: `included`,
  `fee_required`, `unverified`. `bag_fee` is the total for all requested bags
  on that ticket.
- `components`: amount, `null` (needed but unpriced), or absent (not needed).
- `fx`: `{"rate": r, "date": "YYYY-MM-DD", "source": "..."}` converting the
  row currency to the contract currency.
- `add` assigns ids `r1, r2, ...`, validates required fields (exit 2 on
  failure) and appends immediately.

### Computed statuses

Evaluated in this order; the first match wins.

1. `superseded`: another row names it in `supersedes`.
2. `attempt`: outcome is not `populated`.
3. `rejected` (hard gate failed): a direction duration `>=` cap (strict) or
   `>` cap (inclusive); a self-transfer when `self_transfer_ok` is false; cabin,
   dates, origin or destination outside the contract; a `nearby_origin` row,
   or any row with a `positioning` component, when positioning is not allowed; `positioning_overnight` when `overnight_ok` is
   false.
4. `lead`, with reasons: outbound or return direction missing; a direction
   without duration; a ticket still `list`; baggage `unverified` or
   `fee_required` without `bag_fee` when checked bags were requested; a `null`
   component; currency differs from the contract without `fx`; per-person
   pricing with infants present.
5. `qualified`: everything resolved.

All-in total for a qualified row: ticket prices (times adults plus children when
`price_basis` is `per_person`) + bag fees when `fee_required` + components,
converted with `fx` when present.

Lower bound for a lead: the same sum with unknown parts counted as 0. Never
reported as a price.

Risk flags (for ranking practicality, not gates): mixed cabin (label differs
from the pure cabin), airport change, next-day arrival, separate tickets, two
or more stops, positioning or hotel present.

### Commands and exit codes

| Command | Purpose | Exit |
|---|---|---|
| `init --contract FILE [--runs-root DIR]` | validate, expand, write contract and cells | 0, 2 |
| `add --row FILE` (or `-` for stdin) | validate and append a row; print its id and status | 0, 2 |
| `resolve CELL --as na\|no_fare\|none_qualify --reason TEXT` | close a cell without a qualified row | 0, 2 |
| `coverage [--json]` | cells: open/done/resolved, row counts | 0 |
| `rank [--cabin C] [--json]` | qualified rows by all-in, then longest direction, then stops, with risk flags; leads with reasons, lower bound and `pruned: LB x >= best y` | 0 |
| `check [--json]` | `COMPLETE` or `INCOMPLETE` with `OPEN` items; `WARN` lines for unqualified leads cheaper than the best qualified option and single-family corroboration | 0 complete, 4 incomplete, 2 usage |

Pruning is recomputed on every call, so a pruned lead comes back when the best
qualified option is superseded or rejected.

## 5. `source_ledger.py` changes

- `record ... --engine NAME` stores the engine that produced the state; `status`
  and `order` show it.
- `record ID STATE --add --name N --role R --family F [--url U]` registers a
  source missing from the built-in registry.
- New roles `positioning` (rail/bus prices for positioning legs) and `routes`
  (which airlines fly which routes; no fares). `ok` for these roles still
  requires `--results N`.
- Candidate sources are added to the registry as untested (non-core):
  Booking.com Flights, Alternative Airlines, lastminute.com, Gotogate/Mytrip,
  Aviasales; re-tests of Skyscanner, KAYAK/Momondo, Kiwi, Trip.com, Expedia;
  airline-direct SWISS/Lufthansa, easyJet, Ryanair, Vueling/Iberia,
  KLM/Air France, British Airways; stopover programmes of Turkish, Icelandair
  and Qatar; positioning SBB, Trainline, Omio; routes FlightConnections.
  Opodo is listed in the `edreams` family (not independent).
- Timestamps without a timezone are treated as UTC instead of crashing.

## 6. References and docs

- `intake.md`: question template, field defaults and rationale, contract
  mapping, unattended defaults, scope choice, worked example.
- `browser-engines.md`: engine detection (Claude in Chrome and built-in browser
  tools, Cowork navigate/read_page/javascript tools, `command -v browser-act`,
  Hermes `browser_exec`); ladder, pacing and challenge policy; browser-act notes
  without host-specific paths (load browser-act's own skill or `get-skills`,
  one persistent named browser, reopen sessions, run the CLI as the browser's
  OS user); shared techniques (one `innerText` read, fresh screenshot before
  coordinate clicks, date-picker index); a table mapping "run in page" snippets
  to each engine.
- `qualification.md`: both directions, per-direction cap, mixed-cabin labels,
  bag states (zero-based range = unverified), fare family vs base + bag fee,
  reprice supersedes list, currency and pricing basis, `run_log` field mapping.
- `route-hacks.md`: hack matrix and intake permissions, all-in and break-even
  budget, positioning timing, stopover construction, hidden-city rejection with
  checked bags, pruning via `rank`, keyless-first lead discovery.
- `source-ladder.md`: connectors, quick and full ladders, independence test,
  official APIs. The FlightList recipe moves to `flightlist-browser.md`.
- Per-source recipes: drop "issue 2.4" references and host-specific paths;
  `js()`/`cdp()` notation becomes "run in page" via the engine table; keep
  dated provenance.
- `historical-observations.md`: single dated archive, including the former
  support-matrix rows (blocked frontends with failure modes, 2026-09-23 working
  sources, 2026-10-03 canary).
- `source-health.md`: engine field, `--add`, the cross-engine rule, a generic
  no-browser fallback, and the expansion-probe runbook.
- README rewritten around the purpose, the six phases, per-host install
  (including Cowork zip upload), requirements and the capability boundary.
- `safety-and-provenance.md`: engine and challenge policy, lead/qualified
  statuses, inline citation rule (no `grounded-citations` dependency).
- Release checklist and CONTRIBUTING updated; CHANGELOG gains 2.0.0.

## 7. Packaging, validation, tests, CI

- `package.py`: refresh Codex and Claude Code copies; build
  `dist/flight-fare-research-cowork.zip` with root folder
  `flight-fare-research/`, sorted entries and fixed timestamps (deterministic).
- `validate.py`: remove the Cowork card lint; add SKILL.md body <= 2,000 words;
  version agreement between SKILL.md frontmatter, `plugin.json` and the top
  CHANGELOG heading; both scripts compile and `--help` exits 0; zip, when
  present, matches canonical files. Keep reference resolution and copy parity.
- Tests (offline): `test_run_log.py` covering date expansion (cartesian needs
  `confirmed`), strict and inclusive caps at exactly `20:00:00`, each lead
  reason, rejection gates, superseded rows, currency without fx, blocked-only
  cells staying open, `resolve`, exit codes 0/4/2, rank order, pruning and
  re-admission, append-only persistence; an end-to-end quick-run fixture moving
  from Incomplete to Complete; ledger additions; zip determinism and parity;
  new validation checks.
- Skill behaviour check (writing-skills method): subagents get the skill and
  fixture data in pressure scenarios (hurried user with a `CHF 0–104` bag
  range; hack with unpriced positioning; a cabin blocked everywhere). Pass
  means leads are labelled and the report says Incomplete. No live sites.
- CI: pin `pytest>=8,<10`, build and upload the zip, keep the drift guard and
  secret scan.

## 8. Source-expansion probe (after the refactor)

Runs in this cloud environment once the user widens network access.

- Engine: headless Chromium via Playwright on a datacenter IP (ladder rung 3).
  Recorded as such; a block here is not evidence of a block in a real browser.
- Contract: `source_ledger.py canary` (ZRH-LIS, today+30, 7 days, 1 adult,
  economy, CHF). Positioning sources use a rail variant (for example Basel SBB
  to Zurich Airport on the departure date); routes sources use "nonstop routes
  from ZRH". Variants are written into `--evidence`.
- One polite attempt per candidate, paced, cookies declined, no retries after
  an explicit block. Screenshots and raw text stay in the scratchpad, not the
  repo.
- Each result is recorded in the ledger with `--engine headless-playwright`.
  Dated outcomes go into `historical-observations.md` and the registry seed.
  Sources that return populated exact-date results are promoted into the
  ladder; a new recipe reference is written only when a working flow was
  observed.

## 9. Assumptions and risks

- Cowork accepts a zip upload containing scripts and can run them. If not, the
  README says so and the zip still works for other zip-based skill hosts.
- `SKILL.md` must stay under 2,000 words while carrying the key rule, phases,
  gates and output shape; detail lives in references.
- The probe depends on the user opening network access; if hosts stay blocked,
  candidates remain untested in the ledger and the runbook covers a later
  probe from the user's machine.
- browser-act command names change between versions; recipes defer to its own
  skill for current syntax.
