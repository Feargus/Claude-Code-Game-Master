"""about: who or what a fact concerns, with the name cross-check.

The ids given are checked (an unknown one refuses the fact); names found in
the text are added by themselves and reported, and --not-about drops a wrong
one. `gm-note.sh about` changes a recorded fact's list.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.json_ops import JsonOperations
from lib.note_manager import NoteManager
from lib.world_ids import WorldIds
from lib.world_tick import WorldTick, WorldTickError

CAMPAIGN = "dungeon-crawler-carl"


def _cdir(world):
    return Path(world) / "campaigns" / CAMPAIGN


def _fact(world, fid):
    facts = json.loads((_cdir(world) / "facts.json").read_text(encoding="utf-8"))
    return next(f for items in facts.values() for f in items
                if isinstance(f, dict) and f.get("id") == fid)


def _ids(world):
    return WorldIds(JsonOperations(str(_cdir(world))))


# ---------- finding names in the text ----------

@pytest.mark.parametrize("text, expected", [
    ("Tandy met Mordecai in the Bone Garden.",
     ["player", "npc:Mordecai", "location:Bone Garden"]),
    ("Donut sulked.", ["npc:Princess Donut"]),                    # title dropped
    ("mordecai, the bone garden", []),                            # lower case: not a name
    ("Mordecai's map of Bone Garden", ["npc:Mordecai", "location:Bone Garden"]),
    ("Carl, Carl and Carl", ["npc:Carl"]),                        # once
    ("The Carlsberg sign", []),                                   # whole names only
])
def test_mentioned(dcc_world, text, expected):
    assert _ids(dcc_world).mentioned(text) == expected


def test_a_name_inside_a_longer_one_counts_once(dcc_world):
    locs = _cdir(dcc_world) / "locations.json"
    data = json.loads(locs.read_text(encoding="utf-8"))
    data["Garden"] = {}
    locs.write_text(json.dumps(data))
    assert _ids(dcc_world).mentioned("In the Bone Garden.") == ["location:Bone Garden"]


def test_aliases_count(dcc_world):
    npcs = _cdir(dcc_world) / "npcs.json"
    data = json.loads(npcs.read_text(encoding="utf-8"))
    data["Mordecai"]["aliases"] = ["the Manager"]
    npcs.write_text(json.dumps(data))
    assert _ids(dcc_world).mentioned("The Manager is late.") == ["npc:Mordecai"]


# ---------- recording ----------

def test_names_in_the_text_are_added_and_reported(dcc_world, capsys):
    fid = NoteManager(dcc_world).add_fact("session_events", "Mordecai paid the debt",
                                          about=["location:bone garden"])
    assert _fact(dcc_world, fid)["about"] == ["location:Bone Garden", "npc:Mordecai"]
    out = capsys.readouterr().out
    assert "about: location:Bone Garden, npc:Mordecai" in out
    assert "npc:Mordecai found in the text" in out
    assert f"gm-note.sh about {fid} --remove" in out


def test_not_about_drops_a_found_name(dcc_world):
    fid = NoteManager(dcc_world).add_fact("lore", "Carl's mother named a cat after Mordecai",
                                          not_about=["Mordecai"])
    assert _fact(dcc_world, fid)["about"] == ["npc:Carl"]


def test_no_names_no_about_field(dcc_world):
    fid = NoteManager(dcc_world).add_fact("lore", "The rain is acid")
    assert "about" not in _fact(dcc_world, fid)


def test_an_unknown_id_refuses_the_fact(dcc_world, capsys):
    before = (_cdir(dcc_world) / "facts.json").read_text(encoding="utf-8")
    assert NoteManager(dcc_world).add_fact("lore", "x", about=["npc:Mordekai"]) == ""
    err = capsys.readouterr().err
    assert "did you mean: npc:Mordecai" in err and "not recorded" in err
    assert (_cdir(dcc_world) / "facts.json").read_text(encoding="utf-8") == before


def test_set_about_adds_and_removes(dcc_world):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("lore", "Carl sleeps")
    assert nm.set_about(fid, add=["Mordecai"], remove=["npc:Carl"]) == ["npc:Mordecai"]
    assert _fact(dcc_world, fid)["about"] == ["npc:Mordecai"]
    assert nm.set_about(fid, remove=["Mordecai"]) == []
    assert "about" not in _fact(dcc_world, fid)
    with pytest.raises(ValueError, match="No fact"):
        nm.set_about("f9999", add=["Carl"])
    with pytest.raises(ValueError, match="did you mean"):
        nm.set_about(fid, add=["npc:Mordekai"])


# ---------- other writers ----------

def test_world_tick_takes_about_and_finds_names(dcc_world):
    applied = WorldTick(dcc_world).apply([
        {"fact": "Mordecai sold the map.", "about": ["location:Bone Garden"]}])
    assert _fact(dcc_world, applied[0]["fact"])["about"] == [
        "location:Bone Garden", "npc:Mordecai"]


def test_world_tick_refuses_an_unknown_about_and_keeps_nothing(dcc_world):
    before = (_cdir(dcc_world) / "facts.json").read_text(encoding="utf-8")
    with pytest.raises(WorldTickError, match="about"):
        WorldTick(dcc_world).apply([{"fact": "a"}, {"fact": "b", "about": ["npc:Nobody"]}])
    assert (_cdir(dcc_world) / "facts.json").read_text(encoding="utf-8") == before


def test_an_npc_death_is_about_the_npc(dcc_world):
    from lib.npc_manager import NPCManager
    result = NPCManager(dcc_world).kill_npc("Mordecai", cause="fell")
    assert _fact(dcc_world, result["fact"])["about"] == ["npc:Mordecai"]


def test_cli(dcc_world):
    root = Path(__file__).resolve().parent.parent
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(root / "lib" / "note_manager.py"), *a],
        capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    r = run("add", "lore", "Carl hums", "--about", "Bone Garden", "--not-about", "Carl")
    assert r.returncode == 0, r.stderr
    assert "about: location:Bone Garden" in r.stdout
    fid = r.stdout.split("Recorded fact ")[1].split()[0]
    r = run("about", fid, "--add", "player")
    assert r.returncode == 0 and "location:Bone Garden, player" in r.stdout
    r = run("add", "lore", "x", "--about", "npc:Nobody")
    assert r.returncode == 1 and "not recorded" in r.stderr
