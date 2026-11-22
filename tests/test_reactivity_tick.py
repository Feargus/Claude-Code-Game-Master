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


def test_a_consequence_fires_once(dcc_world):
    """Fired is a state: it matches no trigger any more. It used to fire again
    whenever the time of day changed at the same place, and to be reported as
    "already fired here" at every time step until it was resolved."""
    cm = ConsequenceManager(dcc_world)
    scene = {"location": "Floor 3 - The Over City", "time": "day", "present_npcs": [], "events": []}
    first = cm.tick(scene)
    assert any(c["id"] == "c3e61742" for c in first["fired"])  # Sheol on_location, the Over City
    assert all("match_reason" in c for c in first["fired"])
    assert cm.tick(scene) == {"fired": []}                     # the same scene again: nothing
    night = cm.tick({"location": "Floor 3 - The Over City", "time": "night", "present_npcs": []})
    ids = {c["id"] for c in night["fired"]}
    assert "a36a02f6" in ids                                   # Nightstalker, on_time night
    assert "c3e61742" not in ids                               # Sheol has fired: not again
    assert all(c["id"] != "c3e61742" for c in cm.waiting_on_fact())
    assert cm.fire("c3e61742") == {}                           # not by hand either


def test_one_of_several_triggers_fires_it_for_good(dcc_world):
    """"At the junction, or when the clock runs out": after the junction, the
    clock no longer fires it a second time."""
    from lib.threat_clocks import ThreatClockManager
    tcm = ThreatClockManager(dcc_world)
    tcm.add_clock("Patience", 1, advance_on="event")
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The fence loses patience", "x", triggers=[
        {"type": "on_location", "match": "Floor 3 - The Over City"},
        {"type": "on_clock", "match": "Patience"}])
    cm.tick({"location": "Floor 3 - The Over City", "time": "day", "present_npcs": []})
    assert all(c["id"] != cid for c in tcm.advance("Patience")["fired"])


def test_rearm_makes_a_fired_consequence_wait_again(dcc_world):
    """The GM's veto: the moment was wrong. It can then fire again."""
    cm = ConsequenceManager(dcc_world)
    scene = {"location": "Floor 3 - The Over City", "time": "day", "present_npcs": []}
    cm.tick(scene)
    assert "fired" not in cm.rearm("c3e6")                     # a prefix is enough
    assert any(c["id"] == "c3e61742" for c in cm.tick(scene)["fired"])
    cm.resolve("c3e61742")
    for wrong in ("c3e61742", "a36a02f6"):                     # resolved; and one still waiting
        try:
            cm.rearm(wrong)
            raise AssertionError("rearm should refuse")
        except ValueError:
            pass


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
    assert "already_fired" not in result and "near_misses" not in result
