# Flight Fare Research

Use the `flight-fare-research` skill for live airfare or route research.

Run `scripts/browseract.py status` first and use the highest browser engine it finds (a BrowserAct stealth browser, then BrowserAct's local Chromium, then the user's own browser, then a headless tool), with the pacing and challenge rules in its `references/browser-engines.md`. Send the full intake questionnaire (`references/intake.md`), record every observation with `scripts/run_log.py` and finish with `run_log.py check`. Official APIs are used only when credentials are already configured; this integration ships none. Research only: never book, handle payment or account credentials, create the BrowserAct account, or buy proxies or browsers.
