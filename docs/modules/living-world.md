# The living world

*Claude, 2026-11-19: kept from the upstream docs, not yet rewritten.*

Three systems claim to run without the player: consequences fire on triggers, threat
clocks tick toward a beat, and a between-sessions world tick advances off-screen
developments. **They are wired to very different degrees.** Verified 2026-08-13:

| System | Automatic trigger | How it actually runs |
|---|---|---|
| Consequences | **Yes** | `gm-time.sh advance` checks them at each moment of its walk (below), `set` once, `gm-session.sh move` at the destination (on the way only the time can fire one) |
| Threat clocks | **Time-clocks: yes** (since 2026-08-13) | `gm-time.sh advance <duration>` (or `set`) moves the campaign's `game_time`, and every `advance_on: "time"` clock is recomputed from it: it stores `starts_at` and `due_at`, and its filled share is the share of that span that has passed. A clock with no due time gets one day per segment. Event clocks stay manual: `gm-clock.sh advance "<name>" [--ticks N]`; a time clock is refused there, since a push by hand would only stall it until time caught up. A time clock is sped up or slowed down by moving its due time instead: `gm-clock.sh due "<name>" --earlier|--later <duration>` (or `--due-in`, `--due`). The start stays, and the clock is recomputed at once, so bringing it forward may fill segments and fire them on the spot; pushing it back never empties it. Filling one fires its consequence (below) |
| World tick | **No** — GM-invoked by design (`/gm world`) | the developments are a model call; `gm-session.sh world-tick <<'EOF'` (the JSON, then `EOF`) records each as a fact, plus an optional consequence (with real triggers) and/or clock (since 2026-11-06; before, each was a consequence with no usable trigger), is all-or-nothing, warns (naming the overflow) when the count exceeds the advisory cap of 3, and stays logged / rollback-able. Before 2026-08-13 `WorldTick` had no caller at all |

**The walk, and where time stops (since 2026-11-18, `lib/time_walk.py`, `lib/time_stops.py`).**
`advance` doesn't jump: every source of change says when it next changes (a time
clock's next segment, each world rule's block `next_time`, the time-of-day words a
waiting consequence is on), and the step goes from one such moment to the next,
setting the time, moving clocks and rules and checking consequences at each. It stops
at the first moment with something to play now (a consequence that fires and isn't
`offscreen`, a clock that fills, a rule's result with a Do-now line for a holder who
is here) and prints the timeline of the routine rest, how much is left and the
command to go on. `--through "<name>"` (a rule, `"<rule>:<outcome>"`, a consequence id,
a clock) doesn't stop for those; `--through` alone never stops. `gm-session.sh move
--takes` stops on the way (exit 3 from `time_manager.py`; the party doesn't move).
Eight days of a bag drawn every 4 hours take about 0.9 s on the RPi.

So three weeks and ten minutes are not the same pressure: the GM passes how much time
actually elapsed, a clock is full exactly when its due time arrives, and a full clock announces
itself (`⚠ FULL — a dramatic beat is due`) in the tick output and the session brief.
Clocks that must not move on the calendar are declared `advance_on: "event"` and only
ever move by hand.

## A clock that fills fires

`_fire_if_filled` writes the clock's stored `consequence` into the consequence engine,
with an `on_clock` trigger on the clock's last segment, so it fires at once with any
other `on_clock` consequences the fill reaches; its reason is "clock <name> at 3/3". A
countdown running out is a beat that arrives, not a line the GM might notice. The clock's `consequence` field is authored when the clock is
created (`gm-clock.sh`), from the pressure the beat is meant to apply.

Firing is the **transition into full**, not a state check: a clock that was already full
fires nothing, and one reset or extended back below full fires again the next time it
fills. That is what keeps it to once per countdown without a flag to keep in sync
(`consequence_fired` is stamped as provenance, never read as a gate). A clock with no
`consequence` fires nothing.

The write is wrapped in `redirect_stdout(sys.stderr)`: `add_consequence` announces itself
on stdout, and this fires from inside `advance` and time updates, whose own output should
not carry it. `gm-clock.sh add` also gained `--consequence` / `--plot`, which `add_clock`
had always accepted and the parser could never pass — so hand-made clocks were
structurally incapable of carrying the payload.

## Waiting, fired, resolved

A consequence fires **once**. Firing writes `fired` (the reason, the real time, the game
time, the fact that set it off) onto it and leaves it in `active`; from then on it matches
no trigger, whatever its triggers and however long it stays. The brief lists it as `FIRED`
until `gm-consequence.sh resolve` moves it to `resolved`. `gm-consequence.sh rearm` removes
`fired`, so it waits again (the moment was wrong, or it should happen once more); what its
effects did stays done.

Until 2026-11-16 firing only stamped the scene (`last_fired_key`), so an unresolved
consequence fired again when the time of day changed, or when a second trigger matched.

## The log of firings

Every firing appends to `provenance` in `consequences.json` (`gm-consequence.sh log`).
There is no rollback: git is the undo.

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
`add` + a `--plot` clock + an `on_npc` surfacing consequence — then returns one line.
It fits "plan as you go,
never pre-build": one small dormant thread, not a gazetteer.

## Related

- [Scene context](scene-context.md) — where clocks, pending consequences, and READY THREADS surface
- [Importing a book](../flows/import-a-book.md) — where clocks and consequences get seeded
