---
type: Module
title: The world's own rules
description: A campaign's own mechanics (Bleed, a sea level, a gang's patience) built from a few building blocks, defined once in the ruleset, with a value per holder in rule-state.json.
sources:
  - { resource: /lib/world_rules.py }
  - { resource: /tools/gm-rule.sh }
  - { resource: /.claude/skills/gm-rules/SKILL.md }
---

# The world's own rules

Every campaign plays by the repo's rules (skill contests, wounds, growth, clocks,
consequences, facts). A world adds a few rules of its own on top, made with the world
in `/new-game` or `/import` (the `gm-rules` skill), and played from the brief.

## Where things live

| What | File | Written by |
|---|---|---|
| The rules: one building block each, with this world's numbers and words | `ruleset.json` → `rules` | `gm-rule.sh define` (at creation) |
| Rule lines that are no mechanic (prices, the currency) | `ruleset.json` → `plain_rules` | `gm-rule.sh plain` |
| Where each rule stands, per holder | `rule-state.json` | `gm-rule.sh change`/`set`/`reveal`/`hide`, the character's creation, a hand-over |
| Every change, with its cause | `rules.log` (per machine, not in git) | the same |

A rule says who can hold it (`held_by`: `player`, `npc`, `faction`, `location`,
`world`). Each holder has its own value, which starts at the rule's `start` and is
written to `rule-state.json` once it is set or changes. Holders use the facts' ids;
`faction:<id>` names a faction of the world bible's factions graph until factions get
records of their own, and `world` is one value for the whole world.

## What reads them

- **The brief**, YOUR WORLD'S RULES (`world_rules.brief_lines`): the plain lines, then
  each rule in full (summary, when, notes, results, its command) with the character's,
  the world's and the factions' values. Never cut.
- **The cards**: a person's or a place's values, with the results on now
  (`holder_lines`).
- **The HUD** (`gm-statusline.sh`, in jq): the character's known values, `Bleed 4/6`.
- **`gm-player.sh show`**: the character's values, hidden ones marked.

## Hand-overs

When the story passes to another character (`handover.move_id`), the values follow the
people like the facts do: the outgoing character's become the new NPC's, a canon NPC's
become the player's. Values of rules the new holder's kind can't hold are dropped, with
a note.

## Building blocks

Built: the **counter** (a number in a range; results by range, cumulative unless they
have a `to`). Planned, with the effects that let one rule change another and the
`on_rule` trigger for consequences: rolls, rates, hysteresis, overflow, streaks, states,
planes, bags and budgets. The plan and its decisions: `rules-proposal.md` in the
campaign repo.

## What it replaced (2026-11-17)

`stat_schema.vitals` and the sheet's `stats.counters` (`gm-player.sh vital`),
`campaign-overview.json`'s `campaign_rules`, the bible's `signature_systems`, the
campaign's `rules.md`, and `game_core`'s four calculators (`named_track`, `price_roll`,
`reaction_roll`, `guarded_payoff`). Old campaigns are not converted: their old fields
are ignored.
