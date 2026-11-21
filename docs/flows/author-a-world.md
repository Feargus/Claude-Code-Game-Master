# Authoring an original world

*Claude, 2026-11-19: kept from the upstream docs, not yet rewritten.*

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
| **C — The kit and the frame** | draft the kit and the world's own rules; the factions' power and relations; the districts and landmarks, kinds of enemy, the world's words; lock the chronicler + art style. No people yet | — |
| **D — The character** | the `/create-character` interview: their own concept or one of six roles (never a named person), their trouble in broad strokes, fast or slow (`gm-player.sh create`) | — |
| **E — The character's world** | Standing; their people and places; each faction's first plot (touching the character only indirectly); where and when to start; `gm-session.sh opening` with the main plot, the character's trouble | — |

## The stage, not the planet

Phase E writes only what tonight needs: one location you can stand in, 2–4 people
in the room, the exits you can see, and the hook that will not wait — never a
continent. When play walks toward a name that isn't in the journal yet,
`gm-npc.sh create` or `gm-location.sh add` makes it then. Do not census ahead.

## Opening the scene

The opening is written after the character exists and the player has said where
and when to start, so it fits them: `gm-session.sh opening` (`lib/opening.py`) makes
the stage through the normal tools, all or nothing, and refuses once a session has
ended. Every campaign starts with its main plot, the character's trouble from the
interview made concrete; its hook is the plot's first beat, and the people and places it names without a record are its horizon, shown in
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
