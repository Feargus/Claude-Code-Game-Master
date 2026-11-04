"""Tests for leveling: the default XP table, raising attributes and skills, and perks."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.player_manager import PlayerManager

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def campaign(isolated_world_state):
    directory = isolated_world_state / "campaigns" / "test"
    directory.mkdir()
    (isolated_world_state / "active-campaign.txt").write_text("test")
    (directory / "ruleset.json").write_text(json.dumps({"progression": {"model": "xp-levels"}}))
    (directory / "character.json").write_text(json.dumps({
        "name": "Fearghas", "level": 0, "stats": {"DFT": 10, "AGI": 11},
        "skills": {"Long guns": 2}}))
    return directory


def _sheet(campaign):
    return json.loads((campaign / "character.json").read_text())


def test_each_level_costs_100_more_than_the_last():
    assert PlayerManager.DEFAULT_XP_THRESHOLDS[:5] == [100, 300, 600, 1000, 1500]


def test_xp_levels_follow_the_table(campaign, isolated_world_state):
    mgr = PlayerManager(str(isolated_world_state))
    assert mgr.award_xp("Fearghas", 99)["new_level"] == 0
    result = mgr.award_xp("Fearghas", 565)            # 664 in total
    assert result["new_level"] == 3 and result["next_level_xp"] == 1000


def test_raise_attribute_goes_up_one_die_size(campaign, isolated_world_state):
    result = PlayerManager(str(isolated_world_state)).raise_stat("attribute", "dft")
    assert result["previous"] == 10 and result["current"] == 11
    assert _sheet(campaign)["stats"]["DFT"] == 11


def test_raise_attribute_refuses_unknown_or_missing(campaign, isolated_world_state):
    mgr = PlayerManager(str(isolated_world_state))
    assert mgr.raise_stat("attribute", "DEX")["success"] is False
    assert mgr.raise_stat("attribute", "NRV")["success"] is False   # no die on the sheet


def test_raise_skill_adds_one_and_keeps_the_sheets_spelling(campaign, isolated_world_state):
    PlayerManager(str(isolated_world_state)).raise_stat("skill", "long guns")
    assert _sheet(campaign)["skills"] == {"Long guns": 3}


def test_a_new_skill_starts_at_one(campaign, isolated_world_state):
    mgr = PlayerManager(str(isolated_world_state))
    assert mgr.raise_stat("skill", "Medicine")["current"] == 1
    assert mgr.raise_stat("skill", "default")["success"] is False


def test_perks_are_name_and_function(campaign, isolated_world_state):
    mgr = PlayerManager(str(isolated_world_state))
    mgr.set_perk("Night eyes", "+2 Awareness in the dark, -2 in bright light")
    assert mgr.set_perk("night eyes", "+3 in the dark")["replaced"] is True
    assert _sheet(campaign)["perks"] == {"Night eyes": "+3 in the dark"}


def test_wrapper_raise_and_perk(campaign):
    def run(*words):
        return subprocess.run(["bash", str(REPO / "tools" / "gm-player.sh"), *words],
                              capture_output=True, text=True, env=os.environ)
    assert "RAISED Fearghas AGI: d11 -> d12" in run("raise", "attribute", "AGI").stdout
    assert run("raise", "power", "AGI").returncode != 0
    assert "PERK Fearghas gained" in run("perk", "Grip", "+1 Athletics when climbing").stdout
