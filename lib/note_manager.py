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

    def add_fact(self, category: str, fact: str, list_waiting: bool = True,
                 about=None, not_about=None) -> str:
        """Add a fact to the specified category. Returns its id, or "" on failure.

        Each fact carries an id, the in-game time it was recorded (`game_time`,
        copied from campaign-overview.json; left out if the campaign has none)
        and the real-world `timestamp`. `about` lists who or what it concerns:
        the ids given plus the names found in the text, minus `not_about`; an
        unknown id refuses the fact. Afterwards it lists the consequences
        waiting on an event, unless `list_waiting` is False (the caller lists them).
        """
        about_ids, found, errors = self._about(fact, about, not_about)
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
        entry = next((f for items in facts.values() if isinstance(items, list)
                      for f in items if isinstance(f, dict) and f.get('id') == fact_id), None)
        if entry is None:
            raise ValueError(f"No fact '{fact_id}'.")
        about = [i for i in entry.get('about', []) if i not in removing]
        about += [i for i in adding if i not in about]
        if about:
            entry['about'] = about
        else:
            entry.pop('about', None)
        self.json_ops.save_json("facts.json", facts)
        return about

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
                                    about=args.about, not_about=args.not_about):
                sys.exit(1)
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
