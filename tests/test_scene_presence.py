"""Who is in the scene (gm-scene.sh, lib/scene_manager.py).

Presence is the party plus the scene list, kept by enter/leave. Every move
resets it to the party; a list stored for another location is stale. Location
tags only say where an NPC is usually found: a hint in the brief.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.consequence_manager import ConsequenceManager
from lib.scene_manager import SceneManager
from lib.session_manager import SessionManager

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = "dungeon-crawler-carl"
PARTY = {"Carl", "Princess Donut", "Mongo"}  # the fixture's party members


def _cdir(world):
    return Path(world) / "campaigns" / CAMPAIGN


def _overview(world):
    return json.loads((_cdir(world) / "campaign-overview.json").read_text(encoding="utf-8"))


def test_only_the_party_is_present_at_first(dcc_world):
    assert set(SceneManager(dcc_world).present()) == PARTY


def test_enter_and_leave(dcc_world):
    sm = SceneManager(dcc_world)
    result = sm.enter(["mordecai", "npc:The Butcher", "Carl"])
    assert result == {"entered": ["Mordecai", "The Butcher"], "already": ["Carl"]}
    assert set(sm.present()) == PARTY | {"Mordecai", "The Butcher"}
    assert sm.enter(["Mordecai"]) == {"entered": [], "already": ["Mordecai"]}
    assert sm.leave(["The Butcher"]) == ["The Butcher"]
    assert sm.leave(["The Butcher"]) == []
    assert set(sm.present()) == PARTY | {"Mordecai"}


def test_refusals_change_nothing(dcc_world):
    sm = SceneManager(dcc_world)
    with pytest.raises(ValueError, match="did you mean: npc:Mordecai"):
        sm.enter(["Mordekai", "Imani"])          # one bad name: nobody enters
    assert set(sm.present()) == PARTY
    npcs_file = _cdir(dcc_world) / "npcs.json"
    npcs = json.loads(npcs_file.read_text(encoding="utf-8"))
    npcs["Imani"]["status"] = {"state": "dead"}
    npcs_file.write_text(json.dumps(npcs))
    with pytest.raises(ValueError, match="dead"):
        sm.enter(["Imani"])
    with pytest.raises(ValueError, match="party members"):
        sm.leave(["Carl"])


def test_a_move_resets_the_scene_to_the_party(dcc_world):
    SceneManager(dcc_world).enter(["Mordecai"])
    SessionManager(dcc_world).move_party("Bone Garden")
    scene = _overview(dcc_world)["scene"]
    assert scene == {"location": "Bone Garden", "present": []}
    assert set(SceneManager(dcc_world).present()) == PARTY


def test_moving_to_the_same_place_keeps_the_scene(dcc_world):
    sm = SceneManager(dcc_world)
    sm.enter(["Mordecai"])
    SessionManager(dcc_world).move_party(sm.location())
    assert "Mordecai" in sm.present()


def test_a_list_for_another_location_is_stale(dcc_world):
    p = _cdir(dcc_world) / "campaign-overview.json"
    overview = _overview(dcc_world)
    overview["scene"] = {"location": "Somewhere Else", "present": ["Mordecai"]}
    p.write_text(json.dumps(overview))
    assert "Mordecai" not in SceneManager(dcc_world).present()


def test_tags_are_a_hint_not_presence(dcc_world):
    sm = SceneManager(dcc_world)
    npcs_file = _cdir(dcc_world) / "npcs.json"
    npcs = json.loads(npcs_file.read_text(encoding="utf-8"))
    npcs["Mordecai"]["places"]["usual"].append(sm.location())
    npcs_file.write_text(json.dumps(npcs))
    assert "Mordecai" not in sm.present()
    assert sm.usually_here() == ["Mordecai"]
    ctx = SessionManager(dcc_world).get_full_context()
    assert "Usually found here, not in the scene: Mordecai" in ctx
    sm.enter(["Mordecai"])
    assert sm.usually_here() == []


def test_on_npc_fires_when_someone_enters(dcc_world):
    """gm-scene.sh enter runs the consequence check, like a move does."""
    cid = ConsequenceManager(dcc_world).add_consequence(
        "Mordecai hands over the key", "x", trigger_type="on_npc", match="Mordecai")
    env = {**os.environ, "GM_WORLD_STATE_BASE": str(dcc_world)}
    r = subprocess.run(["bash", str(ROOT / "tools" / "gm-scene.sh"), "enter", "Mordecai"],
                       cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Entered: Mordecai" in r.stdout
    assert cid in r.stdout and "Mordecai hands over the key" in r.stdout


def test_cli_refusal_and_show(dcc_world):
    env = {**os.environ, "GM_WORLD_STATE_BASE": str(dcc_world)}
    run = lambda *a: subprocess.run(  # noqa: E731
        ["bash", str(ROOT / "tools" / "gm-scene.sh"), *a],
        cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=60)
    r = run("enter", "Mordekai")
    assert r.returncode == 1 and "did you mean: npc:Mordecai" in r.stderr
    r = run()
    assert r.returncode == 0 and "Present: Carl" in r.stdout


# ---------- a new NPC needs a usual place ----------

def test_create_needs_a_usual_place(dcc_world, capsys):
    from lib.npc_manager import NPCManager
    nm = NPCManager(dcc_world)
    assert not nm.create_npc("Vex", "a fixer", "neutral")
    out = capsys.readouterr().out
    assert "Where is Vex usually found?" in out and '--location "Warehouse Street Level"' in out
    assert not nm.create_npc("Vex", "a fixer", "neutral", locations=["Bone Gardn"])
    assert "did you mean: location:Bone Garden" in capsys.readouterr().out
    assert not nm.create_npc("Vex", "a fixer", "neutral", locations=["Bone Garden"], nowhere=True)
    assert "Vex" not in json.loads((_cdir(dcc_world) / "npcs.json").read_text(encoding="utf-8"))


def test_create_with_places_or_nowhere(dcc_world, capsys):
    from lib.npc_manager import NPCManager
    nm = NPCManager(dcc_world)
    assert nm.create_npc("Vex", "a fixer", "neutral", locations=["bone garden", "Floor 1 Stairs"])
    assert "gm-scene.sh enter \"Vex\"" in capsys.readouterr().out
    assert nm.create_npc("The Voice", "lives on a chip", "neutral", nowhere=True)
    npcs = json.loads((_cdir(dcc_world) / "npcs.json").read_text(encoding="utf-8"))
    assert npcs["Vex"]["places"]["usual"] == ["Bone Garden", "Floor 1 Stairs"]
    assert npcs["The Voice"]["places"]["usual"] == []
    assert npcs["Vex"]["identity"] == {"name": "Vex", "role": "a fixer"}
    assert "Vex" not in SceneManager(dcc_world).present()   # created is not entered


# ---------- changing usual places ----------

def _tags(world, npc):
    return json.loads((_cdir(world) / "npcs.json").read_text(encoding="utf-8"))[npc]["places"]["usual"]


def test_tag_location_checks_names_and_keeps_order(dcc_world, capsys):
    from lib.npc_manager import NPCManager
    nm = NPCManager(dcc_world)
    before = _tags(dcc_world, "Mordecai")
    assert nm.tag_location("mordecai", "bone garden", "Floor 1 Stairs")
    assert _tags(dcc_world, "Mordecai") == before + ["Bone Garden", "Floor 1 Stairs"]
    assert nm.tag_location("Mordecai", "Bone Garden")              # already there
    assert "(no change)" in capsys.readouterr().out
    assert not nm.tag_location("Mordecai", "Bone Gardn")
    assert "did you mean: location:Bone Garden" in capsys.readouterr().out
    assert not nm.tag_location("Mordekai", "Bone Garden")
    assert "did you mean: npc:Mordecai" in capsys.readouterr().out


def test_a_usual_place_after_nowhere(dcc_world):
    from lib.npc_manager import NPCManager
    nm = NPCManager(dcc_world)
    nm.create_npc("The Voice", "lives on a chip", "neutral", nowhere=True)
    nm.tag_location("The Voice", "Bone Garden")
    npc = json.loads((_cdir(dcc_world) / "npcs.json").read_text(encoding="utf-8"))["The Voice"]
    assert npc["places"]["usual"] == ["Bone Garden"]


def test_untag_location_matches_old_tags_loosely(dcc_world, capsys):
    from lib.npc_manager import NPCManager
    nm = NPCManager(dcc_world)
    assert _tags(dcc_world, "Mordecai") == ["Tutorial Guild Hall", "tutorial-guild-hall"]
    assert nm.untag_location("Mordecai", "Tutorial Guild Hall")    # both spellings go
    assert _tags(dcc_world, "Mordecai") == []
    assert not nm.untag_location("Mordecai", "Bone Garden")
    assert "has no usual place 'Bone Garden'" in capsys.readouterr().out
