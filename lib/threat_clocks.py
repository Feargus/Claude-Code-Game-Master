#!/usr/bin/env python3
"""
Threat clocks — felt, mounting pressure (DCC's floor-collapse countdown).

Named segmented clocks that advance on time or events, surfaced in the session
context so stakes are visible and trustworthy. A time clock runs on the in-game
wall clock: it stores when it started and when it is due, and every time change
recomputes how many segments are filled. An event clock is advanced by hand. A filled clock is the trigger for a
dramatic beat / book-native milestone. Tone-respecting: a kit/campaign that wants
no doom clock simply declares none. Dramatic choices made at inflection points are
recorded as consequences (via consequence_manager), tying the fork into the
reactive world.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager


class ThreatClockManager(EntityManager):
    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self._wsd = world_state_dir
        self.clocks_file = "threat-clocks.json"

    def _load(self) -> Dict[str, Any]:
        return self.json_ops.load_json(self.clocks_file) or {}

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
                  due_at: datetime = None, due_in_minutes: int = None) -> Dict[str, Any]:
        """Add a clock. A time clock is due at `due_at`, or `due_in_minutes` from
        now, or by default one day per segment from now."""
        from time_manager import STORED_FORMAT
        data = self._load()
        entry = {"current": 0, "max": int(segments), "advance_on": advance_on}
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
        that arrived. Firing writes a PENDING consequence — it does not resolve
        it or force the GM's hand, same as every other consequence.

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
        with contextlib.redirect_stdout(sys.stderr):
            cid = ConsequenceManager(self._wsd).add_consequence(
                f"[Clock — {name}] {text}", trigger=f"the {name} clock ran out")
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
        """Advance a clock by hand. The returned clock lists the on_clock
        consequences this fired under `fired` (not saved)."""
        data = self._load()
        c = data.get(name)
        if not c:
            return None
        before = int(c.get("current", 0))
        was_full = before >= int(c.get("max", 1))
        c["current"] = min(c["max"], before + int(ticks))
        self._fire_if_filled(name, c, was_full)
        self.json_ops.save_json(self.clocks_file, data)
        return dict(c, fired=self._fire_on_clock(name, before, c))

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

    def remove_clock(self, name: str) -> bool:
        data = self._load()
        if name in data:
            del data[name]
            self.json_ops.save_json(self.clocks_file, data)
            return True
        return False

    def get_clocks(self) -> Dict[str, Any]:
        return self._load()

    def is_full(self, name: str) -> bool:
        c = self._load().get(name)
        return bool(c and c.get("current", 0) >= c.get("max", 1))

    def full_clocks(self) -> Dict[str, Any]:
        return {n: c for n, c in self._load().items() if c.get("current", 0) >= c.get("max", 1)}

    def pending_beats(self) -> Dict[str, Any]:
        """Filled clocks = dramatic beats that are due (an inflection point)."""
        return self.full_clocks()

    def record_choice(self, prompt: str, chosen_fork: str, trigger: str = "player choice",
                      trigger_type: str = None, match: str = None) -> str:
        """Record a dramatic-choice fork as a consequence — the fork→reactive-world wire.

        The GM presents `prompt` with stakes-bearing forks at an inflection point;
        the player's chosen fork is written into the consequence engine so it pays
        off later (optionally with a structured trigger). Returns the consequence id.
        """
        from consequence_manager import ConsequenceManager
        cm = ConsequenceManager(self._wsd)
        text = f"[Choice — {prompt}] {chosen_fork}"
        return cm.add_consequence(text, trigger, trigger_type=trigger_type, match=match)

    @staticmethod
    def due_text(clock: Dict[str, Any]) -> str:
        """', due <time and date>' for a time clock that has a due time, else ''."""
        if clock.get("advance_on", "time") != "time" or not clock.get("due_at"):
            return ""
        from time_manager import STORED_FORMAT, derive_date
        due = datetime.strptime(clock["due_at"], STORED_FORMAT)
        return f", due {due:%H:%M}, {derive_date(due)}"

    @staticmethod
    def render(clocks: Dict[str, Any]) -> str:
        """Render clocks as filled/empty segment bars for the GM-visible context."""
        lines = []
        for name, c in clocks.items():
            cur, mx = int(c.get("current", 0)), int(c.get("max", 1))
            bar = "●" * cur + "○" * max(0, mx - cur)
            flag = "  ⚠ FULL" if cur >= mx else ""
            due = ThreatClockManager.due_text(c)
            lines.append(f"{name}: [{bar}] {cur}/{mx} (on {c.get('advance_on', 'time')}{due}){flag}")
        return "\n".join(lines)


def main():
    import argparse
    import json
    from cli_output import wants_json, strip_json_flag, emit

    parser = argparse.ArgumentParser(description="Threat clocks")
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("add"); p.add_argument("name"); p.add_argument("segments", type=int)
    p.add_argument("--on", default="time")
    p.add_argument("--consequence", help="what happens when it fills (fired into the world)")
    p.add_argument("--linked-plot", dest="linked_plot")
    p.add_argument("--due-in", dest="due_in", help="time clock: due after this long, e.g. 3d, 12h")
    p.add_argument("--due", help='time clock: due at "YYYY-MM-DD HH:MM"')
    p = sub.add_parser("advance"); p.add_argument("name"); p.add_argument("--ticks", type=int, default=1)
    p = sub.add_parser("remove"); p.add_argument("name")
    sub.add_parser("list")
    sub.add_parser("beats")  # filled clocks = beats due
    p = sub.add_parser("choose"); p.add_argument("prompt"); p.add_argument("chosen")
    p.add_argument("--trigger", default="player choice")
    p.add_argument("--trigger-type", dest="trigger_type")
    p.add_argument("--match")

    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help(); sys.exit(1)

    m = ThreatClockManager()
    if args.action == "add":
        from time_manager import TimeError, parse_duration, parse_time
        try:
            out = m.add_clock(args.name, args.segments, advance_on=args.on,
                              consequence=args.consequence, linked_plot=args.linked_plot,
                              due_at=parse_time(args.due) if args.due else None,
                              due_in_minutes=parse_duration(args.due_in) if args.due_in else None)
        except (TimeError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
    elif args.action == "advance":
        out = m.advance(args.name, args.ticks)
    elif args.action == "remove":
        out = {"removed": m.remove_clock(args.name)}
    elif args.action == "beats":
        out = m.pending_beats()
    elif args.action == "choose":
        out = {"consequence_id": m.record_choice(
            args.prompt, args.chosen, trigger=args.trigger,
            trigger_type=getattr(args, "trigger_type", None), match=args.match)}
    else:
        out = m.get_clocks()

    if json_mode:
        emit(out, json_mode=True)
    else:
        print(json.dumps(out, indent=2))
        if args.action == "list":
            print(m.render(out))
        if args.action == "advance" and out:
            from consequence_manager import print_fired
            print_fired(out.get("fired", []))


if __name__ == "__main__":
    main()
