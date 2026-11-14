"""Looking facts up: gm-note.sh show / find / recent. In play the GM wrote throwaway
Python to read facts.json, since `get` only dumps all of it."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.note_manager import NoteManager, fact_details, fact_line
from tests.sheets import npc, player

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def notes(tmp_path):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    files = {
        "campaign-overview.json": {"campaign_name": "C", "game_time": "2187-10-26T05:35"},
        "character.json": player("Fearghas"),
        "npcs.json": {"Wren": npc("Wren", aliases=["the kid"]),
                      "Seraphine Halcyon-Vey": npc("Seraphine Halcyon-Vey", aliases=["Seraphine"])},
        "locations.json": {},
        "facts.json": {
            "plot_local": [
                {"id": "f1", "fact": "The Spine is ninety levels tall.", "holders": ["public"]},
                {"id": "f2", "fact": "Seraphine ordered the scrub.", "holders": [],
                 "about": ["npc:Seraphine Halcyon-Vey"]},
                {"id": "f3", "fact": "Wren saw Seraphine at the rail.", "holders": ["npc:Wren"],
                 "about": ["npc:Wren", "npc:Seraphine Halcyon-Vey"]},
                {"id": "f4", "fact": "The Lantern is the street's town hall.", "holders": ["street"]}],
            "session_events": [
                {"id": "f5", "fact": "Seraphine is a stranger to Fearghas.", "holders": ["player"],
                 "about": ["npc:Seraphine Halcyon-Vey", "player"], "truth": "wrong",
                 "version_of": "f2", "game_time": "2187-10-26T05:35"},
                {"id": "f6", "fact": "An old fact, from before holders."}]},
    }
    for name, payload in files.items():
        (camp / name).write_text(json.dumps(payload))
    return NoteManager(str(ws)), ws


def ids(found):
    return [f["id"] for f in found]


def test_find_by_holder_counts_public_but_not_street(notes):
    manager, _ = notes
    found = manager.find(held_by=["the kid"])           # an alias works
    assert ids(found) == ["f3", "f1"]                   # newest first
    assert found[1]["public"] and "public" not in found[0]
    assert "(public: everyone)" in fact_line(found[1])
    assert ids(manager.find(held_by=["player", "Wren"])) == ["f1"]


def test_find_by_about_secret_hidden_truth_text(notes):
    manager, _ = notes
    assert ids(manager.find(about=["Seraphine"])) == ["f5", "f3", "f2"]
    assert ids(manager.find(about=["Seraphine"], held_by=["player"])) == ["f5"]
    assert ids(manager.find(about=["Seraphine"], hidden=True)) == ["f3", "f2"]
    assert ids(manager.find(secret=True)) == ["f2"]
    assert ids(manager.find(truth="wrong")) == ["f5"]
    assert ids(manager.find(category="plot_local", text="seraphine RAIL")) == ["f3"]
    assert ids(manager.find()) == ["f6", "f5", "f4", "f3", "f2", "f1"]
    with pytest.raises(ValueError, match="Nothing called 'Nobody'"):
        manager.find(held_by=["Nobody"])


def test_show_gives_the_truth_and_its_versions(notes):
    manager, _ = notes
    truth, belief, old = manager.show(["f2", "f5", "f6"])
    assert truth["versions"] == ["f5"]
    assert "versions of it: f5" in fact_details(truth)
    assert "truth: wrong, a version of f2" in fact_details(belief)
    assert "not recorded (an old fact)" in fact_details(old)
    with pytest.raises(ValueError, match="No fact 'f9'"):
        manager.show(["f9"])


def test_cli(notes):
    _, ws = notes

    def run(*args):
        return subprocess.run([sys.executable, str(ROOT / "lib" / "note_manager.py"), *args],
                              capture_output=True, text=True, cwd=str(Path(ws).parent))

    r = run("find", "--about", "Seraphine", "--limit", "1")
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("f5 [2187-10-26 05:35] [WRONG; the truth is f2]")
    assert "+2 more" in r.stdout
    assert run("recent", "2").stdout.count("\n") == 2
    assert json.loads(run("show", "f2", "--json").stdout)[0]["versions"] == ["f5"]
    assert run("find", "--held-by", "Nobody").returncode == 1
