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
| 1 | BrowserAct `chrome-direct` (drives the user's running Chrome) | `command -v browser-act`; see "BrowserAct" below | `browser-act-chrome` |
| 2 | BrowserAct `chrome` (its own Chromium, optionally with the user's Chrome profile imported) | `command -v browser-act`; one persistent named browser | `browser-act` |
| 3 | Host headless browser | Hermes `browser_exec`, Playwright, other headless tools | `headless-<tool>` |

Use the highest rung the host offers. Record the engine on every ledger probe
(`source_ledger.py record … --engine NAME`) and every run row (`"engine"`).
A block on a lower rung says nothing about a higher one: a source blocked on
rung 2 or 3 may get one probe on rung 1 when rung 1 is available.

Install nothing mid-search to change engines. If no browser exists at all, see
the fallback in `source-health.md`.

## Pace like a person, work in parallel

- One search at a time on each site, with about 10–20 seconds between searches
  there. On Google Flights, 12 seconds between searches ran 80+ searches without
  a challenge (2026-10-08); the next day, after about 90 searches in 24 hours,
  Google answered 429 and `google.com/sorry`. Fewer searches beat faster ones:
  discover with one FlightList range search, confirm the cheapest pairs only.
- **Different sites in parallel.** Run each site in its own session or tab at
  the same time: Google sweeping in one, TAP, eDreams, Kiwi or ITA Matrix in
  another. This adds no load to any one site; in the ZRH–GIG run, eDreams,
  FlightList, ITA Matrix and TAP were probed and repriced in a second tab while
  the 50-search Google sweep ran. With BrowserAct, open a second session on the same browser
  (`browser-act --session ffr-aux browser open <id> <url>`); it gets its own tab.
  When the host has subagents, give each one its own session and source family.
- Prefer documented deep links over refilling a form (`gflights.py url`, TAP's
  deep link); fill a form once, then change one field per search.
- Wait for the page's own ready signal (a priced card, a result count), not a
  fixed delay; read results with one page-text read (`get markdown`, or
  `document.querySelector('main').innerText`) instead of screenshots.
- Decline optional cookies once per site and keep the session.
- Spread large batches across the source families the ledger marks `ok`.

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
cookies or sessions other than the user's own (imported only with their
confirmation), no private or reverse-engineered APIs. This holds
even when the user asks for "whatever it takes": the site's controls are the
site's to waive, and an evaded block is not evidence anyone could book.

## BrowserAct (no login needed)

[BrowserAct](https://github.com/browser-act/skills) gives agents a local browser
CLI. Its `chrome` and `chrome-direct` modes are free and need no account; the
skill uses only those.

**Install once, with the user's OK** (it downloads a package):

1. Add BrowserAct's entry skill to the agent's skills folder: the `browser-act`
   folder from `https://github.com/browser-act/skills/tree/main/browser-act`
   (Claude Code: `~/.claude/skills/browser-act/`).
2. Install the CLI: `uv tool install browser-act-cli --python 3.12`, then
   `browser-act --version`. If the command is missing, add `uv tool dir` to `PATH`.

**Every session:**

1. Run `browser-act get-skills core --skill-version 2.0.2` and read all of it;
   it lists the browsers, live sessions and current commands for the installed
   version.
2. Pick the browser by its description in `browser list`. With none suitable,
   propose one and wait for the user's yes before `browser create` (BrowserAct
   requires a separate confirmation for every browser it creates):
   - `chrome-direct`: drives the user's running Chrome with their cookies and
     extensions (rung 1). It occupies that Chrome while it runs, and the user
     sees every page, so they can clear a check themselves.
   - `chrome`: a separate Chromium (rung 2). Name it for the job, for example
     `flight-research`, keep it across runs so consent choices persist, and open
     it with `--headed` when a display exists: headless Chromium is the easiest
     to flag.
3. Open your own session: `browser-act --session <name> browser open <id> <url>`.
   Work in the loop *state → act → `wait stable` → state*. Indices from `state`
   are valid only until the page changes; never reuse old numbers, and never
   operate a session you did not open.
4. Read results with `get markdown` (or `eval` for a recipe's page code) and
   add rows to `run_log.py` as you go. `scripts/gflights.py sweep --session <your session>`
   drives a whole Google Flights batch through the session you opened.
5. A site can block silently: the page stays on a spinner while its own search
   requests fail. `browser-act --session <name> network requests --status 403`
   (or 429) shows them; that is a block (record it), not a slow page.
6. Close your sessions at the end: `browser-act session close <name>`.

`get-skills` also describes `stealth-extract`, `solve-captcha`, `remote-assist`,
stealth browsers and proxies. They need a BrowserAct login or a paid plan, and
the skill does not use them; follow "When a site challenges you" instead.

## Running the recipe snippets

Per-source recipes write page code as plain JavaScript ("run in page") and name
keyboard and text actions generically. Map them to the engine:

| Recipe action | Claude in Chrome / built-in / Cowork | browser-act | Headless (CDP / Playwright) |
|---|---|---|---|
| Run in page | the JavaScript tool | `eval` | `Runtime.evaluate` / `page.evaluate` |
| Type into a field | the type or form-input tool | `input <N> "text"` or `input --selector <css> --text "text"` | `Input.insertText` / `page.keyboard.type` |
| Press a key with a real key code | the key-press tool | `keys "Enter"` | `Input.dispatchKeyEvent` with `windowsVirtualKeyCode` |
| List controls by role and name | read-page / find tools | `state` (indexed `[N]` list) | `Accessibility.getFullAXTree` |
| Click a control | the click tool | `click <N>` or `click --selector <css>` | `page.click` |
| Read the page as text | read-page / get-page-text tools | `get markdown` | `page.innerText` |
| Wait for results | wait / screenshot | `wait stable` | `page.waitForLoadState` |

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
