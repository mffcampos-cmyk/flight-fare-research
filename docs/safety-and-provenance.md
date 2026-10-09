# Safety and provenance

This project performs **research only**. It does not book flights, handle
payments, complete checkout, store credentials, or guarantee observed prices.
This document states the boundary and the evidence rules; the skill
(`skill/SKILL.md`) and `run_log.py` enforce them.

## Browsers and challenges

- **Engine ladder.** Prefer the user's own browser (Claude in Chrome, the Claude
  desktop built-in browser, Cowork's browser), then a persistent browser-act
  browser, then a headless browser. Record the engine with every source state.
- **Pace like a person.** One search at a time on each site with pauses between
  searches (different sites may run in parallel sessions), deep links over
  refilled forms, optional cookies declined once per site and the session kept.
  Speed comes from fewer searches (one FlightList range search for a flexible
  window) and from reading the page's own ready signal, never from evading a
  site's limits.
- **Challenges.** On a CAPTCHA, press-and-hold check, "unusual traffic" page,
  bot page or HTTP 403/429, stop that site for the run. A user watching their
  own browser may complete the check themselves; otherwise record the source as
  blocked (with the engine) and move on.
- **Never:** automated CAPTCHA solving, proxy or TLS rotation, stealth or
  fingerprint changes, imported cookies or sessions, or private and
  reverse-engineered APIs, even when the user asks. A site's controls are the
  site's to waive, and a fare reached by evading them is not evidence anyone
  could book.
- **Consent banners** are normal interaction: decline optional cookies.

## Lead or qualified

`run_log.py` computes each observation's status; the agent never asserts it.

| Status | Meaning |
|---|---|
| `qualified` | Both directions selected, each within the journey-time limit, baggage resolved for the requested bags, every all-in part priced, repriced on the seller's page, currency comparable |
| `lead` | Passes the hard gates but has open items, listed as reasons (for example `baggage unverified`, `positioning unpriced`, `list fare not repriced`) |
| `rejected` | Fails a hard gate: over the duration cap, a forbidden self-transfer, wrong cabin, dates or airports, positioning not allowed |
| `superseded` | Replaced by a later reprice; kept as a stale observation |
| `attempt` | A blocked, empty or broken page; no price |

Only qualified options are recommended. Leads appear under "Leads (not
verified)" with their reasons. The run is complete only when `run_log.py check`
exits 0; otherwise the report ends with `Incomplete:` and the open items.

Quote states on each ticket: `list` (a search-result price), `completed` (the
seller's completed price page on the exact itinerary), `repriced` (a completed
price that replaced an earlier amount).

## Baggage

Per ticket, exactly one of:

- **included:** the completed itinerary or fare family states at least one
  checked piece;
- **fee required:** the page states the first checked bag costs extra (with the
  fee recorded);
- **unverified:** no itinerary-level allowance, or a range starting at zero
  (`CHF 0–104`).

Airline norms, cabin expectations and generic policy pages never make a bag
"included". Each separate ticket needs its own bag line.

## No booking, payment or secrets

- Stop before passenger details. Never enter card numbers, create accounts or
  complete checkout.
- Never ask for, accept or print credentials in chat; check only whether one is
  configured in the environment or secret store.
- The repository must not hold passwords, session tokens, booking tokens or
  checkout handles; CI scans for them.

## Source independence

At least two source families are attempted per cabin. Frontends that share
inventory or a redirect chain are one family (FlightList and Kiwi; Opodo and
eDreams; Momondo and KAYAK; any Google Flights wrapper such as SerpAPI or
FlightsFinder). Before calling a price corroborated, check: both sources ran the
exact search; they use different backends; both showed populated itineraries;
baggage is verified, not inferred; at least one reached a completed seller
price. If any answer is no, say so and lower confidence.

## Citations

Cite only pages actually retrieved: source name, URL (or connector query),
retrieval timestamp with timezone, and the exact claim supported. Keep current
observations, historical reports, policy pages and unvisited links apart. A
blocked page or an indexed deal snippet is never fare evidence.

## See also

- `docs/manual-release-checklist.md`
- `skill/references/browser-engines.md`, `skill/references/qualification.md`,
  `skill/references/source-ladder.md`
- `skill/references/historical-observations.md` for dated source status
