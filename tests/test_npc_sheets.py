"""NPCs on the new sheet (2026-11-11): created with only what play needs, filled in
later with `set`; how they regard the player is a fact they hold, not an
attitude field; the brief's PEOPLE HERE block plays them from their sheet."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.note_manager import NoteManager
from lib.npc_manager import NPCManager
from lib.player_manager import PlayerManager
from lib.session_manager import SessionManager
from tests.sheets import npc, player

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def world(tmp_path):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    files = {
        "campaign-overview.json": {"campaign_name": "C", "game_time": "2189-11-09T23:40",
                                   "player_position": {"current_location": "The Pens"},
                                   "scene": {"location": "The Pens", "present": []}},
        "character.json": player("Lullaby", possessions={"credits": 5}),
        "npcs.json": {},
        "locations.json": {"The Pens": {}},
    }
    for name, payload in files.items():
        (camp / name).write_text(json.dumps(payload))
    return str(ws), camp


def _npcs(camp):
    return json.loads((camp / "npcs.json").read_text())


def test_create_needs_little_and_the_attitude_becomes_a_fact(world, capsys):
    ws, camp = world
    assert NPCManager(ws).create_npc("Tod Brask", "a pit mechanic", "wary",
                                     locations=["The Pens"], aliases=["Tod"],
                                     fields={"big-five": "o1 c2 e-1 a1 n0", "voice": "dry"})
    sheet = _npcs(camp)["Tod Brask"]
    assert sheet == {"identity": {"name": "Tod Brask", "role": "a pit mechanic", "aliases": ["Tod"]},
                     "personality": {"big_five": "O1 C2 E-1 A1 N0", "voice": "dry"},
                     "places": {"usual": ["The Pens"]}}
    feeling = NoteManager(ws).find(held_by=["npc:Tod Brask"], about=["player"])
    assert [f["fact"] for f in feeling] == ["How Tod Brask regards Lullaby: wary."]
    assert feeling[0]["holders"] == ["npc:Tod Brask"] and "at" not in feeling[0]
    assert NPCManager(ws).create_npc("Benno", "a handler", locations=["The Pens"])  # no attitude
    assert NoteManager(ws).find(held_by=["npc:Benno"]) == []
    assert not NPCManager(ws).create_npc("Bad", "x", nowhere=True, fields={"big-five": "ENTJ"})
    assert "Big Five" in capsys.readouterr().out


def test_set_items_party_and_show(world, capsys):
    ws, camp = world
    manager = NPCManager(ws)
    manager.create_npc("Tod", "a mechanic", nowhere=True)
    assert manager.set_fields("tod", {"tells": "wipes his hands when he lies", "goal": "get out"})
    assert manager.item("Tod", "add", "gear", "torque wrench")
    assert manager.item("Tod", "add", "inventory", "a chip", concealed=False)
    assert manager.set_party("Tod", True)
    sheet = _npcs(camp)["Tod"]
    assert sheet["status"] == {"goal": "get out", "party_member": True}
    assert sheet["items"] == {"gear": [{"name": "torque wrench"}], "inventory": [{"name": "a chip"}]}
    NoteManager(ws).add_fact("relations", "Tod trusts Lullaby now.", holders=["npc:Tod"],
                             about=["npc:Tod", "player"])
    capsys.readouterr()
    shown = manager.show("Tod")
    assert "tells: wipes his hands when he lies" in shown and "party member" in shown
    assert "Tod trusts Lullaby now." in shown
    assert manager.set_party("Tod", False) and "party_member" not in _npcs(camp)["Tod"]["status"]


def test_the_brief_plays_people_from_their_sheets(world):
    ws, camp = world
    manager = NPCManager(ws)
    manager.create_npc("Tod", "a mechanic", locations=["The Pens"],
                       fields={"big-five": "O1 C2 E-1 A1 N0", "demeanor": "patient",
                               "physique": "stooped, oil to the elbows", "voice": "dry",
                               "want": "a way out", "need": "to forgive himself"})
    manager.item("Tod", "add", "gear", "wrench")
    manager.item("Tod", "add", "gear", "shiv", concealed=True)
    overview = json.loads((camp / "campaign-overview.json").read_text())
    overview["scene"]["present"] = ["Tod"]
    (camp / "campaign-overview.json").write_text(json.dumps(overview))
    PlayerManager(ws).item("add", "gear", "pipe")
    brief = SessionManager(ws).get_full_context()
    people = brief[brief.index("--- PEOPLE HERE"):]
    assert "Tod (a mechanic; Big Five O1 C2 E-1 A1 N0; patient):" in people
    assert "  look: stooped, oil to the elbows" in people and "  wants: a way out" in people
    assert "  gear: wrench" in people and "shiv" not in people          # concealed
    assert "needs" not in people                                       # only with --full
    assert "Gear (what others can see): pipe" in brief


def test_player_set_and_item_commands(world):
    ws, camp = world

    def run(*args):
        return subprocess.run([sys.executable, str(ROOT / "lib" / "player_manager.py"), *args],
                              capture_output=True, text=True, cwd=str(Path(ws).parent))

    r = run("set", "--style", "a pink ribbon in a chest seam", "--big-five", "O0 C1 E-2 A2 N1")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run("item", "add", "gear", "the ribbon", "--concealed")
    assert "ITEM_ADDED Lullaby gear: the ribbon (concealed)" in r.stdout
    r = run("item", "move", "ribbon")
    assert "gear -> inventory" in r.stdout
    r = run("loot", "--credits", "3", "--items", "scrap")
    sheet = json.loads((camp / "character.json").read_text())
    assert sheet["look"] == {"style": "a pink ribbon in a chest seam"}
    assert sheet["items"]["inventory"] == [{"name": "the ribbon", "concealed": True}, {"name": "scrap"}]
    assert sheet["possessions"]["credits"] == 8
    assert run("set", "--hair", "red").returncode != 0
