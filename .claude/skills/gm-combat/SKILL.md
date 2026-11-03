---
name: gm-combat
description: Running a fight — tracking enemies, order, attack and defense, common situations, damage, dying, and ending it. Load when a hostile action is declared or a fight starts. How a roll works is in gm-skills.
---

# Fights

Every roll in a fight is a skill contest. How to build and run one is in [gm-skills](../gm-skills/SKILL.md), and the fighting skills are in [combat skills](../gm-skills/combat.md). This file covers only what is specific to fights.

Before a fight can kill, make the danger readable: see Stakes & Death in `CLAUDE.md`.

## Start

Track every fight with more than one enemy or more than a couple of beats. Each enemy gets its own line, numbered, with the HP from its sheet (`npcs.json` or `mobs.json`):

```
bash tools/gm-combat.sh start
bash tools/gm-combat.sh add-enemy "street thug 1" 18
bash tools/gm-combat.sh add-enemy "street thug 2" 18
```

Contests use the sheet's name ("street thug"), not the numbered line. An enemy without stats is added first, as [Rolling](../gm-skills/SKILL.md#rolling) describes.

## Order

There is no initiative roll. The GM decides who acts when, from the situation.

## Attack and defense

- **Attack:** the attacker's weapon skill, as the active side, against the defender's Guard (close combat) or Evasion (ranged).
- **Several attackers:** a defender facing several attackers in the same beat defends against each, at −2 per other attacker: [several things at once](../gm-skills/SKILL.md#several-things-at-once). Flanking is this and nothing more.

## Common situations

Sorted by [advantage or modifier](../gm-skills/SKILL.md#advantage-or-modifier).

| Situation | How |
|---|---|
| Cover | Modifier against the attacker. Full cover blocks the attack. |
| Surprise | The surprised side has disadvantage on ITU. |
| Wounded (half HP or less) | −2 to physical rolls. |

## Damage

A hit deals HP damage equal to its quality, so quality 0 is at most a graze. Weapons don't change this. Persist the damage before narrating it:

```
bash tools/gm-combat.sh hp "street thug 1" -7    # an enemy
bash tools/gm-player.sh hp Fearghas -7           # the player
bash tools/gm-npc.sh hp "Carl" -4                # a party member
```

**Massive damage:** a single hit dealing at least the target's max HP kills outright.

## 0 HP

- **Mobs and minor NPCs** are out of the fight.
- **The player and important NPCs are dying.** Each beat, an Endurance roll against difficulty 20, rolled like the nerve toxin in [Rolling](../gm-skills/SKILL.md#rolling). Three successes stabilize them, three failures kill them.
- **When the player dies,** run the Death Protocol in `CLAUDE.md`.

## End

```
bash tools/gm-combat.sh end
```

A fight is won by any means, not only by killing: driving the enemy off, an escape, a trick. Rewards work as in [Reward a great success](../gm-skills/SKILL.md#reward-a-great-success).
