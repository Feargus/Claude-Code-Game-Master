"""Stat blocks for NPCs and mobs (gm-npc.sh stats, gm-mob.sh), checked before they
are saved, and enemies in a fight that read their wounds from them (--as). In play
the GM wrote these into npcs.json and mobs.json by hand."""

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from lib.combat_manager import CombatManager
from lib.npc_manager import NPCManager
from lib.skill_contest import build_side
from lib.stat_block import Mobs, canon_skills, common_skills, merged

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def world(tmp_path):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    for name, payload in {
            "campaign-overview.json": {"campaign_name": "C"},
            "character.json": {"name": "Cass", "stats": {"STR": 10}},
            "npcs.json": {"Rook": {"description": "Asset Recovery",
                                   "stats": {"hp": 10, "STR": 11}}},
            "locations.json": {}}.items():
        (camp / name).write_text(json.dumps(payload))
    return str(ws), camp


def _npcs(camp):
    return json.loads((camp / "npcs.json").read_text())


def test_canon_skills_come_from_the_gm_skills_index():
    skills = canon_skills()
    assert len(skills) == 31 and "Long guns" in skills and "Skill" not in skills
    common = common_skills()
    assert len(common) == 14 and "Guard" in common and "Handguns" not in common


def test_the_example_mobs_have_the_common_skills():
    """Like a starting character (2026-11-11): every common skill at 0 or more, so the
    scale doesn't make a thug worse at noticing things than anyone else (untrained −3)."""
    mobs = json.loads((ROOT / ".claude" / "skills" / "gm-skills" / "mobs.json").read_text())
    for name, mob in mobs.items():
        for skill in common_skills():
            assert mob["skills"].get(skill, -1) >= 0, (name, skill)
    assert mobs["combat merc"]["skills"]["Guard"] == 5 and mobs["rat"]["skills"]["Persuasion"] == 0


def test_npc_stats_are_set_merged_and_rolled(world):
    ws, camp = world
    manager = NPCManager(ws)
    result = manager.set_stats("rook", {"STR": 12, "agi": 11, "default": 10},
                               {"handguns": 4, "Guard": 3}, wounds=3)
    assert result["name"] == "Rook" and result["warnings"] == []
    rook = _npcs(camp)["Rook"]
    assert rook["attributes"] == {"STR": 12, "AGI": 11, "default": 10}
    assert rook["stats"] == {"hp": 10}          # upstream's numbers stay as they were
    assert rook["skills"] == {"Handguns": 4, "Guard": 3}  # canon spelling
    manager.set_stats("Rook", skills={"Insight": 2}, remove_skills=["guard"])
    rook = _npcs(camp)["Rook"]
    assert rook["skills"] == {"Handguns": 4, "Insight": 2} and rook["wounds"] == 3
    side = build_side(camp, ["Rook", "Handguns", "DFT", "STR", "ITU"], None, None)
    assert side["dice_sizes"] == {"DFT": 10, "STR": 12, "ITU": 10} and side["skill_value"] == 4


def test_bad_values_are_refused_and_odd_ones_warned(world):
    ws, camp = world
    manager = NPCManager(ws)
    for kwargs, why in [({"attrs": {"LUCK": 12}}, "Unknown attribute"),
                        ({"attrs": {"STR": 1}}, "at least 2"),
                        ({"wounds": 0}, "wounds: at least 1")]:
        with pytest.raises(ValueError, match=why):
            manager.set_stats("Rook", **kwargs)
    with pytest.raises(ValueError, match="no skill 'Tact'"):
        manager.set_stats("Rook", remove_skills=["Tact"])
    with pytest.raises(ValueError, match="not found"):
        manager.set_stats("Nobody", wounds=2)
    warnings = manager.set_stats("Rook", {"STR": 30}, {"Tecch": 2})["warnings"]
    assert any("d30 is outside" in w for w in warnings)
    assert any("'Tecch' is not a canon skill. Did you mean Tech?" in w for w in warnings)
    (camp / "improvised-skills.md").write_text("## Ratcatching\nstatus: improvised\n")
    assert manager.set_stats("Rook", skills={"Ratcatching": 1},
                             remove_skills=["Tecch"])["warnings"] == [
        "STR d30 is outside the usual d4–d24 (fine if meant)."]


def test_mobs_are_added_checked_and_kept_apart_from_npcs(world):
    ws, camp = world
    mobs = Mobs(ws)
    entry = merged({}, {"STR": 18, "default": 10}, {"Brawling": 6}, wounds=6, note="a war-dog")
    assert mobs.save("Mastiff", entry, create=True) == []
    with pytest.raises(ValueError, match="exists already"):
        mobs.save("mastiff", entry, create=True)
    with pytest.raises(ValueError, match="is npc:Rook"):
        mobs.save("Rook", entry, create=True)
    with pytest.raises(ValueError, match="needs --note"):
        mobs.save("Hound", merged({}, {"STR": 12}, wounds=1), create=True)
    with pytest.raises(ValueError, match="repo's example mobs, which stay"):
        mobs.save("street thug", entry, create=False)
    warnings = mobs.save("street thug", entry, create=True)
    assert "this campaign's version wins" in warnings[0]
    stored = json.loads((camp / "mobs.json").read_text())
    assert stored["Mastiff"]["attributes"] == {"STR": 18, "default": 10}


def test_enemies_read_their_wounds_from_the_sheet(world):
    ws, camp = world
    NPCManager(ws).set_stats("Rook", wounds=3)
    combat = CombatManager(ws)
    assert combat.add_combatant("thug 1", sheet="street thug")["wounds"] == 2  # repo mob
    assert combat.add_combatant("Rook", sheet="rook")["wounds"] == 3
    with pytest.raises(ValueError, match="already a line"):
        combat.add_combatant("thug 1", sheet="street thug")
    with pytest.raises(ValueError, match="Give the wounds, or --as"):
        combat.add_combatant("thug 2")
    with pytest.raises(ValueError, match="gm-body.sh"):
        combat.add_combatant("me", sheet="Cass")
    with pytest.raises(ValueError, match="Unknown name"):
        combat.add_combatant("x", sheet="Nobody")
    assert "thug 1 [rolls as street thug]: ○○" in combat.header()


def test_cli(world):
    ws, camp = world

    def run(script, *args):
        return subprocess.run([sys.executable, str(ROOT / "lib" / script), *args],
                              capture_output=True, text=True, cwd=str(Path(ws).parent))

    r = run("npc_manager.py", "stats", "Rook", "--attr", "STR=12", "--skill", "Handguns=4",
            "--wounds", "3")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "attributes: STR d12" in r.stdout and "wounds: 3" in r.stdout
    assert run("npc_manager.py", "stats", "Rook", "--attr", "STR").returncode == 1
    r = run("stat_block.py", "add", "Mastiff", "--note", "a war-dog", "--attr", "default=12",
            "--wounds", "6")
    assert r.returncode == 0, r.stderr
    assert "street thug" in run("stat_block.py", "list").stdout
    r = run("combat_manager.py", "add-enemy", "Mastiff", "--as", "Mastiff")
    assert r.returncode == 0 and "Mastiff: ○○○○○○" in r.stdout
