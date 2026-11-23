"""A recorded fact can be given a new text (gm-note.sh edit) or taken out of play
(gm-note.sh remove). A removed fact keeps its id in removed-facts.json, so no
other fact gets it; one that something points at can't be removed."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.consequence_manager import ConsequenceManager
from lib.note_manager import NoteManager

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = "dungeon-crawler-carl"


def _load(world, name):
    path = Path(world) / "campaigns" / CAMPAIGN / name
    return json.loads(path.read_text()) if path.exists() else None


def _fresh(world):
    (Path(world) / "campaigns" / CAMPAIGN / "facts.json").write_text("[]")
    return NoteManager(world)


def test_edit_replaces_the_text_and_follows_the_names(dcc_world):
    nm = _fresh(dcc_world)
    fid = nm.add_fact("Mordecai told Carl the stairs are trapped.")
    assert "npc:Mordecai" in _load(dcc_world, "facts.json")[0]["about"]
    done = nm.edit_fact(fid, "The stairs down are trapped.")
    entry = _load(dcc_world, "facts.json")[0]
    assert entry["fact"] == "The stairs down are trapped."
    assert done["old"] == "Mordecai told Carl the stairs are trapped."
    assert "npc:Mordecai" in done["dropped"] and "npc:Mordecai" not in entry.get("about", [])
    assert entry["holders"] == _load(dcc_world, "facts.json")[0]["holders"]   # untouched


def test_edit_refuses_a_word_the_same_text_and_an_attitude(dcc_world):
    nm = _fresh(dcc_world)
    fid = nm.add_fact("The stairs are trapped.")
    for text in ("trapped", "The stairs are trapped."):
        with pytest.raises(ValueError, match="nothing was changed"):
            nm.edit_fact(fid, text)
    feeling = nm.set_attitude("npc:Mordecai", "wary")
    with pytest.raises(ValueError, match="attitude"):
        nm.edit_fact(feeling, "Mordecai likes Carl.")


def test_remove_keeps_the_fact_aside_and_its_id_is_never_given_again(dcc_world):
    nm = _fresh(dcc_world)
    nm.add_fact("The door is barred.")
    fid = nm.add_fact("The door is barred, said twice.")
    nm.remove_fact(fid)
    assert [f["id"] for f in _load(dcc_world, "facts.json")] == ["f1"]
    removed = _load(dcc_world, "removed-facts.json")
    assert removed[0]["id"] == fid and removed[0]["fact"] == "The door is barred, said twice."
    assert removed[0]["removed"]
    assert nm.add_fact("The window is open.") == "f3"


def test_remove_is_refused_while_something_points_at_the_fact(dcc_world):
    nm = _fresh(dcc_world)
    truth = nm.add_fact("The vault holds nothing.", secret=True)
    lie = nm.add_fact("The vault holds gold.", truth="wrong", version_of=truth)
    told = nm.add_fact("The guards change at dawn.", secret=True)
    cm = ConsequenceManager(dcc_world)
    cm.add_consequence("Word gets out", "Carl talks to the guards",
                       effects=[{"type": "tell", "fact": told, "holders": ["street"]}])
    with pytest.raises(ValueError, match=f"{lie} is a version of it"):
        nm.remove_fact(truth)
    with pytest.raises(ValueError, match="tells it when it fires"):
        nm.remove_fact(told)
    assert len(_load(dcc_world, "facts.json")) == 3                 # nothing was removed
    nm.remove_fact(lie)
    nm.remove_fact(truth)                                            # free now


def test_cli_edit_and_remove(dcc_world):
    nm = _fresh(dcc_world)
    fid = nm.add_fact("The stairs are trapped, Mordecai says.")
    env = dict(os.environ, GM_WORLD_STATE_BASE=str(dcc_world), GM_EMBEDDER="off")
    run = lambda *a: subprocess.run(["bash", "tools/gm-note.sh", *a], cwd=ROOT, env=env,
                                    capture_output=True, text=True)
    r = run("edit", fid, "The stairs are trapped.")
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert lines[0] == f"[SUCCESS] Edited fact {fid}"
    assert lines[1] == "  It said: The stairs are trapped, Mordecai says."
    r = run("remove", fid)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[:2] == [f"[SUCCESS] Removed fact {fid}",
                                         "  It said: The stairs are trapped."]
    r = run("remove", fid)
    assert r.returncode == 1 and r.stderr.startswith("[ERROR] No fact")
