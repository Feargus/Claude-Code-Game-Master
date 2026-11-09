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

Anyone can try any skill. A skill missing from the sheet counts as −1; the script does this itself, so just write the skill's real name. A mob or NPC can set its own value with `"default"` in its skills, for example a boss who is competent at everything, or vermin hopeless at anything they weren't built for. Improvised skills are untrained for everyone until someone learns them.

## Advantage or modifier

Ask: **does it change the person, or the task?** The roll already assumes the character is fit and trying their best; only what differs from that counts.

- **The person: advantage or disadvantage** on the attribute it affects. What the character currently *is*: hurt, tired, drunk, frightened, surprised, rested, on a stim. A positive state must already exist in the story before the roll (he slept; he took the stim). Words in the action such as "focused" or "carefully" don't create one. Surprise is the surprised side's disadvantage, usually on ITU, not a bonus for the other side.
- **The task: a modifier.** What the character *has* or is *in*, which would affect anyone doing it: gear, cover, height, light, footing, time pressure, help from others. Cyberware's active functions are gear that happens to be inside the body: a zoom is a modifier like a scope.
- **Rule values: a modifier of fixed size.** Set by the rules or the sheet, not judged in the moment: [several things at once](#several-things-at-once), a trait, the quality of a supporting roll.

Permanent features are on the sheet already, as die sizes, skills or traits. Don't add them again.

**Each fact counts once:** in the difficulty, which describes the task in general, or as a modifier or advantage, which describes what's different right now. "No rope" that set the difficulty doesn't come back as a penalty.

**What a good description earns.** It always chooses the attributes (see [Building a roll](#building-a-roll)). When it adds a fact, such as a method, preparation, using the surroundings or something learned earlier, that fact earns a modifier or a lower difficulty, not both. It can remove the uncertainty and with it the roll. Intensity words ("listening hard", "with all his strength") describe doing the task, which is what the roll measures; they earn nothing.

## Several things at once

Doing several things at once is always allowed. Every roll involved gets −2 for each other thing done at the same time. Abilities that reduce this, such as ambidexterity, are traits.

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
  --active-adv DFT "combat stim" --reactive-dis NRV "surprised" \
  --mod +2 "braced on the car roof" --mod -2 "darkness"

bash tools/gm-skill-contest.sh --active Fearghas Larceny DFT DFT LOG --reactive-dc 20 "sturdy lock"
bash tools/gm-skill-contest.sh --active-dc 20 "nerve toxin" --reactive Fearghas Endurance VIG VIG ITU
```

- **Names:** the player, an NPC from `npcs.json`, or a mob from `mobs.json`. Mobs have no personality, and their instances are interchangeable. Mobs you invent belong to the campaign.
- **Unknown name or no stats:** the script refuses. Give them stats, then roll again; never edit the JSON by hand. `gm-mob.sh list` shows the repo's example mobs: they are the scale.
  ```
  bash tools/gm-npc.sh stats "Rook" --attr STR=12 --attr AGI=11 --attr default=10 \
    --skill Handguns=4 --skill Guard=3 --wounds 3
  bash tools/gm-npc.sh stats "Rook" --skill Insight=2        # later: merged in
  bash tools/gm-mob.sh add "Mastiff" --note "military war-chassis, IFF ripped out" \
    --attr STR=18 --attr VIG=18 --attr default=10 --skill Brawling=6 --wounds 6
  ```
  `--attr default=N` is the die for every attribute not listed; `--skill default=N` the value for untrained skills (otherwise −1). The script checks every value and warns about a skill that isn't canon or improvised.
- **Decide the stats before the roll that needs them,** and don't change them because of how a roll went: they are facts about the world, and the world doesn't get harder after a failure.
- **Advantage and disadvantage** belong to an attribute and affect all its dice in the roll. Each flag takes the attribute and a reason. Repeat the flag to stack them. See [Advantage or modifier](#advantage-or-modifier) for which to use.
- **`--mod`** is one net list, relative to the active side: positive helps the active side, negative helps the reactive side. Leave out anything that affects both sides equally. Every modifier has a label.
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

Whenever a failure creates ongoing fallout: `bash tools/gm-consequence.sh add "[what happens]" "[when]" [--trigger-type ...]`. Persist the cost (mood, wounds, inventory, death) BEFORE narrating it.

## Reward a great success

A clever, effective or unique solve EARNS progress, not just a kill. On a strong success (quality above 10, or an inventive approach), grant spectacle XP before narrating: `bash tools/gm-player.sh award --tier minor|major|legendary --reason "..."`. See `gm-craft → Reward the spectacle`.

## Fail forward (critical)

A failed roll NEVER means "nothing happens". It means "something DIFFERENT happens".
- Failed lockpick? The pick breaks inside. Now you need the key or a louder way.
- Failed persuasion? The NPC keeps what they know, and word of who came asking travels.
- Failed stealth? Not caught yet, but you knocked something over. Now you're on a timer.

Framework: (1) What did they try? (2) What was the intent? (3) What goes sideways into a NEW situation? (4) What choice does that create?

**Fail forward isn't immortality.** "Something different happens" can include death when the stakes were lethal and telegraphed: an over-matched threat, an ignored warning, a tightening string of failures. Don't soften a self-inflicted lethal outcome into a free pass. On PC death, run the Death Protocol (`CLAUDE.md`).

**A failed information roll misreads the world; it never changes it.** Investigation, Awareness, Insight, Tactics and every other roll that reads a situation work on what is already true. Failure means missing it, getting part of it, or believing something wrong about it, never a new fact that makes the world harder than it was. If something the roll could reveal isn't decided yet, decide it before rolling (with the stakes), and record it then: the truth as a fact (`--secret` if nobody knows it yet), the misreading as a version of it the character holds (`--holders player --truth wrong --version-of <id>`). Example of what not to do: a failed Tactics roll against a war-machine, after which the machine gains a hidden coolant reserve so that the plan fails.

**Fail forward isn't free.** Decide what the roll COSTS before rolling. On a failure the stated goal does NOT happen, and that cost lands in the same beat. "Something different" means different and poorer, not different and equally good.

**Don't hand the stake back for free.** A failed roll's goal is denied, and a failed ask is not an invitation to re-ask the same way. If the fiction leaves a door open, such as an NPC who could still be swayed or a lock that could still be forced, opening it should cost something new. The roll reopens when the situation MATERIALLY changes: new leverage, new information, a different approach, or a price paid.

## Index

| Skill | Category | Anchor | In short |
|---|---|---|---|
| Brawling | [Combat](combat.md) | STR | Fighting with the body itself. |
| Bludgeons | [Combat](combat.md) | STR | Swung weight and momentum. |
| Slashing | [Combat](combat.md) | AGI | Flowing cuts, sweeps and whips. |
| Throwing | [Combat](combat.md) | AGI | Anything that leaves the hand, or arrives in it. |
| Evasion | [Combat](combat.md) | AGI | Ranged defense: not being where the bullet goes. |
| Fencing | [Combat](combat.md) | DFT | Thrusts, feints and precise stabs. |
| Handguns | [Combat](combat.md) | DFT | Pistols and guns held without a stock. |
| Long guns | [Combat](combat.md) | DFT | Guns braced on the shoulder. |
| Guard | [Combat](combat.md) | ITU | Close-combat defense: reading the attack in time. |
| Heavy weapons | [Combat](combat.md) | NRV | Guns you can't just pick up and fire. |
| Endurance | [Resistance](resistance.md) | VIG | The body holding out. |
| Composure | [Resistance](resistance.md) | NRV | The mind holding out. |
| Athletics | [Physical](physical.md) | STR | Force: climbing, swimming, lifting. |
| Acrobatics | [Physical](physical.md) | AGI | Grace: balance, parkour, falling well. |
| Stealth | [Physical](physical.md) | AGI | Not being noticed. |
| Rigging | [Vehicles](vehicles.md) | AGI | Being the machine. |
| Piloting | [Vehicles](vehicles.md) | DFT | Driving or flying by hand and eye. |
| Investigation | [Perception](perception.md) | LOG | Deliberate searching and reasoning. |
| Awareness | [Perception](perception.md) | ITU | Noticing anything. |
| Insight | [Perception](perception.md) | EMP | Reading people. |
| Persuasion | [Social](social.md) | PRS | Changing minds openly. |
| Intimidation | [Social](social.md) | PRS | Making people afraid enough to comply. |
| Streetwise | [Social](social.md) | PRS | Knowing the street. |
| Deception | [Social](social.md) | EMP | Making people believe what isn't true. |
| Corpspeak | [Social](social.md) | EMP | Knowing the suits. |
| Larceny | [Tradecraft](tradecraft.md) | DFT | Hands where they shouldn't be. |
| Tech | [Tradecraft](tradecraft.md) | LOG | Making machines work, or stop working. |
| Netrunning | [Tradecraft](tradecraft.md) | LOG | All computer work worth a roll. |
| Medicine | [Tradecraft](tradecraft.md) | LOG | Keeping bodies working. |
| Science | [Knowledge](knowledge.md) | LOG | Academic and theoretical knowledge. |
| Tactics | [Knowledge](knowledge.md) | LOG | Win first, then fight. |
