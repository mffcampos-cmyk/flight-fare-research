# Safety and provenance

This project performs **research only**. It does not book flights, handle
payments, complete checkout, store credentials, or guarantee observed prices.
This document states the boundary and the evidence rules; the skill
(`skill/SKILL.md`) and `run_log.py` enforce them.

## Browsers and challenges

- **Engine ladder.** BrowserAct first: a hosted stealth browser
  (`browser-act-stealth`, needs the free BrowserAct login), then BrowserAct's
  local Chromium (`browser-act`), then the user's own browser (`chrome-direct`,
  Claude in Chrome, the desktop built-in browser, Cowork's browser), then a
  host headless tool. `browseract.py status` finds the highest rung each
  session and, when no login exists, tells the user how to create the free
  account; the agent never creates it and never pastes a key into chat.
  Record the engine with every source state and every row.
- **BrowserAct's free features are the user's own configured tooling.** The
  skill uses stealth browsers, parallel sessions, `solve-captcha`,
  `stealth-extract` and `remote-assist` as the installed CLI offers them. It
  does not buy proxies or browsers (any `purchase_url` or `renewal_url` flow
  goes to the user), does not import anyone else's sessions, and does not use
  private or reverse-engineered APIs. Automated access can be against a
  site's terms: the user runs the skill on their own account and
  responsibility, and the report names every site that challenged the run.
- **Pace like a person, work in parallel.** Every source family runs in its
  own session at once; on one site, the ledger's `sessions_per_site` and
  `pace_seconds`; deep links over refilled forms; optional cookies declined
  once per site and the session kept; Google's daily allowance spent on
  confirmation, not discovery. Speed comes from parallel sessions and fewer,
  wider searches (one FlightList range search per destination), never from
  hammering a site.
- **Challenges.** On a CAPTCHA, press-and-hold check, "unusual traffic" page,
  bot page or HTTP 403/429 in the network log: with a login, `solve-captcha`
  once, then `remote-assist` when a human is reachable (the link goes to the
  user, the agent continues in the same session); a user watching their own
  browser may clear it; otherwise the source is recorded as blocked (with the
  engine and the outcome) and the run moves on. A site that stayed blocked is
  never retried in the same run.
- **Consent banners** are normal interaction: decline optional cookies.

## Lead or qualified

`run_log.py` computes each observation's status; the agent never asserts it.

| Status | Meaning |
|---|---|
| `qualified` | Every leg selected, each within the journey-time limit and the stop, time-window and airline gates, baggage resolved for the requested bags, every all-in part priced (ground rows for nearby airports), repriced on the seller's page, currency comparable |
| `lead` | Passes the hard gates but has open items, listed as reasons (for example `baggage unverified`, `ground unpriced (BSL)`, `list fare not repriced`, `leg 2 not selected`) |
| `rejected` | Fails a hard gate: over the duration cap, too many stops, outside a time window, an excluded airline, a forbidden self-transfer, wrong cabin, dates or airports, an overnight ground leg where none is allowed |
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

- Stop before passenger details. Never enter card numbers, create accounts
  (the BrowserAct account included) or complete checkout.
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
  `skill/references/discovery.md`, `skill/references/source-ladder.md`
- `skill/references/historical-observations.md` for dated source status
