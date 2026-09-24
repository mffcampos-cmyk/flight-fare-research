# Event-Anchored Trip Planning

Use this when airfare research must protect performance at a wedding, race, interview, conference, or similar fixed event.

## 1. Fix the event in local time

- Verify the event date, weekday, destination time zone, and origin-to-destination offset with a live date/time tool.
- If the year is omitted, use the next future occurrence and state that assumption.
- Keep all flight and itinerary times airport-local in `HH:MM:SS`; label next-day and two-days-later arrivals explicitly.

## 2. Build event-safe date pairs

- Convert a requested trip length into rolling matched departure/return pairs first. For example, “10 days, from 5–15 through 10–20” expands to `5→15`, `6→16`, `7→17`, `8→18`, `9→19`, and `10→20`.
- Verify the number of matched pairs programmatically for every origin and cabin. Search the broader Cartesian product only when the user accepts a shorter or longer trip; do not let a cheaper 12-day result silently replace a requested 10-day trip.
- Prefer arrival at least three local sleeps before the event. For eastward travel across about six or more hours, target four sleeps when the trip window allows it because adaptation is slower eastward.

## 3. Rank flights by event readiness before fare

Apply gates in this order:

1. Both directional journeys satisfy the hard duration cap.
2. Arrival preserves the required number of local sleeps.
3. The completed itinerary satisfies checked-bag and cabin requirements.
4. Only then rank price, stops, arrival time, and route hacks.

A positioning-airport bargain that requires arriving the previous day changes the total trip window; disclose that rather than presenting it as equivalent.

## 4. Create a conservative acclimatisation plan

Ground jet-lag guidance in an authoritative health source. For eastward travel:

- Shift sleep and meal times earlier for several days before departure.
- Time in-flight sleep, meals, and light to destination time.
- Use morning outdoor light after arrival, hydration, and only short daytime naps.
- Avoid a full-day excursion, late nightlife, or heavy drinking on the day before the event.
- Keep the event day free except for preparation; place optional sightseeing and long day trips after the event.

Do not prescribe medication or supplements. If mentioning melatonin or sleep medication, direct the traveler to a clinician or pharmacist and keep it optional.

## 5. Output the protected itinerary

Start with the recommended travel window and explain how many destination sleeps precede the event. Then give qualified economy, premium, and business options plus route hacks with any extra positioning day. Include only the jet-lag timing needed to protect the event unless the user asks for a full acclimatisation schedule. Add sightseeing or a day-by-day destination itinerary only when explicitly requested; a user who knows or has lived in the destination needs fare research, not generic tourism advice.