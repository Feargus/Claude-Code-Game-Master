"""on_event: the GM matches recorded facts to awaited events by judgment.

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


def test_waiting_lists_on_event_and_untyped_only(dcc_world):
    _clear_consequences(dcc_world)
    cm = ConsequenceManager(dcc_world)
    ev = cm.add_consequence("The Fork bargains", "free text",
                            trigger_type="on_event", match="someone is alone with the chip")
    old = cm.add_consequence("The Palimpsest learn of it", "when the body is found")
    cm.add_consequence("Priests at the Junction", "x", trigger_type="on_location", match="Floor 2 Junction")
    waiting = {c["id"]: c["awaits"] for c in cm.waiting_on_event()}
    assert waiting == {ev: "someone is alone with the chip", old: "when the body is found"}


def test_recording_a_fact_lists_what_waits(dcc_world, capsys):
    _clear_consequences(dcc_world)
    cid = ConsequenceManager(dcc_world).add_consequence(
        "The Fork bargains", "free text",
        trigger_type="on_event", match="someone is alone with the chip")
    capsys.readouterr()
    fid = NoteManager(dcc_world).add_fact("session_events", "Old Iron kept the chip alone overnight")
    out = capsys.readouterr().out
    assert f"does {fid} fulfil one?" in out
    assert f"[{cid}] awaits \"someone is alone with the chip\"" in out
    assert f"fire <id> --by {fid}" in out


def test_nothing_waiting_prints_nothing_extra(dcc_world, capsys):
    _clear_consequences(dcc_world)
    NoteManager(dcc_world).add_fact("lore", "The rain is acid")
    assert "Waiting on an event" not in capsys.readouterr().out


def test_on_event_never_fires_on_the_scene_check(dcc_world):
    cm = ConsequenceManager(dcc_world)
    c = {"id": "x", "consequence": "c", "trigger": "t",
         "triggers": [{"type": "on_event", "match": "alarm"}]}
    assert cm._matches_now(c, {"location": "alarm", "events": ["alarm"]}) == ""


def test_fire_by_fact_links_the_fact(dcc_world):
    _clear_consequences(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The Fork bargains", "free text",
                             trigger_type="on_event", match="someone is alone with the chip")
    fid = NoteManager(dcc_world).add_fact("session_events", "Old Iron kept the chip alone overnight")
    hit = cm.fire(cid, by_fact=fid)
    assert hit["match_reason"] == f"fact {fid}: Old Iron kept the chip alone overnight"
    prov = _load(dcc_world, "consequences.json")["provenance"][-1]
    assert prov["id"] == cid and prov["fact"] == fid


def test_fire_by_unknown_fact_is_refused(dcc_world):
    _clear_consequences(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("x", "y", trigger_type="on_event", match="z")
    assert cm.fire(cid, by_fact="f999") == {}
    assert "provenance" not in _load(dcc_world, "consequences.json")
