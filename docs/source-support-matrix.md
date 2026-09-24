# Source support matrix

Status of public and credentialed flight sources, seeded from the verified
2026-09-20 session findings and mirrored in `skill/references/source-ladder.md`.

> **Status changes over time.** Accessibility is a moving target: a homepage
> that loads today does not mean its search flow works, and a source blocked
> this run may return on the next. Re-test sources on every run. **CI never
> tests live sites** — this matrix is only as current as its last dated
> observations. "Status" reflects automated browser sessions (browser-act /
> headless Chromium) unless noted.

## Working sources (populated exact-date results)

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
| ITA Matrix | Independent fare/schedule cross-check | **Untested** | Form may not commit; search form may not submit successfully. Test per run — do not treat a recent-search card as current evidence. |
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