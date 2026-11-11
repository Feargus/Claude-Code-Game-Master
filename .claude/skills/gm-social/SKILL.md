---
name: gm-social
description: Social / NPC interaction workflow — load NPC context, how they regard the player, social mechanics (Persuasion/Deception/Intimidation/Insight difficulties), and persisting what they now feel and know + consequences. Load whenever the player talks to, persuades, or reads an NPC ("I talk to...", "I ask...").
---

# Social / NPC Interaction

## 1. Load NPC context
If the NPC isn't in the scene yet (the brief's NPC block), put them there first: `bash tools/gm-scene.sh enter "[name]"`. Presence decides what they get to know and which consequences wait for them.
`bash tools/gm-context.sh "[npc]"` + `bash tools/gm-npc.sh show "[name]"`. Play them from their sheet: role, Big Five, demeanor, `voice` (how they talk), `tells` (what their body gives away), `want` and `goal`, `fears`; and from what they know (the brief's 'they know' lines, and `show`'s list of what they know and feel about the player: play what they hide as hidden). Check prior interactions + active plots.

## 1b. Flesh a stub on first real contact
NPCs correctly START with little: a name, a role, a usual place — that is the anti-gazetteer rule, not a bug. But the moment the player **meaningfully engages** one (talks to them, presses them, reads them), give them an interior so nobody the player actually talks to stays a stub: a **personality**, a **want**, a **secret**, how they **sound** and what gives them away, and persist them —
```bash
bash tools/gm-npc.sh set "[name]" --big-five "O1 C-1 E2 A-2 N1" --voice "[how they talk]" \
  --tells "[a gesture, a habit]" --want "[what they want]" --fears "[what they fear]"
bash tools/gm-note.sh <category> "[what they hide]" --holders "npc:[name]"
```
The Big Five: openness, conscientiousness, extraversion, agreeableness, neuroticism, each −3 to +3, 0 the average person (A− hostile, N+ anxious and volatile, N− calm under pressure). A label alone makes people generic; the voice, a tell and a want make them memorable. The secret is a fact only they hold: the brief shows it under them as something they know, and marks it hidden from the player.
Only on real contact — do not pre-flesh NPCs the player never engages. Once set, it rides into every future scene they're in.

## 2. Attitude
Friendly (helpful, warm) · Neutral (professional, cautious) · Hostile (dismissive, cold). Read it from what they feel about the player (facts they hold about the player, newest first in `gm-npc.sh show`) and their personality: there is no attitude field.

## 3. Social mechanics — when to roll
Roll with `gm-skill-contest.sh` (see `gm-skills`).

| Skill | Difficulty (Friendly / Neutral / Hostile) | Use |
|-------|-----------------------------------|-----|
| Persuasion | 15 / 20 / 25 | Change their mind |
| Deception | 15 / 20 / 25 (plausible→outrageous) | Hide truth |
| Intimidation | 15 / 20 / 25 (weak→strong-willed) | Force compliance |
| Insight | opposed vs Deception, or 15-25 | Read them |

Modifiers for the player: unreasonable request −5; good rapport +2.
**No roll needed:** public info, normal commerce at listed prices, casual talk, giving things freely.

## 4. Persist NPC memory
What happened is a fact, with the NPC among its holders (they were there). When it changes how they feel about the player, record that too, as a fact only they hold: `bash tools/gm-note.sh relations "[name] now [feeling] toward [player], since [what happened]" --holders npc:[name] --about player`. Reactions compound across sessions, because the brief shows these under them.

## 4b. Who now knows what
A conversation is where most knowledge moves. Anything said in the scene that matters goes in as a fact: its default holders are the player and everyone in the scene (`gm-scene.sh`), so an eavesdropper not in the scene needs `--also "npc:[name]"`. When the player tells an NPC something already recorded (or the NPC lets slip one of their facts), `bash tools/gm-note.sh tell <fact id> <holder>...`. A lie the player tells is a wrong version: the truth (if recorded) stays as it is, the lie is a fact the listener holds, `--truth wrong --version-of <truth id>`.

## 5. Consequences
Positive (NPC helps later) / negative (NPC hinders) → `bash tools/gm-consequence.sh add "[event]" "[trigger]" [--trigger-type on_npc --match "[name]"]`. **Mandatory** whenever the interaction leaves ongoing fallout — a failed ask that changes how this NPC treats you later is exactly that.

## Failure — the ask is DENIED and it costs (see `gm-skills → Narrate by quality`)
Decide before rolling what refusal COSTS (never tell the player). On a failed social check:
- **The ask does not happen.** Don't refund the stake by ending on a softer re-ask that costs nothing. If the NPC leaves a door open, that's escalation the fiction has to price — new leverage, new information, or something the player gives up.
- **Whatever was on the table is spent.** If the player was bargaining for lives, cargo, passage, or mercy, the failure is where that thing is lost — not deferred. The NPC responds from their own goals and power; sometimes that's ugly.
- **Persist the shift** so refusals compound like wins do: the new feeling as a fact they hold (`gm-note.sh relations ... --holders npc:[name] --about player`), and a changed aim with `gm-npc.sh set "[name]" --goal "..."`.

## Reward a social win
A real social victory (turning a hostile NPC, winning an ally or a favour, talking your way past a threat) is an achievement: XP for an achievement (an obstacle surmounted, a goal reached, a problem solved, power gained): `gm-growth`.

## Craft (see gm-craft)
NPCs have agendas, not quests. Don't over-share — secrets revealed slowly are 10x better. NPCs can say no, lie, or give bad advice. End with a conversation-ender if they're done.
