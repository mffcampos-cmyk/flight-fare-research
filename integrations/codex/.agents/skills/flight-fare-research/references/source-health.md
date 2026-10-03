# Source health check ("fare-sources doctor")

Pattern borrowed from Agent-Reach's `doctor`: each source has a real probe and a recorded state, and the ladder order comes from evidence rather than memory. The agent runs the probes; `scripts/source_ledger.py` only keeps the books. The ledger is runtime state kept outside the skill folder: `$FFR_LEDGER`, else `$XDG_STATE_HOME/flight-fare-research/source-status.json`, else `~/.local/state/flight-fare-research/source-status.json`. A missing ledger is seeded from the script's built-in source list. Raw probe evidence stays on the machine; never commit the ledger.

## When to run

At the start of every **full-path** request:

```bash
S=<skill_dir>/scripts/source_ledger.py
python3 $S status          # exit 0 = fresh → skip probing; exit 3 = probe the listed core sources
```

Probe only the sources listed under `PROBE NEEDED`. Quick-path requests skip the health check; they still obey the per-run one-attempt rule. The user can ask for a full re-probe at any time.

## Canary contract

```bash
python3 $S canary          # ZRH→LIS, today+30 → +7 days, 1 adult, economy, CHF
```

The same contract every time, so states are comparable across runs. Sources that cannot express it get a source-specific variant, recorded in `--evidence`. Example: AZair is low-cost-carrier only, so it may use a nearby LCC origin.

## One probe per source

1. Open the source with the host browser tool. Use `browser-act` if that CLI is installed; otherwise the Hermes browser tool (`browser_exec`). Decline optional cookies.
2. If a bot page, CAPTCHA, 403 or "Access denied" appears: record `blocked` and stop. **No retries, no stealth, proxies or CAPTCHA solving.** Agent-Reach's server-proxy advice is deliberately not adopted.
3. Otherwise run the canary search through the per-source recipe (`google-flights-browser.md`, `edreams-browser.md`, `flightlist-browser.md`, `ita-matrix-browser.md`, `airline-direct.md`).
4. Classify and record:

| State | Meaning |
|---|---|
| `ok` | Page repeats the exact route, dates, 1 adult, economy, CHF, and shows ≥1 priced itinerary. Requires `--results N`. |
| `partial` | Search works but with a scope or contract gap: LCC only, currency forced, one direction only, no bag data. |
| `blocked` | Explicit bot wall, CAPTCHA, 403, human check. |
| `empty` | Form submits but no populated results, or an empty shell. |
| `error` | Form cannot be driven: date picker won't commit, 404 deep link, broken autocomplete. |

```bash
python3 $S record edreams ok --results 14 --url "<final results URL>" --evidence "canary 2026-11-02/09 populated, per-fare bag labels"
python3 $S record kayak blocked --evidence "redirect to kayak.com/help/bots.html"
python3 $S order           # ladder for this run: USE / UNTESTED / AVOID
```

## Rules

- A canary `ok` proves the source works **today**. It is not fare evidence for the user's trip; never cite canary prices.
- The ledger replaces the hand-kept "last-seen" table. Dated pre-ledger observations stay in `historical-observations.md`.
- Independence still follows `family`: FlightList and Kiwi share `kiwi`; any Google Flights wrapper counts as `google`.
- During a real search, if a source marked `ok` blocks you, record `blocked` right away so the next run sees it.

## No browser on the host (probe fallback)

If `browser_exec` fails with `BU_CDP_URL=http://127.0.0.1:9222 unreachable` and no Chrome is installed, ask the user before installing anything. The approved fallback is user-space, no sudo:

```bash
export PATH=<node-bin>:$PATH; npx -y playwright@latest install chromium     # ~/.cache/ms-playwright
# start as a tracked background process (terminal background=true), throwaway profile:
~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome --headless=new --remote-debugging-port=9222 \
  --remote-debugging-address=127.0.0.1 --user-data-dir=$TMPDIR/ffr-probe-profile --no-first-run --lang=en-US
# stop afterwards; the [f] keeps pgrep from matching its own shell:
pgrep -f 'chrome.*[f]fr-probe-profile' | xargs -r kill
```

**Recipe gap before engine blame (first canary, 2026-10-03):** the headless run recorded FlightList `error` (no autocomplete) and eDreams `partial` (summary, no cards). A headed re-probe showed both were automation gaps, not site or headless failures. Synthetic key events lacked a `keyCode` (see `flightlist-browser.md`). eDreams renders cards only after its "show more results" button (see `edreams-browser.md`). Before recording `error`/`partial`, check the per-source recipe. Say which engine produced each state in `--evidence`.
