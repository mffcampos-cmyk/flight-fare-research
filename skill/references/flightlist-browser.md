# FlightList browser interaction (flightlist.io)

FlightList is a Kiwi-backed discovery source for broad date-range scans, and
the fastest way to cover a flexible window: one search over a departure range
and a return range lists the cheapest itineraries across every date pair, with
both directions. Its jQuery daterangepicker supports different interaction
paths by environment; verify committed dates rather than assuming one event
method always works.

## Whole window in one search

Set the departure picker to the whole outbound range and the return picker to
the whole return range (instance method below, start and end different), set
`#limit` to `200` and `#sort` to `price`, and search. On 2026-10-09 one such
search (ZRH–GIG, 18–22 Dec × 10–14 Jan) returned 200 itineraries across 15 of
the 25 pairs in 23 seconds; the same pairs had taken 25 Google searches.

Read every card with its hidden segment details (`textContent`, not
`innerText`, so collapsed segments with dates and flight numbers are included):

```js
JSON.stringify([...document.querySelectorAll('li.flight')].map(c => ({
  price: c.querySelector('.price')?.textContent.trim(),
  text: c.textContent.replace(/\s+/g, ' ').trim(),
  book: ([...c.querySelectorAll('a')].find(a => a.href.includes('kiwi.com')) || {}).href || null })))
```

Save that JSON and turn it into rows for the run:

```bash
python3 <skill_dir>/scripts/flightlist.py rows --run <run dir> cards.json \
  | python3 <skill_dir>/scripts/run_log.py add --run <run dir> --row -
```

`rows` keeps the cheapest card within the duration cap for each date pair
(`--top N` for more), plus the cheapest card overall when it breaks the cap and
is cheaper, and prints the pairs no card covered. The 200 cards are the
cheapest 200 of the whole window, so expensive pairs can be missing: search
again with the outbound range narrowed to the missing days, or confirm those
pairs on Google (`gflights.py sweep --pairs …`). Cards that combine unrelated carriers (easyJet + Ryanair + GOL)
are Kiwi combinations: the notes flag them as possible self-transfers, which
the Kiwi fare page confirms.

## From a card to a seller's price: the Kiwi fare page

A card's `Book Flight` link opens `kiwi.com/en/booking/fare-selection/`, which
shows the airline's own fare families for that itinerary with what each
includes and the total with Kiwi's fees, before any passenger detail. For KLM
ZRH–GIG 22 Dec / 12 Jan it showed `Light` CHF 1,555.26 (no checked bag),
`Standard` CHF 1,923.08 (23 kg bag) and `Flex` CHF 2,131.25. That page is a
completed quote: record the cheapest family that includes the requested bags
with `quote_state: "completed"` and `baggage: "included"`. The FlightList card
for the same itinerary, searched with one checked bag, said CHF 1,750.91,
which matched neither family: a FlightList price is never the bag-inclusive
total. Kiwi's own results URLs redirected to the home page in the same run;
enter through `Book Flight`.

## Airport selection

Choose the `.eac-item` containing the exact `(IATA)` code, never the first
suggestion. Verify `#from-data` and `#to-data` equal `airport:<IATA>` before
searching. If suggestions do not appear after a bounded wait, delete and retype
the last character once; if still absent, record failure instead of guessing.

The suggestions come from the easyAutocomplete plugin, which loads data only on
a keyup whose `keyCode` is above 40 (or Backspace). Pasting text, setting
`value`, or inserting text does not trigger it. Neither do synthetic key events
without a key code, for example a CDP `Input.dispatchKeyEvent` that omits
`windowsVirtualKeyCode`. Type real keys, or send each character's virtual key
code (`Z`=90, `R`=82, `H`=72). This was verified on 2026-10-03: with key codes,
`ZRH`/`LIS` resolved to `airport:ZRH`/`airport:LIS`. Without them no suggestion
appeared, which looks like a dead site but is a recipe error. BrowserAct's
`input <index> "ZRH"` types real keys and opened the suggestions (2026-10-08).

## Form settings

Set `#type`, `#class`, `#currency`, `#checkedbags`, `#sort`, `#stops` and
`#connections` explicitly. Use `connections=false` when the contract has
`self_transfer_ok: false`. Set `#duration` as a discovery ceiling only:
FlightList can return a journey equal to the ceiling, so parse every direction
yourself and let `run_log.py` apply the strict or inclusive cap.

## Setting the date range (the working method)

Try normal calendar interaction first: for each exact date, select the day
as both start and end, then Apply. The user-observed Cowork retest on 2026-09-24
confirmed clicks worked; earlier CLI failures are not universal behavior.
When screenshots are unavailable (for example a minimized window), a prior
user run succeeded by dispatching `mousedown` then `mouseup` to the matching
`td.available` inside the calendar for the requested month/year. Scope to the
active picker, re-query the cell after each event pair because cells re-render,
and click Apply in that picker's own container. Use this only for ordinary
calendar interaction, never to bypass a bot challenge. The instance method
below remains a fallback. Verify startDate/endDate for BOTH pickers and the
returned itinerary dates regardless of the interaction method.

1. Open the picker by clicking the range field (`#deprange` / `#retrange`).
2. Get the picker instance and set dates with **Date objects** (string formats
   like `'2026-10-01'` return `Invalid date`):

   ```js
   const dp = jQuery('#deprange').data('daterangepicker');
   dp.setStartDate(new Date(2026, 9, 1));  // month is 0-indexed
   dp.setEndDate(new Date(2026, 9, 10));
   ```

3. Click that instance's **Apply** button (`dp.container.find('.applyBtn').click()`).
   The visible span can remain stale even after Apply. Re-read each instance's
   `startDate` and `endDate`, then require the populated results to match the
   intended dates. For an exact-date round trip, set departure start=end to
   the outbound date and return start=end to the return date. Setting both
   pickers to the whole trip window permits mismatched trip lengths.

## Two pickers in the DOM

The page mounts a separate `.daterangepicker` element for departure and for
return. `document.querySelector('.daterangepicker')` returns the FIRST (departure)
— so target the intended picker's own `container` for Apply, rather than relying
on global DOM order. Re-read both picker instances and returned dates.

## Reading results

After clicking Search the URL does not change (AJAX). Wait for the page to
stabilize, then extract from `.flight` cards. Each card's price is in a
`.price`-class element; the itinerary text (dates, airline, flight numbers,
segments) is in the card body. Aggregate the full list programmatically rather
than scanning the rendered markdown.

Parse every card's TWO duration values — the first `(\d+)h\s*(\d+)m` occurrence
is the outbound elapsed, the second is the return elapsed — then apply the
contract cap as `out_min < 1200 and ret_min < 1200` before ranking. The list's
cheapest rows frequently fail the return cap on long-haul routes (a cheap
outbound under the cap can pair with a 29h40m return), so a raw price sort is
not a qualified ranking. Skip cards whose price is missing rather than guessing.

## Submitting and expanding

Click `#submit` and wait for populated `li.flight` cards. The URL does not
encode the search, so save the query settings, retrieval time and raw card text
as you go. Expand a card via `a[data-toggle="collapse"]` to see airlines, flight
numbers, segment times, layovers, airport changes (sometimes only visible
expanded) and the `Book Flight` link.

## Limits

- FlightList hands booking off to Kiwi and uses Kiwi-hosted assets: it is one
  Kiwi-backed discovery family, never an airline-direct quote.
- The checked-bag selector and Kiwi's `searchBags` parameter filter candidates;
  they do not prove the displayed total includes the bag. Rows from FlightList
  are `quote_state: "list"` with `baggage: "unverified"` until repriced.
- A result is bookable only after the Kiwi handoff or the airline site
  completes it.

Engine-specific notes (key events, eval, sessions): `browser-engines.md`.
