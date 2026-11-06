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

    def add_fact(self, category: str, fact: str, list_waiting: bool = True) -> str:
        """Add a fact to the specified category. Returns its id, or "" on failure.

        Each fact carries an id, the in-game time it was recorded (`game_time`,
        copied from campaign-overview.json; left out if the campaign has none)
        and the real-world `timestamp`. Afterwards it lists the consequences
        waiting on an event, unless `list_waiting` is False (the caller lists them).
        """
        facts = self.json_ops.load_json("facts.json")
        assign_missing_ids(facts)

        if category not in facts:
            facts[category] = []

        fact_id = next_fact_id(facts)
        entry = {'id': fact_id, 'fact': fact}
        game_time = (self.json_ops.load_json("campaign-overview.json") or {}).get("game_time")
        if game_time:
            entry['game_time'] = game_time
        entry['timestamp'] = datetime.now(timezone.utc).isoformat()
        facts[category].append(entry)

        if not self.json_ops.save_json("facts.json", facts):
            print(f"[ERROR] Failed to save fact")
            return ""

        print(f"[SUCCESS] Recorded fact {fact_id} in {category}: {fact}")
        if list_waiting:
            self._list_waiting(fact_id)
        return fact_id

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
    if len(sys.argv) < 2:
        print("Usage: python lib/note_manager.py add <category> <fact>")
        print("       python lib/note_manager.py get [category]")
        print("       python lib/note_manager.py categories")
        sys.exit(1)

    action = sys.argv[1]

    try:
        manager = NoteManager()

        if action == 'add':
            if len(sys.argv) < 4:
                print("Usage: python lib/note_manager.py add <category> <fact>")
                sys.exit(1)
            category = sys.argv[2]
            fact = sys.argv[3]
            if not manager.add_fact(category, fact):
                sys.exit(1)

        elif action == 'get':
            category = sys.argv[2] if len(sys.argv) > 2 else None
            facts = manager.get_facts(category)
            print(json.dumps(facts, indent=2))

        elif action == 'categories':
            categories = manager.list_categories()
            for cat in categories:
                print(f"  - {cat}")

        else:
            print(f"Unknown action: {action}")
            sys.exit(1)

    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
