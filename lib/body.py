#!/usr/bin/env python3
"""
Wounds, armor and cyberware on the player's sheet. Replaces HP and AC.

Everything that can break is a row of boxes. A wound fills a box; a full row stops
working. The sheet stores how many boxes are filled.

- body:      one row of 4 per zone. 1 bruise, 2 injured, 3 nearly unusable, 4 destroyed.
- armor:     items with boxes per zone. Each box absorbs one wound and is used up.
             Layers are listed outermost first, and the outermost absorbs first.
- cyberware: items in a zone, with boxes of their own. A wound that gets past the
             armor lands at random in any empty box of the zone, flesh or chrome.
             Chrome boxes only decide whether the chrome works, never the flesh effects.

The GM says where a hit lands and how many wounds it deals; this script does the counting.
"""

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from json_ops import JsonOperations

ZONES = ("head", "chest", "groin", "left_arm", "right_arm", "left_leg", "right_leg")
FATAL = ("head", "chest", "groin")
FLESH_BOXES = 4
EFFECTS = {1: "bruise, no effect", 2: "injured", 3: "nearly unusable", 4: "destroyed"}


class BodyError(Exception):
    """A change that can't be made. The message tells the GM how to fix it."""


def zone_key(text: str) -> str:
    """'Left arm' and 'left_arm' both mean left_arm."""
    zone = text.strip().lower().replace(" ", "_")
    if zone not in ZONES:
        raise BodyError(f"Unknown zone '{text}'. Use one of: {', '.join(ZONES)}.")
    return zone


def body(sheet: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The sheet's body section, with every zone present."""
    section = sheet.setdefault("body", {})
    for zone in ZONES:
        section.setdefault(zone, {"wounds": 0})
    return section


def _left(row: Dict[str, int]) -> int:
    return row["boxes"] - row["damage"]


def _find_item(sheet: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for item in sheet.get("armor", []) + sheet.get("cyberware", []):
        if item["name"].lower() == name.lower():
            return item
    return None


def _flesh_event(zone: str, wounds: int) -> str:
    effect = "dead" if wounds == FLESH_BOXES and zone in FATAL else EFFECTS[wounds]
    return f"{zone}: wound {wounds} of {FLESH_BOXES}, {effect}"


def hit(sheet: Dict[str, Any], zone: str, wounds: int, rng=random) -> List[str]:
    """Deal wounds to a zone: DR first, then armor from the outside in, then a random
    empty box of flesh or chrome. Returns what happened, one line each."""
    zone = zone_key(zone)
    events = []
    covering = [item for item in sheet.get("armor", []) if zone in item["zones"]]

    reduced = min(wounds, sum(item.get("dr", 0) for item in covering))
    if reduced:
        events.append(f"DR stopped {reduced} wound{'s' if reduced > 1 else ''}")
    wounds -= reduced

    part = body(sheet)[zone]
    for _ in range(wounds):
        layer = next((item for item in covering if _left(item["zones"][zone])), None)
        if layer:
            row = layer["zones"][zone]
            row["damage"] += 1
            events.append(f"{layer['name']} absorbed a wound on the {zone}, {_left(row)} left there")
            continue

        if part["wounds"] >= FLESH_BOXES:
            events.append(f"{zone} is already destroyed")
            break

        chrome = [item for item in sheet.get("cyberware", [])
                  if item["zone"] == zone and _left(item)]
        boxes = [None] * (FLESH_BOXES - part["wounds"]) + \
                [item for item in chrome for _ in range(_left(item))]
        target = rng.choice(boxes)
        if target is None:
            part["wounds"] += 1
            events.append(_flesh_event(zone, part["wounds"]))
        else:
            target["damage"] += 1
            stopped = ", stopped working" if not _left(target) else ""
            events.append(f"{target['name']} took the wound, {_left(target)} left{stopped}")
    return events


def heal(sheet: Dict[str, Any], zone: str, wounds: int) -> List[str]:
    zone = zone_key(zone)
    part = body(sheet)[zone]
    if part["wounds"] >= FLESH_BOXES:
        raise BodyError(f"The {zone} is destroyed and never heals. It needs a replacement.")
    part["wounds"] = max(0, part["wounds"] - wounds)
    return [f"{zone}: {part['wounds']} wound{'s' if part['wounds'] != 1 else ''} left"]


def repair(sheet: Dict[str, Any], name: str) -> List[str]:
    """Restore every box of a piece of armor or cyberware."""
    item = _find_item(sheet, name)
    if item is None:
        raise BodyError(f"No armor or cyberware called '{name}'.")
    for row in item["zones"].values() if "zones" in item else [item]:
        row["damage"] = 0
    return [f"{item['name']} repaired"]


def note(sheet: Dict[str, Any], zone: str, text: str) -> List[str]:
    """The story of a zone's wounds, e.g. "lost at the elbow". Empty text clears it."""
    zone = zone_key(zone)
    part = body(sheet)[zone]
    if text:
        part["note"] = text
    else:
        part.pop("note", None)
    return [f"{zone}: note {'set' if text else 'cleared'}"]


def _whole_number(text: str, smallest: int) -> int:
    try:
        number = int(text)
    except ValueError:
        raise BodyError(f"Expected a whole number, got '{text}'.")
    if number < smallest:
        raise BodyError(f"Expected {smallest} or more, got {number}.")
    return number


def add_armor(sheet: Dict[str, Any], name: str, zones: List[str], dr: int = 0) -> List[str]:
    """Wear armor. `zones` are ZONE:BOXES pairs. New armor goes on the outside."""
    if _find_item(sheet, name):
        raise BodyError(f"'{name}' is already on the sheet. Remove it first, or pick another name.")
    rows = {}
    for pair in zones:
        zone, _, boxes = pair.rpartition(":")
        if not zone:
            raise BodyError(f"Expected ZONE:BOXES, got '{pair}'.")
        rows[zone_key(zone)] = {"boxes": _whole_number(boxes, 1), "damage": 0}
    item = {"name": name, "dr": dr, "zones": rows}
    sheet.setdefault("armor", []).insert(0, item)
    return [f"{name} worn on the {', '.join(rows)}"]


def add_cyberware(sheet: Dict[str, Any], name: str, zone: str, boxes: int,
                  effect: str = "") -> List[str]:
    if _find_item(sheet, name):
        raise BodyError(f"'{name}' is already on the sheet. Remove it first, or pick another name.")
    item = {"name": name, "zone": zone_key(zone), "boxes": boxes, "damage": 0, "effect": effect}
    sheet.setdefault("cyberware", []).append(item)
    return [f"{name} installed in the {item['zone']}"]


def remove(sheet: Dict[str, Any], name: str) -> List[str]:
    item = _find_item(sheet, name)
    if item is None:
        raise BodyError(f"No armor or cyberware called '{name}'.")
    section = "armor" if "zones" in item else "cyberware"
    sheet[section].remove(item)
    return [f"{item['name']} removed"]


# --- The picture ---

LABELS = {"head": "head", "chest": "chest", "groin": "groin", "left_arm": "l.arm",
          "right_arm": "r.arm", "left_leg": "l.leg", "right_leg": "r.leg"}


def _boxes(filled: int, size: int, full: str, empty: str) -> str:
    return full * filled + empty * (size - filled)


def cell(sheet: Dict[str, Any], zone: str) -> str:
    """One zone: armor bars, three wound circles (or a cross), chrome diamonds.
    A filled symbol always means hit."""
    parts = [LABELS[zone]]
    armor = "".join(_boxes(item["zones"][zone]["damage"], item["zones"][zone]["boxes"], "▮", "▯")
                    for item in sheet.get("armor", []) if zone in item["zones"])
    if armor:
        parts.append(armor)
    wounds = body(sheet)[zone]["wounds"]
    parts.append("✖" if wounds >= FLESH_BOXES else _boxes(wounds, FLESH_BOXES - 1, "●", "○"))
    chrome = "".join(_boxes(item["damage"], item["boxes"], "◆", "◇")
                     for item in sheet.get("cyberware", []) if item["zone"] == zone)
    if chrome:
        parts.append(chrome)
    return " ".join(parts)


def picture(sheet: Dict[str, Any]) -> str:
    """Three lines, stacked roughly like a body."""
    rows = [("left_arm", "chest", "right_arm"), ("left_leg", "groin", "right_leg")]
    cells = [[cell(sheet, zone) for zone in row] for row in rows]
    left = max(len(row[0]) for row in cells)
    middle = max(len(row[1]) for row in cells)
    lines = [" " * (left + 3) + cell(sheet, "head")]
    lines += [f"{a:<{left}}   {b:<{middle}}   {c}".rstrip() for a, b, c in cells]
    return "\n".join(lines)


def details(sheet: Dict[str, Any]) -> List[str]:
    """Everything the picture leaves out: notes, and what each item is."""
    lines = [f"{zone}: {part['note']}" for zone, part in body(sheet).items() if part.get("note")]
    for item in sheet.get("armor", []):
        rows = ", ".join(f"{zone} {_left(row)}/{row['boxes']}" for zone, row in item["zones"].items())
        dr = f", DR {item['dr']}" if item.get("dr") else ""
        lines.append(f"armor: {item['name']} ({rows}{dr})")
    for item in sheet.get("cyberware", []):
        state = "working" if _left(item) else "broken"
        effect = f", {item['effect']}" if item.get("effect") else ""
        lines.append(f"cyberware: {item['name']} ({item['zone']}, {_left(item)}/{item['boxes']}, "
                     f"{state}{effect})")
    return lines


def show(sheet: Dict[str, Any]) -> str:
    return "\n".join([picture(sheet), *details(sheet)])


# --- The command line ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wounds, armor and cyberware of the player.")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show")
    for action in ("hit", "heal"):
        p = sub.add_parser(action)
        p.add_argument("zone")
        p.add_argument("wounds", nargs="?", default="1")
    p = sub.add_parser("note")
    p.add_argument("zone")
    p.add_argument("text")
    p = sub.add_parser("armor")
    p.add_argument("name")
    p.add_argument("zones", nargs="+", metavar="ZONE:BOXES")
    p.add_argument("--dr", default="0")
    p = sub.add_parser("cyberware")
    p.add_argument("name")
    p.add_argument("zone")
    p.add_argument("boxes")
    p.add_argument("--effect", default="")
    for action in ("repair", "remove"):
        sub.add_parser(action).add_argument("name")
    return parser


def run(args: argparse.Namespace, rng=random) -> str:
    """Load the sheet, make the change, save, and return what to print."""
    campaign_dir = CampaignManager().get_active_campaign_dir()
    if campaign_dir is None:
        raise BodyError("No active campaign.")
    ops = JsonOperations(str(campaign_dir))
    sheet = ops.load_json("character.json")
    if not sheet:
        raise BodyError("No character yet.")

    if args.action == "show":
        return show(sheet)
    if args.action == "hit":
        events = hit(sheet, args.zone, _whole_number(args.wounds, 1), rng)
    elif args.action == "heal":
        events = heal(sheet, args.zone, _whole_number(args.wounds, 1))
    elif args.action == "note":
        events = note(sheet, args.zone, args.text)
    elif args.action == "armor":
        events = add_armor(sheet, args.name, args.zones, _whole_number(args.dr, 0))
    elif args.action == "cyberware":
        events = add_cyberware(sheet, args.name, args.zone, _whole_number(args.boxes, 1),
                               args.effect)
    elif args.action == "repair":
        events = repair(sheet, args.name)
    else:
        events = remove(sheet, args.name)

    ops.save_json("character.json", sheet)
    return "\n".join([*events, "", picture(sheet)])


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(run(args))
    except BodyError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
