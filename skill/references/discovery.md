# Discovery: a region becomes a shortlist of gateways

Use this when a destination group has `"region": true` and no airports yet
(`run_log.py init` says "awaiting a shortlist"; `check` stays incomplete
until the shortlist exists). Discovery finds the cheapest gateway airports for
the window; it never produces a recommendation. Every price it sees is a lead.

## Three sources, in parallel sessions

1. **FlightList range search** (`references/flightlist-browser.md`), one per
   candidate gateway and origin airport, the whole outbound and return
   windows in one search:

   ```bash
   python3 <skill_dir>/scripts/flightlist.py sweep --session ffr-flightlist-1 --run <dir> --cabin economy --from ZRH+BSL+GVA --to BKK
   python3 <skill_dir>/scripts/flightlist.py sweep --session ffr-flightlist-2 --run <dir> --cabin economy --from ZRH+BSL+GVA --to SIN
   ```

   Rows land in the run as `phase: discover` list fares. Before the shortlist
   exists the contract has no destination airports, so run these sweeps for
   the candidates below with `--to`; the rows are recorded against the
   candidate and count once the shortlist includes it.
2. **Google Flights Explore** for the region and the leg-1 window:

   ```bash
   python3 <skill_dir>/scripts/gflights.py explore --region "Southeast Asia" --from ZRH --window 2027-02-01,2027-02-10
   ```

   prints the Explore URL and the form steps (Explore ignores query parameters
   for regions, and no capture of its card text exists: 2026-10-17 the
   datacenter probe got Google's "unusual traffic" check). Drive the form in
   your session, read the destination cards by hand (city, lowest price,
   dates, stops) and record one discover row per gateway airport with
   `run_log.py add` (`quote_state: "list"`, `baggage: "unverified"`,
   `phase: "discover"`, the first leg as `legs[0]`). A challenge here follows
   `references/browser-engines.md`; Explore spends the Google allowance like
   any search.
3. **FlightConnections** (`references/source-ladder.md`) for
   `flights-from-<origin>` on each origin airport: which gateways have
   non-stops from which airport. Routes only, never prices.

## Candidate gateways

Candidates to search, never evidence. Pick from the region's table and add
any the user names.

| Region | Gateways (IATA) | Positioning hubs often cheaper to reach first |
|---|---|---|
| Southeast Asia | BKK, DMK, SIN, KUL, SGN, HAN, MNL, CGK, DPS, RGN, PNH | DOH, DXB, AUH, IST |
| South Asia | DEL, BOM, CMB, MLE, KTM | DOH, DXB, AUH, IST |
| East Asia | HKG, TPE, NRT, HND, ICN, PVG, PEK | DOH, HEL |
| Caribbean | SJU, PUJ, MBJ, CUN, HAV | MAD, LIS, AMS, CDG |

## Propose the shortlist

One message, `shortlist` gateways (default 4) in order of the cheapest
discover price seen, each with the price, its dates, the source and the
retrieval time, all labelled **lead (not verified)**:

> Cheapest gateways for Zurich area → Southeast Asia, 1–10 Feb out, 12–16 nights (leads, not verified):
> 1. **BKK** CHF 612 (FlightList, 3 Feb → 17 Feb, 1 stop, 2027-01-08 14:03 +01:00)
> 2. **KUL** CHF 648 (FlightList, 5 Feb → 19 Feb, 1 stop)
> 3. **SIN** CHF 701 (Explore card, "from CHF 701", Feb)
> 4. **SGN** CHF 735 (FlightList, 2 Feb → 14 Feb, 2 stops)
> Searched but dearer: HAN, MNL, CGK. Not reachable non-stop from BSL or GVA: all of them (FlightConnections).
> Shall I confirm these four, swap one, or add an airport?

Wait for the user's confirmation or edits. Unattended, the proposal stands and
is recorded as an assumption. Then:

```bash
python3 <skill_dir>/scripts/run_log.py shortlist --run <dir> BKK,KUL,SIN,SGN
python3 <skill_dir>/scripts/run_log.py confirm --run <dir> --top 3     # fast mode: tuples to confirm
python3 <skill_dir>/scripts/run_log.py jobs --run <dir>                 # the parallel plan
```

`shortlist` adds the airports to the region group (and its return
reference), rebuilds the date tuples and the comparison cells; `confirm`
picks the cheapest discovered tuples per gateway for the exact-date
confirmation on Google (`gflights.py sweep --tuples …`).

Discovery prices never appear under Recommended: a gateway's price becomes a
recommendation only after confirmation, qualification and repricing like any
other row.
