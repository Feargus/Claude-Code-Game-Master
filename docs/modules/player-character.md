---
type: Module
title: The player character sheet
description: Why the sheet has two shapes, which one is canonical, and how XP, death, and growth are persisted.
sources:
  - { resource: /lib/new_character.py }
  - { resource: /lib/player_manager.py }
generated: { by: cursor-grok-4.6, at: 2026-08-14T19:39:48Z }
---

# The player character sheet

## One sheet shape

The sheet is one flat JSON object (`name`, `stats`, `skills`, `luck`, `body`, …) that the
whole runtime reads. New sheets are written by `gm-player.sh create`
(`lib/new_character.py`); `stats` holds the nine attributes as die sizes. The old
two-shape converter (`character_schema.py`) is gone: nothing writes the other shape any
more.

## One validator: `schemas.validate_character`

Stats other than the nine attributes (`skill_contest.ATTRIBUTES`, the same in every
campaign) are reported. Only `name` and `level` are required (level 0 counts) —
`race`/`class` are optional flavor.

## Growth: XP, levels, skills that learn (2026-11-11)

One system for every campaign, in `lib/growth.py`; the GM's side is the `gm-growth`
skill. The player's skills learn from close contests in the dice script, a skill
point gained pays 10 × its value in XP, a defeated enemy wounds² × 10 (in
`gm-combat.sh end`), an achievement 20/50/100 % of the current level
(`gm-player.sh award --size`). Level N needs 100 × N² XP. XP only makes growth due
(`GROWTH_DUE`, and "Growth due" in the brief); `gm-player.sh grow` applies one level at
a quiet moment and checks the choice (one attribute, two skills, one perk). Every award
goes into the campaign's `xp.log`. The progression models (milestone, resource-axis) and
the spectacle tiers are gone.

## Death is a state, not a deletion

`kill_character` sets `status: 'dead'` (and HP to 0 on a sheet that still has HP), and stamps `died_at` + cause. The sheet
stays. `become(npc_name)` then copies a party member's sheet into `character.json` and
archives the fallen PC to `fallen/<name>-<id>.json`, clearing `died_at` and the dead status
on the new sheet. Nothing is destroyed, which is what lets the world keep referencing,
mourning, and avenging the dead hero.

The player's wounds, armor and cyberware are on the same sheet, changed only through
`gm-body.sh`. There is no HP and no way back from death: `gm-player.sh hp` and `revive`
were removed.

## Related

- [Onboarding and death hand-off](../flows/onboarding-and-death.md) — the flows that call these
- [NPC model](npc-model.md) — party members carry a parallel `character_sheet`
