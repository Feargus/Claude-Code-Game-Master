---
type: Module
title: The world's own rules
description: A campaign's own mechanics (Bleed, a sea level, a gang's patience) built from a few building blocks, defined once in the ruleset, with a value per holder in rule-state.json.
sources:
  - { resource: /lib/world_rules.py }
  - { resource: /lib/rule_effects.py }
  - { resource: /lib/rule_roll.py }
  - { resource: /lib/rule_time.py }
  - { resource: /lib/rule_states.py }
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
have a `to`; options: a **rate**, `lib/rule_time.py`, applied by `time_manager.py` on every
advance and set, counting whole periods from each holder's `rate_from`; **hysteresis**,
a result's `off_at`, using the stored `on`; **overflow**, back to `back_to` with a mark
due, recorded by `gm-rule.sh mark`; **streak**, `gm-rule.sh break`) **states** (`lib/rule_states.py`: a named state per holder, moved along its `moves`
by `gm-rule.sh move`, or any way by `set`; an `after` moves it on as time passes, from
`entered`; a state's effects run on entering, its `when_off` on leaving) and the
**roll** (`lib/rule_roll.py`: dice plus named amounts and
optionally a counter's value, read from results by `from`; keeps nothing, logs the
roll). Planned: planes, bags and budgets.

## Results that act (`lib/rule_effects.py`)

A result's `effects` run when it comes on, its `when_off` when it goes off; its `gm`
line is printed as "Do now:". The effects: `change` (another rule's value, for the
same holder or `of` another), `rate_of` (a holder's rate in steps), `state` (a move, allowed ones only), `clock` (`start` or `advance`), `condition` and `credits`
(the character's). `world_rules.change` runs them and passes a chain along: a change an
effect makes runs its own results' effects, a rule changes once per holder in a chain,
and a chain stops after `MAX_STEPS` effects. Clocks and consequences are opened through
the active campaign, so a change on a campaign that isn't active runs neither (it says
so). What is checked when the rules are defined: the shape of each effect, that a
change names a rule that exists and can be held by the same holder (or its `of`), and
not its own rule. A rule other rules' effects change can't be removed.

**`on_rule`** (`consequence_manager.py`, an event trigger like `on_clock`): the match is
stored as `"<rule>:<value>@<holder>"`; `world_rules.change` fires it for every value the
change reached, after the effects. The plan and its decisions: `rules-proposal.md` in the
campaign repo.

## What it replaced (2026-11-17)

`stat_schema.vitals` and the sheet's `stats.counters` (`gm-player.sh vital`),
`campaign-overview.json`'s `campaign_rules`, the bible's `signature_systems`, the
campaign's `rules.md`, and `game_core`'s four calculators (`named_track`, `price_roll`,
`reaction_roll`, `guarded_payoff`). Old campaigns are not converted: their old fields
are ignored.
