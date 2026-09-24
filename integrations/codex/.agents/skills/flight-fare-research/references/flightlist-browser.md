# FlightList browser interaction (flightlist.io)

FlightList is a Kiwi-backed discovery source for broad date-range scans.
Its jQuery daterangepicker supports different interaction paths by environment;
verify committed dates rather than assuming one event method always works.

## Airport selection

Choose the `.eac-item` containing the exact `(IATA)` code, never the first
suggestion. Verify `#from-data` and `#to-data` equal `airport:<IATA>` before
searching. If suggestions do not appear after a bounded wait, delete and retype
the last character once; if still absent, record failure instead of guessing.

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

## Browser-act CLI note

This file assumes browser-act runs against the live browser. If the CLI and the
browser disagree (CLI run as root does not see the chrome-user-owned browser),
follow the environment and session-reuse section in
`references/browser-act-support.md` — run the CLI as the OS user that owns
the Chrome processes with matching HOME and display; setting HOME alone does
not change daemon ownership.
