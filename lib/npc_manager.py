#!/usr/bin/env python3
"""NPCs: their sheets in npcs.json (sheet.py's format, keyed by name).

Create them, fill in fields when play needs them, give them stats, usual places,
aliases and items, take them into the party, kill them. What an NPC knows, feels
about the player, remembers or hides is not on the sheet: it is facts they hold
(`gm-note.sh ... --holders npc:<name>`), and `show` lists them.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import sheet as sheet_mod
from entity_manager import EntityManager, is_dead, is_party_member, usual_places

# Category of the fact `kill` records. Provisional: categories are due for rework
# (design-notes.md, "World state").
DEATH_FACT_CATEGORY = "session_events"
# Category of how an NPC regards the player (the attitude given at creation).
FEELING_CATEGORY = "relations"


class NPCManager(EntityManager):
    """The active campaign's NPCs."""

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self.npcs_file = "npcs.json"

    # ---------- helpers ----------

    def _npcs(self) -> Dict[str, Any]:
        return self._load_entities(self.npcs_file)

    def _save(self, npcs: Dict[str, Any]) -> bool:
        return self._save_entities(self.npcs_file, npcs)

    def _npc_key(self, name: str) -> str:
        """The NPC's key through the shared resolver, or '' (error printed)."""
        from world_ids import WorldIds
        raw = str(name).strip()
        cid, error = WorldIds(self.json_ops).resolve(
            raw if raw.lower().startswith("npc:") else f"npc:{raw}")
        if error:
            print(f"[ERROR] {error}")
            return ""
        return cid[4:]

    def _usual_places(self, locations) -> tuple:
        """(location keys, errors) for where an NPC is usually found."""
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        keys, errors = [], []
        for raw in locations or []:
            raw = str(raw).strip()
            cid, error = ids.resolve(raw if raw.lower().startswith("location:") else f"location:{raw}")
            if error:
                errors.append(f"{error} (a new place: gm-location.sh add \"<name>\" \"<where>\" first)")
            elif cid[9:] not in keys:
                keys.append(cid[9:])
        return keys, errors

    def get_sheet(self, name: str) -> Optional[Dict[str, Any]]:
        key = self._npc_key(name)
        return self._npcs().get(key) if key else None

    # ---------- creating ----------

    def create_npc(self, name: str, role: str = "", attitude: Optional[str] = None,
                   locations=None, nowhere: bool = False, aliases=None,
                   fields: Optional[Dict[str, str]] = None) -> bool:
        """Create an NPC sheet. Returns True on success, False on failure (printed).

        `role`: who they are in a few words. `attitude`: how they regard the player
        at first ("wary", "owes her a favour"); it becomes a fact they hold about
        the player, not a field, so later feelings are facts too. `locations`:
        where they are usually found (known places), required unless `nowhere`.
        `aliases`: shorter names the story will use, each checked. `fields`: any
        further text fields by flag name (sheet.TEXT_FIELDS), e.g. look, Big Five.
        """
        from world_ids import WorldIds, alias_hint
        places, errors = self._usual_places(locations)
        aliases = [a.strip() for a in aliases or [] if a.strip()]
        ids = WorldIds(self.json_ops)
        errors += [e for a in aliases if (e := ids.check_alias(a, f"npc:{name}"))]
        if nowhere and places:
            errors.append("Give --location or --nowhere, not both.")
        if not nowhere and not places and not errors:
            here = ((self.json_ops.load_json("campaign-overview.json") or {})
                    .get("player_position") or {}).get("current_location", "")
            hint = f' (here: --location "{here}")' if here else ""
            errors.append(f"Where is {name} usually found? Give --location <place>, "
                          f"repeatable{hint}, or --nowhere for someone with no usual place.")
        valid, error = self.validators.validate_name(name)
        if not valid:
            errors.append(error)
        if self._entity_exists(self.npcs_file, name):
            errors.append(f"NPC {name} already exists")
        sheet = sheet_mod.blank("npc", name)
        try:
            sheet_mod.set_fields(sheet, dict(fields or {}, **({"role": role} if role else {})))
            if aliases:
                sheet["identity"]["aliases"] = list(dict.fromkeys(aliases))
            sheet["places"] = {"usual": places}
            sheet_mod.check(sheet, "npc")
        except sheet_mod.SheetError as problem:
            errors.append(str(problem))
        if errors:
            for error in errors:
                print(f"[ERROR] {error}")
            return False
        if not self._add_entity(self.npcs_file, name, sheet):
            return False

        where = ', '.join(places) if places else 'no usual place'
        print(f"[SUCCESS] Created NPC: {name}" + (f" - {role}" if role else "")
              + f"; usually found: {where}")
        if aliases:
            print(f"  Also called: {', '.join(sheet['identity']['aliases'])}")
        elif alias_hint("npc", name):
            print(alias_hint("npc", name))
        if attitude and str(attitude).strip():
            self._first_feeling(name, str(attitude).strip())
        print(f"  Not in the scene yet: bash tools/gm-scene.sh enter \"{name}\" if they're here.")
        self._witness_hint(name)
        return True

    def _first_feeling(self, name: str, attitude: str) -> None:
        """How the NPC regards the player at first, as a fact only they hold."""
        from note_manager import NoteManager
        player = sheet_mod.name(self.json_ops.load_json("character.json") or {}) or "the player"
        NoteManager(self.base_dir).add_fact(
            FEELING_CATEGORY, f"{name} is {attitude} toward {player}.", list_waiting=False,
            about=[f"npc:{name}", "player"], holders=[f"npc:{name}"], nowhere=True)

    def _witness_hint(self, name: str) -> None:
        """A new NPC may have seen what happened here before they had a name (Lord
        Thane in the gallery, a guard who was a mob): point at gm-note.sh witness
        when facts were recorded at the current location."""
        from note_manager import NoteManager
        try:
            notes = NoteManager(self.base_dir) if self.base_dir else NoteManager()
            place, _ = notes._where()
            here = notes.find(at=place) if place else []
        except (RuntimeError, ValueError):
            return
        if here:
            print(f"  Was {name} here for what happened before ({len(here)} fact(s) at "
                  f"{place[9:]})? bash tools/gm-note.sh witness \"{name}\" [--from \"YYYY-MM-DD HH:MM\"] "
                  f"(--dry-run to see what they would learn)")

    # ---------- changing ----------

    def set_fields(self, name: str, values: Dict[str, str]) -> bool:
        key = self._npc_key(name)
        if not key:
            return False
        if not values:
            print(f"[ERROR] Give at least one field (fields: {', '.join(sheet_mod.TEXT_FIELDS)}).")
            return False
        npcs = self._npcs()
        try:
            changed = sheet_mod.set_fields(npcs[key], values)
            sheet_mod.check(npcs[key], "npc")
        except sheet_mod.SheetError as error:
            print(f"[ERROR] {error}")
            return False
        if not self._save(npcs):
            return False
        print(f"[SUCCESS] {key}: set {', '.join(changed)}")
        return True

    def set_stats(self, name: str, attrs=None, skills=None, remove_skills=None,
                  wounds: Optional[int] = None) -> Dict[str, Any]:
        """Set or update an NPC's stats (attributes, skills, wounds), checked
        (stat_block.py). Merges into what is there. Returns {"name", "entry",
        "warnings"}; raises stat_block.StatError, or ValueError for an unknown NPC."""
        from stat_block import check, merged
        key = self._find_entity_name(self.npcs_file, name)
        if not key:
            raise ValueError(f"NPC '{name}' not found")
        npcs = self._npcs()
        entry = merged(npcs[key], attrs, skills, remove_skills, wounds)
        warnings = check(entry, self.campaign_dir)
        if attrs or skills or remove_skills or wounds is not None:
            npcs[key] = entry
            self._save(npcs)
        return {"name": key, "entry": entry, "warnings": warnings}

    def tag_location(self, name: str, *locations: str) -> bool:
        """Add usual places (known locations only, close matches suggested)."""
        key = self._npc_key(name)
        if not key:
            return False
        places, errors = self._usual_places(locations)
        if errors or not places:
            for error in errors or ["Give at least one place."]:
                print(f"[ERROR] {error}")
            return False
        npcs = self._npcs()
        usual = sheet_mod.section(npcs[key], "places").setdefault("usual", [])
        added = [p for p in places if p.lower() not in {t.lower() for t in usual}]
        usual.extend(added)
        if not self._save(npcs):
            return False
        print(f"[SUCCESS] {key} usually found: {', '.join(usual)}" + ("" if added else " (no change)"))
        return True

    def untag_location(self, name: str, *locations: str) -> bool:
        """Remove usual places (matched loosely: case, punctuation, titles)."""
        from entity_aliases import normalize_entity_name
        key = self._npc_key(name)
        if not key:
            return False
        npcs = self._npcs()
        usual = sheet_mod.section(npcs[key], "places").setdefault("usual", [])

        def same(a, b):
            return a.lower() == b.lower() or (
                normalize_entity_name(a) and normalize_entity_name(a) == normalize_entity_name(b))

        missing = [raw for raw in locations if not any(same(raw, t) for t in usual)]
        if missing:
            print(f"[ERROR] {key} has no usual place {', '.join(repr(m) for m in missing)}; "
                  f"usually found: {', '.join(usual) or 'nowhere yet'}")
            return False
        npcs[key]["places"]["usual"] = [t for t in usual if not any(same(r, t) for r in locations)]
        if not self._save(npcs):
            return False
        left = npcs[key]["places"]["usual"]
        print(f"[SUCCESS] {key} usually found: {', '.join(left) or 'nowhere (no usual place left)'}")
        return True

    def item(self, name: str, action: str, place: Optional[str] = None,
             item_name: Optional[str] = None, concealed: bool = False, note: str = "") -> bool:
        key = self._npc_key(name)
        if not key:
            return False
        npcs = self._npcs()
        try:
            if action == "add":
                entry = sheet_mod.add_item(npcs[key], place, item_name, concealed, note)
                message = f"[SUCCESS] {key} {place}: {sheet_mod._item_text(entry)}"
            elif action == "remove":
                entry = sheet_mod.remove_item(npcs[key], item_name)
                message = f"[SUCCESS] {key} no longer has {entry['name']}"
            else:
                print(f"[ERROR] item add|remove, not {action}")
                return False
        except sheet_mod.SheetError as error:
            print(f"[ERROR] {error}")
            return False
        if not self._save(npcs):
            return False
        print(message)
        return True

    def kill_npc(self, name: str, cause: Optional[str] = None) -> Dict[str, Any]:
        """Mark an NPC dead, record the death as a fact, and fire the on_death
        consequences waiting for it. Refuses an NPC who is already dead, so
        on_death fires only once. A dead NPC is no longer present anywhere."""
        key = self._find_entity_name(self.npcs_file, name)
        if not key:
            print(f"[ERROR] NPC {name} not found")
            return {'success': False, 'error': f"NPC {name} not found"}
        npcs = self._npcs()
        if is_dead(npcs[key]):
            print(f"[ERROR] {key} is already dead")
            return {'success': False, 'error': f"{key} is already dead"}
        status = sheet_mod.section(npcs[key], "status")
        status.update({'state': 'dead', 'died_at': self.get_timestamp()})
        game_time = (self.json_ops.load_json("campaign-overview.json") or {}).get("game_time")
        if game_time:
            status['died_game_time'] = game_time
        if cause:
            status['cause'] = cause
        status.pop('party_member', None)
        if not self._save(npcs):
            return {'success': False, 'error': 'failed to save'}
        from scene_manager import SceneManager
        SceneManager(self.base_dir).leave([key], strict=False)

        from note_manager import NoteManager
        fact_id = NoteManager(self.base_dir).add_fact(
            DEATH_FACT_CATEGORY, f"{key} died" + (f": {cause}" if cause else "."))
        from consequence_manager import ConsequenceManager
        fired = ConsequenceManager(self.base_dir).fire_event(
            'on_death', f"npc:{key}", f"{key} died" + (f" ({cause})" if cause else ""))
        return {'success': True, 'name': key, 'status': 'dead', 'cause': cause,
                'fact': fact_id, 'fired': fired}

    # ---------- the party ----------

    def set_party(self, name: str, member: bool) -> bool:
        key = self._npc_key(name)
        if not key:
            return False
        npcs = self._npcs()
        if member and is_dead(npcs[key]):
            print(f"[ERROR] {key} is dead")
            return False
        status = sheet_mod.section(npcs[key], "status")
        if bool(status.get("party_member")) == member:
            print(f"[INFO] {key} is {'already' if member else 'not'} a party member")
            return True
        if member:
            status["party_member"] = True
        else:
            status.pop("party_member", None)
        if not self._save(npcs):
            return False
        print(f"[SUCCESS] {key} " + ("joined the party: present wherever the player is"
                                     if member else "left the party"))
        return True

    def get_party_members(self) -> Dict[str, Dict]:
        return {k: v for k, v in self._npcs().items() if is_party_member(v)}

    # ---------- showing ----------

    def show(self, name: str) -> Optional[str]:
        """The whole sheet, readable, plus what they know and feel about the player."""
        key = self._npc_key(name)
        if not key:
            return None
        npc = self._npcs()[key]
        lines = [f"=== {key} ==="]
        if sheet_mod.aliases(npc):
            lines.append(f"also called: {', '.join(sheet_mod.aliases(npc))}")
        lines += sheet_mod.describe(npc)
        if is_party_member(npc):
            lines.append("party member")
        try:
            from note_manager import NoteManager, fact_line
            known = NoteManager(self.base_dir).find(held_by=[f"npc:{key}"], about=["player"])
        except (RuntimeError, ValueError):
            known = []
        if known:
            lines.append("what they know and feel about the player (newest first):")
            lines += [f"  {fact_line(f)}" for f in known[:8]]
        return "\n".join(lines)

    def list_npcs(self, filter_location: Optional[str] = None) -> Dict[str, Dict]:
        npcs = self._npcs()
        if not filter_location:
            return npcs
        wanted = filter_location.lower()
        return {k: v for k, v in npcs.items() if wanted in [p.lower() for p in usual_places(v)]}


def main():
    import argparse
    from cli_output import wants_json, strip_json_flag, emit, emit_error

    parser = argparse.ArgumentParser(description='NPC sheets')
    sub = parser.add_subparsers(dest='action')

    p = sub.add_parser('create', help='Create an NPC')
    p.add_argument('name')
    p.add_argument('role', help='who they are, in a few words')
    p.add_argument('attitude', nargs='?', help='how they regard the player at first (becomes a fact)')
    p.add_argument('--location', action='append', dest='locations',
                   help='where they are usually found (repeatable)')
    p.add_argument('--nowhere', action='store_true', help='no usual place')
    p.add_argument('--alias', action='append', dest='aliases', help='a shorter name (repeatable)')
    sheet_mod.add_field_flags(p)

    p = sub.add_parser('set', help='Text fields: identity, look, personality, goal')
    p.add_argument('name')
    sheet_mod.add_field_flags(p)

    for action in ('show', 'status'):
        sub.add_parser(action, help='The whole sheet').add_argument('name')

    p = sub.add_parser('stats', help="Show or set an NPC's stats")
    p.add_argument('name')
    p.add_argument('--attr', action='append', default=[], help='ATTR=DIE, e.g. STR=12; default=10 for the rest')
    p.add_argument('--skill', action='append', default=[], help='Skill=VALUE, e.g. Handguns=4; default=N for the rest')
    p.add_argument('--remove-skill', dest='remove_skill', action='append', default=[])
    p.add_argument('--wounds', type=int, help='how many wounds take them out')

    p = sub.add_parser('alias', help="Add or remove an NPC's aliases")
    p.add_argument('name')
    p.add_argument('aliases', nargs='*')
    p.add_argument('--remove', action='append', default=[])

    for action in ('tag-location', 'untag-location'):
        p = sub.add_parser(action, help='Add or remove usual places')
        p.add_argument('name')
        p.add_argument('locations', nargs='+')

    p = sub.add_parser('item', help='Items: add gear|inventory "<item>", remove "<item>"')
    p.add_argument('name')
    p.add_argument('item_action', choices=['add', 'remove'])
    p.add_argument('words', nargs='+')
    p.add_argument('--concealed', action='store_true')
    p.add_argument('--note', default='')

    p = sub.add_parser('kill', help='Mark an NPC dead; fires its on_death consequences')
    p.add_argument('name')
    p.add_argument('--cause')

    p = sub.add_parser('list', help='List NPCs')
    p.add_argument('--location')
    for action in ('promote', 'demote'):
        sub.add_parser(action, help='Into or out of the party').add_argument('name')
    sub.add_parser('party', help='The party members')

    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help()
        sys.exit(1)
    manager = NPCManager()

    if args.action in ('show', 'status'):
        if json_mode:
            npc = manager.get_sheet(args.name)
            sys.exit(emit_error("NPC not found", json_mode=True)) if npc is None else emit(npc, json_mode=True)
            return
        text = manager.show(args.name)
        if text is None:
            sys.exit(1)
        print(text)
    elif args.action == 'create':
        if not manager.create_npc(args.name, args.role, args.attitude, locations=args.locations,
                                  nowhere=args.nowhere, aliases=args.aliases,
                                  fields=sheet_mod.fields_from_args(args)):
            sys.exit(1)
    elif args.action == 'set':
        if not manager.set_fields(args.name, sheet_mod.fields_from_args(args)):
            sys.exit(1)
    elif args.action == 'stats':
        from stat_block import StatError, describe, parse_pairs
        try:
            result = manager.set_stats(args.name, parse_pairs(args.attr, 'attr'),
                                       parse_pairs(args.skill, 'skill'), args.remove_skill,
                                       args.wounds)
        except (StatError, ValueError) as error:
            print(f"[ERROR] {error}")
            sys.exit(1)
        print(describe(result['name'], result['entry']))
        for warning in result['warnings']:
            print(f"  [WARNING] {warning}")
    elif args.action == 'alias':
        from world_ids import change_aliases
        try:
            key, aliases = change_aliases(manager.json_ops, "npc", args.name,
                                          args.aliases, args.remove)
        except ValueError as error:
            print(f"[ERROR] {error}")
            sys.exit(1)
        print(f"{key}: also called {', '.join(aliases)}" if aliases else f"{key}: no aliases")
    elif args.action == 'tag-location':
        if not manager.tag_location(args.name, *args.locations):
            sys.exit(1)
    elif args.action == 'untag-location':
        if not manager.untag_location(args.name, *args.locations):
            sys.exit(1)
    elif args.action == 'item':
        words = args.words
        if args.item_action == 'add':
            if len(words) != 2 or words[0] not in sheet_mod.ITEM_PLACES:
                print('[ERROR] item "<npc>" add gear|inventory "<item>" [--concealed]')
                sys.exit(1)
            ok = manager.item(args.name, 'add', words[0], words[1], args.concealed, args.note)
        else:
            ok = manager.item(args.name, 'remove', None, " ".join(words))
        if not ok:
            sys.exit(1)
    elif args.action == 'kill':
        if json_mode:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                result = manager.kill_npc(args.name, args.cause)
            if not result.get('success'):
                sys.exit(emit_error(result.get('error', 'kill failed'), json_mode=True))
            emit(result, json_mode=True)
            return
        result = manager.kill_npc(args.name, args.cause)
        if not result.get('success'):
            sys.exit(1)
        print(f"DEATH {result['name']} has died." + (f" Cause: {args.cause}" if args.cause else ""))
        from consequence_manager import print_fired
        print_fired(result.get('fired'))
    elif args.action == 'list':
        npcs = manager.list_npcs(args.location)
        if json_mode:
            emit(npcs, json_mode=True)
            return
        for key, npc in npcs.items():
            role = sheet_mod.get(npc, "identity", "role", "")
            dead = " (dead)" if is_dead(npc) else ""
            party = " [party]" if is_party_member(npc) else ""
            print(f"{key}{dead}{party}" + (f" - {role}" if role else ""))
    elif args.action in ('promote', 'demote'):
        if not manager.set_party(args.name, args.action == 'promote'):
            sys.exit(1)
    elif args.action == 'party':
        party = manager.get_party_members()
        print(", ".join(party) if party else "No party members.")


if __name__ == "__main__":
    main()
