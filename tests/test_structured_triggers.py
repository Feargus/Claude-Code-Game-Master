"""Tests for structured-trigger-schema.

Consequences gain optional structured triggers (trigger_type/match) that
the reactivity engine can fire and expire on, additively — legacy free-text
consequences still load and round-trip unchanged.
"""

import json
from pathlib import Path

from lib.consequence_manager import ConsequenceManager


def _consq_path(dcc_world):
    return Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "consequences.json"


def test_add_with_structured_trigger(dcc_world, capsys):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("Guards search the market", "next day",
                             trigger_type="on_location", match="Floor 2 Junction")
    assert cid
    data = json.loads(_consq_path(dcc_world).read_text(encoding="utf-8"))
    new = next(c for c in data["active"] if c["id"] == cid)
    assert new["triggers"] == [{"type": "on_location", "match": "location:Floor 2 Junction"}]
    # the free text next to a structured trigger is not kept, and the GM is told
    assert "trigger" not in new
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"[SUCCESS] Added consequence {cid}"
    assert out[1] == "[NOTE] Trigger text ignored: on_location needs none."
    assert new["consequence"] == "Guards search the market"


def test_free_text_alone_becomes_an_on_event_trigger(dcc_world):
    """No word matching: a bare free-text trigger is the event the GM watches for."""
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("plain consequence", "someday")
    data = json.loads(_consq_path(dcc_world).read_text(encoding="utf-8"))
    new = next(c for c in data["active"] if c["id"] == cid)
    assert new["triggers"] == [{"type": "on_fact", "match": "someday"}]
    assert "trigger_type" not in new


def test_old_free_text_entries_never_fire_on_shared_words(dcc_world):
    cm = ConsequenceManager(dcc_world)
    old = {"id": "o1", "consequence": "c", "trigger": "when the party returns to the market"}
    assert cm.structured_triggers(old) == [
        {"type": "on_fact", "match": "when the party returns to the market"}]
    assert cm._matches_now(old, {"location": "the market", "time": "returns"}) == ""


def test_fixture_exercises_all_trigger_types_and_a_legacy(dcc_world):
    data = json.loads(_consq_path(dcc_world).read_text(encoding="utf-8"))
    items = data.get("active", []) + data.get("pending", [])
    types = {c.get("trigger_type") for c in items if c.get("trigger_type")}
    assert {"on_location", "on_npc", "on_time", "on_fact"}.issubset(types)
    assert any("trigger_type" not in c for c in items), "expected a legacy free-text consequence too"


def test_existing_consequences_round_trip(dcc_world):
    pending = ConsequenceManager(dcc_world).check_pending()
    assert all("consequence" in c and "trigger" in c for c in pending)


def test_on_time_refuses_a_date_and_points_to_a_clock(dcc_world, capsys):
    """on_time matches the time-of-day word; a date would silently never fire."""
    cm = ConsequenceManager(dcc_world)
    before = _consq_path(dcc_world).read_text(encoding="utf-8")
    assert cm.add_consequence("The scrub finishes", "in 2 hours",
                              trigger_type="on_time", match="2187-10-26 07:15") == ""
    assert "gm-clock.sh add" in capsys.readouterr().err
    assert _consq_path(dcc_world).read_text(encoding="utf-8") == before


def test_on_time_accepts_a_time_of_day_word(dcc_world):
    assert ConsequenceManager(dcc_world).add_consequence(
        "The market closes", "tonight", trigger_type="on_time", match="Small hours")


def test_on_time_fires_only_in_its_hours(dcc_world):
    """on_time compares the word for the game time exactly: noon is 11:00-12:59.
    Before, a substring match made 'noon' fire in the Afternoon and 'night' at
    Midnight."""
    cm = ConsequenceManager(dcc_world)
    noon = cm.add_consequence("The market opens", "x", trigger_type="on_time", match="noon")
    night = cm.add_consequence("The patrol passes", "x", trigger_type="on_time", match="night")

    def fired(**world):
        return {c["id"] for c in cm.check_pending(world)} & {noon, night}

    assert fired(game_time="2187-10-26T11:30") == {noon}
    assert fired(game_time="2187-10-26T14:00") == set()           # Afternoon
    assert fired(time="Afternoon") == set()
    assert fired(game_time="2187-10-26T21:15") == {night}
    assert fired(game_time="2187-10-26T23:30") == set()           # Midnight
    # The game time decides, not a word stored elsewhere.
    assert fired(game_time="2187-10-26T11:00", time="Night") == {noon}
    reason = next(c for c in cm.check_pending({"game_time": "2187-10-26T12:59"})
                  if c["id"] == noon)["match_reason"]
    assert reason == "it is Noon (11:00–12:59)"


def test_hours_of_each_word():
    from lib.time_manager import hours_of
    assert hours_of("Noon") == "11:00–12:59"
    assert hours_of("small hours") == "01:00–04:59"
    assert hours_of("midnight") == "23:00–00:59"
    assert hours_of("night") == "21:00–22:59"
    assert hours_of("teatime") == ""


def test_a_consequence_without_any_trigger_is_refused(dcc_world, capsys):
    assert ConsequenceManager(dcc_world).add_consequence("Something happens") == ""
    assert "needs a trigger" in capsys.readouterr().err


def test_triggers_in_words():
    """docs/conventions/output.md, "Triggers in words": as short as it goes."""
    from consequence_manager import trigger_words
    words = {("on_clock", "clock:Sealing:2"): "clock Sealing at 2",
             ("on_location", "location:The Saffron House"): "at The Saffron House",
             ("on_npc", "npc:Mordecai"): "Mordecai is here",
             ("on_death", "npc:Carl"): "Carl dies",
             ("on_death", "player"): "the character dies",
             ("on_learn", "street learns f12"): "the street learns f12",
             ("on_learn", "anyone learns about:npc:Wren"): "anyone learns about Wren",
             ("on_rule", "Hunger:4@npc:Ilaria"): "Hunger of Ilaria at 4",
             ("on_rule", "Addiction:hooked@npc:Wren"): "Addiction of Wren is hooked",
             ("on_rule", "Sea level:5@world"): "Sea level at 5",
             ("on_fact", "Pell bids for the contract"): "Pell bids for the contract"}
    for (ttype, match), expected in words.items():
        assert trigger_words({"type": ttype, "match": match}) == expected


def test_consequence_ids_count_up_like_facts(dcc_world):
    """c1, c2, …: one past every id given, waiting or resolved; found by the id
    whole (a prefix of c12 is c1)."""
    cm = ConsequenceManager(dcc_world)
    first = cm.add_consequence("One", "Carl opens the door")
    second = cm.add_consequence("Two", "Carl opens the window")
    assert (first, second) == ("c1", "c2")
    cm.resolve(first)
    assert cm.add_consequence("Three", "Carl opens the hatch") == "c3"
    data = json.loads(_consq_path(dcc_world).read_text(encoding="utf-8"))
    found, _ = cm._find_active(data, "c3")
    assert found["consequence"] == "Three"
    assert cm._find_active(data, "c")[0] is None
