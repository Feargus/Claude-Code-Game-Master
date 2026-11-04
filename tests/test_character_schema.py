"""Tests for the character validator (kit-aware) and kit-driven XP thresholds."""

import json
from pathlib import Path

from lib.player_manager import PlayerManager
from lib.schemas import validate_character
from lib.world_kit import WorldKit


def _char(dcc_world):
    p = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "character.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_non_5e_kit_with_custom_attributes_validates():
    paul = {"name": "Paul Atreides", "level": 1,
            "stats": {"prescience": 5, "spice_tolerance": 3}}

    class DuneKit:
        def stat_schema(self):
            return {"attributes": ["prescience", "spice_tolerance"]}

    ok, errs = validate_character(paul, DuneKit())
    assert ok, errs


def test_attributes_outside_kit_schema_are_flagged():
    char = {"name": "X", "level": 1, "stats": {"strength": 1}}

    class DuneKit:
        def stat_schema(self):
            return {"attributes": ["prescience"]}

    ok, errs = validate_character(char, DuneKit())
    assert not ok and any("not in active kit" in e for e in errs)


def test_xp_thresholds_delegate_to_kit(dcc_world, tmp_path):
    # Write an xp-levels kit into a copy and confirm thresholds come from it.
    ruleset = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "ruleset.json"
    ruleset.write_text(json.dumps({
        "name": "Custom", "stat_schema": {"attributes": []},
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
    ok, errs = validate_character(_char(dcc_world), WorldKit(dcc_world))
    assert ok, errs


def test_nameless_traveler_validates_without_race_or_class():
    ok, errs = validate_character({"name": "A nameless traveler", "level": 1})
    assert ok, errs
