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


def test_add_with_structured_trigger(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("Guards search the market", "next day",
                             trigger_type="on_location", match="Market")
    assert cid
    data = json.loads(_consq_path(dcc_world).read_text(encoding="utf-8"))
    new = next(c for c in data["active"] if c["id"] == cid)
    assert new["triggers"] == [{"type": "on_location", "match": "Market"}]
    # free-text trigger + description still preserved
    assert new["trigger"] == "next day"
    assert new["consequence"] == "Guards search the market"


def test_free_text_alone_becomes_an_on_event_trigger(dcc_world):
    """No word matching: a bare free-text trigger is the event the GM watches for."""
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("plain consequence", "someday")
    data = json.loads(_consq_path(dcc_world).read_text(encoding="utf-8"))
    new = next(c for c in data["active"] if c["id"] == cid)
    assert new["triggers"] == [{"type": "on_event", "match": "someday"}]
    assert "trigger_type" not in new


def test_old_free_text_entries_never_fire_on_shared_words(dcc_world):
    cm = ConsequenceManager(dcc_world)
    old = {"id": "o1", "consequence": "c", "trigger": "when the party returns to the market"}
    assert cm.structured_triggers(old) == [
        {"type": "on_event", "match": "when the party returns to the market"}]
    assert cm._matches_now(old, {"location": "the market", "time": "returns"}) == ""


def test_fixture_exercises_all_trigger_types_and_a_legacy(dcc_world):
    data = json.loads(_consq_path(dcc_world).read_text(encoding="utf-8"))
    items = data.get("active", []) + data.get("pending", [])
    types = {c.get("trigger_type") for c in items if c.get("trigger_type")}
    assert {"on_location", "on_npc", "on_time", "on_event"}.issubset(types)
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
