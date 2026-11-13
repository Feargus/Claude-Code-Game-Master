---
name: gm-death
description: The Death Protocol — what to do when the player character dies: narrate it, offer the hand-off to a new character, swap them in, and carry the story on. Load right after `gm-player.sh kill --cause "<how>"` has recorded the death.
---

# Death Protocol (the player character dies)

When death can happen and how it must be telegraphed is in `CLAUDE.md` → Stakes & Death; the wound that kills is in [gm-combat](../gm-combat/SKILL.md). This file is what comes after. Death does not end the game or the session: the story passes to another character.

**Persist first, then narrate, then offer the hand-off.**

1. **The death is recorded.** `bash tools/gm-player.sh kill --cause "<how>"` must have run before anything is narrated: it sets the status to dead, stamps the time, records the death as a fact and fires the `on_death player` consequences. If it hasn't run yet, run it now. Record any further consequence the death sets off (`gm-consequence.sh add ...`).
2. **Narrate the death with weight.** Earn the moment; match the prose to the beat. No menu yet.
3. **Offer the hand-off.** The show goes on, it is not GAME OVER. Three routes, framed however the moment calls for:
   - take over a party member already in the scene;
   - make a new character;
   - step in as a figure who already exists in this world.

   Solo, with no party and no fitting figure: offer the last two only.
4. **Swap in the new character.** Both ways run the `/create-character` interview:
   - **A new character:** save with `gm-player.sh create '<json>' --replace`.
   - **A party member or an existing figure:** a canon character, with that NPC's sheet as the first suggestion; save with `gm-player.sh create '<json>' --canon "<NPC>" --replace`.

   Either way the fallen character's sheet goes to `fallen/`, and they become an NPC with what they knew. The new character knows only what they witnessed or were told (`gm-note.sh witness` / `tell`); a canon character keeps what the NPC knew.
5. **Bridge the fiction:** how and why the story passes to this person. Update the location and the scene (`gm-session.sh move`, `gm-scene.sh enter`), then resume play.
6. **The dead stay in the world's memory:** referenced, mourned, looted, avenged. Threads and clocks go on.
