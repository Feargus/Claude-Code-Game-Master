"""on_clock: a consequence fires when a clock reaches a segment.

The match is a clock's name (when it is full) or "<name>:<segment>" (a grim
portent partway). It fires inside the command that moves the clock: a hand
advance, or time passing for a time clock. Each segment fires once.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.threat_clocks import ThreatClockManager

CAMPAIGN = "dungeon-crawler-carl"


def _active(world):
    p = Path(world) / "campaigns" / CAMPAIGN / "consequences.json"
    return json.loads(p.read_text(encoding="utf-8"))["active"]


def _stored(world, cid):
    return next(c for c in _active(world) if c["id"] == cid)


def test_match_is_checked_and_made_canonical(dcc_world):
    ThreatClockManager(dcc_world).add_clock("Tracker", 4, advance_on="event")
    cm = ConsequenceManager(dcc_world)
    assert cm.add_consequence("x", "y", trigger_type="on_clock", match="Nobody's clock") == ""
    assert cm.add_consequence("x", "y", trigger_type="on_clock", match="Tracker:5") == ""
    assert cm.add_consequence("x", "y", trigger_type="on_clock", match="Tracker:0") == ""
    full = cm.add_consequence("x", "y", trigger_type="on_clock", match="tracker")
    assert _stored(dcc_world, full)["triggers"] == [{"type": "on_clock", "match": "Tracker:4"}]
    part = cm.add_consequence("x", "y", trigger_type="on_clock", match="TRACKER : 2")
    assert _stored(dcc_world, part)["triggers"] == [{"type": "on_clock", "match": "Tracker:2"}]


def test_advancing_fires_each_crossed_segment_once(dcc_world):
    tcm = ThreatClockManager(dcc_world)
    tcm.add_clock("Tracker", 4, advance_on="event")
    cm = ConsequenceManager(dcc_world)
    two = cm.add_consequence("Footprints by the door", "x", trigger_type="on_clock", match="Tracker:2")
    full = cm.add_consequence("The tracker arrives", "x", trigger_type="on_clock", match="Tracker")

    assert tcm.advance("Tracker")["fired"] == []                        # 1/4
    hit = tcm.advance("Tracker", ticks=2)["fired"]                     # 1 → 3 crosses 2
    assert [c["id"] for c in hit] == [two]
    assert hit[0]["match_reason"] == "clock Tracker reached 2/4"
    assert [c["id"] for c in tcm.advance("Tracker")["fired"]] == [full]  # 4/4
    assert tcm.advance("Tracker")["fired"] == []                        # already full


def test_fired_list_is_not_saved_into_the_clock(dcc_world):
    tcm = ThreatClockManager(dcc_world)
    tcm.add_clock("Tracker", 2, advance_on="event")
    tcm.advance("Tracker")
    assert "fired" not in tcm.get_clocks()["Tracker"]


def test_time_passing_fires_a_time_clock(dcc_world):
    tcm = ThreatClockManager(dcc_world)
    now = datetime(2187, 10, 26, 6, 0)
    overview = Path(dcc_world) / "campaigns" / CAMPAIGN / "campaign-overview.json"
    data = json.loads(overview.read_text(encoding="utf-8"))
    data["game_time"] = now.strftime("%Y-%m-%dT%H:%M")
    overview.write_text(json.dumps(data))
    tcm.add_clock("Eviction", 3, due_in_minutes=3 * 60)
    cid = ConsequenceManager(dcc_world).add_consequence(
        "Bailiffs at the door", "x", trigger_type="on_clock", match="Eviction:2")

    moved = tcm.update_time_clocks(now + timedelta(hours=2))
    assert [c["id"] for c in moved["Eviction"]["fired"]] == [cid]
    moved = tcm.update_time_clocks(now + timedelta(hours=3))
    assert moved["Eviction"]["fired"] == []


def test_on_clock_never_fires_on_the_scene_check(dcc_world):
    cm = ConsequenceManager(dcc_world)
    c = {"id": "x", "consequence": "c", "trigger": "t",
         "triggers": [{"type": "on_clock", "match": "Tracker:2"}]}
    assert cm._matches_now(c, {"location": "Tracker:2"}) == ""


def test_a_clock_a_consequence_will_start_can_be_matched(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cm.add_consequence("Word gets out", "x", effects=[
        {"type": "start_clock", "name": "Vendetta", "segments": 3, "on": "event"}])
    assert cm.add_consequence("x", "y", trigger_type="on_clock", match="Vendetta:4") == ""
    cid = cm.add_consequence("Dead rat on the door", "y", trigger_type="on_clock", match="vendetta:1")
    assert _stored(dcc_world, cid)["triggers"] == [{"type": "on_clock", "match": "Vendetta:1"}]
