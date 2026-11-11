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


def test_flat_sheet_validates_directly(dcc_world):
    ok, errs = validate_character(_char(dcc_world))
    assert ok, errs


def test_nameless_traveler_validates_without_race_or_class():
    ok, errs = validate_character({"name": "A nameless traveler", "level": 1})
    assert ok, errs
