---
name: gm-growth
description: How the player character grows — skills that improve with use, where XP comes from and when to award it, and the level-up at a quiet moment. Load when the brief or a command says "Growth due", and before awarding XP for an achievement.
---

# Growth

The character grows in two ways: skills improve with use, by themselves, and the character as a whole gains levels from XP. The scripts do all the counting; never work anything out yourself.

## Skills improve with use (automatic)

After every skill contest the player's skill learns from the result: close contests teach, a walkover or a hopeless attempt teaches nothing. Enough learning raises the skill, and every skill point gained gives XP. The dice script does this silently. Don't narrate it, and don't roll anything for the sake of practice.

## Where XP comes from

| Source | How | XP |
|---|---|---|
| Skills used | automatic, in `gm-skill-contest.sh` | 10 × the new skill value |
| An enemy taken out in a tracked fight | automatic, in `gm-combat.sh end` | wounds² × 10 |
| An achievement | `bash tools/gm-player.sh award --size small\|medium\|large --reason "..."` | 20 / 50 / 100 % of the current level |

**Achievements** are the GM's call, awarded as they happen, before narrating the payoff:
- **small:** an obstacle surmounted, a problem solved, an enemy driven off or escaped, a clever or daring move that paid off.
- **medium:** a goal reached (a job step, a lead run down), a real ally or favour won, a powerful enemy outwitted.
- **large:** a major goal achieved (a job done, a mystery solved, a plot thread resolved), power gained (a faction's backing, a rival brought down).

One award per achievement; a fight's kills already pay for themselves. The reason goes into the campaign's `xp.log`. `gm-player.sh xp` is only for corrections.

Level N needs 100 × N² XP in total. XP never raises the level by itself: it makes growth **due**, and the brief then shows "Growth due" under CHARACTER.

## The level-up, at a quiet moment

Never mention to the player that a level is due. Wait for a quiet moment: a rest, sleep, a meal, the character alone with their thoughts. Never mid-fight or mid-scene. When it comes:

1. One sentence in the fiction about where the growth came from, then the question. For example: *"You learned a lot in the pit. The question is what you'll make of it."* No out-of-character comment: not "you levelled up".
2. Present the options, without further comment, drawn from what happened recently in the story (what the character did, what hurt them, what they leaned on):
   - **two attributes**, of which the player picks one: it goes one die size up;
   - **four skills**, of which the player picks two: +1 each (a new one starts at 1);
   - **two perks**, of which the player picks one. A perk is flavourful and two-sided: +2 to one thing and −2 to another, or better in one situation and worse in another. It has a name and says what it does.
3. The player chooses, or proposes their own instead. Accept anything reasonable.
4. Persist it:
   ```
   bash tools/gm-player.sh grow --attribute AGI --skill Guard --skill Stealth \
     --perk "The Promise" "+2 Composure while humming the tune; -2 Stealth while it hums"
   ```
   The script refuses anything other than one attribute, two different skills and one new perk. If more than one level is due, repeat the whole procedure once per level.
5. Narrating what changed is optional: a line at most, in the fiction.
