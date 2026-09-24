# ITA Matrix Browser Cross-Check

Use ITA Matrix as an independent live fare cross-check after Google Flights or another bookable source has produced a shortlist. Matrix is useful for fare and schedule corroboration, but it is not a booking provider and often does not expose checked-bag inclusion.

## Exact-date search

1. Open `https://matrix.itasoftware.com/search` and choose the exact origin and destination suggestions by role `option` plus IATA code. Use the city-wide destination only when the contract allows all airports.
2. Set departure and return dates, traveler count, stops, and cabin explicitly. Verify the rendered heading repeats the route and dates after submission.
3. Submit with the page's `Search` button and wait until the `Complete Trips` table contains actual prices and itinerary rows. Do not treat the initial `Choose your flights` shell as a result.
4. Save the displayed currency, total fare, airlines, both directions, local times, stops, and duration. Matrix may default to the sales-city currency rather than the comparison currency; preserve what it displays instead of silently converting.
5. Keep checked baggage **unverified** unless Matrix explicitly displays an allowance. Use the completed booking page from the primary source to qualify baggage.

## Angular date inputs

The Angular Material date-range inputs can append text or move focus unexpectedly when driven with ordinary typing. Set both values through the native input setter and dispatch the framework events, then re-read the visible values before searching:

```python
js("""(() => {
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  const depart = document.querySelector('input[placeholder="Start date"]');
  const ret = document.querySelector('input[placeholder="End date"]');
  set.call(depart, '12/23/2026');
  depart.dispatchEvent(new Event('input', {bubbles: true}));
  depart.dispatchEvent(new Event('change', {bubbles: true}));
  set.call(ret, '01/13/2027');
  ret.dispatchEvent(new Event('input', {bubbles: true}));
  ret.dispatchEvent(new Event('change', {bubbles: true}));
  ret.dispatchEvent(new Event('blur', {bubbles: true}));
  return [depart.value, ret.value];
})()""")
```

Use the UI's locale format and replace the example dates.

## Cabin selector

Open `mat-select[formcontrolname="cabin"]`, then select the exact accessible option. Observed labels include `Premium Economy` and `Business class or higher`; verify the current labels rather than assuming them.

## Session pitfall

Submit through the search form so Matrix creates its server-side solution session. A hand-built `/flights?search=<base64-json>` URL without the generated solution fields can load an empty results shell instead of executing the search.