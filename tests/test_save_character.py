"""Tests for saving a new character: defaults for everything left out, the
campaign's own counters, and the body with armor and cyberware."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAVE = ROOT / "features" / "character-creation" / "save_character.py"

RULESET = {
    "stat_schema": {"vitals": ["drift"]},
    "progression": {"model": "xp-levels"},
    "systems": [{"primitive": "named_track", "name": "Drift", "config": {"max": 10}}],
}


@pytest.fixture
def campaign(isolated_world_state):
    directory = isolated_world_state / "campaigns" / "test"
    directory.mkdir()
    (isolated_world_state / "active-campaign.txt").write_text("test")
    (directory / "ruleset.json").write_text(json.dumps(RULESET))
    return directory


def _save(payload):
    return subprocess.run([sys.executable, str(SAVE), json.dumps(payload)],
                          capture_output=True, text=True, env=os.environ)


def _sheet(campaign):
    return json.loads((campaign / "character.json").read_text())


def test_a_name_alone_gets_every_default(campaign):
    result = _save({"name": "Mara"})
    assert result.returncode == 0, result.stdout + result.stderr
    sheet = _sheet(campaign)
    assert sheet["level"] == 0 and sheet["xp"] == {"current": 0, "next_level": 100}
    assert sheet["stats"] == {a: 12 for a in
                              ("STR", "AGI", "DFT", "VIG", "LOG", "ITU", "NRV", "PRS", "EMP")}
    assert sheet["luck"] == {"current": 3, "max": 3}
    assert sheet["gold"] == 20
    assert sheet["traits"] == {} and sheet["perks"] == {} and sheet["features"] == []
    assert set(sheet["body"]) == {"head", "chest", "groin", "left_arm", "right_arm",
                                  "left_leg", "right_leg"}
    for gone in ("hp", "ac", "bonds", "flaws", "ideals", "saves"):
        assert gone not in sheet
    assert "attributes set to the default d12" in json.loads(result.stdout)["warnings"][0]


def test_the_campaigns_counters_come_from_its_ruleset(campaign):
    _save({"name": "Mara"})
    assert _sheet(campaign)["drift"] == {"current": 0, "max": 10}


def test_a_counter_without_a_track_is_a_plain_number(campaign):
    ruleset = dict(RULESET, stat_schema={"vitals": ["heat"]})
    (campaign / "ruleset.json").write_text(json.dumps(ruleset))
    _save({"name": "Mara", "heat": 2})
    sheet = _sheet(campaign)
    assert sheet["heat"] == 2 and "drift" not in sheet


def test_given_values_are_kept_whatever_they_are(campaign):
    _save({"name": "Mara", "race": "AI", "class": "anything at all",
           "attributes": {"agi": 18, "LOG": 6}, "skills": {"Piloting": 5}, "luck": 1,
           "traits": {"Vat-grown": "+2 Endurance, -2 Composure"}, "level": 2})
    sheet = _sheet(campaign)
    assert sheet["stats"]["AGI"] == 18 and sheet["stats"]["LOG"] == 6
    assert sheet["skills"] == {"Piloting": 5} and sheet["luck"] == {"current": 1, "max": 1}
    assert sheet["traits"] == {"Vat-grown": "+2 Endurance, -2 Composure"}
    assert sheet["xp"]["next_level"] == 600


def test_armor_and_cyberware_land_on_the_body(campaign):
    _save({"name": "Mara",
           "armor": [{"name": "Long coat", "zones": {"chest": 1, "left_arm": 1}},
                     {"name": "Vest", "zones": {"chest": 2}}],
           "cyberware": [{"name": "Cybereye", "zone": "head", "effect": "zoom"}]})
    sheet = _sheet(campaign)
    assert [a["name"] for a in sheet["armor"]] == ["Long coat", "Vest"]   # outermost first
    assert sheet["armor"][1]["zones"]["chest"] == {"boxes": 2, "damage": 0}
    assert sheet["cyberware"][0]["boxes"] == 1


@pytest.mark.parametrize("payload, message", [
    ({}, "name"),
    ({"name": "Mara", "attributes": {"DEX": 12}}, "Unknown attribute"),
    ({"name": "Mara", "attributes": {"AGI": 1}}, "die size"),
    ({"name": "Mara", "cyberware": [{"name": "Tail", "zone": "tail"}]}, "Unknown zone"),
    ({"name": "Mara", "skills": {"default": 2}}, "not a skill"),
])
def test_refusals(campaign, payload, message):
    result = _save(payload)
    assert result.returncode == 1
    assert message in json.loads(result.stdout)["error"]
    assert not (campaign / "character.json").exists()
