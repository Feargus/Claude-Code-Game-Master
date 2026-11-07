"""on_learn: a consequence fires when someone learns a fact.

The match is "<who> learns <fact id>" or "<who> learns about <id>"; <who> is a
holder id or `anyone`. It fires inside every command that adds a holder:
recording a fact (its first holders learn it), gm-note.sh tell, and world-tick
developments with holders. A consequence fires once per learning, however many
of its descriptions fit.
"""

import json
import subprocess
import sys
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.note_manager import NoteManager
from lib.world_tick import WorldTick

CAMPAIGN = "dungeon-crawler-carl"


def _active(world):
    p = Path(world) / "campaigns" / CAMPAIGN / "consequences.json"
    return json.loads(p.read_text(encoding="utf-8"))["active"]


def _stored(world, cid):
    return next(c for c in _active(world) if c["id"] == cid)


def _on_learn(world, match, text="x"):
    return ConsequenceManager(world).add_consequence(text, "y", trigger_type="on_learn", match=match)


def test_match_is_checked_and_made_canonical(dcc_world):
    fid = NoteManager(dcc_world).add_fact("lore", "The code is 0451", secret=True)
    cid = _on_learn(dcc_world, "mordecai LEARNS " + fid)               # bare names resolve
    assert _stored(dcc_world, cid)["triggers"][0]["match"] == f"npc:Mordecai learns {fid}"
    cid = _on_learn(dcc_world, "street learns about Tandy")
    assert _stored(dcc_world, cid)["triggers"][0]["match"] == "street learns about:player"
    cid = _on_learn(dcc_world, "anyone learns about location:bone garden")
    assert _stored(dcc_world, cid)["triggers"][0]["match"] == "anyone learns about:location:Bone Garden"
    assert _on_learn(dcc_world, "npc:Mordecai learns f9999") == ""       # no such fact
    assert _on_learn(dcc_world, "npc:Mordekai learns " + fid) == ""      # no such NPC
    assert _on_learn(dcc_world, "location:Bone Garden learns " + fid) == ""  # a place can't
    assert _on_learn(dcc_world, "Mordecai knows " + fid) == ""           # no "learns"


def test_tell_fires_for_the_fact_and_for_anyone(dcc_world):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("lore", "The code is 0451", secret=True)
    direct = _on_learn(dcc_world, f"npc:Mordecai learns {fid}", "Mordecai sells the code")
    leak = _on_learn(dcc_world, f"anyone learns {fid}", "The secret is out")
    other = _on_learn(dcc_world, f"street learns {fid}", "Rumours spread")
    nm.tell(fid, ["Mordecai"])
    assert {c["id"] for c in nm.last_fired} == {direct, leak}
    assert "npc:Mordecai learned" in nm.last_fired[0]["match_reason"]
    nm.tell(fid, ["Mordecai"])                       # knew it already: nothing fires
    assert nm.last_fired == []
    nm.tell(fid, ["street"])
    assert {c["id"] for c in nm.last_fired} == {other, leak}


def test_about_fires_for_any_fact_about_them(dcc_world):
    nm = NoteManager(dcc_world)
    cid = _on_learn(dcc_world, "npc:Mordecai learns about player", "Mordecai sells you out")
    fid = nm.add_fact("lore", "Tandy hides a key under the mat", secret=True)
    nm.tell(fid, ["Mordecai"])
    assert [c["id"] for c in nm.last_fired] == [cid]


def test_recording_a_fact_fires_for_its_first_holders(dcc_world, capsys):
    cid = _on_learn(dcc_world, "npc:Carl learns about npc:Mordecai", "Carl confronts Mordecai")
    nm = NoteManager(dcc_world)
    nm.add_fact("session_events", "Mordecai cheated at cards")    # Carl is in the party
    assert [c["id"] for c in nm.last_fired] == [cid]
    assert "Carl confronts Mordecai" in capsys.readouterr().out
    nm.add_fact("session_events", "Mordecai cheated again", secret=True)
    assert nm.last_fired == []                                     # nobody learned anything


def test_one_learning_fires_a_consequence_once(dcc_world):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("lore", "Tandy owes Mordecai", secret=True)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("Debt collectors", "y", triggers=[
        {"type": "on_learn", "match": f"npc:Mordecai learns {fid}"},
        {"type": "on_learn", "match": "anyone learns about player"}])
    nm.tell(fid, ["Mordecai"])
    assert [c["id"] for c in nm.last_fired] == [cid]


def test_world_tick_developments_with_holders_fire(dcc_world):
    cid = _on_learn(dcc_world, "street learns about npc:Mordecai", "Everyone mocks Mordecai")
    applied = WorldTick(dcc_world).apply([
        {"fact": "Mordecai lost his guild licence.", "holders": ["street"]},
        {"fact": "Mordecai wept in private."}])              # nobody: nothing fires
    prov = json.loads((Path(dcc_world) / "campaigns" / CAMPAIGN / "consequences.json")
                      .read_text(encoding="utf-8"))["provenance"]
    assert [p["id"] for p in prov] == [cid]
    assert applied[0]["fact"] in prov[0]["reason"]


def test_on_learn_never_fires_on_the_scene_check(dcc_world):
    c = {"id": "x", "consequence": "c", "trigger": "t",
         "triggers": [{"type": "on_learn", "match": "anyone learns f1"}]}
    assert ConsequenceManager(dcc_world)._matches_now(c, {"location": "anyone learns f1"}) == ""


def test_cli_tell_prints_what_fired(dcc_world):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("lore", "The code is 0451", secret=True)
    _on_learn(dcc_world, f"anyone learns {fid}", "The secret is out")
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root / "lib" / "note_manager.py"), "tell", fid, "street"],
                       capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    assert r.returncode == 0, r.stderr
    assert "street now know(s) it" in r.stdout and "The secret is out" in r.stdout
