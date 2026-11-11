"""Facts recorded precisely: where they happened (`at`), several facts of one beat
at once (`beat`, with "#2" pointing at an earlier one), and catching up a witness
who got a name later (`witness`). Found in play: one fact mixing an open act, a
hidden one and a deception, fixed by editing facts.json; Lord Thane created after
the gallery scene, holding none of it."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.note_manager import NoteManager
from lib.npc_manager import NPCManager
from tests.sheets import npc, player

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def world(tmp_path):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    files = {
        "campaign-overview.json": {"campaign_name": "C", "game_time": "2189-11-09T23:40",
                                   "player_position": {"current_location": "The Holding Pens"},
                                   "scene": {"location": "The Holding Pens",
                                             "present": ["Tod", "Benno Rusk"]}},
        "character.json": player("Lullaby"),
        "npcs.json": {"Tod": npc("Tod"), "Benno Rusk": npc("Benno Rusk", aliases=["Benno"])},
        "locations.json": {"The Holding Pens": {}, "The Sanguine Ring": {}},
    }
    for name, payload in files.items():
        (camp / name).write_text(json.dumps(payload))
    return str(ws), camp


def _facts(camp):
    return {f["id"]: f for items in json.loads((camp / "facts.json").read_text()).values()
            for f in items}


def _set_time(camp, when, place=None):
    path = camp / "campaign-overview.json"
    overview = json.loads(path.read_text())
    overview["game_time"] = when
    if place:
        overview["player_position"] = {"current_location": place}
        overview["scene"] = {"location": place, "present": []}
    path.write_text(json.dumps(overview))


def test_facts_record_where_they_happened(world):
    ws, camp = world
    notes = NoteManager(ws)
    a = notes.add_fact("session_events", "Lullaby hums.")
    b = notes.add_fact("plot_local", "The Mastiff hunts by sound.", secret=True, nowhere=True)
    c = notes.add_fact("plot_local", "The bell rang.", at="The Sanguine Ring")
    facts = _facts(camp)
    assert facts[a]["at"] == "location:The Holding Pens"
    assert "at" not in facts[b]
    assert facts[c]["at"] == "location:The Sanguine Ring"
    assert [f["id"] for f in notes.find(at="The Sanguine Ring")] == [c]
    assert notes.add_fact("x", "y", at="Nowhere Known") == ""


def test_a_beat_splits_a_deception_into_atomic_facts(world):
    ws, camp = world
    notes = NoteManager(ws)
    ids = notes.beat([
        {"fact": "Lullaby faked stuttering servos; Tod drew Benno's eye with his flask."},
        {"fact": "Lullaby worked water into its collar under the surface.",
         "holders": ["player", "Tod"]},
        {"fact": "Lullaby is still glitching from the freeze.",
         "holders": ["Benno"], "truth": "wrong", "version_of": "#2"}])
    facts = _facts(camp)
    first, hidden, belief = (facts[i] for i in ids)
    assert first["holders"] == ["player", "npc:Tod", "npc:Benno Rusk"]   # everyone present
    assert hidden["holders"] == ["player", "npc:Tod"]
    assert belief["holders"] == ["npc:Benno Rusk"]
    assert (belief["truth"], belief["version_of"]) == ("wrong", ids[1])
    stored = json.loads((camp / "facts.json").read_text())
    assert [f["id"] for f in stored["session_events"]] == ids


def test_a_refused_beat_writes_nothing(world):
    ws, camp = world
    notes = NoteManager(ws)
    for items, why in [
            ([{"fact": "a"}, {"fact": "b", "truth": "wrong", "version_of": "#2"}], "earlier fact"),
            ([{"fact": "a", "truth": "wrong"}, {"fact": "b", "truth": "wrong", "version_of": "#1"}],
             "marked wrong"),
            ([{"fact": "a"}, {"fact": "b", "version_of": "#1"}], "give \"truth\""),
            ([{"fact": "a"}, {"fact": "b", "holders": ["Nobody"]}], "Nothing called 'Nobody'"),
            ([{"fact": "a", "where": "x"}], "unknown field"),
            ([], "JSON list")]:
        with pytest.raises(ValueError, match=why):
            notes.beat(items)
    assert not (camp / "facts.json").exists() or _facts(camp) == {}


def test_witness_learns_what_happened_in_the_open(world):
    ws, camp = world
    notes = NoteManager(ws)
    _set_time(camp, "2189-11-09T23:44", "The Sanguine Ring")
    fight = notes.add_fact("session_events", "Lullaby killed the Mastiff.")
    before = notes.add_fact("session_events", "Ysolde dropped her glass.")
    secret = notes.add_fact("plot_local", "Ysolde paid for the bout.", secret=True)
    belief = notes.add_fact("plot_local", "Ysolde is only curious.", truth="wrong",
                            version_of=secret)
    elsewhere = notes.add_fact("session_events", "Pike taped his knuckles.", at="The Holding Pens")
    _set_time(camp, "2189-11-09T23:58")
    late = notes.add_fact("session_events", "The gallery emptied.")
    NPCManager(ws).create_npc("Casimir Thane", "an old lord", "neutral", nowhere=True)

    preview = notes.witness("Casimir Thane", since="2189-11-09 23:40", until="2189-11-09 23:50",
                            dry_run=True)
    assert [f["id"] for f in preview["taught"]] == [before, fight]
    assert sorted(f["id"] for f in preview["suggested"]) == sorted([secret, belief])
    assert "npc:Casimir Thane" not in _facts(camp)[fight]["holders"]

    result = notes.witness("Casimir Thane", since="2189-11-09 23:40",
                           until="2189-11-09 23:50", include=[secret])
    facts = _facts(camp)
    for fid in (fight, before, secret):
        assert "npc:Casimir Thane" in facts[fid]["holders"]
    for fid in (belief, elsewhere, late):
        assert "npc:Casimir Thane" not in facts[fid]["holders"]
    assert result["suggested"] and [f["id"] for f in result["suggested"]] == [belief]
    assert notes.witness("Casimir Thane")["taught"][0]["id"] == late  # the rest of the evening
    with pytest.raises(ValueError, match="Not among the facts"):
        notes.witness("Casimir Thane", include=[elsewhere])


def test_creating_an_npc_points_at_witness(world, capsys):
    ws, _ = world
    NoteManager(ws).add_fact("session_events", "Lullaby hummed in the pens.")
    capsys.readouterr()
    NPCManager(ws).create_npc("Grey Coat", "a house guard", "hostile",
                              locations=["The Holding Pens"])
    out = capsys.readouterr().out
    assert 'Was Grey Coat here for what happened before (1 fact(s) at The Holding Pens)?' in out
    assert 'gm-note.sh witness "Grey Coat"' in out


def test_cli(world):
    ws, camp = world

    def run(*args):
        return subprocess.run([sys.executable, str(ROOT / "lib" / "note_manager.py"), *args],
                              capture_output=True, text=True, cwd=str(Path(ws).parent))

    beat = json.dumps([{"fact": "Lullaby lay still."},
                       {"fact": "Benno thinks it broken.", "holders": ["Benno"],
                        "truth": "wrong", "version_of": "#1"}])
    r = run("beat", beat)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[SUCCESS] Recorded f1, f2" in r.stdout
    r = run("witness", "Tod", "--dry-run")
    assert "npc:Tod would learn 0 fact(s)" in r.stdout and "f2" in r.stdout  # Tod knew f1
    r = run("add", "session_events", "x", "--at", "The Sanguine Ring", "--nowhere")
    assert r.returncode == 1 and "not both" in r.stderr
