---
name: gm-social
description: Social / NPC interaction workflow — load NPC context, attitude check, social mechanics (Persuasion/Deception/Intimidation/Insight difficulties), and persisting NPC memory + consequences. Load whenever the player talks to, persuades, or reads an NPC ("I talk to...", "I ask...").
---

# Social / NPC Interaction

## 1. Load NPC context
If the NPC isn't in the scene yet (the brief's NPC block), put them there first: `bash tools/gm-scene.sh enter "[name]"`. Presence decides what they get to know and which consequences wait for them.
`bash tools/gm-context.sh "[npc]"` + `bash tools/gm-npc.sh status "[name]"`. Surface the NPC's `goal`, `current_mood`, what they know (the brief's 'they know' lines: play what they hide as hidden), `bonds`, and `voice` (`gm-npc.sh voice`). Check prior interactions + active quests.

## 1b. Flesh a stub on first real contact
Present NPCs correctly START as one-line stubs (a play-pack "Present in ..." blurb, no `goal`/`voice`) — that is the anti-gazetteer rule, not a bug. But the moment the player **meaningfully engages** one (talks to them, presses them, reads them), give them an interior so nobody the player actually talks to stays a "neutral stub": author a **want**, a **secret**, and how they **sound**, and persist them —
```bash
bash tools/gm-npc.sh set-inner "[name]" --goal "[what they want]" --voice "[how they sound]"
bash tools/gm-note.sh <category> "[what they hide]" --holders "npc:[name]"
```
The secret is a fact only they hold: the brief shows it under them as something they know, and marks it hidden from the player.
Only on real contact — do not pre-flesh NPCs the player never engages. Once set, it rides into every future scene they're in (mood/goal, what they know, and their remembered `events`).

## 2. Attitude
Friendly (helpful, warm) · Neutral (professional, cautious) · Hostile (dismissive, cold). Derive from history + bonds.

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
`bash tools/gm-npc.sh update "[name]" "[what happened]"` and `bash tools/gm-npc.sh mood "[name]" "[new mood]"` — reactions compound across sessions.

## 4b. Who now knows what
A conversation is where most knowledge moves. Anything said in the scene that matters goes in as a fact: its default holders are the player and everyone in the scene (`gm-scene.sh`), so an eavesdropper not in the scene needs `--also "npc:[name]"`. When the player tells an NPC something already recorded (or the NPC lets slip one of their facts), `bash tools/gm-note.sh tell <fact id> <holder>...`. A lie the player tells is a wrong version: the truth (if recorded) stays as it is, the lie is a fact the listener holds, `--truth wrong --version-of <truth id>`.

## 5. Consequences
Positive (NPC helps later) / negative (NPC hinders) → `bash tools/gm-consequence.sh add "[event]" "[trigger]" [--trigger-type on_npc --match "[name]"]`. **Mandatory** whenever the interaction leaves ongoing fallout — a failed ask that changes how this NPC treats you later is exactly that.

## Failure — the ask is DENIED and it costs (see `gm-skills → Narrate by quality`)
Decide before rolling what refusal COSTS (never tell the player). On a failed social check:
- **The ask does not happen.** Don't refund the stake by ending on a softer re-ask that costs nothing. If the NPC leaves a door open, that's escalation the fiction has to price — new leverage, new information, or something the player gives up.
- **Whatever was on the table is spent.** If the player was bargaining for lives, cargo, passage, or mercy, the failure is where that thing is lost — not deferred. The NPC responds from their own goals and power; sometimes that's ugly.
- **Persist the shift** so refusals compound like wins do: `bash tools/gm-npc.sh mood "[name]" "[new mood]"` + `gm-npc.sh set-inner` (goal/attitude), and `gm-npc.sh update "[name]" "[what happened]"`.

## Reward a social win (award spectacle XP)
A real social victory — a hard persuasion landed, a daring bluff, turning a hostile NPC, talking your way past a threat — EARNS progress like a kill. Persist it before the payoff: `bash tools/gm-player.sh award --tier minor|major|legendary --reason "..."` (level-scaled). See `gm-craft → Reward the spectacle`.

## Craft (see gm-craft)
NPCs have agendas, not quests. Don't over-share — secrets revealed slowly are 10x better. NPCs can say no, lie, or give bad advice. End with a conversation-ender if they're done.
