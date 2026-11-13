#!/usr/bin/env python3
"""The opening: a new campaign's first scene, set up in one go.

One JSON object, applied all-or-nothing through the same functions play uses, so
everything it makes is an ordinary record afterwards: places, NPCs, the scene
list, a plot, facts, clocks, consequences. Nothing is kept as a separate "pack"
that could go stale (it replaced upstream's play pack, 2026-11-08). Run it once,
after the character exists and the player has said where and when to start.

  {"time": "2187-10-25 19:00",                       optional: the start, as gm-time.sh set
   "place": {"name": "Lanternside", "position": "Level 40 of the Spine",
             "description": "...", "aliases": ["..."]},
   "exits": [{"name": "The Lantern noodle stall", "position": "...",
              "description": "...", "path": "visible from here",
              "aliases": ["the Lantern"]}],
   "npcs": [{"name": "Auntie Ro", "who": "...", "attitude": "friendly",
             "aliases": ["Ro"], "location": ["The Lantern noodle stall"],
             "present": true, "physique": "...", "big_five": "O0 C2 E1 A1 N-1",
             "voice": "..."}],
   "plot": {"name": "The Writ", "type": "main", "description": "...",
            "hook": "Dekker's crew walks into the market with a writ ...",
            "npcs": ["Dekker", "Seraphine Halcyon-Vey"], "locations": ["The Chrome"]},
   "developments": [...]}

- A place or NPC that already exists (an import made it) is given by its name
  alone and used as it is; a place with no description yet needs one given. A new place, exits included, needs a `description`
  (what it is like, a sentence or two: on disk before it is narrated) and a
  `position` (an exit's defaults to "next to <the place>"). A new NPC needs
  `who`, and is usually found in the place unless `location` or
  `"nowhere": true` says otherwise. NPCs are in the
  scene unless `"present": false`. Any sheet text field can be given too
  (sheet.TEXT_FIELDS: physique, style, presence, big_five, voice, tells, want,
  fears, ...). `attitude`, their attitude towards the player as one or more adjectives
  ("wary", "fond, exasperated"; leave it out if they have none), becomes a fact
  they hold.
- The plot is required: every campaign starts with at least one. Its `hook`, the
  problem that won't wait, becomes its first beat, so STORY THREADS carries it
  on from there. Its `npcs` and `locations` that have no record yet are the
  horizon: named, and not built until play walks there. An existing plot can be
  given by name ("plot": "<name>", plus "hook" next to it).
- `developments`: the premise, the secrets, the antagonist's clock and any
  consequences, in the form /gm world takes (world_tick.py): each a fact with its
  holders (none given: nobody knows it), optionally a consequence and a clock.
  Clocks link to the opening's plot unless they name another.
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager
from sheet import TEXT_FIELDS, name as sheet_name

PLAY_BEGUN = "### Session Ended:"  # what session-log.md holds once a session has ended


class OpeningError(ValueError):
    """The opening can't be set up. Nothing of it was kept."""


def _as_list(value) -> List[Any]:
    if value is None:
        return []
    return [value] if isinstance(value, (str, dict)) else list(value)


def _entry(raw) -> Dict[str, Any]:
    """A place or NPC given as a bare name or as an object."""
    return raw if isinstance(raw, dict) else {"name": raw}


class Opening:
    def __init__(self, world_state_dir: str = None):
        self.wsd = world_state_dir
        base = EntityManager(world_state_dir)
        if base.campaign_dir is None:
            raise OpeningError("No active campaign.")
        self.campaign_dir = Path(base.campaign_dir)
        self.json_ops = base.json_ops

    # ---------- checks before anything is written ----------

    @staticmethod
    def check(spec: Any) -> None:
        if not isinstance(spec, dict):
            raise OpeningError("The opening is a JSON object (see opening.py).")
        unknown = set(spec) - {"time", "place", "exits", "npcs", "plot", "hook", "developments"}
        if unknown:
            raise OpeningError(f"Unknown field(s): {', '.join(sorted(unknown))}.")
        if not str(_entry(spec.get("place") or {}).get("name") or "").strip():
            raise OpeningError('The opening needs a "place": where the first scene is.')
        for key in ("exits", "npcs"):
            for raw in _as_list(spec.get(key)):
                if not str(_entry(raw).get("name") or "").strip():
                    raise OpeningError(f'Every entry in "{key}" needs a "name".')
        plot = spec.get("plot")
        if isinstance(plot, str):
            name, hook = plot, spec.get("hook")
        elif isinstance(plot, dict):
            name, hook = plot.get("name"), plot.get("hook")
            if spec.get("hook"):
                raise OpeningError('Give the hook inside "plot" (or "plot" as a name plus "hook").')
        else:
            raise OpeningError('The opening needs a "plot": every campaign starts with at '
                               'least one, and the hook is its first beat.')
        if not str(name or "").strip():
            raise OpeningError('The plot needs a "name".')
        if not str(hook or "").strip():
            raise OpeningError('The plot needs a "hook": the problem that won\'t wait.')
        if not isinstance(spec.get("developments") or [], list):
            raise OpeningError('"developments" is a list, as /gm world takes it.')

    def refuse_if_started(self) -> None:
        overview = self.json_ops.load_json("campaign-overview.json") or {}
        if overview.get("opened"):
            raise OpeningError(f"This campaign's opening was set up already ({overview['opened']}).")
        log = self.campaign_dir / "session-log.md"
        if log.exists() and PLAY_BEGUN in log.read_text(encoding="utf-8"):
            raise OpeningError("Play has begun here (a session has ended); the opening "
                               "is for a new campaign.")
        if not sheet_name(self.json_ops.load_json("character.json") or {}):
            raise OpeningError("Create the character first (/create-character): the "
                               "opening is built for them.")

    # ---------- all or nothing ----------

    def _snapshot(self) -> Dict[str, bytes]:
        return {p.name: p.read_bytes() for p in self.campaign_dir.iterdir() if p.is_file()}

    def _restore(self, snapshot: Dict[str, bytes]) -> None:
        for p in self.campaign_dir.iterdir():
            if p.is_file() and p.name not in snapshot:
                p.unlink()
        for name, data in snapshot.items():
            (self.campaign_dir / name).write_bytes(data)

    def apply(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Set up the opening. Returns what it made (see `summary`). Raises
        OpeningError and keeps nothing if any part is malformed or refused:
        every campaign file goes back to what it was."""
        self.check(spec)
        self.refuse_if_started()
        snapshot = self._snapshot()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                result = self._apply(spec)
        except Exception as error:
            self._restore(snapshot)
            said = [ln.strip() for ln in out.getvalue().splitlines() if "[ERROR]" in ln]
            detail = f" ({'; '.join(said)})" if said else ""
            if isinstance(error, ValueError):
                raise OpeningError(f"{str(error).rstrip('.')}{detail}. Nothing of the "
                                   f"opening was kept.") from error
            raise
        result["notes"] = [ln.strip() for ln in out.getvalue().splitlines()
                           if " alias " in ln and "bash tools/" in ln]
        return result

    # ---------- the parts, in order ----------

    def _resolve(self, name: str, kind: str) -> str:
        """The key of an existing NPC or place, or ''."""
        from world_ids import WorldIds
        cid, _ = WorldIds(self.json_ops).resolve_as(name, (kind,))
        return cid.partition(":")[2]

    def _place(self, raw, near: str = None) -> Tuple[str, bool]:
        """(key, created) for a place: an existing one, or a new one made with
        gm-location.sh add's function."""
        from location_manager import LocationManager
        entry = _entry(raw)
        name = str(entry["name"]).strip()
        key = self._resolve(name, "location")
        description = str(entry.get("description") or "").strip()
        if key:
            stored = (self.json_ops.load_json("locations.json") or {}).get(key) or {}
            if not str(stored.get("description") or "").strip():
                if not description:
                    raise OpeningError(f"'{key}' has no description yet: give one, "
                                       f"{{\"name\": \"{key}\", \"description\": \"...\"}}.")
                LocationManager(self.wsd).set_description(key, description)
            return key, False
        position = entry.get("position") or (f"next to {near}" if near else "")
        if not position:
            raise OpeningError(f"The new place '{name}' needs a \"position\": where it is.")
        if not description:
            raise OpeningError(f"The new place '{name}' needs a \"description\": what it is "
                               f"like, a sentence or two.")
        locations = LocationManager(self.wsd)
        if not locations.add_location(name, position, description,
                                      aliases=_as_list(entry.get("aliases"))):
            raise OpeningError(f"The place '{name}' was refused")
        return name, True

    def _connect(self, a: str, b: str, path: str) -> None:
        from location_manager import LocationManager
        locations = self.json_ops.load_json("locations.json") or {}
        if any(c.get("to") == b for c in locations.get(a, {}).get("connections", [])):
            return
        if not LocationManager(self.wsd).connect_locations(a, b, path):
            raise OpeningError(f"Could not connect {a} and {b}")

    def _npc(self, raw, place: str) -> str:
        """The key of an NPC: an existing one, or a new one made with
        gm-npc.sh create's function."""
        from npc_manager import NPCManager
        entry = _entry(raw)
        name = str(entry["name"]).strip()
        key = self._resolve(name, "npc")
        if key:
            return key
        if not str(entry.get("who") or "").strip():
            raise OpeningError(f"The new NPC '{name}' needs \"who\": who they are.")
        nowhere = bool(entry.get("nowhere"))
        usual = _as_list(entry.get("location")) or ([] if nowhere else [place])
        fields = {flag: str(entry[key]) for flag in TEXT_FIELDS
                  for key in (flag, flag.replace("-", "_")) if entry.get(key)}
        if not NPCManager(self.wsd).create_npc(
                name, entry["who"], entry.get("attitude"), locations=usual,
                nowhere=nowhere, aliases=_as_list(entry.get("aliases")), fields=fields):
            raise OpeningError(f"The NPC '{name}' was refused")
        return name

    def _plot(self, spec: Dict[str, Any]) -> Tuple[str, str]:
        """(plot key, hook): the opening's plot, made or found, with the hook as
        its first beat."""
        from plot_manager import PlotManager
        plots = PlotManager(self.wsd)
        plot = spec["plot"]
        if isinstance(plot, str):
            key, hook = plots._find_entity_name(plots.plots_file, plot), spec["hook"]
            if not key:
                raise OpeningError(f"No plot '{plot}'")
        else:
            key, hook = str(plot["name"]).strip(), plot["hook"]
            if not plots.add_plot(key, plot.get("type") or "main", plot.get("description") or "",
                                  status="active", objectives=_as_list(plot.get("objectives")),
                                  npcs=_as_list(plot.get("npcs")),
                                  locations=_as_list(plot.get("locations")),
                                  first_event=str(hook).strip()):
                raise OpeningError(f"The plot '{key}' was refused")
            return key, str(hook).strip()
        plots.update_plot(key, str(hook).strip())
        return key, str(hook).strip()

    def horizon(self, plot_key: str) -> List[str]:
        """The plot's people and places that have no record yet."""
        plot = (self.json_ops.load_json("plots.json") or {}).get(plot_key) or {}
        return ([n for n in plot.get("npcs") or [] if not self._resolve(n, "npc")]
                + [n for n in plot.get("locations") or [] if not self._resolve(n, "location")])

    def _apply(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        from scene_manager import SceneManager
        from session_manager import SessionManager
        from time_manager import TimeManager, describe, parse_time
        from world_tick import WorldTick

        if spec.get("time"):
            TimeManager(self.wsd).set_time(parse_time(spec["time"]))

        place, _ = self._place(spec["place"])
        exits = []
        for raw in _as_list(spec.get("exits")):
            key, _ = self._place(raw, near=place)
            self._connect(place, key, _entry(raw).get("path") or "visible from here")
            exits.append(key)
        SessionManager(self.wsd).move_party(place)

        present = []
        for raw in _as_list(spec.get("npcs")):
            key = self._npc(raw, place)
            if _entry(raw).get("present", True) and key not in present:
                present.append(key)
        if present:
            SceneManager(self.wsd).enter(present)

        plot, hook = self._plot(spec)
        developments = [dict(d) for d in spec.get("developments") or [] if isinstance(d, dict)]
        if len(developments) != len(spec.get("developments") or []):
            raise OpeningError("Every development is a JSON object")
        for d in developments:
            if isinstance(d.get("clock"), dict):
                d["clock"] = {"linked_plot": plot, **d["clock"]}
        try:
            applied, written = WorldTick(self.wsd).record(developments)
        except ValueError as error:
            raise OpeningError(str(error)) from error

        overview = self.json_ops.load_json("campaign-overview.json") or {}
        overview["opened"] = overview.get("game_time") or self.json_ops.get_timestamp()
        self.json_ops.save_json("campaign-overview.json", overview)

        now = TimeManager(self.wsd).get_game_time()
        return {"time": describe(now) if now else "", "place": place, "exits": exits,
                "present": present, "plot": plot, "hook": hook,
                "horizon": self.horizon(plot), "facts": written["facts"],
                "clocks": written["clocks"], "consequences": written["consequences"]}


def summary(result: Dict[str, Any]) -> str:
    lines = ["[SUCCESS] The opening is set up. Narrate the first scene from this:"]
    if result["time"]:
        lines.append(f"  Time: {result['time']}")
    lines.append(f"  Place: {result['place']}"
                 + (f"; exits: {', '.join(result['exits'])}" if result["exits"] else ""))
    lines.append(f"  Here: {', '.join(result['present']) or 'nobody but the character'}")
    lines.append(f"  Plot: {result['plot']}")
    lines.append(f"  Hook: {result['hook']}")
    if result["horizon"]:
        lines.append(f"  On the horizon (named, not built until play walks there): "
                     f"{', '.join(result['horizon'])}")
    made = [f"facts {', '.join(result['facts'])}" if result["facts"] else "",
            f"clocks: {', '.join(result['clocks'])}" if result["clocks"] else "",
            f"consequences {', '.join(result['consequences'])}" if result["consequences"] else ""]
    if any(made):
        lines.append(f"  Recorded: {'; '.join(m for m in made if m)}")
    lines += result.get("notes") or []
    return "\n".join(lines)


def main() -> int:
    """opening.py '<json>' (see the module docstring). --json for structured output."""
    from cli_output import emit, emit_error, strip_json_flag, wants_json
    json_mode = wants_json()
    args = strip_json_flag(sys.argv[1:])
    if len(args) != 1:
        print("Usage: gm-session.sh opening '<json>'   (the fields: lib/opening.py)",
              file=sys.stderr)
        return 1
    try:
        spec = json.loads(args[0])
    except ValueError as error:
        return emit_error(f"The opening isn't valid JSON: {error}", json_mode=json_mode)
    try:
        result = Opening().apply(spec)
    except OpeningError as error:
        return emit_error(str(error), json_mode=json_mode)
    if json_mode:
        emit(result, json_mode=True)
    else:
        print(summary(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
