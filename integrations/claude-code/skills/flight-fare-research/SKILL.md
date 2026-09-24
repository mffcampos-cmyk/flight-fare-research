---
name: flight-fare-research
description: "Use when researching live airfare and route hacks."
version: 1.0.0
author: hermes-curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [flights, airfare, travel, prices, baggage, browser]
    related_skills: [grounded-citations, product-price-monitor, browser-automation]
---

# Flight Fare Research

Research bookable flight choices for fixed or flexible dates. Compare like with like: traveler count, dates, airports, cabin, baggage, currency, and mandatory fees. Treat a search-result price as an observation, not a guaranteed fare.

## Choose the workflow

- **Quick path:** fixed dates, one requested cabin, short/medium haul, no flexible dates, fixed event or stopover, and no explicit route-hack request. For a quick request: discover connectors, use a suitable connected search or Google Flights, qualify the shortlist airline-direct, and attempt one independent OTA cross-check. Run one practical nearby-airport check if permitted, otherwise record why not. Skip rolling pairs, FlightList, ITA Matrix, other cabins, and the full route-hack matrix.
- **Full path:** flexible dates, several requested cabins, long-haul, a fixed event, stopover, or an explicit route-hack request. Use the full ladder, FlightList discovery, rolling matched pairs, the full route-hack matrix and stopover construction below.
- Both paths keep the same exact-date, baggage, cabin, duration-cap, cookie, source-independence and safety gates. State the chosen path and any deliberate skips. Search and report **only the cabins requested**; if none is requested, state an economy assumption rather than silently searching three cabins.

## Procedure

### 1. Pin the search contract

Record travelers, origin area, destination airport/city, outbound and return dates, target trip length, cabin(s), checked/cabin bags, currency, acceptable date/length flexibility, any fixed event, required pre-event local sleeps, hard duration cap, and whether the user wants destination planning or flight research only. If the user knows the destination or asks only for fares, do not add sightseeing or a day-by-day itinerary. If the user names a country or region rather than an airport, search the practical airports without asking unless ground access changes the answer materially.

Use only the origins, currency, nearby gateways and per-direction duration limits specified or confirmed for the current request. Do not infer a home location or persistent travel profile. State any assumptions before searching. Enforce the requested cap independently on outbound and return; a strict cap excludes equality. An explicitly requested multi-day stopover overrides only its continuous elapsed span, not each flown city-pair cap. Display local times and durations as `HH:MM:SS`; identify next-day arrivals. A return date means departure from the destination unless an arrival-home deadline is specified.

Use strict `HH:MM:SS` for every displayed flight time. State whether arrival is next day and keep airport-local times; do not convert silently. Treat a flexible return date as the departure date from the destination unless the user says they must be home by that date; state this interpretation and flag any next-day arrival at the edge of the range. If an arrival-by deadline would change the winner, provide or offer the reranked option.

When travel is anchored to a wedding or other fixed event, calculate the event’s local weekday and time-zone offset before searching. Search exact-length matched date pairs first, prefer arrival at least three local sleeps before the event (four for an eastward shift of roughly six or more hours), and keep the day before the event low-intensity. Load `references/event-anchored-trip-planning.md` for the full planning recipe.

### 2. Collect exact-date live results

Discover connectors first: list available travel connectors and check each for connected status, authorization, and exact-date flight-shopping support, then check coverage, currency, baggage fields, and quote freshness. Kiwi.com, Expedia, and lastminute.com are possible integrations for hosts that expose them, never assumed installed or connected. Prefer a suitable already-connected connector; a blocked public site does not establish connector failure. Fill gaps with browser sources and disclose unavailability. Never ask for or accept secrets in chat.

Use an interactive flight search when static extraction does not render fares. Default to the **browser-act** CLI as the automation engine (real Chromium, JS rendering, form/date-picker interaction, populated-result reads); load `references/browser-act-support.md` for environment setup (non-root Chrome data-dir resolution), session reuse, consent handling (decline non-essential cookies on every source — `Reject all`, `Continue without agreeing`, or equivalent — and never accept optional cookies to obtain fares), and the one-pass source-triage loop before driving any source. Set every search dimension explicitly and verify the resulting page repeats the exact route, dates, traveler count, cabin, and currency before recording any price.

For each result save:

- retrieval time and source URL;
- total round-trip price and currency;
- operating/marketing airlines;
- departure and arrival airports and local times;
- stop count, elapsed duration, airport changes, and overnight arrival;
- cabin mix and baggage status;
- whether the price is a headline list fare or a completed-itinerary booking quote.

Wait for a real result count and populated itineraries. A loading shell, route teaser, cached monthly minimum, CAPTCHA, or bot page is not an exact-date quote.

For a fixed-length flexible trip, enumerate **rolling matched pairs** before searching. Example: “10 days, anywhere from 5–15 through 10–20 March” means `5→15`, `6→16`, `7→17`, `8→18`, `9→19`, and `10→20`—six exact windows per origin/cabin. Keep the fixed event inside every pair and calculate destination sleeps before it. Do not silently replace these with one ±2-day pair or with a cheaper trip of a different length.

Build a broader Cartesian product only when the user explicitly accepts shorter or longer trips; label each trip length and enforce any minimum event buffer. Save every pair, verify the expected count programmatically, and rank from the collected rows. A calendar heatmap or date-grid minimum is not a substitute for exact-date results.

Load `references/source-ladder.md` before choosing collection sources. The default no-credential **full-path** browser flow is:

0. For a **quick** request, a compact variant is: Google Flights `?q=` link (or a connected search), airline-direct qualification, one independent travel-agency cross-check, and one practical nearby-airport check; then stop.
1. Use **FlightList** (full path) to scan broad flexible date ranges, cabins, duration limits, checked-bag candidates, and self-transfer alternatives in one query.
2. Reproduce shortlisted exact date pairs in **Google Flights** and complete both directions.
3. Cross-check the shortlist on **eDreams** — an OTA observed working in prior runs, with its own booking engine and per-fare baggage labels, requiring a fresh exact-date result in this run (see `references/edreams-browser.md` for the form flow).
4. Reprice the winner in the **operating or ticketing airline's own booking engine** to expose branded fare families, baggage, and direct-booking totals.
5. Use **ITA Matrix** for an independent schedule/fare cross-check when its search form submits successfully.
6. Use Booking.com Flights, Alternative Airlines, or **AZair** (low-cost carriers only, `references/azair-browser.md`) as opportunistic cross-checks when their rendered search flow works; never depend on them for exhaustive collection.

FlightList is a discovery source, not final baggage proof: its results lead to Kiwi booking links, and a checked-bag search filter does not establish that the completed fare still includes the bag. For the FlightList date-picker automation and result extraction, load `references/flightlist-browser.md`. For Google Flights browser details and selectors, load `references/google-flights-browser.md`. For ITA Matrix, load `references/ita-matrix-browser.md`. The `references/source-ladder.md` file tracks which public frontends are currently blocked (KAYAK, Priceline, Orbitz, Kiwi direct, and others) with observed failure modes; re-test sources on future runs because accessibility changes.

### 3. Verify the complete itinerary and baggage

Select both outbound and return before judging the fare. Apply any journey-duration cap independently to the outbound and return choices before selecting the lowest price; a cheap outbound does not qualify when every compatible return breaches the cap. The result list may say that optional bag fees apply; it does not prove inclusion. On the completed itinerary, record the explicit baggage line and booking-provider total.

Classify baggage as exactly one of:

- **included** — the completed itinerary or fare family explicitly includes at least one checked piece;
- **fee required** — the page explicitly says the first checked bag costs extra;
- **unverified** — no itinerary-level allowance is exposed, or a range whose lower bound is zero (e.g. `CHF 0–104`) leaves allowance and amount uncertain. A zero lower bound proves neither inclusion nor a required fee; use **fee required** only when an itinerary-specific positive charge or explicit paid-bag requirement is proven.

Never label a fare “bag included” from airline norms, cabin expectations, or a generic policy page. Use the airline policy only to explain which fare family must be selected; reprice that family at checkout when possible.

Expand branded fare families whenever the booking card exposes them. If `View options` is absent, off-screen, inert, or exposes no usable family/baggage details after one bounded attempt, go to the airline booking engine (`references/airline-direct.md`). Compare the cheapest bag-inclusive family against the base fare plus the explicit bag fee; the inclusive family can be cheaper than adding a bag to the headline fare. If the completed page says the price changed, replace the list-page amount with the completed provider total and retain the old amount only as a clearly labeled stale observation.

### 4. Compare cabins honestly

Search economy, premium economy, and business separately when requested. Preserve mixed-cabin labels such as `Economy + Premium Economy` or `Business + Economy`; do not shorten them to the higher cabin. Prefer a slightly higher pure-cabin itinerary over a misleading mixed-cabin headline, and identify which long-haul segment carries the premium cabin when detail is available.

### 5. Run the route-hack matrix

On the **full path**, establish the normal round trip from the home airport, then test every applicable structure below against the same matched date windows and cabin:

1. **Split one-ways:** sum independently priced outbound and return one-way tickets, including different airlines and sales channels; compare the bag-qualified sum with the completed round trip.
2. **Multi-city/open-jaw:** test home→destination plus destination→nearby European hub, the reverse orientation, and mixed home/nearby-airport endpoints. Add the train or positioning leg needed to close the open jaw.
3. **Nearby gateways:** test practical rail/short-flight hubs in both round-trip and one-way combinations. Prefer rail where it eliminates another checked-bag fee or airport connection.
4. **Alternate destination gateways:** test a major regional gateway plus a protected or separately priced local leg only when elapsed time, baggage handling, and misconnection risk remain acceptable.
5. **Stopover and route-specific opportunities:** use the host’s available web-search tool to look for fifth-freedom flights, free/cheap stopover programs, new seasonal routes, rail-and-fly products, and current route deals. Treat indexed deal pages as leads only; every idea must be repriced on exact dates. Use the stopover construction below whenever the user wants one or more nights at a connection hub.
6. **Provider/fare-family arbitrage:** compare airline-direct, reputable aggregator, and exposed branded fare families. Do not rank an OTA teaser above an airline-direct fare until the completed itinerary survives repricing.

#### Stopover construction

1. Price the carrier’s official stopover or multi-city tool first so all sectors can remain on one protected itinerary.
2. If the complete itinerary will not price, build a reproducible fallback: price `home→stopover hub` plus `destination→home` as one long-haul open jaw, then price `stopover hub→destination` separately. Compare both the same-carrier local sector and a cheaper regional carrier.
3. Complete every constituent ticket and verify its provider total and checked-bag line independently; never transfer the baggage allowance from the long-haul ticket to a separate local ticket.
4. Verify the carrier’s official rule for a stay over 24 hours, especially baggage collection, and check entry permission against the traveler’s actual passport rather than inferring nationality. A stopover normally requires baggage collection even when all flights share a carrier.
5. Calculate the exact time in the stopover city, hotel nights, arrival date at the final destination, pre-event local sleeps, and the time-zone change after the stopover. Present a two-night and three-night version separately when both fit the event buffer.
6. Show the bag-qualified flight total, unpriced hotel/ground costs, and fare delta versus the original through itinerary. Label split-ticket protection and recommend the one-ticket stopover whenever its premium is reasonable.

For every positioning, open-jaw, multi-city, or split-ticket result, compute or disclose the all-in total: long-haul ticket, required checked bag, rail/positioning ticket, airport hotel, and unavoidable transfers. Show the **break-even positioning budget** versus the best qualifying home-airport fare. Preserve the total trip window: a previous-day positioning night changes the trip length and event buffer.

Disclose self-transfer, baggage reclaim/recheck, airport changes, separate-ticket misconnection exposure, and transit-entry requirements still needing verification. Recommend previous-day positioning for a high-value long-haul ticket unless the connection is protected on one ticket. For the return positioning leg, reject departures that leave no realistic time after the long-haul arrival for immigration, baggage reclaim, terminal transfer, and recheck; price a later same-day flight or hotel instead, and show that timing in the all-in construction. Reject hidden-city ticketing when checked luggage is required because the bag normally follows the ticketed destination; never present throwaway segments as a bag-compatible hack.

### 6. Cross-check and rank

Use at least two independent live **source families** when accessible—for example FlightList/Kiwi discovery plus Google Flights completion, followed by airline-direct repricing. Two frontends backed by the same inventory or redirect chain are not fully independent; disclose the relationship. An airline-direct booking card exposed inside an aggregator is useful qualification evidence but is not a separate retrieval source until the airline site itself returns the fare.

If a source displays an explicit bot page, CAPTCHA, Cloudflare block, HTTP 403, or provider guard, make one recorded attempt, mark it blocked for that run, and move on. Do not loop retries, install or configure anti-detection tooling, rotate proxies, solve CAPTCHAs, or otherwise evade the provider's controls merely to recover a fare. Use an official API, airline-direct engine, alternate source, or user-visible manual path instead. If only one exact-date source remains, say so plainly and downgrade confidence rather than implying corroboration. Cite only pages actually retrieved, following `grounded-citations` when available. Inline fallback where that skill is unavailable: give source name, retrieved URL (or connector identity/query/offer ID), retrieval timestamp with timezone, and the exact claim supported; distinguish current observations, historical user reports, policies, and unvisited navigation links; never cite a blocked page as fare evidence.

When credentials are already configured, prefer the official APIs in `references/source-ladder.md`: Duffel for live offers plus ancillary-bag pricing, Skyscanner Flights Live Prices for partner inventory, or Amadeus Flight Offers Search/Price for fare and baggage data. Never ask for or accept API secrets in chat; use the configured secret store or environment.

Apply hard gates first: matched trip window, fixed event and sleep buffer, per-direction duration cap, completed cabin integrity, and checked-bag requirement. Then rank **each requested cabin separately** for:

1. lowest qualified all-in total;
2. best time/price balance;
3. best pure-cabin option when the cheapest is mixed;
4. best route hack after positioning cost, added trip days, and failure risk.

On the full path, for each requested cabin, compare the winning round trip against split one-ways, multi-city/open-jaw, and nearby-gateway structures. A hack is a winner only when its all-in total and operational risk beat the home-airport baseline.

Show the baggage state beside every shortlisted price. Do not bury an unpriced bag supplement in a footnote.

## Output Shape

- Start with assumptions, the enumerated matched date windows, event buffer, and retrieval timestamp.
- Give compact sections for the requested cabins only; identify the lowest qualified all-in fare in each. Do not add cabins the user did not ask for.
- Each option includes price, airlines, route, local times, stops/duration, cabin integrity, and baggage state.
- Put split one-ways, multi-city/open-jaw, nearby-airport/rail, and other route hacks in a separate comparison with all-in cost, break-even budget, added days, and risk.
- Include only the event/jet-lag timing needed to justify the travel window. Do not add destination sightseeing or a day-by-day itinerary unless requested.
- End with 3–5 ranked recommendations and direct search/booking links.
- Distinguish live exact-date quotes from generic airline-policy or deal-page evidence.

## Pitfalls

- Verify the completed itinerary before claiming baggage inclusion — list pages commonly quote a no-bag fare.
- Preserve mixed-cabin wording — the highest cabin in the itinerary is not the cabin for every segment.
- Reject stale monthly minima and indexed teaser prices as exact-date evidence — they may describe another travel period.
- Price both directions before reporting a round-trip total — an outbound card can change after the return is chosen.
- Include airport changes explicitly — a nominal one-stop itinerary can require reclaiming bags and crossing a city.
- Compare route hacks only after positioning costs, baggage, added hotel nights, changed trip length, and failure risk—a cheaper long-haul origin can be worse all-in.
- Do not call a Cartesian ±date sweep equivalent to a fixed-length rolling window; generate the matched pairs explicitly and verify their count.
- On the full path, do not stop at nearby-airport round trips; split one-ways and open-jaw/multi-city combinations can produce a lower all-in fare or remove a positioning leg.
- Treat route-hack articles and indexed deal prices as discovery leads, never exact-date evidence.
- Treat FlightList's checked-bag filter as a candidate signal only; its Kiwi handoff must survive fare-family and baggage repricing before the result qualifies.
- Do not count SerpAPI or another Google Flights wrapper as an independent source from Google Flights; FlightList and its Kiwi handoff are one discovery family.
- Stop after one explicit bot/CAPTCHA/403 response from a source during the run; repeated retries waste time and do not improve evidentiary quality.
- Save multi-airport/cabin batches to JSON or CSV and aggregate programmatically—visual scanning loses fares and creates count errors.

## Verification

- [ ] Route, dates, passengers, target trip length, cabins, airports, currency, fixed event, and required pre-event sleeps match the request.
- [ ] Every rolling matched date pair was searched for every required origin/cabin; collected counts equal `pairs × origins × cabins`.
- [ ] Every shortlisted outbound and return independently satisfies the total-journey duration cap; exactly 20 hours fails a strict under-20-hour requirement.
- [ ] Every shortlisted price comes from a populated exact-date result or completed itinerary; any booking-page reprice supersedes the list amount.
- [ ] Every shortlisted option says included, fee required, or unverified for checked baggage, and any exposed base-plus-bag total was compared with the bag-inclusive fare family.
- [ ] Workflow scope is explicit: quick path used (one nearby-airport check plus recorded reason for any skips) or full path used (round trip, split one-ways, multi-city/open-jaw, nearby-airport/rail compared for each requested cabin or marked not applicable with a reason).
- [ ] Mixed cabins, self-transfers, airport changes, separate tickets, and added positioning days are explicit.
- [ ] Any requested multi-day stopover was priced as one protected itinerary first and, when needed, as an open-jaw-plus-local fallback; each ticket’s baggage, hotel nights, event buffer, entry caveat, and delta versus the through fare are explicit.
- [ ] Every route hack shows all-in cost or a clearly labeled unpriced component plus its break-even budget versus the home-airport baseline.
- [ ] Destination sightseeing is omitted unless the user requested it.
- [ ] At least two independent source families were attempted; successful sources, shared inventory relationships, blocked sources, and single-source confidence limits are explicit.
- [ ] Any FlightList candidate was reproduced on a completed booking source before baggage inclusion or bookability was claimed.
- [ ] Sources and retrieval time are present; blocked sources and indexed deal pages are not presented as fare evidence.
