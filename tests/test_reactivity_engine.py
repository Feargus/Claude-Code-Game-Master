"""Tests for reactivity-engine.

check_pending(world_state) evaluates triggers against the scene and returns
the consequences that MATCH (annotated with a match_reason, sorted),
auto-archiving expired ones. Every match is returned; there is no fire limit.
check_pending() with no args stays the legacy raw-active accessor.
"""

from pathlib import Path

from lib.consequence_manager import ConsequenceManager


def _consq_path(dcc_world):
    return Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "consequences.json"


def test_legacy_accessor_returns_active_list(dcc_world):
    pending = ConsequenceManager(dcc_world).check_pending()
    assert isinstance(pending, list) and len(pending) == 3  # fixture active count


def test_on_location_fires_with_reason(dcc_world):
    fired = ConsequenceManager(dcc_world).check_pending(
        {"location": "Floor 3 - The Over City", "time": "day", "present_npcs": []})
    ids = {c["id"] for c in fired}
    assert "c3e61742" in ids  # Sheol: on_location -> the Over City
    assert all("match_reason" in c for c in fired)


def test_on_time_fires(dcc_world):
    fired = ConsequenceManager(dcc_world).check_pending(
        {"location": "Village", "time": "Night", "present_npcs": []})
    assert "a36a02f6" in {c["id"] for c in fired}  # Nightstalker: on_time -> "night"


def test_on_npc_fires(dcc_world):
    fired = ConsequenceManager(dcc_world).check_pending(
        {"location": "Inn", "time": "day", "present_npcs": ["Squeeks"]})
    assert "b5aeefab" in {c["id"] for c in fired}  # Squeeks: on_npc -> npc:Squeeks


def test_nothing_fires_when_no_match(dcc_world):
    fired = ConsequenceManager(dcc_world).check_pending(
        {"location": "Nowhere", "time": "noon", "present_npcs": ["Bob"], "events": []})
    assert fired == []


def test_every_match_is_returned(dcc_world):
    cm = ConsequenceManager(dcc_world)
    ws = {"location": "Floor 3 - The Over City", "time": "night", "present_npcs": [], "events": []}
    ids = {c["id"] for c in cm.check_pending(ws)}
    assert {"c3e61742", "a36a02f6"} <= ids  # Sheol + Nightstalker both match
