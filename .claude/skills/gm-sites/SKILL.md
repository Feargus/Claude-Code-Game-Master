---
name: gm-sites
description: Sites — the targets of runs, jobs and dungeons (vaults, corp towers, sewer complexes, computer systems). Narrative vs mapped mode, laying a site out in advance with site-architect, moving through areas and connections, and the rule that only mapped exits exist. Load when the player sets out for, or enters, such a place. Not for everyday surroundings.
---

# Sites

A site is the target of a run, a job or a dungeon: a place the player tries to get into, through or out of. A computer system is a site too; its areas are its layers (see the campaign's netrunning rules). Everyday places (a bar, a street, a flat) are not sites; narrate them as usual.

| Mode | Best for |
|------|----------|
| **Narrative** (default) | Small or one-off sites: one location with the layout in its description and the areas visited in its notes. |
| **Mapped** | Sites that matter: a heist target, a corp tower, a hard system. Laid out in advance, one location per area, with connections between them. |

## Laying out a mapped site

Before the player gets there, spawn `site-architect` with the site's name, what it is, its size, the areas the story requires, and any source passages. It saves every area and connection. Do this as soon as the player commits to the job, not at the door.

**In a mapped site, only the mapped connections exist.** No door, vent or shortcut appears because the player needs one, and no guard disappears because the player didn't plan for them. Making a new way (blowing a wall, cutting a fence, writing an exploit) is a roll with a cost, never a free discovery.

## Narrative flow

Enter → describe the entrance and the visible ways on → explore → fights as in `gm-combat` → on leaving, note anything that changed.

## Mapped flow

1. **Check the connection:** `bash tools/gm-location.sh connections "<Site> - <Area>"`. Does it exist? Is it locked, hidden, blocked or guarded?
2. **Handle the obstacle:** a key, a code, or the roll named in the connection. A hidden connection must be found first, with the roll it names.
3. **Move:** `bash tools/gm-session.sh move "<Site> - <Area>" --takes <time>`. Only ever to a connected area.
4. **Describe** in 2–4 sentences: what's there and the ways on the player can see. Never mention what is still hidden.

When the site changes (a guard down, a door blown, an alarm raised), persist it: `bash tools/gm-location.sh describe` for the area, or a consequence or clock for what follows.

## Reward a site win

A breakthrough (getting past the security, finding the hidden way, a daring escape, crossing a punishing hazard) is an achievement: XP for an achievement (an obstacle surmounted, a goal reached, a problem solved, power gained): `gm-growth`.
