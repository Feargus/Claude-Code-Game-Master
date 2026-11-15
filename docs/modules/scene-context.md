---
type: Module
title: Scene context — the two doors
description: What the harness pushes to the model each beat, and why "context" means two different things depending on which tool you call.
sources:
  - { resource: /lib/session_manager.py }
  - { resource: /lib/world_kit.py }
  - { resource: /lib/scene_context.py }
  - { resource: /lib/search.py }
  - { resource: /lib/entity_manager.py }
  - { resource: /tools/gm-context.sh }
generated: { by: claude-opus-4-8[1m], at: 2026-08-16T00:00:00Z }
verified: { by: claude-fable-5, at: 2026-08-14T12:19:52Z }
---

# Scene context — the two doors

This is the mechanism the whole product rests on: instead of hoping the model remembers,
the harness *pushes* the campaign at it every beat. Two different commands both call
themselves "context" and return almost disjoint things. Calling the wrong one is the
most common way a beat comes out flat.

| Command | Code | Returns |
|---|---|---|
| `gm-session.sh context` | `Brief` (`lib/brief.py`) | The **start brief** — everything below, as formatted prose for the model |
| `gm-context.sh ["loc"]` | `SceneContext.build` (`lib/scene_context.py:37`) | The **place brief** — this location, NPCs present, named entities, plus grounded source passages |

Neither contains the other. The session brief has no source passages; the place brief has
no history, threads, clocks, voice, or rules. Narrating a scene generally wants both.

## What the start brief carries, and why (rebuilt 2026-11-15)

The brief is read once, at the start of a sitting; during play the cards come with the
commands that change the scene (`lib/cards.py`). It is ordered by plot, because the plots
are the spine: what matters is what belongs to a plot. `Brief.SECTIONS`, in order:

- **header**: the world's name, the place and the game time.
- **kit**, then the **play style** and **images** lines, only where they differ from
  what `CLAUDE.md` says by default.
- **PLOTS**, every open plot, most pressing first (`plot_manager.plot_order`): where it
  stands (its one sentence), whose goal it is, its sketches (named, not built), its clocks,
  the consequences waiting in it, and **what the character doesn't know of it**: secrets
  and facts only others hold, up to five, newest first, each with who knows it, then the
  `gm-note.sh find --plot … --hidden` for the rest. What the character knows is not listed
  per plot: the plot's sentence says it, and LATEST shows what just happened. The secrets
  are what the GM must not forget, and can't search for without knowing they exist.
- **IN NO PLOT**: the same three lists for what belongs to no open plot.
- **CHARACTER** and **PARTY MEMBERS**; **WHAT <NAME> GETS WRONG** (the character's wrong
  or partial beliefs, each with its truth).
- **YOUR WORLD'S RULES** and **SIGNATURE SYSTEMS**, never cut.
- **NARRATIVE VOICE**: the style, the world's own words (the glossary's terms) and three
  sample passages, a prose target, not lore.
- **LATEST**: the five newest facts, for picking up where play stopped.
- **THE SCENE**: the place's card and a card for each person present.

A fact is printed once; later it is named by id ("also f12"). There is no `--full`, no
KEY FACTS by category, and no session summary (the session log is gone). `DM_DEBUG_CONTEXT=1`
prints an approximate token count to stderr without changing the output.

## RAG is optional everywhere, and fails to empty

`SceneContext.build` wraps the entire enhancer call in a bare `except Exception: pass`
(`lib/scene_context.py:56-64`). A campaign with no vector store, a missing `chromadb`, or
a runtime error inside the enhancer all produce the same thing: `passages: []` and
`rag_available: false`. Play continues on world state alone.

The cost of that choice: **a broken RAG install is indistinguishable from a campaign that
was never vectorized.** Neither logs. If passages are unexpectedly empty, check
`rag_available` in `gm-context.sh --json`, then confirm the campaign actually has vectors
rather than assuming the import worked. See [RAG stack](rag-stack.md).

## Which search tool

`gm-search.sh` is the free-text door and takes a mode flag: `--world-only`, `--rag-only`,
or neither for both. `gm-enhance.sh query` is **not** a search — it takes an entity *name*.
Reaching for it with a free-text phrase returns nothing and looks like an empty world.

Who is here is one helper, `npcs_present` (`lib/entity_manager.py`): party members
always, plus the NPCs on the **scene list** (`campaign-overview.json` → `scene`), which
`gm-scene.sh enter` / `leave` keep and every move resets to the party (since 2026-11-07).
A list stored for another location counts as empty. Location tags no longer decide
presence: they say where an NPC is usually found (`npcs_usually_at`, exact,
case-insensitive), shown in the brief as "Usually found here, not in the scene". Before,
presence was the tags, so an NPC was "here" whenever the player stood where they were
tagged, and never anywhere else; in rust-chrome that meant nobody was ever present except
in "Lanternside" itself.
Both context doors, consequence tick, a fact's default holders and the ready-threads
nudge call it.
Substring was the place-brief bug — "The Inn" must not count as "The Inner Sanctum",
and an untagged party member must still stand in the room. CLI `gm-search.sh
--tag-location` / `--tag-quest` may still substring-search for discovery; that is not
presence. The field those tags live in used to have two spellings — see
[the NPC location tag split](../gotchas/npc-location-tag-split.md).

## Related

- [Campaign memory](campaign-memory.md) — where "previously on" is built from
- [Living world](living-world.md) — clocks and consequences that appear in the brief
- [A play turn](../flows/play-turn.md) — where in the loop each door is called
