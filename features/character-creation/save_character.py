#!/usr/bin/env python3
"""
Save a character to world-state JSON files
Supports multi-campaign system (saves to active campaign's character.json)
"""

import json
import sys
import os
from pathlib import Path

# Add lib directory to path for imports
lib_path = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from campaign_manager import CampaignManager
from world_kit import WorldKit
import visual_appearance as va_mod

def resolve_hp(character_data):
    """HP as {current, max}. An authored HP is preserved exactly.

    Returns (hp_dict, warning_or_None). With no authored HP it falls back to
    10/10; the warning names that fallback so the caller can surface it.
    """
    authored = character_data.get('hp')
    if isinstance(authored, dict):
        max_hp = authored.get('max', authored.get('current', 0))
        return {"current": authored.get('current', max_hp), "max": max_hp}, None
    if isinstance(authored, (int, float)):
        return {"current": authored, "max": authored}, None
    return (
        {"current": 10, "max": 10},
        "hp defaulted to 10/10; the kit does not derive HP — author it",
    )


def create_character_id(name):
    """Convert character name to file-safe ID"""
    return name.lower().replace(' ', '-').replace("'", '').replace('"', '')

def save_character(character_data):
    """Save character to campaign's character.json file"""

    kit = WorldKit()

    # Validate required fields. `attributes` is the World Kit's stat_schema name;
    # `stats` is the legacy alias (and the canonical flat key we persist).
    # Only name + level are universal, matching schemas.validate_character.
    required_fields = ['name', 'level']
    for field in required_fields:
        if field not in character_data:
            return {"error": f"Missing required field: {field}"}
    stats = character_data.get('attributes', character_data.get('stats'))
    if stats is None:
        return {"error": "Missing required field: attributes (legacy alias: stats)"}

    # Generate character ID
    char_id = create_character_id(character_data['name'])

    hp, hp_warning = resolve_hp(character_data)
    warnings = [hp_warning] if hp_warning else []

    # Build complete character object
    character = {
        "id": char_id,
        "name": character_data['name'],
        "race": character_data.get('race', ''),
        "class": character_data.get('class', ''),
        "level": character_data['level'],
        "hp": hp,
        "ac": character_data.get('ac', 10),  # Default AC, can be overridden
        "stats": stats,
        "skills": character_data.get('skills', {}),
        "equipment": character_data.get('equipment', []),
        "features": character_data.get('features', []),
        "background": character_data.get('background', ''),
        "alignment": character_data.get('alignment', ''),
        "bonds": character_data.get('bonds', ''),
        "flaws": character_data.get('flaws', ''),
        "ideals": character_data.get('ideals', ''),
        "traits": character_data.get('traits', ''),
        "notes": character_data.get('notes', []),
        "gold": character_data.get('gold', 0),
        "xp": character_data.get('xp', {"current": 0, "next_level": 300}),
        # Canonical look-of-the-character for consistent image generation.
        "visual_appearance": va_mod.normalize(character_data.get('visual_appearance'))
    }


    # Kit vitals beyond hp (vigor, corruption, water, ...) live top-level on the
    # flat sheet — carry through whatever the kit declares and the author supplied.
    for vital in kit.vitals():
        if vital != 'hp' and vital in character_data:
            character[vital] = character_data[vital]

    # Get the active campaign directory
    campaign_mgr = CampaignManager()
    campaign_dir = campaign_mgr.get_active_campaign_dir()

    # Determine save path based on campaign system
    if campaign_mgr.get_active():
        # New format: save to character.json in campaign folder
        file_path = campaign_dir / "character.json"
    else:
        # Legacy format: save to characters/<name>.json
        characters_dir = Path("world-state/characters")
        characters_dir.mkdir(parents=True, exist_ok=True)
        file_path = characters_dir / f"{char_id}.json"

    try:
        with open(file_path, 'w') as f:
            json.dump(character, f, indent=2)

        return {
            "success": True,
            "character_id": char_id,
            "file_path": str(file_path),
            "campaign": campaign_mgr.get_active() or "legacy",
            "character": character,
            "warnings": warnings,
        }

    except Exception as e:
        return {"error": f"Failed to save character: {str(e)}"}

def main():
    """CLI interface for character saving"""
    
    if len(sys.argv) < 2:
        print("Usage: save_character.py '<character_json>' or save_character.py --stdin")
        print("Example: save_character.py '{\"name\":\"Thorin\",\"race\":\"Dwarf\",\"class\":\"Fighter\",\"level\":1,\"stats\":{\"str\":16,\"dex\":12,\"con\":15,\"int\":10,\"wis\":13,\"cha\":8}}'")
        sys.exit(1)
    
    try:
        if sys.argv[1] == '--stdin':
            # Read from stdin
            character_json = sys.stdin.read().strip()
        else:
            # Read from argument
            character_json = sys.argv[1]
        
        character_data = json.loads(character_json)
        result = save_character(character_data)
        
        print(json.dumps(result, indent=2))
        
        if "error" in result:
            sys.exit(1)
            
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {str(e)}"}, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Unexpected error: {str(e)}"}, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()