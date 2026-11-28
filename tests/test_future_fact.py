"""A future fact: a consequence whose own text becomes a fact when it fires.

The GM commits to it when the consequence is made; until it fires it is no fact
(nobody knows it, nothing reads it as having happened), and then the script
records it, with the fields it was given.
"""

import json
import os
import subprocess
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.note_manager import NoteManager
from lib.threat_clocks import ThreatClockManager

CAMPAIGN = "dungeon-crawler-carl"
ROOT = Path(__file__).resolve().parent.parent
PARTY = ["player", "npc:Carl", "npc:Princess Donut", "npc:Mongo"]  # the fixture's scene
HERE = "location:Warehouse Street Level"


def _facts(world):
    return json.loads((Path(world) / "campaigns" / CAMPAIGN / "facts.json").read_text(encoding="utf-8"))


def _fact(world, fid):
    return next(f for f in _facts(world) if f.get("id") == fid)


def _new(world, before):
    return [f for f in _facts(world) if f.get("id") not in before]


def test_a_future_fact_is_no_fact_until_it_fires(dcc_world):
    truth = NoteManager(dcc_world).add_fact("The showrunners plan to flood the floor",
                                            holders=["faction:showrunners"])
    cm = ConsequenceManager(dcc_world)
    before = {f["id"] for f in _facts(dcc_world)}
    cid = cm.add_consequence("The floor is closed for cleaning", "y", effects=[
        {"type": "fact", "holders": ["street"], "truth": "wrong", "version_of": truth}])
    assert _new(dcc_world, before) == []
    hit = cm.fire(cid)
    [made] = _new(dcc_world, before)
    assert made["fact"] == "The floor is closed for cleaning"
    assert (made["holders"], made["truth"], made["version_of"]) == (["street"], "wrong", truth)
    assert "at" not in made                                  # nobody here knows it
    assert hit["effects_done"] == [f"recorded as {made['id']}, known to: street"]


def test_who_knows_it_when_nothing_is_given(dcc_world):
    """In the scene: whoever is there when it fires, and it happened here. Off-screen:
    nobody, and nowhere."""
    cm = ConsequenceManager(dcc_world)
    before = {f["id"] for f in _facts(dcc_world)}
    cm.fire(cm.add_consequence("The ceiling gives way", "y", effects=[{"type": "fact"}]))
    [here] = _new(dcc_world, before)
    assert here["holders"] == PARTY and here["at"] == HERE
    before = {f["id"] for f in _facts(dcc_world)}
    cm.fire(cm.add_consequence("The showrunners change the rules", "y", offscreen=True,
                               effects=[{"type": "fact"}]))
    [away] = _new(dcc_world, before)
    assert away["holders"] == [] and "at" not in away


def test_its_plots_go_with_it(dcc_world):
    from lib.plot_manager import PlotManager
    PlotManager(dcc_world).add("The Flood", "Flood the floor before the crawlers reach it.")
    cm = ConsequenceManager(dcc_world)
    before = {f["id"] for f in _facts(dcc_world)}
    cm.fire(cm.add_consequence("The pumps start", "y", plots=["The Flood"],
                               effects=[{"type": "fact", "holders": ["street"]}]))
    [made] = _new(dcc_world, before)
    assert made["plots"] == ["The Flood"]


def test_bad_fields_are_refused(dcc_world):
    cm = ConsequenceManager(dcc_world)
    truth = NoteManager(dcc_world).add_fact("The crate was empty")
    for bad in ({"type": "fact", "holders": ["street"], "secret": True},
                {"type": "fact", "holders": ["npc:Nobody"]},
                {"type": "fact", "truth": "maybe"},
                {"type": "fact", "version_of": truth},
                {"type": "fact", "truth": "wrong", "version_of": "f9999"},
                {"type": "fact", "at": "Nowhere Known"}):
        assert cm.add_consequence("x", "y", effects=[bad]) == "", bad


def test_a_clock_brings_it(dcc_world):
    tcm = ThreatClockManager(dcc_world)
    tcm.add_clock("Flood", 2, advance_on="event")
    cm = ConsequenceManager(dcc_world)
    cm.add_consequence("Water seeps under the doors", trigger_type="on_clock", match="Flood:1",
                       effects=[{"type": "fact", "holders": ["street"]}])
    before = {f["id"] for f in _facts(dcc_world)}
    fired = tcm.advance("Flood")["fired"]
    [made] = _new(dcc_world, before)
    assert made["fact"] == "Water seeps under the doors" and made["holders"] == ["street"]
    assert fired[0]["effects_done"] == [f"recorded as {made['id']}, known to: street"]


def test_the_command(dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=str(dcc_world))

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-consequence.sh"), *words],
                              capture_output=True, text=True, env=env)
    alone = run("add", "The floor is closed", "--trigger-type", "on_time", "--match", "night",
                "--holders", "street")
    assert alone.returncode == 1 and "give --fact too" in alone.stderr
    made = run("add", "The floor is closed", "--trigger-type", "on_time", "--match", "night",
               "--fact", "--holders", "street")
    assert made.returncode == 0, made.stderr
    listed = run("check").stdout
    assert "when it fires, becomes a fact, known to street" in listed
