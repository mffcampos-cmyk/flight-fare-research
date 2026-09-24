# Safety and provenance

This project performs **research only**. It does not book flights, handle
payments, complete checkout, store credentials, or guarantee observed prices.
This document is the source of truth for the capability boundary and the
evidentiary rules; the skill (`skill/SKILL.md`) restates and enforces them.

## Anti-evasion stance

- **No CAPTCHA solving, proxy rotation, stealth fingerprints, or TLS
  rotation.** When a source shows an explicit bot page, CAPTCHA, Cloudflare
  block, HTTP 403, or provider guard, do not install or configure
  anti-detection tooling to recover a fare.
- **One recorded attempt per blocked source per run.** Record the failure
  mode and move on. Repeated retries against a blocked source waste time and
  do not improve evidentiary quality. Use an official API, an airline-direct
  engine, an alternate aggregator, or a user-visible manual path instead.
- **Consent is normal interaction, not evasion.** Google properties present a
  consent page before search; accept/store the consent choice normally (single
  browser, shared cookies). Interacting normally with a consent prompt is
  legitimate use, not circumvention.
- **Do not unofficially reverse-engineer a site's private API** merely to
  inflate source count or recover a fare that is otherwise guarded. Wrapper or
  scraping endpoints require provenance, terms, and freshness checks before
  use.

## Prices are observations, not guarantees

- A search-result price is an **observation** at a retrieval time, not a
  guaranteed fare and not a booking.
- A result card or list-page amount can change at checkout (fare families,
  mandatory fees, price repricing). When a completed page says the price
  changed, replace the list amount with the completed provider total and keep
  the old amount only as a clearly labelled stale observation.
- Do not rank an aggregator teaser above an airline-direct fare until the
  exact itinerary survives checkout repricing.

## No booking, payment, or account secrets

- Do **not** complete a booking or checkout, enter a card number, create an
  account, or accept API secrets. Never render a trip bookable from this tool.
- Never ask for, accept, or print API credentials in chat. Use the configured
  secret store or environment variables, and check only *whether* a credential
  is configured — never its value.
- **No secret storage.** This repo must not accumulate saved passwords,
  session tokens, booking tokens, or checkout handles.
- On a release boundary, confirm no secret, session, or booking tokens are
  present in the working tree before tagging (see
  `docs/manual-release-checklist.md`).

## Baggage states

Classify checked-baggage status on the completed itinerary as exactly one of:

- **included** — the completed itinerary or fare family explicitly includes at
  least one checked piece;
- **fee required** — the page explicitly says the first checked bag costs
  extra;
- **unverified** — no itinerary-level allowance is exposed.

Never label a fare "bag included" from airline norms, cabin expectations, or a
generic policy page. A result list that says optional bag fees apply does not
prove inclusion; the completed itinerary line and booking-provider total are
the evidence.

## Quote states

Distinguish the evidence grade of every recorded price:

- **list** — a headline list fare from a search-result card (no-bag base fare
  common; not completed);
- **completed** — a completed-itinerary provider or airline quote fetched on
  exact dates,
- **repriced** — the current completed provider amount after a booking page
  reprices the fare from an earlier list/repriced value. The pre-reprice amount
  is retained only as a clearly labelled stale observation. In the stored
  evidence, the row's price is the current value and any previous amount is the
  stale one.

A "completed" or "repriced" label requires the exact route, dates, travelers,
cabin, and currency to be reproduced in the completed page.

## Source independence

At least two independent live **source families** are required before a fare
is called corroborated. Two frontends backed by the same inventory or a
redirect chain are not fully independent — disclose the relationship. Wrappers
that re-aggregate another source (e.g. FlightsFinder re-aggregating Google
Flights / KAYAK / Skyscanner / Momondo, SerpAPI wrapping Google Flights) never
count as a separate source family.

Apply the source-independence test (from `skill/references/source-ladder.md`):

1. Did both sources execute the exact route, dates, passengers, cabin, and
   currency?
2. Do they rely on different inventory/search backends?
3. Did both expose a populated itinerary rather than an indexed teaser?
4. Is baggage independently verified or still inferred?
5. Did at least one source reach a completed provider or airline fare?

If any answer is no, state the limitation and lower confidence. When only one
exact-date source remains, say so plainly and downgrade confidence rather than
implying corroboration. Cite only pages actually retrieved, following
`grounded-citations`; indexed deal pages are discovery leads, never
exact-date evidence.

## See also

- `docs/source-support-matrix.md` — current dated support status per source.
- `docs/manual-release-checklist.md` — pre-release confirmation that the
  boundary holds and the tree is clean.
- `skill/references/source-ladder.md` — canonical routing, browser recipes, and
  the source-independence test.