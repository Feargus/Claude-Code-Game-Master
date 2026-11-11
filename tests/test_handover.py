"""Handing the story to another character (handover.py): what a person knows
stays theirs. The outgoing character becomes an NPC with their facts; a canon
character takes the NPC's facts as the player's (2026-11-11: a canon start used
to leave everything the NPC knew with the NPC record)."""

import json
import re
from pathlib import Path

import pytest

from lib.json_ops import JsonOperations
from lib.new_character import CharacterCreator
from lib.note_manager import NoteManager
from lib.world_ids import WorldIds

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def camp(isolated_world_state):
    directory = isolated_world_state / "campaigns" / "c"
    directory.mkdir()
    (isolated_world_state / "active-campaign.txt").write_text("c")
    files = {
        "campaign-overview.json": {"campaign_name": "C", "game_time": "2189-11-09T23:40",
                                   "player_position": {"current_location": "The Pens"},
                                   "scene": {"location": "The Pens", "present": ["Tod"]}},
        "npcs.json": {"Tod Brask": {"aliases": ["Tod"], "tags": {"locations": ["The Pens"]}},
                      "Benno": {"tags": {"locations": []}}},
        "locations.json": {"The Pens": {}},
    }
    files["campaign-overview.json"]["scene"]["present"] = ["Tod Brask"]
    for name, payload in files.items():
        (directory / name).write_text(json.dumps(payload))
    return isolated_world_state, directory


def _facts(directory):
    return {f["id"]: f for items in json.loads((directory / "facts.json").read_text()).values()
            for f in items}


def _consequences(directory):
    return json.loads((directory / "consequences.json").read_text())["active"]


def test_a_canon_character_takes_what_the_npc_knew(camp):
    ws, directory = camp
    assert CharacterCreator().create({"name": "Lullaby"})["success"]
    notes = NoteManager(str(ws))
    seen = notes.add_fact("session_events", "Lullaby hummed; Tod Brask listened.")
    secret = notes.add_fact("plot_local", "Tod Brask keeps a key in his boot.",
                            holders=["npc:Tod Brask"])
    (directory / "consequences.json").write_text(json.dumps({"active": [
        {"id": "c1", "consequence": "x", "triggers": [{"type": "on_npc", "match": "npc:Tod Brask"}]},
        {"id": "c2", "consequence": "y", "triggers": [
            {"type": "on_learn", "match": "npc:Benno learns about npc:Tod Brask"}],
         "effects": [{"type": "tell", "fact": secret, "holders": ["npc:Tod Brask", "npc:Benno"]}]},
    ], "resolved": []}))

    # Lullaby dies; Tod takes over.
    result = CharacterCreator().create({"name": "x"}, canon="tod", replace=True)
    assert result["success"]
    facts = _facts(directory)
    assert facts[seen]["holders"] == ["npc:Lullaby", "player"]
    assert facts[seen]["about"] == ["npc:Lullaby", "player"]
    assert facts[secret]["holders"] == ["player"]
    c1, c2 = _consequences(directory)
    assert c1["triggers"][0]["match"] == "player"
    assert c2["triggers"][0]["match"] == "npc:Benno learns about player"
    assert c2["effects"][0]["holders"] == ["player", "npc:Benno"]
    assert any("c1 waited for npc:Tod Brask" in n for n in result["warnings"])

    npcs = json.loads((directory / "npcs.json").read_text())
    assert npcs["Tod Brask"]["is_player_character"] is True
    assert npcs["Lullaby"]["former_player_character"] is True
    overview = json.loads((directory / "campaign-overview.json").read_text())
    assert overview["scene"]["present"] == []

    ids = WorldIds(JsonOperations(str(directory)))
    for name in ("Tod", "Tod Brask", "npc:Tod Brask", "npc:tod"):
        assert ids.resolve(name) == ("player", "")
    assert ids.resolve("Lullaby") == ("npc:Lullaby", "")
    assert ids.mentioned("Tod opened the gate for Lullaby.") == ["player", "npc:Lullaby"]
    assert ids.present() == ["player"]


def test_a_new_character_after_a_death_starts_knowing_nothing(camp):
    ws, directory = camp
    CharacterCreator().create({"name": "Lullaby"})
    fact = NoteManager(str(ws)).add_fact("session_events", "Lullaby lost its leg.",
                                         holders=["player"])
    assert CharacterCreator().create({"name": "Vex"}, replace=True)["success"]
    assert _facts(directory)[fact]["holders"] == ["npc:Lullaby"]
    assert _facts(directory)[fact]["about"] == ["npc:Lullaby"]


def test_the_interview_example_saves(camp):
    """The example in /create-character is the default character: it must save."""
    text = (ROOT / ".claude" / "commands" / "create-character.md").read_text()
    data = json.loads(re.search(r"gm-player.sh create '(\{.*\})'", text).group(1))
    result = CharacterCreator().create(data)
    assert result["success"], result
    skills = result["character"]["skills"]
    assert "Brawling" not in skills and skills["Guard"] == 0 and skills["Piloting"] == 4
