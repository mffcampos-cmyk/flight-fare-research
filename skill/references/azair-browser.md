# AZair browser interaction (azair.eu)

Verified 2026-09-20: AZair loads and renders (no bot wall, no CAPTCHA) in a
plain headless Chrome session. Use it for LOW-COST carrier route discovery only.

## Scope

AZair combines low-cost carriers (easyJet, Ryanair, Wizz, Vueling, AirAsia,
Jet2, flydubai, etc. — 62 airlines listed) across Europe, the Mediterranean and
Asia to find cheap multi-carrier routings between many airports at once. It does
NOT cover full-service long-haul networks (KLM/AF/Lufthansa/Swiss/TAP interline),
so it cannot answer a long-haul route like ZRH→RIO on its own — treat it as a
route-hack discovery complement for the European feeder/LCC leg.

## Use cases

- Splitting a long-haul trip: find cheap LCC feeder flights (home city → a
  long-haul hub) and cheap LCC alternatives for positioning legs.
- Comparing many regional airports simultaneously (a grid, not one pair).
- Applying a `duration` ceiling to LCC routings.

## Limits

- No baggage qualification at the search level; LCC baggage is per-carrier
  add-on and must be priced at the airline checkout.
- Results are headline list fares, not completed quotes; every candidate must be
  repriced on the airline or aggregator site for the exact date pair.
- Coverage is LCC-focused; absence of a full-service airline in results is a
  scope limit, not evidence it is cheaper.

Keep AZair in the "blocked/partial" pragmatic tier: usable, quick to click
through, but rarely the final booking source and never authoritative for
baggage.
