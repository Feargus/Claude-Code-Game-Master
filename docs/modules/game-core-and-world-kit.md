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

## Ruleset syntax is normalized before the core sees it

`progression` accepts a string shorthand (`"progression": "milestone"`). `level` is an accepted alias for `xp-levels` in both
`make_progression` and `spectacle_award`.

Nothing outside `WorldKit` may re-parse `ruleset.json` for these fields. `player_manager`
asks the kit — vitals from `vitals()`, thresholds off the built `progression` object — so a
syntax the kit accepts can never crash a sheet operation, and there is exactly one place a
new shorthand has to be taught.

## Failure modes: two silent, one now audible

The engine prefers degrading to erroring — a half-authored kit should still be playable —
but it means kit bugs surface as *bland play*, not as a stack trace. Both fallbacks that
would silently swap out a world's math now say so.

1. **Unrecognized model name → a warning, then the default.** `make_progression` falls
   through to `MilestoneProgression`, but prints a one-line `[WARNING]` naming the
   offending value. A typo in `ruleset.json`
   (`"xp-level"` for `"xp-levels"`) still costs the campaign its XP math, but it no longer
   does it invisibly. The warnings go to **stderr**, never stdout, so `--json` output on
   the tool wrappers stays parseable.
2. **Missing ruleset → the standard rules.** `WorldKit.__init__` falls back to
   `DEFAULT_RULESET`: "Standard rules", `xp-levels` progression, no vitals, and the canon
   skills of `gm-skills` (2026-11-08; before, "Generic Adventure" with milestone
   progression and `hp`, which left one-shots at level 0 with zero experience awards).
   Vitals are a world's own counters on top of the standard rules, never `hp`: wounds
   replaced it, and every character has a body.
3. **Dangling `rules_doc` → `None`.** `rules_doc_path()` returns `None` when the declared
   file is absent, so a kit copied from a sibling campaign quietly loses its rules prose.
   `overview_seed.py` nulls the dangling pointer at import time rather than repairing it.

To check a live campaign rather than trusting any of this: `bash tools/gm-campaign.sh path`
then read its `ruleset.json`, or run `uv run python lib/world_kit.py info --json`.

## `spectacle_award` is a calculator, not a transaction

`spectacle_award` (`lib/game_core.py`) computes amounts and returns them. It reads no
files and writes none. Persistence, level-up detection, and the DCC follower co-award are
the caller's job — `gm-player.sh award` → `player_manager`. Calling the core function
directly awards nothing.

Its XP is scaled to the gap to the next level rather than being a flat table, so one tier
stays meaningful at level 1 and level 12. The `followers` amount is only applied when the
kit declares a secondary follower currency, which is why the same tier pays differently in
a Dungeon Crawler Carl campaign than in a swords-and-sorcery one.

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

Like `spectacle_award`, all four **compute and return a plain dict — they read no
files and write none**; persistence is the caller's job. Rolls are seedable via
`rng` for deterministic tests, and reuse the module dice roller when it is
omitted. `uv run python lib/game_core.py` runs their edge-case self-check.

Rolls and harm are not in the core any more: every roll is a skill contest
(`lib/skill_contest.py`) and harm is wounds (`lib/body.py`). The old d20 / 2d6 /
dice-pool resolution models and the HP lethality classifier were removed.

## No mechanics Skill is D&D-only any more

`gm-levelup` and `gm-conditions` were 5e and deferred to the KIT block. Both are now
written for this fork's system (attributes as die sizes, skill contests, wounds), so no
skill checks the kit any more.

## Related

- [Player character](player-character.md) — where progression state is persisted
- [World bible](world-bible.md) — the prose spine a kit is drafted from
- [Authoring a world](../flows/author-a-world.md) — who writes `ruleset.json` for an original world
