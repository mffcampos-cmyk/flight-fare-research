# Google Flights Browser Recipe

Use this only when the live Google Flights UI is the selected source. Re-read the rendered controls because labels and DOM structure can change.

## Exact-date search

**Open the search by URL.** `scripts/gflights.py url` builds the exact search
(the `tfs` parameter) for any cabin, one-way, round trip, multi-city, and
several airports on one end:

```bash
G=<skill_dir>/scripts/gflights.py
python3 $G url --cabin premium ZRH-GIG@2026-12-22 GIG-ZRH@2027-01-12          # round trip
python3 $G url --cabin economy ZRH-GIG@2026-12-22                             # one-way
python3 $G url --cabin economy ZRH-GIG@2026-12-22 GRU-ZRH@2027-01-12          # open jaw
python3 $G url --cabin economy BSL+GVA+MXP+MUC+FRA-GIG@2026-12-22 GIG-BSL+GVA+MXP+MUC+FRA@2027-01-12
```

Every one of these opened populated results on 2026-10-08. The older
natural-language link (`/travel/flights?q=Flights%20from%20...`) worked for
economy and business but landed on the Google Flights home page for premium
economy and first; do not use it for those cabins.

**Wait for the first priced card, not a timer.** The page text always contains
the words `Loading results` (hidden header text), so waiting for them to
disappear waits forever. The page is ready when a card with a price appears
under a heading such as `Top departing flights`, `Top flights`, `Departing
flights`, `Returning flights` or `Top flights to <city>`. Read it every second
or two and stop at the first card; a fixed 30-second wait per search tripled
the sweep time in the live run.

**Verify the page repeats the search.** The selected cabin is the line just
above the cabin list (`Premium economy` above `* Economy`), and a round trip or
one-way page says `Track prices from … departing 2026-12-22 and returning
2027-01-12` (one-way: `departing 2026-12-22` only). A multi-city page has no
such line: check that every card departs on the first leg's date.
`gflights.py parse --anchor <first-leg date> <page text file>` returns the
state (`results`, `empty`, `loading`, `challenge`), the selected cabin, the
repeated dates and every card (price, local times with dates, duration, stops,
airlines and operator, departure and arrival airports, layovers, mixed-cabin
label) as JSON.

**Sweep many pairs unattended (BrowserAct).** With a BrowserAct session open
(`browser-engines.md`), one command runs a search per cabin and date pair of
the run, verifies each page, records the cheapest cards within the duration
cap as list rows and stops at the first challenge:

```bash
python3 $G sweep --run <run dir> --session ffr --cabins economy,business \
  --pairs 2026-12-22_2027-01-12,2026-12-21_2027-01-13 --top 3 --pause 12
```

Other engines: open the `url` output, read the page text, pipe it to `parse`,
and add the rows with `run_log.py add` (it accepts a JSON array).

**Spend Google searches on confirmation, not discovery.** On one network,
about 90 Google Flights searches within a day were followed by HTTP 429 and a
redirect to `google.com/sorry` (2026-10-09). Discover the cheapest pairs of a
flexible window with one FlightList range search (`flightlist-browser.md`),
then confirm only the cheapest few pairs here. The `Date grid` dialog (7×7
date pairs around the searched dates) is the request Google refused first: if
its cells stay as `0000` placeholders, treat it as a block and do not retry.

**By hand, when no URL can be used:**

1. Open `https://www.google.com/travel/flights?hl=en&curr=<CURRENCY>` and decline optional cookies (`Reject all` or equivalent; a consent screen is not a bot block).
2. Inventory controls with `Accessibility.getFullAXTree`; match route controls by `aria-label` and airport suggestions by role `option` plus the exact IATA code.
3. Set origin and destination, then open the visible departure/return field.
4. Google may render duplicate date inputs: one in the search form and one in the open calendar. Identify the active calendar input from its non-zero bounding rectangle or focus it directly with JavaScript. Insert the date with CDP `Input.insertText`, press Enter, and click the `Done. Search for round trip flights...` button. Avoid coordinate clicks near the top-right header because they can hit Sign in rather than the calendar.
5. Click Search and verify the `/travel/flights/search` page repeats the requested dates and route.
6. Wait for the first priced card as above; save the query URL and the page text.

With browser-act, a verified alternative is `input --selector` on the active
calendar's unique input followed by `keys Enter` for each date. Inspect the
current DOM to identify that input (do not persist transient `aria-describedby`
values from a prior run). Then click the current `Done. Search...` button,
re-read state, and click Search. Never chain selectors across a re-render
without checking the new state.

The same steps in page code (run in page; key and text actions mapped per engine in `browser-engines.md`):

```js
// focus the second (calendar) Return input, then insert the locale date text and press Enter with key code 13
document.querySelectorAll('input[aria-label="Return"]')[1].focus();
```

Use locale-appropriate date text and verify the rendered human-readable date after entry; do not assume the input accepted it.

## Cabin searches

Prefer `gflights.py url --cabin <economy|premium|business|first>`. By hand,
open the control whose accessible label starts with `Change seating class`,
then select the exact role `option`: `Economy`, `Premium economy`, `Business`
or `First`. After each change, wait for refreshed result cards and verify the
cabin name in the form.

Treat labels such as `Economy + Premium Economy`, `First Class + Business
Class` or `First Class + Economy` as mixed cabin and keep them verbatim in
`cabin_label`. On long-haul routes they are the norm, not the exception: every
premium-economy card ZRH–GIG was `Economy + Premium Economy` (the hop to the
hub is economy), and no first-class itinerary reached GIG without a business
or economy domestic leg.

## Full itinerary and baggage

When driving the page through the browser-act CLI, result cards are `div[role=link]`
elements, and the selectable outbound/return is the link whose `aria-label`
starts with the price, e.g. `From 1416 euros round trip total. 1 stop flight
with Air France...`. Prefer the visible flight card over an off-screen `Select flight` element. When `Select flight`'s ref is off-screen or not clickable, click the flight card itself (which selected the outbound and then the return in the dated user run). Verify the page header afterwards: a return-direction heading such as `Lisbon to Zürich` means the return list is shown, while `Round trip to …` means the booking page. After the
outbound link click you land on `Choose return`; after the return link click you
land on `/travel/flights/booking`.

1. Select an outbound through the accessible result link ending in `Select flight`. Its accessible name carries the total duration; parse that duration and discard the link before clicking when it breaches the contract.
2. On `Choose return`, parse every `Select flight` link again, filter by the return-duration cap, then choose the lowest-priced valid return. Treat an empty filtered set as a rejected outbound rather than relaxing the cap. For an explicitly selected strict under-20-hour cap, accept `< 1200` minutes and reject `>= 1200`.
3. Wait for `/travel/flights/booking`, then for `Lowest total price`, `Booking options`, and a baggage line. The booking route can render the selected flights before provider cards arrive, so poll and re-read rather than saving the first shell.
4. Record the provider quote and exact baggage wording, for example `1st checked bag available for a fee` or `No checked bags`. In some locations the page says `Booking isn't supported yet in your location` and lists no providers; the bag line still shows, and the seller must be reached directly (`airline-direct.md`, or the OTA named in `Bag fee info isn't available when booking with <OTA>`). This completed-itinerary text overrides assumptions made from the result list. If the page says the previous price changed, use the new completed total everywhere the option is ranked.
5. Expand `View options` when it exposes branded families such as Basic, Standard, Flex, or Latitude. Capture each relevant family price and baggage allowance, then compare `base fare + explicit first-bag fee` with the cheapest family that includes a bag; recommend the lower compliant total.
6. If `View options` is absent, off-screen, or exposes no families when clicked, go to the airline's own booking engine (`airline-direct.md`) instead of assuming Google exposes branded fares. Keep the bag fee-required or unverified; do not infer an included bag.
7. A bag price shown as a range with a zero lower bound (e.g. `1st checked bag: CHF 0–104`) is `baggage: "unverified"`: neither included nor a proven fee. Reprice in the airline's own fare families (`airline-direct.md`) before any bag-inclusive total is ranked.

## One-way and multi-city searches

Open them with `gflights.py url` (one leg, or legs that do not reverse each
other). If a page shows the form but no result count, click the visible
`Search` button once, wait again, and only then classify the query as
populated or unavailable. A route form or empty `Search results` heading is not
evidence that no fare exists; `No results returned.` after an executed search
is (it happened for a three-leg business multi-city ZRH–LIS–GIG–ZRH).

Distinguish in-window results from teasers: the price grid header `from €X` and a card like `Travel Oct 4 – 12 for €819` describe OTHER date windows, not the queried contract. Only cards inside the results headings for the exact entered dates count as exact-date evidence.

For multi-city results, the first card price is for the **entire trip**, but it is still only a first-leg choice: a row recorded from it has `return not selected` until you select every later leg. Enforce the duration cap on each separately flown journey, and wait for the final booking page before evaluating price or baggage. If the structure never returns a populated fare after an executed search, record it as “no published fare returned” rather than converting the constituent headline cards into a synthetic through fare.

Several airports on one end (`BSL+GVA+MXP+MUC+FRA-GIG@…`) return one list with each
card's own departure airport; `parse` reports it in `from`.

## Batch collection

`gflights.py sweep` is the batch path with BrowserAct; by hand, add one row per
populated page with `run_log.py add` as soon as it is read (the cheapest
relevant cards as `list` rows, or an attempt row when the page did not
populate). `run_log.py coverage` then shows which comparisons are still open;
revisit shortlisted itineraries one by one to select the return and qualify
baggage.

A page that never showed a priced card may be retried once with a longer wait.
A page that showed a bot check, CAPTCHA, `unusual traffic`, HTTP 403/429 or a
redirect to `google.com/sorry` is a challenge: follow `browser-engines.md` and
do not retry it.
