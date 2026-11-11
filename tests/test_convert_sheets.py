"""TEMPORARY, with lib/convert_sheets.py: the old sheets convert without losing what
the new format keeps (2026-11-11). Both go once the old campaigns are retired."""

import json

from lib.convert_sheets import convert_campaign
from lib.sheet import check


def test_a_campaign_converts(tmp_path):
    (tmp_path / "character.json").write_text(json.dumps({
        "id": "lullaby", "name": "Lullaby", "race": "android", "class": "pit fighter",
        "level": 2, "xp": {"current": 500, "next_level": 900}, "stats": {"STR": 14},
        "skills": {"Brawling": 2}, "luck": {"current": 3, "max": 3}, "traits": {"Cracked governor": "x"},
        "features": ["Combat Sleeve"], "alignment": "loyal", "flaws": "a temper",
        "equipment": ["pink ribbon"], "credits": 4, "conditions": ["tired"],
        "visual_appearance": {"sex": "female-presenting", "age": "11 years", "clothing": "rags",
                              "demeanor": "gentle"},
        "body": {"left_leg": {"wounds": 4}}, "armor": [], "cyberware": [], "drift": {"current": 2, "max": 10},
        "current_location": "Tod's Workshop"}))
    (tmp_path / "npcs.json").write_text(json.dumps({"Tod": {
        "description": "a mechanic", "attitude": "friendly", "aliases": ["Toddy"],
        "tags": {"locations": ["Tod's Workshop"], "quests": []}, "current_mood": "tired",
        "goal": "get out", "voice": "dry", "wounds": 2, "status": "dead",
        "events": [{"event": "Tod hid Lullaby.", "timestamp": "x"}]}}))
    (tmp_path / "mobs.json").write_text(json.dumps({"rat": {"attributes": {"default": 6},
                                                           "skills": {}, "note": "vermin", "wounds": 1}}))
    report = convert_campaign(tmp_path)
    assert any("current_location" in line for line in report)
    pc = check(json.loads((tmp_path / "character.json").read_text()), "player")
    assert pc["identity"] == {"name": "Lullaby", "race": "android", "role": "pit fighter"}
    assert pc["look"] == {"physique": "female-presenting; 11 years", "style": "rags", "presence": "gentle"}
    assert pc["personality"] == {"values": "loyal", "fears": "a temper"}
    assert pc["stats"]["traits"] == {"Cracked governor": "x", "Combat Sleeve": ""}
    assert pc["stats"]["counters"] == {"drift": {"current": 2, "max": 10}}
    assert pc["progress"] == {"level": 2, "xp": 500}
    assert pc["items"] == {"inventory": [{"name": "pink ribbon"}]} and pc["possessions"] == {"credits": 4}
    assert pc["body"]["zones"] == {"left_leg": {"wounds": 4}}
    tod = check(json.loads((tmp_path / "npcs.json").read_text())["Tod"], "npc")
    assert tod["identity"] == {"name": "Tod", "aliases": ["Toddy"], "role": "a mechanic"}
    assert tod["status"] == {"state": "dead", "goal": "get out"} and tod["body"] == {"wounds": 2}
    facts = json.loads((tmp_path / "facts.json").read_text())["npc_memories"]
    assert [f["fact"] for f in facts] == ["Tod is friendly toward the player.", "Tod hid Lullaby."]
    assert facts[0]["holders"] == ["npc:Tod"] and facts[0]["id"] == "f1"
    rat = json.loads((tmp_path / "mobs.json").read_text())["rat"]
    assert rat["identity"] == {"name": "rat", "background": "vermin"}
    assert convert_campaign(tmp_path)  # a second run changes nothing
    assert len(json.loads((tmp_path / "facts.json").read_text())["npc_memories"]) == 2
