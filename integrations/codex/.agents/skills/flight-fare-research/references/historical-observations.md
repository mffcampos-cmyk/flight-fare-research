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
