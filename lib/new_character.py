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
- the ids follow the people (handover.py): the outgoing character becomes an NPC
  with what they knew, and a canon character (an NPC from the campaign) takes what
  the NPC knew as the player's.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import body
import sheet as sheet_mod
from entity_manager import EntityManager
from skill_contest import ATTRIBUTES
from world_kit import WorldKit
from handover import hand_over
from stat_block import canon_skills, common_skills

DEFAULT_ATTRIBUTE = 12
DEFAULT_LUCK = 7
DEFAULT_CREDITS = 20


class CharacterError(Exception):
    """A sheet that can't be saved. The message says what to fix."""


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


def _skills(given: Dict[str, Any], untrained: List[str]) -> Dict[str, int]:
    """The interview's skills, plus every common skill at 0 unless it is listed in
    `untrained` (a pacifist who never threw a punch). A skill left off the sheet is
    untrained; the sheet never holds a negative value."""
    canon = {name.lower(): name for name in canon_skills()}
    skills = {}
    for name, value in given.items():
        name = canon.get(str(name).lower(), str(name))
        if name.lower() == "default":
            raise CharacterError("'default' is not a skill.")
        if not isinstance(value, int) or value < 0:
            raise CharacterError(f"{name}: a skill on the sheet is a whole number of 0 or more, "
                                 f"not {value!r}. Leave an untrained skill off the sheet.")
        skills[name] = value
    common = common_skills()
    if not isinstance(untrained, list):
        raise CharacterError('"untrained" is a list of common skills the character lacks.')
    dropped = set()
    for name in untrained:
        match = next((c for c in common if c.lower() == str(name).lower()), None)
        if match is None:
            raise CharacterError(f"'{name}' is not a common skill, so it is untrained anyway unless "
                                 f"it is listed under skills. Common: {', '.join(common)}.")
        if match in skills:
            raise CharacterError(f"{match} is both under skills and untrained.")
        dropped.add(match)
    for name in common:
        if name not in skills and name not in dropped:
            skills[name] = 0
    return skills


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


def _body(character: Dict[str, Any], given: Dict[str, Any]) -> None:
    """Unwounded zones, plus armor and cyberware from the interview. The interview
    gives armor as {"name", "zones": {zone: boxes}, "dr"?}, outermost first; add_armor
    puts each new piece outside, so they are added in reverse."""
    character["body"] = {"zones": {}}
    body.body(character)
    try:
        for piece in reversed(given.get("armor") or []):
            zones = [f"{zone}:{boxes}" for zone, boxes in (piece.get("zones") or {}).items()]
            body.add_armor(character, piece["name"], zones, int(piece.get("dr", 0)))
        for piece in given.get("cyberware") or []:
            body.add_cyberware(character, piece["name"], piece["zone"], int(piece.get("boxes", 1)),
                               piece.get("effect", ""))
    except (body.BodyError, KeyError, TypeError) as error:
        raise CharacterError(f"Armor or cyberware: {error}")


def build_character(data: Dict[str, Any], kit: WorldKit) -> Tuple[Dict[str, Any], List[str]]:
    """The full sheet (sheet.py) from the interview's answers, with defaults for the
    rest. The answers come in the sheet's sections; `untrained` lists common skills
    the character lacks."""
    data = dict(data)
    untrained = data.pop("untrained", None) or []
    identity = dict(data.get("identity") or {})
    if not identity.get("name"):
        raise CharacterError("Missing required field: identity.name")
    stats = dict(data.get("stats") or {})
    given_attributes = stats.get("attributes") or {}
    luck = stats.get("luck", DEFAULT_LUCK)
    if isinstance(luck, int):
        luck = {"current": luck, "max": luck}
    progress = dict(data.get("progress") or {})
    level = int(progress.get("level", 0))

    character = sheet_mod.merge(data, {
        "identity": identity,
        "stats": {"attributes": _attributes(given_attributes),
                  "skills": _skills(stats.get("skills") or {}, untrained),
                  "traits": _named(stats.get("traits"), "traits"),
                  "perks": _named(stats.get("perks"), "perks"),
                  "luck": luck,
                  "counters": _counters(stats.get("counters") or {}, kit)},
        "progress": {"level": level, "xp": int(progress.get("xp", 0)),
                     "practice": progress.get("practice") or {}},
        "possessions": {"credits": DEFAULT_CREDITS, **(data.get("possessions") or {})},
        "status": {"state": "alive", "conditions": [], **(data.get("status") or {})},
    })
    if not character["stats"]["counters"]:
        del character["stats"]["counters"]
    try:
        character["items"] = {place: [sheet_mod.item(i) for i in (data.get("items") or {}).get(place) or []]
                              for place in sheet_mod.ITEM_PLACES}
        _body(character, data.get("body") or {})
        sheet_mod.check(character, "player")
    except sheet_mod.SheetError as error:
        raise CharacterError(str(error))

    left_out = [a for a in ATTRIBUTES if a not in {k.upper() for k in given_attributes}]
    warnings = [f"attributes set to the default d{DEFAULT_ATTRIBUTE}: {', '.join(left_out)}"] \
        if left_out else []
    return character, warnings


class CharacterCreator(EntityManager):

    def _archive(self, old: Dict[str, Any]) -> str:
        """Archive the outgoing character.json to fallen/."""
        fallen_dir = self.campaign_dir / "fallen"
        fallen_dir.mkdir(parents=True, exist_ok=True)
        slug = (sheet_mod.name(old) or "former-hero").lower().replace(" ", "-").replace("'", "")
        path = fallen_dir / f"{slug}.json"
        self.json_ops.save_json(str(path), old)
        return str(path)

    def create(self, data: Dict[str, Any], canon: Optional[str] = None,
               replace: bool = False) -> Dict[str, Any]:
        """Build, save and wire in the new character. Returns a result dict."""
        existing = self.json_ops.load_json("character.json")
        if existing and not replace:
            who = sheet_mod.name(existing) or "an existing character"
            return {"success": False,
                    "error": f'this campaign already plays "{who}" — pass --replace to hand the story to someone new'}

        data = dict(data)
        if canon:
            resolved = self._find_entity_name("npcs.json", canon)
            if not resolved:
                return {"success": False, "error": f'no NPC named "{canon}" in this campaign'}
            npc = (self.json_ops.load_json("npcs.json") or {})[resolved]
            data = sheet_mod.merge(sheet_mod.from_npc(npc), data)
            data["identity"]["name"] = resolved

        try:
            character, warnings = build_character(
                data, WorldKit(str(self.campaign_mgr.world_state_dir)))
        except CharacterError as error:
            return {"success": False, "error": str(error)}

        archived = self._archive(existing) if existing else None
        notes = hand_over(self.json_ops, existing or None, resolved if canon else None,
                          self.get_timestamp())
        if not self.json_ops.save_json("character.json", character):
            return {"success": False, "error": "failed to save character.json"}

        self.json_ops.update_json("campaign-overview.json",
                                  {"current_character": sheet_mod.name(character)})
        return {"success": True, "character": character, "warnings": warnings + notes,
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
    lines = [f"✓ {sheet_mod.name(character)} enters the world"]
    lines += [f"Note: {w}" for w in result["warnings"]]
    if result["archived"]:
        lines.append(f"Archived the outgoing hero to: {result['archived']}")
    emit(character, message="\n".join(lines), json_mode=json_mode)


if __name__ == "__main__":
    main()
