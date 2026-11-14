"""Tests for the generic game core: conditions and the three
progression models. No D&D 5e assumptions — thresholds/tiers are all supplied."""

from lib import game_core as gc


def test_conditions_add_remove_idempotent():
    c = gc.add_condition([], "poisoned")
    c = gc.add_condition(c, "poisoned")  # idempotent
    assert c == ["poisoned"]
    assert gc.remove_condition(c, "poisoned") == []








def test_no_5e_symbols_in_core():
    src = (gc.__file__)
    with open(src, encoding="utf-8") as f:
        text = f.read().lower()
    for banned in ("spell slot", "strength", "dexterity", "level 20", "proficiency"):
        assert banned not in text, f"core must stay 5e-agnostic; found {banned!r}"
