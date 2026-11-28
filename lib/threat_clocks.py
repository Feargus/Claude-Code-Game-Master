#!/usr/bin/env python3
"""
Threat clocks — felt, mounting pressure (DCC's floor-collapse countdown).

Named segmented clocks that advance on time or events, surfaced in the session
context so stakes are visible and trustworthy. A time clock runs on the in-game
wall clock: it stores when it started and when it is due, and every time change
recomputes how many segments are filled. An event clock is advanced by hand.
A clock only counts. What it brings are consequences waiting on its segments:
signs on the way, and its outcome on the last segment (made with the clock from
its `consequence` text, add_clock); each fires when the clock reaches its
segment. Tone-respecting: a campaign that wants no doom clock simply declares
none.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager
from game_time import STORED_FORMAT, current_time

# A clock is named by a short key ("Tracker", "Slow scrub"): triggers, commands
# and the brief use it, so it must stay as it is. What the clock is about goes
# into its `text`, which can be reworded freely.
MAX_NAME_WORDS = 3
MAX_NAME_CHARS = 30


def clock_of(trigger) -> tuple[str, int | None]:
    """(clock name, segment or None) of an on_clock trigger ("clock:<name>:<segment>"),
    ('', None) for any other trigger."""
    if not isinstance(trigger, dict) or trigger.get("type") != "on_clock":
        return "", None
    match = str(trigger.get("match", ""))
    rest = match[len("clock:"):] if match.lower().startswith("clock:") else match
    name, _, segment = rest.rpartition(":")
    return (name, int(segment)) if segment.isdigit() and name else (rest, None)


def outcomes(store, clocks) -> dict[str, list[dict[str, Any]]]:
    """{clock name: the consequences still waiting on its last segment}: what each
    clock brings when it is full."""
    out: dict[str, list[dict[str, Any]]] = {}
    lower = {str(k).lower(): k for k in (clocks or {})}
    for c in (store or {}).get("active", []) if isinstance(store, dict) else []:
        if not isinstance(c, dict) or c.get("fired"):
            continue
        for t in c.get("triggers") or []:
            name, segment = clock_of(t)
            key = lower.get(name.lower())
            if key is not None and segment == int(clocks[key].get("max", 1)):
                out.setdefault(key, []).append(c)
                break
    return out


def check_name(raw) -> str:
    """A new clock's short name, tidied (single spaces), or ValueError."""
    name = " ".join(str(raw or "").split())
    if not name:
        raise ValueError("A clock needs a short name, e.g. \"Tracker\".")
    if ":" in name or len(name.split()) > MAX_NAME_WORDS or len(name) > MAX_NAME_CHARS:
        raise ValueError(
            f"A clock's name is a short key, one to {MAX_NAME_WORDS} words and at most "
            f"{MAX_NAME_CHARS} characters, without a colon (\"Tracker\", \"Slow scrub\"): "
            f"triggers and commands use it, so it has to stay the same. Put what the clock "
            f"is about into its text (gm-clock.sh add \"<short name>\" N --text \"...\"); "
            f"got '{name}'.")
    return name


class ThreatClockManager(EntityManager):
    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self._wsd = world_state_dir
        self.clocks_file = "threat-clocks.json"

    def _load(self) -> dict[str, Any]:
        return self.json_ops.load_json(self.clocks_file) or {}

    @staticmethod
    def _find(data: dict[str, Any], raw) -> str | None:
        """The key of the clock `raw` names: its short name (case ignored, with or
        without a leading "clock:"), or failing that its whole text. None if none."""
        from world_ids import find_clock  # the one lookup, shared with on_clock triggers
        return find_clock(data, raw) or None

    def _missing(self, raw) -> str:
        """Why `raw` names no clock, with close matches (the shared resolver's words)."""
        from world_ids import WorldIds
        return WorldIds(self.json_ops).resolve_as(raw, ("clock",))[1] or f"No clock '{raw}'."

    @staticmethod
    def _schedule(clock: dict[str, Any], now: datetime) -> None:
        """Give a time clock its start and due time if it lacks them.

        A clock added before the campaign had a game time, or before clocks ran on
        the wall clock, gets one day per segment: it counts as started one day per
        filled segment ago, and is due one day per empty segment from now.
        """
        cur, mx = int(clock.get("current", 0)), int(clock.get("max", 1))
        clock.setdefault("starts_at", (now - timedelta(days=cur)).strftime(STORED_FORMAT))
        clock.setdefault("due_at", (now + timedelta(days=mx - cur)).strftime(STORED_FORMAT))

    def add_clock(self, name: str, segments: int, advance_on: str = "time",
                  consequence: str = None, plots=None,
                  due_at: datetime = None, due_in_minutes: int = None,
                  text: str = None) -> dict[str, Any]:
        """Add a clock. `name` is its short key (check_name), `text` what it is
        about. A time clock is due at `due_at`, or `due_in_minutes` from now, or
        by default one day per segment from now."""
        name = check_name(name)
        if int(segments) < 1:
            raise ValueError(f"A clock needs at least 1 segment, not {segments}.")
        if advance_on not in ("time", "event"):
            raise ValueError(f"A clock advances on time or event, not {advance_on!r}.")
        if advance_on == "event" and (due_at is not None or due_in_minutes is not None):
            raise ValueError("Only a time clock has a due time: an event clock fills when "
                             "the story advances it (gm-clock.sh advance). Drop --due/--due-in, "
                             "or make it a time clock (--on time).")
        data = self._load()
        taken = self._find(data, name)
        if taken is not None:
            c = data[taken]
            raise ValueError(
                f"A clock '{taken}' exists already ({c.get('current', 0)}/{c.get('max', 1)}); "
                f"adding it again would reset it. Advance it or move its due time "
                f"(gm-clock.sh advance / due), or remove it first (gm-clock.sh remove).")
        entry = {"current": 0, "max": int(segments), "advance_on": advance_on}
        if str(text or "").strip():
            entry = {"text": str(text).strip(), **entry}
        if plots:
            from plot_manager import resolve_plots
            keys, errors = resolve_plots(self.json_ops, plots)
            if errors:
                raise ValueError(" ".join(errors))
            entry["plots"] = keys
        if advance_on == "time":
            now = current_time(self.json_ops)
            if due_in_minutes is not None:
                if now is None:
                    raise ValueError("The campaign has no game time yet, so a clock can't "
                                     "be due in a duration. Set the time first, or use --due.")
                due_at = now + timedelta(minutes=due_in_minutes)
            if due_at is not None:
                entry["due_at"] = due_at.strftime(STORED_FORMAT)
            if now is not None:
                entry["starts_at"] = now.strftime(STORED_FORMAT)
                self._schedule(entry, now)
        data[name] = entry
        self.json_ops.save_json(self.clocks_file, data)
        if str(consequence or "").strip():
            return dict(data[name], outcome=self._add_outcome(name, entry, consequence))
        return data[name]

    def _add_outcome(self, name: str, clock: dict[str, Any], text: str) -> str:
        """The clock's outcome: a consequence waiting on its last segment, made now,
        so what the clock brings is a consequence like any other (shown, compared,
        fired and resolved the same way). Returns its id; removes the clock and
        raises ValueError if it is refused."""
        import contextlib
        import io

        from consequence_manager import ConsequenceManager
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cid = ConsequenceManager(self._wsd).add_consequence(
                str(text).strip(), trigger_type="on_clock", match=f"{name}:{clock['max']}",
                plots=clock.get("plots"))
        if not cid:
            self.remove_clock(name)
            why = " ".join(ln.replace("[ERROR] ", "") for ln in err.getvalue().splitlines())
            raise ValueError(f"The clock's outcome was refused, so the clock wasn't added: {why}")
        return cid

    def _fire_on_clock(self, name: str, before: int, clock: dict[str, Any]) -> list:
        """Fire the on_clock consequences for every segment the clock just reached.

        Called after the clocks file is saved, since a fired consequence may start
        a clock of its own. Returns the fired consequences.
        """
        from consequence_manager import ConsequenceManager
        cm = ConsequenceManager(self._wsd)
        mx = int(clock.get("max", 1))
        fired = []
        for segment in range(before + 1, int(clock.get("current", 0)) + 1):
            # The id, and the bare form consequences stored before clocks had ids.
            fired += cm.fire_event("on_clock", [f"clock:{name}:{segment}", f"{name}:{segment}"],
                                   f"clock {name} at {segment}/{mx}")
        return fired

    def advance(self, name: str, ticks: int = 1) -> dict[str, Any] | None:
        """Advance an event clock by hand. The returned clock lists the on_clock
        consequences this fired under `fired` (not saved).

        A time clock is refused: game time fills it, and a push by hand would
        only stall it until time caught up, full at the same moment as before.
        """
        data = self._load()
        name = self._find(data, name)
        if name is None:
            return None
        c = data[name]
        if c.get("advance_on", "time") == "time":
            raise ValueError(f"'{name}' is a time clock: it fills as game time passes "
                             f"(gm-time.sh), not by hand.")
        if int(ticks) < 1:
            raise ValueError(f"--ticks must be at least 1, not {ticks}.")
        before = int(c.get("current", 0))
        c["current"] = min(c["max"], before + int(ticks))
        self.json_ops.save_json(self.clocks_file, data)
        return dict(c, fired=self._fire_on_clock(name, before, c))

    def move_due(self, name: str, due_at: datetime = None, due_in_minutes: int = None,
                 shift_minutes: int = None) -> dict[str, Any]:
        """Move a time clock's due time; give exactly one of the three.

        `shift_minutes` moves the current due time (negative = earlier),
        `due_in_minutes` counts from the game time, `due_at` is the moment itself.
        The start stays, so the clock is recomputed at once: brought forward, it may
        fill segments now (and fire them); pushed back, it keeps what it has filled
        and waits for time to catch up, since clocks never empty. Returns the clock
        with the on_clock consequences it fired under `fired` (not saved).
        """
        if sum(x is not None for x in (due_at, due_in_minutes, shift_minutes)) != 1:
            raise ValueError("Give exactly one of --earlier, --later, --due-in or --due.")
        data = self._load()
        key = self._find(data, name)
        if key is None:
            raise ValueError(self._missing(name))
        name, c = key, data[key]
        if c.get("advance_on", "time") != "time":
            raise ValueError(f"'{name}' is an event clock: it has no due time. "
                             f"Advance it by hand instead.")
        if int(c.get("current", 0)) >= int(c.get("max", 1)):
            raise ValueError(f"'{name}' is already full.")
        now = current_time(self.json_ops)
        if now is None and due_at is None:
            raise ValueError("The campaign has no game time yet. Set it first, or use --due.")
        if now is not None:
            self._schedule(c, now)
        if shift_minutes is not None:
            due_at = datetime.strptime(c["due_at"], STORED_FORMAT) + timedelta(minutes=shift_minutes)
        elif due_in_minutes is not None:
            due_at = now + timedelta(minutes=due_in_minutes)
        if "starts_at" in c and due_at <= datetime.strptime(c["starts_at"], STORED_FORMAT):
            raise ValueError(f"'{name}' started {c['starts_at'].replace('T', ' ')}; "
                             f"it can't be due before that.")
        c["due_at"] = due_at.strftime(STORED_FORMAT)
        self.json_ops.save_json(self.clocks_file, data)
        moved = self.update_time_clocks(now) if now is not None else {}
        return moved.get(name) or dict(self._load()[name], fired=[])

    def next_moment(self, after: datetime) -> tuple[datetime, list[str]] | None:
        """The earliest moment after `after` at which a time clock reaches its next
        segment (the time `update_time_clocks` would first move it), with the clocks
        due then. Segment k of m is reached when k/m of the time from start to due
        has passed, to the minute; the last at the due time."""
        import math
        due_at: dict[datetime, list[str]] = {}
        for name, c in self._load().items():
            if c.get("advance_on", "time") != "time" or "starts_at" not in c or "due_at" not in c:
                continue
            cur, mx = int(c.get("current", 0)), int(c.get("max", 1))
            if cur >= mx:
                continue
            starts = datetime.strptime(c["starts_at"], STORED_FORMAT)
            due = datetime.strptime(c["due_at"], STORED_FORMAT)
            span = int((due - starts).total_seconds() // 60)
            moment = min(due, starts + timedelta(minutes=math.ceil((cur + 1) * span / mx)))
            due_at.setdefault(max(moment, after + timedelta(minutes=1)), []).append(name)
        if not due_at:
            return None
        first = min(due_at)
        return first, due_at[first]

    def update_time_clocks(self, now: datetime) -> dict[str, Any]:
        """Recompute every time clock from the game time.

        Filled segments are the share of the time between start and due that has
        passed, so a 4-segment clock due in 4 days fills one segment a day, and is
        full once the due time is reached. Clocks only ever fill up: setting the
        time back never empties one. `gm-time.sh` calls this after every change.
        Event clocks (advance_on != 'time') are untouched — the GM advances those
        by hand. Returns {name: clock} for the clocks that moved; each lists the
        on_clock consequences it fired under `fired` (not saved).
        """
        data = self._load()
        moved = {}
        changed = False
        for name, c in data.items():
            if c.get("advance_on", "time") != "time":
                continue
            if "starts_at" not in c or "due_at" not in c:
                self._schedule(c, now)
                changed = True
            cur, mx = int(c.get("current", 0)), int(c.get("max", 1))
            if cur >= mx:
                continue
            starts = datetime.strptime(c["starts_at"], STORED_FORMAT)
            due = datetime.strptime(c["due_at"], STORED_FORMAT)
            if now >= due:
                filled = mx
            else:
                span = int((due - starts).total_seconds() // 60)
                elapsed = int((now - starts).total_seconds() // 60)
                filled = mx * elapsed // span if span > 0 else 0
            if filled <= cur:
                continue
            c["current"] = filled
            moved[name] = (cur, c)
            changed = True
        if changed:
            self.json_ops.save_json(self.clocks_file, data)
        return {name: dict(c, fired=self._fire_on_clock(name, before, c))
                for name, (before, c) in moved.items()}

    def set_text(self, name: str, text: str) -> dict[str, Any]:
        """Reword what a clock is about; its short name, which triggers use,
        stays. An empty text removes it. Returns the clock; raises ValueError."""
        data = self._load()
        key = self._find(data, name)
        if key is None:
            raise ValueError(self._missing(name))
        rest = {k: v for k, v in data[key].items() if k != "text"}
        data[key] = {"text": text.strip(), **rest} if str(text or "").strip() else rest
        self.json_ops.save_json(self.clocks_file, data)
        return data[key]

    def remove_clock(self, name: str) -> list[str] | None:
        """Remove a clock and what still waits on it: a consequence waiting only on
        this clock (a sign, its outcome) goes; one that also waits on something else
        keeps its other triggers. What has fired stays. Returns the ids of the
        consequences removed, or None if there is no such clock."""
        data = self._load()
        name = self._find(data, name)
        if name is None:
            return None
        del data[name]
        self.json_ops.save_json(self.clocks_file, data)
        store = self.json_ops.load_json("consequences.json") or {}
        removed, kept, changed = [], [], False
        for c in store.get("active", []):
            mine = [t for t in c.get("triggers") or [] if clock_of(t)[0].lower() == name.lower()]
            if c.get("fired") or not mine:
                kept.append(c)
                continue
            rest = [t for t in c["triggers"] if t not in mine]
            changed = True
            if rest:
                kept.append(dict(c, triggers=rest))
            else:
                removed.append(c.get("id"))
        if changed:
            store["active"] = kept
            self.json_ops.save_json("consequences.json", store)
        return removed

    def get_clocks(self) -> dict[str, Any]:
        return self._load()

    def full_clocks(self) -> dict[str, Any]:
        """The full clocks: dramatic beats that are due."""
        return {n: c for n, c in self._load().items() if c.get("current", 0) >= c.get("max", 1)}

    @staticmethod
    def due_text(clock: dict[str, Any]) -> str:
        """', due <time and date>' for a time clock that has a due time, else ''."""
        if clock.get("advance_on", "time") != "time" or not clock.get("due_at"):
            return ""
        from time_manager import derive_date  # here: time_manager imports this module
        due = datetime.strptime(clock["due_at"], STORED_FORMAT)
        return f", due {due:%H:%M}, {derive_date(due)}"

    @staticmethod
    def by_urgency(clocks: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """(name, clock) pairs, most urgent first: full clocks (a beat is due),
        then time clocks by due time, soonest first, then event clocks (no due
        time), fullest first. Ties keep the order the clocks were made in."""
        def key(item):
            c = item[1]
            cur, mx = int(c.get("current", 0)), max(1, int(c.get("max", 1)))
            if cur >= mx:
                return (0, "", 0.0)
            if c.get("advance_on", "time") == "time" and c.get("due_at"):
                return (1, str(c["due_at"]), 0.0)
            return (2, "", -cur / mx)
        return sorted(clocks.items(), key=key)

    @staticmethod
    def render(clocks: dict[str, Any]) -> str:
        """Render clocks as filled/empty segment bars for the GM-visible context,
        most urgent first."""
        lines = []
        for name, c in ThreatClockManager.by_urgency(clocks):
            cur, mx = int(c.get("current", 0)), int(c.get("max", 1))
            bar = "●" * cur + "○" * max(0, mx - cur)
            flag = "  ⚠ FULL" if cur >= mx else ""
            due = ThreatClockManager.due_text(c)
            about = f" — {c['text']}" if c.get("text") else ""
            lines.append(f"{name}: [{bar}] {cur}/{mx} (on {c.get('advance_on', 'time')}{due})"
                         f"{flag}{about}")
        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Threat clocks")
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("add")
    p.add_argument("name", help='the short key triggers and commands use, e.g. "Tracker"')
    p.add_argument("segments", type=int)
    p.add_argument("--text", help="what the clock is about (can be reworded later)")
    p.add_argument("--on", default="time")
    p.add_argument("--consequence", help="what happens when it fills (fired into the world)")
    p.add_argument("--plot", action="append", dest="plots", default=[],
                   help="the plot it belongs to (repeatable)")
    p.add_argument("--due-in", dest="due_in", help="time clock: due after this long, e.g. 3d, 12h")
    p.add_argument("--due", help='time clock: due at "YYYY-MM-DD HH:MM"')
    p = sub.add_parser("advance")
    p.add_argument("name")
    p.add_argument("--ticks", type=int, default=1)
    p = sub.add_parser("due")
    p.add_argument("name")
    p.add_argument("--earlier", help="due this much sooner, e.g. 1d, 6h")
    p.add_argument("--later", help="due this much later")
    p.add_argument("--due-in", dest="due_in", help="due this long from now")
    p.add_argument("--due", help='due at "YYYY-MM-DD HH:MM"')
    p = sub.add_parser("text")
    p.add_argument("name")
    p.add_argument("text")
    p = sub.add_parser("remove")
    p.add_argument("name")
    sub.add_parser("list")
    sub.add_parser("beats")  # filled clocks = beats due

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    m = ThreatClockManager()

    def refuse(message: str):
        print(f"[ERROR] {message}", file=sys.stderr)
        sys.exit(1)

    def line(clock_name: str, clock: dict[str, Any]) -> str:
        return m.render({clock_name: clock})

    try:
        if args.action == "add":
            from time_manager import TimeError, parse_duration, parse_time
            try:
                due_at = parse_time(args.due) if args.due else None
                due_in = parse_duration(args.due_in) if args.due_in else None
            except TimeError as error:
                refuse(str(error))
            out = m.add_clock(args.name, args.segments, advance_on=args.on,
                              consequence=args.consequence, plots=args.plots,
                              text=args.text, due_at=due_at, due_in_minutes=due_in)
            key = m._find(m.get_clocks(), args.name)
            due = ThreatClockManager.due_text(out)        # computed: news to the GM
            text = [f"[SUCCESS] Added clock {key}" + (f" ({due[2:]})" if due else "")
                    + (f", with its outcome {out['outcome']}" if out.get("outcome") else "")]
            if out.get("outcome"):
                from recall_notes import event_lines
                text += event_lines(m.campaign_dir, [f"consequence:{out['outcome']}"])
        elif args.action == "advance":
            out = m.advance(args.name, args.ticks)
            if out is None:
                refuse(m._missing(args.name))
            key = m._find(m.get_clocks(), args.name)
            text = [line(key, out)]
        elif args.action == "due":
            from time_manager import TimeError, parse_duration, parse_time
            if sum(bool(x) for x in (args.earlier, args.later, args.due_in, args.due)) != 1:
                refuse("Give exactly one of --earlier, --later, --due-in or --due.")
            try:
                shift = (-parse_duration(args.earlier) if args.earlier else
                         parse_duration(args.later) if args.later else None)
                due_at = parse_time(args.due) if args.due else None
                due_in = parse_duration(args.due_in) if args.due_in else None
            except TimeError as error:
                refuse(str(error))
            out = m.move_due(args.name, due_at=due_at, due_in_minutes=due_in,
                             shift_minutes=shift)
            key = m._find(m.get_clocks(), args.name)
            text = [line(key, out)]
        elif args.action == "text":
            out = m.set_text(args.name, args.text)
            key = m._find(m.get_clocks(), args.name)
            text = [f"[SUCCESS] {line(key, out)}"]
        elif args.action == "remove":
            key = m._find(m.get_clocks(), args.name)
            removed = m.remove_clock(args.name)
            if removed is None:
                refuse(m._missing(args.name))
            out = {"removed": key}
            text = [f"[SUCCESS] Removed clock {key}"
                    + (f", and what waited on it: {', '.join(removed)}" if removed else "")]
        elif args.action == "beats":
            out = m.full_clocks()
            text = [m.render(out) if out else "No clock is full."]
        else:
            out = m.get_clocks()
            text = [m.render(out) if out else "No clocks yet (gm-clock.sh add)."]
    except ValueError as error:
        refuse(str(error))

    print("\n".join(text))
    if args.action in ("advance", "due") and out:
        from consequence_manager import print_fired
        print_fired(out.get("fired", []))

if __name__ == "__main__":
    main()
