"""Tests for the generic game core: conditions and the three
progression models. No D&D 5e assumptions — thresholds/tiers are all supplied."""

from lib import game_core as gc


def test_conditions_add_remove_idempotent():
    c = gc.add_condition([], "poisoned")
    c = gc.add_condition(c, "poisoned")  # idempotent
    assert c == ["poisoned"]
    assert gc.remove_condition(c, "poisoned") == []


def test_milestone_progression():
    p = gc.make_progression("milestone")
    s = p.advance({})
    s = p.advance(s)
    assert p.level(s) == 2


def test_xp_levels_progression_uses_supplied_thresholds():
    p = gc.make_progression("xp-levels", thresholds=[100, 300, 600])
    s = p.advance({}, xp=150)
    assert p.level(s) == 2  # past 100, below 300
    s = p.advance(s, xp=500)  # total 650
    assert p.level(s) == 4


def test_resource_axis_progression():
    p = gc.make_progression("resource-axis", resource="viewers", tiers=[1_000_000, 1_000_000_000])
    s = p.advance({}, amount=2_000_000)
    assert p.level(s) == 1
    s = p.advance(s, amount=1_000_000_000)
    assert p.level(s) == 2


def test_no_5e_symbols_in_core():
    src = (gc.__file__)
    text = open(src, encoding="utf-8").read().lower()
    for banned in ("spell slot", "strength", "dexterity", "level 20", "proficiency"):
        assert banned not in text, f"core must stay 5e-agnostic; found {banned!r}"
