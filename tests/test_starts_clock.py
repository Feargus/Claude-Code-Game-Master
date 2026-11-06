"""Effects: a consequence that starts a threat clock when it fires.

Clocks could already create consequences (when they fill); this is the other
direction. The effect runs whichever way the consequence fires: scene check,
event trigger, or by hand. A clock that already exists is left alone.
"""

import json
import subprocess
import sys
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.npc_manager import NPCManager
from lib.threat_clocks import ThreatClockManager

CAMPAIGN = "dungeon-crawler-carl"
HUNT = {"type": "start_clock", "name": "Vendetta", "segments": 3, "on": "event",
        "consequence": "The brothers come for you"}


def _clocks(world):
    return ThreatClockManager(world).get_clocks()


def _set_game_time(world, stamp="2187-10-26T06:00"):
    p = Path(world) / "campaigns" / CAMPAIGN / "campaign-overview.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["game_time"] = stamp
    p.write_text(json.dumps(data))


def test_bad_effects_are_refused(dcc_world):
    cm = ConsequenceManager(dcc_world)
    for bad in ({"type": "explode"}, {"type": "start_clock"},
                {"type": "start_clock", "name": "X", "segments": 0},
                {"type": "start_clock", "name": "X", "due_in": "soonish"},
                {"type": "start_clock", "name": "X", "on": "event", "due_in": "3d"},
                {"type": "start_clock", "name": "X", "due_in": "3d", "due": "2187-11-01 08:00"}):
        assert cm.add_consequence("x", "y", effects=[bad]) == "", bad


def test_firing_by_hand_starts_the_clock(dcc_world, capsys):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("Word gets out", "the job goes loud", effects=[HUNT])
    assert "Vendetta" not in _clocks(dcc_world)  # nothing until it fires
    hit = cm.fire(cid, reason="the job went loud")
    clock = _clocks(dcc_world)["Vendetta"]
    assert (clock["current"], clock["max"], clock["advance_on"]) == (0, 3, "event")
    assert clock["consequence"] == "The brothers come for you"
    assert hit["effects_done"] == ["started clock Vendetta (0/3, on event)"]


def test_an_existing_clock_is_left_alone(dcc_world):
    tcm = ThreatClockManager(dcc_world)
    tcm.add_clock("Vendetta", 5, advance_on="event")
    tcm.advance("Vendetta", 2)
    cm = ConsequenceManager(dcc_world)
    hit = cm.fire(cm.add_consequence("x", "y", effects=[HUNT]))
    assert _clocks(dcc_world)["Vendetta"]["current"] == 2
    assert "already running" in hit["effects_done"][0]


def test_due_in_counts_from_when_it_fires(dcc_world):
    _set_game_time(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("x", "y", effects=[
        {"type": "start_clock", "name": "Eviction", "segments": 2, "due_in": "2d"}])
    _set_game_time(dcc_world, "2187-10-27T06:00")  # a day passes first
    cm.fire(cid)
    assert _clocks(dcc_world)["Eviction"]["due_at"] == "2187-10-29T06:00"


def test_no_game_time_is_reported_not_crashed(dcc_world):
    p = Path(dcc_world) / "campaigns" / CAMPAIGN / "campaign-overview.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data.pop("game_time", None)
    p.write_text(json.dumps(data))
    cm = ConsequenceManager(dcc_world)
    hit = cm.fire(cm.add_consequence("x", "y", effects=[
        {"type": "start_clock", "name": "Eviction", "due_in": "2d"}]))
    assert hit["effects_done"][0].startswith("could not start clock Eviction")
    assert "Eviction" not in _clocks(dcc_world)


def test_a_death_starts_a_clock_whose_segment_fires_the_next_beat(dcc_world):
    npc = next(iter(json.loads(
        (Path(dcc_world) / "campaigns" / CAMPAIGN / "npcs.json").read_text(encoding="utf-8"))))
    cm = ConsequenceManager(dcc_world)
    cm.add_consequence("His brothers swear revenge", "when he dies",
                       trigger_type="on_death", match=npc, effects=[HUNT])
    result = NPCManager(dcc_world).kill_npc(npc)
    assert "started clock Vendetta" in result["fired"][0]["effects_done"][0]

    omen = cm.add_consequence("A dead rat nailed to your door", "x",
                              trigger_type="on_clock", match="Vendetta:1")
    fired = ThreatClockManager(dcc_world).advance("Vendetta")["fired"]
    assert [c["id"] for c in fired] == [omen]


def test_scene_check_carries_out_effects(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cm.add_consequence("Gangers spot you", "x", trigger_type="on_location",
                       match="Zzyzx Alley", effects=[HUNT])
    fired = cm.tick({"location": "Zzyzx Alley", "time": "night", "date": "d1"})["fired"]
    assert any("started clock Vendetta" in line
               for c in fired for line in c.get("effects_done", []))


def test_cli_starts_clock_flags(dcc_world):
    root = Path(__file__).resolve().parent.parent
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(root / "lib" / "consequence_manager.py"), *a],
        capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    r = run("add", "x", "y", "--clock-due-in", "3d")
    assert r.returncode != 0 and "--starts-clock" in (r.stdout + r.stderr)
    r = run("add", "Word gets out", "the job goes loud", "--starts-clock", "Vendetta",
            "--clock-segments", "3", "--clock-on", "event", "--json")
    assert r.returncode == 0, r.stderr
    cid = json.loads(r.stdout)["data"]["id"]
    stored = next(c for c in ConsequenceManager(dcc_world).check_pending() if c["id"] == cid)
    assert stored["effects"] == [{"type": "start_clock", "name": "Vendetta",
                                  "segments": 3, "on": "event"}]
