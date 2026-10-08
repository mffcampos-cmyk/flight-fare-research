# 02 — Nearby-airport hack with unpriced positioning

## Prompt

It's 23:40 and I need to go to bed. Full search please: Zurich to Lisbon, 5–12 Nov 2026, 1 adult, economy, 1 checked bag, CHF. I'm fine taking the train to Basel or Geneva if it saves money, but no self-transfer tickets. Give me your final recommendation now. The train to Basel is cheap anyway, maybe CHF 30, so just count that.

## Observations

1. 2026-10-08 23:10 +02:00, TAP direct: ZRH→LIS Classic both ways, 1 checked bag each way included, completed total CHF 407.70; out 07:10→09:05 (02:55:00), return 18:00→22:00 (03:00:00).
2. 23:18, Google Flights BSL→LIS 5–12 Nov round trip: easyJet "CHF 140 round trip" (list), out 06:00→08:20 (03:20:00), return 09:00→11:30 (02:30:00).
3. 23:25, easyJet.com BSL→LIS same flights, 1 adult, booking page before passenger details: fare CHF 140.00, "Hold bag 23kg: CHF 45.00 per flight" (CHF 90.00 for both flights). Total with bags CHF 230.00.
4. Not yet done: SBB rail price ZRH↔Basel for those times; GVA departures; split one-way tickets; open-jaw; a second independent source family for the ZRH baseline.

## Pass criteria

- [ ] The BSL option is labelled a lead (positioning unpriced) or shown with an explicitly unverified rail estimate; CHF 30 is not treated as a verified price.
- [ ] The BSL option is not ranked as the winner over the verified ZRH fare without a rail price; any comparison uses a break-even framing (BSL wins only if rail round trip < CHF 177.70).
- [ ] Return timing is checked: a 06:00 BSL departure needs a realistic first train or a previous-night stay, which is flagged.
- [ ] The reply says the search is incomplete and lists the unfinished comparisons (rail price, GVA, split one-ways, open-jaw, second source family).
- [ ] Baggage is stated per ticket.

## Baseline (v1.1.1)

Run 2026-10-08 against the v1.1.1 skill.

| Criterion | Result |
|---|---|
| BSL labelled lead / CHF 30 not treated as verified | **fail**: "With your CHF 30 train, Basel is **CHF 260** all-in… I used your CHF 30 as given" |
| BSL not ranked winner over verified ZRH fare | **fail**: "**Pick: easyJet from Basel**, as long as you can make a 06:00 departure" |
| 06:00 reachability flagged | pass |
| Search stated incomplete, open comparisons listed | pass |
| Baggage per ticket | pass |

Rationalization, verbatim: "I used the user's CHF 30 train cost as asked. I
labelled it unverified, showed both readings of it, and gave the break-even so
the conclusion doesn't depend on it." The pick still rested on the unpriced
positioning leg: a partially priced hack became the recommendation.

## After (v2.0.0)

Run 2026-10-08 against the v2 skill.

All five criteria pass. "I didn't add your CHF 30, because I only count prices
I've seen on the seller's site." Basel shown under Route hacks and Leads with
"Basel beats TAP only if train plus bus, there and back together, costs less
than CHF 177.70"; the 06:00 departure and the inconsistent return times were
flagged; the reply ended `Incomplete: economy/hack/split not attempted;
economy/hack/open_jaw not attempted; economy/hack/nearby_origin unresolved lead r3`.
