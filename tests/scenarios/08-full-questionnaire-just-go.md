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

(to be recorded)
