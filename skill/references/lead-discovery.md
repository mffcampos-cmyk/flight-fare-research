# Lead discovery tiers (route hacks, stopovers, deals)

Ideas from Agent-Reach (keyless channels) and Perplexity's fast/default search split. Every lead is a **candidate** that must be repriced on exact dates. Record which tier produced it. None of these tiers yields a bookable fare.

## Tier 1: broad fan-out (host web search, keyless)

Run one short query per hack type, in parallel, rather than one long query:

- `<carrier> stopover program <hub>`: free or cheap stopover schemes
- `fifth freedom flights <origin region> <destination>`
- `new route <origin> <destination> <season/year>`: seasonal launches
- `<airline> sale <month year>` / `rail and fly <airline> <country>`

Keep result titles, URLs and publication dates. Discard pages without a date, or older than the travel season they claim to describe.

## Tier 2: official policy and terms pages (Jina Reader or host extract)

Stopover rules, fare-family baggage tables, transit and entry conditions:

```bash
curl -s "https://r.jina.ai/https://www.<airline>.com/<policy-page>"
```

Jina Reader returns clean markdown with no key and no browser. Use it, or the host extract tool, instead of driving a browser for static pages. It cannot render fares, because those are JS-driven. Policy text explains which fare family to select; it never qualifies a price (see SKILL.md §3).

## Tier 3: Perplexity Search API (optional)

Only when `PERPLEXITY_API_KEY` is already in the environment or secret store. Never ask for it in chat.

- **fast preset** for Tier-1-style fan-out. Perplexity reports 160 ms median and 230 ms p95 per search, and about 68% lower model-plus-search cost than its default preset at comparable task quality.
- **default preset** for high-stakes questions (entry/transit permission, stopover baggage collection, fare rules). Perplexity reports higher relevance (2.45 vs 2.21 relevance score) and answer availability (59.6% vs 56.7%) for it.

All figures are Perplexity's own (Photon blog, 2026), not controlled comparisons.

## Tier 4: deal feeds and community posts

RSS deal sites, Reddit, X posts: historical user reports at best. Label them as such, with post date. Do not configure account cookies, OpenCLI browser-session reuse, or proxies to reach them; that crosses the skill's anti-evasion rule. Verify a feed URL exists before using it with a feed reader.
