#!/usr/bin/env python3
"""Note/fact management module for GM tools."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from json_ops import JsonOperations


def assign_missing_ids(facts: dict) -> dict:
    """Give every fact an id ("f1", "f2", ...), so other records can point to it.

    Facts without one (written before ids existed, or by the import scripts,
    which write facts.json directly) are numbered in the order they were
    recorded, after the highest existing id. A bare string becomes
    {"fact": <string>}. Changes `facts` in place and returns it.
    """
    entries = []
    highest = 0
    for category, items in facts.items():
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                item = {'fact': str(item)}
                items[i] = item
            fid = str(item.get('id', ''))
            if fid.startswith('f') and fid[1:].isdigit():
                highest = max(highest, int(fid[1:]))
            elif 'id' not in item:
                entries.append(item)
    entries.sort(key=lambda item: str(item.get('timestamp', '')))
    for item in entries:
        highest += 1
        item['id'] = f"f{highest}"
    return facts


TRUTH_VALUES = ("partial", "wrong")  # a missing `truth` means true


def fact_text(entry) -> str:
    """A fact's text as the GM should read it, wherever it is shown or searched:
    a secret (holders recorded and empty: nobody knows it) is marked [SECRET], one
    that others know but the player character doesn't is marked [HIDDEN FROM PLAYER],
    a wrong or partial version is marked with the id of the truth."""
    if not isinstance(entry, dict):
        return str(entry)
    text = str(entry.get('fact', entry.get('text', entry.get('event', ''))))
    holders = entry.get('holders')
    if holders == []:
        text = f"[SECRET] {text}"
    elif isinstance(holders, list) and not {'player', 'public'} & set(holders):
        text = f"[HIDDEN FROM PLAYER] {text}"     # who knows it: the NPC block
    truth, of = entry.get('truth'), entry.get('version_of')
    if truth == 'wrong':
        return f"[WRONG; the truth is {of}] {text}" if of else f"[WRONG] {text}"
    if truth == 'partial':
        return f"[PARTIAL; fuller: {of}] {text}" if of else f"[PARTIAL] {text}"
    return text


def next_fact_id(facts: dict) -> str:
    """The id the next fact gets. Expects every fact to have one already."""
    highest = 0
    for items in facts.values():
        if isinstance(items, list):
            for item in items:
                fid = str(item.get('id', '')) if isinstance(item, dict) else ''
                if fid.startswith('f') and fid[1:].isdigit():
                    highest = max(highest, int(fid[1:]))
    return f"f{highest + 1}"


class NoteManager:
    """Manage campaign facts and notes."""

    def __init__(self, world_state_dir: str = "world-state"):
        self.world_state_dir = world_state_dir
        self.last_fired = []  # on_learn consequences fired by the last add_fact / tell
        self.campaign_mgr = CampaignManager(world_state_dir)
        self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()

        if self.campaign_dir is None:
            raise RuntimeError("No active campaign. Run /new-game or /import first.")

        self.json_ops = JsonOperations(str(self.campaign_dir))

        # Ensure facts file exists
        facts_path = self.campaign_dir / "facts.json"
        if not facts_path.exists():
            self.json_ops.save_json("facts.json", {})

    def _about(self, fact: str, about=None, not_about=None):
        """(about ids, ids found in the text, errors) for a new fact.

        The ids given are checked; names found in the text are added, except those
        in `not_about`. That is the cross-check: the GM needn't remember who a
        fact names (design-notes.md, "A fact's fields").
        """
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        given, errors = ids.resolve_all(about)
        dropped, more = ids.resolve_all(not_about)
        errors += more
        found = [i for i in ids.mentioned(fact) if i not in given and i not in dropped]
        return [i for i in given if i not in dropped] + found, found, errors

    def _holders(self, holders=None, secret: bool = False, also=None):
        """(holder ids, errors) for a new fact. None = the default: the player and
        the NPCs present; `also` adds to the default. `secret` = nobody (a GM-only
        secret)."""
        from world_ids import WorldIds
        if sum([holders is not None, secret, bool(also)]) > 1:
            return [], ["Give one of --holders (instead of the default), --also (on top "
                        "of it) or --secret (nobody)."]
        if secret:
            return [], []
        ids = WorldIds(self.json_ops)
        if holders is not None:
            return ids.resolve_all(holders, holders=True)
        extra, errors = ids.resolve_all(also, holders=True)
        default = ids.present()
        return default + [h for h in extra if h not in default], errors

    def add_fact(self, category: str, fact: str, list_waiting: bool = True,
                 about=None, not_about=None, holders=None, secret: bool = False,
                 also=None, truth=None, version_of=None) -> str:
        """Add a fact to the specified category. Returns its id, or "" on failure.

        Each fact carries an id, the in-game time it was recorded (`game_time`,
        copied from campaign-overview.json; left out if the campaign has none)
        and the real-world `timestamp`. `about` lists who or what it concerns:
        the ids given plus the names found in the text, minus `not_about`; an
        unknown id refuses the fact. `holders` lists who knows it: by default
        the player and the NPCs present (`also` adds to that); a list given
        replaces it; `secret`
        (or an empty list) means nobody, a GM-only secret. Afterwards it lists
        the consequences waiting on an event, unless `list_waiting` is False.
        """
        about_ids, found, errors = self._about(fact, about, not_about)
        holder_ids, more = self._holders(holders, secret, also)
        errors += more
        truth, version_of, version_notes, more = self._check_version(
            self.json_ops.load_json("facts.json") or {}, truth, version_of)
        errors += more
        if errors:
            for error in errors:
                print(f"[ERROR] {error}", file=sys.stderr)
            print("[ERROR] Fact not recorded.", file=sys.stderr)
            return ""
        facts = self.json_ops.load_json("facts.json")
        assign_missing_ids(facts)

        if category not in facts:
            facts[category] = []

        fact_id = next_fact_id(facts)
        entry = {'id': fact_id, 'fact': fact}
        if about_ids:
            entry['about'] = about_ids
        entry['holders'] = holder_ids
        if truth:
            entry['truth'] = truth
        if version_of:
            entry['version_of'] = version_of
        game_time = (self.json_ops.load_json("campaign-overview.json") or {}).get("game_time")
        if game_time:
            entry['game_time'] = game_time
        entry['timestamp'] = datetime.now(timezone.utc).isoformat()
        facts[category].append(entry)

        if not self.json_ops.save_json("facts.json", facts):
            print(f"[ERROR] Failed to save fact")
            return ""

        print(f"[SUCCESS] Recorded fact {fact_id} in {category}: {fact}")
        if about_ids:
            which = "all" if found == about_ids else ", ".join(found)
            note = (f" ({which} found in the text; drop a wrong one with "
                    f"gm-note.sh about {fact_id} --remove <id>)") if found else ""
            print(f"  about: {', '.join(about_ids)}{note}")
        print(f"  known to: {', '.join(holder_ids) if holder_ids else 'nobody (a secret)'}")
        for note in version_notes:
            print(f"  {note}")
        if truth:
            print(f"  {fact_text({'truth': truth, 'version_of': entry.get('version_of')}).strip()}")
        if holders is None and not secret:
            self._named_but_absent(fact_id, about_ids, holder_ids)
        from consequence_manager import print_fired
        print_fired(self._learned(fact_id, entry, holder_ids))
        if list_waiting:
            self._list_waiting(fact_id)
        return fact_id

    def set_about(self, fact_id: str, add=None, remove=None) -> list:
        """Add ids to, or remove them from, a recorded fact's `about`.
        Returns the new list; raises ValueError for an unknown fact or id."""
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        adding, errors = ids.resolve_all(add)
        removing, more = ids.resolve_all(remove)
        if errors + more:
            raise ValueError("; ".join(errors + more))
        facts = self.json_ops.load_json("facts.json")
        entry = self._entry(facts, fact_id)
        about = [i for i in entry.get('about', []) if i not in removing]
        about += [i for i in adding if i not in about]
        if about:
            entry['about'] = about
        else:
            entry.pop('about', None)
        self.json_ops.save_json("facts.json", facts)
        return about

    def _named_but_absent(self, fact_id: str, about_ids, holder_ids) -> None:
        """The scene cross-check: living NPCs a scene fact names who aren't in the
        scene. Either they're here and the GM forgot `gm-scene.sh enter`, or the
        fact is only about them, which is fine."""
        npcs = self.json_ops.load_json("npcs.json") or {}
        absent = [i[4:] for i in about_ids if i.startswith("npc:") and i not in holder_ids
                  and (npcs.get(i[4:]) or {}).get("status") != "dead"]
        if absent:
            names = " ".join(f'"{n}"' for n in absent)
            print(f"  Named but not in the scene: {', '.join(absent)}. If they're here: "
                  f"bash tools/gm-scene.sh enter {names}, then "
                  f"gm-note.sh tell {fact_id} {' '.join('npc:' + n for n in absent)}")

    def _learned(self, fact_id: str, entry: dict, new_holders) -> list:
        """Fire the on_learn consequences for holders who just learned a fact.
        Returns the fired consequences (also kept in `last_fired`)."""
        from consequence_manager import ConsequenceManager
        self.last_fired = []
        if not new_holders:
            return []
        about = entry.get('about') or []
        values = []
        for who in list(new_holders) + ['anyone']:
            values.append(f"{who} learns {fact_id}")
            values += [f"{who} learns about:{a}" for a in about]
        try:
            cm = ConsequenceManager(self.world_state_dir)
        except RuntimeError:
            return []
        self.last_fired = cm.fire_event(
            'on_learn', values, f"{', '.join(new_holders)} learned {fact_id}: {entry['fact']}")
        return self.last_fired

    def _check_version(self, facts: dict, truth=None, version_of=None, fact_id=None):
        """(truth, version_of, notes, errors) for a fact, checked.

        `truth`: None (true), partial or wrong. `version_of`: the fullest true
        version. A version of a version points at its root instead, so the truth
        is always one step away. It can't point at itself, or at a wrong fact
        with no truth behind it. A version needs a truth (partial or wrong).
        """
        errors, notes = [], []
        if truth in ('true', ''):
            truth = None
        if truth is not None and truth not in TRUTH_VALUES:
            errors.append(f"truth is partial or wrong (or true), not {truth!r}.")
        if version_of and truth is None and not errors:
            errors.append("A version of another fact is partial or wrong; give --truth too "
                          "(a true, full version would be the same fact twice).")
        if version_of:
            try:
                target = self._entry(facts, version_of)
            except ValueError as error:
                return truth, None, notes, [str(error)]
            root = target.get('version_of')
            if root:
                notes.append(f"{version_of} is itself a version of {root}; pointing at {root}.")
                version_of, target = root, self._entry(facts, root)
            if version_of == fact_id:
                errors.append("A fact can't be a version of itself.")
            elif target.get('truth') == 'wrong':
                errors.append(f"{version_of} is marked wrong; version_of points at the truth.")
        return truth, version_of, notes, errors

    def set_truth(self, fact_id: str, truth=None, version_of=None, keep_version=True) -> dict:
        """Mark a recorded fact true (None), partial or wrong, and/or link it to
        the fullest true version. Returns the entry; raises ValueError."""
        facts = self.json_ops.load_json("facts.json")
        entry = self._entry(facts, fact_id)
        if keep_version and version_of is None:
            version_of = entry.get('version_of')
        truth, version_of, notes, errors = self._check_version(facts, truth, version_of, fact_id)
        if any(f.get('version_of') == fact_id for items in facts.values() if isinstance(items, list)
               for f in items if isinstance(f, dict)) and (truth == 'wrong' or version_of):
            errors.append(f"Other facts are versions of {fact_id}; it is their truth.")
        if errors:
            raise ValueError(" ".join(errors))
        for key, value in (('truth', truth), ('version_of', version_of)):
            if value:
                entry[key] = value
            else:
                entry.pop(key, None)
        self.json_ops.save_json("facts.json", facts)
        for note in notes:
            print(f"  {note}")
        return entry

    def _entry(self, facts: dict, fact_id: str) -> dict:
        entry = next((f for items in facts.values() if isinstance(items, list)
                      for f in items if isinstance(f, dict) and f.get('id') == fact_id), None)
        if entry is None:
            raise ValueError(f"No fact '{fact_id}'.")
        return entry

    def tell(self, fact_id: str, holders) -> list:
        """Someone learns a recorded fact: add holders. Returns those who are new
        (already knowing isn't learning). Raises ValueError for an unknown fact or id."""
        from world_ids import WorldIds
        adding, errors = WorldIds(self.json_ops).resolve_all(holders, holders=True)
        if errors:
            raise ValueError("; ".join(errors))
        facts = self.json_ops.load_json("facts.json")
        entry = self._entry(facts, fact_id)
        known = entry.setdefault('holders', [])
        new = [h for h in adding if h not in known]
        self.last_fired = []
        if new:
            known.extend(new)
            self.json_ops.save_json("facts.json", facts)
            self._learned(fact_id, entry, new)
        return new

    def remove_facts(self, fact_ids) -> int:
        """Delete the facts with these ids (undoing a world tick). Returns how many."""
        ids = set(fact_ids)
        facts = self.json_ops.load_json("facts.json")
        removed = 0
        for category, items in facts.items():
            if not isinstance(items, list):
                continue
            kept = [f for f in items if not (isinstance(f, dict) and f.get('id') in ids)]
            removed += len(items) - len(kept)
            facts[category] = kept
        if removed:
            self.json_ops.save_json("facts.json", facts)
        return removed

    def _list_waiting(self, fact_id: str) -> None:
        """Show the consequences waiting on an event, so the GM can judge whether
        the new fact fulfils one (design-notes.md, "World state")."""
        from consequence_manager import ConsequenceManager, print_waiting
        try:
            waiting = ConsequenceManager(self.world_state_dir).waiting_on_event()
        except RuntimeError:
            return
        print_waiting(fact_id, waiting)

    def get_facts(self, category: str = None) -> dict:
        """Get facts, optionally filtered by category."""
        facts = self.json_ops.load_json("facts.json")
        if category:
            return {category: facts.get(category, [])}
        return facts

    def list_categories(self) -> list:
        """List all fact categories."""
        facts = self.get_facts()
        return list(facts.keys())


def main():
    """CLI interface for note management."""
    import argparse
    parser = argparse.ArgumentParser(description="Facts")
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("add", help="record a fact")
    p.add_argument("category"); p.add_argument("fact")
    p.add_argument("--about", action="append", default=[],
                   help="who or what it concerns (repeatable): player, npc:<name>, location:<name>")
    p.add_argument("--not-about", dest="not_about", action="append", default=[],
                   help="a name found in the text that the fact is not about")
    p_add = p
    p_add.add_argument("--holders", action="append",
                       help="who knows it (repeatable), instead of the default: the player "
                            "and the NPCs present. player, npc:<name>, street, public")
    p_add.add_argument("--also", action="append",
                       help="who else knows it, on top of the default (repeatable)")
    p_add.add_argument("--secret", action="store_true", help="nobody knows it (GM only)")
    p_add.add_argument("--truth", choices=list(TRUTH_VALUES),
                       help="partial (true, but leaves things out) or wrong; default true")
    p_add.add_argument("--version-of", dest="version_of",
                       help="the id of the fullest true version of this fact")
    p = sub.add_parser("truth", help="mark a recorded fact true, partial or wrong")
    p.add_argument("fact_id"); p.add_argument("truth", choices=["true"] + list(TRUTH_VALUES))
    p.add_argument("--version-of", dest="version_of")
    p.add_argument("--no-version", dest="no_version", action="store_true",
                   help="drop the link to the true version")
    p = sub.add_parser("tell", help="someone learns a recorded fact")
    p.add_argument("fact_id"); p.add_argument("holders", nargs="+")
    p = sub.add_parser("about", help="change a recorded fact's about")
    p.add_argument("fact_id")
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--remove", action="append", default=[])
    p = sub.add_parser("get"); p.add_argument("category", nargs="?")
    sub.add_parser("categories")
    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        manager = NoteManager()
        if args.action == 'add':
            if not manager.add_fact(args.category, args.fact,
                                    about=args.about, not_about=args.not_about,
                                    holders=args.holders, secret=args.secret,
                                    also=args.also, truth=args.truth,
                                    version_of=args.version_of):
                sys.exit(1)
        elif args.action == 'truth':
            entry = manager.set_truth(args.fact_id, args.truth, args.version_of,
                                      keep_version=not args.no_version)
            print(f"{args.fact_id}: {fact_text(entry)}")
        elif args.action == 'tell':
            new = manager.tell(args.fact_id, args.holders)
            print(f"{args.fact_id}: {', '.join(new)} now know(s) it" if new else
                  f"{args.fact_id}: they knew it already")
            from consequence_manager import print_fired
            print_fired(manager.last_fired)
        elif args.action == 'about':
            about = manager.set_about(args.fact_id, args.add, args.remove)
            print(f"{args.fact_id} about: {', '.join(about) or '(nothing)'}")
        elif args.action == 'get':
            print(json.dumps(manager.get_facts(args.category), indent=2))
        elif args.action == 'categories':
            for cat in manager.list_categories():
                print(f"  - {cat}")
    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
