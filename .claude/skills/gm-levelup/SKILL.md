---
name: gm-levelup
description: Leveling — the XP table, what a level-up gives (one attribute, three skills, maybe a perk), and the commands that apply it. Load when gm-player.sh xp prints LEVEL_UP.
---

# Level up

Trigger: `gm-player.sh xp` (or `award`) prints **LEVEL_UP**.

## XP

A character starts at level 0. Each level costs 100 XP more than the last:

| Level | Total XP |
|---|---|
| 1 | 100 |
| 2 | 300 |
| 3 | 600 |
| 4 | 1,000 |
| 5 | 1,500 |

The script keeps the count; never work it out yourself. XP comes from missions, fights, accomplishments and notable actions (see [Reward a great success](../gm-skills/SKILL.md#reward-a-great-success)).

## What a level-up gives

- **One attribute +1:** one die size up, e.g. d11 to d12. The player chooses.
- **Three different skills +1 each.** The player chooses. A skill the character doesn't have yet starts at 1.
- **Sometimes a perk.** Invent one when the story earned it. Make it flavorful and two-sided: +2 to one skill and −2 to another, or better by day and worse at night. A perk has a name and what it does.

## Apply it

Ask the player for their choices, then persist them before narrating:

```
bash tools/gm-player.sh raise attribute DFT
bash tools/gm-player.sh raise skill "Long guns"
bash tools/gm-player.sh perk "Night eyes" "+2 Awareness in the dark, -2 in bright light"
```

`perk` with an existing name rewrites what it does. Keep the moment short and in the fiction: what changed in the character, not a list of numbers.
