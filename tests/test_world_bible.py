"""Tests for world-bible-schema: structured fidelity spine (voice/factions/geography/...)."""

from lib.world_bible import WorldBible, validate_bible


def test_dcc_bible_loads_and_validates(dcc_world):
    wb = WorldBible(dcc_world)
    assert wb.exists()
    ok, errs = wb.validate()
    assert ok, errs
    assert wb.bible["name"] == "Dungeon Crawler Carl"


def test_geography_parses_as_a_graph(dcc_world):
    geo = WorldBible(dcc_world).geography()
    assert {n["id"] for n in geo["nodes"]} >= {"floor1", "floor4"}
    assert any("stairwell" in e["adjacency"] for e in geo["edges"])


def test_voice_present_and_the_rules_not_required(dcc_world):
    """The world's own rules are the ruleset's (world_rules.py), not the bible's."""
    wb = WorldBible(dcc_world)
    assert wb.voice().get("style")
    bible = dict(wb.bible)
    bible.pop("signature_systems", None)
    assert validate_bible(bible) == (True, [])


def test_validator_rejects_missing_graph():
    bad = {"name": "X", "voice": {}, "tone": "t", "themes": [], "geography": {"nodes": []}}
    ok, errs = validate_bible(bad)
    assert not ok and any("geography must be a graph" in e for e in errs)


def test_the_bible_has_no_factions():
    """The factions and their ties are in factions.json (design-notes.md, "Factions")."""
    new = {"name": "X", "voice": {}, "tone": "t", "themes": [],
           "geography": {"nodes": [], "edges": []}}
    assert validate_bible(new) == (True, [])
