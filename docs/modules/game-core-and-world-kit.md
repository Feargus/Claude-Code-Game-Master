---
type: Module
title: Game core and World Kit
description: The system-agnostic engine and the per-campaign ruleset that configures it — and the two separate rule surfaces a world actually plays by.
sources:
  - { resource: /lib/game_core.py }
  - { resource: /lib/world_kit.py }
  - { resource: /lib/overview_seed.py }
generated: { by: claude-opus-4-8[1m], at: 2026-08-15T16:22:00Z }
---

# Game core and World Kit

`game_core.py` is the engine every world runs on; `ruleset.json` is the per-campaign
declaration of how *this* world plays; `WorldKit` binds them. The docstrings on both
modules state their own contracts. What follows is only what spans files.

## A world plays by TWO rule surfaces, not one

This is the fact that most often surprises someone editing rules, because the two live
in different files, are loaded by different code, and used to be surfaced to the GM
from the *wrong* one.

| Surface | Lives in | Read by | Holds |
|---|---|---|---|
| **Mechanics** | `ruleset.json` | `WorldKit` | kit identity, stat schema, progression, vitals, skills, **signature_systems** |
| **Legacy flavor** | `campaign-overview.json` → `campaign_rules` | `WorldKit.campaign_rules()` | loot boxes, viewer counts — used only when the kit has no signature_systems |
| **Rules prose** | the file named by `ruleset.rules_doc` | `WorldKit.rules_doc_path()` | long-form rules text, loaded on demand |

**Signature systems on the kit ARE rendered in scene context.** YOUR WORLD'S RULES
prints `WorldKit.signature_systems()` when the ruleset has any (list form, or the
Conan dict-of-name→summary migration case — both normalize to `{name, summary}`),
never truncated. `campaign_rules` is the **legacy fallback** for campaigns that
never got systems onto the kit (DCC's fixture is this case). Adding a system to
`ruleset.json` is no longer a silent no-op.

`overview_seed.py` still exists because imports used to leave `campaign_rules` empty
while the book's systems lived in prose inside a plot description — that path still
feeds the fallback. See [scene-context](scene-context.md).

## Failure modes

The engine prefers degrading to erroring — a half-authored kit should still be playable —
but it means kit bugs surface as *bland play*, not as a stack trace. Both fallbacks that
would silently swap out a world's math now say so.

1. **Missing ruleset → the standard rules.** `WorldKit.__init__` falls back to
   `DEFAULT_RULESET`: "Standard rules", no vitals, and the canon skills of `gm-skills`
   (2026-11-08; before, "Generic Adventure" with `hp`). Growth (XP, levels) is no longer
   a kit setting at all (2026-11-11): it is the same for every campaign (`lib/growth.py`).
   Vitals are a world's own counters on top of the standard rules, never `hp`: wounds
   replaced it, and every character has a body.
2. **Dangling `rules_doc` → `None`.** `rules_doc_path()` returns `None` when the declared
   file is absent, so a kit copied from a sibling campaign quietly loses its rules prose.
   `overview_seed.py` nulls the dangling pointer at import time rather than repairing it.

To check a live campaign rather than trusting any of this: `bash tools/gm-campaign.sh path`
then read its `ruleset.json`, or run `uv run python lib/world_kit.py info --json`.

## Signature-system primitives are calculators, too

`game_core` ships four more world-agnostic building blocks a world's signature
systems are assembled from — every name, threshold, and die comes in as an
argument, none of it is book-specific:

- **`named_track(current, delta, config)`** — a meter with threshold
  consequences (corruption, doom, heat); applies a clamped delta and reports
  which thresholds it newly crossed, up or down. The only one that never rolls.
- **`price_roll(severity, config, rng=None)`** — what a marked action costs the
  actor; rolls, subtracts severity, and reads the cost off a ladder.
- **`reaction_roll(track_value, config, rng=None)`** — an NPC's opening
  disposition, shifted by a track/reputation value onto a tier.
- **`guarded_payoff(config, rng=None)`** — rolled before a marked treasure is
  taken; returns `clean` / `guardian_wakes` / `curse_attaches`.

All four **compute and return a plain dict — they read no
files and write none**; persistence is the caller's job. Rolls are seedable via
`rng` for deterministic tests, and reuse the module dice roller when it is
omitted. `uv run python lib/game_core.py` runs their edge-case self-check.

Rolls and harm are not in the core any more: every roll is a skill contest
(`lib/skill_contest.py`) and harm is wounds (`lib/body.py`). The old d20 / 2d6 /
dice-pool resolution models and the HP lethality classifier were removed.

## No mechanics Skill is D&D-only any more

`gm-levelup` (now `gm-growth`) and `gm-conditions` were 5e and deferred to the KIT block. Both are now
written for this fork's system (attributes as die sizes, skill contests, wounds), so no
skill checks the kit any more.

## Related

- [Player character](player-character.md) — where progression state is persisted
- [World bible](world-bible.md) — the prose spine a kit is drafted from
- [Authoring a world](../flows/author-a-world.md) — who writes `ruleset.json` for an original world
