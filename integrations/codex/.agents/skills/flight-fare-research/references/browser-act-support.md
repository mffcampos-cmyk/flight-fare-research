# Browser Act support for fare research

Use the **browser-act** CLI as the default interactive engine for fare sources:
it drives a real Chromium, renders JS, fills forms, and reads populated results.
Prefer it over static extraction (web_extract/curl) whenever the source needs
form interaction, autocomplete, date pickers, or anti-bot-rendered pages. Load
the browser-act skill first; this file records only fare-research-specific
lessons.

## Environment: the CLI and the browser can be on different data dirs

On hosts where Chrome must run as a non-root user (e.g. `chrome-user`), the
browser processes and their `browsers.db`/sessions live under THAT user's HOME,
while a root shell invokes the CLI against its own data dir. Symptoms:

- `browser-act browser list` shows browser IDs that do not match the running
  Chrome process args (compare `ps -u chrome-user -a chrome | grep remote-debugging-port`);
- `browser open <id>` fails with "Browser not found" even though `ps` shows a
  live Chrome for a different ID;
- an existing session appears in `browser list` under the other user but not
  under the current environment vars.

Fix: run the CLI as the same OS user as Chrome, with that user's HOME and
working display. HOME alone does not change process ownership and can create
root-owned daemon files. On the reviewed Linux host (2026-09-23):

```bash
su - chrome-user -c 'export HOME=/home/chrome-user DISPLAY=:99; /root/.local/bin/browser-act --session SESSION_NAME state'
```

The username, display and executable path are environment-specific, not
installation requirements. Confirm them locally; do not blindly change
ownership or restart someone else's browser.

## Session lifetime: reopen, do not recreate

A named session is a runtime handle, not a durable object. Between runs it can
disappear (`session list` empty) while the underlying browser and its profile
survive. Do not create a new browser just because the session expired; instead, open your own uniquely named session on the SAME browser ID.
Cookies/profile may survive, but a new session does not guarantee restoration
of the previous tab, filled form, or result state. Never operate another
conversation's session merely because its name appears in a handover.

```bash
# find the live browser id first
su - chrome-user -c 'export HOME=/home/chrome-user DISPLAY=:99; /root/.local/bin/browser-act browser list'
# then open a new uniquely named session on the observed ID, for example:
su - chrome-user -c 'export HOME=/home/chrome-user DISPLAY=:99; /root/.local/bin/browser-act --session research-new browser open BROWSER_ID https://www.flightlist.io/'
```

After attaching, run `state` before assuming the previous form values are
visible, and verify origin/destination/date labels before searching again.

## Consent and bot walls are part of the flow

- Google properties redirect to a consent page first
  (`consent.google.com/m?continue=...`). Interact with it normally: find the
  `Reject all` (or equivalent non-essential refusal) control in `state` and click
it; do not treat the consent page as a block. Decline optional cookies on every
site. After declining, the session keeps the choice for subsequent
navigations (same browser, shared cookies).
- A title or body already signals a dead source before you invest in the form.
  On `browser open`, check the rendered title/URL immediately:
  `Bot or Not?`, `Access Denied`, `kayak.com/help/bots.html`, an empty DOM,
  or a CAPTCHA means: record the source+failure mode (see
  `source-ladder.md`), make the one allowed attempt if a search can still be
tried, then move on. Do not tune stealth/proxy/CAPTCHA settings to force it.

## Source triage loop (quick)

For each candidate source, one bounded pass:

1. `browser open <id> <homepage>` — record title and final URL.
2. If a bot/denied signal appears, log it and stop (no form work).
3. Otherwise try an exact-date search (deep URL first if documented, else the
   form; see per-source reference files).
4. If populated fares render, save the query contract + raw text and add the
   source to the working tiers; if the search flow 404s, redirects to a bot
   page, or never populates, log the failure mode and move on.

This mirrors the skill rule: one recorded attempt per source per run.

## Parallel sessions on one browser

Open independent sessions (`browser open` with different `--session` names) on
the SAME browser id for cross-checks: each session is its own window sharing
cookies/login state, so consent or login is done once. Useful for running
FlightList and eDreams side by side on the same route. Close sessions
(`session close <name>`) when done to free resources.

## Date pickers: drive the widget instance, not DOM events

jQuery daterangepicker-style widgets (FlightList) and readonly date inputs
(eDreams) ignore typed input and synthetic clicks. Patterns that work:

- FlightList: `jQuery('#deprange').data('daterangepicker')` -
  `setStartDate/setEndDate` with **Date objects**, then click the picker's
  `Apply` button (see `flightlist-browser.md`).
- eDreams: click the readonly date field to open the popup calendar, then click
  the `div.odf-calendar-day` cell; verify the input text afterwards (see
  `edreams-browser.md`).
- Google Flights: focus the active calendar input and `Input.insertText` the
  locale date, then Enter (see `google-flights-browser.md`).

Verify the submitted date contract and the returned itinerary dates. FlightList's
visible range span can stay stale after Apply even though the picker and search
use the new dates: inspect BOTH startDate/endDate for BOTH picker instances,
then verify dates on populated results. Neither a cosmetic label nor picker
internals alone proves that the returned fares match the contract.

## Pitfalls

- Session names from another conversation/run are not yours; a session you
  did not create may be live for someone else. Reuse only sessions you opened.
- `browser list` under the wrong HOME shows the wrong world: always confirm the
  data dir matches the user who owns the Chrome processes.
- A populated-looking homepage is not a working search flow; always complete
  one exact-date search before classifying a source as usable.
- Closing `session close` the shared browser's last session does not kill the
  browser profile; reuse it next run.
