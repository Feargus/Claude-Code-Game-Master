"""Tests for the campaign's own counters (ruleset `stat_schema.vitals`): they are saved
with a new character and read or changed with `gm-player.sh vital`.

Both fixture worlds are built in tmp_path, so nothing here reads or writes the
repo's world-state (the live active-campaign.txt is never touched).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lib.player_manager import PlayerManager

ROOT = Path(__file__).resolve().parent.parent
NEW_CHARACTER = ROOT / "lib" / "new_character.py"

HYBORIAN_RULESET = {
    "name": "The Hyborian Age",
    "kit": "hyborian",
    "stat_schema": {"vitals": ["vigor", "corruption"]},
    "progression": {"model": "milestone"},
    "active_agents": [],
}


CONAN = {
    "identity": {"name": "Conan", "race": "Cimmerian", "role": "Reaver"},
    "progress": {"level": 6},
    "stats": {"attributes": {"STR": 18, "AGI": 13, "VIG": 17},
              "counters": {"vigor": {"current": 5, "max": 5}, "corruption": 0}},
}


def _make_world(tmp_path, slug, ruleset):
    world = tmp_path / "world-state"
    campaign = world / "campaigns" / slug
    campaign.mkdir(parents=True)
    (world / "active-campaign.txt").write_text(slug, encoding="utf-8")
    (campaign / "ruleset.json").write_text(json.dumps(ruleset), encoding="utf-8")
    return world


@pytest.fixture
def hyborian_world(tmp_path):
    return _make_world(tmp_path, "hyborian", HYBORIAN_RULESET)





def _save(world, payload):
    """Run `create` against `world`."""
    return subprocess.run(
        [sys.executable, str(NEW_CHARACTER), json.dumps(payload), "--replace"],
        capture_output=True, text=True, env={**os.environ, "GM_WORLD_STATE_BASE": str(world)},
    )


def _sheet(world):
    slug = (world / "active-campaign.txt").read_text(encoding="utf-8").strip()
    return json.loads((world / "campaigns" / slug / "character.json").read_text(encoding="utf-8"))


def test_attributes_are_in_the_stats_section(hyborian_world):
    r = _save(hyborian_world, CONAN)
    assert r.returncode == 0, r.stdout + r.stderr
    attributes = _sheet(hyborian_world)["stats"]["attributes"]
    assert attributes["STR"] == 18 and attributes["AGI"] == 13 and attributes["LOG"] == 12


def test_no_5e_fields_on_the_sheet(hyborian_world):
    _save(hyborian_world, CONAN)
    sheet = _sheet(hyborian_world)
    assert not {"saves", "hp", "ac"} & set(sheet) & set(sheet["stats"])


def test_kit_vitals_persist(hyborian_world):
    _save(hyborian_world, CONAN)
    sheet = _sheet(hyborian_world)
    assert sheet["stats"]["counters"] == {"vigor": {"current": 5, "max": 5}, "corruption": 0}


def test_kit_vitals_are_readable_and_modifiable(hyborian_world):
    _save(hyborian_world, CONAN)
    mgr = PlayerManager(str(hyborian_world))

    assert mgr.modify_vital(None, "vigor")["current"] == 5

    spent = mgr.modify_vital(None, "vigor", -2)
    assert spent["success"] and spent["current"] == 3 and spent["max"] == 5

    tainted = mgr.modify_vital(None, "corruption", +1)
    assert tainted["success"] and tainted["current"] == 1

    # Shape is preserved: the dict track stays a dict, the plain track stays plain.
    sheet = _sheet(hyborian_world)
    assert sheet["stats"]["counters"] == {"vigor": {"current": 3, "max": 5}, "corruption": 1}

    assert mgr.modify_vital(None, "vigor", set_value=5)["current"] == 5


def test_vitals_appear_in_show_output(hyborian_world):
    _save(hyborian_world, CONAN)
    mgr = PlayerManager(str(hyborian_world))
    mgr.modify_vital(None, "vigor", -2)
    mgr.modify_vital(None, "corruption", +1)

    summary = mgr.show_player("Conan")
    assert "Vigor: 3/5" in summary and "Corruption: 1" in summary


def test_undeclared_vital_is_refused(hyborian_world):
    _save(hyborian_world, CONAN)
    result = PlayerManager(str(hyborian_world)).modify_vital(None, "sanity", -1)
    assert result["success"] is False


def test_hp_is_refused_because_wounds_replaced_it(hyborian_world):
    _save(hyborian_world, CONAN)
    mgr = PlayerManager(str(hyborian_world))
    result = mgr.modify_vital(None, "hp", -8)
    assert result["success"] is False and "gm-body.sh" in result["error"]
    assert "hp" not in _sheet(hyborian_world)["stats"]


def test_every_vital_response_has_the_same_shape(hyborian_world):
    _save(hyborian_world, CONAN)
    mgr = PlayerManager(str(hyborian_world))

    vigor = mgr.modify_vital(None, "vigor", -2)
    read = mgr.modify_vital(None, "corruption")

    keys = {"success", "name", "vital", "current", "max"}
    assert keys <= vigor.keys() and keys <= read.keys()
