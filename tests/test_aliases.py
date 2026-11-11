"""Aliases: shorter names for NPCs and places ("Ishbel" for "Ishbel Rue", "the Yard"
for "Old Iron's Yard"), so the name check finds them in a fact's text. The GM gives
them; the script refuses one that would point at two things."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.json_ops import JsonOperations
from lib.location_manager import LocationManager
from lib.npc_manager import NPCManager
from lib.world_ids import WorldIds, change_aliases
from tests.sheets import npc, player

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def world(tmp_path):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    files = {
        "campaign-overview.json": {"campaign_name": "C",
                                   "player_position": {"current_location": "Old Iron's Yard"}},
        "npcs.json": {"Old Iron": npc("Old Iron", places=["Old Iron's Yard"]),
                      "Brother Erasure": npc("Brother Erasure", places=[])},
        "locations.json": {"Old Iron's Yard": {}, "Lanternside": {}},
        "character.json": player("Fearghas"),
    }
    for name, payload in files.items():
        (camp / name).write_text(json.dumps(payload))
    return str(ws), camp


def _ids(camp):
    return WorldIds(JsonOperations(str(camp)))


def test_create_with_aliases_and_find_them_in_text(world):
    ws, camp = world
    assert NPCManager(ws).create_npc("Ishbel Rue", "a Scrubbed woman", "neutral",
                                     locations=["Old Iron's Yard"], aliases=["Ishbel"])
    npcs = json.loads((camp / "npcs.json").read_text())
    assert npcs["Ishbel Rue"]["identity"]["aliases"] == ["Ishbel"]
    ids = _ids(camp)
    assert ids.mentioned("Erasure took forty years from Ishbel.") == ["npc:Ishbel Rue"]
    assert ids.resolve("Ishbel") == ("npc:Ishbel Rue", "")


def test_a_clashing_alias_refuses_the_npc(world, capsys):
    ws, camp = world
    manager = NPCManager(ws)
    for alias, why in [("Old Iron", "already names npc:Old Iron"),
                       ("Fearghas", "already names player"),
                       ("Lanternside", "already names location:Lanternside"),
                       ("street", "a word ids use"),
                       ("Ishbel Rue", "own name")]:
        assert not manager.create_npc("Ishbel Rue", "x", "neutral", nowhere=True, aliases=[alias])
        assert why in capsys.readouterr().out
    assert "Ishbel Rue" not in json.loads((camp / "npcs.json").read_text())


def test_the_nudge_only_for_names_of_several_words(world, capsys):
    ws, _ = world
    manager = NPCManager(ws)
    manager.create_npc("Sister Lacuna", "a scrub-priest", "hostile", nowhere=True)
    assert 'gm-npc.sh alias "Sister Lacuna"' in capsys.readouterr().out
    manager.create_npc("Tally", "a sentry", "friendly", nowhere=True)
    assert "alias" not in capsys.readouterr().out


def test_add_and_remove_aliases_later(world):
    ws, camp = world
    ops = JsonOperations(str(camp))
    assert change_aliases(ops, "npc", "brother erasure", add=["Erasure"]) == (
        "Brother Erasure", ["Erasure"])
    assert _ids(camp).mentioned("Erasure rang his bell.") == ["npc:Brother Erasure"]
    with pytest.raises(ValueError, match="already names npc:Brother Erasure"):
        change_aliases(ops, "npc", "Old Iron", add=["Erasure"])
    with pytest.raises(ValueError, match="has no alias 'Iron'"):
        change_aliases(ops, "npc", "Old Iron", remove=["Iron"])
    assert change_aliases(ops, "npc", "Brother Erasure", remove=["erasure"]) == (
        "Brother Erasure", [])
    assert "aliases" not in json.loads((camp / "npcs.json").read_text())["Brother Erasure"]["identity"]


def test_places_get_aliases_too(world, capsys):
    ws, camp = world
    ops = JsonOperations(str(camp))
    change_aliases(ops, "location", "Old Iron's Yard", add=["the Yard"])
    assert _ids(camp).mentioned("Priests came to the Yard at dawn.") == ["location:Old Iron's Yard"]
    assert LocationManager(ws).add_location("The Mercy Line stairwells", "down from Lanternside",
                                            aliases=["the Mercy Line"])
    assert "Also called: the Mercy Line" in capsys.readouterr().out
    assert not LocationManager(ws).add_location("Yard Two", "nearby", aliases=["the Yard"])
    assert "already names location:Old Iron's Yard" in capsys.readouterr().out


def test_cli_alias_commands(world):
    ws, camp = world

    def run(script, *args):
        return subprocess.run([sys.executable, str(ROOT / "lib" / script), *args],
                              capture_output=True, text=True, cwd=str(Path(ws).parent))

    r = run("npc_manager.py", "alias", "Brother Erasure", "Erasure")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Brother Erasure: also called Erasure" in r.stdout
    r = run("location_manager.py", "alias", "Old Iron's Yard", "the Yard")
    assert "Old Iron's Yard: also called the Yard" in r.stdout
    r = run("npc_manager.py", "alias", "Old Iron", "the Yard")
    assert r.returncode == 1 and "already names location:Old Iron's Yard" in r.stdout


def test_an_alias_the_name_check_already_finds_is_explained(world, capsys):
    """In play the GM gave 'Saint Ayo's' the alias "Ayo's" and was told it was the
    place's 'own name', which made no sense; titles are ignored, so it is found."""
    ws, camp = world
    assert not LocationManager(ws).add_location("Saint Ayo's", "a clinic", aliases=["Ayo's"])
    out = capsys.readouterr().out
    assert "needs no alias: the name check already finds it as 'Saint Ayo's'" in out
