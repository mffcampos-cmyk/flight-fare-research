# Historical source observations

Dated prior-run and user-reported evidence, preserved to keep operational recipes current. These are not guarantees and do not reflect the state of any connector. Recheck relevant sources once per run under the anti-evasion policy.

## Source-ladder legacy notes (2026-09-20)

Verified working in a plain headless Chrome session that day: FlightList rendered discovery cards; eDreams rendered exact-date round-trip results with prices, stops, local times and per-fare baggage labels. Public frontends explicitly blocked or rendering empty that day: KAYAK, Momondo, Skyscanner, Expedia, Kiwi direct, Trip.com, Wego, Jetcost, PanFlights, Star Alliance booking, Orbitz, Priceline, CheapOair, Decolar, eSky, JetRadar, Airwander. AZair loaded without a bot wall (low-cost scope only).

## eDreams retest (2026-09-23)

ZRH–LIS, 2026-10-01 outbound and 2026-10-10 return, 1 adult, Economy, EUR returned populated itinerary cards. A ~2.5-week minimum lead report was NOT reproduced. Selecting the direct day text inside the correct month worked; whole-cell text missed days with fares.

## Google Flights and TAP user observations (2026-09-23)

Test search ZRH→LIS, Thu 5 Nov → Thu 12 Nov 2026, 1 adult, economy, 1 checked bag, run in the Cowork built-in browser:

- A plain `?q=` link loaded populated results with route, dates, 1 adult and economy all verified in the form: `https://www.google.com/travel/flights?q=Flights%20from%20ZRH%20to%20LIS%20on%202026-11-05%20through%202026-11-12%20economy&curr=CHF&hl=en`
- On the booking page Google showed the bag price as a range: `1st checked bag: CHF 0–104` — a zero lower bound, so allowance/amount is unverified.
- Clicking the flight card (not the off-screen `Select flight` button) selected the outbound and then the return; the page title changed to `Lisbon to Zürich` (return list) then `Round trip to …` (booking page).
- TAP direct link (see `airline-direct.md`) returned Discount/Classic/Plus families; Classic included one bag each way.

These are dated observations for provenance; validate them live before relying on the URLs.

## First ledger canary (2026-10-03, headless Playwright Chromium)

ZRH→LIS 2026-11-02/09, 1 adult, economy, CHF. Google Flights `?q=` link: ok, 8 results. TAP deep link (format in `airline-direct.md`): ok, 5 direct + 8 connecting outbound. ITA Matrix form: ok, Complete Trips in CHF. eDreams.ch (CHF, German UI; button `Flug suchen`, placeholders `Von?`/`Nach?`/`Hinflug`/`Rückflug`): exact results hash plus summary, but no cards rendered (partial). FlightList: autocomplete dead (error). Live state now lives in the local source ledger (see `source-health.md`).

## Headed re-probe (2026-10-03, system Chromium, same canary)

Both earlier failures were recipe gaps. FlightList: ok once key events carried a real `keyCode`; 100 cards, all on the exact dates in CHF. eDreams.ch: ok after declining consent via the `Weiter ohne Zustimmung` link and clicking `Weitere 30 Ergebnisse anzeigen`; 6 cards with both directions, hand-baggage labels, and struck regular vs Prime price. Headless Chromium was not shown to be the cause.

## Blocked public frontends (2026-09-20, automated browser)

| Source | Failure mode |
|---|---|
| KAYAK | search URL redirects to `/help/bots.html` (retested) |
| Momondo | dedicated bot page |
| Skyscanner | person-or-robot CAPTCHA |
| Expedia | bot challenge |
| Kiwi (direct) | HTTP 403 / navigation failure (retested) |
| Trip.com | provider guard |
| Wego | Cloudflare block |
| Jetcost | Cloudflare block |
| PanFlights | HTTP 403 |
| Star Alliance booking | HTTP 403 |
| Orbitz | "Bot or Not?" human check |
| Priceline | press-and-hold "confirm you are a human" wall |
| CheapOair | empty DOM headless |
| Decolar | title loads, body empty |
| eSky | "Access Denied" |
| JetRadar | TLS certificate error (`ERR_CERT_COMMON_NAME_INVALID`) |
| Airwander | DNS failure; site appears defunct |

FlightsFinder rendered but re-aggregates Google Flights, KAYAK, Skyscanner and
Momondo: not an independent family.

## Release smoke test (2026-09-23, ZRH–LIS 1–10 Oct 2026, 1 adult, economy, EUR)

| Source | Result |
|---|---|
| FlightList | 100 exact-date cards; both durations parsed, all under a 20-hour cap; list fares, bags unverified |
| Google Flights | completed provider card €353 (list €355), easyJet + Vueling on separate tickets; bag fee required; return arrives 11 Oct |
| eDreams | six exact-date cards; sample SWISS regular €500 vs Prime €416; bags unverified |

## Expansion probe (2026-10-08, headless Playwright Chromium, datacenter egress proxy)

Canary ZRH⇄LIS 7–14 Nov 2026, 1 adult, economy. One paced attempt per source,
optional cookies declined, no retries after a challenge (three still-loading
pages got one longer wait). This is browser ladder rung 3, the most likely to be
challenged: a block here says nothing about the user's own browser.

| Source | Result |
|---|---|
| Google Flights (`?q=` link) | ok: search repeated, 10 round-trip cards in CHF (nonstop TAP/SWISS from CHF 134) |
| TAP direct (deep link) | ok: search repeated, 5 direct flights, CHF per direction |
| FlightConnections (`flights-from-zurich-zrh`) | ok (routes): 218 destinations, 61 airlines, non-stop filters |
| Booking.com Flights (deep link) | empty: form repeated the search, then "We don't have any flights matching your search" |
| Kiwi direct (deep link) | empty: page loads (was HTTP 403 on 2026-09-20), filters shown, no results after 45 s |
| Aviasales (deep link) | empty: route and dates repeated, results never rendered |
| KAYAK, Momondo | blocked: "Was ist ein Bot?" |
| Skyscanner | blocked: press-and-hold "Are you a person or a robot?" |
| Expedia | blocked: HTTP 429 "Bot oder Mensch?" |
| Trip.com | blocked: HTTP 432 "whaleguard block" |
| easyJet (deep link) | blocked: HTTP 403 Access Denied |
| lastminute.com, Icelandair, Omio | blocked: Cloudflare challenge |
| SWISS, Lufthansa | blocked: HTTP 403 "Security check" |
| Iberia | blocked: HTTP 403 "connection was interrupted" |
| Qatar Airways | blocked: HTTP 403 Access Denied |
| SBB | blocked: HTTP 403, empty body |
| Alternative Airlines, Gotogate, Opodo, AZair, Ryanair, Vueling, Trainline | homepage loads; search flow not driven (still untested) |
| British Airways | "high demand" holding page (untested) |
| KLM, Air France, Turkish Airlines | not reached: the environment's proxy reported "upstream request failed" (untested) |

Takeaways: airline and rail sites guard headless sessions hardest, so price
them in the user's own browser (rung 1). Kiwi direct and Booking.com load
headless but returned no fares; try them on rung 1 before relying on them.
