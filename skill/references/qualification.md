# Qualify a candidate

A candidate becomes **qualified** only when `run_log.py` computes it so. Until
then it is a **lead**, whatever its price. This file says what to capture on
the page and which row field it goes into; `run_log.py add` prints the status
and any lead reasons after each row.

## Steps for each shortlisted candidate

1. **Select every leg.** Choose each flown leg of the contract (both
   directions of a round trip, every leg of a multi-city) and reach the
   booking or fare-family page. Record one entry per leg in `legs`
   (`"leg": 1`, `"leg": 2`, …). A stopover or a same-day self-transfer that
   splits one contract leg into two flown journeys uses `"part": 1` and
   `"part": 2` with the same `leg`. A cheap leg 1 with no compatible leg 2 is
   not an option. Missing leg → lead (`leg 2 not selected`).
2. **Check journey time per leg.** Record each leg's `duration` as
   `HH:MM:SS` from the page, plus local `dep`/`arr` timestamps (airport-local,
   with the date, so next-day arrivals show). `run_log` rejects any leg or
   part at or over a strict cap (exactly `20:00:00` fails "under 20 hours")
   or over an inclusive cap. A stopover's stay does not count; each flown
   part does. `max_stops`, time windows and excluded airlines are gates on
   the same entries.
3. **Keep the cabin label verbatim.** `cabin` is the cabin you searched;
   `cabin_label` is what the itinerary says (`Economy + Premium Economy`).
   Mixed labels are flagged in `rank`; prefer a slightly dearer pure-cabin
   option over a misleading mixed one, and say which segment carries which
   cabin when the page shows it.
4. **Record baggage per ticket.** Each ticket's `baggage` is exactly one of:
   - `included`: the completed itinerary or fare family states at least one
     checked piece;
   - `fee_required`: the page states the first checked bag costs extra; put the
     total for all requested bags on that ticket in `bag_fee`;
   - `unverified`: no itinerary-level allowance is shown, or a range starts at
     zero (`1st checked bag: CHF 0–104`), which proves neither inclusion nor a
     fee.

   When the contract asks for full-size cabin bags (`cabin_per_person` > 0),
   record `cabin_bag` per ticket the same way (`included`, `fee_required` with
   `cabin_bag_fee`, `unverified`).

   Airline norms, cabin expectations, a friend's advice and generic policy
   pages explain which fare family to pick; only the completed page or fare
   family sets the state. Separate tickets each need their own bag line; one
   ticket's allowance never covers another.
5. **Compare fare families.** When the page shows branded families, record the
   cheapest bag-inclusive family and, if cheaper, base fare plus explicit bag
   fee, as separate rows. If `View options` is missing or inert after one
   attempt, reprice on the airline's own site (`references/airline-direct.md`).
6. **Reprice with the seller.** Reach the airline or booking provider's
   completed price page (stop before passenger details) and set
   `quote_state` to `completed`. If the price changed from a list amount, add
   the new row with `quote_state: "repriced"` and `"supersedes": "<old id>"`;
   the old row stays as a labelled stale observation. Any ticket still `list`
   → lead (`list fare not repriced`). A FlightList card's `Book Flight` link
   is repriced in one command: `kiwi.py fare --session ffr-kiwi-1 --run <dir>
   --supersedes r4 <kiwi fare-selection URL>` (`references/flightlist-browser.md`).
7. **Price every part.** A row departing from or arriving at a nearby airport
   (`"via": "rail"` in the contract) needs a **ground row** for that airport
   and date (below); without one → lead (`ground unpriced (BSL)`).
   `components` holds the other all-in extras: `hotel` (an unavoidable night),
   `transfers`. A needed part you have not priced is `null` → lead
   (`hotel unpriced`). An estimate from the user, a guess or a typical fare is
   still unpriced: put the estimate in `notes` and let the break-even in
   `references/route-hacks.md` carry it.
8. **Currency and price basis.** Keep amounts in the currency shown. If it
   differs from the contract, add `fx` with rate, date and source; without it
   → lead. `price_basis` is `total` unless the page shows per-person prices;
   with infants travelling, always record totals.

The candidate is done when `run_log.py add` prints `qualified`, or when its
remaining lead reasons cannot be resolved (say which, and keep it in the Leads
section of the report).

## Row example

A completed round trip, one ticket, both legs, recorded from the seller's page:

```json
{"source": "tap-direct", "family": "tap", "engine": "browser-act-stealth", "outcome": "populated",
 "url": "https://booking.flytap.com/…", "retrieved_at": "2027-01-08T14:09:00+01:00",
 "cabin": "economy", "cabin_label": "Economy", "hack": null, "phase": "exact",
 "origin": "ZRH", "destination": "LIS", "dates": ["2027-02-05", "2027-02-12"],
 "currency": "CHF", "price_basis": "total",
 "tickets": [{"price": 407.70, "quote_state": "completed", "provider": "TAP",
              "baggage": "included", "bag_fee": null, "booking_url": "https://booking.flytap.com/…"}],
 "legs": [
   {"leg": 1, "part": 1, "from": "ZRH", "to": "LIS", "dep": "2027-02-05T07:10:00", "arr": "2027-02-05T09:05:00",
    "duration": "02:55:00", "stops": 0, "airlines": ["TP"], "airport_change": false, "self_transfer": false},
   {"leg": 2, "part": 1, "from": "LIS", "to": "ZRH", "dep": "2027-02-12T18:00:00", "arr": "2027-02-12T22:00:00",
    "duration": "03:00:00", "stops": 0, "airlines": ["TP"], "airport_change": false, "self_transfer": false}],
 "components": {}, "notes": "Classic family both ways"}
```

One row is one bookable combination for one date tuple: a round trip on one
ticket, a multi-city on one or several tickets, or a split, open-jaw or
stopover with every ticket it needs (each ticket with its own price, quote
state and bag line) and every flown leg. `dates` is the run's date tuple (one
date per contract leg); `origin` and `destination` are leg 1's airports.
`phase` is `exact` for an exact-date search and `discover` for a range
search; `add` refuses rows whose cabin, dates or airports differ from the
run's contract.

## Ground rows

The rail, bus or flight between a home airport and a nearby airport, priced
on the operator's site (SBB, Trainline, Omio, the airline) for the date the
row flies; one row per direction:

```json
{"kind": "ground", "source": "sbb", "engine": "browser-act-stealth", "url": "https://www.sbb.ch/…",
 "retrieved_at": "2027-01-08T14:20:00+01:00", "from": "ZRH", "to": "BSL", "date": "2027-02-03",
 "price": 32.40, "currency": "CHF", "quote_state": "completed", "notes": "IC 2 06:04 -> 07:03, 2nd class"}
```

`rank` adds, to every fare row that uses that airport on that date, the
cheapest completed ground row for the pair (either direction); the day before
counts only where the contract allows an overnight (`overnight_ok`), and is
flagged `overnight before departure`. One priced train serves every fare row
from that airport. A positioning **flight** is a ticket on the fare row, not a
ground row.

Save rows with `run_log.py add --run <dir> --row FILE` (or `--row -` from
stdin) the moment you have read the page; rows are append-only, so a crash
loses nothing. `add` takes a JSON array or JSON Lines mixing fare rows, ground
rows and attempts, so a page of cards is one call; if any row is invalid, none
is saved. Attempts that showed no fare go in too, with `"outcome": "blocked"`,
`"empty"` or `"error"`; an `empty` attempt names the search it ran (`origin`,
`destination`, `dates`) so `resolve … --as no_fare` can close that cell.

## Lead reasons and their fix

| Lead reason | Fix |
|---|---|
| `leg N not selected` | Select the missing leg on the same itinerary |
| `duration unknown (leg N)` | Read the elapsed time from the itinerary details |
| `list fare not repriced` | Reach the seller's completed price page (`kiwi.py fare`, TAP deep link, eDreams checkout) |
| `baggage unverified` | Price a bag-inclusive family, or add the bag at the seller |
| `bag fee unknown` | Read the explicit fee on the seller's page; if it appears only after passenger details, use a bag-inclusive family from a seller that shows it (below) |
| `ground unpriced (XXX)` | Add a ground row for that airport and date from the operator's site |
| `hotel unpriced` / `transfers unpriced` | Price it on its own site |
| `currency differs; no fx recorded` | Add `fx` with rate, date and source |
| `per-person price with infants; record the total` | Record the booking total |
| `cabin bag unverified` / `cabin bag fee unknown` | Read the cabin-bag allowance or fee on the seller's page |

## Sellers that show bags and the total before passenger details

Observed 2026-10-08 on a BrowserAct `chrome` browser; recipes in the files named.

| Seller | What it shows | Record |
|---|---|---|
| Kiwi.com fare page, from FlightList `Book Flight` (`kiwi.py fare`) | The airline's families (e.g. KLM Light / Standard / Flex) with bags and totals including Kiwi's fees | `completed`; the bag family as `included` |
| TAP deep link (`references/airline-direct.md`) | Per-direction family panels with hold bags; round-trip total beside `Continue` | `completed`; `included` when both families list a hold bag |
| eDreams checkout summary (`references/edreams-browser.md`) | Fare text (e.g. `Economy Light … Kein Aufgabegepäck`) and `Normalpreis` | `completed`; without a bag `fee_required`, `bag_fee: null` |
| Google Flights booking page (`references/google-flights-browser.md`) | The bag line (`No checked bags`, `1st checked bag … fee`); providers can be hidden by location | evidence for the bag state only; the price stays `list` |
| airfrance.ch, klm.ch, swiss.com | Blocked on BrowserAct `chrome`; untested on a stealth browser | try the stealth browser or the user's own browser, or Kiwi for AF/KLM families |

## Closing a comparison without a qualified row

`run_log.py resolve <cell> --as <kind> --reason "…"` closes one comparison:

- `no_fare`: a baseline, discover, confirm or hack search ran and returned no
  published fare (an `empty` or populated row must exist; a blocked page is
  not a search).
- `none_qualify`: a cabin's `reprice` comparison when priced candidates exist
  but none can qualify (all over the cap, or every seller blocked).
- `na`: the comparison cannot apply to this trip; say why.

Every closure is listed by `check` and must appear in the report.
