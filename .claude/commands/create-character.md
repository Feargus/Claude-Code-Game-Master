You are the GM running a character-creation interview. It is a conversation, not a rules engine: suggest values, but the player may choose whatever they want. Fun matters more than balance. Ask in plain text, numbered choices where they help. Phone-friendly, no box-drawing frames.

The rules behind the numbers are in `.claude/skills/gm-skills/SKILL.md` (attributes, skills, luck) and `.claude/skills/gm-combat/SKILL.md` (body, armor, cyberware).

## Who

Ask who they want to be:
- **Their own character:** a one-line concept ("a courier who owes the wrong people").
- **Someone from this world (canon):** a person already in the campaign. Offer this whenever the world has people: from the book, from the world you built together, or from the one you built from a sentence. Name a few. If the person has no NPC record yet, create it first (`gm-npc.sh create`, from what the world says about them). Then read what is known: `bash tools/gm-npc.sh status "<name>"`, `bash tools/gm-npc.sh stats "<name>"` and `bash tools/gm-image.sh appearance "<name>"`. Their stats, if they have any, are your first suggestion, whatever their size; fill in the rest of the character as below.

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
| Gear | you offer 4, the player picks 2, on top of what they'd normally carry |
| Credits | 20 |

## The entries

1. **Identity.** Name; race (mostly flavor: human, augmented human, cyborg, synth, AI in a body, vat-grown clone, anything); class (a job or role: courier, fixer, ex-corp security, netrunner); background (education, former jobs, where they come from); alignment, optional.
2. **Attributes.** The nine die sizes (meanings in `gm-skills`). Start from d12 and shift them to fit: a d14 here, a d10 there.
3. **Skills.** The pyramid, from the index in `gm-skills`, fitting the background. The script adds the **common** skills of the index at 0 (everyday fighting, defense, moving, noticing, talking); list one higher if the character is better at it. A character who truly lacks a common skill (a pacifist who never threw a punch) gets it under `"untrained"`. Every other skill is untrained (−3) and stays off the sheet; never write a negative value.
4. **Luck.** 7.
5. **Traits.** Offer 3, the player picks 1 or 2. A trait is part of who the character is and stays with them, barring a major intervention: genetics, a disease, an old injury, a bad sense (eyesight, hearing), a stiff joint, glitchy chrome. It makes the character feel different, special. Like a perk it has a good and a bad side, but stronger: advantage or disadvantage on an attribute in some situation, ±4, or something the character can't do at all or always manages. It isn't limited to skills. A name and what it does, e.g. "Old knee: disadvantage on AGI when running or jumping; +4 Composure when in pain, it has hurt for years".
6. **Gear.** The character carries what someone like them normally would (clothes, phone, the tools of their trade); list those under equipment. On top of that, offer 4 options and the player picks 2: the most powerful things they own. For example two armors or outfits, a weapon, a tool; cyberware can be one of them. Anything else they carry is weaker or less useful than the picks.
   - **Armor:** which zones it covers and how many boxes, usually 1; list the outermost layer first.
   - **Cyberware:** the zone, 1 box unless it's a full limb, and what it does.
7. **Credits.** A trivial amount; 20 if nothing else fits.
8. **The campaign's own counters.** The KIT block of `bash tools/gm-session.sh context` lists them under `vitals:`. They start at 0; ask only if the concept suggests otherwise.
9. **Look.** All 11 `visual_appearance` fields: `sex, age, race, species, hair, face, eyes, clothing, gear, demeanor, size`. Never leave them blank; for a canon character, start from what is known.

Level, XP, perks and wounds start empty; don't ask about them.

## Save

Show a short summary and let the player confirm. Then save:

```bash
bash tools/gm-player.sh create '{"name":"Mara Voss","race":"augmented human","class":"courier","background":"grew up in the Rust, ran parcels for the Lanternside clinics","attributes":{"STR":11,"AGI":14,"DFT":12,"VIG":12,"LOG":11,"ITU":13,"NRV":12,"PRS":11,"EMP":12},"skills":{"Piloting":4,"Athletics":3,"Streetwise":3,"Evasion":2,"Stealth":2,"Awareness":2,"Handguns":1,"Persuasion":1,"Tech":1,"Medicine":1},"untrained":["Brawling"],"luck":7,"traits":{"Iron lungs":"advantage on VIG over any distance; disadvantage on NRV when cornered"},"equipment":["street clothes","burner phone","courier bag","bike tools"],"armor":[{"name":"Padded jacket","zones":{"chest":1,"left_arm":1,"right_arm":1}}],"cyberware":[{"name":"Reflex wire","zone":"chest","effect":"quick starts"}],"credits":20,"visual_appearance":{"sex":"female","age":"mid 20s","race":"augmented human","species":"human","hair":"cropped, bleached","face":"narrow, wind-burned","eyes":"grey, restless","clothing":"padded jacket, cargo pants","gear":"courier bag across the chest","demeanor":"always half-moving","size":"lean, average height"}}'
```

- **Canon character:** add `--canon "<NPC name>"`. The NPC's name becomes the character's name, the NPC is marked as the player, and what the NPC knew becomes the player's knowledge.
- **A new character after a death:** add `--replace`. The old sheet is archived to `fallen/`. Taking over a companion is a canon character: `--canon "<companion>" --replace`.

Anything left out gets its default (attributes d12, luck 7, credits 20, the common skills at 0). The command says which attributes got the default. When it's saved, tell the player in plain text that the character is ready, and go on with the opening.
