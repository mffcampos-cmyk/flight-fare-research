# Qualify a candidate

A candidate becomes **qualified** only when `run_log.py` computes it so. Until
then it is a **lead**, whatever its price. This file says what to capture on
the page and which row field it goes into; `run_log.py add` prints the status
and any lead reasons after each row.

## Steps for each shortlisted candidate

1. **Select both directions.** Choose the outbound, then a return that also
   fits the contract, and reach the booking or fare-family page. Record both
   in `directions` (`"dir": "out"` and `"dir": "ret"`). A cheap outbound with
   no compatible return is not an option. Missing direction → lead
   (`outbound not selected` / `return not selected`).
2. **Check journey time per direction.** Record each `duration` as `HH:MM:SS`
   from the page, plus local `dep`/`arr` timestamps (airport-local, with the
   date, so next-day arrivals show). `run_log` rejects any direction at or over
   a strict cap (exactly `20:00:00` fails "under 20 hours") or over an
   inclusive cap. A stopover's continuous stay does not count against the cap;
   each flown journey does.
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
   attempt, reprice on the airline's own site (`airline-direct.md`).
6. **Reprice with the seller.** Reach the airline or booking provider's
   completed price page (stop before passenger details) and set
   `quote_state` to `completed`. If the price changed from a list amount, add
   the new row with `quote_state: "repriced"` and `"supersedes": "<old id>"`;
   the old row stays as a labelled stale observation. Any ticket still `list`
   → lead (`list fare not repriced`).
7. **Price every part.** `components` holds the all-in extras: `positioning`
   (train or flight to the departure airport and back), `hotel`, `transfers`.
   A needed part you have not priced is `null` → lead (`<part> unpriced`). An
   estimate from the user, a guess or a typical fare is still `null`: put the
   estimate in `notes` and let the break-even in `route-hacks.md` carry it.
8. **Currency and price basis.** Keep amounts in the currency shown. If it
   differs from the contract, add `fx` with rate, date and source; without it
   → lead. `price_basis` is `total` unless the page shows per-person prices;
   with infants travelling, always record totals.

The candidate is done when `run_log.py add` prints `qualified`, or when its
remaining lead reasons cannot be resolved (say which, and keep it in the Leads
section of the report).

## Row example

```json
{"source": "tap-direct", "family": "tap", "engine": "claude-in-chrome", "outcome": "populated",
 "url": "https://booking.flytap.com/…", "retrieved_at": "2026-10-08T14:09:00+02:00",
 "cabin": "economy", "cabin_label": "Economy", "hack": null,
 "origin": "ZRH", "destination": "LIS", "outbound_date": "2026-11-05", "return_date": "2026-11-12",
 "currency": "CHF", "price_basis": "total",
 "tickets": [{"price": 407.70, "quote_state": "completed", "provider": "TAP",
              "baggage": "included", "bag_fee": null, "booking_url": "https://booking.flytap.com/…"}],
 "directions": [
   {"dir": "out", "from": "ZRH", "to": "LIS", "dep": "2026-11-05T07:10:00", "arr": "2026-11-05T09:05:00",
    "duration": "02:55:00", "stops": 0, "airlines": ["TP"], "airport_change": false, "self_transfer": false},
   {"dir": "ret", "from": "LIS", "to": "ZRH", "dep": "2026-11-12T18:00:00", "arr": "2026-11-12T22:00:00",
    "duration": "03:00:00", "stops": 0, "airlines": ["TP"], "airport_change": false, "self_transfer": false}],
 "components": {}, "notes": "Classic family both ways"}
```

One row is one bookable combination: a round trip on one ticket, or a split,
open-jaw or stopover with every ticket it needs (each ticket with its own price,
quote state and bag line) and all its legs (`out` and `ret`; a stopover has
several legs in one direction). `add` refuses rows whose cabin, dates or
airports differ from the run's contract.

Save it with `run_log.py add --run <dir> --row FILE` (or `--row -` from stdin) the moment
you have read the page; rows are append-only, so a crash loses nothing.
Attempts that showed no fare go in too, with `"outcome": "blocked"`, `"empty"`
or `"error"`.

## Lead reasons and their fix

| Lead reason | Fix |
|---|---|
| `outbound not selected` / `return not selected` | Select the missing direction on the same itinerary |
| `duration unknown (out)` | Read the elapsed time from the itinerary details |
| `list fare not repriced` | Reach the seller's completed price page |
| `baggage unverified` | Price a bag-inclusive family, or add the bag at the seller |
| `bag fee unknown` | Read the explicit fee on the seller's page |
| `positioning unpriced` (any part) | Price the train/flight/hotel on its own site |
| `currency differs; no fx recorded` | Add `fx` with rate, date and source |
| `per-person price with infants; record the total` | Record the booking total |
| `cabin bag unverified` / `cabin bag fee unknown` | Read the cabin-bag allowance or fee on the seller's page |

## Closing a comparison without a qualified row

`run_log.py resolve <cell> --as <kind> --reason "…"` closes one comparison:

- `no_fare`: a baseline or hack search ran and returned no published fare (an
  `empty` or populated row must exist; a blocked page is not a search).
- `none_qualify`: a cabin's `reprice` comparison when priced candidates exist
  but none can qualify (all over the cap, or every seller blocked).
- `na`: the comparison cannot apply to this trip; say why.

Every closure is listed by `check` and must appear in the report.
