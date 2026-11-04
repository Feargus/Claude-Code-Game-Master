"""Tests for `gm-player.sh create`: the sheet with its defaults, and the wiring
(overwrite guard, --replace archiving, the overview, canon NPCs, the opening).
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.campaign_manager import CampaignManager
from lib.new_character import CharacterCreator
from lib.opening_seed import seed_opening
from lib.player_manager import PlayerManager

ROOT = Path(__file__).resolve().parent.parent
ATTRIBUTES = ("STR", "AGI", "DFT", "VIG", "LOG", "ITU", "NRV", "PRS", "EMP")
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


def _create(*args, data=None):
    words = [json.dumps(data)] if data is not None else []
    return subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh"), "create", *words, *args, "--json"],
                          capture_output=True, text=True, env=os.environ)


def _ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["data"]


def _error(result):
    assert result.returncode == 1
    return json.loads(result.stdout)["error"]


def _sheet(campaign):
    return json.loads((campaign / "character.json").read_text())


# --- The sheet ---

def test_a_name_alone_gets_every_default(campaign):
    sheet = _ok(_create(data={"name": "Mara"}))
    assert sheet == _sheet(campaign)
    assert sheet["level"] == 0 and sheet["xp"] == {"current": 0, "next_level": 100}
    assert sheet["stats"] == {a: 12 for a in ATTRIBUTES}
    assert sheet["luck"] == {"current": 3, "max": 3} and sheet["credits"] == 20
    assert sheet["traits"] == {} and sheet["perks"] == {} and sheet["features"] == []
    assert set(sheet["body"]) == {"head", "chest", "groin", "left_arm", "right_arm",
                                  "left_leg", "right_leg"}
    for gone in ("hp", "ac", "bonds", "flaws", "ideals", "saves"):
        assert gone not in sheet


def test_the_campaigns_counters_come_from_its_ruleset(campaign):
    assert _ok(_create(data={"name": "Mara"}))["drift"] == {"current": 0, "max": 10}


def test_a_counter_without_a_track_is_a_plain_number(campaign):
    (campaign / "ruleset.json").write_text(json.dumps(dict(RULESET, stat_schema={"vitals": ["heat"]})))
    sheet = _ok(_create(data={"name": "Mara", "heat": 2}))
    assert sheet["heat"] == 2 and "drift" not in sheet


def test_given_values_are_kept_whatever_they_are(campaign):
    sheet = _ok(_create(data={
        "name": "Mara", "race": "AI", "class": "anything at all",
        "attributes": {"agi": 18, "LOG": 6}, "skills": {"Piloting": 5}, "luck": 1,
        "traits": {"Vat-grown": "+2 Endurance, -2 Composure"}, "level": 2}))
    assert sheet["stats"]["AGI"] == 18 and sheet["stats"]["LOG"] == 6
    assert sheet["skills"] == {"Piloting": 5} and sheet["luck"] == {"current": 1, "max": 1}
    assert sheet["traits"] == {"Vat-grown": "+2 Endurance, -2 Composure"}
    assert sheet["xp"]["next_level"] == 600


def test_armor_and_cyberware_land_on_the_body(campaign):
    sheet = _ok(_create(data={
        "name": "Mara",
        "armor": [{"name": "Long coat", "zones": {"chest": 1, "left_arm": 1}},
                  {"name": "Vest", "zones": {"chest": 2}}],
        "cyberware": [{"name": "Cybereye", "zone": "head", "effect": "zoom"}]}))
    assert [a["name"] for a in sheet["armor"]] == ["Long coat", "Vest"]   # outermost first
    assert sheet["armor"][1]["zones"]["chest"] == {"boxes": 2, "damage": 0}
    assert sheet["cyberware"][0]["boxes"] == 1


def test_left_out_attributes_are_named_in_the_human_output(campaign):
    result = subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh"), "create",
                             json.dumps({"name": "Mara", "attributes": {"AGI": 14}})],
                            capture_output=True, text=True, env=os.environ)
    assert "Mara enters the world" in result.stdout
    assert "default d12: STR, DFT" in result.stdout


@pytest.mark.parametrize("data, message", [
    ({}, "name"),
    ({"name": "Mara", "attributes": {"DEX": 12}}, "Unknown attribute"),
    ({"name": "Mara", "attributes": {"AGI": 1}}, "die size"),
    ({"name": "Mara", "cyberware": [{"name": "Tail", "zone": "tail"}]}, "Unknown zone"),
    ({"name": "Mara", "skills": {"default": 2}}, "not a skill"),
])
def test_refusals_leave_no_sheet(campaign, data, message):
    assert message in _error(_create(data=data))
    assert not (campaign / "character.json").exists()


# --- The wiring ---

def test_an_existing_character_is_not_overwritten(campaign):
    _ok(_create(data={"name": "Mara"}))
    assert "already plays" in _error(_create(data={"name": "Vex"}))
    assert _sheet(campaign)["name"] == "Mara"


def test_replace_archives_the_old_character(campaign):
    _ok(_create(data={"name": "Mara"}))
    _ok(_create("--replace", data={"name": "Vex"}))
    assert _sheet(campaign)["name"] == "Vex"
    assert json.loads((campaign / "fallen" / "mara-mara.json").read_text())["name"] == "Mara"


def test_the_overview_records_the_character(campaign):
    _ok(_create(data={"name": "Mara"}))
    overview = json.loads((campaign / "campaign-overview.json").read_text())
    assert overview["current_character"] == "Mara"


def test_canon_resolves_the_npc_and_marks_it_as_the_player(dcc_world):
    env = {**os.environ, "GM_WORLD_STATE_BASE": str(dcc_world)}
    result = subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh"), "create",
                             json.dumps({"name": "whatever", "class": "game guide"}),
                             "--canon", "mordecai", "--replace", "--json"],
                            capture_output=True, text=True, env=env)
    assert _ok(result)["name"] == "Mordecai"
    npc = json.loads((Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "npcs.json")
                     .read_text())["Mordecai"]
    assert npc["is_player_character"] is True and npc["became_pc"] is True


def test_canon_unknown_npc_is_refused(campaign):
    assert "Nobody" in _error(_create("--canon", "Nobody", data={"name": "Nobody"}))


def test_first_character_reseeds_the_opening(isolated_world_state):
    from tests.test_opening_seed import PIRATE_PLOT, _setup_two_arcs

    cm = CampaignManager()
    cdir = cm.create("Hyboria", "Hyboria")
    assert cm.set_active("Hyboria")
    _setup_two_arcs(cdir)
    seed_opening(str(cdir), timestamp="2026-01-01T00:00:00Z")

    result = CharacterCreator().create(
        {"name": "Conan", "background": "pirate-era sailor on the Black Coast"})
    assert result["success"]

    ov = json.loads((cdir / "campaign-overview.json").read_text())
    assert ov["current_character"] == "Conan" and ov.get("opening_matched_to_pc") is True
    assert ov["player_position"]["current_location"] == "The Tigress"
    assert (ov.get("opening_hook") or {}).get("plot") == PIRATE_PLOT

    # A later set must not rewrite a PC-matched opening.
    ov["player_position"]["current_location"] = "WRONG"
    (cdir / "campaign-overview.json").write_text(json.dumps(ov), encoding="utf-8")
    assert PlayerManager().set_current_player("Conan")
    ov = json.loads((cdir / "campaign-overview.json").read_text())
    assert ov["player_position"]["current_location"] == "WRONG"


def test_replace_does_not_reseed_a_matched_opening(isolated_world_state):
    from tests.test_opening_seed import _setup_two_arcs

    cm = CampaignManager()
    cdir = cm.create("Hyboria", "Hyboria")
    assert cm.set_active("Hyboria")
    _setup_two_arcs(cdir)
    seed_opening(str(cdir), timestamp="2026-01-01T00:00:00Z")
    assert CharacterCreator().create(
        {"name": "Conan", "background": "pirate-era sailor on the Black Coast"})["success"]

    ov = json.loads((cdir / "campaign-overview.json").read_text())
    ov["player_position"]["current_location"] = "WRONG"
    (cdir / "campaign-overview.json").write_text(json.dumps(ov), encoding="utf-8")
    log_before = (cdir / "session-log.md").read_text()

    assert CharacterCreator().create(
        {"name": "Valeria", "background": "a thief of Aquilonia"}, replace=True)["success"]
    ov = json.loads((cdir / "campaign-overview.json").read_text())
    assert ov["current_character"] == "Valeria"
    assert ov["player_position"]["current_location"] == "WRONG"
    assert (cdir / "session-log.md").read_text() == log_before
