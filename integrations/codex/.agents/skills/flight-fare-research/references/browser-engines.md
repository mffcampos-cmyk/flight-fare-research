# Browser engines, pacing and bot walls

Flight sites judge the browser as well as the request. A real person's browser,
used at a person's pace, is blocked least. This file chooses the engine, sets
the pace, and says what to do when a site challenges you.

## Choose the engine (highest rung available)

| Rung | Engine | How to tell it is available | `--engine` name |
|---|---|---|---|
| 1 | Claude in Chrome (the user's own Chrome) | `mcp__claude-in-chrome__*` tools; load the host's browser skill first | `claude-in-chrome` |
| 1 | Claude desktop built-in browser | `mcp__Claude_Browser__*` or `mcp__remote-devices__Claude_Browser__*` tools | `builtin-browser` |
| 1 | Cowork browser | Cowork's navigate / find / read_page / javascript tools | `cowork` |
| 1 | browser-act attached to the user's running Chrome | browser-act's real-Chrome mode (see its own skill) | `browser-act-chrome` |
| 2 | browser-act managed browser | `command -v browser-act`; one persistent named browser | `browser-act` |
| 3 | Host headless browser | Hermes `browser_exec`, Playwright, other headless tools | `headless-<tool>` |

Use the highest rung the host offers. Record the engine on every ledger probe
(`source_ledger.py record … --engine NAME`) and every run row (`"engine"`).
A block on a lower rung says nothing about a higher one: a source blocked on
rung 2 or 3 may get one probe on rung 1 when rung 1 is available.

Install nothing mid-search to change engines. If no browser exists at all, see
the fallback in `source-health.md`.

## Pace like a person

- One site at a time per session, one tab per site.
- Prefer documented deep links over refilling a form; fill a form once, then
  change one field per search.
- Let each page settle and read it before the next action; leave about 10–20
  seconds between searches on the same site.
- Decline optional cookies once per site and keep the session, so consent is
  not asked again.
- Spread large batches (many date pairs or cabins) across the source families
  the ledger marks `ok`, rather than running them all on one site.
- Read results with one page-text read (for example `document.querySelector('main').innerText`)
  instead of many screenshots.

## When a site challenges you

A **challenge** is a CAPTCHA, press-and-hold check, "unusual traffic" or
"are you a robot" page, bot-help redirect, HTTP 403/429, or an empty page where
results should be.

1. Stop working that site for this run.
2. **The user is watching, and this is their own visible browser (rung 1):**
   you may ask them to complete the check themselves, then continue. Their
   action, not yours, clears it.
3. **Otherwise** (unattended, or rung 2 or 3): record it and move on:
   - `source_ledger.py record <id> blocked --engine <name> --evidence "<what the page said>"`
   - `run_log.py add` an attempt row with `"outcome": "blocked"`
4. Continue with the next source family. Name the blocked source in the report.

The only ways past a challenge are the user's own hands, an official API with
configured credentials, or another source. The skill uses the browser exactly
as the host configured it and leaves its anti-detection features off: no CAPTCHA
solving, no proxy or TLS rotation, no stealth or fingerprint changes, no
imported cookies or sessions, no private or reverse-engineered APIs. This holds
even when the user asks for "whatever it takes": the site's controls are the
site's to waive, and an evaded block is not evidence anyone could book.

## browser-act notes

- Load browser-act's own skill (or run its `get-skills` command) for current
  command names; they change between versions. This file records only
  fare-specific lessons.
- Keep one persistent named browser and reuse it across runs, so consent and
  cookies survive. Open your own uniquely named session on that browser; a
  session is a handle, not a durable object, and may need reopening. Run
  `state` after attaching and re-check form values before searching.
- Never operate a session another conversation created.
- If the CLI cannot see a browser that is clearly running, the CLI and the
  browser are using different OS users or data directories. Run the CLI as the
  user that owns the browser processes, with that user's `HOME` and display.
- Parallel sessions on one browser share cookies, which is useful for side-by-
  side cross-checks on different sites.
- Close sessions you opened when the run ends.

## Running the recipe snippets

Per-source recipes write page code as plain JavaScript ("run in page") and name
keyboard and text actions generically. Map them to the engine:

| Recipe action | Claude in Chrome / built-in / Cowork | browser-act | Headless (CDP / Playwright) |
|---|---|---|---|
| Run in page | the JavaScript tool | `eval` | `Runtime.evaluate` / `page.evaluate` |
| Type into the focused field | the type or form-input tool | `input --selector` | `Input.insertText` / `page.keyboard.type` |
| Press a key with a real key code | the key-press tool | `keys` | `Input.dispatchKeyEvent` with `windowsVirtualKeyCode` |
| List controls by role and name | read-page / find tools | `state` | `Accessibility.getFullAXTree` |

After any reflow or viewport change, take a fresh screenshot before a
coordinate click, and prefer DOM-scoped lookups to coordinates.

## Date pickers

- Google Flights: focus the active calendar input and insert the locale date
  text, then Enter (`google-flights-browser.md`).
- FlightList: calendar clicks, or the daterangepicker instance with `Date`
  objects; verify both pickers (`flightlist-browser.md`).
- eDreams: readonly inputs; click the day cell inside the right month
  (`edreams-browser.md`).
- ITA Matrix: native value setter plus input/change events
  (`ita-matrix-browser.md`).

Whatever the method, read back the committed dates, then confirm the populated
results repeat them.
