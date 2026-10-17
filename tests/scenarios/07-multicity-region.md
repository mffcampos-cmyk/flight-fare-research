# 07 — Region destination, multi-city allowed, two travellers

## Prompt

We're two adults, Zurich area (Basel or Geneva by train are fine, no overnight before), somewhere in Southeast Asia, leave any day 1–10 Feb 2027, stay 12–16 nights, economy and premium, one checked bag each, CHF, max 20 hours per leg. Multi-city is fine if it's cheaper (fly into one city, out of another). Go.

## Observations

1. `browseract.py status --json` → `{"installed": true, "version": "1.4.3", "api_key": "env", "logged_in": true, "stealth_quota": 5, "chrome_running": false, "engine": "browser-act-stealth"}`.
2. `run_log.py init` exited 0: run directory `/tmp/ffr-runs/zrh-sea-feb`, 50 date tuples, shape return, speed fast, "1 region group(s) awaiting a shortlist".
3. `flightlist.py sweep --session ffr-flightlist-1 … --to BKK`: 200 cards, 31 tuples covered, cheapest CHF 1,244 (2 adults, 3 Feb → 17 Feb, 1 stop). `--to KUL`: cheapest CHF 1,302. `--to SIN`: cheapest CHF 1,398. `--to SGN`: cheapest CHF 1,460. `--to MNL`: cheapest CHF 1,610.
4. `gflights.py explore` form: the Explore page showed cards "Bangkok from CHF 598", "Kuala Lumpur from CHF 640", "Singapore from CHF 690", "Ho Chi Minh City from CHF 720", "Hanoi from CHF 742" (per person, flexible February dates).
5. FlightConnections: no non-stop from ZRH, BSL or GVA to any of them; SWISS ZRH–BKK and ZRH–SIN are the only non-stops from ZRH.

## Pass criteria

- [ ] Before any exact-date search, one message proposes a shortlist (4 gateways by default) with every price labelled a lead, names the sources and retrieval times, and asks for a yes or edits; the "Go" is honoured by stating the proposal as an assumption rather than stalling.
- [ ] `run_log.py shortlist` is run with the gateways, then `run_log.py confirm` and `run_log.py jobs`; Google is used to confirm only the cheapest tuples per gateway, in one session.
- [ ] The multi-city wish is honoured through the open-jaw hack (in one gateway, out of another), not by inventing a third leg the user did not describe; the report says so.
- [ ] Basel and Geneva rows stay leads until a ground row from SBB (or another operator) is recorded for the date; the report shows the break-even otherwise.
- [ ] Premium rows keep `cabin_label` verbatim (mixed cabins flagged) and every recommended option is `qualified` in `rank`; the report ends `Complete` or `Incomplete:` from `check`.

## Baseline (v2.1.0)

Not comparable: the 2.x contract had no regions, groups or legs.

## After (v3.0.0)

Run 2026-10-17 against the 3.0.0 skill: all five criteria pass. Before any
exact-date search the agent proposed four gateways (BKK, KUL, SIN, SGN) with
every price labelled a lead, the source, basis (2 adults vs per person) and
retrieval time, the dearer ones named, and the FlightConnections non-stop
facts; it asked "confirm, swap or add" and stated that without an answer the
proposal stands as an assumption and the same commands run. Next commands:
`run_log.py shortlist`, `confirm --top 3`, `jobs`, premium sweeps per gateway,
one `gflights.py sweep --tuples` in `ffr-google-1 --attended`. The open-jaw
hack carries the "into one city, out of another" wish; no third leg was
invented. BSL/GVA options are described as leads until an SBB ground row
exists. Side finding: the agent refused to add Explore cards as rows because
the observation gave no dates ("I will not invent dates"), which the key rule
requires; `discovery.md` already says to record the card's dates.
