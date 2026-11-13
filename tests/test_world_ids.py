"""Ids for what a fact can be about or held by (lib/world_ids.py).

One resolver for player, npc:, location:, street and public. Input is
forgiving, the stored id is the exact key, and anything unknown is refused
with close matches.
"""

import json
from pathlib import Path

import pytest

from lib.json_ops import JsonOperations
from lib.world_ids import WorldIds

CAMPAIGN = "dungeon-crawler-carl"


@pytest.fixture
def ids(dcc_world):
    return WorldIds(JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN)))


@pytest.mark.parametrize("raw, expected", [
    ("player", "player"),
    ("Tandy", "player"),                       # the player character's name
    ("npc:Carl", "npc:Carl"),
    ("npc:carl", "npc:Carl"),                  # case
    ("npc:Donut", "npc:Princess Donut"),       # title dropped
    ("Mordecai", "npc:Mordecai"),              # bare name
    ("location:bone-garden", "location:Bone Garden"),
    ("Floor 1 Stairs", "location:Floor 1 Stairs"),
    ("street", "street"),
    ("PUBLIC", "public"),
])
def test_resolves_to_the_exact_key(ids, raw, expected):
    assert ids.resolve(raw) == (expected, "")


def test_unknown_is_refused_with_close_matches(ids):
    cid, error = ids.resolve("npc:Mordekai")
    assert cid == "" and "did you mean: npc:Mordecai" in error
    cid, error = ids.resolve("Bone Gardn")
    assert cid == "" and "location:Bone Garden" in error
    cid, error = ids.resolve("Zzyzx")
    assert cid == "" and "did you mean" not in error


def test_kinds_that_come_later_say_so(ids):
    assert "factions" in ids.resolve("faction:Meridian")[1]
    assert "items" in ids.resolve("item:chip")[1]
    assert "unknown kind" in ids.resolve("god:Odin")[1]


def test_a_bare_name_that_fits_two_kinds_is_refused(ids, dcc_world):
    locs = Path(dcc_world) / "campaigns" / CAMPAIGN / "locations.json"
    data = json.loads(locs.read_text(encoding="utf-8"))
    data["Mordecai"] = {}
    locs.write_text(json.dumps(data))
    cid, error = ids.resolve("Mordecai")
    assert cid == "" and "npc:Mordecai" in error and "location:Mordecai" in error
    assert ids.resolve("npc:Mordecai") == ("npc:Mordecai", "")


def test_resolve_all_collapses_duplicates_and_collects_errors(ids):
    got, errors = ids.resolve_all(["Carl", "npc:carl", "player", "Zzyzx", "Tandy"])
    assert got == ["npc:Carl", "player"]
    assert len(errors) == 1


def test_all_ids_lists_everything(ids):
    every = ids.all_ids()
    assert every[0] == "player" and every[-2:] == ["street", "public"]
    assert "npc:Carl" in every and "location:Bone Garden" in every


def test_a_clock_resolves_only_where_a_clock_is_asked_for(ids, dcc_world):
    """clock:<key> goes through the same resolver, but a fact is never about or
    held by a clock, so the general lookups refuse it."""
    from lib.threat_clocks import ThreatClockManager
    assert "no clocks yet" in ids.resolve_as("Tracker", ("clock",))[1]
    tcm = ThreatClockManager(dcc_world)
    tcm.add_clock("Tracker", 3, advance_on="event", text="The tracker closes in")
    tcm.add_clock("Slow scrub", 4, advance_on="event")
    for raw in ("Tracker", "tracker", "clock:TRACKER", "the tracker closes in"):
        assert ids.resolve_as(raw, ("clock",)) == ("clock:Tracker", "")
    assert ids.resolve_as("Trakcer", ("clock",)) == ("", "No clock 'Trakcer'; did you mean: Tracker?")
    assert ids.resolve_as("scrub", ("clock",))[1] == "No clock 'scrub'; did you mean: Slow scrub?"
    assert ids.resolve_as("Doom", ("clock",))[1] == "No clock 'Doom'. Clocks: Tracker, Slow scrub."
    assert ids.resolve("clock:Tracker")[0] == ""
    assert ids.resolve("Tracker")[0] == ""
    assert ids.resolve_holder("clock:Tracker")[0] == ""
    assert "clock:Tracker" in ids.all_ids()
