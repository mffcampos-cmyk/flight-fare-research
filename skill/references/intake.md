# Intake: pin the search contract

The contract is the user's answers written down before any search. Every row,
gate and comparison is checked against it, so a missing answer becomes a silent
guess later. Intake is done when `run_log.py init` exits 0.

## Ask once, with defaults

Send one message that lists only what the user has not already said, each item
with the default you will use. The user corrects what is wrong and the run
starts. Example for "cheap flights to Lisbon next month, I live in Zurich":

> Before I search, here is what I'll assume. Reply with any changes:
> - **Route:** Zurich (ZRH) ⇄ Lisbon (LIS), round trip
> - **Dates:** 7 nights, any outbound from 1 to 23 Nov (23 exact date pairs). Different trip length?
> - **Travellers:** 1 adult
> - **Cabin:** economy
> - **Bags:** 1 checked bag (23 kg) each way, plus a cabin bag
> - **Currency:** CHF
> - **Journey time:** no limit per direction. Want one (e.g. under 10 hours)?
> - **Other airports:** Zurich only. Shall I also try Basel (BSL) or Geneva (GVA) by train if it saves money?
> - **Separate tickets:** each direction may be its own ticket, but no self-transfer connections (where you collect bags and re-check in between flights on separate tickets).

When the user says "just go", or the run is unattended, start with the
defaults and record each one in `assumptions`; the report opens with that list.

## Fields

| Ask about | Contract key | Default | Why it matters |
|---|---|---|---|
| Route | `origins`, `destinations` | the airports named; a city or country becomes its practical airports, listed as an assumption | Every row must match; other airports are hacks, not baseline |
| Dates | `dates` (`pairs`, `rolling`, `cartesian`, or `outbound` for one-way) | fixed dates as given; a flexible month becomes `rolling` with a stated trip length | Exact-date coverage is counted per pair |
| Varying trip lengths | `dates.cartesian.confirmed` | not allowed until the user says yes | Separate outbound and return ranges imply trips of different lengths |
| Travellers | `travelers.adults`, `children_ages`, `infants` | 1 adult | Per-person prices are multiplied; infants need total prices |
| Cabin(s) | `cabins` | economy, stated as an assumption | Only requested cabins are searched and reported |
| Checked bags | `bags.checked_per_person` | 1 | Decides whether baggage keeps a fare a lead |
| Currency | `currency` | the home airport's currency | Other currencies need an exchange rate in `fx` |
| Journey-time limit | `max_duration` (`value` `HH:MM:SS`, `strict`) | `null` (no limit), said out loud | Applied to each direction separately |
| Other departure airports | `nearby_origins`, `positioning.allowed`, `rail_ok`, `overnight_ok` | home airports only; when allowed: rail yes, overnight no | Positioning cost and timing decide whether the hack is real |
| Other arrival airports | `alt_destinations` | none | Opens the alternative-destination and open-jaw hacks |
| Self-transfer | `self_transfer_ok` | `false` | A missed self-transfer connection is the traveller's loss |
| Stopover | `hacks` includes `stopover` | only when asked | Adds a stopover comparison |
| Fixed event or arrival deadline | `event` | none | See `event-anchored-trip-planning.md` |

A return date is the day the flight leaves the destination unless the user
gives an arrive-home deadline.

## Scope

- **Quick:** fixed dates, one cabin, short or medium haul, no hack or stopover
  request. Comparisons: each date pair, one nearby-airport check (when
  allowed), a second source family, and an airline or provider reprice.
- **Full:** anything else (flexible dates, long haul, several cabins, route
  hacks, stopover, fixed event). Comparisons: every date pair × origin × cabin,
  plus every permitted hack per cabin.

`init` turns scope and permissions into the list of comparisons, and marks
forbidden ones not applicable with the reason.

## Create the run

The example below is the Lisbon request after the user replied "yes, Basel and Geneva by train are fine"; without that reply, `nearby_origins` stays empty and `positioning.allowed` false.

```bash
cat > /tmp/contract.json <<'JSON'
{"run_id": "zrh-lis-nov", "scope": "full", "trip_type": "return",
 "travelers": {"adults": 1}, "currency": "CHF",
 "origins": ["ZRH"], "destinations": ["LIS"],
 "nearby_origins": ["BSL", "GVA"],
 "positioning": {"allowed": true, "rail_ok": true, "overnight_ok": false},
 "dates": {"rolling": {"first_outbound": "2026-11-01", "last_outbound": "2026-11-23", "trip_days": 7}},
 "cabins": ["economy"], "bags": {"checked_per_person": 1},
 "max_duration": null, "self_transfer_ok": false,
 "assumptions": ["7 nights", "1 checked bag per person", "no journey-time limit"]}
JSON
python3 <skill_dir>/scripts/run_log.py init --contract /tmp/contract.json
```

`init` prints the run directory and the number of comparisons. Run
`run_log.py coverage` to see them. If the user changes an answer after the run
has started, create a new run with a new `run_id`.
