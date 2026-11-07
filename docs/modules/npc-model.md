---
type: Module
title: The NPC model
description: What an NPC carries beyond a description — inner life, canonical voice lines, party-member sheets, and combat stats.
sources:
  - { resource: /lib/npc_manager.py }
  - { resource: /lib/skill_contest.py }
generated: { by: gk-a8r14q, at: 2026-08-14T18:00:37Z }
verified: { by: claude-fable-5, at: 2026-08-13T14:16:30Z }
---

# The NPC model

An NPC in `npcs.json` is four things stacked on one key: a description, an **inner life**,
a **voice**, and — if promoted — a full **character sheet**. The stacking is additive by
design, so an NPC extracted from a book with nothing but a name still loads.

## `voice` and `context` are not the same field

This trips people every time:

| Field | Holds | Read by |
|---|---|---|
| `context` | **canonical voice lines** — verbatim dialogue from the source | `get_voice()` (`lib/npc_manager.py:274`) |
| `voice` | a free-text *description* of how they speak | `get_inner_life()` |

So "set the NPC's voice" is ambiguous: `set-inner` writes the description, while the
quotable lines live in `context`, which the RAG enhancement pass populates.
The session brief prints lines from `context` under the heading "NPC VOICES", so an NPC
with a rich `voice` description but an empty `context` speaks no lines at all.

`get_voice` is explicitly read-only and never mutates `context` — enhancement writes it,
play only reads it.

## Inner life defaults

`INNER_LIFE_FIELDS = ('goal', 'current_mood', 'voice', 'bonds')`, all optional,
all defaulted on read (`current_mood` → `'neutral'`). `current_mood` persists across
sessions — an NPC you angered stays angry.

There is no `secret` field any more (2026-11-07): what an NPC hides is a fact with the NPC
as its only holder, shown under them in the brief and marked `[HIDDEN FROM PLAYER]`.

## Party members carry a second sheet, in a different shape

Promote copies existing combat stats into the party sheet when the NPC has them
(written by the GM); defaults apply only to a
genuinely statless NPC, and the output says which. Note what this is **not**: it is a
nested sheet on the NPC record, not the flat top-level shape the PC uses
(see [player character](player-character.md)). The two never converge except in
`gm-player.sh become`, which copies a party sheet into `character.json` and flattens it.

`demote_from_party_member` keeps the `character_sheet` — history is preserved, only the
flag flips. Party membership is also what makes an NPC count as *present* everywhere,
regardless of location tags (`lib/consequence_manager.py:263`).

## Combat stats are written by the GM

Extracted NPCs carry no game numbers. When an NPC needs to roll, the GM gives them
`stats` (the nine attributes as die sizes), `skills` and `wounds` in `npcs.json`, scaled
by `.claude/skills/gm-skills/mobs.json`. The skill contest refuses an NPC without stats
and says so. (The old `npc_stats.py`, which assigned D&D HP/CR tiers, is gone.)

## Location tags: one field, since 2026-08-13

`tags.locations` is the only location field — the legacy `location_tags` split was
unified (`lib/tag_unify.py`, run at import normalize). Campaigns imported before then
need the one-time `gm-npc.sh unify-tags`; see
[the tag-split gotcha](../gotchas/npc-location-tag-split.md).

## Related

- [Entity graph](entity-graph.md) — how NPC names resolve despite drift
- [RAG stack](rag-stack.md) — what fills `context` with real dialogue
