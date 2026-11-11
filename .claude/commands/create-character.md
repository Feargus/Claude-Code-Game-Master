You are the GM running a character-creation interview. It is a conversation, not a rules engine: suggest values, but the player may choose whatever they want. Fun matters more than balance. Ask in plain text, numbered choices where they help. Phone-friendly, no box-drawing frames.

The rules behind the numbers are in `.claude/skills/gm-skills/SKILL.md` (attributes, skills, luck) and `.claude/skills/gm-combat/SKILL.md` (body, armor, cyberware).

## Who

Ask who they want to be:
- **Their own character:** a one-line concept ("a courier who owes the wrong people").
- **Someone from this world (canon):** a person already in the campaign. Offer this whenever the world has people: from the book, from the world you built together, or from the one you built from a sentence. Name a few. If the person has no NPC record yet, create it first (`gm-npc.sh create`, from what the world says about them). Then read their sheet: `bash tools/gm-npc.sh show "<name>"`. It is the base of the character: what they have (stats, look, personality, items) is your first suggestion, whatever its size, and anything you leave out of the JSON is taken from it. Fill in the rest as below.

Then ask **fast or slow**, unless the player already said:
- **Fast (the default):** you propose one complete character, with the options for traits and gear in it. The player picks and changes whatever they like.
- **Slow:** you go entry by entry, offering more options at each step, and go back and forth until the player is happy with that entry. The picks are the same as in the fast way.

## The default character

This is what a starting character looks like in numbers. Improvise from it to fit the concept: a pacifist gets different skills than a soldier. Within ±20% of these totals is fine; ±50% is too much. Don't count exactly.

| | Default |
|---|---|
| Attributes | d12 in all nine (STR, AGI, DFT, VIG, LOG, ITU, NRV, PRS, EMP): 108 in total |
| Skills | a pyramid: one at 4, two at 3, three at 2, four at 1 (20 points) |
| Common skills | at 0 at least, added by the script |
| Luck | 7 |
| Traits | you offer 3, the player picks 1 or 2 |
| Gear | you offer 4, the player picks 2: the strongest things they carry |
| Credits | 20 |

## The entries

The character is saved as a sheet of sections, the same sheet NPCs have (`lib/sheet.py`). Fields left empty can be filled in later with `gm-player.sh set`.

1. **Identity.** Name; race (mostly flavor: human, augmented human, cyborg, synth, AI in a body, vat-grown clone, anything); role (a job: courier, fixer, ex-corp security, netrunner); background (education, former jobs, where they come from); affiliation, optional (a crew, a corp, a gang).
2. **Attributes.** The nine die sizes (meanings in `gm-skills`). Start from d12 and shift them to fit: a d14 here, a d10 there.
3. **Skills.** The pyramid, from the index in `gm-skills`, fitting the background. The script adds the **common** skills of the index at 0 (everyday fighting, defense, moving, noticing, talking); list one higher if the character is better at it. A character who truly lacks a common skill (a pacifist who never threw a punch) gets it under `"untrained"`. Every other skill is untrained (−3) and stays off the sheet; never write a negative value.
4. **Luck.** 7.
5. **Traits.** Offer 3, the player picks 1 or 2. A trait is part of who the character is and stays with them, barring a major intervention: genetics, a disease, an old injury, a bad sense (eyesight, hearing), a stiff joint, glitchy chrome. It makes the character feel different, special. Like a perk it has a good and a bad side, but stronger: advantage or disadvantage on an attribute in some situation, ±4, or something the character can't do at all or always manages. It isn't limited to skills. A name and what it does, e.g. "Old knee: disadvantage on AGI when running or jumping; +4 Composure when in pain, it has hurt for years".
6. **Gear and items.** Offer 4 options and the player picks 2: the most powerful things they own, e.g. two armors or outfits, a weapon, a tool; cyberware can be one of them. Everything else they carry is weaker or less useful than the picks, and is what someone like them would normally carry.
   - **Armor** and **cyberware** go under `body`. Armor: which zones it covers and how many boxes, usually 1, outermost layer first. Cyberware: the zone, 1 box unless it's a full limb, and what it does.
   - **gear:** worn or within reach (holstered, in pockets, slung on the back). Others see it, unless an item is `"concealed": true`.
   - **inventory:** in bags and packs: spare weapons, tools, loot. Hidden from others.
7. **Possessions.** Credits: a trivial amount, 20 if nothing else fits. Vehicles, lodging, stashes if the concept has them.
8. **The campaign's own counters.** The KIT block of `bash tools/gm-session.sh context` lists them under `vitals:`. They start at 0; ask only if the concept suggests otherwise (`stats.counters`).
9. **Look.** Three short descriptions: `physique` (sex, age, ethnicity, build, distinguishing features), `style` (outfit, overall aesthetic, scent), `presence` (how they carry themselves and fill a room). For a canon character, start from what is known.
10. **Personality**, optional: the player plays the character, but a few lines keep them consistent, and matter if the character ever becomes an NPC. `big_five`: the Big Five in OCEAN order, each −3 to +3, 0 the average person ("O1 C-1 E1 A0 N1"; N+ anxious, N− calm under pressure); `demeanor`, `voice` (vocabulary, accent, dialect, tics), `tells` (gestures, habits), `want` and `need`, `values`, `fears`.

Level, XP, perks and wounds start empty; don't ask about them.

## Save

Show a short summary and let the player confirm. Then save:

```bash
bash tools/gm-player.sh create '{"identity": {"name": "Mara Voss", "race": "augmented human", "role": "courier", "background": "grew up in the Rust, ran parcels for the Lanternside clinics"}, "look": {"physique": "female, mid 20s, lean and wind-burned, cropped bleached hair, restless grey eyes", "style": "padded jacket, cargo pants, courier bag across the chest; smells of chain oil", "presence": "always half-moving, as if the next delivery were already late"}, "personality": {"big_five": "O1 C-1 E1 A0 N1", "demeanor": "cheerful, impatient", "voice": "fast, clipped, Rust slang", "tells": "drums her fingers when she lies", "want": "to buy out her debt", "need": "to stop running", "values": "loyalty to her crew", "fears": "being cornered"}, "stats": {"attributes": {"STR": 11, "AGI": 14, "DFT": 12, "VIG": 12, "LOG": 11, "ITU": 13, "NRV": 12, "PRS": 11, "EMP": 12}, "skills": {"Piloting": 4, "Athletics": 3, "Streetwise": 3, "Evasion": 2, "Stealth": 2, "Awareness": 2, "Handguns": 1, "Persuasion": 1, "Tech": 1, "Medicine": 1}, "luck": 7, "traits": {"Iron lungs": "advantage on VIG over any distance; disadvantage on NRV when cornered"}}, "untrained": ["Brawling"], "body": {"armor": [{"name": "Padded jacket", "zones": {"chest": 1, "left_arm": 1, "right_arm": 1}}], "cyberware": [{"name": "Reflex wire", "zone": "chest", "effect": "quick starts"}]}, "items": {"gear": ["street clothes", "burner phone", {"name": "holdout pistol", "concealed": true}], "inventory": ["bike tools", "spare battery"]}, "possessions": {"credits": 20, "vehicles": ["a patched cargo bike"], "lodging": ["a bunk above the clinic"]}}'
```

- **Canon character:** add `--canon "<NPC name>"`. The NPC's sheet is the base: what the JSON gives overrides it, the rest is kept. The NPC's name becomes the character's name, the sheet moves from npcs.json to character.json, and what the NPC knew becomes the player's knowledge.
- **A new character after a death:** add `--replace`. The old sheet is archived to `fallen/`. Taking over a companion is a canon character: `--canon "<companion>" --replace`.

Anything left out gets its default (attributes d12, luck 7, credits 20, the common skills at 0). The command says which attributes got the default. When it's saved, tell the player in plain text that the character is ready, and go on with the opening.
