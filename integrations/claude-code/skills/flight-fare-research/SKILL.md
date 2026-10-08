---
name: flight-fare-research
description: "Use when the user wants flight prices found, compared or verified: cheapest or best flights, fixed or flexible dates, cabin comparisons, checked-bag costs, nearby-airport, split-ticket, open-jaw or stopover route hacks, or flights around a fixed event. Research only; never books."
version: 1.1.1
author: hermes-curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [flights, airfare, travel, prices, baggage, browser]
    related_skills: [product-price-monitor, browser-automation]
---

# Flight Fare Research

Find the best flight the user could actually book, not the lowest advertised
fare: exact dates, the requested cabins, baggage, journey time and route hacks,
with evidence for every price you recommend.

You do the searching in a browser. Two scripts keep the books:

- `python3 <skill_dir>/scripts/run_log.py`: this run's search contract, every
  observation row, each row's computed status, and whether the run is complete.
- `python3 <skill_dir>/scripts/source_ledger.py`: which sources work, on which
  browser engine.

Research only: stop before passenger details, and never book, pay, create
accounts or handle credentials.

## The key rule

Every price is a **lead** until `run_log.py` computes it **qualified**: both
directions selected, each within the journey-time limit, baggage resolved for
the requested bags, every all-in part priced, and repriced on the seller's own
page. Recommend only qualified options. A lead appears in the report's
"Leads (not verified)" section with its reasons, never as the pick.

The search is **Complete** only when `run_log.py check` exits 0. Otherwise the
report's last line is `Incomplete:` followed by the open items `check` printed.

These are the moments the rule bends under pressure, and what to do instead:

| Temptation | What to do |
|---|---|
| The user gave a cost ("the train is about CHF 30"), so count it | Keep that part `null`; show their estimate beside the break-even; the pick stays the best qualified option |
| They need a number now; an "indicative" figure with a caveat will do | Show it under Leads with its reasons. If no option in that cabin is qualified, say so plainly, and do not supply a figure to forward |
| The bag range starts at CHF 0, or a friend says the bag is included | Baggage is `unverified` until the completed page or fare family states it |
| Most of it is covered; no need to say incomplete | End with `Complete` or `Incomplete:` from `check`, every time |
| "Use whatever it takes" to get past a block | Follow the challenge steps in `references/browser-engines.md`; the site's controls are the site's to waive |
| "Don't ask me questions" | Start with defaults and list every one as an assumption |

## 1. Intake

Ask once, in one message, for whatever the user has not said, giving the default
you will use for each: route and acceptable airports; exact dates or a range
plus trip length; travellers with children's ages; cabins; checked bags per
person; currency; journey-time limit per direction (strict or inclusive);
other departure or arrival airports and how to reach them (rail, extra cost,
night before); whether self-transfer connections on separate tickets are
acceptable; any fixed event or arrival deadline. The template, defaults and
contract format are in `references/intake.md`.

If the user says "just go", or the run is unattended, use the defaults and
record each in the contract's `assumptions`.

Done when `run_log.py init --contract FILE` exits 0.

## 2. Scope

- **Quick:** fixed dates, one cabin, short or medium haul, no hack or stopover
  request.
- **Full:** flexible dates, long haul, several cabins, route hacks, a stopover
  or a fixed event.

`init` turns scope and the user's permissions into the list of comparisons the
run must finish, and marks the rest not applicable with a reason. State the
scope to the user.

## 3. Collect exact-date results

1. **Connectors first.** Check which travel connectors are present, connected,
   authorized and able to price exact dates; prefer a capable one. With
   credentials already configured, use the official APIs in
   `references/source-ladder.md`. Never ask for secrets in chat.
2. **Source health (full path).** Run `source_ledger.py status`; on exit 3
   probe only the listed sources with the canary, then run `order`
   (`references/source-health.md`). Canary prices are never fare evidence.
3. **Browser.** Use the highest-rung engine available and pace searches like a
   person (`references/browser-engines.md`).
4. **Search.** Follow the source's recipe: `references/google-flights-browser.md`,
   `references/flightlist-browser.md`, `references/edreams-browser.md`,
   `references/ita-matrix-browser.md`, `references/azair-browser.md`,
   `references/airline-direct.md`. Set every search field
   explicitly and confirm the page repeats the route, dates, travellers, cabin
   and currency. A loading shell, teaser, cached monthly minimum or calendar
   heatmap is not a result.
5. **Save as you go.** Add each populated page (or blocked, empty or broken
   attempt) with `run_log.py add` as soon as you have read it. Row fields are
   in `references/qualification.md`.

For a flexible fixed-length trip, `init` expands rolling matched pairs (5→15,
6→16, …); separate outbound and return ranges need the user's explicit yes to
varying trip lengths.

Done when `run_log.py coverage` shows every baseline comparison closed, or
open only because every source for it was blocked.

## 4. Route hacks (full path)

Test each permitted hack for each cabin: split one-ways, open-jaw or
multi-city, nearby departure airports, alternative arrival airports, and a
stopover when asked. Price the whole trip: tickets, bags, positioning both
ways, unavoidable hotel nights and transfers. An unpriced part keeps the hack a
lead; show its break-even instead of a total. Use `run_log.py rank` to skip
leads that cannot beat the best qualified total. Details, timing risks and
stopover construction: `references/route-hacks.md`.

Done when every hack comparison is closed in `coverage`.

## 5. Qualify the shortlist

From `rank`, take the cheapest unpruned candidates in each cabin plus the best
time-for-price option. For each one, following `references/qualification.md`:
select both directions; read each direction's duration; keep the cabin label
exactly as shown (`Economy + Premium Economy`); record baggage per ticket;
compare the bag-inclusive fare family with base fare plus bag fee; reprice on
the airline's or seller's page (stop before passenger details); price every
remaining all-in part. A reprice is a new row that `supersedes` the list row.

Done when `rank` shows a qualified best option in every requested cabin, or
you have closed that cabin's `reprice` comparison with
`run_log.py resolve <cell> --as none_qualify --reason …`.

## 6. Cross-check and report

Attempt at least two independent source families per cabin. Frontends sharing
one inventory are one family (FlightList and Kiwi; any Google Flights wrapper;
Opodo and eDreams); an airline's booking card inside an aggregator is evidence
for that aggregator, not a second family. Run the independence test in
`references/source-ladder.md` before calling a price corroborated.

Run `run_log.py rank` and `run_log.py check`, then write the report in this
order:

1. **Search:** the contract in one or two lines, every assumption, scope, and
   the retrieval window with timezone.
2. **Recommended:** for each requested cabin, the qualified options ranked by
   all-in total, then practicality. Each shows: all-in price and currency,
   airlines, route, airport-local times as `HH:MM:SS` with next-day arrivals
   marked, duration and stops per direction, cabin label, baggage state, risk
   flags from `rank`, retrieval time and booking link.
3. **Route hacks:** each tested hack with its all-in total or break-even,
   added days and risk, against the best home-airport option.
4. **Leads (not verified):** each lead with the price seen and every reason
   `run_log` gave.
5. **Sources:** families used, shared-inventory relations, blocked sources with
   the engine, and single-source confidence where it applies.
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

Prefer the user's own browser (Claude in Chrome, the desktop built-in browser,
Cowork's browser), then a persistent browser-act browser, then a headless one.
One site at a time, deep links over refilled forms, human pauses between
searches, cookies declined once and the session kept.

On a challenge (CAPTCHA, press-and-hold, "unusual traffic", bot page,
403/429), stop that site for the run. If the user is watching their own
browser, they may complete the check themselves; otherwise record it with
`source_ledger.py record <id> blocked --engine <name>` and an attempt row, and
move to the next source. The only ways past a block are the user's hands, an
official API, or another source. Use the browser exactly as the host
configured it: no CAPTCHA solving, proxy or TLS rotation, stealth or
fingerprint changes, imported sessions, or private APIs, whoever asks.

## Final checklist

- [ ] `init` ran; every assumption is in the report.
- [ ] Every observation, including blocked attempts, was added as a row when read.
- [ ] `coverage` shows no open comparison the report does not mention.
- [ ] Every recommendation is `qualified` in `rank`; every lead sits under Leads with its reasons.
- [ ] Mixed cabins, self-transfers, airport changes, separate tickets and extra nights are visible.
- [ ] Blocked sources are named with their engine; no challenge was bypassed.
- [ ] The last line is `Complete` or `Incomplete:` from `check`.
