# Flight Fare Research

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An Agent Skill for evidence-based live airfare and route research. It collects exact-date fare observations, applies explicit duration and baggage gates, and records source provenance and blocked-source outcomes.

## Supported hosts

- [Hermes](https://hermes-agent.nousresearch.com/)
- OpenAI Codex
- Claude Code

- **Cowork** — a self-contained variant optimized for the Cowork built-in browser lives in `integrations/cowork/SKILL.md` (no CLI/CDP dependencies, word-bounded, uses Cowork's native actions and hosted tools). This canonical `skill/` remains modular and host-agnostic for the environments above.

## Installation

This repository ships the canonical skill (`skill/`) plus per-host packages. Edit `skill/` and regenerate the packaged copies with `python3 scripts/package.py`; validate with `python3 scripts/validate.py`.

### Hermes

```bash
integrations/hermes/install.sh
```

### Codex

From the repository root, start Codex in the integration directory:

```bash
cd integrations/codex
codex
```

This makes `.agents/skills/flight-fare-research/` and `AGENTS.md` local to the
Codex workspace. Alternatively, copy the skill directory into your project's
`.agents/skills/` after checking for an existing installation.

### Claude Code

```bash
claude --plugin-dir integrations/claude-code
```

### Cowork (single-file skill card)

Use only [`integrations/cowork/SKILL.md`](integrations/cowork/SKILL.md) when adding
or replacing the Cowork skill card. Do not inline the canonical references or
use the Claude Code plugin as a Cowork card. Keep the frontmatter with the body.
The variant uses Cowork's available native browser tools; it requires no CLI.
The standalone card is general-purpose: provide origins, currency, nearby-airport
permissions and duration limits for each request. No personal profile is bundled.
Browser regression findings inform the recipes; they are not fare guarantees.
Cards may omit version/license metadata; the changelog records the revision.
The standalone body budget is now 1,500–2,600 words to retain working recipes.

## Requirements

The modular Hermes/Codex/Claude Code package is **browser-act-first**; the standalone Cowork card is not. Install and configure `browser-act` in the host environment before running rendered, interactive flight searches. See `skill/references/browser-act-support.md` for environment setup and session handling.

## Capability boundary

This project performs research only. It does not book flights, handle payments, complete checkout, store credentials, or guarantee observed prices. See the [Safety and provenance guide](docs/safety-and-provenance.md) for the full rules, and the [Source support matrix](docs/source-support-matrix.md) for dated per-source status.

## Documentation

- [Safety and provenance](docs/safety-and-provenance.md) — anti-evasion rules, observation-not-guarantee, baggage/quote states, source independence.
- [Source support matrix](docs/source-support-matrix.md) — dated status of working / partial / blocked / untested sources.
- [Manual release checklist](docs/manual-release-checklist.md) — the pre-release browser-act run that gates tagging.
- [Feedback review](docs/feedback-review.md) — disposition of the 24-item 2026-09-23 review (quick/full workflows, connector discovery, cookie/bag/currency gates, provenance of user-observed recipes).

- [Cowork integration review](docs/cowork-v1.8-review.md) — supplied card validation,
  latest browser fixes and validation scope.

## License

MIT. See [LICENSE](LICENSE).