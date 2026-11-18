#!/usr/bin/env python3
"""Factions: a group of people with a shared goal, impulses and values
(design-notes.md → "Factions"; ideas-for-systems.md §5).

factions.json, keyed by a short id ("lull"), which is how the rest of the world
names the faction: `faction:lull` holds facts and world-rule values, is what a
fact is about, and learns things (on_learn). The record only describes the faction:

    "lull": {"name": "Lull Corporation", "aliases": ["Lull"], "kind": "megacorp",
             "description": "…", "impulses": ["…"], "values": ["…"],
             "leader": "npc:…", "successor": "npc:…",
             "assets": [{"name": "The Mesh", "note": "…"}], "tags": ["corp"]}

Everything else lives where it already has a home: its goal is a plot it owns, its
secrets are facts it holds, the world's own numbers for it (Patience, Alert) are
world rules held by factions.

Campaigns made before factions.json list their factions in the world bible's
factions graph. Where there is no factions.json, world rules still find them there
(`known`); the first `create` copies them in, so the values held by them carry over.
"""

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

FILE = "factions.json"
BIBLE = "world-bible.json"
TEXT_FIELDS = ("name", "kind", "description")
PEOPLE_FIELDS = ("leader", "successor")
LIST_FIELDS = ("impulses", "values", "tags")
FIELDS = TEXT_FIELDS + PEOPLE_FIELDS + LIST_FIELDS
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class FactionError(ValueError):
    """A faction change that can't be made. The message says how to fix it."""


# ---------- reading ----------

def has_file(json_ops) -> bool:
    return (Path(json_ops.world_state_dir) / FILE).exists()


def load(json_ops) -> dict[str, dict[str, Any]]:
    """The factions of factions.json ({} if there is none)."""
    data = json_ops.load_json(FILE) or {}
    if not isinstance(data, dict):
        raise FactionError(f"{FILE} must be an object of factions by id.")
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def from_bible(json_ops) -> dict[str, dict[str, Any]]:
    """The world bible's faction nodes, as records (an older campaign's factions)."""
    graph = (json_ops.load_json(BIBLE) or {}).get("factions") or {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    out = {}
    for node in nodes or []:
        if isinstance(node, dict) and str(node.get("id") or "").strip():
            fid = str(node["id"]).strip()
            out[fid] = {"name": str(node.get("name") or fid).strip()}
            if str(node.get("description") or "").strip():
                out[fid]["description"] = str(node["description"]).strip()
    return out


def known(json_ops) -> dict[str, dict[str, Any]]:
    """The campaign's factions: factions.json, or for an older campaign without it,
    the world bible's."""
    return load(json_ops) if has_file(json_ops) else from_bible(json_ops)


def make_id(name: str) -> str:
    """'lull-corporation' for "Lull Corporation", 'combine' for "The Combine"."""
    words = re.sub(r"[^a-z0-9]+", " ", str(name).lower()).split()
    if len(words) > 1 and words[0] == "the":
        words = words[1:]
    return "-".join(words)


def resolver_table(json_ops) -> dict[str, dict[str, Any]]:
    """{id: {"aliases": [name, *aliases]}}: the factions as the id resolver matches
    them, by id, name or alias (world_ids.py)."""
    return {fid: {"aliases": [f.get("name", fid), *(f.get("aliases") or [])]}
            for fid, f in load(json_ops).items()}


# ---------- the manager ----------

class FactionManager:
    """Create and change the factions of one campaign (a JsonOperations on its folder)."""

    def __init__(self, json_ops):
        self.json_ops = json_ops
        self.notes: list[str] = []

    def _ids(self):
        from world_ids import WorldIds
        return WorldIds(self.json_ops)

    def _save(self, table: dict[str, Any]) -> None:
        self.json_ops.save_json(FILE, table)

    def key(self, raw) -> str:
        """The id of the faction `raw` names (id, name or alias), or FactionError. In an
        older campaign without factions.json, a faction of the world bible's."""
        text = " ".join(str(raw or "").split())
        if not has_file(self.json_ops):
            bare = text.partition(":")[2] if text.lower().startswith("faction:") else text
            found = [fid for fid, f in from_bible(self.json_ops).items()
                     if bare.lower() in (fid.lower(), f["name"].lower())]
            if found:
                return found[0]
            raise FactionError(f"No faction '{bare}' (bash tools/gm-faction.sh list).")
        cid, error = self._ids().resolve_as(text if text.lower().startswith("faction:")
                                            else f"faction:{text}", ("faction",))
        if error:
            raise FactionError(f"{error.rstrip('.')} (bash tools/gm-faction.sh list).")
        return cid.partition(":")[2]

    def _person(self, raw) -> str:
        if not str(raw or "").strip():
            return ""
        cid, error = self._ids().resolve_as(raw, ("npc",))
        if error:
            raise FactionError(f"{error} A faction's leader or successor is a known NPC "
                               f"(gm-npc.sh create).")
        return cid

    def _check_name(self, name: str, fid: str, another: bool) -> None:
        """A name no other faction, person or place has, and not close to another
        faction's unless `another`."""
        from world_ids import close_name_refusal
        ids = self._ids()
        problem = ids.check_alias(name, f"faction:{fid}")
        if problem and "already names" in problem:
            raise FactionError(problem)
        close = [c for c in ids.close_names(name, "faction") if c != f"faction:{fid}"]
        refusal = "" if another else close_name_refusal(close, "faction", name)
        if refusal:
            raise FactionError(refusal)

    def _seed(self) -> dict[str, Any]:
        """factions.json as it is, or started from the world bible's factions."""
        if has_file(self.json_ops):
            return load(self.json_ops)
        table = from_bible(self.json_ops)
        if table:
            self._save(table)
            listed = ", ".join(f"{k} ({v['name']})" for k, v in table.items())
            self.notes.append(f"{FILE} started from the world bible's factions: {listed}.")
        return table

    def create(self, name: str, description: str, fid: str = "", kind: str = "",
               impulses=(), values=(), aliases=(), tags=(), leader: str = "",
               successor: str = "", another: bool = False) -> str:
        """A new faction; returns its id. `description` is required: what it is, a
        sentence or two (on disk before it is narrated, like a place)."""
        name = " ".join(str(name or "").split())
        description = " ".join(str(description or "").split())
        if not name:
            raise FactionError("A faction needs a name.")
        if not description:
            raise FactionError(f"{name} needs a description: what it is, in a sentence or two.")
        fid = (fid or make_id(name)).strip().lower()
        if not ID_RE.match(fid):
            raise FactionError(f"A faction's id is short, lowercase letters, digits and "
                               f"dashes (\"lull\", \"red-hand\"); got '{fid}'. Give one with --id.")
        table = self._seed()
        if fid in table:
            raise FactionError(f"There is a faction '{fid}' already ({table[fid].get('name')}). "
                               f"Give another id with --id.")
        self._check_name(name, fid, another)
        row = {"name": name}
        if aliases := self._checked_aliases(name, fid, aliases):
            row["aliases"] = aliases
        if kind.strip():
            row["kind"] = " ".join(kind.split())
        row["description"] = description
        row.update({field: items for field, given in (("impulses", impulses), ("values", values))
                    if (items := _lines(given))})
        row.update({field: who for field, raw in (("leader", leader), ("successor", successor))
                    if (who := self._person(raw))})
        if tags := _tags(tags):
            row["tags"] = tags
        table[fid] = row
        self._save(table)
        return fid

    def _checked_aliases(self, name: str, fid: str, aliases) -> list[str]:
        from entity_aliases import normalize_entity_name
        aliases = list(dict.fromkeys(a.strip() for a in aliases if a.strip()))
        same = [a for a in aliases if normalize_entity_name(a) == normalize_entity_name(name)]
        if same:
            raise FactionError(f"'{same[0]}' needs no alias: it is {name}'s own name (case, "
                               f"punctuation and a leading 'the' are ignored).")
        problems = [p for a in aliases if (p := self._ids().check_alias(a, f"faction:{fid}"))]
        if problems:
            raise FactionError(" ".join(problems))
        return aliases

    def set_field(self, raw, field: str, given: list[str]) -> tuple[str, Any]:
        """Replace one field (a list field: all of it; nothing given clears it).
        Returns (id, the value before)."""
        if field not in FIELDS:
            raise FactionError(f"A faction's fields are {', '.join(FIELDS)} (aliases: "
                               f"gm-faction.sh alias; assets: gm-faction.sh asset); "
                               f"not '{field}'.")
        self._seed()
        fid = self.key(raw)
        table = load(self.json_ops)
        row = table[fid]
        before = row.get(field)
        if field in LIST_FIELDS:
            value = _tags(given) if field == "tags" else _lines(given)
        else:
            if len(given) > 1:
                raise FactionError(f"{field} is one value; put it in quotes.")
            value = " ".join(given[0].split()) if given else ""
            if field in ("name", "description") and not value:
                raise FactionError(f"A faction's {field} can't be empty.")
            if field == "name":
                self._check_name(value, fid, another=True)
            if field in PEOPLE_FIELDS:
                value = self._person(value)
        if value:
            row[field] = value
        else:
            row.pop(field, None)
        self._save(table)
        return fid, before

    def asset(self, raw, name: str, note: str = "", remove: bool = False) -> tuple[str, list]:
        """Add a named asset (or replace its note), or remove it. Returns (id, assets)."""
        self._seed()
        fid = self.key(raw)
        table = load(self.json_ops)
        row = table[fid]
        name = " ".join(str(name or "").split())
        assets = [a for a in row.get("assets") or [] if isinstance(a, dict)]
        mine = [a for a in assets if str(a.get("name", "")).lower() == name.lower()]
        if remove:
            if not mine:
                raise FactionError(f"{row['name']} has no asset '{name}' (it has: "
                                   f"{', '.join(a['name'] for a in assets) or 'none'}).")
            assets = [a for a in assets if a not in mine]
        else:
            note = " ".join(str(note or "").split())
            if not name or not note:
                raise FactionError("An asset needs a name and a note: what it is, one sentence.")
            if mine:
                mine[0]["note"] = note
            else:
                assets.append({"name": name, "note": note})
        if assets:
            row["assets"] = assets
        else:
            row.pop("assets", None)
        self._save(table)
        return fid, assets

    # ---------- showing ----------

    def line(self, fid: str, row: dict[str, Any]) -> str:
        kind = f", {row['kind']}" if row.get("kind") else ""
        return f"faction:{fid} — {row.get('name', fid)}{kind}: {row.get('description', '')}".rstrip(": ")

    def show(self, raw) -> str:
        """The faction in full, its world-rule values, and the facts it knows (by id)."""
        fid = self.key(raw)
        row = known(self.json_ops)[fid]
        return "\n".join([f"{row['name']} (faction:{fid})", *_record_lines(row),
                          *self._world_lines(f"faction:{fid}")])

    def _world_lines(self, cid: str) -> list[str]:
        import facts as fact_file
        import world_rules
        lines = []
        if rules := world_rules.holder_lines(self.json_ops, cid):
            lines += ["  World rules:", *(f"    {r}" for r in rules)]
        facts = fact_file.load(self.json_ops)
        held = [f["id"] for f in facts if cid in (f.get("holders") or [])]
        about = [f["id"] for f in facts if cid in (f.get("about") or [])]
        lines.append(f"  Knows: {', '.join(held)} (gm-note.sh find --held-by {cid})" if held
                     else "  Knows: nothing recorded")
        if about:
            lines.append(f"  Facts about it: {', '.join(about)} (gm-note.sh find --about {cid})")
        return lines

    def list_lines(self) -> list[str]:
        lines = [self.line(fid, row) for fid, row in known(self.json_ops).items()]
        if lines and not has_file(self.json_ops):
            lines.append("(From the world bible: the first gm-faction.sh create, set, alias or "
                         "asset copies them into factions.json.)")
        return lines


def _record_lines(row: dict[str, Any]) -> list[str]:
    lines = [f"  Also called: {', '.join(row['aliases'])}"] if row.get("aliases") else []
    lines += [f"  {field.capitalize()}: {row[field]}" for field in ("kind", "description")
              if row.get(field)]
    for field in ("impulses", "values"):
        if row.get(field):
            lines += [f"  {field.capitalize()}:", *(f"    - {item}" for item in row[field])]
    lines += [f"  {field.capitalize()}: {row[field].partition(':')[2]}" for field in PEOPLE_FIELDS
              if row.get(field)]
    lines += [f"  Asset: {a['name']}: {a['note']}" for a in row.get("assets") or []]
    if row.get("tags"):
        lines.append(f"  Tags: {', '.join(row['tags'])}")
    return lines


def _lines(given) -> list[str]:
    return [" ".join(str(i).split()) for i in given if str(i).strip()]


def _tags(given) -> list[str]:
    return list(dict.fromkeys(" ".join(str(t).lower().split()) for t in given if str(t).strip()))


# ---------- the command line ----------

def main() -> int:
    import argparse

    from campaign_manager import CampaignManager
    from json_ops import JsonOperations
    from world_ids import change_aliases

    parser = argparse.ArgumentParser(description="Factions")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("create", help="a new faction")
    p.add_argument("name")
    p.add_argument("--description", required=True, help="what it is, a sentence or two")
    p.add_argument("--id", default="", help='its short id ("lull"); default: from the name')
    p.add_argument("--kind", default="", help="gang, syndicate, megacorp, …")
    p.add_argument("--impulse", action="append", default=[], help="what drives it (repeatable)")
    p.add_argument("--value", action="append", default=[],
                   help="what it stands for, or never does (repeatable)")
    p.add_argument("--alias", action="append", default=[], help="a shorter name (repeatable)")
    p.add_argument("--tag", action="append", default=[], help="corp, gang, police… (repeatable)")
    p.add_argument("--leader", default="")
    p.add_argument("--successor", default="")
    p.add_argument("--another", action="store_true", help="another faction, though the name is close")
    p = sub.add_parser("set", help="replace one field")
    p.add_argument("faction")
    p.add_argument("field")
    p.add_argument("values", nargs="*")
    p = sub.add_parser("alias", help="add or remove shorter names")
    p.add_argument("faction")
    p.add_argument("aliases", nargs="*")
    p.add_argument("--remove", action="append", default=[])
    p = sub.add_parser("asset", help="a named asset: add, change its note, or remove")
    p.add_argument("faction")
    p.add_argument("name")
    p.add_argument("note", nargs="?", default="")
    p.add_argument("--remove", action="store_true")
    sub.add_parser("show", help="a faction in full").add_argument("faction")
    sub.add_parser("list", help="every faction, one line each")
    args = parser.parse_args()

    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        print("[ERROR] No active campaign.", file=sys.stderr)
        return 1
    m = FactionManager(JsonOperations(str(campaign)))
    try:
        if args.action == "create":
            fid = m.create(args.name, args.description, args.id, args.kind, args.impulse,
                           args.value, args.alias, args.tag, args.leader, args.successor,
                           args.another)
            print(f"[SUCCESS] Faction faction:{fid} ({args.name})")
        elif args.action == "set":
            fid, before = m.set_field(args.faction, args.field, args.values)
            was = "; ".join(before) if isinstance(before, list) else before
            print(f"[SUCCESS] faction:{fid} {args.field} set" + (f" (was: {was})" if was else ""))
        elif args.action == "alias":
            if not args.aliases and not args.remove:
                raise FactionError("Give the aliases to add, or --remove <alias>.")
            m._seed()
            key, aliases = change_aliases(m.json_ops, "faction", args.faction,
                                          args.aliases, args.remove)
            print(f"faction:{key} is also called: {', '.join(aliases) or 'nothing else'}")
        elif args.action == "asset":
            fid, assets = m.asset(args.faction, args.name, args.note, args.remove)
            print(f"faction:{fid} assets: {', '.join(a['name'] for a in assets) or 'none'}")
        elif args.action == "show":
            print(m.show(args.faction))
        else:
            lines = m.list_lines()
            print("\n".join(lines) if lines else
                  "No factions yet (bash tools/gm-faction.sh create \"<name>\" --description \"…\").")
    except (FactionError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    finally:
        for note in m.notes:                       # the bible's factions copied in
            print(f"[NOTE] {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
