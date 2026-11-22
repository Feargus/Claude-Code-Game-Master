# Game core and World Kit

*Claude, 2026-11-19: kept from the upstream docs, not yet rewritten.*

`game_core.py` is the engine every world runs on; `ruleset.json` is the per-campaign
declaration of what *this* world adds; `WorldKit` reads it. The docstrings on both
modules state their own contracts. What follows is only what spans files.

## One place for a world's rules

`ruleset.json` holds the kit's name, the skills it declares, its active agents, and the
world's own rules (`rules` and `plain_rules`, read and written by `lib/world_rules.py`:
[the world's own rules](world-rules.md)). The brief shows them as YOUR WORLD'S RULES.

Until 2026-11-17 a world's rules were spread over four places (the bible's
`signature_systems`, `campaign-overview.json`'s `campaign_rules`, `rules.md`, and the
kit's `systems` with `stat_schema.vitals`), shown twice in the brief, and only one of
them connected to a command. All four are gone; old campaigns keep the fields, which
nothing reads.

`overview_seed.py` writes a book's name, genre and tone into `campaign-overview.json`
at import; nothing about rules.

## Failure modes

1. **Missing ruleset → the standard rules.** `WorldKit.__init__` falls back to
   `DEFAULT_RULESET`: "Standard rules", no rules of its own, and the canon skills of
   `gm-skills`. Growth (XP, levels) is no kit setting: it is the same for every
   campaign (`lib/growth.py`).
2. **A world with no rules of its own** has no YOUR WORLD'S RULES section in the
   brief, and `gm-rule.sh` says so. A quick world from one sentence has one rule of its
   own, `Standing`, which every world defines.

To check a live campaign: `bash tools/gm-rule.sh list`, or
`uv run python lib/world_kit.py info`.

## What is left in the core

Conditions (`add_condition`, `remove_condition`). Rolls and harm are not in the core:
every roll is a skill contest (`lib/skill_contest.py`) and harm is wounds
(`lib/body.py`). A world's own mechanics are `lib/world_rules.py`.

## Related

- [The world's own rules](world-rules.md) — the building blocks, values per holder
- [Player character](player-character.md) — where progression state is persisted
- [World bible](world-bible.md) — the prose spine a kit is drafted from
- [Authoring a world](../flows/author-a-world.md) — who writes `ruleset.json` for an original world
