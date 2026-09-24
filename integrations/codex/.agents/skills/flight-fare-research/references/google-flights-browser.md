# Google Flights Browser Recipe

Use this only when the live Google Flights UI is the selected source. Re-read the rendered controls because labels and DOM structure can change.

## Exact-date search

**Optional fast path (`?q=` link):** navigate to the URL-encoded natural-language link, e.g. `https://www.google.com/travel/flights?q=Flights%20from%20ZRH%20to%20LIS%20on%202026-11-05%20through%202026-11-12%20economy&curr=CHF&hl=en`, replacing route, dates, cabin, and currency from the contract. This is a navigation hint, not a stable API or verified quote. After it loads, verify in the form: round-trip mode, airports, both dates, traveler count, cabin, currency, and populated exact-date results. If the link parses wrong, shows teasers instead of the exact window, or yields no populated results, use the full form below. The dated user report that produced this pattern is preserved in `historical-observations.md`.

1. Otherwise open `https://www.google.com/travel/flights?hl=en&curr=<CURRENCY>` and decline optional cookies (`Reject all` or equivalent; a consent screen is not a bot block).
2. Inventory controls with `Accessibility.getFullAXTree`; match route controls by `aria-label` and airport suggestions by role `option` plus the exact IATA code.
3. Set origin and destination, then open the visible departure/return field.
4. Google may render duplicate date inputs: one in the search form and one in the open calendar. Identify the active calendar input from its non-zero bounding rectangle or focus it directly with JavaScript. Insert the date with CDP `Input.insertText`, press Enter, and click the `Done. Search for round trip flights...` button. Avoid coordinate clicks near the top-right header because they can hit Sign in rather than the calendar.
5. Click Search and verify the `/travel/flights/search` page repeats the requested dates and route.
6. Wait until `document.body.innerText` contains a result count and populated fare cards; save the query URL and rendered text.

With browser-act, a verified alternative is `input --selector` on the active
calendar's unique input followed by `keys Enter` for each date. Inspect the
current DOM to identify that input (do not persist transient `aria-describedby`
values from a prior run). Then click the current `Done. Search...` button,
re-read state, and click Search. Never chain selectors across a re-render
without checking the new state.

Representative CDP control probes (only when the host exposes CDP helpers):

```python
nodes = cdp('Accessibility.getFullAXTree')['nodes']
# Filter nodes by role/name before printing; the full tree is too large.

js("document.querySelectorAll('input[aria-label=\"Return\"]')[1].focus()")
cdp('Input.insertText', text='01/12/2027')
cdp('Input.dispatchKeyEvent', type='keyDown', key='Enter', code='Enter', windowsVirtualKeyCode=13)
cdp('Input.dispatchKeyEvent', type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13)
```

Use locale-appropriate date text and verify the rendered human-readable date after entry; do not assume the input accepted it.

## Cabin searches

Open the control whose accessible label starts with `Change seating class`, then select the exact role `option`: `Economy`, `Premium economy`, or `Business`. After each change, wait for refreshed result cards and verify the cabin name in the form.

Treat labels such as `Economy + Premium Economy`, `Premium Economy + Economy`, or `Business Class + Economy` as mixed cabin. Preserve the label in output.

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
4. Record the provider quote and exact baggage wording, for example `1st checked bag available for a fee`. This completed-itinerary text overrides assumptions made from the result list. If the page says the previous price changed, use the new completed total everywhere the option is ranked.
5. Expand `View options` when it exposes branded families such as Basic, Standard, Flex, or Latitude. Capture each relevant family price and baggage allowance, then compare `base fare + explicit first-bag fee` with the cheapest family that includes a bag; recommend the lower compliant total.
6. If `View options` is absent, off-screen, or exposes no families when clicked, go to the airline's own booking engine (`airline-direct.md`) instead of assuming Google exposes branded fares. Keep the bag fee-required or unverified; do not infer an included bag.
7. A bag price shown as a range with a zero lower bound (e.g. `1st checked bag: CHF 0–104`) means the allowance and exact amount are unverified — a zero lower bound is neither "included" nor a proven mandatory fee (issue 2.4). Reprice in the airline's own fare families (`airline-direct.md`) before any bag-inclusive total is ranked.

## One-way and multi-city searches

A generated one-way or multi-city `/travel/flights/search?tfs=...` URL can open a populated form without executing the search. After navigation, test for a real result count; when it is absent, click the visible `Search` button, wait again, and only then classify the query as populated or unavailable. A route form or empty `Search results` heading is not evidence that no fare exists.

Distinguish in-window results from teasers: the price grid header `from €X` and a card like `Travel Oct 4 – 12 for €819` describe OTHER date windows, not the queried contract. Only cards inside `Top departing flights` / the results list for the exact entered dates count as exact-date evidence.

For multi-city results, the first card price is for the **entire trip**, but it is still only a first-leg choice. Select every subsequent leg, enforce the duration cap on each separately flown journey, and wait for the final booking page before evaluating price or baggage. If the structure never returns a populated fare after an executed search, record it as “no published fare returned” rather than converting the constituent headline cards into a synthetic through fare.

## Batch collection

For multiple airports/cabins, append each populated page to a JSON or CSV file with route, cabin, URL, raw rendered text, and retrieval time. Parse minima and counts programmatically, then revisit shortlisted itineraries individually for return choice and baggage qualification. Do not depend on opaque `tfs` bytes as a permanent interface; if reusing a generated URL as a batch optimization, verify every outcome in the visible form before accepting its data.

Persist each row before advancing so a timeout does not discard the batch. After the run, compare the collected and populated counts with the expected Cartesian product, retry only loading/incomplete rows without a real result count using a longer bounded wait; never retry rows with an explicit bot page, CAPTCHA, HTTP 403 or provider guard, then rewrite those rows in place while preserving successful observations. This recovery pattern avoids rerunning hundreds of completed searches because one browser session stalled.
