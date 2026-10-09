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

## TAP long haul on BrowserAct (2026-10-08, ZRH–GIG)

The same deep link worked for ZRH–GIG on a BrowserAct `chrome` browser. What
the page does:

- Each direction lists flights with buttons whose accessible names are
  `Economy from 1029.3 CHF`, `Economy Prime from …`, `Executive from …`.
  Clicking one expands the fare families, each with a `Select` button and its
  contents (`Hand baggage + Personal item | 1 x | Hold baggage`, seat, changes).
  Read the families from the panel, not from the button: on one return the
  button said `from 877.65` while the cheapest selectable family was 932.65.
- After the outbound and the return are selected, the header reads `Round trip
  … <total> CHF … Continue`: the round-trip total before any passenger detail.
  That total, with the hold bag stated in both chosen families, is a
  `completed` quote with `baggage: "included"`.
- `Economy Prime` families are labelled `Mixed Cabin` in the panel; keep that
  wording in `cabin_label` (`run_log` flags it).
- TAP keeps a previous search's stopover in browser storage: a later deep link
  opened with `Stopover 3 day(s)` already applied. Before a new search on
  booking.flytap.com, clear it in page: `sessionStorage.clear();
  localStorage.clear()`, then reload the deep link.

**Portugal Stopover.** On an outbound fare panel, `Add Stopover` opens a dialog:
both travel dates (date pickers; step months with `Go to next month`), the city
(`Lisbon`, `Porto`, `Terceira`), the direction (`Zurich - Rio de Janeiro` or the
return) and 1–10 nights; `Confirm Stopover` opens `/booking/flights-stopover`,
which lists whole-trip itineraries with one total each. For ZRH 18 Dec → 3
nights Lisbon → GIG 21 Dec, back 11 Jan, the cheapest was CHF 2,744.75, while
TAP's through fares with a bag on nearby dates were CHF 1,962–2,012: "no
additional cost" did not mean the same fare. Price the stopover, then compare.

**Positioning flights** (for example ZRH–LIS before a separate long-haul
ticket) use the same deep link and panels. ZRH–LIS 18:00 on 22 Dec: lowest
family CHF 232.85 without a hold bag, next family CHF 267.85 with one.

## Air France and KLM (2026-10-08)

A deep link prefills the search form:
`https://wwws.airfrance.ch/en/search?pax=1:0:0:0:0:0:0:0&cabinClass=ECONOMY&activeConnection=0&connections=ZRH:A:20261222%3EGIG:A-GIG:A:20270112%3EZRH:A&bookingFlow=LEISURE`
(klm.ch takes the same parameters). On a BrowserAct `chrome` browser the search
never completed: the button kept spinning while the site's own search requests
(`gql/v1 … SharedSearchContext…`) returned HTTP 403. There is no visible
challenge, so check the network log instead of waiting (BrowserAct:
`network requests --status 403`) and record `blocked` with the engine. The
user's own browser may still work (one probe allowed on a higher rung).
Qualify AF/KLM fares through the Kiwi fare page instead
(`flightlist-browser.md`): it shows their Light / Standard / Flex families.

## Other carriers tried (2026-10-08)

- **SWISS** (swiss.com): a bot interstitial (`Just a moment… verifying you are
  not a bot`) stayed on screen: `blocked` on BrowserAct `chrome`.
- **GOL** (voegol.com.br): the site loads, but Lisbon as origin answers `There
  are no flights for the selected segment` although GOL's LIS–GIG nonstop
  (operated by Wamos) is sold through Google-listed OTAs and eDreams. From
  Europe, price it through an OTA; its cheapest fare has no checked bag.

## Workflow

1. Decline non-essential cookies; load the airline direct-search or a documented deep link.
2. Set origin, destination, dates, travelers, and cabin explicitly; verify the rendered itinerary repeats the route, dates, and passenger count.
3. Record per-direction and round-trip totals, currency, fare family name, and explicit checked-bag state (pieces or first-bag price).
4. If baggage is shown as a range with a zero lower bound (e.g. `CHF 0–104`), the allowance and amount are **unverified**: not included, not a proven fee. Reprice to a family with an explicit bag line before ranking.
5. Compare the cheapest bag-inclusive family against base + explicit bag fee; recommend the lower qualifying total and show the baggage state beside the price.

## Honesty

Keep the price in the displayed currency; any cross-currency conversion is labelled with the rate and date. Carriers not listed above are unverified until tested; do not extrapolate TAP's behavior to Lufthansa, easyJet or others.
