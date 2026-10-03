# Source support matrix

Status of public and credentialed flight sources, seeded from the verified
2026-09-20 session findings. Since v1.1.0 each user's live per-run state is kept
in a local source ledger (`skill/references/source-health.md`); this matrix is
the published, dated summary and is not regenerated automatically.

> **Status changes over time.** Accessibility is a moving target: a homepage
> that loads today does not mean its search flow works, and a source blocked
> this run may return on the next. Re-test sources on every run. **CI never
> tests live sites** — this matrix is only as current as its last dated
> observations. "Status" reflects automated browser sessions (browser-act /
> headless Chromium) unless noted.

## Latest ledger canary (2026-10-03)

Fixed canary contract: ZRH→LIS, 2026-11-02 → 2026-11-09, 1 adult, economy,
CHF. Engine: **headless** Playwright Chromium (no browser-act). A canary `ok`
proves the search flow worked that day; its prices are not fare evidence.

| Source | Canary state | Notes |
|--------|--------------|-------|
| Google Flights (`?q=` link) | **ok** | Consent declined; form repeated route, dates, 1 adult, economy, CHF; 8 results. |
| TAP booking engine (deep link) | **ok** | The documented deep-link format still works; 5 direct + 8 connecting outbound priced in CHF (per-direction pricing). |
| ITA Matrix | **ok** (was untested) | Form submit with native-setter dates; heading repeated route and dates; Complete Trips priced in CHF. |
| eDreams (`edreams.ch`) | **partial** | Form, calendar and exact results hash worked in CHF; only the summary rendered, no itinerary cards. Re-probe in a headed browser before demoting. |
| FlightList | **error** | Page loads without a bot wall, but airport autocomplete returned no suggestions. Re-probe in a headed browser before demoting. |

The eDreams and FlightList results may be headless-specific; both worked in
ordinary browser sessions on 2026-09-23 (below).

## Working sources (populated exact-date results, 2026-09-23)

| Source | Type | Status | Date of observation | Notes |
|--------|------|--------|---------------------|-------|
| FlightList (`flightlist.io`) | Discovery frontend (Kiwi-backed) | **Working** | 2026-09-23 | ZRH–LIS Oct 1–10: 100 exact-date populated cards collected; both durations parsed and under cap. List fares only; checked bags unverified. Hands booking off to Kiwi — not an independent airline quote. |
| Google Flights | Exact-date search + completion | **Working** | 2026-09-23 | ZRH–LIS Oct 1–10: completed provider card €353 (list €355), easyJet + Vueling, separate tickets; checked bags fee required; return arrives Oct 11. |
| eDreams (`edreams.com`) | OTA (own booking engine) | **Working** | 2026-09-23 | ZRH–LIS Oct 1–10: six initial exact-date cards collected; sampled SWISS regular list fare €500 versus Prime €416, checked bags unverified. Prior minimum-lead claim not reproduced; date cells include fare text. Drive the form. |

## Partially usable

| Source | Type | Status | Date of observation | Notes |
|--------|------|--------|---------------------|-------|
| AZair (`azair.eu`) | LCC route-hack search | **Partial / LCC-only** | 2026-09-20 | Loads without a bot wall; low-cost carriers only (Europe/Mediterranean/Asia). Cannot answer long-haul networks. |
| FlightsFinder | Search frontend | **Not an independent source** | 2026-09-20 | Renders, but re-aggregates Google Flights, KAYAK, Skyscanner and Momondo — same inventory/backends. Do not count as a separate source family. |

## Blocked public frontends

One attempt per source per run; record the failure mode then move on. Do not
loop retries or install evasion tooling.

| Source | Failure mode | Date of observation |
|--------|--------------|---------------------|
| KAYAK | search URL redirects to `/help/bots.html` — blocked for search | 2026-09-20 (retested) |
| Momondo | dedicated bot page | 2026-09-20 |
| Skyscanner | person-or-robot CAPTCHA | 2026-09-20 |
| Expedia | bot challenge | 2026-09-20 |
| Kiwi (direct) | HTTP 403 / navigation failure | 2026-09-20 (retested) |
| Trip.com | provider guard | 2026-09-20 |
| Wego | Cloudflare block | 2026-09-20 |
| Jetcost | Cloudflare block | 2026-09-20 |
| PanFlights | HTTP 403 | 2026-09-20 |
| Star Alliance booking | HTTP 403 | 2026-09-20 |
| Orbitz | "Bot or Not?" human check | 2026-09-20 |
| Priceline | press-and-hold "confirm you are a human" wall | 2026-09-20 |
| CheapOair | renders an empty DOM tree headless | 2026-09-20 |
| Decolar | homepage title loads but body renders empty | 2026-09-20 |
| eSky | "Access Denied" | 2026-09-20 |
| JetRadar | TLS cert error (`ERR_CERT_COMMON_NAME_INVALID`) | 2026-09-20 |
| Airwander | DNS resolution failure — site appears defunct | 2026-09-20 |

## Untested / requires credentials

| Source | Type | Status | Notes |
|--------|------|--------|-------|
| ITA Matrix | Independent fare/schedule cross-check | **ok on 2026-10-03 canary** | See the latest canary above. Test per run; do not treat a recent-search card as current evidence. |
| Duffel | Official API | Untested (credentialed) | Requires `DUFFEL_ACCESS_TOKEN`; live offers + ancillary baggage pricing. |
| Skyscanner API | Official API | Untested (credentialed) | Requires `SKYSCANNER_API_KEY` + partner access. Baggage fields need explicit partner enablement. |
| Amadeus | Official API | Untested (credentialed) | Flight Offers Search/Price; enterprise products need approved access. |
| Aviasales / Travelpayouts | Official API | Untested (credentialed) | Needs partner credentials, user IP/User-Agent, large MAU project. Not a default dependency. |
| Sabre | Commercial GDS/NDC | Untested (credentialed) | Only with approved credentials + specific shopping product. |
| Travelport | Commercial GDS/NDC | Untested (credentialed) | Only with approved credentials + specific shopping product. |

Only the three working sources above were re-tested on 2026-09-23. Other
rows retain their earlier observation dates, not a claim of current access.
See [sanitized release evidence](release-evidence/2026-09-23.json) for the
matched contract, directional times, quote states and collection scope.

## See also

- `skill/references/source-ladder.md` — canonical source ladder, browser recipes, and the source-independence test.
- `docs/safety-and-provenance.md` — safety and provenance rules that govern how blocked and working sources are handled.
- `docs/manual-release-checklist.md` — the pre-release browser-act run that confirms working sources before tagging.