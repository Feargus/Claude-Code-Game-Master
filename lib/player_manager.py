#!/usr/bin/env python3
"""The player character's sheet (character.json, in sheet.py's format): show it,
change its fields, items, credits and conditions, XP and growth, death. (The
world's own rules, Bleed and the like, are world_rules.py: gm-rule.sh.)

Creation is new_character.py; wounds, armor and cyberware are body.py.
A campaign has one player character, so no command takes a name: they all work
on the active one.
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import sheet as sheet_mod
from entity_manager import EntityManager


class PlayerManager(EntityManager):
    """The active campaign's player character."""

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self.character_file = self.campaign_dir / "character.json"

    # ---------- loading ----------

    def _load_character(self) -> dict | None:
        """The player's sheet, or None."""
        return self.json_ops.load_json("character.json") or None

    def _save_character(self, data: dict) -> bool:
        return self.json_ops.save_json("character.json", data)

    def _sheet(self) -> dict[str, Any] | None:
        char = self._load_character()
        if not char:
            print("[ERROR] No character yet. Create one: gm-player.sh create", file=sys.stderr)
        return char

    @staticmethod
    def _refuse(message: str) -> dict[str, Any]:
        print(f"[ERROR] {message}", file=sys.stderr)
        return {'success': False, 'error': message}

    # ---------- showing ----------

    def summary_line(self, char: dict[str, Any]) -> str:
        from body import summary as wound_summary
        from growth import level
        identity = char.get("identity") or {}
        who = " ".join(x for x in (identity.get("race"), identity.get("role")) if x)
        line = (f"{sheet_mod.name(char)}" + (f" - {who}" if who else "")
                + f" - Level {level(char)} (Wounds: {wound_summary(char)}, "
                  f"{self._money().capitalize()}: "
                  f"{sheet_mod.get(char, 'possessions', 'credits', 0)})")
        import world_rules
        rules = world_rules.summary(self.json_ops)
        if rules:
            line += f" | {rules}"
        if sheet_mod.is_dead(char):
            line += " | DEAD"
        if sheet_mod.conditions(char):
            line += f" | Conditions: {', '.join(sheet_mod.conditions(char))}"
        return line

    def show_player(self) -> str | None:
        char = self._sheet()
        if not char:
            return None
        return "\n".join([self.summary_line(char), *sheet_mod.describe(char)])

    # ---------- fields ----------

    def set_fields(self, values: dict[str, str]) -> dict[str, Any]:
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

    def change_aliases(self, add: list[str], remove: list[str]) -> dict[str, Any]:
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
                 reason: str = "") -> dict[str, Any]:
        """Book XP (growth.add_xp: logged in xp.log). XP only makes growth due;
        the level rises when it is applied (`grow`) at a quiet moment. Prints
        the XP in all, and a [DO] when a level has become due."""
        from growth import add_xp
        char = self._sheet()
        if not char:
            return {'success': False}
        result = add_xp(self.campaign_dir, char, int(amount), source, reason)
        if not self._save_character(char):
            return {'success': False}
        char_name = sheet_mod.name(char)
        print(f"[SUCCESS] {result['total']} XP in all")
        if result['due']:
            print(f"[DO] Growth due ({result['due']} level{'s' if result['due'] > 1 else ''}): at "
                  f"the next quiet moment (rest, sleep, time alone), gm-growth. Don't tell the player.")
        return {'success': True, 'name': char_name, 'xp_gained': int(amount),
                'current_xp': result['total'], 'growth_due': result['due']}

    def award(self, size: str, reason: str) -> dict[str, Any]:
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

    def _skill_key(self, skills: dict[str, int], name: str) -> str:
        """The skill's key on the sheet: as the sheet has it, else as the skill
        list spells it. Raises SkillError for a name that is no skill (skills.py),
        so growth can't put a skill on the sheet that no roll would ever find."""
        import skills as skill_list
        known = skill_list.find(self.campaign_dir, name)["name"]
        return next((k for k in skills if k.lower() == known.lower()), known)

    def raise_stat(self, kind: str, target: str) -> dict[str, Any]:
        """A correction: one attribute one die size up, or one skill +1 (a skill
        not on the sheet, untrained, becomes 0). Growth goes through `grow`."""
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
            try:
                key = self._skill_key(table, target.strip())
            except ValueError as error:
                return self._refuse(str(error))
            old = table.get(key)
            table[key] = new = 0 if old is None else max(old, 0) + 1
        if not self._save_character(char):
            return {'success': False}
        print(f"[SUCCESS] {key} is d{new} now" if kind == 'attribute' else
              f"[SUCCESS] {key} is {new} now")
        return {'success': True, 'kind': kind, 'name': key, 'previous': old, 'current': new}

    def set_perk(self, perk: str, function: str) -> dict[str, Any]:
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
        print(f"[SUCCESS] {'Rewrote' if replaced else 'Added'} perk {key}")
        return {'success': True, 'perk': key, 'function': function, 'replaced': replaced}

    def grow(self, attribute: str, skills: list[str], perk: str, effect: str) -> dict[str, Any]:
        """Apply one level of growth that XP has made due: exactly one attribute
        one die size up, two different skills +1 (an untrained one becomes 0) and one
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
        try:
            names = [self._skill_key(table, n) for n in names]
        except ValueError as error:
            return self._refuse(str(error))
        if names[0] == names[1]:
            return self._refuse("Growth raises exactly two different skills (--skill twice).")
        perks = stats.setdefault('perks', {})
        if not str(perk or '').strip() or not str(effect or '').strip():
            return self._refuse('Growth brings one new perk: --perk "<name>" "<what it does>".')
        if any(k.lower() == perk.strip().lower() for k in perks):
            return self._refuse(f"{sheet_mod.name(char)} has a perk '{perk}' already; "
                                f"name the new one differently.")

        attributes[key] += 1
        changes = [f"{key} d{attributes[key] - 1} -> d{attributes[key]}"]
        for skill in names:
            old = table.get(skill)
            table[skill] = 0 if old is None else max(old, 0) + 1
            changes.append(f"{skill} {old if old is not None else 'new'} -> {table[skill]}")
        perks[perk.strip()] = effect.strip()
        changes.append(f"perk {perk.strip()}: {effect.strip()}")
        sheet_mod.section(char, "progress")["level"] = level(char) + 1
        if not self._save_character(char):
            return {'success': False}
        log_growth(self.campaign_dir, char, "; ".join(changes))
        print(f"[SUCCESS] {sheet_mod.name(char)} is level {level(char)} now")
        if growth_due(char):
            print(f"[DO] Growth due ({growth_due(char)} more): run grow again with new choices.")
        return {'success': True, 'level': level(char), 'changes': changes}

    # ---------- death ----------

    def kill_character(self, cause: str | None = None) -> dict[str, Any]:
        """Mark the player character dead, record it as a fact, fire on_death player."""
        char = self._sheet()
        if not char:
            return {'success': False}
        char_name = sheet_mod.name(char)
        status = sheet_mod.section(char, "status")
        if status.get('state') == 'dead':
            return self._refuse(
                f"{char_name} is dead already" + (f" ({status['cause']})" if status.get('cause') else "")
                + ": a death is recorded once. Go on with the Death Protocol (gm-death): the "
                "hand-off to the next character.")
        status['state'] = 'dead'
        status['died_at'] = self.get_timestamp()
        if cause:
            status['cause'] = cause
        if not self._save_character(char):
            return {'success': False}
        from note_manager import NoteManager
        report = io.StringIO()                    # the fact's lines, after the first line
        with contextlib.redirect_stdout(report):
            fact_id = NoteManager(self.base_dir).add_fact(
                f"{char_name} (the player character) died" + (f": {cause}" if cause else "."),
                first_line=False)
        print(f"[SUCCESS] {char_name} is dead" + (f" ({fact_id})" if fact_id else ""))
        print(report.getvalue(), end="")
        from consequence_manager import ConsequenceManager
        fired = ConsequenceManager(self.base_dir).fire_event(
            'on_death', 'player', f"{char_name} died" + (f" ({cause})" if cause else ""))
        return {'success': True, 'name': char_name, 'status': 'dead',
                'died_at': status['died_at'], 'cause': cause, 'fact': fact_id, 'fired': fired}

    # ---------- credits and items ----------

    def _money(self) -> str:
        """The world's word for credits (world_bible.currency)."""
        from world_bible import currency
        return currency(self.json_ops)

    def modify_credits(self, amount: int | None = None) -> dict[str, Any]:
        char = self._sheet()
        if not char:
            return {'success': False}
        char_name = sheet_mod.name(char)
        possessions = sheet_mod.section(char, "possessions")
        current = int(possessions.get('credits', 0) or 0)
        if amount is None:
            print(f"{char_name}: {current} {self._money()}")
            return {'success': True, 'name': char_name, 'credits': current}
        new = current + amount
        if new < 0:
            # Refused: this used to set the credits to 0 and report the whole sum
            # as spent, so the GM narrated a purchase the character couldn't pay.
            return self._refuse(f"{char_name} has {current} {self._money()}, not the {abs(amount)} "
                                f"this would spend. Nothing was spent.")
        possessions['credits'] = new
        if not self._save_character(char):
            return {'success': False}
        print(f"[SUCCESS] {new} {self._money()} now")
        return {'success': True, 'name': char_name, 'credits_change': amount,
                'current_credits': new}

    def item(self, action: str, place: str | None = None, name: str | None = None,
             concealed: bool = False, note: str = "") -> dict[str, Any]:
        """add (to gear or inventory), remove (by name, from `place` or either), move
        (to the other place), list."""
        char = self._sheet()
        if not char:
            return {'success': False}
        try:
            if action == 'list':
                for where in sheet_mod.ITEM_PLACES:
                    listed = sheet_mod.items(char, where)
                    print(f"{where}: " + ("; ".join(sheet_mod._item_text(i) for i in listed)
                                          or "(nothing)"))
                return {'success': True, 'items': char.get('items', {})}
            if action == 'add':
                entry = sheet_mod.add_item(char, place, name, concealed, note)
                message = f"[SUCCESS] Added \"{entry['name']}\" to {place}"
            elif action == 'remove':
                entry = sheet_mod.remove_item(char, name, place)
                message = f"[SUCCESS] Removed \"{entry['name']}\" from {entry['place']}"
            elif action == 'move':
                entry = sheet_mod.remove_item(char, name)
                target = place or ('inventory' if entry['place'] == 'gear' else 'gear')
                moved = {k: v for k, v in entry.items() if k != 'place'}
                if concealed:
                    moved['concealed'] = True
                sheet_mod.add_item(char, target, moved['name'], moved.get('concealed', False),
                                   moved.get('note', ''))
                message = f"[SUCCESS] Moved \"{entry['name']}\" to {target}"
            else:
                return self._refuse(f"Unknown item action '{action}': add, remove, move or list.")
        except sheet_mod.SheetError as error:
            return self._refuse(str(error))
        if not self._save_character(char):
            return {'success': False}
        print(message)
        return {'success': True, 'items': char.get('items', {})}

    def apply_loot(self, items: list[str], credit_amount: int = 0) -> dict[str, Any]:
        """Loot into the inventory, plus credits, in one save."""
        char = self._sheet()
        if not char:
            return {'success': False}
        possessions = sheet_mod.section(char, "possessions")
        before = int(possessions.get('credits', 0) or 0)
        if credit_amount < 0:
            return self._refuse("Loot is a gain: --credits can't be negative. Spending is "
                                "gm-player.sh credits -N.")
        for entry in items:
            sheet_mod.add_item(char, 'inventory', entry)
        if credit_amount:
            possessions['credits'] = before + credit_amount
        if not self._save_character(char):
            return {'success': False}
        print("[SUCCESS] Loot into the inventory"
              + (f"; {possessions['credits']} {self._money()} now" if credit_amount else ""))
        return {'success': True, 'items_added': items, 'credits_added': credit_amount,
                'total_credits': possessions.get('credits', before)}

    # ---------- conditions ----------

    def modify_condition(self, action: str, condition: str | None = None) -> dict[str, Any]:
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


def _int(text: str, what: str) -> int:
    try:
        return int(str(text).replace('+', ''))
    except ValueError:
        print(f"[ERROR] Invalid {what}: {text}", file=sys.stderr)
        sys.exit(1)


def main():
    import argparse

    from cli_output import emit_error

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
    p = sub.add_parser('raise', help='Correction: an attribute or a skill +1')
    p.add_argument('kind', choices=['attribute', 'skill'])
    p.add_argument('target')
    p = sub.add_parser('perk', help='Correction: add or rewrite a perk')
    p.add_argument('perk')
    p.add_argument('function')

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

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)
    manager = PlayerManager()

    if args.action == 'get':
        char = manager._load_character()
        if not char:
            sys.exit(emit_error("No character yet: /create-character makes one."))
        print(json.dumps(char, indent=2, ensure_ascii=False))
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
    elif args.action == 'raise':
        result = manager.raise_stat(args.kind, args.target)
    elif args.action == 'perk':
        result = manager.set_perk(args.perk, args.function)
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
                print('[ERROR] Usage: gm-player.sh item add gear|inventory "<item>" '
                      '[--concealed] [--note "..."]', file=sys.stderr)
                sys.exit(1)
            place, words = words[0], words[1:]
        elif args.item_action == 'remove' and len(words) == 2 and words[0] in sheet_mod.ITEM_PLACES:
            place, words = words[0], words[1:]
        elif args.item_action in ('remove', 'move') and len(words) != 1:
            form = ('remove [gear|inventory] "<item>"' if args.item_action == 'remove'
                    else 'move "<item>" [--to gear|inventory]')
            print(f'[ERROR] Usage: gm-player.sh item {form} (the item\'s name in quotes)',
                  file=sys.stderr)
            sys.exit(1)
        result = manager.item(args.item_action, place or args.to, words[0] if words else None,
                              args.concealed, args.note)
    elif args.action == 'loot':
        if not args.items and args.credits == 0:
            print("[ERROR] Provide --items and/or --credits", file=sys.stderr)
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
