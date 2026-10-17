# Browser engines, sessions, pacing and challenges

Flight sites judge the browser as well as the request. BrowserAct's browsers
are the first choice: its stealth browsers are built for sites that block
automation, its local Chromium keeps a persistent profile, and both run many
sessions in parallel. The user's own browser is the fallback. This file
chooses the engine, checks the BrowserAct login, sets the pace, and says what
to do when a site challenges you.

## The ladder (highest rung available)

| Rung | Engine | Needs | `--engine` name |
|---|---|---|---|
| 1 | BrowserAct stealth browser: hosted, headless, fingerprint masking, up to 5 on the free account, optional proxy | CLI installed and a BrowserAct login | `browser-act-stealth` |
| 2 | BrowserAct `chrome`: local Chromium, one persistent named browser, headed when a display exists | CLI installed | `browser-act` |
| 3 | The user's own browser: BrowserAct `chrome-direct` (their running Chrome), Claude in Chrome (`mcp__claude-in-chrome__*`), the desktop built-in browser (`mcp__Claude_Browser__*`), Cowork's browser | the host, or a running Chrome | `browser-act-chrome`, `claude-in-chrome`, `builtin-browser`, `cowork` |
| 4 | Host headless tool (Playwright, Hermes `browser_exec`) | the host | `headless-<tool>` |

Use the highest rung for every source, except that a source the ledger marks
`ok` only on a lower rung keeps that rung. Record the engine on every ledger
probe (`source_ledger.py record … --engine NAME`) and every run row. A block
on rung 1 allows one probe on rung 3 (the user's own browser, with their
cookies): `source_ledger.py order --engine <name>` lists what may be re-probed.

## Every session: `browseract.py status`

```bash
python3 <skill_dir>/scripts/browseract.py status            # the two intake lines
python3 <skill_dir>/scripts/browseract.py status --json     # for scripts
python3 <skill_dir>/scripts/browseract.py engine --host-tools claude-in-chrome,builtin-browser
```

The JSON has `installed`, `version`, `api_key` (`env`, `config`, `cli` or
null), `logged_in`, `stealth_quota`, `chrome_running`, `engine` and
`checked_at`. The result is cached for 24 hours (`--fresh` to redo it).
Detection order: `browser-act --version`; `BROWSERACT_API_KEY`; the CLI
config's `api_key`; `browser-act auth poll`; finally a key-gated read-only
command whose "API key required" refusal is read.

The intake's browser line (item 18) is the text `status` prints:

- **Not installed:** *BrowserAct CLI: not installed. With your OK I run
  `uv tool install browser-act-cli --python 3.12` (it downloads a package);
  until then the next rung of the ladder is used.*
- **Installed, logged in:** *BrowserAct account: logged in (key from env);
  human handoff via remote-assist is available on a challenge.*
- **Installed, not logged in:** *BrowserAct account: not logged in. The free
  account unlocks stealth browsers, CAPTCHA solving and human handoff. Run
  `browser-act auth login`, open the URL it prints to create the account, then
  `browser-act auth poll`. Continuing on the local `chrome` browser meanwhile.*

The agent never creates the account, never pastes a key into chat, and runs
`browser-act auth set <key>` only with a key the user supplies out of band. An
unattended run never stalls on the account line: the default is to continue
on rung 2.

## Browsers and sessions

Read `browser-act get-skills core` once per session for the installed
version's exact commands; the recipes name the commands as of CLI 1.4.3.

- **Stealth (rung 1).** One persistent stealth browser named `ffr-stealth`,
  created on first use with `browser create --type stealth --name ffr-stealth
  --desc "flight research"` (BrowserAct asks the user to confirm every browser
  it creates; say why). Discovery sweeps may add `--private true` browsers up
  to the quota. Proxy options (`--dynamic-proxy`, `--custom-proxy`) are passed
  only when the user has configured one (`FFR_PROXY`, or a proxy they name);
  the agent never opens a purchase, renewal or deletion flow (a returned
  `purchase_url` is handed to the user).
- **Chrome (rung 2).** One persistent browser named `ffr`, the user's Chrome
  profile imported once if they agree (record the yes in the state
  directory), `--headed` when a display exists.
- **Sessions.** Every job gets its own session named `ffr-<source>-<n>`
  (`ffr-flightlist-1`, `ffr-google-1`, `ffr-kiwi-2`); the agent drives only
  sessions it opened, never one the user or another agent opened, and closes
  them at the end with `browseract.py close --all-mine`. A session name is a
  live handle, not a durable id: re-open rather than reuse a stale name.
- **Driver.** The scripts share `browseract.py`: `Session(name).open(url)`,
  `navigate`, `read_markdown`, `eval`, `wait_for(regex)`, `network_status`,
  `close`, and `handle_challenge`. Silent blocks show up in the network log
  (`browser-act --session <name> network requests --status 403`), not on the page.

## Parallelism and pacing

- Different source families always run at the same time, one session each:
  FlightList discovering in `ffr-flightlist-1` while Google confirms in
  `ffr-google-1` and Kiwi reprices in `ffr-kiwi-1`. `run_log.py jobs` prints
  the plan; with subagents, give each one a job list.
- Within one site, `sessions_per_site` parallel sessions (default 2; Google
  1). Pacing per site comes from the ledger (`pace_seconds`: 8 by default,
  12 on Google) and from the page's own ready signal (a priced card, a result
  count), never a fixed wait.
- Google keeps its daily allowance rule: about 90 searches in 24 hours drew
  HTTP 429 and `google.com/sorry` (2026-10-09). Discover with FlightList,
  confirm the cheapest tuples on Google.
- Deep links over refilled forms; decline optional cookies once per site and
  keep the session; read results with one page-text read.

## When a site challenges you

A **challenge** is a CAPTCHA, press-and-hold check, "unusual traffic" or
"are you a robot" page, bot-help redirect, HTTP 403/429 in the network log,
or an empty results shell after the timeout. `browseract.py`'s
`handle_challenge` applies this order; the sweeps call it for you:

1. **Logged in:** `browser-act --session <name> solve-captcha` once. Solved
   (`solved=True`) → continue, and note it on the row.
2. **Not solved, user reachable:** `remote-assist --objective "<source>
   <search>"`, send the user the link, wait up to 10 minutes for the page to
   change, then continue in the same session.
3. **Not solved, user watching their own browser (rung 3):** ask them to
   clear it, then continue.
4. **Otherwise:** record it and stop that site for the run:
   `source_ledger.py record <id> blocked --engine <name> --evidence "<what the
   page said>"` and a `run_log.py add` attempt row with `"outcome": "blocked"`.
   Name the blocked source in the report and move to the next family.

Never: book, pay, enter passenger details, create accounts, buy proxies or
browsers, import anyone else's sessions, or use private or reverse-engineered
APIs. BrowserAct's free features are the user's own configured tooling; the
skill uses them as configured and nothing beyond.

## Running the recipe snippets

Per-source recipes write page code as plain JavaScript ("run in page") and
name keyboard and text actions generically. Map them to the engine:

| Recipe action | BrowserAct (`browser-act --session <name> …`) | Claude in Chrome / built-in / Cowork | Headless (CDP / Playwright) |
|---|---|---|---|
| Run in page | `eval "<js>"` (or `eval --stdin`) | the JavaScript tool | `Runtime.evaluate` / `page.evaluate` |
| Type into a field with real keys | `input --selector <css> --text "text"` | the type or form-input tool | `Input.insertText` / `page.keyboard.type` |
| Press a key with a real key code | `keys "Enter"` | the key-press tool | `Input.dispatchKeyEvent` with `windowsVirtualKeyCode` |
| List controls by role and name | `state` (indexed `[N]` list) | read-page / find tools | `Accessibility.getFullAXTree` |
| Click a control | `click <N>` or `click --selector <css>` | the click tool | `page.click` |
| Read the page as text | `get markdown` | read-page / get-page-text tools | `page.innerText` |
| Wait for results | `wait stable`, or poll `get markdown` | wait / screenshot | `page.waitForLoadState` |
| Silent block | `network requests --status 403` | the network tool, if any | `Network.responseReceived` |

Indices from `state` are valid only until the page changes; never reuse old
numbers. After any reflow, take a fresh screenshot before a coordinate click,
and prefer DOM-scoped lookups to coordinates.

## Date pickers

- Google Flights: build the search URL with `gflights.py url` instead of the
  calendar (`references/google-flights-browser.md`).
- FlightList: `flightlist.py sweep` sets both pickers through the
  daterangepicker instance with `Date` objects and reads them back
  (`references/flightlist-browser.md`).
- eDreams: readonly inputs; click the day cell inside the right month
  (`references/edreams-browser.md`).
- ITA Matrix: native value setter plus input/change events
  (`references/ita-matrix-browser.md`).

Whatever the method, read back the committed dates, then confirm the populated
results repeat them.

## No browser on the host

Ask the user before installing anything. Prefer installing BrowserAct
(`uv tool install browser-act-cli --python 3.12`). The last resort is
user-space Playwright Chromium with a throwaway profile (rung 4,
`headless-playwright`), started as a tracked background process and stopped
afterwards; it is the engine most likely to be challenged.
