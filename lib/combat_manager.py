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

ADD_ENEMY = 'bash tools/gm-combat.sh add-enemy "<name>" --as "<NPC or mob>"'


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
        """A new, empty fight. Refused (ValueError) while one with enemies is
        running: starting over used to wipe it without a word, and `end` then
        paid no XP for those already taken out."""
        running = [c['name'] for c in self._load().get('combatants') or []]
        if running:
            raise ValueError(
                f"A fight is running ({', '.join(running)}). Add to it with add-enemy, or end "
                f"it first: gm-combat.sh end (it pays XP for those taken out).")
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

    def fighter_lines(self) -> list[str]:
        """One indented line per enemy: its wounds as boxes, its notes and conditions."""
        lines = []
        for c in self._load().get('combatants') or []:
            boxes = '●' * c['taken'] + '○' * (c['wounds'] - c['taken'])
            out = ', out' if c['taken'] >= c['wounds'] else ''
            extra = ', '.join(c['notes'] + c['conditions'])
            sheet = f" [rolls as {c['as']}]" if c.get('as') and c['as'].lower() != c['name'].lower() else ""
            lines.append(f"  {c['name']}{sheet}: {boxes}{out}" + (f" ({extra})" if extra else ""))
        return lines

    def header(self) -> str:
        data = self._load()
        if not data.get('active'):
            return "No fight running."
        if not data.get('combatants'):
            return f"A fight has begun, with no enemies yet: {ADD_ENEMY}"
        return "\n".join(["⚔ FIGHT", *self.fighter_lines()])


def main():
    import argparse

    from cli_output import emit_error

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

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    m = CombatManager()
    if args.action in ('header', 'status'):
        print(m.header())
        return
    actions = {
        'start': lambda: m.start(),
        'add-enemy': lambda: m.add_combatant(args.name, args.wounds, args.sheet),
        'wound': lambda: m.wound(args.name, args.count, args.note),
        'condition': lambda: m.set_condition(args.name, args.op, args.condition),
        'end': lambda: m.end(),
    }
    try:
        out = actions[args.action]()
    except ValueError as error:
        sys.exit(emit_error(str(error)))
    if out is None:
        names = ", ".join(c['name'] for c in m._load().get('combatants') or []) or "nobody yet"
        sys.exit(emit_error(f"'{args.name}' isn't in the fight (in it: {names})."))
    print("\n".join(_report(m, args, out)))


def _report(m: CombatManager, args, out) -> list[str]:
    """What a command did: a [SUCCESS] line, then the enemies (or what is due)."""
    if args.action == 'start':
        return [f"[SUCCESS] A fight has begun; add each enemy: {ADD_ENEMY}"]
    if args.action == 'end':
        defeated = ", ".join(out['defeated']) or "nobody"
        lines = [f"[SUCCESS] The fight is over. Taken out: {defeated}"
                 + (f"; +{out['xp']} XP" if out['xp'] else "")]
        due = out.get('growth_due')
        if due:
            lines.append(f"[DO] Growth due ({due} level{'s' if due > 1 else ''}): at the next "
                         f"quiet moment (rest, sleep, time alone), gm-growth. Don't tell the "
                         f"player.")
        return lines
    if args.action == 'add-enemy':
        first = (f"[SUCCESS] {out['name']} joins the fight ({out['wounds']} wound"
                 f"{'s' if out['wounds'] != 1 else ''} take them out)")
    elif args.action == 'wound':
        first = (f"[SUCCESS] {out['name']}: {out['taken']} of {out['wounds']} wounds"
                 + (", out" if out['taken'] >= out['wounds'] else ""))
    else:
        done = "added to" if args.op == 'add' else "removed from"
        first = f"[SUCCESS] {args.condition} {done} {out['name']}"
    return [first, *m.fighter_lines()]

if __name__ == "__main__":
    main()
