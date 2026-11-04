---
name: gm-combat
description: Running a fight — tracking enemies, order, attack and defense, wounds and what they do, death, and ending it. Load when a hostile action is declared or a fight starts. How a roll works is in gm-skills.
---

# Fights

Every roll in a fight is a skill contest. How to build and run one is in [gm-skills](../gm-skills/SKILL.md), and the fighting skills are in [combat skills](../gm-skills/combat.md). This file covers only what is specific to fights.

Before a fight can kill, make the danger readable: see Stakes & Death in `CLAUDE.md`.

## Start

Track every fight with more than one enemy or more than a couple of beats. Each enemy gets its own line, numbered, with the `wounds` from its sheet (`npcs.json` or `mobs.json`): the number of wounds that takes it out.

```
bash tools/gm-combat.sh start
bash tools/gm-combat.sh add-enemy "street thug 1" 2
bash tools/gm-combat.sh add-enemy "street thug 2" 2
```

Contests use the sheet's name ("street thug"), not the numbered line. An enemy without stats is added first, as [Rolling](../gm-skills/SKILL.md#rolling) describes.

## Order

There is no initiative roll. The GM decides who acts when, from the situation.

## Attack and defense

- **Attack:** the attacker's weapon skill, as the active side, against the defender's Guard (close combat) or Evasion (ranged).
- **Several attackers:** a defender facing several attackers in the same beat defends against each, at −2 per other attacker: [several things at once](../gm-skills/SKILL.md#several-things-at-once). Flanking is this and nothing more.
- **Where it lands:** where the attacker aimed. With no aim stated, pick the zone from the fiction. Zones: head, chest, groin, left arm, right arm, left leg, right leg.

## Common situations

Sorted by [advantage or modifier](../gm-skills/SKILL.md#advantage-or-modifier).

| Situation | How |
|---|---|
| Cover | Modifier against the attacker. Full cover blocks the attack. |
| Surprise | The surprised side has disadvantage on ITU. |

## Wounds

A hit deals **1 + quality ÷ 5 wounds**, rounded down: quality 0–4 is 1 wound, 5–9 is 2, 10–14 is 3. Weapons don't change this. Persist the wounds before narrating them.

**The player:** the script applies armor and cyberware itself, and prints what happened.

```
bash tools/gm-body.sh hit chest 2
```

Narrate what it prints: armor that took the blow, chrome that broke, the wound and its effect. `gm-body.sh show` shows the whole body. Healing: `gm-body.sh heal`; armor and chrome: `gm-body.sh repair`.

**Enemies:** each wound counts toward their total. A wound to a limb also disables that limb: record it as a note.

```
bash tools/gm-combat.sh wound "street thug 1" 1 --note "right arm disabled"
```

At their total they are out of the fight: dead, unconscious or fled, as the fiction suggests.

## What wounds do

Each zone of the player's body takes four wounds. Wounds absorbed by armor or chrome don't count.

| Wounds in a zone | Effect |
|---|---|
| 1 | A bruise or scratch. It hurts, nothing more. |
| 2 | Injured: **disadvantage** on rolls that use that part, on the attribute that depends on it most (arm: STR or DFT; leg: AGI; head: LOG or ITU; chest: VIG). Pass it with its reason: `--active-dis DFT "injured right arm"`. |
| 3 | Nearly unusable, but still there. Only very basic use: no weapon or tool use with that arm, no running on that leg (only limping), no clear thinking (head), no cardio or exertion (chest). Rolls that need more aren't possible; basic use still has the disadvantage. |
| 4 | Destroyed. An arm or leg is severed or useless for good. Head, chest or groin: **dead**. |

A wound is the character's own state, so it's always a disadvantage, never a modifier.

## Death

The fourth wound in head, chest or groin kills. There is no dying state and no rescue roll; the earlier wounds and armor damage were the warning. When the player dies, run the Death Protocol in `CLAUDE.md`.

## End

```
bash tools/gm-combat.sh end
```

A fight is won by any means, not only by killing: driving the enemy off, an escape, a trick. Rewards work as in [Reward a great success](../gm-skills/SKILL.md#reward-a-great-success).
