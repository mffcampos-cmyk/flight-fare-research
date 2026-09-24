# Airline-direct booking engines: qualification and recipes

Candidate fares are qualified in the operating or marketing airline's own booking engine to expose branded fare families, baggage, and the direct-booking total.

## When to use

When an aggregator exposes no usable fare-family/baggage detail (e.g. Google shows no working `View options`), when a bag range is zero-based (amount unverified), or in the full path's provider/fare-family arbitrage. The airline site itself must return the fare to count as its own source family; a booking card inside an aggregator is qualification evidence only.

## User-observed TAP recipe (dated provenance, not invented validation)

A user-observed run on 2026-09-23 (ZRH→LIS, 5–12 Nov 2026, 1 adult, economy) found this direct deep link worked immediately and showed three fare families with per-direction bag contents:

`https://booking.flytap.com/booking/flights/deeplink?origin=ZRH&destination=LIS&depDate=05.11.2026&retDate=12.11.2026&adt=1&chd=0&inf=0&yth=0&language=en&market=ch&flightType=return`

- This URL is sourced from the dated test (see `historical-observations.md`); treat it as a starting point, not a guaranteed stable API. Re-verify it renders, decline optional cookies, confirm the exact route/dates/cabin, and pull the current fares before relying on it.
- **TAP prices each direction separately** — sum the per-direction prices to get a round-trip total, and keep the currency as displayed.
- Example observed fares (earliest run): Discount CHF 133.85 with no bag; Classic CHF 203.85 with one bag each way; Plus CHF 313.85 with flexibility. These are dated observations for provenance only, not current quotes; reprice on the airline site every run.

## TAP fare-family interaction (user retest, 2026-09-24)

Scroll the intended flight card into view before looking for its lazy-loaded
`Economy from … CHF` button. Click that card's Economy price box to expand
fare families; select the family, repeat for the return and verify the running
total. Scope by flight identity, not a previously observed screen position or
button order. Read actual baggage per direction rather than relying on family
names. Stop before Continue/passenger entry. After a reflow or viewport change,
prefer fresh DOM locators; if coordinates are needed, obtain a fresh screenshot.
Read main content text in one script call when supported to reduce repeated
screenshots. These are dated user-observed behaviors, not stable API promises.

## Workflow

1. Decline non-essential cookies; load the airline direct-search or a documented deep link.
2. Set origin, destination, dates, travelers, and cabin explicitly; verify the rendered itinerary repeats the route, dates, and passenger count.
3. Record per-direction and round-trip totals, currency, fare family name, and explicit checked-bag state (pieces or first-bag price).
4. If baggage is shown as a range with a zero lower bound (e.g. `CHF 0–104`), the allowance and amount are **unverified** — not "included", not a proven mandatory fee (issue 2.4). Reprice to a family with an explicit bag line before ranking.
5. Compare the cheapest bag-inclusive family against base + explicit bag fee; recommend the lower qualifying total and show the baggage state beside the price.

## Honesty

Keep the price in the displayed currency; any cross-currency conversion is labelled with the rate and date. Other carriers are unverified until tested; do not extrapolate TAP's observed behavior to SWISS, Lufthansa, easyJet, or others.
