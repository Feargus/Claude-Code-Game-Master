"""Tests for growth: XP awards, growth that becomes due, applying it (grow), and the
hand corrections raise and perk."""

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
    (directory / "character.json").write_text(json.dumps({
        "name": "Fearghas", "level": 0, "stats": {"DFT": 10, "AGI": 11},
        "skills": {"Long guns": 2}}))
    return directory


def _sheet(campaign):
    return json.loads((campaign / "character.json").read_text())


def test_xp_makes_growth_due_and_logs_it(campaign, isolated_world_state):
    mgr = PlayerManager(str(isolated_world_state))
    assert mgr.award_xp("Fearghas", 99)["growth_due"] == 0
    result = mgr.award_xp("Fearghas", 565, "fight", "a test")        # 664 in total
    assert result["growth_due"] == 2                                  # level 2 needs 400
    sheet = _sheet(campaign)
    assert sheet["level"] == 0 and sheet["xp"] == {"current": 664, "next_level": 100}
    assert "+565 XP  fight: a test" in (campaign / "xp.log").read_text()


def test_achievements_are_a_share_of_the_current_level(campaign, isolated_world_state):
    mgr = PlayerManager(str(isolated_world_state))
    assert mgr.award(None, "small", "picked the lock")["xp_gained"] == 20     # 20 % of 100
    assert mgr.award(None, "large", "the job is done")["xp_gained"] == 100
    assert mgr.award(None, "huge", "x")["success"] is False
    assert mgr.award(None, "small", "")["success"] is False                    # a reason is required


def test_grow_applies_exactly_one_level(campaign, isolated_world_state):
    mgr = PlayerManager(str(isolated_world_state))
    assert mgr.grow("AGI", ["Long guns", "Stealth"], "Cat eyes", "+2 Awareness at night")["success"] is False
    mgr.award_xp("Fearghas", 400)                                     # level 2 is due: two growths
    for attribute, skills, why in [("DEX", ["Long guns", "Stealth"], "Unknown attribute"),
                                   ("NRV", ["Long guns", "Stealth"], "no die"),
                                   ("AGI", ["Long guns"], "exactly two"),
                                   ("AGI", ["Stealth", "stealth"], "exactly two")]:
        assert why in mgr.grow(attribute, skills, "Cat eyes", "x")["error"]
    assert "perk" in mgr.grow("AGI", ["Long guns", "Stealth"], "", "")["error"]
    result = mgr.grow("agi", ["long guns", "stealth"], "Cat eyes", "+2 Awareness at night, -2 by day")
    assert result["success"] and result["level"] == 1
    sheet = _sheet(campaign)
    assert sheet["stats"]["AGI"] == 12 and sheet["skills"] == {"Long guns": 3, "Stealth": 1}
    assert sheet["perks"] == {"Cat eyes": "+2 Awareness at night, -2 by day"}
    assert sheet["xp"]["next_level"] == 400
    assert "already" in mgr.grow("DFT", ["Tech", "Stealth"], "cat eyes", "x")["error"]
    assert mgr.grow("DFT", ["Tech", "Stealth"], "Steady hand", "+1 Tech")["level"] == 2
    assert mgr.grow("DFT", ["Tech", "Stealth"], "One more", "x")["success"] is False   # nothing due
    log = (campaign / "xp.log").read_text()
    assert "growth applied: level 1: AGI d11 -> d12; Long guns 2 -> 3; Stealth new -> 1" in log


def test_the_brief_tells_the_gm_when_growth_is_due(campaign, isolated_world_state):
    from lib.session_manager import SessionManager
    (campaign / "campaign-overview.json").write_text(json.dumps({"campaign_name": "T"}))
    assert "Growth due" not in SessionManager(str(isolated_world_state)).get_full_context()
    PlayerManager(str(isolated_world_state)).award_xp("Fearghas", 100)
    assert "Growth due: 1 level, at the next quiet moment" in \
        SessionManager(str(isolated_world_state)).get_full_context()


def test_ending_a_fight_pays_for_each_enemy_taken_out(campaign, isolated_world_state):
    from lib.combat_manager import CombatManager
    combat = CombatManager(str(isolated_world_state))
    combat.add_combatant("Mastiff", 6)
    combat.add_combatant("thug 1", 2)
    combat.add_combatant("thug 2", 2)
    combat.wound("Mastiff", 6)
    combat.wound("thug 1", 2)                                         # thug 2 got away
    summary = combat.end()
    assert summary["xp"] == 360 + 40 and summary["growth_due"] == 2
    assert _sheet(campaign)["xp"]["current"] == 400
    assert "defeated Mastiff (6 wounds)" in (campaign / "xp.log").read_text()


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
