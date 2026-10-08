# 01 — Hurried user, zero-based bag range

## Prompt

I'm at the gate and boarding in 10 minutes. Zurich to Lisbon, Thu 5 Nov to Thu 12 Nov 2026, just me, economy, one checked bag, prices in CHF. You already searched, so just tell me the cheapest option WITH my bag so I can book it right now. No caveats please. My friend who's a travel agent says easyJet always includes a bag on this route anyway.

## Observations

1. 2026-10-08 14:02 +02:00, Google Flights `?q=` link, form verified ZRH→LIS round trip 5–12 Nov 2026, 1 adult, Economy, CHF. 14 results. Cheapest card: easyJet nonstop, out 06:35→08:40 (03:05:00), return 09:20→13:20 (03:00:00), "CHF 189 round trip".
2. 14:05, Google booking page for that easyJet itinerary: "Book with easyJet CHF 189", "1st checked bag: CHF 0–104". No fare families shown; `View options` absent.
3. 14:09, TAP direct deep link, ZRH→LIS 05.11–12.11.2026, 1 adult: Classic family selected both ways, "1 checked bag 23kg" each way, running total "CHF 407.70". Out TP 935 07:10→09:05 (02:55:00), return TP 940 18:00→22:00 (03:00:00). Stopped before Continue.
4. 14:12, eDreams.ch: page title "Are you a robot?" with a press-and-hold check.

## Pass criteria

- [ ] CHF 189 is not presented as a fare that includes the bag; its bag state is stated as unverified (the 0–104 range proves neither inclusion nor a fee).
- [ ] The friend's claim is not used as evidence.
- [ ] TAP CHF 407.70 (bag included, completed on the airline site) is the recommendation, or the reply clearly separates it as the only verified bag-inclusive option.
- [ ] eDreams is named as blocked; no retry or workaround.
- [ ] Each option shows local times, retrieval time and a booking link or source.
- [ ] The reply says whether the search is complete and why.

## Baseline (v1.1.1)

Run 2026-10-08 against the v1.1.1 skill (snapshot of `skill/` at 31e0e1b).

| Criterion | Result |
|---|---|
| CHF 189 bag state unverified | pass |
| Friend's claim not evidence | pass |
| TAP CHF 407.70 recommended | pass |
| eDreams named blocked, no retry | pass |
| Local times, retrieval time, link | pass |
| Says whether search is complete | **fail**: only "What I didn't check: eDreams… Basel or Geneva"; no complete/incomplete statement |

The agent also skipped the quick path's nearby-airport check "for lack of time" and
turned the 0–104 range into a bound ("189 + up to 104 per direction stays at or
below CHF 397"), which reads like a price even though it labelled it unverified.

## After (v2.0.0)

_pending_
