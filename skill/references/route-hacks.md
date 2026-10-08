# Route hacks

A hack is a different ticket structure for the same trip. It wins only when its
**qualified** all-in total and its risk beat the best qualified home-airport
option for the same cabin and dates. A hack with any unpriced part is a lead,
and a lead is never the pick.

## Which hacks apply

`run_log.py init` creates one comparison per cabin for each permitted hack and
marks the rest not applicable with a reason. Record hack rows with `"hack"`
set; `run_log.py coverage` shows what is still open.

| Hack (`hack`) | What to test | Needs |
|---|---|---|
| `split` | Outbound and return as separate one-way tickets, any airlines or sellers; compare the bag-qualified sum with the round trip | return trip |
| `open_jaw` | Home → destination with return from (or to) another airport, plus the ground leg that closes the gap; both orientations | return trip |
| `nearby_origin` | Round trips and one-ways from the nearby airports, plus the rail or flight to reach them | `positioning.allowed` and `nearby_origins` |
| `alt_destination` | A regional gateway plus a protected or separately priced local leg, when elapsed time and bag handling stay acceptable | `alt_destinations` |
| `stopover` | The carrier's stopover product, then the fallback below | requested by the user |

Fare-family arbitrage (airline direct vs aggregator vs branded families) is part
of qualification, not a separate hack: see `qualification.md`.

## All-in and break-even

All-in = tickets + bag fees for the requested bags + positioning (both ways) +
unavoidable hotel nights + transfers. `run_log` sums the parts; a `null` part
keeps the row a lead and counts as 0 only in its lower bound.

When one part is unpriced, show the **break-even** instead of a total: the most
that part can cost before the hack stops winning.

> BSL ⇄ LIS easyJet with bags: CHF 230.00 (completed). Best qualified ZRH option: CHF 407.70.
> Basel wins only if the train plus any airport bus, both ways, costs under CHF 177.70.
> Rail not priced yet. **Lead, not a recommendation.**

A cost the user estimates ("the train is about CHF 30") belongs in the message
as their estimate next to the break-even. The recommendation stays the best
qualified option until the part is priced on its seller's site.

## Timing and risk

- A previous-day positioning trip or airport hotel changes the trip window and
  any event buffer; it needs `positioning.overnight_ok` and goes in `hotel`.
- Reject a return positioning leg that leaves no realistic time after the long
  flight for immigration, baggage reclaim, terminal change and re-check; price
  a later connection or a hotel instead.
- Check that an early first departure is reachable by the first train or bus
  with bag-drop time; otherwise it needs a hotel night.
- Separate tickets: disclose self-transfer, bag reclaim and re-check, airport
  changes and misconnection exposure. On a high-value long-haul ticket,
  recommend previous-day positioning unless the connection is on one ticket.
- Hidden-city or throwaway tickets are not bag-compatible: checked bags go to
  the ticketed destination. Leave them out when bags are checked.

## Stopover construction

1. Price the carrier's own stopover or multi-city tool first, so every sector
   stays on one protected ticket.
2. If it will not price, build the fallback: `home → stopover hub` plus
   `destination → home` as one open jaw, and `stopover hub → destination`
   separately (try the same carrier and a cheaper regional carrier).
3. Complete every ticket and record each ticket's own bag line.
4. Check the carrier's rule for stays over 24 hours (bags are usually
   collected) and entry rules for the traveller's actual passport.
5. Work out the time in the stopover city, hotel nights, arrival date at the
   destination, sleeps before any event, and the time-zone change. Show a
   two-night and a three-night version when both fit.
6. Report the qualified flight total, unpriced hotel and ground costs, and the
   difference from the through fare. Prefer the one-ticket stopover when its
   premium is reasonable.

## Pruning

`run_log.py rank` lists leads cheapest lower bound first and marks
`pruned: LB x >= best y` when a lead cannot beat the best qualified total even
with its unknown parts at 0. Spend slow repricing only on unpruned leads.
Pruning is recomputed on every call, so a pruned lead returns automatically if
the best option is later rejected or superseded. A comparison whose populated
rows are all rejected or pruned is finished.

## Finding hack leads

Leads from the web are ideas to price, never prices. Reprice every one on the
exact dates, then add it as a row.

0. **Which routes exist:** for each nearby or alternative airport, read its
   FlightConnections page (`source-ladder.md`) to see which airlines fly
   non-stop to the destination; price only those.
1. **Broad, keyless:** one short web search per hack type, run in parallel:
   `<carrier> stopover program <hub>`, `fifth freedom flights <region> <destination>`,
   `new route <origin> <destination> <season>`, `<airline> sale <month year>`,
   `rail and fly <airline> <country>`. Keep title, URL and publication date;
   drop undated pages or ones older than the travel season they describe.
2. **Official policy pages** (stopover rules, fare-family bag tables, transit
   and entry rules): read them as text with the host's fetch tool or
   `curl -s "https://r.jina.ai/<URL>"`. Policy explains which family to pick; it
   never qualifies a price.
3. **Perplexity Search API**, only when `PERPLEXITY_API_KEY` is already set:
   the fast preset for fan-out, the default preset for entry, transit and
   baggage-rule questions.
4. **Deal feeds, forums, social posts:** historical reports with their post
   date. Reach them without account cookies or proxies.
