"""The tell effect: a consequence that, when it fires, makes holders learn a fact.

This is how the knowledge ladder climbs by itself ("the witness gets away:
the Palimpsest learn f42"). The holders are added through gm-note.sh's own
path, so on_learn consequences fire too, and chains end because someone who
knows already learns nothing.
"""

import json
import subprocess
import sys
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.note_manager import NoteManager
from lib.threat_clocks import ThreatClockManager

CAMPAIGN = "dungeon-crawler-carl"


def _fact(world, fid):
    facts = json.loads((Path(world) / "campaigns" / CAMPAIGN / "facts.json").read_text(encoding="utf-8"))
    return next(f for items in facts.values() for f in items
                if isinstance(f, dict) and f.get("id") == fid)


def _secret(world, text="Tandy killed the priest"):
    return NoteManager(world).add_fact("session_events", text, secret=True)


def test_bad_tell_effects_are_refused(dcc_world):
    cm = ConsequenceManager(dcc_world)
    fid = _secret(dcc_world)
    for bad in ({"type": "tell", "fact": "f9999", "holders": ["street"]},
                {"type": "tell", "fact": fid, "holders": []},
                {"type": "tell", "fact": fid, "holders": ["npc:Nobody"]},
                {"type": "tell", "fact": fid, "holders": ["location:Bone Garden"]}):
        assert cm.add_consequence("x", "y", effects=[bad]) == "", bad


def test_holders_are_made_canonical(dcc_world):
    fid = _secret(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("x", "y", effects=[{"type": "tell", "fact": fid, "holders": ["mordecai"]}])
    stored = next(c for c in cm.check_pending() if c["id"] == cid)
    assert stored["effects"] == [{"type": "tell", "fact": fid, "holders": ["npc:Mordecai"]}]


def test_firing_tells(dcc_world):
    fid = _secret(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The witness talks", "y",
                             effects=[{"type": "tell", "fact": fid, "holders": ["Mordecai", "street"]}])
    hit = cm.fire(cid)
    assert _fact(dcc_world, fid)["holders"] == ["npc:Mordecai", "street"]
    assert hit["effects_done"] == [f"npc:Mordecai, street now know(s) {fid}"]
    again = cm.fire(cid)
    assert again["effects_done"] == [f"npc:Mordecai, street knew {fid} already"]


def test_the_ladder_climbs_by_itself(dcc_world):
    """A clock runs out -> the witness tells -> on_learn -> a hunt clock starts."""
    fid = _secret(dcc_world)
    tcm = ThreatClockManager(dcc_world)
    tcm.add_clock("The witness gets away", 1, advance_on="event")
    cm = ConsequenceManager(dcc_world)
    cm.add_consequence("The witness reaches Mordecai", "y",
                       trigger_type="on_clock", match="The witness gets away",
                       effects=[{"type": "tell", "fact": fid, "holders": ["Mordecai"]}])
    hunt = cm.add_consequence("Mordecai hunts Tandy", "y",
                              trigger_type="on_learn", match="Mordecai learns about player",
                              effects=[{"type": "start_clock", "name": "The hunt", "segments": 3,
                                        "on": "event"}])
    fired = tcm.advance("The witness gets away")["fired"]
    lines = fired[0]["effects_done"]
    assert lines[0] == f"npc:Mordecai now know(s) {fid}"
    assert lines[1] == f"that fired [{hunt}] Mordecai hunts Tandy"
    assert lines[2].strip() == "started clock The hunt (0/3, on event)"
    assert "The hunt" in tcm.get_clocks()


def test_a_loop_stops_when_nobody_learns_anything_new(dcc_world):
    """`anyone learns` fires again at each learning; its own tell then finds
    everyone knowing already, and the chain ends."""
    fid = _secret(dcc_world)
    cm = ConsequenceManager(dcc_world)
    gossip = cm.add_consequence("Gossip spreads", "y", trigger_type="on_learn",
                                match=f"anyone learns {fid}",
                                effects=[{"type": "tell", "fact": fid, "holders": ["street"]}])
    notes = NoteManager(dcc_world)
    notes.tell(fid, ["Mordecai"])            # fires gossip -> street learns -> gossip again -> stop
    assert _fact(dcc_world, fid)["holders"] == ["npc:Mordecai", "street"]
    first = notes.last_fired[0]
    assert first["id"] == gossip
    assert first["effects_done"][0] == f"street now know(s) {fid}"
    assert f"that fired [{gossip}]" in first["effects_done"][1]
    assert "knew" in first["effects_done"][2]


def test_cli_tells_flags(dcc_world):
    fid = _secret(dcc_world)
    root = Path(__file__).resolve().parent.parent
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(root / "lib" / "consequence_manager.py"), *a],
        capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    r = run("add", "x", "y", "--tells", fid)
    assert r.returncode != 0 and "go together" in (r.stdout + r.stderr)
    r = run("add", "The witness talks", "y", "--tells", fid, "--to", "Mordecai", "--to", "public")
    assert r.returncode == 0, r.stderr
    assert f"when it fires, tells {fid} to npc:Mordecai, public" in r.stdout
