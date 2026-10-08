# Flight Source Ladder

Choose sources by evidentiary value, not by brand count. A populated exact-date result is stronger than a route teaser; a completed provider quote is stronger than a result card; an airline fare-family page is stronger than a generic baggage policy.

## Capability discovery and workflow scope

Check available connectors first: which are present, connected, authorized, support exact-date flight shopping, and what coverage/currency/baggage/freshness they expose. Kiwi.com, Expedia, lastminute.com are possible integrations, not installed dependencies; never assume connected. Prefer a capable connected connector; a blocked public site does not establish connector failure. Record backend relationships, not app-name counts.

Which comparisons a quick or full run needs is set at intake (`intake.md`) and tracked by `run_log.py coverage`. The quick path uses Google Flights (or a connected search), airline-direct qualification and one independent cross-check; FlightList, ITA Matrix and the hack matrix belong to the full path.

## Default no-credential ladder

### 1. FlightList: broad flexible discovery

Use `https://www.flightlist.io/` when the task has many date combinations, nearby gateways, cabin classes, a duration cap, or checked-bag requirements. Its rendered form supports date ranges, return trips, economy/premium/business/first, currencies, stop limits, maximum duration, self-transfer inclusion/exclusion, and 0–2 checked bags.

Form settings, date pickers, result parsing and limitations: `flightlist-browser.md`. FlightList hands booking off to Kiwi, so it is one Kiwi-backed discovery family; its checked-bag filter is a candidate signal, not baggage proof.

### 2. Google Flights: exact grid and completion

Use Google Flights to reproduce exact date pairs, select an outbound and a qualifying return, identify mixed cabins and airport changes, and capture the completed booking-provider card. Follow `google-flights-browser.md`.

### 3. eDreams: OTA cross-check (verify fresh each run)

Prior runs observed exact-date populated results, no fixed minimum lead, and per-fare baggage labels; those are dated observations archived in `historical-observations.md`, not current guarantees. In this run, load the main search form, decline optional cookies (`Continue without agreeing` or equivalent), select the direct day text within the correct month/year, verify the input values, and require a populated result. Drive the form — deep-link URL guessing 404s. Details in `references/edreams-browser.md`. Compare `Regular price` (non-membership) and reprice at checkout.

### 4. Airline-direct booking engines: qualification

After selecting a candidate, search the same itinerary on the marketing or ticketing airline site. Prefer the direct result when it exposes:

- branded fare family;
- checked-bag pieces/weight or explicit first-bag price;
- ticket total including mandatory fees;
- change/refund terms;
- operating carrier and cabin per segment.

If the airline engine cannot reconstruct an interline itinerary, retain the completed aggregator quote but label direct repricing unavailable. A generic policy page can identify which fare family includes a bag; it cannot qualify an unpriced fare.

### 5. ITA Matrix: independent fare/schedule cross-check

Use Matrix for fare and schedule corroboration, not booking or baggage. Follow `ita-matrix-browser.md`. If its Angular date controls do not commit or the results shell remains empty, record the failure and continue instead of treating a recent-search card as current evidence.

### 6. Opportunistic OTA cross-checks

Booking.com Flights and Alternative Airlines can expose broad inventory and sometimes fare add-ons. Use them only when the exact route/date form produces populated results in the current session. Their homepages loading does not prove their autocomplete, pricing backend, or checkout works.

Do not rank an OTA teaser above airline-direct unless the exact itinerary survives checkout repricing. Record the merchant of record and avoid equating flexible-ticket insurance with an airline-flexible fare.

## Partially usable sources (pragmatic tier)

- **AZair** (`azair.eu`) — loads without a bot wall; scope is low-cost carriers only (Europe/Mediterranean/Asia). Good for LCC route-hack discovery, cannot answer long-haul networks. See `references/azair-browser.md`.
- **FlightsFinder** — renders, but is a wrapper that re-aggregates Google Flights, KAYAK, Skyscanner and Momondo; NOT an independent backend. Do not count it as a separate source family.

## Current accessibility: the source ledger

Do not keep a hand-written status table here. Live per-source state (ok / partial / blocked / empty / error, with timestamps, evidence and inventory family) lives in the local source ledger (outside the skill folder; path rules in `source-health.md`), maintained by `scripts/source_ledger.py` via the canary probes in `source-health.md`. Run `source_ledger.py status` and `order` instead of trusting memory. Its seed rows came from the dated observations archived in `historical-observations.md` (2026-09-20/23), which also keep the detailed failure modes for KAYAK, Momondo, Skyscanner, Expedia, Kiwi direct, Orbitz, Priceline, CheapOair, Decolar, eSky, JetRadar, Airwander, PanFlights, Star Alliance, Wego, Jetcost and Trip.com.

Untested sources stay untested until probed.

Make one attempt per source per run and follow the challenge steps in `browser-engines.md` when a site blocks you. Cite only populated exact-date pages, never indexed snippets. Re-test on a future run because accessibility changes; a homepage loading today does not mean its search flow works.

## Credentialed official APIs

Check only whether credentials are configured; never print secret values or request them in chat.

### Duffel

Use when `DUFFEL_ACCESS_TOKEN` is configured. Duffel returns live airline offers, segments, owner airline, fare conditions, expiry, and—where supported—available services such as an additional checked bag. Request a single offer with available services, add the intended bag service, then price the offer again. Coverage is limited to participating airlines, and offers commonly expire within minutes.

### Skyscanner Flights Live Prices

Use when `SKYSCANNER_API_KEY` is configured and partner access is active. The official create/poll flow returns real-time prices, agents, deep links, legs, segments, carriers, duration, stop counts, airport-change flags, and itinerary refresh. Baggage fields require explicit partner enablement; the API documentation marks the generic `includeBaggageData` flag as non-functional/deprecated. Treat absent baggage as unverified.

### Amadeus Flight Offers Search/Price

Use when the appropriate Amadeus credentials and product access are configured. Flight Offers Search can return fare recommendations, bag allowance, first ancillary-bag prices, and fare details; Flight Offers Price validates the fare; Branded Fares Upsell exposes bundles. Enterprise products require approved access and should not be assumed from a generic Amadeus account.

### Aviasales/Travelpayouts

Do not make this a default dependency. Its real-time Flight Search API supports complex and multi-city searches but requires partner credentials, the actual user's IP/User-Agent, and a project with at least 50,000 monthly active users. The Data API is cached discovery data, not a live exact-date booking quote.

### Sabre and Travelport

Treat these as commercial GDS/NDC integrations. Use only when the user's environment already has approved credentials and the specific shopping product. They are not public fallbacks.

### Wrappers and scraping APIs

SerpAPI's Google Flights endpoint can improve transport reliability but is not independent from Google Flights. Unofficial RapidAPI, scraper, or reverse-engineered endpoints require provenance, terms, and freshness checks before use; never introduce one merely to inflate source count.

## Source-independence test

Before calling a fare corroborated, answer:

1. Did both sources execute the exact route, dates, passengers, cabin, and currency?
2. Do they rely on different inventory/search backends?
3. Did both expose a populated itinerary rather than an indexed teaser?
4. Is baggage independently verified or still inferred?
5. Did at least one source reach a completed provider or airline fare?

If any answer is no, state the limitation and lower confidence.