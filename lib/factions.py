#!/usr/bin/env python3
"""Factions: a group of people with a shared goal, impulses and values
(design-notes.md → "Factions"; ideas-for-systems.md §5).

factions.json, keyed by a short id ("lull"), which is how the rest of the world
names the faction: `faction:lull` holds facts and world-rule values, is what a
fact is about, and learns things (on_learn). The record only describes the faction:

    "lull": {"name": "Lull Corporation", "aliases": ["Lull"], "kind": "megacorp",
             "description": "…", "impulses": ["…"], "values": ["…"],
             "leader": "npc:…", "successor": "npc:…",
             "assets": [{"name": "The Mesh", "note": "…"}], "tags": ["corp"],
             "ties": {"psm": "pays the building's bills; one creature, two logos"}}

`ties`: how this faction sees each other one it has history with, a line of text;
the Relation (faction_rules.py) is the number, the tie says why.

Everything else lives where it already has a home: its goal is a plot it owns, its
secrets are facts it holds, the world's own numbers for it (Patience, Alert) are
world rules held by factions.

Membership is on the NPC's sheet: `identity.factions`, [{"id": "lull"}, {"id":
"coven", "secret": true}]. What a faction knows, every member knows: an NPC knows a
fact they hold, or one held by a faction they belong to (`knows`). Joining is
learning (the member's on_learn consequences fire), leaving loses the faction's
knowledge. A secret membership is known only to the faction's members: the GM sees
it marked; anyone else finding out is a fact ("Jax is in the Coven").

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


# ---------- members ----------

def memberships(sheet) -> list[dict[str, Any]]:
    """A sheet's memberships: [{"id": ..., "secret": True}] ("secret" only when true)."""
    found = ((sheet or {}).get("identity") or {}).get("factions") or []
    return [m for m in found if isinstance(m, dict) and m.get("id")]


def knowers(holder: str, npcs: dict[str, Any]) -> set[str]:
    """The holders whose knowledge `holder` draws on: themselves, and for an NPC each
    faction they belong to (what a faction knows, every member knows)."""
    out = {holder}
    kind, _, key = holder.partition(":")
    if kind == "npc":
        out |= {f"faction:{m['id']}" for m in memberships(npcs.get(key))}
    return out


def knows(holder: str, holders, npcs: dict[str, Any]) -> bool:
    """Whether `holder` knows a fact held by `holders` (`public`: everyone)."""
    return isinstance(holders, list) and ("public" in holders
                                          or bool(knowers(holder, npcs) & set(holders)))


def members(npcs: dict[str, Any], fid: str, living: bool = True) -> list[tuple[str, bool]]:
    """(NPC key, secret) of a faction's members; the dead too unless `living`."""
    from entity_manager import is_dead
    return [(key, bool(m.get("secret"))) for key, npc in npcs.items()
            if isinstance(npc, dict) and (not living or not is_dead(npc))
            for m in memberships(npc) if m["id"] == fid]


# ---------- presence ----------

PRESENCE = (0, 5)     # 0 not there (an enemy's headquarters), 1 a few, 3 a strong hand, 5 they run it
EYES = 4              # from here, a fact recorded at the place gets the hint "they have eyes here"


def presence(json_ops, place: str) -> dict[str, int]:
    """{faction id: 0–5} at a place (its key); a faction not listed: never written."""
    loc = (json_ops.load_json("locations.json") or {}).get(place) or {}
    found = loc.get("presence") if isinstance(loc, dict) else None
    return dict(found) if isinstance(found, dict) else {}


def eyes(json_ops, place_id: str) -> list[tuple[str, int]]:
    """(faction id, presence) of the factions with eyes at `location:<key>`, most first."""
    here = presence(json_ops, place_id.partition(":")[2])
    return sorted(((f, n) for f, n in here.items() if n >= EYES), key=lambda x: -x[1])


def presence_of(json_ops, fid: str) -> list[tuple[str, int]]:
    """(place key, presence) of one faction, most first."""
    places = json_ops.load_json("locations.json") or {}
    found = [(k, (v.get("presence") or {}).get(fid)) for k, v in places.items() if isinstance(v, dict)]
    return sorted(((k, n) for k, n in found if n is not None), key=lambda x: -x[1])


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
        fid = _check_id((fid or make_id(name)).strip().lower())
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
        self._into_bag(fid)
        for field in PEOPLE_FIELDS:
            if row.get(field):
                self._ensure_member(fid, row[field], field)
        return fid

    def _into_bag(self, fid: str) -> None:
        """A new faction gets its full share of the faction bag at once, as if it had
        been there from the start (decided 2026-11-19): 3 tokens of its own, 1 job token
        and 2 blanks. A bag never drawn yet holds them already (its start is built from
        the factions)."""
        import faction_rules
        import rule_bag
        import world_rules
        if faction_rules.BAG not in (world_rules.load_state(self.json_ops).get("world") or {}):
            return
        for kind, n in ((fid, faction_rules.OWN_TOKENS),
                        (faction_rules.job_kind(fid), faction_rules.JOB_TOKENS),
                        (faction_rules.BLANK, faction_rules.BLANKS)):
            rule_bag.put(self.json_ops, faction_rules.BAG, "world", kind, n, cause="a new faction")
        self.notes.append(f"{faction_rules.BAG}: {fid} gets its share of the bag, "
                          f"{faction_rules.OWN_TOKENS} tokens, a job token and "
                          f"{faction_rules.BLANKS} blanks.")

    def _checked_aliases(self, name: str, fid: str, aliases) -> list[str]:
        aliases = list(dict.fromkeys(a.strip() for a in aliases if a.strip()))
        from world_ids import WorldIds
        aliases, dropped = WorldIds.drop_own_names(aliases, name)
        self.notes += dropped
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
        if field in PEOPLE_FIELDS and value:
            self._ensure_member(fid, value, field)
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

    def tie(self, raw, raw_other, text: str = "") -> tuple[str, str, str]:
        """How faction `raw` sees `raw_other`, one line; an empty text removes it.
        Returns (id, other id, the text before)."""
        self._seed()
        fid, other = self.key(raw), self.key(raw_other)
        if fid == other:
            raise FactionError("A tie is between two factions.")
        table = load(self.json_ops)
        ties = dict(table[fid].get("ties") or {})
        before = ties.pop(other, "")
        text = " ".join(str(text or "").split())
        if text:
            ties[other] = text
        elif not before:
            raise FactionError(f"{fid} has no tie to {other} to remove; give the text.")
        if ties:
            table[fid]["ties"] = ties
        else:
            table[fid].pop("ties", None)
        self._save(table)
        return fid, other, before

    # ---------- membership ----------

    def _npc(self, raw) -> tuple[str, str]:
        cid, error = self._ids().resolve_as(raw, ("npc",))
        if error:
            raise FactionError(f"{error.rstrip('.')}. Only NPCs belong to factions for now; the "
                               f"character's memberships come with what the character knows.")
        return cid, cid.partition(":")[2]

    def _ensure_member(self, fid: str, cid: str, why: str) -> None:
        npcs = self.json_ops.load_json("npcs.json") or {}
        key = cid.partition(":")[2]
        if not any(m["id"] == fid for m in memberships(npcs.get(key))):
            self.join(fid, cid)
            self.notes.append(f"{key} is its {why}, so a member now.")

    def join(self, raw_faction, raw_npc, secret: bool | None = None) -> dict[str, Any]:
        """An NPC joins a faction, and learns what it knows: their on_learn consequences
        fire for each fact. `secret`: only the faction's members know. For a member
        already, `secret` True or False changes only the flag. Returns {"faction",
        "npc", "learned": fact ids, "fired": consequences, "changed": flag only}."""
        from entity_manager import is_dead
        self._seed()
        fid = self.key(raw_faction)
        cid, key = self._npc(raw_npc)
        npcs = self.json_ops.load_json("npcs.json") or {}
        npc = npcs[key]
        name = load(self.json_ops)[fid]["name"]
        had = next((m for m in memberships(npc) if m["id"] == fid), None)
        if had:
            if secret is None or bool(had.get("secret")) == secret:
                raise FactionError(f"{key} is a member of {name} already"
                                   + (" (secret)." if had.get("secret") else ".")
                                   + " --secret or --open changes who knows it.")
            if secret:
                had["secret"] = True
            else:
                had.pop("secret", None)
            self.json_ops.save_json("npcs.json", npcs)
            return {"faction": fid, "npc": key, "learned": [], "fired": [], "changed": True}
        if is_dead(npc):
            raise FactionError(f"{key} is dead and joins nothing.")
        import facts as fact_file
        facts = fact_file.load(self.json_ops)
        knew = {f["id"] for f in facts if knows(cid, f.get("holders"), npcs)}
        identity = npc.setdefault("identity", {})
        identity["factions"] = memberships(npc) + [{"id": fid, **({"secret": True} if secret else {})}]
        self.json_ops.save_json("npcs.json", npcs)
        learned = [f for f in facts if f["id"] not in knew and knows(cid, f.get("holders"), npcs)]
        return {"faction": fid, "npc": key, "learned": [f["id"] for f in learned],
                "fired": self._learn(cid, learned), "changed": False}

    def _learn(self, cid: str, learned: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fire `cid`'s on_learn consequences for facts they just learned, oldest first."""
        if not learned:
            return []
        from note_manager import NoteManager
        from rule_effects import _base
        base = _base(self.json_ops)
        if base is None:
            self.notes.append("Not the active campaign: on_learn consequences weren't checked.")
            return []
        notes, fired = NoteManager(base), []
        for f in learned:
            fired += notes._learned(f["id"], f, [cid])
        return fired

    def leave(self, raw_faction, raw_npc) -> dict[str, Any]:
        """An NPC leaves a faction and no longer knows what only it knew. Returns
        {"faction", "npc", "lost": fact ids}."""
        import facts as fact_file
        self._seed()
        fid = self.key(raw_faction)
        cid, key = self._npc(raw_npc)
        npcs = self.json_ops.load_json("npcs.json") or {}
        mine = memberships(npcs[key])
        if not any(m["id"] == fid for m in mine):
            raise FactionError(f"{key} is no member of {load(self.json_ops)[fid]['name']}.")
        facts = fact_file.load(self.json_ops)
        knew = [f["id"] for f in facts if knows(cid, f.get("holders"), npcs)]
        npcs[key]["identity"]["factions"] = [m for m in mine if m["id"] != fid]
        if not npcs[key]["identity"]["factions"]:
            del npcs[key]["identity"]["factions"]
        self.json_ops.save_json("npcs.json", npcs)
        by_id = {f["id"]: f for f in facts}
        lost = [i for i in knew if not knows(cid, by_id[i].get("holders"), npcs)]
        return {"faction": fid, "npc": key, "lost": lost}

    def set_presence(self, raw_place, given: list[str], remove=()) -> tuple[str, dict[str, int]]:
        """Presence at a place: "<faction>=N" each (0–5), `remove` forgets one. Returns
        (place key, presence)."""
        self._seed()
        cid, error = self._ids().resolve_as(raw_place, ("location",))
        if error:
            raise FactionError(error)
        place = cid.partition(":")[2]
        here = presence(self.json_ops, place)
        for raw in given:
            name, sep, number = str(raw).rpartition("=")
            if not sep or not number.strip().lstrip("-").isdigit():
                raise FactionError(f"Presence is <faction>=N, N from {PRESENCE[0]} to "
                                   f"{PRESENCE[1]} (\"kin=4\"); got '{raw}'.")
            n = int(number)
            if not PRESENCE[0] <= n <= PRESENCE[1]:
                raise FactionError(f"Presence goes from {PRESENCE[0]} (not there) to "
                                   f"{PRESENCE[1]} (they run it), not {n}.")
            here[self.key(name)] = n
        for raw in remove:
            fid = self.key(raw)
            if fid not in here:
                raise FactionError(f"{place} has no presence of faction:{fid} written.")
            del here[fid]
        places = self.json_ops.load_json("locations.json") or {}
        if here:
            places[place]["presence"] = dict(sorted(here.items(), key=lambda x: -x[1]))
        else:
            places[place].pop("presence", None)
        self.json_ops.save_json("locations.json", places)
        return place, presence(self.json_ops, place)

    # ---------- showing ----------

    def line(self, fid: str, row: dict[str, Any]) -> str:
        kind = f", {row['kind']}" if row.get("kind") else ""
        return f"faction:{fid} — {row.get('name', fid)}{kind}: {row.get('description', '')}".rstrip(": ")

    def show(self, raw) -> str:
        """The faction in full, its world-rule values, and the facts it knows (by id)."""
        fid = self.key(raw)
        row = known(self.json_ops)[fid]
        return "\n".join([f"{row['name']} (faction:{fid})", *_record_lines(row, self.json_ops),
                          *self._member_lines(fid), *self._presence_lines(fid),
                          *self._plot_lines(f"faction:{fid}"), *self._job_lines(fid),
                          *self._world_lines(f"faction:{fid}")])

    def _job_lines(self, fid: str) -> list[str]:
        from faction_jobs import job_lines
        return job_lines(self.json_ops, fid)

    def _presence_lines(self, fid: str) -> list[str]:
        found = presence_of(self.json_ops, fid)
        return [f"  Presence: {', '.join(f'{k} {n}' for k, n in found)}"] if found else []

    def _plot_lines(self, cid: str) -> list[str]:
        plots = self.json_ops.load_json("plots.json") or {}
        lines = [f"  Wants: {p.get('goal') or '(no goal written)'} (plot {k}, {p.get('status', 'open')})"
                 for k, p in plots.items() if isinstance(p, dict) and p.get("owner") == cid]
        involved = [k for k, p in plots.items() if isinstance(p, dict) and p.get("owner") != cid
                    and cid in (p.get("involves") or [])]
        if involved:
            lines.append(f"  In plots: {', '.join(involved)}")
        return lines

    def _member_lines(self, fid: str) -> list[str]:
        from entity_manager import is_dead
        npcs = self.json_ops.load_json("npcs.json") or {}
        listed = [key + (" (secret: only its members know)" if secret else "")
                  + (" (dead)" if is_dead(npcs[key]) else "")
                  for key, secret in members(npcs, fid, living=False)]
        return [f"  Members: {'; '.join(listed)}" if listed else "  Members: none named"]

    def _world_lines(self, cid: str) -> list[str]:
        import faction_rules
        import facts as fact_file
        import world_rules
        lines = [f"  {line[0].upper()}{line[1:]}" for line in faction_rules.card_lines(
            self.json_ops, cid.partition(":")[2])] if has_file(self.json_ops) else []
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
            lines.append("(From the world bible: gm-faction.sh from-bible copies them into "
                         "factions.json, as does the first create, set, alias, asset or join; "
                         "until then facts can't name them.)")
        return lines


def _cmd_create(m, args):
    fid = m.create(args.name, args.description, args.id, args.kind, args.impulse, args.value,
                   args.alias, args.tag, args.leader, args.successor, args.another)
    print(f"[SUCCESS] Faction faction:{fid} ({args.name})")


def _cmd_set(m, args):
    fid, before = m.set_field(args.faction, args.field, args.values)
    was = "; ".join(before) if isinstance(before, list) else before
    print(f"[SUCCESS] faction:{fid} {args.field} set" + (f" (was: {was})" if was else ""))


def _cmd_alias(m, args):
    from world_ids import change_aliases
    if not args.aliases and not args.remove:
        raise FactionError("Give the aliases to add, or --remove <alias>.")
    m._seed()
    key, aliases = change_aliases(m.json_ops, "faction", args.faction, args.aliases, args.remove)
    print(f"faction:{key} is also called: {', '.join(aliases) or 'nothing else'}")


def _cmd_asset(m, args):
    fid, assets = m.asset(args.faction, args.name, args.note, args.remove)
    print(f"faction:{fid} assets: {', '.join(a['name'] for a in assets) or 'none'}")


def _cmd_tie(m, args):
    fid, other, before = m.tie(args.faction, args.other, args.text)
    what = f"sees {other}: {' '.join(args.text.split())}" if args.text.strip() else f"has no tie to {other} now"
    print(f"[SUCCESS] faction:{fid} {what}" + (f" (was: {before})" if before else ""))


def _cmd_leave(m, args):
    done = m.leave(args.faction, args.npc)
    print(f"[SUCCESS] npc:{done['npc']} left faction:{done['faction']}")
    if done["lost"]:
        print(f"  No longer knows (only the faction did): {', '.join(done['lost'])}. What they "
              f"take along is told with gm-note.sh tell <id> \"npc:{done['npc']}\".")


def _cmd_turn(m, args):
    import faction_turns
    from cli_output import json_input
    try:
        print("\n".join(faction_turns.run(m.json_ops, json_input(args.actions, "the actions"),
                                          only=args.only)))
    except faction_turns.TurnError as error:
        raise FactionError(str(error)) from error


def _cmd_job(m, args):
    import faction_jobs
    from cli_output import json_input
    try:
        if args.what == "offer":
            lines = faction_jobs.offer(m.json_ops, args.faction, json_input(args.spec, "the job"))
        else:
            lines = faction_jobs.outcome(m.json_ops, args.faction, args.what)
    except faction_jobs.JobError as error:
        raise FactionError(str(error)) from error
    print("\n".join(lines))


def _cmd_ask(m, args):
    import faction_jobs
    try:
        lines = (faction_jobs.ask_again if args.again else faction_jobs.ask)(m.json_ops)
    except faction_jobs.JobError as error:
        raise FactionError(str(error)) from error
    print("\n".join(lines))


def _from_bible(m) -> None:
    if has_file(m.json_ops):
        raise FactionError(f"There is a {FILE} already: the factions are copied in.")
    if not m._seed():
        raise FactionError("The world bible lists no factions.")


def _cmd_list(m, args):
    lines = m.list_lines()
    print("\n".join(lines) if lines else
          "No factions yet (bash tools/gm-faction.sh create \"<name>\" --description \"…\").")


def _print_join(done: dict[str, Any], secret) -> None:
    from consequence_manager import print_fired
    who, fid = f"npc:{done['npc']}", f"faction:{done['faction']}"
    if done["changed"]:
        print(f"[SUCCESS] {who}'s membership of {fid} is "
              + ("secret now: only its members know" if secret else "open now"))
        return
    print(f"[SUCCESS] {who} joined {fid}" + (" (secret: only its members know)" if secret else ""))
    if done["learned"]:
        print(f"  Now knows what the faction knows: {', '.join(done['learned'])}")
    print_fired(done["fired"])


def _check_id(fid: str) -> str:
    import faction_rules
    if fid in (faction_rules.BLANK, faction_rules.JOKER, faction_rules.PEOPLE):
        raise FactionError(f"'{fid}' is a kind of token in the faction bag; give the faction "
                           f"another id with --id.")
    if not ID_RE.match(fid):
        raise FactionError(f"A faction's id is short, lowercase letters, digits and "
                           f"dashes (\"lull\", \"red-hand\"); got '{fid}'. Give one with --id.")
    return fid


def _dead_mark(json_ops, cid: str) -> str:
    from entity_manager import is_dead
    npc = (json_ops.load_json("npcs.json") or {}).get(cid.partition(":")[2]) if json_ops else None
    return " (dead)" if isinstance(npc, dict) and is_dead(npc) else ""


def succession(json_ops, cid: str) -> list[str]:
    """After `cid` died: the factions it led or was to lead, and what to do."""
    out = []
    for fid, row in load(json_ops).items():
        if row.get("leader") == cid:
            heir = row.get("successor", "")
            out.append(f"{cid.partition(':')[2]} led {row.get('name', fid)}: " + (
                f"{heir.partition(':')[2]} takes over (bash tools/gm-faction.sh set {fid} leader "
                f"\"{heir}\", then set a new successor); its impulses may shift with the new leader."
                if heir else f"it has no successor: who takes over is a plot of its own "
                f"(gm-faction.sh set {fid} leader <npc>)."))
        elif row.get("successor") == cid:
            out.append(f"{cid.partition(':')[2]} was to lead {row.get('name', fid)}: name another "
                       f"successor (gm-faction.sh set {fid} successor <npc>).")
    return out


def _record_lines(row: dict[str, Any], json_ops=None) -> list[str]:
    lines = [f"  Also called: {', '.join(row['aliases'])}"] if row.get("aliases") else []
    lines += [f"  {field.capitalize()}: {row[field]}" for field in ("kind", "description")
              if row.get(field)]
    for field in ("impulses", "values"):
        if row.get(field):
            lines += [f"  {field.capitalize()}:", *(f"    - {item}" for item in row[field])]
    lines += [f"  {field.capitalize()}: {row[field].partition(':')[2]}{_dead_mark(json_ops, row[field])}"
              for field in PEOPLE_FIELDS if row.get(field)]
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
    p = sub.add_parser("tie", help="how one faction sees another, a line; no text removes it")
    p.add_argument("faction")
    p.add_argument("other")
    p.add_argument("text", nargs="?", default="")
    p = sub.add_parser("join", help="an NPC joins: they learn what the faction knows")
    p.add_argument("faction")
    p.add_argument("npc")
    flag = p.add_mutually_exclusive_group()
    flag.add_argument("--secret", dest="secret", action="store_const", const=True,
                      help="only the faction's members know it")
    flag.add_argument("--open", dest="secret", action="store_const", const=False,
                      help="a member already: no longer secret")
    p = sub.add_parser("leave", help="an NPC leaves: they no longer know what only it knew")
    p.add_argument("faction")
    p.add_argument("npc")
    sub.add_parser("show", help="a faction in full").add_argument("faction")
    sub.add_parser("list", help="every faction, one line each")
    sub.add_parser("from-bible", help="an older campaign: copy the bible's factions in")
    p = sub.add_parser("turn", help="a faction turn: the JSON list of actions after the command")
    p.add_argument("actions", nargs="?", default="-")
    p.add_argument("--only", help="this one faction takes its turn, nobody else (without it, "
                                  "every faction needs an action)")
    p = sub.add_parser("job", help="a faction's job for the character: offer (the JSON after "
                                   "the command), then done, failed or refused")
    p.add_argument("what", choices=("offer", "done", "failed", "refused"))
    p.add_argument("faction")
    p.add_argument("spec", nargs="?", default="-")
    p = sub.add_parser("ask", help="an owed ask: one of the character's people, drawn at random")
    p.add_argument("--again", action="store_true", help="draw another person (the first didn't fit)")
    args = parser.parse_args()

    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        print("[ERROR] No active campaign.", file=sys.stderr)
        return 1
    m = FactionManager(JsonOperations(str(campaign)))
    try:
        COMMANDS[args.action](m, args)
    except (FactionError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    finally:
        for note in m.notes:                       # the bible's factions copied in
            print(f"[NOTE] {note}")
    return 0


COMMANDS = {
    "create": _cmd_create, "set": _cmd_set, "alias": _cmd_alias, "asset": _cmd_asset,
    "join": lambda m, args: _print_join(m.join(args.faction, args.npc, args.secret), args.secret),
    "leave": _cmd_leave, "tie": _cmd_tie, "from-bible": lambda m, args: _from_bible(m), "turn": _cmd_turn, "show": lambda m, args: print(m.show(args.faction)), "list": _cmd_list,
    "job": _cmd_job, "ask": _cmd_ask,
}


if __name__ == "__main__":
    sys.exit(main())
