#!/usr/bin/env python3
"""
Save a new character to the active campaign's character.json.

Character creation is an interview, not a rules engine: the GM suggests values and
the player may choose whatever they like. This script only fills in what the
interview left out with the defaults, and checks what other scripts rely on
(attribute names and die sizes, zone names). The full sheet is written in one go.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

lib_path = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from campaign_manager import CampaignManager
from world_kit import WorldKit
from player_manager import PlayerManager
from skill_contest import ATTRIBUTES
import body
import visual_appearance as va_mod

DEFAULT_ATTRIBUTE = 12
DEFAULT_LUCK = 3
DEFAULT_GOLD = 20


class CharacterError(Exception):
    """A sheet that can't be saved. The message says what to fix."""


def create_character_id(name):
    """Convert character name to file-safe ID"""
    return name.lower().replace(' ', '-').replace("'", '').replace('"', '')


def _attributes(given: Dict[str, Any]) -> Dict[str, int]:
    """All nine attributes as die sizes; any left out get the default."""
    stats = {}
    for key, value in (given or {}).items():
        attribute = key.upper()
        if attribute not in ATTRIBUTES:
            raise CharacterError(f"Unknown attribute '{key}'. Use: {', '.join(ATTRIBUTES)}.")
        if not isinstance(value, int) or value < 2:
            raise CharacterError(f"{attribute} needs a whole die size of 2 or more, got {value!r}.")
        stats[attribute] = value
    return {attribute: stats.get(attribute, DEFAULT_ATTRIBUTE) for attribute in ATTRIBUTES}


def _named(given: Any, what: str) -> Dict[str, str]:
    """Traits and perks: {"name": "what it does"}."""
    if not given:
        return {}
    if not isinstance(given, dict):
        raise CharacterError(f"{what} must be an object of name: what it does.")
    return {str(name): str(function) for name, function in given.items()}


def _counters(given: Dict[str, Any], kit: WorldKit) -> Dict[str, Any]:
    """The campaign's own counters (ruleset `stat_schema.vitals`), each starting at 0
    unless the interview set it. A counter with a named_track of the same name in the
    ruleset gets that track's max."""
    tracks = {s["name"].lower(): s.get("config", {}) for s in kit.systems()
              if s.get("primitive") == "named_track"}
    counters = {}
    for name in kit.vitals():
        if name == "hp":
            continue
        value = given.get(name, 0)
        maximum = tracks.get(name.lower(), {}).get("max")
        if isinstance(value, dict):
            counters[name] = value
        elif maximum is not None:
            counters[name] = {"current": value, "max": maximum}
        else:
            counters[name] = value
    return counters


def _body(character: Dict[str, Any], data: Dict[str, Any]) -> None:
    """Unwounded zones, plus armor and cyberware from the interview. Armor is listed
    outermost first; add_armor puts each new piece outside, so the list is reversed."""
    body.body(character)
    try:
        for item in data.get("armor") or []:
            zones = [f"{zone}:{boxes}" for zone, boxes in (item.get("zones") or {}).items()]
            body.add_armor(character, item["name"], zones, int(item.get("dr", 0)))
        for item in data.get("cyberware") or []:
            body.add_cyberware(character, item["name"], item["zone"], int(item.get("boxes", 1)),
                               item.get("effect", ""))
    except (body.BodyError, KeyError) as error:
        raise CharacterError(f"Armor or cyberware: {error}")
    character["armor"] = list(reversed(character.get("armor", [])))


def build_character(data: Dict[str, Any], kit: WorldKit, thresholds: List[int]) -> Tuple[Dict[str, Any], List[str]]:
    """The full sheet from the interview's answers, with defaults for the rest."""
    if not data.get("name"):
        raise CharacterError("Missing required field: name")
    level = int(data.get("level", 0))
    given_attributes = data.get("attributes", data.get("stats")) or {}
    luck = data.get("luck", DEFAULT_LUCK)
    if isinstance(luck, int):
        luck = {"current": luck, "max": luck}

    character = {
        "id": create_character_id(data["name"]),
        "name": data["name"],
        "race": data.get("race", ""),
        "class": data.get("class", ""),
        "level": level,
        "xp": {"current": int(data.get("xp", 0)),
               "next_level": thresholds[level] if level < len(thresholds) else 0},
        "stats": _attributes(given_attributes),
        "skills": {str(k): int(v) for k, v in (data.get("skills") or {}).items()},
        "luck": luck,
        **_counters(data, kit),
        "traits": _named(data.get("traits"), "traits"),
        "perks": _named(data.get("perks"), "perks"),
        "features": list(data.get("features") or []),
        "background": data.get("background", ""),
        "alignment": data.get("alignment", ""),
        "equipment": list(data.get("equipment") or []),
        "gold": int(data.get("gold", DEFAULT_GOLD)),
        "notes": list(data.get("notes") or []),
        "conditions": list(data.get("conditions") or []),
        "visual_appearance": va_mod.normalize(data.get("visual_appearance")),
    }
    _body(character, data)

    warnings = []
    if "default" in character["skills"]:
        raise CharacterError("'default' is not a skill.")
    left_out = [a for a in ATTRIBUTES if a not in {k.upper() for k in given_attributes}]
    if left_out:
        warnings.append(f"attributes set to the default d{DEFAULT_ATTRIBUTE}: {', '.join(left_out)}")
    return character, warnings


def save_character(character_data):
    """Save character to campaign's character.json file"""
    campaign_mgr = CampaignManager()
    campaign_dir = campaign_mgr.get_active_campaign_dir()
    if campaign_dir is None:
        return {"error": "No active campaign."}

    try:
        character, warnings = build_character(
            character_data, WorldKit(), PlayerManager()._xp_thresholds())
    except CharacterError as error:
        return {"error": str(error)}

    file_path = campaign_dir / "character.json"
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(character, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"error": f"Failed to save character: {str(e)}"}

    return {
        "success": True,
        "character_id": character["id"],
        "file_path": str(file_path),
        "campaign": campaign_mgr.get_active(),
        "character": character,
        "warnings": warnings,
    }


def main():
    """CLI interface for character saving"""
    if len(sys.argv) < 2:
        print("Usage: save_character.py '<character_json>' or save_character.py --stdin")
        print('Example: save_character.py \'{"name":"Mara","race":"augmented human","class":"courier",'
              '"attributes":{"AGI":14,"ITU":13},"skills":{"Athletics":2,"Piloting":2}}\'')
        sys.exit(1)

    try:
        raw = sys.stdin.read().strip() if sys.argv[1] == '--stdin' else sys.argv[1]
        character_data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {str(e)}"}))
        sys.exit(1)

    result = save_character(character_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
