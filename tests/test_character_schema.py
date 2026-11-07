"""Tests for the character validator and kit-driven XP thresholds."""

import json
from pathlib import Path

from lib.player_manager import PlayerManager
from lib.schemas import validate_character


def _char(dcc_world):
    p = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "character.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_the_nine_attributes_validate():
    ok, errs = validate_character({"name": "X", "level": 1, "stats": {"STR": 12, "agi": 10}})
    assert ok, errs


def test_other_attributes_are_flagged():
    ok, errs = validate_character({"name": "X", "level": 1, "stats": {"strength": 1}})
    assert not ok and any("unknown attributes" in e for e in errs)


def test_xp_thresholds_delegate_to_kit(dcc_world, tmp_path):
    # Write an xp-levels kit into a copy and confirm thresholds come from it.
    ruleset = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "ruleset.json"
    ruleset.write_text(json.dumps({
        "name": "Custom",
        "progression": {"model": "xp-levels", "thresholds": [50, 120, 250]},
        "active_agents": [],
    }), encoding="utf-8")
    pm = PlayerManager(dcc_world)
    assert pm._xp_thresholds() == [0, 50, 120, 250]  # kit-driven, not the 5e table


def test_xp_thresholds_default_when_kit_not_xp_levels(dcc_world):
    # DCC ships resource-axis -> falls back to the default table (unchanged behavior).
    pm = PlayerManager(dcc_world)
    assert pm._xp_thresholds() == PlayerManager.DEFAULT_XP_THRESHOLDS


def test_flat_sheet_validates_directly(dcc_world):
    ok, errs = validate_character(_char(dcc_world))
    assert ok, errs


def test_nameless_traveler_validates_without_race_or_class():
    ok, errs = validate_character({"name": "A nameless traveler", "level": 1})
    assert ok, errs
