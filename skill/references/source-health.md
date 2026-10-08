# Source health ledger

Each source has a real probe and a recorded state, so the order of sources
comes from evidence rather than memory. The agent runs the probes;
`scripts/source_ledger.py` keeps the books. The ledger is runtime state outside
the skill folder: `$FFR_LEDGER`, else
`$XDG_STATE_HOME/flight-fare-research/source-status.json`, else
`~/.local/state/flight-fare-research/source-status.json`. A missing ledger is
seeded from the script's built-in list. Raw probe evidence stays on the
machine; never commit the ledger.

## When to run

At the start of every full-path run:

```bash
S=<skill_dir>/scripts/source_ledger.py
python3 $S status    # exit 0: fresh, skip probing; exit 3: probe the core sources listed
python3 $S order     # USE / UNTESTED / AVOID for this run, with the engine of each state
```

Probe only the sources under `PROBE NEEDED`. Quick runs skip the gate but
still record any block they meet. The user can ask for a full re-probe at any
time.

## Canary contract

```bash
python3 $S canary    # ZRH→LIS, today+30 → +7 days, 1 adult, economy, CHF
```

The same search every time, so states compare across runs. A source that cannot
express it gets a variant written into `--evidence`: an LCC-only site may use a
nearby LCC origin; a `positioning` source (rail) prices the train to the
departure airport on the canary date; a `routes` source lists nonstop routes
from the canary origin.

## One probe per source

1. Open the source with the highest-rung engine available (`browser-engines.md`)
   and decline optional cookies.
2. On a challenge, record `blocked` with the engine and stop; no retries.
3. Otherwise run the canary through the source's recipe.
4. Classify and record:

| State | Meaning |
|---|---|
| `ok` | The page repeats the exact search and shows ≥1 priced result. Requires `--results N`. |
| `partial` | Works with a scope or contract gap: LCC only, forced currency, one direction, no bag data. |
| `blocked` | Bot wall, CAPTCHA, 403/429, human check. |
| `empty` | Submits but returns no populated results. |
| `error` | Cannot be driven: picker will not commit, 404 deep link, dead autocomplete. |

```bash
python3 $S record edreams ok --results 14 --engine claude-in-chrome \
  --url "<results URL>" --evidence "canary 2026-11-07/14 populated, per-fare bag labels"
python3 $S record kayak blocked --engine browser-act --evidence "redirect to kayak.com/help/bots.html"
python3 $S record condor-direct ok --results 3 --engine claude-in-chrome --add \
  --name "Condor" --role airline --family condor --url https://www.condor.com/ --evidence "canary populated"
```

`--add` registers a source the built-in list lacks (another airline, a rail
seller). Roles: `discovery`, `exact`, `ota`, `airline`, `crosscheck`,
`opportunistic`, `positioning` (rail or bus to an airport), `routes` (which
airlines fly where; no fares).

## Rules

- A canary `ok` proves the search flow works today; its prices are never fare
  evidence for the user's trip.
- During a real search, record what you meet: a block right away, and an `ok`
  with `--evidence "real search <route/dates>, not canary"`.
- States are per engine. A block recorded on `browser-act` or a headless engine
  does not prove a block in the user's own browser; with a rung-1 engine
  available, one probe there is allowed.
- Independence follows `family`: FlightList and Kiwi share `kiwi`; Opodo shares
  `edreams`; Momondo shares `kayak`; any Google Flights wrapper is `google`.
- Before recording `error` or `partial`, check the source's recipe: the first
  canary's FlightList "dead autocomplete" and eDreams "no cards" were recipe
  gaps (missing key codes; an unclicked "show more" button), not site failures.

## Expansion probe

To widen the search, probe the `UNTESTED` sources that `order` lists: one
polite attempt each with the canary (or a recorded variant), paced per
`browser-engines.md`, recorded with the engine. Sources that return populated
exact-date results join the ladder in `source-ladder.md`; write a recipe file
only for a flow you actually completed.

## No browser on the host

Ask the user before installing anything. The approved fallback is user-space
Playwright Chromium with a throwaway profile, started as a tracked background
process and stopped afterwards:

```bash
npx -y playwright@latest install chromium
~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome --headless=new \
  --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 \
  --user-data-dir="$TMPDIR/ffr-probe-profile" --no-first-run --lang=en-US
pgrep -f 'chrome.*[f]fr-probe-profile' | xargs -r kill
```

This is rung 3 (`headless-playwright`): the most likely to be challenged.
