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
    assert CombatManager(dcc_world).header() == "(no active combat)"
