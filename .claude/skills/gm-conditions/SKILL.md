---
name: gm-conditions
description: Conditions — temporary states such as blinded, grappled, frightened, poisoned or exhausted, what each does, and how to persist them. Load when applying or resolving a condition.
---

# Conditions

A condition is the character's own temporary state, so it is a **disadvantage** on the attribute it affects, or something the character **can't do**, never a modifier (see [advantage or modifier](../gm-skills/SKILL.md#advantage-or-modifier)). Wounds are not conditions; they are in [gm-combat](../gm-combat/SKILL.md).

Apply a condition when the story causes it, and remove it as soon as it ends. Pass its disadvantage with the condition as the reason: `--active-dis NRV "frightened"`.

```
bash tools/gm-condition.sh add Fearghas "grappled"
bash tools/gm-condition.sh remove Fearghas "grappled"
bash tools/gm-combat.sh condition "street thug 1" add prone     # an enemy in a fight
```

## Examples

Not a closed list: use these as they are, adapt them, or invent new ones the same way.

| Condition | Effect | Ends |
|---|---|---|
| Blinded | Disadvantage on DFT and ITU when sight matters. Can't aim at anything out of reach. | Sight returns. |
| Deafened | Disadvantage on ITU when hearing matters. Can't follow speech. | Hearing returns. |
| Dazed | Disadvantage on LOG and ITU. | After a beat. |
| Stunned | No action. | After a beat. |
| Frightened | Disadvantage on NRV. Won't move closer to the source on their own. | The source is gone, or a Composure roll. |
| Grappled | Held: can't move away. Disadvantage on AGI. | Breaking free: Brawling or Athletics against the holder's Brawling. |
| Restrained | Tied, pinned or trapped: can't move. Disadvantage on AGI and DFT. | Cut, picked or forced free. |
| Prone | Lying down: disadvantage on AGI in close combat. Counts as cover against ranged attacks. | Standing up, which takes the move. |
| Poisoned, drugged, drunk | Disadvantage on the attribute the substance hits: VIG for sickness, LOG or ITU for intoxication, NRV for fear toxins. | It wears off or is treated. |
| Unconscious | No action, unaware of everything. An attack needs no roll to hit. | Waking up. |
| Exhausted | After 48 hours without sleep or rest: disadvantage on every roll, on its anchor attribute. | Sleep or real rest. |
