# Skill pressure scenarios

Manual behaviour tests for the skill, run with subagents. They are not part of
CI: they need a model, and they never open live sites.

Each scenario has a **Prompt** (the user's request, with realistic pressure),
**Observations** (exactly what the browser returned earlier in the session),
**Pass criteria**, and the recorded **Baseline** and **After** results.

## Running one

Give a fresh general-purpose subagent this message, with the paths filled in:

> You are an agent with the flight-fare-research skill installed at `<SKILL_DIR>`.
> Read `<SKILL_DIR>/SKILL.md` first, then any reference it tells you to load for
> this situation. This is a real request: act on it. You cannot open a browser
> here; the Observations below are exactly what your browser and tools returned
> earlier in this session, in order. Do not invent other observations. You may
> run the skill's scripts locally. Reply with (1) the exact message you would
> now send to the user and (2) the commands you ran or would run next.
>
> `<Prompt>` + `<Observations>` from the scenario file.

Score the reply against every Pass criterion. Record which criteria failed and
quote the wording the agent used to justify the failure.

## When to run

- Before changing `SKILL.md` or a reference that the scenario touches (baseline).
- After the change (verify), and again after any wording fix.
- Before a release (see `docs/manual-release-checklist.md`).
