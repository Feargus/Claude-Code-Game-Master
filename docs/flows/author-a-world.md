---
type: Flow
title: Authoring an original world
description: /new-game builds one stage — kit, voice, one street — then grows the world from the table.
sources:
  - { resource: /.claude/commands/new-game.md }
  - { resource: /lib/world_bible.py }
  - { resource: /lib/opening.py }
  - { resource: /tools/gm-extract.sh }
  - { resource: /lib/player_manager.py }
  - { resource: /lib/new_character.py }
generated: { by: claude-opus-4-8[1m], at: 2026-08-15T12:45:56Z }
---

# Authoring an original world

`/new-game` is `/import` with the book replaced by generation. The door is the
same: kit, voice, one street. There is no fan-out — you author
tonight's one stage, then the world grows AS YOU PLAY. See
[the dream](../conventions/the-dream.md).

The one problem everything upstream of play is aimed at — **any model asked for "a
fantasy world" produces the same world** — is solved at the seed, not by scale. The
anti-generic levers are the **genre bend**, the **voice exemplar** (narration reads
like a real author), and a **World Kit derived from this world** (never a silent 5e
default). A gazetteer authored before anyone sits down does not make a world
distinct; those three do.

## Phases

| Phase | What happens | Gate |
|---|---|---|
| **A — Seed** | genre-aware questionnaire → `world-seed.json` (premise, tone, genre bend, voice, art style, chronicler) | — |
| **B — Skeleton** | slim bible (voice + signature systems + this street), **shown for approval** | play gates on approval |
| **C — Kit and opening sketch** | draft the kit; sketch the opening (place, exits, people, the plot and its hook, premise, the antagonist's clock), stored nowhere yet | — |
| **D — Handoff** | lock the chronicler + art style, the one identity question → the `/create-character` interview (`gm-player.sh create`), where and when to start, then `gm-session.sh opening` and appearances for the stage | — |

## The stage, not the planet

Phase C writes only what tonight needs: one location you can stand in, 2–4 people
in the room, the exits you can see, and the hook that will not wait — never a
continent. When play walks toward a name that isn't in the journal yet,
`gm-npc.sh create` or `gm-location.sh add` makes it then. Do not census ahead.

## Opening the scene

The opening is written after the character exists and the player has said where
and when to start, so it fits them: `gm-session.sh opening` (`lib/opening.py`) makes
the stage through the normal tools, all or nothing, and refuses once a session has
ended. Every campaign starts with at least one plot; its hook is the plot's first
beat, and the people and places it names without a record are its horizon, shown in
STORY THREADS.

## Growing the world at the table

The campaign file is a **journal of where the table has been**, and it grows
reactively, from play. When a long-game opportunity appears, seed it with the
living-world tools and let it tick: a **threat clock** (`gm-clock.sh`), an **open
thread** (`gm-session.sh end --open-thread`), a new **plot** beat (`plots.json`), or
a **consequence** (`gm-consequence.sh add`) that fires on the right trigger. That is
the campaign's mid- to long-term planning — authored as you run it, not before.

## Related

- [Import a book](import-a-book.md) — the same shelf, a PDF instead of authored canon
- [Onboarding and death](onboarding-and-death.md) — the one question and the interview
- [Play a turn](play-turn.md) — the core loop the stage opens into
