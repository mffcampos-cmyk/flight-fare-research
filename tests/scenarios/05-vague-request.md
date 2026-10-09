# 05 — Vague request, "don't ask me questions"

## Prompt

Find me cheap flights to Lisbon next month. I live in Zurich. Don't ask me a million questions, just go.

## Observations

(None yet: this is the start of the session. Today is 2026-10-08.)

## Pass criteria

- [ ] Before any search, the reply either asks the missing intake items in one message with a proposed default for each, or (honouring "just go") states each default as an explicit assumption.
- [ ] The intake covers: exact dates or trip length, passengers, cabin, checked bags, currency, per-direction duration limit, nearby airports / positioning tolerance, self-transfer tolerance.
- [ ] Checked bags are not silently assumed away (a bag default is stated).
- [ ] No fares are invented.

## Baseline (v1.1.1)

Run 2026-10-08 against the v1.1.1 skill.

| Criterion | Result |
|---|---|
| One intake message or explicit defaults before searching | pass (honoured "just go" with defaults) |
| Covers dates/length, passengers, cabin, bags, currency, duration limit, positioning, self-transfer | **fail**: no duration limit stated; self-transfer tolerance not stated (internally "Allow self-transfers but label them"); positioning only as an opt-in |
| Bag default stated | **partial**: "checked-bag status next to every price… plus the cheapest option that includes a bag", no explicit bag assumption |
| No invented fares | pass |

## After (v2.0.0)

Run 2026-10-08 against the v2 skill.

All four criteria pass. One message of defaults covering dates (23 rolling
7-night pairs), travellers, cabin, 1 checked bag, CHF, "Journey time: no
limit", Zurich only with Basel/Geneva offered, and "No self-transfer
connections". The agent reported two skill gaps, both fixed in the same commit:
`open_jaw` stayed open with no second airport (now auto not-applicable), and
`intake.md`'s example contract contradicted its defaults table (now labelled as
the post-reply contract).
