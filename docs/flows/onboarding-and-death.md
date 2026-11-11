---
type: Flow
title: Onboarding and the death hand-off
description: The holodeck door — one question, then the room — and how the story continues after the PC dies rather than ending.
sources:
  - { resource: /lib/new_character.py }
  - { resource: /tools/gm-player.sh }
  - { resource: /lib/player_manager.py }
  - { resource: /lib/opening.py }
  - { resource: /CLAUDE.md }
  - { resource: /.claude/commands/create-character.md }
generated: { by: claude-opus-4-8[1m], at: 2026-08-15T12:45:56Z }
verified: { by: claude-fable-5, at: 2026-08-13T15:15:27Z }
---

# Onboarding and the death hand-off

Two flows, one shared conviction: **the mechanics are not the point, and the player should
never be made to do bookkeeping to keep playing.** Entering a world is the holodeck
door — one question, then the room. Dying costs one choice. The book stays on the
chair; do not make them wait through a census to talk to someone they came for.

## Entry: one question, then the interview

"Who are you in this world?" has two answers: someone from this world (an NPC in the
campaign) or someone of the player's own (a one-line concept). Then the GM runs the
`/create-character` interview, the fast way by default: it proposes a complete character
and the player changes what they like. It is not a rules engine: the GM suggests values
(d12 attributes, luck 3, a few skills), the player may choose anything.

The interview is a command, not an agent: an agent runs once and can't ask the player
anything.

The finished interview is saved with **`bash tools/gm-player.sh create '<json>'
[--canon "<NPC>"] [--replace]`** (`lib/new_character.py`). It fills everything left out
with defaults, checks only what scripts rely on (attribute names and die sizes, zone
names), and wires the new PC in the same places [`become()`](#become-is-the-only-path-that-moves-a-sheet)
does:

- it **refuses to overwrite a sitting PC**; `--replace` is the explicit hand-off, and it
  archives the outgoing sheet to `fallen/` before writing
- it sets `current_character` on `campaign-overview.json`, which is what session start,
  status, and world stats read
- it moves nothing: in a new campaign the opening comes after it (`gm-session.sh opening`)
- `--canon` resolves the NPC alias-aware (`_find_entity_name`), uses the canonical key as
  the PC's name, and marks the NPC `is_player_character` (plus `is_party_member: false` /
  `became_pc: true`) so scene context stops voicing the PC as an NPC standing nearby

## Death: persist, narrate, then offer the hand-off

Order matters and is stated in `CLAUDE.md`: persist first, narrate second, menu third.
Offering the menu before the death has landed narratively is the failure mode this
ordering exists to prevent.

1. `gm-player.sh kill --cause "<how>"` — sets `status: dead`, HP 0, stamps
   `died_at`. Log it as a fact; record any consequence it triggers.
2. Narrate the death with weight. **No menu yet.**
3. Offer three continuations: take over a **party member**, roll a **new character**, or
   step in as a **canon figure**. (Solo with no party and no fitting canon figure: options
   2 and 3 only.) Rolling a new character spawns `create-character`, which
   has no 5e wizard builder any more. `CLAUDE.md` SWAP is the runtime instruction.
4. Swap, bridge the fiction, resume.

That hand-off is the only way on — death moves the story to someone else and is not
undone. (There used to be a `revive` command; it was removed with HP.) See
[the player character sheet](../modules/player-character.md).

## `become()` is the only path that moves a sheet

`gm-player.sh become "<name>"` (`lib/player_manager.py:542`) does five things in one call:
resolves the name **alias-aware** (so "Princess Donut" finds "Donut"), flattens the party
member's `character_sheet` into `character.json`, archives the fallen PC to
`fallen/<name>-<id>.json`, updates `current_character` on the overview, and **demotes the
promoted NPC from the party** (`is_party_member: false`, `became_pc: true`) so they aren't
tracked twice. The NPC record itself stays — the world still knows who they were.

Its two hard preconditions are worth knowing before the moment arrives, because both fail
loudly mid-hand-off:

- the target must already be `is_party_member` — promote first (`gm-npc.sh promote`)
- the target must have a `character_sheet`

The new sheet gets `status: alive` and has `died_at` / `cause` stripped, so a sheet that
was previously killed can be taken over cleanly.

## Nothing is deleted

The fallen PC's sheet is archived, not removed; the dead status is a field, not an absence.
That is what lets the world keep referencing, mourning, looting, and avenging a dead hero —
the "the show goes on" framing in `CLAUDE.md` is backed by state that still exists.

## Related

- [The player character sheet](../modules/player-character.md)
- [NPC model](../modules/npc-model.md) — where party sheets live before the swap
