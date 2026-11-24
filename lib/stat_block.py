#!/usr/bin/env python3
"""Stat blocks for NPCs and mobs: what the dice script rolls for anyone but the player.

The stat parts of a sheet (sheet.py), read by skill_contest.py and the combat
tracker:

    "stats":    {"attributes": {"STR": 12, "AGI": 11, "default": 10},  default = the rest
                 "skills": {"Handguns": 4, "Guard": 3, "default": 0}}  default = not listed
    "body":     {"wounds": 3}                       how many take them out
    "identity": {"background": "one line"}          a mob's note

A skill not listed counts the block's `default` if it has one, else 0 for the
common skills (the Common column of the gm-skills index) and −3 for the rest
(skill_contest.untrained_value). A weakness in a common skill is listed
explicitly, at any value. Player sheets are different: their common skills are
written onto the sheet at creation (new_character.py).

`gm-npc.sh stats` writes it onto an NPC in npcs.json, `gm-mob.sh` onto a mob in the
campaign's mobs.json (the repo's mobs.json in gm-skills is the scale, read-only).
Everything is checked before it is saved; the GM never edits these files by hand.

    gm-mob.sh list
    gm-mob.sh show "<mob>"
    gm-mob.sh add "<mob>" --note "..." [--attr STR=14]... [--skill Brawling=3]... [--wounds N]
    gm-mob.sh stats "<mob>" [--attr ...] [--skill ...] [--remove-skill X] [--wounds N] [--note ...]
"""

import difflib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import skills as skill_list
from sheet import ATTRIBUTES, SheetError, check_die
from sheet import check as sheet_check
from skills import IMPROVISED_FILE

REPO_MOBS = skill_list.SKILLS_DIR / "mobs.json"
COMMON_VALUE = 0   # a common skill an NPC or mob doesn't list, unless it has a default
USUAL_DIE = (4, 24)  # outside: a warning, not a refusal (power creep is fine)


class StatError(ValueError):
    """A stat block that can't be saved. The message says how to fix it."""


def canon_skills() -> list[str]:
    """The canon skills, in the order of the gm-skills index (skills.py reads it)."""
    return [skill["name"] for skill in skill_list.canon().values()]


def common_skills() -> list[str]:
    """The skills every new character starts with at 0 or more: the index rows
    marked in the Common column."""
    return [skill["name"] for skill in skill_list.canon().values() if skill["common"]]


def parse_pairs(pairs, what: str) -> dict[str, int]:
    """["STR=12", "Long guns=3"] -> {"STR": 12, "Long guns": 3}."""
    out = {}
    for raw in pairs or []:
        name, sep, value = str(raw).partition("=")
        name = name.strip()
        if not sep or not name:
            raise StatError(f"--{what} takes NAME=VALUE, e.g. --{what} "
                            f"{'STR=12' if what == 'attr' else 'Handguns=3'}; got '{raw}'.")
        try:
            out[name] = int(value.strip())
        except ValueError:
            raise StatError(f"--{what} {name}: the value is a whole number, not '{value.strip()}'.") from None
    return out


def _attribute_key(name: str) -> str:
    key = name.strip().upper()
    if key == "DEFAULT":
        return "default"
    if key not in ATTRIBUTES:
        raise StatError(f"Unknown attribute '{name}'. Use one of: {', '.join(ATTRIBUTES)} "
                        f"(or default).")
    return key


def _skill_key(name: str, known: list[str]) -> str:
    """The skill's canon spelling if it is a canon skill, else the name as given."""
    if name.strip().lower() == "default":
        return "default"
    return next((k for k in known if k.lower() == name.strip().lower()), name.strip())


def check(block: dict[str, Any], campaign_dir: Path | None = None) -> list[str]:
    """Warnings for a block that is valid but unusual. Raises StatError if invalid."""
    warnings = []
    attributes = (block.get("stats") or {}).get("attributes") or {}
    for key, size in attributes.items():
        try:
            check_die(key, size)
        except SheetError as error:
            raise StatError(str(error)) from error
        if not USUAL_DIE[0] <= size <= USUAL_DIE[1]:
            warnings.append(f"{key} d{size} is outside the usual d{USUAL_DIE[0]}–d{USUAL_DIE[1]} "
                            f"(fine if meant).")
    known = canon_skills()
    table = skill_list.table(campaign_dir)       # the same list the dice script checks
    for name, value in ((block.get("stats") or {}).get("skills") or {}).items():
        if not isinstance(value, int):
            raise StatError(f"{name}: a skill value is a whole number, not {value!r}.")
        entry = table.get(" ".join(name.split()).lower())
        if name == "default" or (entry and entry["status"] != "banned"):
            continue
        if entry:
            warnings.append(f"'{name}' is banned in this campaign ({IMPROVISED_FILE}): "
                            f"it can't be rolled.")
            continue
        close = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
        hint = f" Did you mean {close[0]}?" if close else ""
        warnings.append(f"'{name}' is not a canon skill.{hint} It can't be rolled until it is a "
                        f"skill: if it is improvised, add it to the campaign's {IMPROVISED_FILE} "
                        f"(gm-skills, Improvised skills).")
    wounds = (block.get("body") or {}).get("wounds")
    if wounds is not None and (not isinstance(wounds, int) or wounds < 1):
        raise StatError(f"wounds: at least 1, not {wounds!r}.")
    return warnings


def merged(entry: dict[str, Any], attrs=None, skills=None, remove_skills=None,
           wounds: int | None = None, note: str | None = None) -> dict[str, Any]:
    """A copy of the sheet `entry` with the changes merged in. Raises StatError."""
    known = canon_skills()
    out = json.loads(json.dumps(entry or {}))
    stats = out.setdefault("stats", {})
    block_attrs = dict(stats.get("attributes") or {})
    for name, size in (attrs or {}).items():
        block_attrs[_attribute_key(name)] = size
    block_skills = dict(stats.get("skills") or {})
    for name in remove_skills or []:
        key = next((k for k in block_skills if k.lower() == name.strip().lower()), None)
        if key is None:
            raise StatError(f"There is no skill '{name}' to remove.")
        del block_skills[key]
    for name, value in (skills or {}).items():
        key = _skill_key(name, known)
        old = next((k for k in block_skills if k.lower() == key.lower()), None)
        if old:
            del block_skills[old]
        block_skills[key] = value
    if block_attrs:
        stats["attributes"] = block_attrs
    if block_skills or "skills" in stats:
        stats["skills"] = block_skills
    if not stats:
        del out["stats"]
    if wounds is not None:
        out.setdefault("body", {})["wounds"] = wounds
    if note is not None:
        out.setdefault("identity", {})["background"] = note
    return out


def is_sketch(entry: dict[str, Any]) -> bool:
    """A mob without attributes or wounds yet: it can't be rolled or fought."""
    return not ((entry.get("stats") or {}).get("attributes")
                and "wounds" in (entry.get("body") or {}))


def describe(name: str, entry: dict[str, Any]) -> str:
    """One readable block."""
    stats = entry.get("stats") or {}
    attrs = stats.get("attributes") or {}
    order = [a for a in ATTRIBUTES if a in attrs] + (["default"] if "default" in attrs else [])
    skills = stats.get("skills") or {}
    lines = [f"{name}:"]
    note = (entry.get("identity") or {}).get("background")
    if note:
        lines.append(f"  {note}")
    lines.append("  attributes: " + (", ".join(f"{a} d{attrs[a]}" for a in order) or "(none: can't roll)"))
    lines.append("  skills: " + (", ".join(f"{k} {v}" for k, v in skills.items()) or "(none listed)"))
    if "default" in skills:
        lines.append(f"  not listed: {skills['default']} (the default, common skills included)")
    else:
        lines.append(f"  not listed: common skills {COMMON_VALUE}, the rest untrained −3")
    lines.append(f"  wounds: {(entry.get('body') or {}).get('wounds', '(not set)')}")
    lines += [f"  {line}" for line in not_ready(name, entry)]
    return "\n".join(lines)


def saved_lines(key: str, entry: dict, warnings, create: bool) -> list[str]:
    """After a mob is added or its stats set: the one line, then what it still
    needs ([NOTE]: a sketch may wait) and what looks wrong ([CHECK])."""
    if create and is_sketch(entry):               # a roll will say what it needs
        lines = [f"[SUCCESS] Added mob {key} (sketch)"]
    else:
        lines = [f"[SUCCESS] {'Added' if create else 'Updated'} mob {key}"]
        lines += [f"[NOTE] {line}" for line in not_ready(key, entry)]
    return lines + [f"[CHECK] {w}" for w in warnings]


def not_ready(name: str, entry: dict, tool: str = "gm-mob.sh") -> list[str]:
    """What a sheet still needs before it is rolled or fought (attributes, wounds),
    as one line with the command; [] if nothing. A sketch may lack them on purpose."""
    attrs = (entry.get("stats") or {}).get("attributes") or {}
    missing = [what for what, have in (("attributes", attrs),
                                       ("wounds", "wounds" in (entry.get("body") or {})))
               if not have]
    if not missing:
        return []
    return [f"not ready: give it {' and '.join(missing)} before it is rolled or fought "
            f"({tool} stats \"{name}\" --attr ... --wounds N)"]


# ---------- mobs ----------

class Mobs:
    """The campaign's mobs.json, checked; the repo's mobs are the scale."""

    def __init__(self, world_state_dir: str = None):
        from entity_manager import EntityManager
        base = EntityManager(world_state_dir)
        if base.campaign_dir is None:
            raise StatError("No active campaign.")
        self.campaign_dir = Path(base.campaign_dir)
        self.json_ops = base.json_ops

    def campaign(self) -> dict[str, Any]:
        return self.json_ops.load_json("mobs.json") or {}

    @staticmethod
    def repo() -> dict[str, Any]:
        return json.loads(REPO_MOBS.read_text(encoding="utf-8"))

    def _key(self, mobs: dict[str, Any], name: str) -> str | None:
        return next((k for k in mobs if k.lower() == name.strip().lower()), None)

    def find(self, name: str) -> tuple[str, dict[str, Any], str]:
        """(key, entry, where) for a mob, campaign first; raises StatError."""
        for where, mobs in (("campaign", self.campaign()), ("repo", self.repo())):
            key = self._key(mobs, name)
            if key:
                return key, mobs[key], where
        raise StatError(f"No mob '{name}'. gm-mob.sh list shows them.")

    def _refuse_taken(self, name: str) -> list[str]:
        """A mob's name must not be the player's or an NPC's: the dice script looks
        those up first, so the mob would never be rolled."""
        from world_ids import WorldIds
        cid, _ = WorldIds(self.json_ops).resolve_as(name, ("player", "npc"))
        if cid:
            raise StatError(f"'{name}' is {cid}: the dice script would roll them, never "
                            f"the mob. Give the mob another name.")
        warnings = []
        if self._key(self.repo(), name):
            warnings.append(f"'{name}' also names one of the repo's example mobs; this "
                            f"campaign's version wins.")
        return warnings

    def save(self, name: str, entry: dict[str, Any], create: bool) -> list[str]:
        mobs = self.campaign()
        key = self._key(mobs, name)
        if create and key:
            raise StatError(f"The mob '{key}' exists already; change it with gm-mob.sh stats.")
        if not create and not key:
            if self._key(self.repo(), name):
                raise StatError(f"'{name}' is one of the repo's example mobs, which stay as "
                                f"they are. Add a campaign version: gm-mob.sh add.")
            raise StatError(f"No mob '{name}' in this campaign. Add it: gm-mob.sh add.")
        warnings = self._refuse_taken(name) if create else []
        if create and not str((entry.get("identity") or {}).get("background") or "").strip():
            raise StatError("A new mob needs --note: one line on what it is.")
        warnings += check(entry, self.campaign_dir)
        entry.setdefault("identity", {})["name"] = key or name.strip()
        try:
            sheet_check(entry, "mob")
        except SheetError as error:
            raise StatError(str(error)) from error
        mobs[key or name.strip()] = entry
        self.json_ops.save_json("mobs.json", mobs)
        return warnings


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Mobs: interchangeable enemies with stats")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("list")
    p = sub.add_parser("show")
    p.add_argument("name")
    for action in ("add", "stats"):
        p = sub.add_parser(action)
        p.add_argument("name")
        p.add_argument("--attr", action="append", default=[], help="ATTR=DIE, e.g. STR=12; default=10 for the rest")
        p.add_argument("--skill", action="append", default=[], help="Skill=VALUE, e.g. Brawling=3")
        p.add_argument("--remove-skill", dest="remove_skill", action="append", default=[])
        p.add_argument("--wounds", type=int)
        p.add_argument("--note")
    args = parser.parse_args()
    try:
        mobs = Mobs()
        if args.action == "list":
            campaign = mobs.campaign()
            print("This campaign's mobs:" if campaign else "This campaign has no mobs of its own.")
            for key, entry in campaign.items():
                print(describe(key, entry))
            print("\nThe repo's example mobs (the scale for new ones):")
            for key, entry in mobs.repo().items():
                print(describe(key, entry))
        elif args.action == "show":
            key, entry, where = mobs.find(args.name)
            print(describe(key, entry) + ("" if where == "campaign" else "\n  (a repo example mob)"))
        elif args.action in ("add", "stats"):
            create = args.action == "add"
            current = {} if create else mobs.campaign().get(
                mobs._key(mobs.campaign(), args.name) or "", {})
            entry = merged(current, parse_pairs(args.attr, "attr"), parse_pairs(args.skill, "skill"),
                           args.remove_skill, args.wounds, args.note)
            warnings = mobs.save(args.name, entry, create)
            key = mobs._key(mobs.campaign(), args.name)
            print("\n".join(saved_lines(key, entry, warnings, create)))
        else:
            parser.print_help()
            return 1
    except StatError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
