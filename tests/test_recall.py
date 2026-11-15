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


# ---------- step d: the cards and the brief rank by the scene ----------

def _here(dcc_world):
    import json
    overview = json.loads((Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"
                           / "campaign-overview.json").read_text())
    return overview["player_position"]["current_location"]


def test_the_place_card_shows_what_fits_the_scene_not_only_the_place(dcc_world, monkeypatch):
    """A fact that matches the scene wins over newer ones that don't, though it
    wasn't recorded at the place; what the character doesn't know has its own list."""
    from lib.cards import Cards
    from lib.location_manager import LocationManager
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    place = _here(dcc_world)
    LocationManager(dcc_world).set_description(place, "Rusted cranes and stacked crates line the street.")
    n = NoteManager(dcc_world)
    old = n.add_fact("lore", "Behind the rusted cranes and stacked crates runs a smuggler's tunnel.",
                     holders=["player"], nowhere=True)
    for food in ("a sandwich", "an apple", "some soup"):
        n.add_fact("session_events", f"Donut ate {food}.", holders=["player"], nowhere=True)
    hidden = n.add_fact("plot_local", "The crates on the street hide stolen cranes parts.",
                        holders=["npc:Mordecai"], nowhere=True)
    card = Cards(n.json_ops).location_card(place)
    known = [line for line in card if line.startswith("  fits here:")]
    assert known and known[0].startswith(f"  fits here: {old} ")
    unknown = [line for line in card if "doesn't know:" in line]
    assert unknown and unknown[0].split(": ", 1)[1].startswith(hidden)


def test_without_vectors_the_place_and_its_people_come_first(dcc_world):
    """GM_EMBEDDER=off (the default in tests): the bonuses and recency decide."""
    from lib.recall import SceneRanker
    n = NoteManager(dcc_world)
    place = _here(dcc_world)
    mine = n.add_fact("lore", "The street floods every spring.", holders=["player"],
                      about=[f"location:{place}"], nowhere=True)
    newer = n.add_fact("lore", "Something happened far away.", holders=["player"], nowhere=True)
    ranker = SceneRanker(n.json_ops, place)
    assert not ranker.by_meaning
    order = [f["id"] for f in ranker.rank([n._entry(n.json_ops.load_json("facts.json"), x)
                                           for x in (newer, mine)])]
    assert order == [mine, newer]


# ---------- step e: a new plot is offered the facts that look part of it ----------

def test_a_new_plot_is_offered_the_facts_closest_to_it(notes, dcc_world):
    from lib.plot_manager import PlotManager
    from lib.recall import suggest_for_plot
    n, ids = notes
    key = PlotManager(dcc_world).add("Circus Debts", "The circus clown and the knives he owes for.")
    found = [f["id"] for f in suggest_for_plot(n, key)["facts"]]
    assert found[:2] and set(found[:2]) <= {ids["clown"], ids["secret"]}
    assert ids["door"] not in found[:2]
