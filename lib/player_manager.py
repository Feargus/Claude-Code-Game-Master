#!/usr/bin/env python3
"""The player character's sheet (character.json, in sheet.py's format): show it,
change its fields, items, credits, counters and conditions, XP and growth, death.

Creation is new_character.py; wounds, armor and cyberware are body.py.
A campaign has one player character, so no command takes a name: they all work
on the active one.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import sheet as sheet_mod
from entity_manager import EntityManager


class PlayerManager(EntityManager):
    """The active campaign's player character."""

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self._kit_base = world_state_dir
        self._kit = None
        self.character_file = self.campaign_dir / "character.json"

    # ---------- loading ----------

    def _load_character(self) -> Optional[Dict]:
        """The player's sheet, or None."""
        return self.json_ops.load_json("character.json") or None

    def _save_character(self, data: Dict) -> bool:
        return self.json_ops.save_json("character.json", data)

    def _sheet(self) -> Optional[Dict[str, Any]]:
        char = self._load_character()
        if not char:
            print("[ERROR] No character yet. Create one: gm-player.sh create")
        return char

    def world_kit(self):
        if self._kit is None:
            from world_kit import WorldKit
            self._kit = WorldKit(self._kit_base)
        return self._kit

    @staticmethod
    def _refuse(message: str) -> Dict[str, Any]:
        print(f"[ERROR] {message}")
        return {'success': False, 'error': message}

    # ---------- showing ----------

    def get_player(self) -> Optional[Dict]:
        return self._sheet()

    def summary_line(self, char: Dict[str, Any]) -> str:
        from body import summary as wound_summary
        from growth import level
        identity = char.get("identity") or {}
        who = " ".join(x for x in (identity.get("race"), identity.get("role")) if x)
        line = (f"{sheet_mod.name(char)}" + (f" - {who}" if who else "")
                + f" - Level {level(char)} (Wounds: {wound_summary(char)}, "
                  f"Credits: {sheet_mod.get(char, 'possessions', 'credits', 0)})")
        line += self._counters_summary(char)
        if sheet_mod.is_dead(char):
            line += " | DEAD"
        if sheet_mod.conditions(char):
            line += f" | Conditions: {', '.join(sheet_mod.conditions(char))}"
        return line

    def show_player(self) -> Optional[str]:
        char = self._sheet()
        if not char:
            return None
        return "\n".join([self.summary_line(char), *sheet_mod.describe(char)])

    # ---------- fields ----------

    def set_fields(self, values: Dict[str, str]) -> Dict[str, Any]:
        """Text fields of the sheet (identity, look, personality), by flag name."""
        char = self._sheet()
        if not char:
            return {'success': False}
        if not values:
            return self._refuse("Give at least one field, e.g. --style \"...\" "
                                f"(fields: {', '.join(sheet_mod.TEXT_FIELDS)}).")
        try:
            changed = sheet_mod.set_fields(char, values)
            sheet_mod.check(char, "player")
        except sheet_mod.SheetError as error:
            return self._refuse(str(error))
        if not self._save_character(char):
            return {'success': False}
        print(f"[SUCCESS] {sheet_mod.name(char)}: set {', '.join(changed)}")
        return {'success': True, 'changed': changed}

    def change_aliases(self, add: List[str], remove: List[str]) -> Dict[str, Any]:
        """Add or remove the shorter names the story uses for the character, checked
        like an NPC's (world_ids.change_aliases). Without any, show them."""
        from world_ids import change_aliases
        char = self._sheet()
        if not char:
            return {'success': False}
        try:
            name, aliases = change_aliases(self.json_ops, "player", "", add, remove)
        except ValueError as error:
            return self._refuse(str(error))
        print(f"{name}: also called {', '.join(aliases)}" if aliases else f"{name}: no aliases")
        return {'success': True, 'aliases': aliases}

    # ---------- XP and growth ----------

    def award_xp(self, amount: int, source: str = "correction",
                 reason: str = "") -> Dict[str, Any]:
        """Book XP (growth.add_xp: logged in xp.log). XP only makes growth due;
        the level rises when it is applied (`grow`) at a quiet moment. Prints
        XP_GAIN, and GROWTH_DUE for the GM when a level has become due."""
        from growth import add_xp
        char = self._sheet()
        if not char:
            return {'success': False}
        result = add_xp(self.campaign_dir, char, int(amount), source, reason)
        if not self._save_character(char):
            return {'success': False}
        char_name = sheet_mod.name(char)
        print(f"XP_GAIN {char_name} gained {amount} XP ({result['total']} in all)")
        if result['due']:
            print(f"GROWTH_DUE {result['due']} level(s): at the next quiet moment (rest, sleep, "
                  f"time alone), see gm-growth. Don't tell the player.")
        return {'success': True, 'name': char_name, 'xp_gained': int(amount),
                'current_xp': result['total'], 'growth_due': result['due']}

    def award(self, size: str, reason: str) -> Dict[str, Any]:
        """XP for an achievement the GM judges: small, medium or large, i.e. 20, 50
        or 100 % of the current level's span (growth.py)."""
        from growth import achievement_xp
        char = self._sheet()
        if not char:
            return {'success': False, 'error': 'no character'}
        if not str(reason or '').strip():
            return self._refuse("Give --reason: what was achieved (it goes into xp.log).")
        try:
            amount = achievement_xp(char, size)
        except ValueError as error:
            return self._refuse(str(error))
        return self.award_xp(amount, f"achievement ({size})", reason)

    def get_xp_status(self) -> Optional[Dict[str, Any]]:
        from growth import growth_due, level, next_level_xp, xp_total
        char = self._sheet()
        if not char:
            return None
        now, current, due = level(char), xp_total(char), growth_due(char)
        print(f"{sheet_mod.name(char)} - Level {now}")
        print(f"XP: {current}/{next_level_xp(char)}")
        print(f"GROWTH_DUE {due} level(s)" if due else
              f"Next level in: {next_level_xp(char) - current} XP")
        return {'name': sheet_mod.name(char), 'level': now, 'current_xp': current,
                'next_level_xp': next_level_xp(char), 'growth_due': due}

    def _skill_key(self, skills: Dict[str, int], name: str) -> str:
        key = next((k for k in skills if k.lower() == name.lower()), None)
        if key is None:
            from stat_block import canon_skills
            key = next((k for k in canon_skills() if k.lower() == name.lower()), name)
        return key

    def raise_stat(self, kind: str, target: str) -> Dict[str, Any]:
        """A correction: one attribute one die size up, or one skill +1 (a skill
        not on the sheet starts at 1). Growth goes through `grow`."""
        from sheet import ATTRIBUTES
        char = self._sheet()
        if not char:
            return {'success': False, 'error': 'no character'}
        stats = sheet_mod.section(char, "stats")
        if kind == 'attribute':
            key = target.upper()
            if key not in ATTRIBUTES:
                return self._refuse(f"Unknown attribute '{target}'. Use one of: {', '.join(ATTRIBUTES)}")
            table = stats.setdefault('attributes', {})
            old = table.get(key)
            if not isinstance(old, int):
                return self._refuse(f"{sheet_mod.name(char)} has no die for {key} yet")
            table[key] = new = old + 1
        else:
            if target.strip().lower() == 'default':
                return self._refuse("'default' is not a skill")
            table = stats.setdefault('skills', {})
            key = self._skill_key(table, target.strip())
            old = table.get(key)
            table[key] = new = 1 if old is None else old + 1
        if not self._save_character(char):
            return {'success': False}
        shown = f"d{old} -> d{new}" if kind == 'attribute' else (
            f"{old} -> {new}" if old is not None else f"new, {new}")
        print(f"RAISED {sheet_mod.name(char)} {key}: {shown}")
        return {'success': True, 'kind': kind, 'name': key, 'previous': old, 'current': new}

    def set_perk(self, perk: str, function: str) -> Dict[str, Any]:
        """A correction: rewrite a perk, or add one by hand."""
        char = self._sheet()
        if not char:
            return {'success': False, 'error': 'no character'}
        perks = sheet_mod.section(char, "stats").setdefault('perks', {})
        key = next((k for k in perks if k.lower() == perk.lower()), perk)
        replaced = key in perks
        perks[key] = function
        if not self._save_character(char):
            return {'success': False}
        print(f"PERK {sheet_mod.name(char)} {'updated' if replaced else 'gained'} {key}: {function}")
        return {'success': True, 'perk': key, 'function': function, 'replaced': replaced}

    def grow(self, attribute: str, skills: List[str], perk: str, effect: str) -> Dict[str, Any]:
        """Apply one level of growth that XP has made due: exactly one attribute
        one die size up, two different skills +1 (a new one starts at 1) and one
        new perk. Raises the level by one and logs it."""
        from growth import growth_due, level, log_growth
        from sheet import ATTRIBUTES
        char = self._sheet()
        if not char:
            return {'success': False, 'error': 'no character'}
        if growth_due(char) < 1:
            return self._refuse("No growth is due: the XP hasn't reached the next level.")
        stats = sheet_mod.section(char, "stats")
        attributes = stats.setdefault('attributes', {})
        key = str(attribute or '').strip().upper()
        if key not in ATTRIBUTES:
            return self._refuse(f"Unknown attribute '{attribute}'. Use one of: {', '.join(ATTRIBUTES)}.")
        if not isinstance(attributes.get(key), int):
            return self._refuse(f"{sheet_mod.name(char)} has no die for {key} yet.")
        table = stats.setdefault('skills', {})
        names = [str(x).strip() for x in skills or []]
        if len(names) != 2 or names[0].lower() == names[1].lower():
            return self._refuse("Growth raises exactly two different skills (--skill twice).")
        if any(n.lower() == 'default' for n in names):
            return self._refuse("'default' is not a skill.")
        perks = stats.setdefault('perks', {})
        if not str(perk or '').strip() or not str(effect or '').strip():
            return self._refuse('Growth brings one new perk: --perk "<name>" "<what it does>".')
        if any(k.lower() == perk.strip().lower() for k in perks):
            return self._refuse(f"{sheet_mod.name(char)} has a perk '{perk}' already; "
                                f"name the new one differently.")

        attributes[key] += 1
        changes = [f"{key} d{attributes[key] - 1} -> d{attributes[key]}"]
        for n in names:
            skill = self._skill_key(table, n)
            old = table.get(skill)
            table[skill] = 1 if old is None or old < 1 else old + 1
            changes.append(f"{skill} {old if old is not None else 'new'} -> {table[skill]}")
        perks[perk.strip()] = effect.strip()
        changes.append(f"perk {perk.strip()}: {effect.strip()}")
        sheet_mod.section(char, "progress")["level"] = level(char) + 1
        if not self._save_character(char):
            return {'success': False}
        log_growth(self.campaign_dir, char, "; ".join(changes))
        print(f"GROWN {sheet_mod.name(char)} to level {level(char)}: " + "; ".join(changes))
        if growth_due(char):
            print(f"GROWTH_DUE {growth_due(char)} more level(s): run grow again with new choices.")
        return {'success': True, 'level': level(char), 'changes': changes}

    # ---------- the campaign's own counters (stats.counters) ----------

    def _kit_vitals(self) -> List[str]:
        return [v for v in self.world_kit().vitals() if v != 'hp']

    @staticmethod
    def _read_counter(char: Dict, name: str):
        raw = (sheet_mod.get(char, "stats", "counters") or {}).get(name)
        if isinstance(raw, dict):
            return raw.get('current', 0), raw.get('max')
        if isinstance(raw, (int, float)):
            return raw, None
        return 0, None

    def _counters_summary(self, char: Dict) -> str:
        parts = []
        for name in (sheet_mod.get(char, "stats", "counters") or {}):
            current, maximum = self._read_counter(char, name)
            parts.append(f"{name.capitalize()}: " + (f"{current}/{maximum}" if maximum is not None
                                                     else f"{current}"))
        return f" | {' | '.join(parts)}" if parts else ""

    def modify_vital(self, vital: str, amount: Optional[int] = None,
                     set_value: Optional[int] = None) -> Dict[str, Any]:
        """Read or change one of the campaign's counters (its ruleset's vitals)."""
        if vital == 'hp':
            return self._refuse("HP isn't used. Wounds go through gm-body.sh.")
        declared = self._kit_vitals()
        if vital not in declared:
            return self._refuse(f"'{vital}' is not a counter in this world. "
                                f"Declared: {', '.join(declared) if declared else '(none)'}")
        char = self._sheet()
        if not char:
            return {'success': False}
        char_name = sheet_mod.name(char)
        current, maximum = self._read_counter(char, vital)
        if amount is None and set_value is None:
            print(f"{char_name} - {vital}: " + (f"{current}/{maximum}" if maximum is not None
                                               else f"{current}"))
            return {'success': True, 'name': char_name, 'vital': vital,
                    'current': current, 'max': maximum}
        new_value = max(0, set_value if set_value is not None else current + amount)
        if maximum is not None:
            new_value = min(new_value, maximum)
        counters = sheet_mod.section(char, "stats").setdefault("counters", {})
        if isinstance(counters.get(vital), dict):
            counters[vital]['current'] = new_value
        else:
            counters[vital] = new_value
        if not self._save_character(char):
            return {'success': False}
        print(f"VITAL {char_name} {vital}: {current} -> {new_value}")
        print(f"{vital.capitalize()}: " + (f"{new_value}/{maximum}" if maximum is not None
                                          else f"{new_value}"))
        return {'success': True, 'name': char_name, 'vital': vital, 'previous': current,
                'current': new_value, 'max': maximum}

    # ---------- death ----------

    def kill_character(self, cause: Optional[str] = None) -> Dict[str, Any]:
        """Mark the player character dead, record it as a fact, fire on_death player."""
        char = self._sheet()
        if not char:
            return {'success': False}
        char_name = sheet_mod.name(char)
        status = sheet_mod.section(char, "status")
        status['state'] = 'dead'
        status['died_at'] = self.get_timestamp()
        if cause:
            status['cause'] = cause
        if not self._save_character(char):
            return {'success': False}
        print(f"DEATH {char_name} has died.")
        if cause:
            print(f"Cause: {cause}")
        print("STATUS: DEAD")

        from note_manager import NoteManager
        from npc_manager import DEATH_FACT_CATEGORY
        fact_id = NoteManager(self.base_dir).add_fact(
            DEATH_FACT_CATEGORY,
            f"{char_name} (the player character) died" + (f": {cause}" if cause else "."))
        from consequence_manager import ConsequenceManager
        fired = ConsequenceManager(self.base_dir).fire_event(
            'on_death', 'player', f"{char_name} (the player character) died"
            + (f" ({cause})" if cause else ""))
        return {'success': True, 'name': char_name, 'status': 'dead',
                'died_at': status['died_at'], 'cause': cause, 'fact': fact_id, 'fired': fired}

    # ---------- credits and items ----------

    def modify_credits(self, amount: Optional[int] = None) -> Dict[str, Any]:
        char = self._sheet()
        if not char:
            return {'success': False}
        char_name = sheet_mod.name(char)
        possessions = sheet_mod.section(char, "possessions")
        current = int(possessions.get('credits', 0) or 0)
        if amount is None:
            print(f"{char_name}: {current} credits")
            return {'success': True, 'name': char_name, 'credits': current}
        new = current + amount
        if new < 0:
            print(f"[WARNING] {char_name} only has {current} credits (tried to spend "
                  f"{abs(amount)}). Set to 0.")
            new = 0
        possessions['credits'] = new
        if not self._save_character(char):
            return {'success': False}
        if amount > 0:
            print(f"CREDITS_GAINED {char_name} gained {amount} credits!")
        elif amount < 0:
            print(f"CREDITS_SPENT {char_name} spent {abs(amount)} credits!")
        print(f"Credits: {new}")
        return {'success': True, 'name': char_name, 'credits_change': amount,
                'current_credits': new}

    def item(self, action: str, place: Optional[str] = None, name: Optional[str] = None,
             concealed: bool = False, note: str = "") -> Dict[str, Any]:
        """add (to gear or inventory), remove (by name, either place), move (to the
        other place), list."""
        char = self._sheet()
        if not char:
            return {'success': False}
        char_name = sheet_mod.name(char)
        try:
            if action == 'list':
                for where in sheet_mod.ITEM_PLACES:
                    listed = sheet_mod.items(char, where)
                    print(f"{where}: " + ("; ".join(sheet_mod._item_text(i) for i in listed)
                                          or "(nothing)"))
                return {'success': True, 'items': char.get('items', {})}
            if action == 'add':
                entry = sheet_mod.add_item(char, place, name, concealed, note)
                message = f"ITEM_ADDED {char_name} {place}: {sheet_mod._item_text(entry)}"
            elif action == 'remove':
                entry = sheet_mod.remove_item(char, name)
                message = f"ITEM_REMOVED {char_name} {entry['place']}: {entry['name']}"
            elif action == 'move':
                entry = sheet_mod.remove_item(char, name)
                target = place or ('inventory' if entry['place'] == 'gear' else 'gear')
                moved = {k: v for k, v in entry.items() if k != 'place'}
                if concealed:
                    moved['concealed'] = True
                sheet_mod.add_item(char, target, moved['name'], moved.get('concealed', False),
                                   moved.get('note', ''))
                message = f"ITEM_MOVED {char_name} {entry['name']}: {entry['place']} -> {target}"
            else:
                return self._refuse(f"Unknown item action '{action}': add, remove, move or list.")
        except sheet_mod.SheetError as error:
            return self._refuse(str(error))
        if not self._save_character(char):
            return {'success': False}
        print(message)
        return {'success': True, 'items': char.get('items', {})}

    def apply_loot(self, items: List[str], credits: int = 0) -> Dict[str, Any]:
        """Loot into the inventory, plus credits, in one save."""
        char = self._sheet()
        if not char:
            return {'success': False}
        possessions = sheet_mod.section(char, "possessions")
        before = int(possessions.get('credits', 0) or 0)
        for entry in items:
            sheet_mod.add_item(char, 'inventory', entry)
        if credits:
            possessions['credits'] = before + credits
        if not self._save_character(char):
            return {'success': False}
        print(f"LOOT {sheet_mod.name(char)} received (into the inventory):")
        if credits > 0:
            print(f"  + {credits} credits")
        for entry in items:
            print(f"  + {entry}")
        print(f"Credits: {before} -> {possessions.get('credits', before)}")
        return {'success': True, 'items_added': items, 'credits_added': credits,
                'total_credits': possessions.get('credits', before)}

    # ---------- conditions ----------

    def modify_condition(self, action: str, condition: Optional[str] = None) -> Dict[str, Any]:
        char = self._sheet()
        if not char:
            return {'success': False}
        char_name = sheet_mod.name(char)
        conditions = sheet_mod.section(char, "status").setdefault("conditions", [])
        if action == 'list':
            print(f"{char_name}'s Conditions:")
            for c in conditions or ["(none)"]:
                print(f"  - {c}")
            return {'success': True, 'name': char_name, 'conditions': conditions}
        if not condition:
            return self._refuse(f"Condition name required for {action}")
        if action == 'add':
            if condition.lower() in [c.lower() for c in conditions]:
                print(f"{char_name} already has condition: {condition}")
                return {'success': True, 'name': char_name, 'conditions': conditions}
            conditions.append(condition)
            message = f"CONDITION_ADDED {char_name}: {condition}"
        elif action == 'remove':
            found = next((c for c in conditions if c.lower() == condition.lower()), None)
            if found is None:
                return self._refuse(f"Condition '{condition}' not found on {char_name}")
            conditions.remove(found)
            message = f"CONDITION_REMOVED {char_name}: {found}"
        else:
            return self._refuse(f"Unknown condition action: {action}")
        if not self._save_character(char):
            return {'success': False}
        print(message)
        return {'success': True, 'name': char_name, 'conditions': conditions}


def _parse_vital_change(args):
    """(amount, set_value) for `vital <name> [<+/-N> | set N]`. Both None = read only."""
    if args.amount is None:
        return None, None
    if args.amount.lower() == 'set':
        if args.value is None:
            raise ValueError("set requires a value")
        return None, int(args.value)
    return int(args.amount.lstrip('+')), None


def _int(text: str, what: str) -> int:
    try:
        return int(str(text).replace('+', ''))
    except ValueError:
        print(f"[ERROR] Invalid {what}: {text}")
        sys.exit(1)


def main():
    import argparse
    from cli_output import wants_json, strip_json_flag, emit, emit_error

    parser = argparse.ArgumentParser(description='The player character')
    sub = parser.add_subparsers(dest='action')

    sub.add_parser('show', help='The whole sheet, readable')
    sub.add_parser('get', help='The sheet as JSON')
    p = sub.add_parser('set', help='Text fields: identity, look, personality')
    sheet_mod.add_field_flags(p)

    p = sub.add_parser('alias', help='Add or remove a shorter name the story uses')
    p.add_argument('aliases', nargs='*')
    p.add_argument('--remove', action='append', default=[])

    p = sub.add_parser('xp', help='Correct XP by hand (logged)')
    p.add_argument('amount')
    p.add_argument('--reason', default='')
    p = sub.add_parser('award', help='XP for an achievement: small, medium or large')
    p.add_argument('--size', required=True, choices=['small', 'medium', 'large'])
    p.add_argument('--reason', required=True)
    p = sub.add_parser('grow', help='Apply one level of growth that is due')
    p.add_argument('--attribute', required=True)
    p.add_argument('--skill', action='append', default=[])
    p.add_argument('--perk', nargs=2, required=True, metavar=('NAME', 'EFFECT'))
    sub.add_parser('level-check', help='XP and level')
    p = sub.add_parser('raise', help='Correction: an attribute or a skill +1')
    p.add_argument('kind', choices=['attribute', 'skill'])
    p.add_argument('target')
    p = sub.add_parser('perk', help='Correction: add or rewrite a perk')
    p.add_argument('perk')
    p.add_argument('function')

    p = sub.add_parser('vital', help="Read or change one of the campaign's counters")
    p.add_argument('vital')
    p.add_argument('amount', nargs='?')
    p.add_argument('value', nargs='?')
    p = sub.add_parser('kill', help='The player character dies')
    p.add_argument('--cause')

    p = sub.add_parser('credits', help='Show or change credits')
    p.add_argument('amount', nargs='?', help='+N or -N; without it, show them')
    p = sub.add_parser('item', help='Items: add, remove, move, list')
    p.add_argument('item_action', choices=['add', 'remove', 'move', 'list'])
    p.add_argument('words', nargs='*', help='add: gear|inventory "<item>"; remove/move: "<item>"')
    p.add_argument('--concealed', action='store_true')
    p.add_argument('--note', default='')
    p.add_argument('--to', choices=list(sheet_mod.ITEM_PLACES), help='move: where to')
    p = sub.add_parser('loot', help='Items into the inventory, plus credits')
    p.add_argument('--credits', type=int, default=0)
    p.add_argument('--items', nargs='+', default=[])
    p = sub.add_parser('condition', help='Conditions: add, remove, list')
    p.add_argument('cond_action', choices=['add', 'remove', 'list'])
    p.add_argument('condition', nargs='?')

    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help()
        sys.exit(1)
    manager = PlayerManager()

    if args.action in ('get', 'show') and json_mode or args.action == 'get':
        char = manager._load_character()
        if not char:
            sys.exit(emit_error("no character yet", json_mode=True) if json_mode else 1)
        if json_mode:
            emit(char, json_mode=True)
        else:
            print(json.dumps(char, indent=2, ensure_ascii=False))
        return
    if json_mode and args.action in ('vital', 'kill', 'award'):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            if args.action == 'vital':
                try:
                    amount, set_value = _parse_vital_change(args)
                except ValueError:
                    sys.exit(emit_error(f"invalid amount: {args.amount}", json_mode=True))
                result = manager.modify_vital(args.vital, amount, set_value)
            elif args.action == 'kill':
                result = manager.kill_character(args.cause)
            else:
                result = manager.award(args.size, args.reason)
        if result.get('success'):
            emit(result, json_mode=True)
        else:
            sys.exit(emit_error(result.get('error', f'{args.action} failed'), json_mode=True))
        return

    if args.action == 'show':
        text = manager.show_player()
        if not text:
            sys.exit(1)
        print(text)
        return
    if args.action == 'set':
        result = manager.set_fields(sheet_mod.fields_from_args(args))
    elif args.action == 'alias':
        result = manager.change_aliases(args.aliases, args.remove)
    elif args.action == 'xp':
        result = manager.award_xp(_int(args.amount, "XP amount"), "correction", args.reason)
    elif args.action == 'award':
        result = manager.award(args.size, args.reason)
    elif args.action == 'grow':
        result = manager.grow(args.attribute, args.skill, args.perk[0], args.perk[1])
    elif args.action == 'level-check':
        result = {'success': bool(manager.get_xp_status())}
    elif args.action == 'raise':
        result = manager.raise_stat(args.kind, args.target)
    elif args.action == 'perk':
        result = manager.set_perk(args.perk, args.function)
    elif args.action == 'vital':
        try:
            amount, set_value = _parse_vital_change(args)
        except ValueError:
            print(f"[ERROR] Invalid amount: {args.amount} {args.value or ''}".rstrip())
            sys.exit(1)
        result = manager.modify_vital(args.vital, amount, set_value)
    elif args.action == 'kill':
        result = manager.kill_character(args.cause)
        if result.get('success'):
            from consequence_manager import print_fired
            print_fired(result.get('fired'))
    elif args.action == 'credits':
        amount = None if args.amount is None else _int(args.amount, "credits amount")
        result = manager.modify_credits(amount)
    elif args.action == 'item':
        words = list(args.words)
        place = None
        if args.item_action == 'add':
            if len(words) != 2 or words[0] not in sheet_mod.ITEM_PLACES:
                print('[ERROR] item add gear|inventory "<item>" [--concealed] [--note "..."]')
                sys.exit(1)
            place, words = words[0], words[1:]
        elif args.item_action in ('remove', 'move') and len(words) != 1:
            print(f'[ERROR] item {args.item_action} "<item>"')
            sys.exit(1)
        result = manager.item(args.item_action, place or args.to, words[0] if words else None,
                              args.concealed, args.note)
    elif args.action == 'loot':
        if not args.items and args.credits == 0:
            print("[ERROR] Provide --items and/or --credits")
            sys.exit(1)
        result = manager.apply_loot(args.items, args.credits)
    elif args.action == 'condition':
        result = manager.modify_condition(args.cond_action, args.condition)
    else:
        parser.print_help()
        sys.exit(1)
    if not result.get('success'):
        sys.exit(1)


if __name__ == "__main__":
    main()
