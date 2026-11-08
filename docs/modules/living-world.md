---
type: Module
title: The living world — consequences, clocks, world tick
description: The three systems that make the world move on its own, and which of them are actually wired to fire.
sources:
  - { resource: /lib/consequence_manager.py }
  - { resource: /lib/entity_manager.py }
  - { resource: /lib/threat_clocks.py }
  - { resource: /lib/world_tick.py }
  - { resource: /lib/time_manager.py }
  - { resource: /lib/plot_manager.py }
  - { resource: /lib/session_manager.py }
  - { resource: /tools/gm-time.sh }
  - { resource: /tools/gm-session.sh }
  - { resource: /tools/gm-clock.sh }
  - { resource: /tools/gm-plot.sh }
  - { resource: /.claude/agents/plot-weaver.md }
generated: { by: claude-opus-4-8[1m], at: 2026-08-16T00:00:00Z }
verified: { by: cursor-grok-4.6, at: 2026-08-14T19:13:47Z }
---

# The living world

Three systems claim to run without the player: consequences fire on triggers, threat
clocks tick toward a beat, and a between-sessions world tick advances off-screen
developments. **They are wired to very different degrees.** Verified 2026-08-13:

| System | Automatic trigger | How it actually runs |
|---|---|---|
| Consequences | **Yes** | `gm-session.sh move` and `gm-time.sh advance` both call `gm-consequence.sh tick` after they write |
| Threat clocks | **Time-clocks: yes** (since 2026-08-13) | `gm-time.sh advance <duration>` (or `set`) moves the campaign's `game_time`, and every `advance_on: "time"` clock is recomputed from it: it stores `starts_at` and `due_at`, and its filled share is the share of that span that has passed. A clock with no due time gets one day per segment. Event clocks stay manual: `gm-clock.sh advance "<name>" [--ticks N]`; a time clock is refused there, since a push by hand would only stall it until time caught up. A time clock is sped up or slowed down by moving its due time instead: `gm-clock.sh due "<name>" --earlier|--later <duration>` (or `--due-in`, `--due`). The start stays, and the clock is recomputed at once, so bringing it forward may fill segments and fire them on the spot; pushing it back never empties it. Filling one fires its consequence (below) |
| World tick | **No** — GM-invoked by design (`/gm world`) | the developments are a model call; `gm-session.sh world-tick '<json>'` records each as a fact, plus an optional consequence (with real triggers) and/or clock (since 2026-11-06; before, each was a consequence with no usable trigger), is all-or-nothing, warns (naming the overflow) when the count exceeds the advisory cap of 3, and stays logged / rollback-able. Before 2026-08-13 `WorldTick` had no caller at all |

So three weeks and ten minutes are not the same pressure: the GM passes how much time
actually elapsed, a clock is full exactly when its due time arrives, and a full clock announces
itself (`⚠ FULL — a dramatic beat is due`) in the tick output and the session brief.
Clocks that must not move on the calendar are declared `advance_on: "event"` and only
ever move by hand.

## A clock that fills fires (since 2026-08-14)

`_fire_if_filled` writes the clock's stored `consequence` into the consequence engine as
`[Clock — <name>] <text>`, with an `on_clock` trigger on the clock's last segment, so it
fires at once with any other `on_clock` consequences the fill reaches (until 2026-11-06 it
got a free-text trigger and sat waiting on an event that had already happened). Before this the text was
only echoed in a print, so a countdown running out was a line the GM might notice rather
than a beat that arrived. The clock's `consequence` field is authored when the clock is
created (`gm-clock.sh`), from the pressure the beat is meant to apply.

Firing is the **transition into full**, not a state check: a clock that was already full
fires nothing, and one reset or extended back below full fires again the next time it
fills. That is what keeps it to once per countdown without a flag to keep in sync
(`consequence_fired` is stamped as provenance, never read as a gate). A clock with no
`consequence` fires nothing.

The write is wrapped in `redirect_stdout(sys.stderr)`: `add_consequence` announces itself
on stdout, and this fires from inside `advance` and time updates, whose `--json` output is
parsed. `gm-clock.sh add` also gained `--consequence` / `--linked-plot`, which `add_clock`
had always accepted and the parser could never pass — so hand-made clocks were
structurally incapable of carrying the payload.

## Firing does not resolve

`tick()` stamps `last_fired_key` = `location|time|date` on newly fired consequences and
leaves them **active**. The stamp is an annotation, not a suppressor: a second tick in
the same scene still reports the match as already-fired (no re-stamp, no new provenance).
Walking away and coming back **re-arms it**, because the key changed.

The fire slice is still `limit=2` (highest-confidence first) so a beat does not stutter
with five payoffs at once — remaining matches are disclosed as matched-not-fired rather
than dropped. `check_pending(..., world_state)` uses the same disclose-not-hide rule.

- The GM can veto a firing narratively and nothing needs undoing; the consequence is
  still there.
- A consequence only leaves `active` via explicit `resolve <id>` or by expiring. A
  campaign that never resolves accumulates a permanently pending list.

## How triggers match, and one check that misfires

Structured triggers (`--trigger-type on_location|on_npc|on_time|on_death|on_clock|on_event`
with `--match`, repeatable for several triggers, any one of which fires the consequence).
`on_location` and `on_npc` hold ids (`location:<key>`, `npc:<key>`, see `lib/world_ids.py`),
checked when the consequence is added and compared exactly with the current location and
the NPCs present (2026-11-08; before, any substring matched, so "Ro" fired for Old Iron).
`on_time` holds a time-of-day word and fires exactly in its hours on the game clock
(`noon` 11:00–12:59; 2026-11-08, before which `noon` also fired in the Afternoon). `on_death`,
`on_clock` and `on_event` are the exceptions, event triggers never checked on the scene:
`on_death` fires once, inside `gm-npc.sh kill` / `gm-player.sh kill`; `on_clock` fires once
per segment, inside `gm-clock.sh advance` or the time update that moves the clock;
`on_learn` fires when a fact gets a holder (`gm-note.sh` and `gm-note.sh tell`);
`on_event` is matched by the GM, since
every fact recorded with `gm-note.sh` lists the consequences waiting on an event, and the
GM fires a fitting one with `gm-consequence.sh fire <id> --by <fact id>`. There is no word
matching: a consequence added with only a free-text trigger gets it as its `on_event`
trigger, and older entries with only free text are read that way (removed 2026-11-06:
upstream's fallback scored word overlap against the scene, firing on mere mentions and
missing paraphrases).

There is no expiry (removed 2026-11-07): `--expiry` was a word match against the scene
that a date never passed. A time limit is a clock.

## Provenance and the one-beat undo

Every firing appends to `provenance` in `consequences.json` (`gm-consequence.sh log`), and
`tick()` writes a `_snapshot` of the pre-fire lists. `rollback` restores that snapshot —
but the snapshot is overwritten by the next tick, so **rollback is exactly one beat deep**.

`WorldTick` keeps a separate, deeper log (`world-tick-log.json`) and rolls back by removing
the facts, consequences and clocks it added. `apply` writes every proposal; the cap of 3 is a
warning that names what overflowed, not a silent drop. A malformed or refused part undoes
the whole tick, and if the log write fails, `WorldTick.apply` undoes what it just wrote
rather than leaving un-rollbackable state.

## Presence is shared: the scene list

`tick_from_session` calls `npcs_present`, the same party-or-scene-list test as the
session brief and the place brief, so `on_npc` fires only for NPCs the GM put in the
scene (`gm-scene.sh enter`, which also runs the tick at once). See
[scene context](scene-context.md).

## Async plot planning — the plot desk (since 2026-08-16)

Mid/long-game planning gained a live plot-creation path and an async worker. Two facts
that span files:

- **`gm-plot.sh add` is the only run-time way to CREATE a plot** (`plot_manager.add_plot`).
  Before it, `plots.json` was populated solely by the `/import` extractor; the GM could
  only `update`/`complete`/`fail` existing rows. A seeded thread defaults to
  `status: dormant`, so it stays OUT of active STORY THREADS. Advancing it wakes it:
  `update_plot` flips `dormant`/`available` -> `active` (a not-yet-active thread that gets
  progress is now in play). `add` refuses to clobber an existing name — extend that one
  instead.
- **Dormant threads resurface on their own via READY THREADS.** `SessionManager._ready_threads`
  surfaces a dormant plot when one of its linked `npcs` is present (same `npcs_present`
  predicate as everything else), its linked `location` is current, or a clock whose
  `linked_plot` names it is at least half full — rendered as `--- READY THREADS ---` in the
  brief. It only *nudges*; the GM wakes the thread with `gm-plot.sh update`. The plot's
  `npcs`/`locations` are therefore load-bearing metadata, not decoration.

The **`plot-weaver`** agent (`.claude/agents/plot-weaver.md`) is the async front door:
spawned in the background from a one-line seed, it grounds the idea in RAG, weaves it onto
existing entities/edges/clocks (via the WORLD INDEX), and persists ONE dormant thread —
`add` + a `--linked-plot` clock + an `on_npc` surfacing consequence — then returns one line.
It is the story analog of the background scene-illustrator, and it fits "plan as you go,
never pre-build": one small dormant thread, not a gazetteer.

## Related

- [Scene context](scene-context.md) — where clocks, pending consequences, and READY THREADS surface
- [Importing a book](../flows/import-a-book.md) — where clocks and consequences get seeded
