---
type: Module
title: The player character sheet
description: Why the sheet has two shapes, which one is canonical, and how XP, death, and the spectacle award are persisted.
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

## XP delegates to the kit, then falls back

`_xp_thresholds` asks the kit's built `progression` object — not `ruleset.json` — and uses
its thresholds **only when the model is `xp-levels` (or its `level` alias) and thresholds
are present**. Anything else — milestone kits, resource-axis kits, an `xp-levels` kit that
forgot its table — silently uses `DEFAULT_XP_THRESHOLDS`. So a milestone world still
accrues levels if something calls `award_xp`. Going through the kit is what keeps every
ruleset shorthand it accepts (a bare `"progression": "milestone"`, the `level` alias) from
raising here.

That table also sets the ceiling: `_max_level` is its length, so `MAX` and
`ready_to_level` come from the kit. A world declaring eleven thresholds tops out at level
12; 20 is only where the *default* table ends, not a rule of the engine.

**Reads never write.** `_xp_view` returns `{current, next_level}` off the sheet — honoring
both the legacy plain-integer XP and the canonical object — and creates nothing. A
milestone or resource-axis sheet that has never tracked XP therefore does not sprout an
`xp` object from a status check, a spectacle beat, or an HP change. `award_xp` is the only
thing that writes the object, because that call is an explicit grant.

`award_xp` prints the literal token `LEVEL_UP` on a level gain, and `get_xp_status` prints
`READY_TO_LEVEL_UP`. Those strings are the interface: the GM watches for them to trigger
the level-up ceremony. Changing their wording breaks the routing described in
[lean core and skill routing](../conventions/lean-core-and-skill-routing.md).

## Spectacle awards route back through `award_xp`

`award_spectacle` computes amounts via `game_core.spectacle_award`, then — for XP-based
kits — applies them **through `award_xp`** rather than writing XP directly, specifically
so `LEVEL_UP` detection still fires. A spectacle beat can therefore level the character,
which is the point: non-kill achievements advance the same axis kills do. See
[game core and World Kit](game-core-and-world-kit.md).

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
