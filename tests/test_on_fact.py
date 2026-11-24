"""on_fact: the GM matches recorded facts to awaited events by judgment.

No script guesses whether a fact fulfils an event. Each recorded fact lists
the consequences waiting on one; the GM fires a fitting one with
`fire <id> --by <fact id>`.
"""

import json
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.note_manager import NoteManager

CAMPAIGN = "dungeon-crawler-carl"


def _load(world, name):
    return json.loads((Path(world) / "campaigns" / CAMPAIGN / name).read_text(encoding="utf-8"))


def _clear_consequences(world):
    (Path(world) / "campaigns" / CAMPAIGN / "consequences.json").write_text(
        json.dumps({"active": [], "resolved": []}))


def test_on_fact_never_fires_on_the_scene_check(dcc_world):
    cm = ConsequenceManager(dcc_world)
    c = {"id": "x", "consequence": "c", "trigger": "t",
         "triggers": [{"type": "on_fact", "match": "alarm"}]}
    assert cm._matches_now(c, {"location": "alarm", "events": ["alarm"]}) == ""


def test_fire_by_fact_links_the_fact(dcc_world):
    _clear_consequences(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The Fork bargains", "free text",
                             trigger_type="on_fact", match="someone is alone with the chip")
    fid = NoteManager(dcc_world).add_fact("Old Iron kept the chip alone overnight")
    hit = cm.fire(cid, by_fact=fid)
    assert hit["match_reason"] == f"fact {fid}: Old Iron kept the chip alone overnight"
    prov = _load(dcc_world, "consequences.json")["provenance"][-1]
    assert prov["id"] == cid and prov["fact"] == fid


def test_fire_by_unknown_fact_is_refused(dcc_world):
    _clear_consequences(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("x", "y", trigger_type="on_fact", match="z")
    assert cm.fire(cid, by_fact="f999") == {}
    assert "provenance" not in _load(dcc_world, "consequences.json")
