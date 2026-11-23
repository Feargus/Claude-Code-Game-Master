# Game core and the world's rules

`game_core.py` is the engine every world runs on. `ruleset.json` holds what *this*
world adds, its own rules (`rules` and `plain_rules`), read and written by
`lib/world_rules.py` ([the world's own rules](world-rules.md)); the brief shows them as
YOUR WORLD'S RULES. `gm-rule.sh define` makes the file; a world without rules of its own
has none and plays by the repo's rules alone.

The rolls, attributes, skills, wounds and growth (XP, levels) are the same for every
campaign (`gm-skills`, `gm-combat`, `lib/growth.py`); the skills are the canon list and
the campaign's improvised ones (`lib/skills.py`). To check a live campaign:
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
