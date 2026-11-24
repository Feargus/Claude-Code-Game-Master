#!/usr/bin/env python3
"""Plots: someone's goal with progress, or the problem the story turns on.

plots.json, keyed by a short name that is the plot's id (`plot:<key>`), like a
clock's. A plot holds:

    goal          what it is after, one line: the owner's aim, or for a plot nobody
                  owns, what solving its problem means
    owner         whose goal it is (player, npc:<key>, faction:<id>); may be empty
    kind          one of schemas.PLOT_KINDS (main, antagonist, mystery, ...)
    status        open, completed or failed
    stands        where it stands now, one line, replaced by each update
    stands_at     the game time of that update
    involves      ids of the people, places and factions it involves (npc:, location:, faction:)
    follows       the plot this one replaces, if any (goals get replaced)
    outcome       what came of it, written when it ends
    game_time, created   when it began, in the game and in real time

Its history is its facts: facts, consequences, clocks and glossary entries
point at their plots (`plots`, a list of keys). People and places don't: the
plot lists who and what it involves.

Open plots are sorted most pressing first (plot_order); the brief, `list` and
the cards use the same order.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import facts as fact_file
from entity_manager import EntityManager, npcs_present
from game_time import STORED_FORMAT, stored_time
from schemas import PLOT_KIND_ORDER, PLOT_KINDS, PLOT_STATUSES

PLOTS = "plots.json"
OWNERS = ("player", "npc", "faction")              # whose goal a plot can be
INVOLVED = ("npc", "location", "faction")          # who and what it can involve
MAX_KEY_WORDS = 4
MAX_KEY_CHARS = 30


class PlotError(ValueError):
    """A plot change that can't be made. The message says how to fix it."""


def check_key(raw) -> str:
    """A new plot's short name, tidied, or PlotError."""
    key = " ".join(str(raw or "").split())
    if not key:
        raise PlotError('A plot needs a short name, e.g. "Eleventh Question".')
    if ":" in key or len(key.split()) > MAX_KEY_WORDS or len(key) > MAX_KEY_CHARS:
        raise PlotError(
            f"A plot's name is a short key, one to {MAX_KEY_WORDS} words and at most "
            f"{MAX_KEY_CHARS} characters, without a colon (\"Eleventh Question\"): facts, "
            f"clocks and consequences point at it, so it has to stay the same. What the plot "
            f"is after goes into --goal. Got '{key}'.")
    return key


def find_plot(plots: dict[str, Any], raw) -> str:
    """The key of the plot `raw` names (case ignored, with or without "plot:"), or ''."""
    wanted = " ".join(str(raw or "").split())
    if wanted.lower().startswith("plot:"):
        wanted = wanted[5:].strip()
    return next((k for k in plots if k.lower() == wanted.lower()), "") if wanted else ""


def owner_name(json_ops, owner: str) -> str:
    """How an owner is named: the character's name, an NPC's key, a faction's name."""
    import world_rules
    return world_rules.holder_name(json_ops, owner)


def plot_name(json_ops, key: str, plot: dict[str, Any], status: bool = False) -> str:
    """A plot as the lists name it: "The Sold Contract (main, Cantor Aurel Strake)",
    with its status too when asked ("…, open)")."""
    parts = [plot.get("kind", "?")]
    if plot.get("owner"):
        parts.append(owner_name(json_ops, plot["owner"]))
    if status:
        parts.append(plot.get("status", "open"))
    return f"{key} ({', '.join(parts)})"


def moved_by(json_ops, key: str) -> list[str]:
    """What will move a plot by itself: its clocks and waiting consequences, by name
    or id (an owner's goal goes nowhere without one)."""
    clocks = json_ops.load_json("threat-clocks.json") or {}
    store = json_ops.load_json("consequences.json") or {}
    found = [f"clock {n}" for n, c in clocks.items()
             if isinstance(c, dict) and key in (c.get("plots") or [])]
    found += [f"consequence {c.get('id')}" for c in store.get("active", [])
              if isinstance(c, dict) and key in (c.get("plots") or []) and not c.get("fired")]
    return found


def resolve_plots(json_ops, raws) -> tuple[list[str], list[str]]:
    """(plot keys, errors) for names given on a command line; duplicates collapse."""
    import difflib
    plots = json_ops.load_json(PLOTS) or {}
    keys, errors = [], []
    for raw in raws or []:
        key = find_plot(plots, raw)
        if not key:
            close = difflib.get_close_matches(str(raw).lower(), [k.lower() for k in plots],
                                              n=3, cutoff=0.6)
            hint = (f"; did you mean: {', '.join(k for k in plots if k.lower() in close)}?"
                    if close else f". Plots: {', '.join(plots) or 'none yet'}.")
            errors.append(f"No plot '{raw}'{hint}")
        elif key not in keys:
            keys.append(key)
    return keys, errors


def _when(stamp: str) -> datetime | None:
    try:
        return datetime.strptime(str(stamp), STORED_FORMAT) if stamp else None
    except ValueError:
        return None


def plot_order(json_ops, plots: dict[str, Any] | None = None) -> list[str]:
    """The open plots' keys, most pressing first:

    1. a consequence linked to it has fired and is not resolved (newest firing first);
    2. it involves the current place or someone in the scene;
    3. the soonest due time of a time clock linked to it; then event clocks, fullest first;
    4. the game time of its newest linked fact or update (newer first);
    5. its kind (schemas.PLOT_KINDS order).
    """
    plots = plots if plots is not None else (json_ops.load_json(PLOTS) or {})
    overview = json_ops.load_json("campaign-overview.json") or {}
    pos = overview.get("player_position") or {}
    here = pos.get("current_location", "") if isinstance(pos, dict) else ""
    npcs = json_ops.load_json("npcs.json") or {}
    scene = {f"npc:{n}" for n in npcs_present(npcs, here, overview.get("scene"))}
    scene.add(f"location:{here}")
    import sites
    scene.add(f"location:{sites.site_of(here)}")          # the site it is in

    fired: dict[str, str] = {}
    store = json_ops.load_json("consequences.json") or {}
    for c in store.get("active", []) if isinstance(store, dict) else []:
        if isinstance(c, dict) and c.get("fired"):
            for key in c.get("plots") or []:
                fired[key] = max(fired.get(key, ""), str(c["fired"].get("at", "")))

    due: dict[str, tuple] = {}
    for clock in (json_ops.load_json("threat-clocks.json") or {}).values():
        if not isinstance(clock, dict) or int(clock.get("current", 0)) >= int(clock.get("max", 1)):
            continue
        if clock.get("advance_on", "time") == "time" and clock.get("due_at"):
            rank = (0, str(clock["due_at"]), 0.0)
        else:
            rank = (1, "", -int(clock.get("current", 0)) / max(1, int(clock.get("max", 1))))
        for key in clock.get("plots") or []:
            due[key] = min(due.get(key, (2, "", 0.0)), rank)

    newest: dict[str, str] = {}
    for f in fact_file.load(json_ops):
        for key in f.get("plots") or []:
            newest[key] = max(newest.get(key, ""), str(f.get("game_time") or ""))

    def rank(key):
        p = plots[key]
        moved = max(newest.get(key, ""), str(p.get("stands_at") or ""))
        return (0 if key in fired else 1, _negate(fired.get(key, "")),
                0 if scene & set(p.get("involves") or []) else 1,
                due.get(key, (2, "", 0.0)), _negate(moved),
                PLOT_KIND_ORDER.get(p.get("kind"), len(PLOT_KIND_ORDER)))

    open_keys = [k for k, p in plots.items()
                 if isinstance(p, dict) and (p.get("status") or "open") == "open"]
    return sorted(open_keys, key=rank)


def _negate(text: str) -> tuple:
    """A sort key that puts later texts (times) first."""
    return tuple(-ord(ch) for ch in text) + (0,)


class PlotManager(EntityManager):
    """The active campaign's plots."""

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self.plots_file = PLOTS

    # ---------- helpers ----------

    def plots(self) -> dict[str, Any]:
        data = self.json_ops.load_json(self.plots_file) or {}
        return data if isinstance(data, dict) else {}

    def _save(self, plots: dict[str, Any]) -> None:
        self.json_ops.save_json(self.plots_file, plots)

    def key(self, raw) -> str:
        """The key of an existing plot, or PlotError with close matches."""
        keys, errors = resolve_plots(self.json_ops, [raw])
        if errors:
            raise PlotError(errors[0])
        return keys[0]

    def _ids(self, raws, kinds=("player", "npc", "location")) -> list[str]:
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        out, errors = [], []
        for raw in raws or []:
            cid, error = ids.resolve_as(raw, kinds)
            if error:
                errors.append(error)
            elif cid not in out:
                out.append(cid)
        if errors:
            raise PlotError(" ".join(errors))
        return out

    def _close(self, key: str) -> list[str]:
        """Existing plots whose key is close to `key` (as world_ids.close_names)."""
        import difflib
        words = set(key.lower().split())
        close = []
        for other in self.plots():
            theirs = set(other.lower().split())
            if words <= theirs or theirs <= words or \
                    difflib.SequenceMatcher(None, key.lower(), other.lower()).ratio() >= 0.8:
                close.append(other)
        return close

    # ---------- making and changing ----------

    def add(self, raw_key: str, goal: str, owner: str = "",
            kind: str = "main", involves=(), follows: str = "", stands: str = "",
            another: bool = False) -> str:
        """A new plot. Returns its key; raises PlotError."""
        key = check_key(raw_key)
        plots = self.plots()
        if find_plot(plots, key):
            raise PlotError(f"There is a plot '{find_plot(plots, key)}' already.")
        close = [] if another else self._close(key)
        if close:
            raise PlotError(f"'{key}' is close to the plot {', '.join(close)}: one plot under "
                            f"two names splits its story. If it really is another plot, add --another.")
        if kind not in PLOT_KINDS:
            raise PlotError(f"A plot's kind is one of {', '.join(PLOT_KINDS)}, not '{kind}'.")
        if not str(goal or "").strip():
            raise PlotError("Say what the plot is after, in a line: --goal \"...\" (the "
                            "owner's aim, or what solving its problem means).")
        row = {"goal": " ".join(str(goal).split()), "kind": kind,
               "status": "open", "involves": self._ids(involves, INVOLVED)}
        if owner:
            row["owner"] = self._ids([owner], OWNERS)[0]
        if follows:
            row["follows"] = self.key(follows)
        now = stored_time(self.json_ops)
        if str(stands or "").strip():
            row["stands"] = " ".join(stands.split())
            if now:
                row["stands_at"] = now
        if now:
            row["game_time"] = now
        row["created"] = self.get_timestamp()
        plots[key] = row
        self._save(plots)
        return key

    def set_stands(self, raw_key: str, stands: str) -> tuple[str, str]:
        """Where the plot stands now. Returns (key, what it said before)."""
        key = self.key(raw_key)
        if not str(stands or "").strip():
            raise PlotError("Say where the plot stands now, in a line.")
        plots = self.plots()
        if plots[key].get("status", "open") != "open":
            raise PlotError(f"'{key}' is {plots[key]['status']}; it has its outcome.")
        before = plots[key].get("stands", "")
        plots[key]["stands"] = " ".join(stands.split())
        now = stored_time(self.json_ops)
        if now:
            plots[key]["stands_at"] = now
        self._save(plots)
        return key, before

    def involve(self, raw_key: str, add=(), remove=()) -> list[str]:
        """Add people, places and factions to what a plot involves, or remove them."""
        key = self.key(raw_key)
        plots = self.plots()
        have = list(plots[key].get("involves") or [])
        gone = self._ids(remove, INVOLVED) if remove else []
        missing = [g for g in gone if g not in have]
        if missing:
            raise PlotError(f"'{key}' doesn't involve {', '.join(missing)}.")
        have = [i for i in have if i not in gone]
        have += [i for i in self._ids(add, INVOLVED) if i not in have]
        plots[key]["involves"] = have
        self._save(plots)
        return have

    def set_goal(self, raw_key: str, goal: str) -> tuple[str, str]:
        """Reword what a plot is after. Returns (key, what it said before)."""
        key = self.key(raw_key)
        if not str(goal or "").strip():
            raise PlotError("Say what the plot is after, in a line.")
        plots = self.plots()
        before = plots[key].get("goal", "")
        plots[key]["goal"] = " ".join(goal.split())
        self._save(plots)
        return key, before

    def end(self, raw_key: str, status: str, outcome: str, next_plot: str = "") -> str:
        """Complete or fail a plot with its outcome. `next_plot` names the plot that
        replaces it (made first); that one then follows it."""
        if status not in ("completed", "failed"):
            raise PlotError(f"A plot ends completed or failed, not '{status}'.")
        key = self.key(raw_key)
        if not str(outcome or "").strip():
            raise PlotError("Say what came of it: the outcome is what stays of the plot.")
        plots = self.plots()
        if plots[key].get("status", "open") != "open":
            raise PlotError(f"'{key}' is {plots[key]['status']} already.")
        follower = self.key(next_plot) if next_plot else ""
        if follower == key:
            raise PlotError("A plot can't follow itself.")
        plots[key].update(status=status, outcome=" ".join(outcome.split()))
        now = stored_time(self.json_ops)
        if now:
            plots[key]["ended_at"] = now
        if follower:
            plots[follower]["follows"] = key
        self._save(plots)
        return key

    # ---------- showing ----------

    def line(self, key: str) -> str:
        """One plot on one line: kind, key, where it stands (or what it is after)."""
        p = self.plots()[key]
        text = p.get("stands") or p.get("goal", "")
        return f"{plot_name(self.json_ops, key, p)}: {text}"

    def show(self, raw_key: str) -> str:
        """The plot in full, with its clocks, consequences and facts."""
        from note_manager import fact_line
        key = self.key(raw_key)
        p = self.plots()[key]
        lines = [f"=== {plot_name(self.json_ops, key, p, status=True)} ===",
                 f"goal: {p.get('goal', '')}"]
        if p.get("stands"):
            lines.append(f"stands: {p['stands']}")
        if p.get("involves"):
            lines.append(f"involves: {', '.join(p['involves'])}")
        if p.get("follows"):
            lines.append(f"follows: {p['follows']}")
        if p.get("outcome"):
            lines.append(f"outcome: {p['outcome']}")
        clocks = {n: c for n, c in (self.json_ops.load_json("threat-clocks.json") or {}).items()
                  if key in (c.get("plots") or [])}
        for name, c in clocks.items():
            lines.append(f"clock {name}: {c.get('current', 0)}/{c.get('max', 1)}")
        store = self.json_ops.load_json("consequences.json") or {}
        for c in store.get("active", []):
            if key in (c.get("plots") or []):
                lines.append(f"consequence {c.get('id')}: {c.get('consequence', '')}")
        facts = [f for f in fact_file.newest_first(fact_file.load(self.json_ops))
                 if key in (f.get("plots") or [])]
        if facts:
            lines.append("facts, newest first:")
            lines += [f"  {fact_line(f)}" for f in facts[:10]]
            if len(facts) > 10:
                lines.append(f"  +{len(facts) - 10} more (gm-note.sh find --plot \"{key}\")")
        return "\n".join(lines)


def _suggest_facts(key: str) -> None:
    """After gm-plot.sh add: the recorded facts that look part of the new plot."""
    from note_manager import NoteManager, fact_text
    from recall import suggest_for_plot
    result = suggest_for_plot(NoteManager(), key)
    if not result["facts"]:
        return
    for f in result["facts"]:
        print(f"[CHECK] {f['id']} may be part of it: {fact_text(f)}"
              + (f" (in {', '.join(f['plots'])})" if f.get("plots") else ""))
        print(f'  If it is: bash tools/gm-note.sh plot {f["id"]} --add "{key}"')


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Plots")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("add", help="a new plot")
    p.add_argument("key", help='its short name, e.g. "Eleventh Question"')
    p.add_argument("--goal", required=True,
                   help="what it is after, one line: the owner's aim, or what solving it means")
    p.add_argument("--owner", default="", help="whose goal it is: player, an NPC or a faction")
    p.add_argument("--kind", default="main", choices=list(PLOT_KINDS))
    p.add_argument("--involves", action="append", default=[],
                   help="a person, place or faction it involves (repeatable)")
    p.add_argument("--follows", default="", help="the plot this one replaces")
    p.add_argument("--stands", default="", help="where it stands at the start")
    p.add_argument("--another", action="store_true", help="another plot, though the name is close")
    p = sub.add_parser("stands", help="where a plot stands now")
    p.add_argument("key")
    p.add_argument("stands")
    p = sub.add_parser("involve", help="people and places a plot involves")
    p.add_argument("key")
    p.add_argument("ids", nargs="*")
    p.add_argument("--remove", action="append", default=[])
    p = sub.add_parser("goal", help="reword what a plot is after")
    p.add_argument("key")
    p.add_argument("goal")
    for action in ("complete", "fail"):
        p = sub.add_parser(action, help=f"the plot ends: {action}")
        p.add_argument("key")
        p.add_argument("outcome", help="what came of it")
        p.add_argument("--next", default="", help="the plot that replaces it (made first)")
    sub.add_parser("show", help="a plot in full").add_argument("key")
    p = sub.add_parser("list", help="plots, most pressing first")
    p.add_argument("--status", choices=list(PLOT_STATUSES), default="open")
    args = parser.parse_args()

    try:
        m = PlotManager()
        if args.action == "add":
            key = m.add(args.key, args.goal, args.owner, args.kind,
                        args.involves, args.follows, args.stands, args.another)
            print(f"[SUCCESS] Plot {key} ({args.kind})")
            if args.owner and not moved_by(m.json_ops, key):
                print(f"[NOTE] Nothing will move this plot by itself: the world moves only on "
                      f"/gm world. Give {key} a clock (bash tools/gm-clock.sh add \"<short name>\" 4 "
                      f"--text \"<what it is about>\" --due-in <when> --plot \"{key}\"), or a "
                      f"consequence with --plot \"{key}\".")
            _suggest_facts(key)
        elif args.action == "stands":
            key, _ = m.set_stands(args.key, args.stands)
            print(f"[SUCCESS] Where {key} stands is updated")
        elif args.action == "involve":
            have = m.involve(args.key, args.ids, args.remove)
            print(f"{m.key(args.key)} involves: {', '.join(have) or 'nobody yet'}")
        elif args.action == "goal":
            key, before = m.set_goal(args.key, args.goal)
            print(f"[SUCCESS] {key}'s goal reworded (was: {before})")
        elif args.action in ("complete", "fail"):
            key = m.end(args.key, "completed" if args.action == "complete" else "failed",
                        args.outcome, args.next)
            print(f"[SUCCESS] {key} {args.action}d" if args.action == "complete"
                  else f"[SUCCESS] {key} failed")
        elif args.action == "show":
            print(m.show(args.key))
        else:
            plots = m.plots()
            keys = (plot_order(m.json_ops, plots) if args.status == "open" else
                    [k for k, p in plots.items() if p.get("status") == args.status])
            for key in keys:
                print(m.line(key))
            if not keys:
                print(f"No {args.status} plots.")
    except PlotError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
