#!/usr/bin/env python3
"""
Create the player character from a finished interview.

Character creation is an interview, not a rules engine: the GM suggests values and
the player may choose whatever they like. This module fills in what the interview
left out with the defaults, checks only what other scripts rely on (attribute names
and die sizes, zone names), writes the whole sheet, and wires the new character in:

- it refuses to overwrite an existing character unless `replace` is set, and then
  archives the outgoing sheet to fallen/ first;
- it records the character on the campaign overview;
- for a canon character (an NPC from the campaign), it marks that NPC as the player
  so scene context stops voicing them;
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import body
import visual_appearance as va_mod
from entity_manager import EntityManager
from player_manager import PlayerManager
from skill_contest import ATTRIBUTES
from world_kit import WorldKit

DEFAULT_ATTRIBUTE = 12
DEFAULT_LUCK = 3
DEFAULT_CREDITS = 20


class CharacterError(Exception):
    """A sheet that can't be saved. The message says what to fix."""


def character_id(name: str) -> str:
    """Convert character name to file-safe ID"""
    return name.lower().replace(' ', '-').replace("'", '').replace('"', '')


def _attributes(given: Dict[str, Any]) -> Dict[str, int]:
    """All nine attributes as die sizes; any left out get the default."""
    stats = {}
    for key, value in given.items():
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


def build_character(data: Dict[str, Any], kit: WorldKit,
                    thresholds: List[int]) -> Tuple[Dict[str, Any], List[str]]:
    """The full sheet from the interview's answers, with defaults for the rest."""
    if not data.get("name"):
        raise CharacterError("Missing required field: name")
    level = int(data.get("level", 0))
    given_attributes = data.get("attributes", data.get("stats")) or {}
    luck = data.get("luck", DEFAULT_LUCK)
    if isinstance(luck, int):
        luck = {"current": luck, "max": luck}
    skills = {str(k): int(v) for k, v in (data.get("skills") or {}).items()}
    if "default" in {k.lower() for k in skills}:
        raise CharacterError("'default' is not a skill.")

    character = {
        "id": character_id(data["name"]),
        "name": data["name"],
        "race": data.get("race", ""),
        "class": data.get("class", ""),
        "level": level,
        "xp": {"current": int(data.get("xp", 0)),
               "next_level": thresholds[level] if level < len(thresholds) else 0},
        "stats": _attributes(given_attributes),
        "skills": skills,
        "luck": luck,
        **_counters(data, kit),
        "traits": _named(data.get("traits"), "traits"),
        "perks": _named(data.get("perks"), "perks"),
        "features": list(data.get("features") or []),
        "background": data.get("background", ""),
        "alignment": data.get("alignment", ""),
        "equipment": list(data.get("equipment") or []),
        "credits": int(data.get("credits", DEFAULT_CREDITS)),
        "notes": list(data.get("notes") or []),
        "conditions": list(data.get("conditions") or []),
        "visual_appearance": va_mod.normalize(data.get("visual_appearance")),
    }
    _body(character, data)

    left_out = [a for a in ATTRIBUTES if a not in {k.upper() for k in given_attributes}]
    warnings = [f"attributes set to the default d{DEFAULT_ATTRIBUTE}: {', '.join(left_out)}"] \
        if left_out else []
    return character, warnings


class CharacterCreator(EntityManager):

    def _archive(self) -> Optional[str]:
        """Archive the outgoing character.json to fallen/, the way become() does."""
        old = self.json_ops.load_json("character.json")
        if not old:
            return None
        fallen_dir = self.campaign_dir / "fallen"
        fallen_dir.mkdir(parents=True, exist_ok=True)
        slug = (old.get("name") or "former-hero").lower().replace(" ", "-")
        path = fallen_dir / f"{slug}-{old.get('id') or slug}.json"
        self.json_ops.save_json(str(path), old)
        return str(path)

    def _mark_as_pc(self, npc_name: str) -> None:
        """Flag the canon NPC as the PC so scene context stops voicing them as an NPC."""
        npcs = self.json_ops.load_json("npcs.json") or {}
        if npc_name in npcs:
            npcs[npc_name]["is_player_character"] = True
            npcs[npc_name]["is_party_member"] = False
            npcs[npc_name]["became_pc"] = True
            self.json_ops.save_json("npcs.json", npcs)

    def create(self, data: Dict[str, Any], canon: Optional[str] = None,
               replace: bool = False) -> Dict[str, Any]:
        """Build, save and wire in the new character. Returns a result dict."""
        existing = self.json_ops.load_json("character.json")
        if existing and not replace:
            who = existing.get("name", "an existing character")
            return {"success": False,
                    "error": f'this campaign already plays "{who}" — pass --replace to hand the story to someone new'}

        data = dict(data)
        if canon:
            resolved = self._find_entity_name("npcs.json", canon)
            if not resolved:
                return {"success": False, "error": f'no NPC named "{canon}" in this campaign'}
            data["name"] = resolved

        try:
            character, warnings = build_character(
                data, WorldKit(str(self.campaign_mgr.world_state_dir)),
                PlayerManager(str(self.campaign_mgr.world_state_dir))._xp_thresholds())
        except CharacterError as error:
            return {"success": False, "error": str(error)}

        archived = self._archive() if existing else None
        if not self.json_ops.save_json("character.json", character):
            return {"success": False, "error": "failed to save character.json"}

        self.json_ops.update_json("campaign-overview.json", {"current_character": character["name"]})
        if canon:
            self._mark_as_pc(character["name"])

        return {"success": True, "character": character, "warnings": warnings,
                "archived": archived}


def main():
    import argparse
    import json
    from cli_output import wants_json, strip_json_flag, emit, emit_error

    parser = argparse.ArgumentParser(description="Create the player character from a finished interview")
    parser.add_argument("character", help="the character as JSON, or --stdin to read it")
    parser.add_argument("--canon", metavar="NPC", help="the character is this NPC from the campaign")
    parser.add_argument("--replace", action="store_true",
                        help="hand the story to a new PC (archives the current one to fallen/)")
    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))

    try:
        raw = sys.stdin.read() if args.character == "--stdin" else args.character
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        sys.exit(emit_error(f"invalid JSON: {error}", json_mode))

    result = CharacterCreator().create(data, canon=args.canon, replace=args.replace)
    if not result["success"]:
        sys.exit(emit_error(result["error"], json_mode))

    character = result["character"]
    lines = [f"✓ {character['name']} enters the world (level {character['level']})"]
    lines += [f"Note: {w}" for w in result["warnings"]]
    if result["archived"]:
        lines.append(f"Archived the outgoing hero to: {result['archived']}")
    emit(character, message="\n".join(lines), json_mode=json_mode)


if __name__ == "__main__":
    main()
