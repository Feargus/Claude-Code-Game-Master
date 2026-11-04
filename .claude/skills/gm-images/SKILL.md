---
name: gm-images
description: Generated scene images (OpenAI gpt-image-2) — when to illustrate, the locked art style and character looks, the scene-illustrator agent, and diegetic presentation. Load only when scene context reports `Scene images: ENABLED`.
---

# Scene images

**Currently disabled:** there is no `OPENAI_API_KEY` in `.env`. Kept for later use. If scene context reports `Scene images: DISABLED`, close this skill, never call `gm-image.sh`, and don't mention images.

When ENABLED, **illustrate GENEROUSLY and with glee** — at ~$0.04 an image, lean toward YES. A new location, a monster/boss reveal, big loot, a player's styled flourish, a comedic beat, a haunting vista — any beat with a real visual or emotional charge earns a picture.

**Every character has a locked `visual_appearance`** (11 fields: sex, age, race, species, hair, face, eyes, clothing, gear, demeanor, size) — authored at creation and updated when their look changes (`gm-player.sh set-appearance` / `gm-npc.sh set-appearance`).

**Any image containing the PC or an NPC MUST render their stored appearance** — the illustrator pulls it (`gm-image.sh appearance "<name>"`) and passes each character by name to `gm-image.sh generate --character "<name>"`, which auto-injects the block so recurring characters stay on-model (right sex, right gear) image to image. If a character in frame has no block yet, author one first.

**Spawn the `scene-illustrator` agent IN THE BACKGROUND** (Agent tool, `run_in_background: true`) with a one-line beat brief AND the campaign's locked art style passed verbatim (from `gm-image.sh chronicler` — the style is set at campaign creation, not chosen by the agent) — it owns the art bible, reads live state (gear/wounds/location), writes the fully-specified prompt (every prompt opens with that locked `In the style of ...`), and runs the slow image call OFF the critical path. Keep narrating; when it returns the `file://` link, DROP it on the player mid-scene. (Direct fallback if you must do it inline: `bash tools/gm-image.sh generate --title "<Title>" --prompt "<vivid visual description, art style, mood, lighting; do NOT include game UI/text>"`.) It saves a PNG to the campaign's `images/` and prints a clickable `file://` link — show that link to the player so they can open the picture. This is tested and works.

**Present every image DIEGETICALLY, in the world's voice** — frame it as an artifact made by an in-world chronicler ("AND BEHOLD, this great battle as set to ink by the scholar Astreus —"), and keep the SAME chronicler + art-style signature across the campaign so the gallery reads like one artbook (Conan → rough Frazetta-esque ink/woodcut; cyberpunk → neon concept art; etc.). Match the chronicler's persona to tone (grim, comic, reverent). See `gm-craft → Diegetic Illustration` for the craft. The player can summon one too ("show me", "paint that").

**Don't re-shoot the same static room** and skip genuinely flat beats — but when in doubt, illustrate. Each call is a real OpenAI charge, logged (`gm-image.sh log` for the running total). Use `--quality low` for throwaway gags, `medium` default, `high` for marquee moments.
