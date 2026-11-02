---
name: gm-skills
description: How every dice roll works. Load whenever the player attempts something uncertain or anything is rolled (attack, defense, resistance, any check): when to roll, choosing the skill and attributes, running the contest, narrating the quality, and failing forward.
---

# Attributes and skills

Every roll uses a skill. There are no checks on attributes alone. A skill is a way of using your attributes, so combat, defense, resistance (saving throws), tradecraft and knowledge are all skills.

This file defines when to roll, what is rolled, and how to read the result.

## When to roll

- Uncertain outcome: it could go either way
- Stakes matter: success or failure changes the story
- Risk of harm: physical, social, or resource loss
- Contested: someone opposes it
- Time pressure

**Don't roll for:** trivial tasks, impossible tasks, routine professional work, or anything with no meaningful consequence for failure.

## Attributes

Attributes are die sizes (about 6 to 20). They form a pyramid: four physical, three mental, two social, Luck on top.

| | Power | Finesse | Resistance |
|---|---|---|---|
| Luck | LCK | | |
| Social | Presence (PRS) | Empathy (EMP) | |
| Mental | Logic (LOG) | Intuition (ITU) | Nerve (NRV) |
| Physical | Strength (STR) | Agility (AGI), Deftness (DFT) | Vigor (VIG) |

- **STR, Strength:** force. Pushing, pulling, lifting, breaking, striking, grabbing.
- **AGI, Agility:** the whole body in motion. Balance, grace, speed, reflexes; the gymnast and the parkour runner.
- **DFT, Deftness:** the hands. Hand-eye coordination, fine motor skill, aiming, shooting, picking locks, steering.
- **VIG, Vigor:** the body holding out. Stamina, toughness, resisting poison, disease and exhaustion.
- **LOG, Logic:** knowing by reasoning. Deducing, analyzing, deliberate thought, learned knowledge.
- **ITU, Intuition:** knowing without reasoning, about yourself and your surroundings. Gut feeling, situational awareness, noticing what matters, introspection ("why do I trust him?"), mental muscle memory.
- **NRV, Nerve:** the mind holding out. Courage, calm under pressure, concentration, resisting fear, pain and manipulation.
- **PRS, Presence:** pushing outward. Force of personality, commanding a room, impressing, threatening.
- **EMP, Empathy:** reaching into others. Reading people, connecting, mirroring, knowing what someone feels or wants. Strictly about other people.
- **LCK, Luck:** never rolled. The roll script spends it automatically on narrow failures.

**Attribute order.** The three attributes of a roll are always written in this order: STR, AGI, DFT, VIG, LOG, ITU, NRV, PRS, EMP. The anchor is marked, not moved.

## Building a roll

1. **Choose the skill** from the index below. Open the category file for its applications.
2. **The anchor attribute is always one of the three dice.** It is what makes the skill that skill: you can't shoot with Empathy.
3. **Choose the other two from the description of the action.** The listed applications are examples, not a closed list. The same skill rolls differently depending on how it is done: a careful aimed shot is not a snap shot while diving. Read the player's prose sensibly, not arbitrarily; the description is their argument for the attributes. NPCs follow the same rules.
4. **Attributes may repeat** (STR, STR, VIG). Very specialized one-off actions may even use one attribute three times (arm-wrestling: STR, STR, STR). Avoid doubling Intuition; it already appears almost everywhere.

Pass the names of the skill and attributes to the script. It looks up all the numbers itself: die sizes, skill value and luck. See [Rolling](#rolling).

**One task, several skills.** Different parts of one weapon or task can use different skills. A longsword thrust is Fencing, a cut is Slashing, a mordhau strike is Bludgeons, and trapping an arm with the pommel is Brawling.

## Untrained

A character without the skill rolls normally and adds a penalty instead of a skill value:
- **−3** for Tradecraft and Knowledge skills (learned over years, through work and study)
- **−1** for everything else

Improvised skills follow the same rule by category: brain surgery is −3, arm-wrestling is −1.

## Several things at once

Doing several things at once is always allowed, at a penalty to every roll involved. Abilities that reduce this, such as ambidexterity, are traits.

## Cooperating with yourself

A character may use one skill to set up another, mainly so a strong skill can make up for a weak one. Netrunning maps a bomb's wireless trigger, then Tech disarms it.
- Both rolls use the **same difficulty**.
- The quality of the supporting roll becomes a modifier on the main roll.
- Preparing takes time. In a fight, that's a beat.

Two rolls that each reach a useful part of the goal, without any bonus passed between them, are always allowed too. Both count as good play and good writing.

## Improvised skills and statuses

Rare actions don't need a permanent skill. When nothing in the index fits, check `improvised-skills.md` in the active campaign's folder, then invent a skill on the spot: name, category, anchor, a one-line description, and the applications used. Add it to that file with status `improvised`, creating the file if needed. New applications for existing skills go there the same way.

Never edit the skill files in this folder during play. They hold the canon skills, and only the player changes them.

| Status | Meaning | Where |
|---|---|---|
| `canon` | Fixed. Use as written. | This folder |
| `improvised` | Invented in play, in effect immediately. | Campaign folder |
| `banned` | The player disliked it. Never use it, and never invent anything like it again. | Campaign folder |

Only the player changes statuses. The player promotes an improvised skill by moving it to this folder.

Narrower expertise comes from **traits**, not extra skills. For example, a piloting trait can give +2 for aircraft only.

## Rolling

Every roll is a contest between an **active** side, which acts, and a **reactive** side, which resists. Either side can be a flat difficulty instead of a character.

1. **Decide the stakes first:** the difficulty, if there is one, and what a failure will cost. Never tell the player.
2. **Build the roll** as above.
3. **Run the contest.**
4. **Narrate the quality.** Never show dice, numbers, difficulties or skill names to the player.

```
bash tools/gm-skill-contest.sh \
  --active Fearghas "Long guns" AGI DFT ITU \
  --reactive "street thug" Evasion AGI ITU NRV \
  --active-adv DFT --reactive-dis NRV \
  --mod +2 "good feint" --mod -2 "darkness"

bash tools/gm-skill-contest.sh --active Fearghas Larceny DFT DFT LOG --reactive-dc 20 "sturdy lock"
bash tools/gm-skill-contest.sh --active-dc 20 "nerve toxin" --reactive Fearghas Endurance VIG VIG ITU
```

- **Names:** the player, an NPC from `npcs.json`, or a mob from `mobs.json`. Mobs have no personality, and their instances are interchangeable. Mobs you invent go in the campaign's `mobs.json`.
- **Unknown name or no stats:** the script refuses. Add the entry, using `mobs.json` in this folder as the scale, then roll again.
- **Advantage and disadvantage** belong to an attribute and affect all its dice in the roll. Repeat the attribute to stack them.
- **`--mod`** is one net list, relative to the active side: positive helps the active side, negative helps the reactive side. Leave out anything that affects both sides equally. Every modifier has a label.
- **Untrained:** still write the skill's real name, add `--active-untrained` or `--reactive-untrained`, and give the penalty from [Untrained](#untrained) (−1 or −3) as `--mod VALUE "untrained skill"`. If the reactive side is untrained, the penalty helps the active side, so its sign flips.
- **Difficulties:** easy 15, normal 20, hard 25, very hard 30 or more.

The script prints one line, such as `quality: 7`. Quality 0 or more means the **active** side succeeds, so a tie goes to the active side. When the player is the reactive side, read the result from their opponent's point of view: a positive quality is bad for the player.

`quality: 0 (lucky)` or `quality: -1 (lucky)` means the player's luck turned a narrow loss into a narrow win. Luck is automatic, belongs to the player alone, and is never a choice. The narration may give it the flavor of a lucky break, never in game terms.

## Narrate by quality

| Quality | Result |
|---|---|
| Above 20 | Critical success: more than they hoped for, a bonus or a flourish, a window opens. |
| 11 to 20 | Clean success: it looks easy, with an extra benefit. |
| 0 to 10 | Success with a cost that fits the activity: materials when crafting, time when traveling, a wrong target or zone in combat. |
| −1 to −10 | Failure: the goal is denied, and something small but visible is spent. |
| −11 to −20 | Bad failure: a clear failure plus a complication. |
| Below −20 | Critical failure: a mishap. |

**No failure is free.** A near miss costs less, never nothing. Name what was spent, never "you fail, nothing changes". Use these as a guide:

| | −1 to −10 | −11 to −20 | Below −20 |
|---|---|---|---|
| **Physical** | A named cost: position lost, footing, noise made, a tool or supply spent. Further down, a resource spent and attention drawn. | Minor harm. | Real harm. With lethal, telegraphed stakes, this can be a death-gate hit. Reserve that for earned, signposted danger. |
| **Social** | Refused, and their attitude shifts or a bystander notices. Further down, attitude turns negative and a concrete price is paid: a favor burned, a term worsened, something taken. | They act against you. How that looks comes from the NPC's own goals and power, and sometimes it's ugly. | Hostile, and word spreads. |
| **Information** | Partial and misleading in a way that matters. Further down, nothing usable, and the asking costs: time burned, a lead gone cold, an opportunity closed while you dug. | A wrong conclusion believed true. | It triggers a ward or alerts whoever owns the secret. |

Whenever a failure creates ongoing fallout: `bash tools/gm-consequence.sh add "[what happens]" "[when]" [--trigger-type ...]`. Persist the cost (mood, HP, inventory, death) BEFORE narrating it.

## Reward a great success

A clever, effective or unique solve EARNS progress, not just a kill. On a strong success (quality above 10, or an inventive approach), grant spectacle XP before narrating: `bash tools/gm-player.sh award --tier minor|major|legendary --reason "..."`. See `gm-craft → Reward the spectacle`.

## Fail forward (critical)

A failed roll NEVER means "nothing happens". It means "something DIFFERENT happens".
- Failed lockpick? The pick breaks inside. Now you need the key or a louder way.
- Failed persuasion? The NPC keeps what they know, and word of who came asking travels.
- Failed stealth? Not caught yet, but you knocked something over. Now you're on a timer.

Framework: (1) What did they try? (2) What was the intent? (3) What goes sideways into a NEW situation? (4) What choice does that create?

**Fail forward isn't immortality.** "Something different happens" can include death when the stakes were lethal and telegraphed: an over-matched threat, an ignored warning, a tightening string of failures. Don't soften a self-inflicted lethal outcome into a free pass. On PC death, run the Death Protocol (`CLAUDE.md`).

**Fail forward isn't free.** Decide what the roll COSTS before rolling. On a failure the stated goal does NOT happen, and that cost lands in the same beat. "Something different" means different and poorer, not different and equally good.

**Don't hand the stake back for free.** A failed roll's goal is denied, and a failed ask is not an invitation to re-ask the same way. If the fiction leaves a door open, such as an NPC who could still be swayed or a lock that could still be forced, opening it should cost something new. The roll reopens when the situation MATERIALLY changes: new leverage, new information, a different approach, or a price paid.

## Index

| Skill | Category | Anchor | Untrained | In short |
|---|---|---|---|---|
| Brawling | [Combat](combat.md) | STR | −1 | Fighting with the body itself. |
| Bludgeons | [Combat](combat.md) | STR | −1 | Swung weight and momentum. |
| Slashing | [Combat](combat.md) | AGI | −1 | Flowing cuts, sweeps and whips. |
| Throwing | [Combat](combat.md) | AGI | −1 | Anything that leaves the hand, or arrives in it. |
| Evasion | [Combat](combat.md) | AGI | −1 | Ranged defense: not being where the bullet goes. |
| Fencing | [Combat](combat.md) | DFT | −1 | Thrusts, feints and precise stabs. |
| Handguns | [Combat](combat.md) | DFT | −1 | Pistols and guns held without a stock. |
| Long guns | [Combat](combat.md) | DFT | −1 | Guns braced on the shoulder. |
| Guard | [Combat](combat.md) | ITU | −1 | Close-combat defense: reading the attack in time. |
| Heavy weapons | [Combat](combat.md) | NRV | −1 | Guns you can't just pick up and fire. |
| Endurance | [Resistance](resistance.md) | VIG | −1 | The body holding out. |
| Composure | [Resistance](resistance.md) | NRV | −1 | The mind holding out. |
| Athletics | [Physical](physical.md) | STR | −1 | Force: climbing, swimming, lifting. |
| Acrobatics | [Physical](physical.md) | AGI | −1 | Grace: balance, parkour, falling well. |
| Stealth | [Physical](physical.md) | AGI | −1 | Not being noticed. |
| Rigging | [Vehicles](vehicles.md) | AGI | −1 | Being the machine. |
| Piloting | [Vehicles](vehicles.md) | DFT | −1 | Driving or flying by hand and eye. |
| Investigation | [Perception](perception.md) | LOG | −1 | Deliberate searching and reasoning. |
| Awareness | [Perception](perception.md) | ITU | −1 | Noticing anything. |
| Insight | [Perception](perception.md) | EMP | −1 | Reading people. |
| Persuasion | [Social](social.md) | PRS | −1 | Changing minds openly. |
| Intimidation | [Social](social.md) | PRS | −1 | Making people afraid enough to comply. |
| Streetwise | [Social](social.md) | PRS | −1 | Knowing the street. |
| Deception | [Social](social.md) | EMP | −1 | Making people believe what isn't true. |
| Corpspeak | [Social](social.md) | EMP | −1 | Knowing the suits. |
| Larceny | [Tradecraft](tradecraft.md) | DFT | −3 | Hands where they shouldn't be. |
| Tech | [Tradecraft](tradecraft.md) | LOG | −3 | Making machines work, or stop working. |
| Netrunning | [Tradecraft](tradecraft.md) | LOG | −3 | All computer work worth a roll. |
| Medicine | [Tradecraft](tradecraft.md) | LOG | −3 | Keeping bodies working. |
| Science | [Knowledge](knowledge.md) | LOG | −3 | Academic and theoretical knowledge. |
| Tactics | [Knowledge](knowledge.md) | LOG | −3 | Win first, then fight. |
