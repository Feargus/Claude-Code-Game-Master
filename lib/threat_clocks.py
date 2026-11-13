#!/usr/bin/env python3
"""
Threat clocks — felt, mounting pressure (DCC's floor-collapse countdown).

Named segmented clocks that advance on time or events, surfaced in the session
context so stakes are visible and trustworthy. A time clock runs on the in-game
wall clock: it stores when it started and when it is due, and every time change
recomputes how many segments are filled. An event clock is advanced by hand.
A filled clock fires its consequence; consequences with an on_clock trigger
fire at the segment they name. Tone-respecting: a kit/campaign that wants no
doom clock simply declares none.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager

# A clock is named by a short key ("Tracker", "Slow scrub"): triggers, commands
# and the brief use it, so it must stay as it is. What the clock is about goes
# into its `text`, which can be reworded freely.
MAX_NAME_WORDS = 3
MAX_NAME_CHARS = 30


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

    def _load(self) -> Dict[str, Any]:
        return self.json_ops.load_json(self.clocks_file) or {}

    @staticmethod
    def _find(data: Dict[str, Any], raw) -> Optional[str]:
        """The key of the clock `raw` names: its short name (case ignored, with or
        without a leading "clock:"), or failing that its whole text. None if none."""
        from world_ids import find_clock  # the one lookup, shared with on_clock triggers
        return find_clock(data, raw) or None

    def _missing(self, raw) -> str:
        """Why `raw` names no clock, with close matches (the shared resolver's words)."""
        from world_ids import WorldIds
        return WorldIds(self.json_ops).resolve_as(raw, ("clock",))[1] or f"No clock '{raw}'."

    def _game_time(self) -> Optional[datetime]:
        # Imported here: time_manager imports this module.
        from time_manager import STORED_FORMAT
        stored = (self.json_ops.load_json("campaign-overview.json") or {}).get("game_time")
        return datetime.strptime(stored, STORED_FORMAT) if stored else None

    @staticmethod
    def _schedule(clock: Dict[str, Any], now: datetime) -> None:
        """Give a time clock its start and due time if it lacks them.

        A clock added before the campaign had a game time, or before clocks ran on
        the wall clock, gets one day per segment: it counts as started one day per
        filled segment ago, and is due one day per empty segment from now.
        """
        from time_manager import STORED_FORMAT
        cur, mx = int(clock.get("current", 0)), int(clock.get("max", 1))
        clock.setdefault("starts_at", (now - timedelta(days=cur)).strftime(STORED_FORMAT))
        clock.setdefault("due_at", (now + timedelta(days=mx - cur)).strftime(STORED_FORMAT))

    def add_clock(self, name: str, segments: int, advance_on: str = "time",
                  consequence: str = None, linked_plot: str = None,
                  due_at: datetime = None, due_in_minutes: int = None,
                  text: str = None) -> Dict[str, Any]:
        """Add a clock. `name` is its short key (check_name), `text` what it is
        about. A time clock is due at `due_at`, or `due_in_minutes` from now, or
        by default one day per segment from now."""
        name = check_name(name)
        from time_manager import STORED_FORMAT
        if int(segments) < 1:
            raise ValueError(f"A clock needs at least 1 segment, not {segments}.")
        if advance_on not in ("time", "event"):
            raise ValueError(f"A clock advances on time or event, not {advance_on!r}.")
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
        if consequence:
            entry["consequence"] = consequence
        if linked_plot:
            entry["linked_plot"] = linked_plot
        if advance_on == "time":
            now = self._game_time()
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
        return data[name]

    def _fire_if_filled(self, name: str, clock: Dict[str, Any], was_full: bool) -> Optional[str]:
        """Write a clock's stored consequence into the world as it FILLS.

        A clock carried its `consequence` text only as a printed FULL flag, so a
        countdown running out was a line the GM might notice rather than a beat
        that arrived. This writes a consequence on the clock's last segment, which
        fires at once; it stays pending until the GM resolves it, like any other.

        Firing is the *transition* into full, which is what keeps it to once per
        countdown without a flag to keep in sync: a clock that was already full
        fires nothing, and one reset or extended back below full fires again the
        next time it fills. Mutates `clock` (stamps `consequence_fired` as
        provenance); the caller saves.
        """
        if was_full or int(clock.get("current", 0)) < int(clock.get("max", 1)):
            return None
        text = clock.get("consequence")
        if not text:
            return None
        import contextlib
        from consequence_manager import ConsequenceManager
        # add_consequence announces itself on stdout; this one fires from inside
        # advance and time updates, whose --json output must stay parseable.
        # Its trigger is the clock's last segment, so _fire_on_clock fires it right
        # after the save, with everything else the fill set off.
        with contextlib.redirect_stdout(sys.stderr):
            cid = ConsequenceManager(self._wsd).add_consequence(
                f"[Clock — {name}] {text}", trigger=f"the {name} clock ran out",
                trigger_type="on_clock", match=f"{name}:{clock.get('max', 1)}")
        clock["consequence_fired"] = cid
        return cid

    def _fire_on_clock(self, name: str, before: int, clock: Dict[str, Any]) -> list:
        """Fire the on_clock consequences for every segment the clock just reached.

        Called after the clocks file is saved, since a fired consequence may start
        a clock of its own. Returns the fired consequences.
        """
        from consequence_manager import ConsequenceManager
        cm = ConsequenceManager(self._wsd)
        mx = int(clock.get("max", 1))
        fired = []
        for segment in range(before + 1, int(clock.get("current", 0)) + 1):
            fired += cm.fire_event("on_clock", f"{name}:{segment}",
                                   f"clock {name} reached {segment}/{mx}")
        return fired

    def advance(self, name: str, ticks: int = 1) -> Optional[Dict[str, Any]]:
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
        was_full = before >= int(c.get("max", 1))
        c["current"] = min(c["max"], before + int(ticks))
        self._fire_if_filled(name, c, was_full)
        self.json_ops.save_json(self.clocks_file, data)
        return dict(c, fired=self._fire_on_clock(name, before, c))

    def move_due(self, name: str, due_at: datetime = None, due_in_minutes: int = None,
                 shift_minutes: int = None) -> Dict[str, Any]:
        """Move a time clock's due time; give exactly one of the three.

        `shift_minutes` moves the current due time (negative = earlier),
        `due_in_minutes` counts from the game time, `due_at` is the moment itself.
        The start stays, so the clock is recomputed at once: brought forward, it may
        fill segments now (and fire them); pushed back, it keeps what it has filled
        and waits for time to catch up, since clocks never empty. Returns the clock
        with the on_clock consequences it fired under `fired` (not saved).
        """
        from time_manager import STORED_FORMAT
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
        now = self._game_time()
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

    def update_time_clocks(self, now: datetime) -> Dict[str, Any]:
        """Recompute every time clock from the game time.

        Filled segments are the share of the time between start and due that has
        passed, so a 4-segment clock due in 4 days fills one segment a day, and is
        full once the due time is reached. Clocks only ever fill up: setting the
        time back never empties one. `gm-time.sh` calls this after every change.
        Event clocks (advance_on != 'time') are untouched — the GM advances those
        by hand. Returns {name: clock} for the clocks that moved; each lists the
        on_clock consequences it fired under `fired` (not saved).
        """
        from time_manager import STORED_FORMAT
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
            self._fire_if_filled(name, c, was_full=False)  # full clocks skipped above
            moved[name] = (cur, c)
            changed = True
        if changed:
            self.json_ops.save_json(self.clocks_file, data)
        return {name: dict(c, fired=self._fire_on_clock(name, before, c))
                for name, (before, c) in moved.items()}

    def set_text(self, name: str, text: str) -> Dict[str, Any]:
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

    def remove_clock(self, name: str) -> bool:
        data = self._load()
        name = self._find(data, name)
        if name is not None:
            del data[name]
            self.json_ops.save_json(self.clocks_file, data)
            return True
        return False

    def get_clocks(self) -> Dict[str, Any]:
        return self._load()

    def is_full(self, name: str) -> bool:
        data = self._load()
        c = data.get(self._find(data, name) or "")
        return bool(c and c.get("current", 0) >= c.get("max", 1))

    def full_clocks(self) -> Dict[str, Any]:
        return {n: c for n, c in self._load().items() if c.get("current", 0) >= c.get("max", 1)}

    def pending_beats(self) -> Dict[str, Any]:
        """Filled clocks = dramatic beats that are due (an inflection point)."""
        return self.full_clocks()

    @staticmethod
    def due_text(clock: Dict[str, Any]) -> str:
        """', due <time and date>' for a time clock that has a due time, else ''."""
        if clock.get("advance_on", "time") != "time" or not clock.get("due_at"):
            return ""
        from time_manager import STORED_FORMAT, derive_date
        due = datetime.strptime(clock["due_at"], STORED_FORMAT)
        return f", due {due:%H:%M}, {derive_date(due)}"

    @staticmethod
    def by_urgency(clocks: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
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
    def render(clocks: Dict[str, Any]) -> str:
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
    import json
    from cli_output import wants_json, strip_json_flag, emit

    parser = argparse.ArgumentParser(description="Threat clocks")
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("add")
    p.add_argument("name", help='the short key triggers and commands use, e.g. "Tracker"')
    p.add_argument("segments", type=int)
    p.add_argument("--text", help="what the clock is about (can be reworded later)")
    p.add_argument("--on", default="time")
    p.add_argument("--consequence", help="what happens when it fills (fired into the world)")
    p.add_argument("--linked-plot", dest="linked_plot")
    p.add_argument("--due-in", dest="due_in", help="time clock: due after this long, e.g. 3d, 12h")
    p.add_argument("--due", help='time clock: due at "YYYY-MM-DD HH:MM"')
    p = sub.add_parser("advance"); p.add_argument("name"); p.add_argument("--ticks", type=int, default=1)
    p = sub.add_parser("due"); p.add_argument("name")
    p.add_argument("--earlier", help="due this much sooner, e.g. 1d, 6h")
    p.add_argument("--later", help="due this much later")
    p.add_argument("--due-in", dest="due_in", help="due this long from now")
    p.add_argument("--due", help='due at "YYYY-MM-DD HH:MM"')
    p = sub.add_parser("text"); p.add_argument("name"); p.add_argument("text")
    p = sub.add_parser("remove"); p.add_argument("name")
    sub.add_parser("list")
    sub.add_parser("beats")  # filled clocks = beats due

    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help(); sys.exit(1)

    m = ThreatClockManager()
    # The clock's own short name, however it was typed (case, "clock:", its text).
    shown = m._find(m.get_clocks(), getattr(args, "name", "")) or getattr(args, "name", "")
    if args.action == "text":
        try:
            out = m.set_text(args.name, args.text)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
    elif args.action == "add":
        from time_manager import TimeError, parse_duration, parse_time
        try:
            out = m.add_clock(args.name, args.segments, advance_on=args.on,
                              consequence=args.consequence, linked_plot=args.linked_plot,
                              text=args.text,
                              due_at=parse_time(args.due) if args.due else None,
                              due_in_minutes=parse_duration(args.due_in) if args.due_in else None)
        except (TimeError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
    elif args.action == "advance":
        try:
            out = m.advance(args.name, args.ticks)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
        if out is None:
            print(f"Error: {m._missing(args.name)}", file=sys.stderr)
            sys.exit(1)
    elif args.action == "due":
        from time_manager import TimeError, parse_duration, parse_time
        try:
            shift = (-parse_duration(args.earlier) if args.earlier else
                     parse_duration(args.later) if args.later else None)
            if args.earlier and args.later:
                raise ValueError("Give exactly one of --earlier, --later, --due-in or --due.")
            out = m.move_due(args.name, due_at=parse_time(args.due) if args.due else None,
                             due_in_minutes=parse_duration(args.due_in) if args.due_in else None,
                             shift_minutes=shift)
        except (TimeError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
    elif args.action == "remove":
        out = {"removed": m.remove_clock(args.name)}
    elif args.action == "beats":
        out = m.pending_beats()
    else:
        out = m.get_clocks()

    if json_mode:
        emit(out, json_mode=True)
    else:
        print(json.dumps(out, indent=2))
        if args.action == "list":
            print(m.render(out))
        if args.action in ("due", "text"):
            print(m.render({shown: out}))
        if args.action in ("advance", "due") and out:
            from consequence_manager import print_fired
            print_fired(out.get("fired", []))


if __name__ == "__main__":
    main()
