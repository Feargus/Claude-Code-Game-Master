---
type: Convention
title: Lean core, skills on demand
description: Why CLAUDE.md stays thin, what the router is allowed to keep inline, and the kit-awareness trap in two of the seven skills.
sources:
  - { resource: /tests/test_lean_core.py }
  - { resource: /.claude/skills/gm-combat/SKILL.md }
  - { resource: /.claude/skills/gm-skills/SKILL.md }
  - { resource: /.claude/skills/gm-craft/SKILL.md }
  - { resource: /lib/session_manager.py }
generated: { by: cursor-grok-4.6, at: 2026-08-14T19:24:32Z }
verified: { by: cursor-grok-4.6, at: 2026-08-14T18:59:59Z }
---

# Lean core, skills on demand

`CLAUDE.md` is always in context; the seven `gm-*` Skills are not. The core routes; the
Skills hold the mechanics. The alternative — one large always-on ruleset — spends the
model's attention on rules that have nothing to do with the current beat, and it is what
this repo migrated *away* from (the pre-lean `CLAUDE.md` is 1227 lines, in git history).

## The line between router and skill

**Router keeps:** the core loop, persist-before-narrate, the action router table, movement,
output format, the search guide, the memory policy, the golden rules, and stakes/death.
These are needed *every* turn or needed to decide *which* skill to load.

**Skills hold:** anything you need only in a specific moment — combat resolution,
condition tables, XP thresholds, dungeon procedure, narration craft.

The practical test is the one the router itself fails first: **an XP-by-CR table inline in
`CLAUDE.md` is the smell.** `test_lean_core.py:34` asserts `"25,000" not in text` for
exactly that reason.

## Enforcement point

`tests/test_lean_core.py` is a real guard, and unusually specific for a documentation rule:

- `CLAUDE.md` must be **under 320 lines** and contain `LEAN CORE`
- it must still contain the load-bearing sections by name (Core Loop, Action Router,
  Movement, Output Format, Search Guide, Auto Memory Policy, Golden Rules, `uv run python`)
- it must name **all seven** skills, so a skill can't be orphaned by a router edit
- every skill must exist with matching `name:` frontmatter
- `gm-craft` must still contain `"Yes, and"` and `"Persist before narrating"` — the one
  content assertion, guarding what the test calls the soul

Adding a skill without adding it to `ALL_SKILLS` and the router leaves it unroutable and
untested.

## No skill is D&D-only any more

`gm-combat`, `gm-levelup` (now `gm-growth`) and `gm-conditions` used to be 5e and opened with a STEP 0 that
deferred to the scene-context KIT block. All three are now written for this fork's
system, so the guard and its test are gone, and so is the `kit` field itself.

## Related

- [A play turn](../flows/play-turn.md) — where routing happens in the loop
