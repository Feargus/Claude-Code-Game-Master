#!/usr/bin/env python3
"""
Skill contest: the one dice roll of the game.

Every roll is a contest between two sides, active and reactive. A side is either
someone who rolls a skill, or a flat DC. The GM says who rolls what; this script
looks up the numbers, rolls, and prints a single quality:

    quality = active total - reactive total + net modifiers

quality >= 0 means the active side succeeds, so an exact tie goes to the active
side. The dice themselves are never printed, only written to the campaign's log,
so the GM can't leak them into the narration.

Luck belongs to the player alone. It is spent automatically on the narrowest
possible loss, which turns that loss into the narrowest possible win.

The player's skill also learns from every contest it is rolled in (growth.py):
close results teach, and enough learnings raise the skill and grant XP. That
happens silently; the output stays the quality alone.
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from json_ops import JsonOperations

ATTRIBUTES = ("STR", "AGI", "DFT", "VIG", "LOG", "ITU", "NRV", "PRS", "EMP")
DICE_PER_ROLL = 3

REPO_MOBS = Path(__file__).parent.parent / ".claude" / "skills" / "gm-skills" / "mobs.json"
LOG_FILE = "skill-contest.log"
UNTRAINED = -3  # skill value for a skill the sheet doesn't list, unless the sheet sets a default


class ContestError(Exception):
    """A contest that can't be rolled. The message tells the GM how to fix it."""


def roll_attribute(rng, sides: int, count: int, advantages: int = 0,
                   disadvantages: int = 0) -> Dict[str, Any]:
    """Roll one attribute's dice: each advantage adds a die and drops the lowest,
    each disadvantage adds a die and drops the highest."""
    rolled = [rng.randint(1, sides) for _ in range(count + advantages + disadvantages)]
    ranked = sorted(rolled)
    kept = ranked[advantages:len(ranked) - disadvantages]
    return {"sides": sides, "rolled": rolled, "kept": kept}


def _count(edges: List[Dict[str, str]], attribute: str) -> int:
    return sum(1 for edge in edges if edge["attribute"] == attribute)


def roll_side(rng, side: Dict[str, Any]) -> int:
    """Roll a side and return its total. Fills in side["dice"] for the log."""
    if "dc" in side:
        return side["dc"]

    side["dice"] = {}
    total = side["skill_value"]
    for attribute in dict.fromkeys(side["attributes"]):  # unique, in the order given
        result = roll_attribute(
            rng,
            side["dice_sizes"][attribute],
            side["attributes"].count(attribute),
            _count(side["advantages"], attribute),
            _count(side["disadvantages"], attribute),
        )
        side["dice"][attribute] = result
        total += sum(result["kept"])
    return total


def apply_luck(quality: int, player_role: Optional[str], luck: int) -> Optional[int]:
    """The quality after a luck rescue, or None if luck doesn't apply.

    An exact tie goes to the active side, so the narrowest loss is -1 for an active
    player and 0 for a reactive one.
    """
    if luck <= 0:
        return None
    if player_role == "active" and quality == -1:
        return 0
    if player_role == "reactive" and quality == 0:
        return -1
    return None


def resolve_contest(rng, active: Dict[str, Any], reactive: Dict[str, Any],
                    mods: List[Dict[str, Any]], luck: int = 0) -> Dict[str, Any]:
    """Roll a contest. Touches no files, so it can be tested on its own."""
    active_total = roll_side(rng, active)
    reactive_total = roll_side(rng, reactive)
    raw_quality = active_total - reactive_total + sum(mod["value"] for mod in mods)

    player_role = "active" if active.get("is_player") else \
        "reactive" if reactive.get("is_player") else None
    rescued = apply_luck(raw_quality, player_role, luck)

    return {
        "active_total": active_total,
        "reactive_total": reactive_total,
        "raw_quality": raw_quality,
        "quality": raw_quality if rescued is None else rescued,
        "lucky": rescued is not None,
    }


def format_result(result: Dict[str, Any]) -> str:
    return f"quality: {result['quality']}" + (" (lucky)" if result["lucky"] else "")


def _find(table: Dict[str, Any], name: str) -> Optional[Any]:
    """Look a name up in a dict, ignoring case."""
    for key, value in table.items():
        if key.lower() == name.lower():
            return value
    return None


def find_sheet(campaign_dir: Path, name: str) -> Dict[str, Any]:
    """Find who a name refers to: the player, a named NPC, then a mob. A mob in the
    campaign's mobs.json wins over one of the same name in the repo's."""
    ops = JsonOperations(str(campaign_dir))

    character = ops.load_json("character.json") or {}
    if character.get("name", "").lower() == name.lower():
        return {**character, "is_player": True}

    for table in (ops.load_json("npcs.json"),
                  ops.load_json("mobs.json"),
                  json.loads(REPO_MOBS.read_text(encoding="utf-8"))):
        sheet = _find(table or {}, name)
        if sheet is not None:
            return sheet

    raise ContestError(f"Unknown name '{name}'. Add it to npcs.json or mobs.json, then roll again.")


def dice_sizes(sheet: Dict[str, Any], name: str, attributes: List[str]) -> Dict[str, int]:
    """The die size of each attribute. Mobs may set a `default` for the rest."""
    # NPCs and mobs keep die sizes under "attributes" (gm-npc.sh stats, gm-mob.sh);
    # the player's sheet and older entries under "stats".
    table = sheet.get("attributes") or sheet.get("stats")
    if not table:
        raise ContestError(f"{name} has no stats yet. Add them, then roll again.")

    sizes = {}
    for attribute in attributes:
        size = table.get(attribute, table.get("default"))
        if not isinstance(size, int) or size < 2:
            raise ContestError(f"{name} has no usable die for {attribute} (found {size!r}).")
        sizes[attribute] = size
    return sizes


def skill_value(sheet: Dict[str, Any], skill: str) -> Optional[int]:
    """The sheet's value for a skill, or None if the sheet doesn't list it."""
    skills = sheet.get("skills") or {}
    return None if skill.lower() == "default" else _find(skills, skill)


def untrained_value(sheet: Dict[str, Any]) -> int:
    """A skill the sheet doesn't list. Mobs and NPCs may set a `default`."""
    return (sheet.get("skills") or {}).get("default", UNTRAINED)


def _edges(name: str, attributes: List[str], pairs: Optional[List[List[str]]]) -> List[Dict[str, str]]:
    """`ATTR REASON` pairs from the command line, checked against the attributes rolled."""
    edges = [{"attribute": attribute.upper(), "label": label} for attribute, label in pairs or []]
    for edge in edges:
        if edge["attribute"] not in attributes:
            raise ContestError(
                f"{edge['attribute']} has advantage or disadvantage, but {name} isn't rolling it.")
    return edges


def build_side(campaign_dir: Path, spec: List[str], advantages: Optional[List[List[str]]],
               disadvantages: Optional[List[List[str]]]) -> Dict[str, Any]:
    """Turn `NAME SKILL ATTR ATTR ATTR` into a side that is ready to roll."""
    name, skill, *attributes = spec
    attributes = [attribute.upper() for attribute in attributes]

    for attribute in attributes:
        if attribute not in ATTRIBUTES:
            raise ContestError(f"Unknown attribute '{attribute}'. Use one of: {', '.join(ATTRIBUTES)}.")
    advantages = _edges(name, attributes, advantages)
    disadvantages = _edges(name, attributes, disadvantages)

    sheet = find_sheet(campaign_dir, name)
    sizes = dice_sizes(sheet, name, attributes)
    value = skill_value(sheet, skill)
    return {
        "name": name,
        "skill": skill,
        "skill_value": untrained_value(sheet) if value is None else value,
        "untrained": value is None,
        "attributes": attributes,
        "advantages": advantages,
        "disadvantages": disadvantages,
        "dice_sizes": sizes,
        "is_player": sheet.get("is_player", False),
    }


def build_dc(spec: List[str]) -> Dict[str, Any]:
    return {"dc": _whole_number(spec[0]), "label": spec[1]}


def _whole_number(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ContestError(f"Expected a whole number, got '{text}'.")


def spend_luck(campaign_dir: Path) -> None:
    ops = JsonOperations(str(campaign_dir))
    character = ops.load_json("character.json")
    character["luck"]["current"] -= 1
    ops.save_json("character.json", character)


def format_log_entry(time: str, active: Dict[str, Any], reactive: Dict[str, Any],
                     mods: List[Dict[str, Any]], result: Dict[str, Any]) -> str:
    """One roll as a block of labeled lines, followed by a blank line."""
    fields = {"active": active, "reactive": reactive, "mods": mods, "result": result}
    lines = [f"time: {time}"]
    lines += [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()]
    return "\n".join(lines) + "\n\n"


def write_log(campaign_dir: Path, active: Dict[str, Any], reactive: Dict[str, Any],
              mods: List[Dict[str, Any]], result: Dict[str, Any]) -> None:
    time = datetime.now().isoformat(timespec="seconds")
    with (campaign_dir / LOG_FILE).open("a", encoding="utf-8") as f:
        f.write(format_log_entry(time, active, reactive, mods, result))


def run_contest(args: argparse.Namespace, rng=random) -> Dict[str, Any]:
    """The full contest: look up both sides, roll, spend luck, write the log."""
    if args.active_dc and args.reactive_dc:
        raise ContestError("Both sides are DCs, so nothing rolls. At least one side needs a skill.")
    if args.active_dc and (args.active_adv or args.active_dis):
        raise ContestError("A DC doesn't roll, so it can't have advantage or disadvantage.")
    if args.reactive_dc and (args.reactive_adv or args.reactive_dis):
        raise ContestError("A DC doesn't roll, so it can't have advantage or disadvantage.")

    campaign_dir = CampaignManager().get_active_campaign_dir()
    if campaign_dir is None:
        raise ContestError("No active campaign.")

    active = build_dc(args.active_dc) if args.active_dc else \
        build_side(campaign_dir, args.active, args.active_adv, args.active_dis)
    reactive = build_dc(args.reactive_dc) if args.reactive_dc else \
        build_side(campaign_dir, args.reactive, args.reactive_adv, args.reactive_dis)
    if active.get("is_player") and reactive.get("is_player"):
        raise ContestError("The player can't be on both sides of a contest.")

    mods = [{"value": _whole_number(value), "label": label} for value, label in args.mod or []]

    luck = 0
    if active.get("is_player") or reactive.get("is_player"):
        character = JsonOperations(str(campaign_dir)).load_json("character.json")
        luck = (character.get("luck") or {}).get("current", 0)

    result = resolve_contest(rng, active, reactive, mods, luck)
    if result["lucky"]:
        spend_luck(campaign_dir)
    player = active if active.get("is_player") else reactive if reactive.get("is_player") else None
    if player is not None:
        result["learned"] = practise(campaign_dir, player["skill"], result["quality"])
    write_log(campaign_dir, active, reactive, mods, result)
    return result


def practise(campaign_dir: Path, skill: str, quality: int) -> list:
    """The player's skill learns from the contest (growth.learn); saves the sheet.
    Returns the skill points gained, [] for none."""
    from growth import learn
    ops = JsonOperations(str(campaign_dir))
    character = ops.load_json("character.json")
    gains = learn(campaign_dir, character, skill, quality)
    ops.save_json("character.json", character)
    return gains


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Roll a skill contest. Prints the quality; >= 0 means the active side succeeds.")

    spec = ("NAME", "SKILL", "ATTR", "ATTR", "ATTR")
    active = parser.add_mutually_exclusive_group(required=True)
    active.add_argument("--active", nargs=2 + DICE_PER_ROLL, metavar=spec)
    active.add_argument("--active-dc", nargs=2, metavar=("DC", "LABEL"))
    reactive = parser.add_mutually_exclusive_group(required=True)
    reactive.add_argument("--reactive", nargs=2 + DICE_PER_ROLL, metavar=spec)
    reactive.add_argument("--reactive-dc", nargs=2, metavar=("DC", "LABEL"))

    for flag in ("--active-adv", "--active-dis", "--reactive-adv", "--reactive-dis"):
        parser.add_argument(flag, nargs=2, action="append", metavar=("ATTR", "REASON"),
                            help="an attribute and the reason; repeatable")
    parser.add_argument("--mod", nargs=2, action="append", metavar=("VALUE", "LABEL"),
                        help="net modifier relative to the active side; repeatable")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(format_result(run_contest(args)))
    except ContestError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
