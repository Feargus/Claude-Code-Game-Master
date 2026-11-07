#!/usr/bin/env python3
"""
Off-screen developments (/gm world): the world keeps living when you look away.

The GM proposes a few small developments (a model call in /gm). This module
owns the deterministic machinery. Each development is something that HAPPENED,
recorded as a fact; it may also set something in motion: a consequence with a
real trigger, and/or a threat clock. A tick is all-or-nothing (an invalid part
undoes the whole tick), warns past an advisory cap (default 3), is logged, and
the last one can be rolled back.

A development (JSON object):
  {"fact": "Dekker has hired a tracker who hunts the grey sleeve.",   required
   "category": "plot_local",                                          optional
   "about": ["npc:Dekker"],     optional; names in the fact are added anyway
   "holders": ["npc:Dekker"],   optional; default nobody (it happened off-screen)
   "truth": "wrong", "version_of": "f12",   optional: a cover story, a planted lie
   "consequence": {"text": "The tracker finds Fearghas",              optional
                   "triggers": [{"type": "on_location", "match": "Old Iron's Yard"}]},
   "clock": {"name": "The tracker closes in", "segments": 3,          optional
             "due_in": "3d", "consequence": "The tracker finds Fearghas"}}
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from consequence_manager import ConsequenceManager

# Default fact category: one the session brief shows under KEY FACTS.
# Provisional, like all categories (design-notes.md, "World state").
DEFAULT_CATEGORY = "plot_local"


class WorldTickError(ValueError):
    """A development is malformed; nothing from the tick was kept."""


class WorldTick:
    def __init__(self, world_state_dir: str = None):
        self.world_state_dir = world_state_dir
        self.cm = ConsequenceManager(world_state_dir)
        self.json_ops = self.cm.json_ops
        self.log_file = "world-tick-log.json"
        self.last_overflow: List[Dict[str, Any]] = []

    # ---------- validation ----------

    @staticmethod
    def _check(d: Any, i: int) -> None:
        """Refuse a malformed development before anything is written."""
        where = f"development {i + 1}"
        if not isinstance(d, dict):
            raise WorldTickError(f"{where} must be a JSON object")
        if not str(d.get("fact") or d.get("text") or "").strip():
            raise WorldTickError(f"{where} needs a \"fact\": what happened off-screen")
        con = d.get("consequence")
        if con is not None:
            if not isinstance(con, dict) or not str(con.get("text", "")).strip():
                raise WorldTickError(f"{where}: \"consequence\" needs a \"text\"")
            if not con.get("triggers"):
                raise WorldTickError(
                    f"{where}: \"consequence\" needs \"triggers\", e.g. "
                    f"[{{\"type\": \"on_location\", \"match\": \"...\"}}]. For a time "
                    f"limit, use a \"clock\" instead.")
        clock = d.get("clock")
        if clock is not None:
            if not isinstance(clock, dict) or not str(clock.get("name", "")).strip():
                raise WorldTickError(f"{where}: \"clock\" needs a \"name\"")
            try:
                if int(clock.get("segments", 0)) < 1:
                    raise ValueError
            except (TypeError, ValueError):
                raise WorldTickError(f"{where}: \"clock\" needs \"segments\" of 1 or more")

    # ---------- apply / undo ----------

    def _undo(self, facts: List[str], consequences: List[str], clocks: List[str]) -> bool:
        """Remove what a tick wrote. Returns False if a write failed."""
        from note_manager import NoteManager
        from threat_clocks import ThreatClockManager
        if facts:
            NoteManager(self.world_state_dir or "world-state").remove_facts(facts)
        if consequences:
            ids = set(consequences)
            data = self.json_ops.load_json("consequences.json") or {}
            data["active"] = [c for c in data.get("active", []) if c.get("id") not in ids]
            if not self.json_ops.save_json("consequences.json", data):
                return False
        if clocks:
            tcm = ThreatClockManager(self.world_state_dir)
            for name in clocks:
                tcm.remove_clock(name)
        return True

    def apply(self, developments: List[Dict[str, Any]], cap: int = 3,
              enabled: bool = True) -> List[Dict[str, Any]]:
        """Record every development. enabled=False = no-op (tone).

        Returns one entry per development: {"text", "fact", and "consequence" /
        "clock" when it set one up}. Raises WorldTickError and keeps nothing if
        any part is malformed or refused. `cap` is advisory: all apply, and
        anything past it is named in a warning (stderr + `last_overflow`).
        """
        from note_manager import NoteManager
        from threat_clocks import ThreatClockManager
        from time_manager import TimeError, parse_duration, parse_time

        self.last_overflow = []
        if not enabled or not developments:
            return []
        for i, d in enumerate(developments):
            self._check(d, i)

        notes = NoteManager(self.world_state_dir or "world-state")
        def as_list(value):
            return [value] if isinstance(value, str) else list(value or [])

        for i, d in enumerate(developments):
            _, _, errors = notes._about("", as_list(d.get("about")))
            if errors:
                raise WorldTickError(f"development {i + 1}: about: {'; '.join(errors)}")
            _, errors = notes._holders(as_list(d.get("holders")))
            if errors:
                raise WorldTickError(f"development {i + 1}: holders: {'; '.join(errors)}")
            _, _, _, errors = notes._check_version(
                notes.json_ops.load_json("facts.json") or {}, d.get("truth"), d.get("version_of"))
            if errors:
                raise WorldTickError(f"development {i + 1}: {' '.join(errors)}")
        written = {"facts": [], "consequences": [], "clocks": []}
        applied = []
        try:
            for i, d in enumerate(developments):
                text = str(d.get("fact") or d.get("text")).strip()
                fid = notes.add_fact(d.get("category") or DEFAULT_CATEGORY, text,
                                     list_waiting=False, about=as_list(d.get("about")),
                                     holders=as_list(d.get("holders")),
                                     truth=d.get("truth"), version_of=d.get("version_of"))
                if not fid:
                    raise WorldTickError(f"development {i + 1}: the fact could not be saved")
                written["facts"].append(fid)
                entry = {"text": text, "fact": fid}

                con = d.get("consequence")
                if con:
                    cid = self.cm.add_consequence(
                        con["text"], con.get("trigger") or "off-screen development",
                        triggers=con["triggers"])
                    if not cid:
                        raise WorldTickError(f"development {i + 1}: the consequence was "
                                             f"refused (see the error above)")
                    written["consequences"].append(cid)
                    entry["consequence"] = cid

                clock = d.get("clock")
                if clock:
                    tcm = ThreatClockManager(self.world_state_dir)
                    name = clock["name"].strip()
                    if name in tcm.get_clocks():
                        raise WorldTickError(f"development {i + 1}: a clock named "
                                             f"'{name}' already exists")
                    try:
                        tcm.add_clock(
                            name, int(clock["segments"]),
                            advance_on=clock.get("on", "time"),
                            consequence=clock.get("consequence"),
                            due_at=parse_time(clock["due"]) if clock.get("due") else None,
                            due_in_minutes=(parse_duration(clock["due_in"])
                                            if clock.get("due_in") else None))
                    except (TimeError, ValueError) as error:
                        raise WorldTickError(f"development {i + 1}: clock: {error}")
                    written["clocks"].append(name)
                    entry["clock"] = name
                applied.append(entry)
        except WorldTickError:
            self._undo(written["facts"], written["consequences"], written["clocks"])
            raise

        if len(applied) > cap:
            self.last_overflow = applied[cap:]
            names = ", ".join(a["text"] for a in self.last_overflow)
            print(f"[WORLD TICK] warning: cap {cap} exceeded; also applied: {names}",
                  file=sys.stderr)

        log = self.json_ops.load_json(self.log_file) or {"ticks": []}
        log["ticks"].append({
            "facts": written["facts"],
            "added": written["consequences"],
            "clocks": written["clocks"],
            "at": self.json_ops.get_timestamp(),
            "developments": [a["text"] for a in applied],
        })
        if not self.json_ops.save_json(self.log_file, log):
            # Without the log entry the tick could not be rolled back: undo it now.
            self._undo(written["facts"], written["consequences"], written["clocks"])
            return []
        return applied

    def waiting(self, applied: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Consequences waiting on an event that the tick's facts might fulfil
        (leaving out the ones this tick just created)."""
        own = {a.get("consequence") for a in applied}
        return [c for c in self.cm.waiting_on_event() if c["id"] not in own]

    def rollback_last(self) -> bool:
        """Undo the most recent world tick: its facts, consequences and clocks."""
        log = self.json_ops.load_json(self.log_file) or {"ticks": []}
        if not log["ticks"]:
            return False
        last = log["ticks"][-1]
        # Only pop the log entry if the removal persisted, so a failed write
        # never leaves the log and state inconsistent.
        if not self._undo(last.get("facts", []), last.get("added", []), last.get("clocks", [])):
            return False
        log["ticks"].pop()
        self.json_ops.save_json(self.log_file, log)
        return True

    def history(self) -> List[Dict[str, Any]]:
        return (self.json_ops.load_json(self.log_file) or {}).get("ticks", [])


def main():
    """CLI: the GM proposes developments (a model call in /gm); this persists them.

    apply '<json>'   json = a list of developments (see the module docstring)
    rollback         undo the most recent tick
    history          show all ticks
    """
    import argparse
    import json
    from cli_output import wants_json, strip_json_flag, emit, emit_error

    parser = argparse.ArgumentParser(description="Between-session world tick")
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("apply"); p.add_argument("developments", help="JSON list of developments")
    p.add_argument("--cap", type=int, default=3)
    sub.add_parser("rollback")
    sub.add_parser("history")

    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help(); sys.exit(1)

    wt = WorldTick()
    if args.action == "apply":
        try:
            devs = json.loads(args.developments)
        except ValueError:
            sys.exit(emit_error("developments must be a JSON list", json_mode=json_mode))
        if not isinstance(devs, list):
            sys.exit(emit_error("developments must be a JSON list", json_mode=json_mode))
        import contextlib
        import io
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out if json_mode else sys.stdout):
                applied = wt.apply(devs, cap=args.cap)
        except WorldTickError as error:
            sys.exit(emit_error(f"{str(error).rstrip('.')}. Nothing from this tick was kept.",
                                json_mode=json_mode))
        waiting = wt.waiting(applied)
        if json_mode:
            payload = {"applied": applied, "waiting_on_event": waiting}
            overflow = getattr(wt, "last_overflow", []) or []
            if overflow:
                payload["overflow"] = overflow
                payload["warning"] = (
                    f"cap {args.cap} exceeded; also applied: "
                    + ", ".join(a["text"] for a in overflow)
                )
            emit(payload, json_mode=True)
        else:
            if not applied:
                print("[WORLD TICK] nothing applied")
            for a in applied:
                extra = "".join(f", {k} {a[k]}" for k in ("consequence", "clock") if a.get(k))
                print(f"[WORLD TICK] {a['fact']}{extra}: {a['text']}")
            if waiting:
                from consequence_manager import print_waiting
                print_waiting(", ".join(a["fact"] for a in applied), waiting)
    elif args.action == "rollback":
        ok = wt.rollback_last()
        if json_mode:
            emit({"rolled_back": ok}, json_mode=True)
        else:
            print("[WORLD TICK] rolled back last tick" if ok else "[WORLD TICK] nothing to roll back")
        if not ok:
            sys.exit(1)
    else:
        out = wt.history()
        if json_mode:
            emit({"ticks": out}, json_mode=True)
        else:
            print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
