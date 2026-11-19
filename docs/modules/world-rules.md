---
type: Module
title: The world's own rules
description: A campaign's own mechanics (Bleed, a sea level, a gang's patience) built from a few building blocks, defined once in the ruleset, with a value per holder in rule-state.json.
sources:
  - { resource: /lib/world_rules.py }
  - { resource: /lib/rule_counter.py }
  - { resource: /lib/rule_errors.py }
  - { resource: /lib/rule_effects.py }
  - { resource: /lib/rule_roll.py }
  - { resource: /lib/rule_time.py }
  - { resource: /lib/rule_states.py }
  - { resource: /lib/rule_plane.py }
  - { resource: /lib/rule_bag.py }
  - { resource: /lib/rule_budget.py }
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
written to `rule-state.json` once it is set or changes. Holders use the facts' ids
(`faction:<id>` from `factions.json`; in an older campaign without it, a faction of the
world bible's factions graph), and `world` is one value for the whole world.

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

One module per block, each with the same names, which `world_rules.py` dispatches to
through its table `BLOCKS` (2026-11-17): `FIELDS`, `HOLDS` (whether it keeps a value
per holder; a roll doesn't), `check`, `default`, `outcomes` (what can carry effects),
`rule_lines`, `holder_line`, `summary`, `start` and `set_start` (starting values),
`on_redefine` (fit a holder's value to a redefined rule, or say why not),
`apply_time` (what time moves) and `report_lines`. A new block is a new module and a
line in `BLOCKS`. `RulesError` lives in `rule_errors.py`, so that it is one class
however `world_rules.py` is loaded (as the script behind `gm-rule.sh`, or imported).

Built: the **counter** (`lib/rule_counter.py`: a number in a range; results by range, cumulative unless they
have a `to`; options: a **rate**, `lib/rule_time.py`, applied by `time_manager.py` on every
advance and set, counting whole periods from each holder's `rate_from`; **hysteresis**,
a result's `off_at`, using the stored `on`; **overflow**, back to `back_to` with a mark
due, recorded by `gm-rule.sh mark`; **streak**, `gm-rule.sh break`) the **budget** (`lib/rule_budget.py`: split all at once with `gm-rule.sh split`, each
part's effects once per `per` units; then spent until `refill`, or until its `period`
passes, from `period_from`), the **bag** (`lib/rule_bag.py`: tokens per holder, drawn at random by count, kept out
or put back; `draw_every` draws once per period from `draw_from`; `put`/`take`/`refill`;
an empty bag reports `when_empty`), the **plane** (`lib/rule_plane.py`: two axes per holder, stored as `axes`; regions
by `where` conditions, all that hold are on; a change moves one axis; `rates` per
axis, each with its own `rate_from`), **states** (`lib/rule_states.py`: a named state per holder, moved along its `moves`
by `gm-rule.sh move`, or any way by `set`; an `after` moves it on as time passes, from
`entered`; a state's effects run on entering, its `when_off` on leaving) and the
**roll** (`lib/rule_roll.py`: dice plus named amounts and
optionally a counter's value, read from results by `from`; keeps nothing, logs the
roll).

## Results that act (`lib/rule_effects.py`)

A result's `effects` run when it comes on, its `when_off` when it goes off; its `gm`
line is printed as "Do now:". The effects: `change` (another rule's value, for the
same holder or `of` another), `rate_of` (a holder's rate in steps, and its own point: `toward` or `shift`), `state` (a move, allowed ones only), `tokens` (into or out of a bag), `clock` (`start` or `advance`), `condition` and `credits`
(the character's: for any other holder they are "not done", and a clock started for
another holder names them in its text). A rate with `toward` pulls the value
toward it (`by` above 0) or pushes it away (below 0), from either side
(`rule_time.step`); `rate_of` can turn a pull into a push. `world_rules.change` runs them and passes a chain along: a change an
effect makes runs its own results' effects, a rule changes once per holder in a chain,
and a chain stops after `MAX_STEPS` effects. Clocks and consequences are opened through
the active campaign, so a change on a campaign that isn't active runs neither (it says
so). What is checked when the rules are defined: the shape of each effect, that a
change names a rule that exists and can be held by the same holder (or its `of`), and
not its own rule. A rule other rules' effects change can't be removed.

**A consequence's rule effects** (`consequence_manager.py`, `"type": "rule"`, `gm-consequence.sh
add --rule-effect`): `change`, `rate_of`, `state` or `tokens`, checked when the consequence
is added as a rule's are, `of` resolved to its holder, run through `rule_effects.run` when it
fires.

**The faction bag** (`faction_rules.bag_rule`, "Faction turns"): a repo bag whose tokens
and `draw_every` are built from the current factions each time the rules are read. Two
bag options it uses, open to any bag: `top_up` (below N tokens, add some, and a kind
that ran out) and `"owed": true` on a result (the drawn token waits in the holder's
`owed` queue; `rule_bag.owed`, `settle`). `gm-faction.sh turn --only` settles the oldest
owed turn of that faction, a full turn a joker; `time_manager.print_moments` and the
brief list what is owed.

**`Standing`** (`world_rules.STANDING`): how each faction regards the character. Every
campaign defines it, and scripts read it by this name, so a rule of that name must be a
counter held by factions. A faction's own point is a holder's rate `toward`
(`gm-rule.sh rate --toward`).

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
