"""Tests for the fight tracker: each enemy's wounds and notes survive a resume."""

from lib.combat_manager import CombatManager


def test_start_and_add_enemy(dcc_world):
    m = CombatManager(dcc_world)
    m.start()
    c = m.add_combatant("street thug 1", 2)
    assert c["wounds"] == 2 and c["taken"] == 0
    assert m.is_active()


def test_wounds_survive_a_simulated_resume(dcc_world):
    m = CombatManager(dcc_world)
    m.start()
    m.add_combatant("corp guard 1", 2)
    m.wound("corp guard 1", 1, note="right arm disabled")
    # New manager instance = fresh load from disk (simulates resume/compaction).
    resumed = CombatManager(dcc_world)
    c = resumed._find(resumed._load(), "corp guard 1")
    assert c["taken"] == 1 and c["notes"] == ["right arm disabled"]


def test_wounds_stop_at_the_limit_and_mark_defeated(dcc_world):
    m = CombatManager(dcc_world)
    m.start()
    m.add_combatant("rat 1", 1)
    m.add_combatant("rat 2", 1)
    assert m.wound("rat 1", 5)["taken"] == 1
    assert "rat 1: ●, out" in m.header()
    assert m.end()["defeated"] == ["rat 1"]


def test_header_shows_boxes_notes_and_conditions(dcc_world):
    m = CombatManager(dcc_world)
    m.start()
    m.add_combatant("ganger 1", 2)
    m.wound("ganger 1", note="left leg disabled")
    m.set_condition("ganger 1", "add", "prone")
    assert "ganger 1: ●○ (left leg disabled, prone)" in m.header()


def test_unknown_enemy_is_none(dcc_world):
    m = CombatManager(dcc_world)
    m.start()
    assert m.wound("nobody") is None


def test_end_clears_state(dcc_world):
    m = CombatManager(dcc_world)
    m.start()
    m.add_combatant("Orc", 2)
    m.end()
    assert not CombatManager(dcc_world).is_active()


def test_combat_is_optional(dcc_world):
    # Never starting combat is a valid state (narrated skirmish).
    assert CombatManager(dcc_world).is_active() is False
    assert CombatManager(dcc_world).header() == "No fight running."


def test_start_refuses_while_a_fight_is_running(dcc_world):
    """Starting over wiped the running fight without a word: an enemy already
    taken out was gone, and `end` paid no XP for it."""
    import os
    import subprocess
    from pathlib import Path

    import pytest
    m = CombatManager(dcc_world)
    m.start()
    m.start()                                    # an empty fight may be started again
    m.add_combatant("rat 1", 1)
    m.add_combatant("rat 2", 1)
    m.wound("rat 1", 1)
    with pytest.raises(ValueError, match="A fight is running \\(rat 1, rat 2\\)"):
        m.start()
    tool = Path(__file__).resolve().parent.parent / "tools" / "gm-combat.sh"
    result = subprocess.run(["bash", str(tool), "start"], capture_output=True, text=True,
                            env=dict(os.environ, GM_WORLD_STATE_BASE=dcc_world))
    assert result.returncode == 1 and "[ERROR] A fight is running" in result.stderr
    assert "gm-combat.sh end" in result.stderr
    assert m.end()["defeated"] == ["rat 1"]      # the fight is as it was
    m.start()                                    # after `end`, a new one starts


def test_each_command_says_what_it_did(dcc_world):
    """A fight just begun said "(no active combat)" (the What Remains playtest): each
    command's first line now says what it did, then the enemies, one line each."""
    import os
    import subprocess
    from pathlib import Path
    tool = Path(__file__).resolve().parent.parent / "tools" / "gm-combat.sh"
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(tool), *words], capture_output=True, text=True, env=env)
    assert run("header").stdout == "No fight running.\n"
    assert run("start").stdout.startswith("[SUCCESS] A fight has begun; add each enemy: bash tools/")
    assert run("header").stdout.startswith("A fight has begun, with no enemies yet")
    assert run("add-enemy", "rat 1", "1").stdout.splitlines() == [
        "[SUCCESS] rat 1 joins the fight (1 wound take them out)", "  rat 1: ○"]
    assert run("add-enemy", "rat 2", "2").stdout.splitlines()[0] == (
        "[SUCCESS] rat 2 joins the fight (2 wounds take them out)")
    assert run("condition", "rat 2", "add", "prone").stdout.splitlines() == [
        "[SUCCESS] prone added to rat 2", "  rat 1: ○", "  rat 2: ○○ (prone)"]
    assert run("wound", "rat 1").stdout.splitlines()[0] == "[SUCCESS] rat 1: 1 of 1 wounds, out"
    missing = run("wound", "rat 3")
    assert missing.returncode == 1 and "'rat 3' isn't in the fight (in it: rat 1, rat 2)" in missing.stderr
    ended = run("end").stdout.splitlines()               # the test character has growth due
    assert ended[0] == "[SUCCESS] The fight is over. Taken out: rat 1; +10 XP"
    assert ended[1].startswith("[DO] Growth due (") and len(ended) == 2
