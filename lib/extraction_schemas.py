#!/usr/bin/env python3
"""
JSON schemas for content extraction (story only, no game mechanics)
Defines exact structure for agent outputs
"""

# NPC Schema - For character extraction
NPC_SCHEMA = {
    "name": "",  # Required, max 100 chars
    "description": "",  # 80+ words narrative description
    "attitude": "",  # enum: friendly/neutral/hostile/suspicious/helpful
    "location_tags": [],  # Where they appear in the module
    "events": [],  # Optional: notable events or quests
    # Canonical look for consistent image generation. Fill every field you can
    # ground in the source; leave unknowns "". Keys are FIXED (see
    # lib/visual_appearance.py VISUAL_FIELDS).
    "visual_appearance": {
        "sex": "", "age": "", "race": "", "species": "", "hair": "",
        "face": "", "eyes": "", "clothing": "", "gear": "",
        "demeanor": "", "size": ""
    },
    "dialogue": [],  # Optional: notable quotes or conversation topics
    "source": ""  # Document name/section
}

# Location Schema - For place extraction
LOCATION_SCHEMA = {
    "name": "",  # Required location name
    "position": "",  # Relative position or coordinates
    "description": "",  # Rich narrative description
    "connections": [],  # [{to: name, path: description}]
    "features": [],  # Notable features or areas within
    "inhabitants": [],  # NPCs or creatures found here
    "hazards": [],  # Traps, environmental dangers
    "notes": "",  # Optional special features or secrets
    "source": ""  # Document name/section
}

# Item Schema - For treasure/equipment extraction
ITEM_SCHEMA = {
    "name": "",  # Item name
    "description": "",  # Physical and narrative description
    "type": "",  # weapon/armor/tool/device/treasure/equipment/prop/artifact
    "location": "",  # Where it's found or who has it
    "source": ""  # Document name/section
}

# Plot Hook Schema - For quest/story extraction
PLOT_HOOK_SCHEMA = {
    "name": "",  # Quest or plot name
    "description": "",  # Full description
    "type": "",  # main/side/personal/world/optional
    "npcs": [],  # Related NPCs by name
    "locations": [],  # Related locations
    "objectives": [],  # Quest objectives
    "rewards": "",  # Potential rewards
    "consequences": "",  # What happens if ignored/failed
    "source": ""  # Document name/section
}

# Faction Schema - For organization extraction
FACTION_SCHEMA = {
    "name": "",  # Faction name
    "description": "",  # Goals and nature
    "leader": "",  # Leader NPC name
    "members": [],  # Notable member NPCs
    "headquarters": "",  # Base location
    "allies": [],  # Allied factions
    "enemies": [],  # Enemy factions
    "source": ""  # Document name/section
}

# Batch extraction result schema
EXTRACTION_RESULT_SCHEMA = {
    "document": "",  # Source document name
    "extraction_date": "",  # When extracted
    "npcs": {},  # name -> NPC_SCHEMA
    "locations": {},  # name -> LOCATION_SCHEMA
    "items": {},  # name -> ITEM_SCHEMA
    "plot_hooks": {},  # name -> PLOT_HOOK_SCHEMA
    "factions": {},  # name -> FACTION_SCHEMA
    "metadata": {
        "total_chunks": 0,
        "chunks_processed": 0,
        "extraction_method": "concurrent_agents",
        "agents_used": []
    }
}

def get_schema(schema_type: str) -> dict:
    """Get a specific schema by type"""
    schemas = {
        'npc': NPC_SCHEMA,
        'location': LOCATION_SCHEMA,
        'item': ITEM_SCHEMA,
        'plot_hook': PLOT_HOOK_SCHEMA,
        'faction': FACTION_SCHEMA,
        'result': EXTRACTION_RESULT_SCHEMA
    }
    return schemas.get(schema_type, {})


def validate_extraction(data: dict, schema_type: str) -> tuple[bool, list]:
    """
    Validate extracted data against schema
    Returns (is_valid, errors)
    """
    schema = get_schema(schema_type)
    errors = []

    if not schema:
        return False, [f"Unknown schema type: {schema_type}"]

    # Check required fields
    for field, default in schema.items():
        if field not in data and not isinstance(default, (list, dict)):
            errors.append(f"Missing required field: {field}")

    # Validate specific fields
    if schema_type == 'npc':
        if 'name' in data and len(data.get('name', '')) > 100:
            errors.append("NPC name exceeds 100 characters")
        if 'attitude' in data and data['attitude'] not in ['friendly', 'neutral', 'hostile', 'suspicious', 'helpful']:
            errors.append(f"Invalid attitude: {data['attitude']}")

    return len(errors) == 0, errors


if __name__ == "__main__":
    # Test schema validation
    test_npc = {
        "name": "Old Iron",
        "description": "A scrap-surgeon who rebuilt himself from salvage, piece by piece.",
        "attitude": "neutral",
        "location_tags": ["Old Iron's Yard"],
        "source": "test"
    }

    valid, errors = validate_extraction(test_npc, 'npc')
    print(f"NPC validation: {'PASS' if valid else 'FAIL'}")
    if errors:
        for error in errors:
            print(f"  - {error}")