"""on_location, on_npc and on_death hold ids (world_ids.py), checked when added and
compared exactly. Before, the match was any text, compared as a substring: "Ro"
fired whenever Old Iron was present, "Yard" in the Junkyard Market."""

import json

from lib.consequence_manager import ConsequenceManager
from tests.sheets import npc, player


def _campaign(tmp_path, scene=None):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    files = {
        "campaign-overview.json": {"campaign_name": "C",
                                   "player_position": {"current_location": "Yard"},
                                   "scene": scene or {"location": "Yard", "present": []}},
        "npcs.json": {"Ro": npc("Ro"), "Old Iron": npc("Old Iron")},
        "locations.json": {"Yard": {}, "Junkyard Market": {}},
        "character.json": player("Fearghas"),
    }
    for name, payload in files.items():
        (camp / name).write_text(json.dumps(payload))
    return str(ws), camp


def _triggers(camp, cid):
    data = json.loads((camp / "consequences.json").read_text(encoding="utf-8"))
    return next(c for c in data["active"] if c["id"] == cid)["triggers"]


def test_names_are_stored_as_ids(tmp_path):
    ws, camp = _campaign(tmp_path)
    cm = ConsequenceManager(ws)
    cid = cm.add_consequence("x", "y", triggers=[
        {"type": "on_location", "match": "yard"},
        {"type": "on_npc", "match": "ro"},
        {"type": "on_death", "match": "npc:Old Iron"},
        {"type": "on_death", "match": "Fearghas"}])
    assert _triggers(camp, cid) == [
        {"type": "on_location", "match": "location:Yard"},
        {"type": "on_npc", "match": "npc:Ro"},
        {"type": "on_death", "match": "npc:Old Iron"},
        {"type": "on_death", "match": "player"}]


def test_unknown_or_wrong_kind_is_refused(tmp_path, capsys):
    ws, _ = _campaign(tmp_path)
    cm = ConsequenceManager(ws)
    assert cm.add_consequence("x", "y", trigger_type="on_location", match="Lantern") == ""
    assert "No location 'Lantern'. It matches a known place" in capsys.readouterr().err
    assert cm.add_consequence("x", "y", trigger_type="on_location", match="Old Iron") == ""
    assert "is npc:Old Iron, not a place" in capsys.readouterr().err
    assert cm.add_consequence("x", "y", trigger_type="on_npc", match="Yard") == ""
    assert cm.add_consequence("x", "y", trigger_type="on_npc", match="player") == ""
    assert cm.add_consequence("x", "y", trigger_type="on_death", match="location:Yard") == ""


def test_matching_is_exact(tmp_path):
    ws, _ = _campaign(tmp_path)
    cm = ConsequenceManager(ws)
    at_yard = cm.add_consequence("a", "b", trigger_type="on_location", match="Yard")
    ro_here = cm.add_consequence("c", "d", trigger_type="on_npc", match="Ro")

    def fired(location, present):
        hits = cm.check_pending({"location": location, "present_npcs": present}, limit=10)
        return {c["id"] for c in hits}

    assert fired("Junkyard Market", ["Old Iron"]) == set()
    assert fired("Yard", ["Old Iron"]) == {at_yard}
    assert fired("Junkyard Market", ["Ro"]) == {ro_here}


def test_the_scene_check_fires_on_ids(tmp_path):
    ws, _ = _campaign(tmp_path, scene={"location": "Yard", "present": ["Ro"]})
    cm = ConsequenceManager(ws)
    at_yard = cm.add_consequence("a", "b", trigger_type="on_location", match="Yard")
    ro_here = cm.add_consequence("c", "d", trigger_type="on_npc", match="Ro")
    iron_here = cm.add_consequence("e", "f", trigger_type="on_npc", match="Old Iron")
    fired = {c["id"] for c in cm.tick_from_session(limit=10)["fired"]}
    assert fired == {at_yard, ro_here}
    assert iron_here not in fired
