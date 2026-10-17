# Intake: the questionnaire and the contract

The contract is the user's answers written down before any search. Every row,
gate and comparison is checked against it, so a missing answer becomes a silent
guess later. Intake is done when `run_log.py init` exits 0.

## Ask everything, once

Send one message listing every option the skill has, in the order below, each
with the default you will use. Items the user already stated are shown as
confirmed, not asked again, but still listed. The user corrects what is wrong
and the run starts. "Just go", or an unattended run, takes every default and
records each one in `assumptions`; the report opens with that list.

The browser line (item 18) comes from `browseract.py status`
(`references/browser-engines.md`), run before the message.

Template for "Zurich area to Southeast Asia in February, two of us":

> Before I search, here is everything I'll assume. Reply with any changes:
> 1. **Trip shape:** round trip (one-way and multi-city with the legs listed are possible)
> 2. **Origin airports:** Zurich (ZRH), plus Basel (BSL) and Geneva (GVA) by train; no overnight before departure. Also Milan, Munich or Stuttgart?
> 3. **Destination:** Southeast Asia (a region): I'll propose the 4 cheapest gateway airports first. Different shortlist size, or name the airports?
> 4. **Dates per leg:** out any day 1–10 Feb 2027, back 12–16 nights later (one date per leg, a range, ±days, or a trip length)
> 5. **Travellers:** 2 adults (children with ages, infants?)
> 6. **Cabins:** economy (premium economy, business, first?)
> 7. **Bags:** 1 checked bag (23 kg) per person, no full-size cabin bag
> 8. **Currency:** CHF
> 9. **Journey-time limit:** none per leg (e.g. 20 hours, strict or inclusive?)
> 10. **Maximum stops:** none (e.g. 1)
> 11. **Departure or arrival time windows:** none (e.g. depart after 06:00)
> 12. **Airlines:** no preference, none excluded
> 13. **Route hacks:** split one-way tickets on, open-jaw on, stopover off
> 14. **Self-transfer:** no self-transfer connections on separate tickets
> 15. **Budget ceiling:** none (options above it are flagged, never hidden)
> 16. **Speed mode:** fast (discover the window, confirm the cheapest dates); thorough searches every date
> 17. **Fixed event or arrival deadline:** none
> 18. **Browser:** BrowserAct stealth browser (logged in). *or:* BrowserAct account: not logged in … (the exact lines are in `references/browser-engines.md`)

## Fields

| Item | Contract key | Default | Why it matters |
|---|---|---|---|
| 1 Trip shape | derived from `legs` (one leg: one-way; two reversing legs: return; else multi-city) | as given | Decides which hacks apply and how rows are read |
| 2 Origin airports | `legs[0].from.airports`; a nearby airport has `"via": "rail"` (or `bus`, `flight`, `car`) and `overnight_ok` | the named airport plus rail-reachable ones, no overnight | A `via` airport needs a priced ground row before a row from it can qualify |
| 3 Destination | `legs[0].to`: airports, or `"region": true` with an empty list until `run_log.py shortlist` | the named airport; a region gets a shortlist of `shortlist` gateways (default 4) | Discovery proposes gateways; every destination airport gets its own comparisons |
| 4 Dates per leg | `legs[n].dates`: `fixed`, `range` (`from`, `to`), `flex` (`date`, `minus`, `plus`) or `after_leg` (`leg`, `min_days`, `max_days`) | as given; a flexible month becomes a `range` | `init` expands them into date tuples; thorough mode caps them at 200 |
| 5 Travellers | `travelers.adults`, `children_ages`, `infants` | 1 adult | Per-person prices are multiplied; infants need totals |
| 6 Cabins | `cabins` | economy | Only requested cabins are searched and reported |
| 7 Bags | `bags.checked_per_person`, `bags.cabin_per_person` | 1 and 0 | Decides whether baggage keeps a fare a lead |
| 8 Currency | `currency` | the home airport's | Other currencies need `fx` on the row |
| 9 Journey-time limit | `max_duration` (`value` `HH:MM:SS`, `strict`) | `null`, said out loud | Applied to each flown leg (and each part of a split leg) |
| 10 Maximum stops | `max_stops` | `null` | A hard gate per leg |
| 11 Time windows | `time_windows`: `{"leg", "dep_after", "dep_before", "arr_after", "arr_before"}` (`HH:MM`) | `[]` | A hard gate on local times |
| 12 Airlines | `airlines.prefer`, `airlines.exclude` (two-letter codes) | both empty | Excluded is a gate; preferred is a tie-break and a flag |
| 13 Route hacks | `hacks.split`, `hacks.open_jaw`, `hacks.stopover` | split and open-jaw on (return trips), stopover off | One comparison per enabled hack and cabin |
| 14 Self-transfer | `self_transfer_ok` | `false` | A missed self-transfer connection is the traveller's loss |
| 15 Budget | `budget` | `null` | `rank` flags options above it |
| 16 Speed mode | `speed`: `fast` or `thorough` | fast above 10 date tuples, else thorough | Fast: one range search per destination plus confirmation of the cheapest tuples; thorough: every tuple |
| 17 Fixed event | `event` | `null` | See `references/event-anchored-trip-planning.md` |
| 18 Browser | not in the contract; recorded as `engine` on every row | the highest rung `browseract.py status` finds | A block on one engine says nothing about another |
| Positioning | `positioning.allowed`, `positioning.overnight_ok` | allowed, no overnight | `allowed: false` drops every `via` airport with a stated assumption |
| Scope | `scope`: `quick` (fixed dates, one cabin, no hacks) or `full` | full | Quick skips the source-health gate |

A leg's `from` or `to` may be a reference to another leg's group (`"to:1"`,
`"from:1"`), so a return leg reverses the first without repeating it. The
first airport in an origin group is the home airport; the others are nearby.

## Create the run

The questionnaire above, after "yes to all":

```bash
cat > /tmp/contract.json <<'JSON'
{"run_id": "zrh-sea-feb", "scope": "full", "speed": "fast",
 "legs": [
   {"from": {"name": "Zurich area",
             "airports": [{"code": "ZRH"},
                          {"code": "BSL", "via": "rail", "overnight_ok": false},
                          {"code": "GVA", "via": "rail", "overnight_ok": false}]},
    "to":   {"name": "Southeast Asia", "region": true, "airports": []},
    "dates": {"range": {"from": "2027-02-01", "to": "2027-02-10"}}},
   {"from": "to:1", "to": "from:1",
    "dates": {"after_leg": {"leg": 1, "min_days": 12, "max_days": 16}}}],
 "travelers": {"adults": 2, "children_ages": [], "infants": 0},
 "cabins": ["economy"],
 "bags": {"checked_per_person": 1, "cabin_per_person": 0},
 "currency": "CHF",
 "max_duration": null, "max_stops": null, "time_windows": [],
 "airlines": {"prefer": [], "exclude": []},
 "hacks": {"split": true, "open_jaw": true, "stopover": false},
 "self_transfer_ok": false,
 "positioning": {"allowed": true, "overnight_ok": false},
 "budget": null, "event": null, "shortlist": 4,
 "assumptions": ["1 checked bag per person", "no journey-time limit", "no self-transfers"]}
JSON
python3 <skill_dir>/scripts/run_log.py init --contract /tmp/contract.json
```

`init` prints the run directory, the number of date tuples and comparison
cells, and whether a region group is waiting for a shortlist. Pass the
directory as `--run <dir>` to every later command (`shortlist`, `confirm`,
`add`, `rank`, `coverage`, `resolve`, `check`, `jobs`); without it the most
recently used run is taken, which is wrong when several searches run at once.

- A region destination: run discovery (`references/discovery.md`), then
  `run_log.py shortlist --run <dir> BKK,SIN,KUL,SGN`.
- Fast mode: after the discover sweeps, `run_log.py confirm --run <dir> --top 3`
  picks the cheapest tuples per destination to confirm on an exact-date source.
- If the user changes an answer after the run has started, create a new run
  with a new `run_id`.

A return date is the day the flight leaves the destination unless the user
gives an arrive-home deadline.
