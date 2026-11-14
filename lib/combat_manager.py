#!/usr/bin/env python3
"""
Persisted fight state: each enemy's wounds, notes and conditions.

Kept in `combat_state.json` so a fight survives turns, compaction and resume.
Fights are OPTIONAL: a narrated skirmish that never calls `start` still works.

Each enemy instance has its own line ("street thug 1", "street thug 2") with the
number of wounds that takes it out, from its sheet. Notes record disabled parts
("right arm disabled"). The player's wounds live on the sheet (`gm-body.sh`).
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager
from game_core import add_condition, remove_condition


class CombatManager(EntityManager):

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self.combat_file = "combat_state.json"

    def _load(self) -> dict[str, Any]:
        return self.json_ops.load_json(self.combat_file) or {}

    def _save(self, data: dict[str, Any]) -> bool:
        return self.json_ops.save_json(self.combat_file, data)

    def is_active(self) -> bool:
        return bool(self._load().get('combatants'))

    def start(self) -> dict[str, Any]:
        data = {'active': True, 'combatants': []}
        self._save(data)
        return data

    def add_combatant(self, name: str, wounds: int | None = None,
                      sheet: str | None = None) -> dict[str, Any]:
        """Add an enemy line. `sheet` names the NPC or mob it is an instance of
        ("street thug 2" as "street thug"): its wounds come from that sheet, and
        contests use that name. Raises ValueError."""
        if (wounds is None) == (sheet is None):
            raise ValueError("Give the wounds, or --as <NPC or mob> to read them from its sheet.")
        if sheet is not None:
            from skill_contest import ContestError, find_sheet
            try:
                found = find_sheet(self.campaign_dir, sheet)
            except ContestError as error:
                raise ValueError(str(error)) from error
            if found.get('is_player'):
                raise ValueError("The player's wounds live on the sheet (gm-body.sh), not here.")
            wounds = (found.get('body') or {}).get('wounds')
            if not isinstance(wounds, int) or wounds < 1:
                raise ValueError(f"'{sheet}' has no wounds on its sheet; set them with "
                                 f"gm-npc.sh stats / gm-mob.sh stats --wounds N.")
        if int(wounds) < 1:
            raise ValueError("wounds: at least 1.")
        data = self._load()
        if not data.get('active'):
            data = self.start()
        if self._find(data, name):
            raise ValueError(f"There is already a line '{name}'; number them ('{name} 2').")
        combatant = {'name': name, 'wounds': int(wounds), 'taken': 0,
                     'notes': [], 'conditions': []}
        if sheet is not None:
            combatant['as'] = sheet
        data.setdefault('combatants', []).append(combatant)
        self._save(data)
        return combatant

    def _find(self, data, name):
        for c in data.get('combatants', []):
            if c['name'].lower() == name.lower():
                return c
        return None

    def wound(self, name: str, count: int = 1, note: str | None = None) -> dict[str, Any] | None:
        """Deal wounds. A note records what they did, e.g. "right arm disabled"."""
        data = self._load()
        c = self._find(data, name)
        if c is None:
            return None
        c['taken'] = min(c['wounds'], c['taken'] + count)
        if note:
            c['notes'].append(note)
        self._save(data)
        return c

    def set_condition(self, name: str, action: str, condition: str) -> dict[str, Any] | None:
        data = self._load()
        c = self._find(data, name)
        if c is None:
            return None
        c['conditions'] = (add_condition(c['conditions'], condition) if action == 'add'
                           else remove_condition(c['conditions'], condition))
        self._save(data)
        return c

    def end(self) -> dict[str, Any]:
        """Close the fight. Each enemy taken out earns the player its wounds² × 10
        XP (growth.py), booked and logged here; driving one off or escaping is an
        achievement the GM awards instead (gm-growth)."""
        data = self._load()
        defeated = [c for c in data.get('combatants', []) if c['taken'] >= c['wounds']]
        summary = {
            'combatants': [c['name'] for c in data.get('combatants', [])],
            'defeated': [c['name'] for c in defeated],
            'xp': 0,
        }
        self._save({})  # clear — the fight is over
        if defeated and self.json_ops.load_json("character.json"):
            from growth import add_xp, fight_xp
            character = self.json_ops.load_json("character.json")
            for c in defeated:
                xp = fight_xp(c['wounds'])
                result = add_xp(self.campaign_dir, character, xp, "fight",
                                f"defeated {c['name']} ({c['wounds']} wounds)")
                summary['xp'] += xp
            self.json_ops.save_json("character.json", character)
            summary['growth_due'] = result['due']
        return summary

    def header(self) -> str:
        data = self._load()
        if not data.get('combatants'):
            return "(no active combat)"
        lines = ["⚔ FIGHT"]
        for c in data['combatants']:
            boxes = '●' * c['taken'] + '○' * (c['wounds'] - c['taken'])
            out = ', out' if c['taken'] >= c['wounds'] else ''
            extra = ', '.join(c['notes'] + c['conditions'])
            sheet = f" [rolls as {c['as']}]" if c.get('as') and c['as'].lower() != c['name'].lower() else ""
            lines.append(f"  {c['name']}{sheet}: {boxes}{out}" + (f" ({extra})" if extra else ""))
        return "\n".join(lines)


def main():
    import argparse
    import json

    from cli_output import emit, emit_error, strip_json_flag, wants_json

    parser = argparse.ArgumentParser(description="Persisted fight state")
    sub = parser.add_subparsers(dest='action')
    sub.add_parser('start')
    p = sub.add_parser('add-enemy')
    p.add_argument('name')
    p.add_argument('wounds', type=int, nargs='?')
    p.add_argument('--as', dest='sheet', help='the NPC or mob it is an instance of; wounds from its sheet')
    p = sub.add_parser('wound')
    p.add_argument('name')
    p.add_argument('count', type=int, nargs='?', default=1)
    p.add_argument('--note')
    p = sub.add_parser('condition')
    p.add_argument('name')
    p.add_argument('op', choices=['add', 'remove'])
    p.add_argument('condition')
    sub.add_parser('header')
    sub.add_parser('status')
    sub.add_parser('end')

    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help()
        sys.exit(1)

    m = CombatManager()
    out = None
    if args.action == 'start':
        out = m.start()
    elif args.action == 'add-enemy':
        try:
            out = m.add_combatant(args.name, args.wounds, args.sheet)
        except ValueError as error:
            sys.exit(emit_error(str(error), json_mode=json_mode))
    elif args.action == 'wound':
        out = m.wound(args.name, args.count, args.note)
    elif args.action == 'condition':
        out = m.set_condition(args.name, args.op, args.condition)
    elif args.action == 'end':
        out = m.end()
    elif args.action in ('header', 'status'):
        print(m.header())
        return

    if out is None:
        if json_mode:
            sys.exit(emit_error("combatant not found", json_mode=True))
        print("[ERROR] combatant not found", file=sys.stderr)
        sys.exit(1)
    if json_mode:
        emit(out, json_mode=True)
    else:
        print(json.dumps(out, indent=2))
        print(m.header())


if __name__ == "__main__":
    main()
