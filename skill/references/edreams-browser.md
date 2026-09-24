# eDreams browser interaction (edreams.com)

Observed working as an independent OTA cross-check in prior runs (dated evidence in `historical-observations.md`); verify a fresh exact-date result in the current run before depending on it.

URL guessing does NOT work: `edreams.com/flights/results?...` and
`edreams.com/flights/search?...` both 404 (Nuxt). Search only via the form;
the results URL is a hash fragment like
`/travel/#results/type=R;from=ZRH;to=RIO;dep=2026-10-01;ret=2026-10-10;...` that
is unusable to pre-seed — always drive the form.

## Working form flow

1. Decline non-essential cookies (`Continue without agreeing` or equivalent). Identify the visible **main flight-search form** — the one that pairs `Where to?` with a `Search Flights` submit — and scope ALL field lookup inside it, because `Where from?` matches two inputs (a Prime "flight deals" widget lower on the page also matches; typing there does nothing). Prefer the form that contains `Departure` and `Return` beside `Where from?` / `Where to?`. Reject any match outside the main form.
2. Origin: type `ZRH`, wait ~2s for autocomplete, then click the suggestion item
   whose text contains the airport name AND code (e.g. `Zurich Airport` + `ZRH`).
   Verify the field now reads `Zurich Airport` (city name, not code) before continuing.
3. Destination: same pattern (`RIO` → `Rio de Janeiro`).
4. **Dates cannot be typed**: the inputs are readonly. Inspect whether the
   calendar is already open. If closed, click `Departure`, wait for hydration,
   and inspect `.odf-calendar-title`; retry once only if still closed. If absent
   after that, record the form failure rather than looping. With the calendar
   open, identify the next-month arrow from the current DOM (multiple
   `.odf-btn-circle` controls may exist). Advance to the requested month/year,
   verifying each title; allow only the required month advances plus one.
   Continue to day selection without clicking Departure again.
5. Locate the `.odf-calendar` with the requested `.odf-calendar-title` (month
   AND year), then find its `div.odf-calendar-day` by the direct day text node,
   not whole `textContent`: a populated cell can read `1€107`, not `1`.
   Reject cells with the `disabled` class. Never select by day number across
   both months. Verify the input afterwards. If the calendar is absent, allow
   hydration and inspect again; reopen the field only when the popup is closed.
   Example after inspecting the current DOM:
   ```js
   const month = [...document.querySelectorAll('.odf-calendar')]
     .find(el => el.querySelector('.odf-calendar-title')?.textContent.trim() === "October '26");
   const day = [...(month?.querySelectorAll('.odf-calendar-day') || [])]
     .find(el => [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim() === '1')
       && !el.classList.contains('disabled'));
   if (!day) throw new Error('Requested date is not available in the visible calendar');
   day.click();
   ```
6. Read back Departure after selecting its day. Open the `Return` field
   explicitly and confirm the active field before selecting its day; never
   assume automatic switching, especially with restored dates. Read back BOTH
   values before submitting. A second day click can otherwise overwrite the
   departure. Recheck all pre-filled fields: eDreams may restore a prior search.
7. Submit with the `Search Flights` button (NOT `Search Flight + Hotel`). Wait for
   the results view (URL hash contains `#results/type=R;from=...`).

## Reading results

- After submitting, wait for the summary bar and inspect populated itinerary
  cards in the rendered main content. If only the summary is exposed, try the
  desired ranking tab (`Cheapest` / `Best` / `Fastest`) and one bounded scroll,
  then inspect the main content again (or a screenshot when supported).
  This is a fallback observed in a prior run, not a universal rendering rule.
  If cards remain absent after that bounded attempt, record incomplete results;
  never substitute the summary headline for an itinerary.
- Treat the summary bar and any `Cheapest` headline as discovery only, not a
  qualifying quote: the `Cheapest` option can contain a 2-stop, 23h+ outbound
  that fails a per-direction cap while its aggregate headline looks acceptable.
  Locate the matching itinerary card and parse BOTH directional durations before
  ranking or reporting it.
- Each itinerary card lists outbound and return as separate blocks: airline,
  `Hand luggage` / bag label, departure time, `1 stop`, arrival time, airport
  codes, and the `€ price`. `Per passenger` is the basis — check the booking
  quote for the true total.
- The displayed price can be a group-specific, first-booking, Prime, or Welcome
  discount. When the card exposes `Prime discounted price` and `Regular price`,
  retain both as observations, rank the regular/non-membership price by default,
  and re-open the fare family before treating either as a final total.
- **Currency:** record each price in the currency the site shows (eDreams may show EUR while other sources show CHF). Do not convert silently; if comparing across currencies, show a clearly labelled conversion with the exchange rate and its date, and never present the converted amount as a bookable quote. A base currency such as CHF belongs to an optional named user profile, not a universal assumption.

## Prior-run evidence

A fresh ordinary Chrome session on 2026-09-23 accepted ZRH–LIS, 2026-10-01 outbound and 2026-10-10 return, 1 adult, Economy, EUR, and returned populated itinerary cards. A prior report of a ~2.5-week minimum lead time was NOT reproduced; do not promote that observation to a provider rule. The old whole-cell text selector missed days that include fare amounts; selecting the direct day text inside the correct month worked. This is archived historical evidence (`historical-observations.md`), not a current-accessibility guarantee. Check the active departure/return field and calendar state before concluding a date is disabled.

## Pitfalls

- Do not type into date fields; they are readonly and will silently clear.
- The autocomplete suggestion click must land on the item containing the IATA
  code; clicking a bare city name can pick the wrong airport.
- eDreams is an OTA: verify baggage and totals in the completed itinerary, and
  treat its headline price as a list observation until the booking step reprices.
- `Prime` marketing (discounts, freeze-price upsell) is not a fare feature; ignore
  it for fare comparison and compare `Regular price`.
- The `/flights/` page can render while the search module is still hydrating;
  wait for the `Where from?` input to appear before filling.
