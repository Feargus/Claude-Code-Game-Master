"""Tests for reactivity-tick-wiring.

tick() fires matching consequences once per scene (last_fired_key annotates
already-fired matches rather than suppressing them) and re-arms when the scene
changes; tick_from_session() builds the world_state from campaign state. The
wrappers (gm-session.sh move, gm-time.sh) call this so firing is automatic, not
eyeballed.
"""

import json
from pathlib import Path

from lib.consequence_manager import ConsequenceManager


def test_tick_fires_then_dedups_same_scene(dcc_world):
    cm = ConsequenceManager(dcc_world)
    scene = {"location": "Floor 3 - The Over City", "time": "day", "present_npcs": [], "events": []}
    first = cm.tick(scene)
    assert any(c["id"] == "c3e61742" for c in first["fired"])  # Sheol on_location, the Over City
    assert all("match_reason" in c for c in first["fired"])
    # Same scene again -> still reported, annotated already-fired, not re-stamped.
    second = cm.tick(scene)
    assert any(c["id"] == "c3e61742" for c in second["already_fired"])
    assert all(c["id"] != "c3e61742" for c in second["fired"])
    sheol = next(c for c in second["already_fired"] if c["id"] == "c3e61742")
    assert sheol.get("already_fired") is True
    assert "match_reason" in sheol


def test_tick_rearms_on_scene_change(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cm.tick({"location": "Floor 3 - The Over City", "time": "day", "present_npcs": []})
    # New scene (night) -> Nightstalker fires, and Sheol re-arms (different ctx key).
    third = cm.tick({"location": "Floor 3 - The Over City", "time": "night", "present_npcs": []})
    ids = {c["id"] for c in third["fired"]}
    assert "a36a02f6" in ids  # Nightstalker on_time night
    assert "c3e61742" in ids  # Sheol re-armed by changed scene


def test_every_match_fires_with_its_effects(dcc_world):
    """There is no limit per check. With one (it was two), a third consequence at
    the same place waited: its clock started only on a second check there, and
    never if the player moved on first."""
    cm = ConsequenceManager(dcc_world)
    place = "Floor 3 - The Over City"
    ids = [cm.add_consequence(f"payoff {i}", "here", trigger_type="on_location", match=place)
           for i in range(2)]
    ids.append(cm.add_consequence(
        "the hunt begins", "here", trigger_type="on_location", match=place,
        effects=[{"type": "start_clock", "name": "The hunt", "segments": 2, "on": "event"}]))
    result = cm.tick({"location": place, "time": "night", "present_npcs": []})
    assert set(ids) <= {c["id"] for c in result["fired"]}
    assert all("match_reason" in c for c in result["fired"])
    clocks = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "threat-clocks.json"
    assert "The hunt" in json.loads(clocks.read_text(encoding="utf-8"))


def test_tick_from_session_runs_against_campaign_state(dcc_world):
    # Reads current location/time from campaign-overview without error.
    result = ConsequenceManager(dcc_world).tick_from_session()
    assert isinstance(result, dict)
    assert "fired" in result and "disclosed" not in result
    assert "already_fired" in result and "near_misses" not in result
