"""Recall by meaning: gm-note.sh find --like (step 12c, 2026-11-15). The fake
embedder stands in for the model: texts that share words count as close."""

import subprocess
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from lib.note_manager import NoteManager  # noqa: E402
from lib.recall import find_like  # noqa: E402

TOOLS = Path(__file__).resolve().parent.parent / "tools"


@pytest.fixture
def notes(dcc_world, monkeypatch):
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    n = NoteManager(dcc_world)
    ids = {
        "clown": n.add_fact("session_events", "The sad clown juggled knives at the circus gate.",
                            holders=["player"]),
        "door": n.add_fact("session_events", "The stairwell door is braced open with a crate.",
                           holders=["player"]),
        "secret": n.add_fact("plot_local", "The circus clown works for Mordecai.",
                             holders=["npc:Mordecai"]),
    }
    return n, ids


def test_the_closest_fact_comes_first(notes):
    n, ids = notes
    result = find_like(n, "a clown at the circus", limit=3)
    assert result["method"] == "meaning"
    assert result["facts"][0]["id"] in (ids["clown"], ids["secret"])
    assert ids["door"] not in [f["id"] for f in result["facts"][:2]]


def test_who_knows_it_filters_and_near_misses_are_named(notes):
    n, ids = notes
    result = find_like(n, "the circus clown", limit=1, held_by=["player"])
    assert [f["id"] for f in result["facts"]] == [ids["clown"]]
    assert (ids["secret"], "not held by player") in result["near_misses"]


def test_about_raises_the_rank_but_excludes_nothing(notes):
    n, ids = notes
    result = find_like(n, "a door", limit=0, about=["npc:Mordecai"])
    found = [f["id"] for f in result["facts"]]
    assert ids["door"] in found and ids["clown"] in found          # not about Mordecai, still there
    plain = {f["id"]: f["score"] for f in find_like(n, "a door", limit=0)["facts"]}
    boosted = {f["id"]: f["score"] for f in result["facts"]}
    assert boosted[ids["secret"]] == pytest.approx(plain[ids["secret"]] + 0.10)


def test_a_fact_not_embedded_yet_is_embedded_by_the_query(notes, monkeypatch):
    """Recorded after the background job ran: the query embeds it itself."""
    n, ids = notes
    monkeypatch.setenv("GM_EMBEDDER", "off")                     # no update this time
    late = n.add_fact("session_events", "A juggler in greasepaint waits by the tent.",
                      holders=["player"])
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    result = find_like(n, "juggler greasepaint tent", limit=1)
    assert result["not_embedded"] == 0 and result["facts"][0]["id"] == late


def test_without_the_model_keywords_rank(notes, monkeypatch):
    n, ids = notes
    monkeypatch.setenv("GM_EMBEDDER", "off")
    result = find_like(n, "stairwell door", limit=1)
    assert result["method"] == "keywords" and result["facts"][0]["id"] == ids["door"]


def test_the_command(isolated_world_state):
    def run(*args):
        return subprocess.run(["bash", str(TOOLS / args[0]), *args[1:]], capture_output=True, text=True)
    run("gm-campaign.sh", "create", "t")
    run("gm-campaign.sh", "switch", "t")
    run("gm-note.sh", "add", "session_events", "The ferry is called Charon.", "--holders", "player")
    out = run("gm-note.sh", "find", "--like", "the ferry")
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("Facts ranked by keywords") and "Charon" in out.stdout
    gone = run("gm-recall.sh", "recall", "the ferry")
    assert gone.returncode == 1 and "find --like" in gone.stderr
