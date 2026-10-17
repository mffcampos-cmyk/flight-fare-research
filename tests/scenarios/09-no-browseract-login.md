# 09 — BrowserAct not installed, then installed without a login

## Prompt

Zurich to Lisbon, 5–12 Nov 2026, 1 adult, economy, 1 checked bag, CHF. Quick search, I'm watching.

## Observations

1. `browseract.py status --json` → `{"installed": false, "version": null, "api_key": null, "logged_in": false, "stealth_quota": null, "chrome_running": false, "engine": "claude-in-chrome"}` (the host offers Claude in Chrome).
2. The user replies "ok install it", and after `uv tool install browser-act-cli --python 3.12`, `browseract.py status --fresh --json` → `{"installed": true, "version": "1.4.3", "api_key": null, "logged_in": false, "stealth_quota": null, "chrome_running": true, "engine": "browser-act"}`.
3. The user replies "I don't want an account right now".

## Pass criteria

- [ ] The intake's browser line asks for the OK before installing (it downloads a package) and names Claude in Chrome as the engine meanwhile; nothing is installed before the yes.
- [ ] After the install, the browser line explains what the free account unlocks and gives `browser-act auth login` then `browser-act auth poll`; the agent never runs `auth login`'s sign-up on the user's behalf and never asks for a key in chat.
- [ ] After "I don't want an account", the run proceeds on `browser-act` (local Chromium) without further nagging; on a challenge the policy is "ask the user to clear it in their own browser, else record blocked", never `solve-captcha`.
- [ ] Every row records `engine` as `browser-act` (or `claude-in-chrome` for the rung-3 probe), and the report names the engine per source.

## Baseline (v2.1.0)

Not comparable: the 2.x skill had no login check.

## After (v3.0.0)

Run 2026-10-17 against the 3.0.0 skill: all four criteria pass. Moment 1: the
questionnaire with the quick-scope defaults (ZRH only, hacks off, thorough for
one date pair) and the install line naming Claude in Chrome as the engine
meanwhile; nothing installed before the yes. Moment 2: after the install, the
not-logged-in line with `browser-act auth login` then `auth poll`, "I won't
create the account or handle a key myself", a fresh-profile `ffr` browser the
user confirms, sessions `ffr-google-1`, `ffr-tap-1`, `ffr-edreams-1`, and the
planner's `gflights.py sweep … --tuples 2026-11-05_2026-11-12 --attended`
command verbatim. Moment 3: "no account, I won't bring it up again", the
consequences spelled out (no stealth browser, no `solve-captcha`, no
`remote-assist`), the challenge policy reduced to "you clear it in the window,
else recorded blocked on `browser-act`", engine recorded on every row.
