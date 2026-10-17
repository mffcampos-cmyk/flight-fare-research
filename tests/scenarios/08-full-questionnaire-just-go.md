# 08 — Vague request, "don't ask me questions", the full questionnaire as assumptions

## Prompt

Find me cheap flights to Lisbon next month. I live in Zurich. Don't ask me a million questions, just go.

## Observations

1. Today is 2027-01-08. `browseract.py status --json` → `{"installed": true, "version": "1.4.3", "api_key": null, "logged_in": false, "stealth_quota": null, "chrome_running": true, "engine": "browser-act"}`.

## Pass criteria

- [ ] The first message lists all 18 questionnaire items with the default taken for each (trip shape, origin airports with Basel/Geneva by train, destination, dates per leg as a February range with a stated trip length, travellers, cabins, bags, currency, journey-time limit, max stops, time windows, airlines, the three hacks, self-transfer, budget, speed mode, fixed event, browser) and says it is proceeding on them because the user said "just go".
- [ ] The browser line says BrowserAct is not logged in, gives `browser-act auth login` and `browser-act auth poll`, and continues on the local `chrome` browser without waiting.
- [ ] Checked bags are not silently assumed away (a bag default is stated).
- [ ] The contract written for `run_log.py init` has every assumption in `assumptions`, `speed` set, and `hacks` with the three booleans.
- [ ] No fares are invented.

## Baseline (v2.1.0)

Scenario 05 against the 2.x skill: one message of defaults covering nine items; the 3.0 items (max stops, time windows, airlines, hacks on/off, budget, speed mode, browser line) did not exist.

## After (v3.0.0)

Run 2026-10-17 against the 3.0.0 skill: all five criteria pass. One message
with the 18 items and a default each (round trip; ZRH plus BSL and GVA by
rail, no overnight; LIS; out 1–28 Feb 2027, back 3–7 nights later; 1 adult;
economy; 1 checked bag, no cabin bag; CHF; no limit; no stops cap; no
windows; no airline preference; split and open-jaw on, stopover off; no
self-transfer; no budget; fast; no event; the not-logged-in browser line with
`browser-act auth login` and `auth poll`, continuing on the local browser).
The contract written for `init` carried 18 assumptions, `speed: fast` and the
three hack booleans (checked in the run directory); `init` gave 140 tuples and
6 cells; `source_ledger.py status` exit 3 was honoured with canary probes
before the sweep; no fares were claimed.
