---
name: flight-fare-research
description: "Use when the user wants flight prices found, compared or verified: cheapest or best flights, one-way, round-trip or multi-city, fixed or flexible dates, nearby airports by train, a region such as Southeast Asia, cabin comparisons, checked-bag costs, split-ticket, open-jaw or stopover route hacks, or flights around a fixed event. Research only; never books."
version: 3.0.0
author: hermes-curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [flights, airfare, travel, prices, baggage, browser, browseract]
    related_skills: [product-price-monitor, browser-automation, browser-act]
---

# Flight Fare Research

Find the best flight the user could actually book, not the lowest advertised
fare: exact dates, every leg, the requested cabins, baggage, journey time and
route hacks, with evidence for every price you recommend. One-way, round trip
and multi-city; airport groups (Zurich plus Basel and Geneva by train); a
region destination that becomes a shortlist of gateways.

You do the searching in a browser, BrowserAct first. The scripts keep the
books and drive the sweeps (`python3 <skill_dir>/scripts/<name>.py`):

- `run_log.py`: the search contract, every observation row, each row's
  computed status, the parallel job plan, and whether the run is complete.
- `browseract.py`: BrowserAct login check, engine choice, sessions, the
  challenge policy.
- `flightlist.py sweep`, `gflights.py sweep`, `kiwi.py fare`: unattended
  discovery, exact-date confirmation and repricing through BrowserAct.
- `source_ledger.py`: which sources work, on which engine, at what pace.

Research only: stop before passenger details, and never book, pay, create
accounts (the BrowserAct account included) or handle credentials.

## The key rule

Every price is a **lead** until `run_log.py` computes it **qualified**: every
leg selected, each within the journey-time limit and the stop and time-window
gates, baggage resolved for the requested bags, every all-in part priced (a
nearby airport needs a priced ground row), and repriced on the seller's own
page. Recommend only qualified options. A lead appears in the report's
"Leads (not verified)" section with its reasons, never as the pick.

The search is **Complete** only when `run_log.py check` exits 0. Otherwise the
report's last line is `Incomplete:` followed by the open items `check` printed.

These are the moments the rule bends under pressure, and what to do instead:

| Temptation | What to do |
|---|---|
| The user gave a cost ("the train is about CHF 30"), so count it | No ground row, no total: show their estimate beside the break-even; the pick stays the best qualified option |
| They need a number now; an "indicative" figure with a caveat will do | Show it under Leads with its reasons. If no option in that cabin is qualified, say so plainly, and do not supply a figure to forward |
| The bag range starts at CHF 0, or a friend says the bag is included | Baggage is `unverified` until the completed page or fare family states it |
| Most of it is covered; no need to say incomplete | End with `Complete` or `Incomplete:` from `check`, every time |
| Skip the questionnaire, they are in a hurry | One message with every default; "just go" turns the defaults into listed assumptions |
| A discovery price is good enough to recommend | Discovery rows are leads; confirm, qualify, reprice |

## 0. Browser

Run `browseract.py status` first (`references/browser-engines.md`). It says
whether the BrowserAct CLI is installed, whether an account key exists, and
which engine you will use: a BrowserAct stealth browser (`browser-act-stealth`,
needs the free login) first, then BrowserAct's local Chromium (`browser-act`),
then the user's own browser (`chrome-direct`, Claude in Chrome, the built-in
browser, Cowork), then a host headless tool. The line it prints goes into the
intake message: when there is no login, it tells the user the two commands
(`browser-act auth login`, then `browser-act auth poll`) and continues on the
local browser meanwhile; when the CLI is missing, it asks for the OK to
install it. Never create the account or paste a key yourself. Open your own
sessions, named `ffr-<source>-<n>`, and close them at the end
(`browseract.py close --all-mine`).

## 1. Intake

Send the questionnaire in `references/intake.md`: one message, all 18 items,
each with the default you will use. Trip shape and legs; origin airports with
the rail-reachable ones; destination airport, city or region; dates per leg;
travellers; cabins; checked and cabin bags; currency; journey-time limit;
maximum stops; time windows; airlines preferred or excluded; the three route
hacks on or off; self-transfer; budget; speed mode (fast or thorough); fixed
event; and the browser line from step 0. "Just go", or an unattended run,
takes every default and records each in `assumptions`.

Done when `run_log.py init --contract FILE` exits 0. It prints the run
directory (pass it as `--run <dir>` to every later command), the date tuples
and comparison cells, and whether a region is awaiting a shortlist. The
contract format is in `references/intake.md`.

## 2. Discovery (regions)

When the destination is a region, follow `references/discovery.md`: FlightList
range searches per candidate gateway (`flightlist.py sweep`), Google Flights
Explore by hand (`gflights.py explore` prints the steps), and FlightConnections
for non-stops from each origin airport, all in parallel sessions. Propose the
`shortlist` cheapest gateways in one message, every price labelled a lead,
and wait for the user's yes or edits (unattended: the proposal stands, as an
assumption). Then `run_log.py shortlist --run <dir> BKK,SIN,…`.

## 3. Collect

1. **Source health (full scope).** Run `source_ledger.py status`; on exit 3
   probe only the listed sources with the canary, then `order --engine <yours>`
   for the order, the pacing and the sources that may be re-probed on your
   rung (`references/source-health.md`). Canary prices are never fare evidence.
2. **Plan.** `run_log.py jobs --run <dir>` prints one job list per parallel
   session: FlightList discover sweeps, the Google confirmation sweep (one
   session, the daily allowance), Kiwi reprices, and the cells to do by hand.
   Run the sessions at the same time; with subagents, give each one a list.
3. **Fast mode.** `flightlist.py sweep` records discover rows for the whole
   window per destination; `run_log.py confirm --run <dir> --top 3` picks the
   cheapest tuples per gateway; `gflights.py sweep --tuples …` confirms them
   with exact-date list rows (`references/google-flights-browser.md`,
   `references/flightlist-browser.md`). Tuples no card covered still need a
   search before `coverage` closes them.
4. **Thorough mode.** Every date tuple on Google (`gflights.py sweep`), plus
   the other recipes: `references/edreams-browser.md`,
   `references/ita-matrix-browser.md`, `references/azair-browser.md`,
   `references/airline-direct.md`. Set every field explicitly and confirm the
   page repeats the legs, dates, travellers, cabin and currency. A loading
   shell, teaser, cached monthly minimum or calendar heatmap is not a result.
5. **Save as you go.** The sweeps record rows themselves; by hand, add each
   populated page (or blocked, empty or broken attempt) with `run_log.py add`
   the moment you have read it. Row fields are in `references/qualification.md`.

Done when `run_log.py coverage` shows every discover, confirm or baseline
comparison closed, or open only because every source for it was blocked.

## 4. Route hacks

Test each hack switched on at intake for each cabin: split one-way tickets,
open-jaw, and a stopover when asked. Nearby airports, alternative destinations
and multi-city are baseline now, not hacks. Price the whole trip: tickets,
bags, ground rows both ways, unavoidable hotel nights and transfers. An
unpriced part keeps the hack a lead; show its break-even instead of a total.
Record each combination as one row holding every ticket and every flown leg
(a stopover or a same-day self-transfer splits a leg into parts). Use
`run_log.py rank` to skip leads that cannot beat the best qualified total.
Details: `references/route-hacks.md`.

Done when every hack comparison is closed in `coverage`.

## 5. Qualify the shortlist

From `rank`, take the cheapest unpruned candidates in each cabin plus the best
time-for-price option. For each one, following `references/qualification.md`:
select every leg; read each leg's duration; keep the cabin label exactly as
shown (`Economy + Premium Economy`); record baggage per ticket; compare the
bag-inclusive fare family with base fare plus bag fee; reprice on the seller's
page (a FlightList card's Kiwi link is one command, `kiwi.py fare`; TAP and
eDreams show the total before passenger details); price every remaining
all-in part, and add a ground row for each nearby airport and date from the
operator's site. A reprice is a new row that `supersedes` the list row.

Done when `rank` shows a qualified best option in every requested cabin, or
you have closed that cabin's `reprice` comparison with
`run_log.py resolve <cell> --as none_qualify --reason …` (allowed once a priced
candidate exists). The other closures: `no_fare` after an executed search
returned no published fare, and `na` when a comparison cannot apply; every
closure appears in `check` and in the report.

## 6. Cross-check and report

Attempt at least two independent source families per cabin. Frontends sharing
one inventory are one family (FlightList and Kiwi; any Google Flights wrapper;
Opodo and eDreams); an airline's booking card inside an aggregator is evidence
for that aggregator, not a second family. Run the independence test in
`references/source-ladder.md` before calling a price corroborated.

Run `run_log.py rank` and `run_log.py check`, then write the report in this
order:

1. **Search:** the contract in one or two lines, every assumption, the
   shortlist for a region, the speed mode, and the retrieval window with
   timezone.
2. **Recommended:** for each requested cabin, the qualified options ranked by
   all-in total, then practicality. Each shows: all-in price and currency
   (ground rows included), airlines, route, every leg with airport-local times
   as `HH:MM:SS` and next-day arrivals marked, duration and stops per leg,
   cabin label, baggage state, risk flags from `rank` (budget, mixed cabin,
   self-transfer, overnight before departure), retrieval time and booking link.
3. **Route hacks:** each tested hack with its all-in total or break-even,
   added days and risk, against the best home-airport option.
4. **Leads (not verified):** each lead with the price seen and every reason
   `run_log` gave; discovery prices for gateways not confirmed go here.
5. **Sources:** families used, shared-inventory relations, blocked sources with
   the engine and the challenge outcome, and single-source confidence where it
   applies.
6. **Last line:** `Complete`, or `Incomplete:` plus each open item from
   `check`.

Cite only pages you retrieved: source, URL (or connector query), timestamp
with timezone, and the claim it supports. Keep currencies as shown; a
conversion carries its rate and date. Only the requested cabins appear, and
destination sightseeing only when asked. For a wedding, race or other fixed
event, plan the window with `references/event-anchored-trip-planning.md`.

If the scripts cannot run on this host, keep the same fields by hand and end
with `Incomplete: completeness not machine-checked`.

## Browsers and bot walls

BrowserAct's free features are the user's own tooling and the fastest path
through blocked sites: stealth browsers, parallel sessions, `solve-captcha`
and `remote-assist` (`references/browser-engines.md`). Every source family runs
in its own session at the same time; on one site, the ledger's
`sessions_per_site` and `pace_seconds`; deep links over refilled forms;
cookies declined once and the session kept. Every Google search spends a
limited daily allowance, so discover with FlightList and confirm the cheapest
tuples on Google.

On a challenge (CAPTCHA, press-and-hold, "unusual traffic", bot page, 403/429
in the network log), the sweeps apply the policy for you: with a login,
`solve-captcha` once, then `remote-assist` when the user is reachable (send
them the link, continue in the same session); a user watching their own
browser may clear it; otherwise record it with `source_ledger.py record <id>
blocked --engine <name>` and an attempt row, and move to the next source.
Never book, pay, buy proxies or browsers, import anyone else's sessions, or use
private APIs, whoever asks.

## Final checklist

- [ ] `browseract.py status` ran; the browser line is in the intake message; sessions are yours and closed at the end.
- [ ] The full questionnaire was sent, or every default is listed as an assumption.
- [ ] A region got a shortlist the user saw; `init` ran; every assumption is in the report.
- [ ] Every observation, including blocked attempts and ground rows, was added as a row when read.
- [ ] `coverage` shows no open comparison the report does not mention.
- [ ] Every recommendation is `qualified` in `rank`; every lead sits under Leads with its reasons.
- [ ] Mixed cabins, self-transfers, airport changes, separate tickets, ground legs and extra nights are visible.
- [ ] Blocked sources are named with their engine and challenge outcome.
- [ ] The last line is `Complete` or `Incomplete:` from `check`.
