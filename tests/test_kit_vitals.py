"""Tests for character-save-kit-vitals: saving a PC and tracking vitals honors the
active World Kit instead of hardcoding D&D 5e.

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
SAVE_CHARACTER = ROOT / "features" / "character-creation" / "save_character.py"

HYBORIAN_RULESET = {
    "name": "The Hyborian Age",
    "kit": "hyborian",
    "stat_schema": {
        "attributes": ["might", "guile", "grit"],
        "vitals": ["hp", "vigor", "corruption"],
    },
    "progression": {"model": "milestone"},
    "active_agents": [],
}


CONAN = {
    "name": "Conan",
    "race": "Cimmerian",
    "class": "Reaver",
    "level": 6,
    "attributes": {"might": 18, "guile": 13, "grit": 17},
    "hp": {"current": 58, "max": 58},
    "vigor": {"current": 5, "max": 5},
    "corruption": 0,
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
    """Run save_character.py against `world` (it resolves world-state from cwd)."""
    return subprocess.run(
        [sys.executable, str(SAVE_CHARACTER), json.dumps(payload)],
        capture_output=True, text=True, cwd=str(world.parent), env={**os.environ},
    )


def _sheet(world):
    slug = (world / "active-campaign.txt").read_text(encoding="utf-8").strip()
    return json.loads((world / "campaigns" / slug / "character.json").read_text(encoding="utf-8"))


def test_attributes_is_the_stat_key(hyborian_world):
    r = _save(hyborian_world, CONAN)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _sheet(hyborian_world)["stats"] == CONAN["attributes"]


def test_stats_is_still_accepted_as_a_legacy_alias(hyborian_world):
    legacy = {k: v for k, v in CONAN.items() if k != "attributes"}
    legacy["stats"] = CONAN["attributes"]
    r = _save(hyborian_world, legacy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _sheet(hyborian_world)["stats"] == CONAN["attributes"]


def test_authored_max_hp_is_preserved(hyborian_world):
    _save(hyborian_world, CONAN)
    hp = _sheet(hyborian_world)["hp"]
    assert hp["max"] == 58 and hp["current"] == 58


def test_no_5e_save_block_on_a_non_dnd5e_sheet(hyborian_world):
    _save(hyborian_world, CONAN)
    assert "saves" not in _sheet(hyborian_world)


def test_kit_vitals_persist(hyborian_world):
    _save(hyborian_world, CONAN)
    sheet = _sheet(hyborian_world)
    assert sheet["vigor"] == {"current": 5, "max": 5}
    assert sheet["corruption"] == 0


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
    assert sheet["vigor"] == {"current": 3, "max": 5}
    assert sheet["corruption"] == 1

    assert mgr.modify_vital(None, "vigor", set_value=5)["current"] == 5


def test_vitals_appear_in_show_output(hyborian_world):
    _save(hyborian_world, CONAN)
    mgr = PlayerManager(str(hyborian_world))
    mgr.modify_vital(None, "vigor", -2)
    mgr.modify_vital(None, "corruption", +1)

    summary = mgr.show_player("Conan")
    assert "Vigor: 3/5" in summary and "Corruption: 1" in summary
    assert "Vigor: 3/5" in mgr.show_all_players()[0]


def test_undeclared_vital_is_refused(hyborian_world):
    _save(hyborian_world, CONAN)
    result = PlayerManager(str(hyborian_world)).modify_vital(None, "sanity", -1)
    assert result["success"] is False


def test_hp_is_refused_because_wounds_replaced_it(hyborian_world):
    _save(hyborian_world, CONAN)
    mgr = PlayerManager(str(hyborian_world))
    result = mgr.modify_vital(None, "hp", -8)
    assert result["success"] is False and "gm-body.sh" in result["error"]
    assert _sheet(hyborian_world)["hp"]["current"] == 58


def test_every_vital_response_has_the_same_shape(hyborian_world):
    _save(hyborian_world, CONAN)
    mgr = PlayerManager(str(hyborian_world))

    vigor = mgr.modify_vital(None, "vigor", -2)
    read = mgr.modify_vital(None, "corruption")

    keys = {"success", "name", "vital", "current", "max"}
    assert keys <= vigor.keys() and keys <= read.keys()


def test_non_dnd5e_missing_hp_warns_and_defaults_to_10(hyborian_world):
    """Unauthored HP on a non-dnd5e kit persists 10/10 and names the fallback."""
    payload = {k: v for k, v in CONAN.items() if k != "hp"}
    r = _save(hyborian_world, payload)
    assert r.returncode == 0, r.stdout + r.stderr
    result = json.loads(r.stdout)
    assert _sheet(hyborian_world)["hp"] == {"current": 10, "max": 10}
    warnings = result["warnings"]
    assert isinstance(warnings, list) and warnings
    assert any("10/10" in w for w in warnings)
    assert any("author" in w.lower() for w in warnings)
