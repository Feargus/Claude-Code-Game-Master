# Game core and the world's rules

*Claude, 2026-11-19: kept from the upstream docs, not yet rewritten. 2026-11-23: the
World Kit is gone.*

`game_core.py` is the engine every world runs on; `ruleset.json` holds what *this*
world adds: its own rules (`rules` and `plain_rules`), read and written by
`lib/world_rules.py` ([the world's own rules](world-rules.md)). The brief shows them as
YOUR WORLD'S RULES. `gm-rule.sh define` makes the file; a world without rules of its own
has none, and plays by the repo's rules alone.

Until 2026-11-17 a world's rules were spread over four places (the bible's
`signature_systems`, `campaign-overview.json`'s `campaign_rules`, `rules.md`, and the
kit's `systems` with `stat_schema.vitals`), shown twice in the brief, and only one of
them connected to a command. All four are gone; old campaigns keep the fields, which
nothing reads.

Until 2026-11-23 `ruleset.json` also held a "World Kit": a name, declared skills and
active agents, drafted from the bible (`gm-extract.sh draft-ruleset`) and shown as the
brief's KIT section. The name repeated the world's, nothing declared skills any more
(they are `lib/skills.py`: the canon list and the campaign's improvised ones), and nothing
read the agents. Old campaigns keep the fields, which nothing reads.

The rolls, attributes, skills, wounds and growth (XP, levels) are the same for every
campaign (`gm-skills`, `gm-combat`, `lib/growth.py`). To check a live campaign:
`bash tools/gm-rule.sh list`.

## What is left in the core

Conditions (`add_condition`, `remove_condition`). Rolls and harm are not in the core:
every roll is a skill contest (`lib/skill_contest.py`) and harm is wounds
(`lib/body.py`). A world's own mechanics are `lib/world_rules.py`.

## Related

- [The world's own rules](world-rules.md) — the building blocks, values per holder
- [Player character](player-character.md) — where progression state is persisted
- [World bible](world-bible.md) — the prose spine a world is drafted from
- [Authoring a world](../flows/author-a-world.md) — who writes `ruleset.json` for an original world
