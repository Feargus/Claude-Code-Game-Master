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
        "clown": n.add_fact("The sad clown juggled knives at the circus gate.",
                            holders=["player"]),
        "door": n.add_fact("The stairwell door is braced open with a crate.",
                           holders=["player"]),
        "secret": n.add_fact("The circus clown works for Mordecai.",
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
    late = n.add_fact("A juggler in greasepaint waits by the tent.",
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
    run("gm-note.sh", "add", "The ferry is called Charon.", "--holders", "player")
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
    old = n.add_fact("Behind the rusted cranes and stacked crates runs a smuggler's tunnel.",
                     holders=["player"], nowhere=True)
    for food in ("a sandwich", "an apple", "some soup"):
        n.add_fact(f"Donut ate {food}.", holders=["player"], nowhere=True)
    hidden = n.add_fact("The crates on the street hide stolen cranes parts.",
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
    mine = n.add_fact("The street floods every spring.", holders=["player"],
                      about=[f"location:{place}"], nowhere=True)
    newer = n.add_fact("Something happened far away.", holders=["player"], nowhere=True)
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


# ---------- step e: someone like this exists already ----------

def _open(dcc_world, opened=True):
    import json
    path = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "campaign-overview.json"
    data = json.loads(path.read_text())
    data["opened"] = "2187-10-26T05:00" if opened else None
    path.write_text(json.dumps(data))


def test_a_person_like_an_existing_one_is_refused_in_play(dcc_world, monkeypatch, capsys):
    from lib.npc_manager import NPCManager
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    npcs = NPCManager(dcc_world)
    assert npcs.create_npc("Vex Marrow", "a one-eyed fence who buys stolen crawler loot", nowhere=True)
    _open(dcc_world)
    assert not npcs.create_npc("The Fence", "a one-eyed fence who buys stolen crawler loot",
                               nowhere=True)
    assert "reads like Vex Marrow" in capsys.readouterr().out
    assert npcs.create_npc("The Fence", "a one-eyed fence who buys stolen crawler loot",
                           nowhere=True, another=True)
    assert npcs.create_npc("Pell", "a baker of glowing bread", nowhere=True)     # nothing like it


def test_before_the_opening_nothing_is_checked(dcc_world, monkeypatch):
    """Building a world makes many records at once; each check would load the model."""
    from lib.npc_manager import NPCManager
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    _open(dcc_world, opened=False)
    npcs = NPCManager(dcc_world)
    assert npcs.create_npc("Vex Marrow", "a one-eyed fence who buys stolen crawler loot", nowhere=True)
    assert npcs.create_npc("The Fence", "a one-eyed fence who buys stolen crawler loot", nowhere=True)


# ---------- the check as a fact is recorded (recall_notes.py, 2026-11-22) ----------

def test_a_new_fact_names_the_plot_and_the_person_it_looks_like(dcc_world, monkeypatch, capsys):
    import recall_notes
    from lib.npc_manager import NPCManager
    from lib.plot_manager import PlotManager
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    monkeypatch.setattr(recall_notes, "CONFIDENT", 0.99)    # suggested, not linked
    NPCManager(dcc_world).create_npc("Vex Marrow", "one-eyed fence buying stolen crawler loot",
                                     nowhere=True)
    PlotManager(dcc_world).add("Stolen Loot", "Who buys the stolen crawler loot, and for whom.")
    capsys.readouterr()
    fid = NoteManager(dcc_world).add_fact("The one-eyed fence was buying stolen crawler loot again.",
                                          holders=["player"], nowhere=True)
    printed = capsys.readouterr().out
    assert f"{fid} looks part of Stolen Loot" in printed
    assert f"{fid} reads like it is about npc:Vex Marrow" in printed


def test_a_new_fact_names_the_consequence_it_may_trigger_and_the_log_keeps_it(
        dcc_world, monkeypatch, capsys):
    """Only the trigger is embedded (trigger:<id>), not what the consequence does;
    the GM fires it, never the check; firing by the fact is logged as the answer."""
    from lib.consequence_manager import ConsequenceManager
    from lib.embedding_store import EmbeddingStore
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    camp = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The auditors open the books", "the factor bids",
                             trigger_type="on_fact",
                             match="the factor bids for the contract at the hall")
    capsys.readouterr()
    fid = NoteManager(dcc_world).add_fact("The factor bids for the contract at the hall today.",
                                          holders=["player"], nowhere=True)
    printed = capsys.readouterr().out
    assert f"{fid} may trigger [{cid[:4]}]" in printed
    assert f"gm-consequence.sh fire {cid} --by {fid}" in printed
    assert not any(c["id"] == cid and c.get("fired") for c in cm.waiting_on_fact())   # not fired
    from lib.embedder import FakeEmbedder
    assert f"trigger:{cid}" in EmbeddingStore(camp).vectors(FakeEmbedder.name)
    log = (camp / "recall-check.log").read_text(encoding="utf-8")
    assert f"{fid} trigger {cid}" in log
    cm.fire(cid, by_fact=fid)
    assert f"fired {cid} by {fid}" in (camp / "recall-check.log").read_text(encoding="utf-8")


def test_a_fact_far_from_every_trigger_names_none(dcc_world, monkeypatch, capsys):
    from lib.consequence_manager import ConsequenceManager
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    ConsequenceManager(dcc_world).add_consequence(
        "x", "y", trigger_type="on_fact", match="the factor bids for the contract at the hall")
    capsys.readouterr()
    NoteManager(dcc_world).add_fact("Rain fell on the quiet market.", holders=["player"],
                                    nowhere=True)
    assert "may trigger" not in capsys.readouterr().out


def test_without_the_model_a_fact_is_refused(dcc_world, monkeypatch, capsys):
    import embedder
    monkeypatch.setenv("GM_EMBEDDER", "")
    monkeypatch.setattr(embedder, "files_missing", lambda: ["model_q4.onnx_data"])
    n = NoteManager(dcc_world)
    before = len(n._all())
    assert n.add_fact("The fence came back at dawn.", holders=["player"], nowhere=True) == ""
    assert "gm-recall.sh setup" in capsys.readouterr().err
    assert len(n._all()) == before


def test_a_confident_plot_and_person_are_linked_at_once_with_the_undo(dcc_world, monkeypatch, capsys):
    """From CONFIDENT a plot or a person is linked, not suggested (2026-11-22)."""
    import recall_notes                       # as note_manager imports it
    from lib.npc_manager import NPCManager
    from lib.plot_manager import PlotManager
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    monkeypatch.setattr(recall_notes, "CONFIDENT", 0.30)    # the fake embedder's plot score is low
    NPCManager(dcc_world).create_npc("Vex Marrow", "one-eyed fence buying stolen crawler loot",
                                     nowhere=True)
    PlotManager(dcc_world).add("Stolen Loot", "Who buys the stolen crawler loot, and for whom.")
    capsys.readouterr()
    n = NoteManager(dcc_world)
    fid = n.add_fact("The one-eyed fence was buying stolen crawler loot again.",
                     holders=["player"], nowhere=True)
    printed = capsys.readouterr().out
    assert f"{fid} put in Stolen Loot by recall" in printed
    assert f"gm-note.sh plot {fid} --remove \"Stolen Loot\"" in printed
    assert f"{fid} is about npc:Vex Marrow too, by recall" in printed
    fact = next(f for f in n._all() if f["id"] == fid)
    assert fact["plots"] == ["Stolen Loot"] and "npc:Vex Marrow" in fact["about"]


def test_a_new_fact_that_repeats_an_earlier_one_is_named_with_the_fix(dcc_world, monkeypatch, capsys):
    """"X told Y …" after the news is on record: tell the earlier fact, keep only
    what is new. Versions of one truth are meant to resemble it: never named."""
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    nm = NoteManager(dcc_world)
    news = nm.add_fact("Seren is to marry Strake at the next feast of the Steward.",
                       holders=["npc:Mordecai"], nowhere=True)
    capsys.readouterr()
    told = nm.add_fact("Seren is to marry Strake at the next feast of the Steward, she said.",
                       holders=["player", "npc:Mordecai"], nowhere=True)
    printed = capsys.readouterr().out
    assert f"[CHECK] {told} may repeat {news}" in printed
    assert f"gm-note.sh tell {news} player --from" in printed
    assert f"gm-note.sh edit {told}" in printed
    again = nm.add_fact("Seren is to marry Strake at the next feast of the Steward, again.",
                        holders=["npc:Mordecai"], nowhere=True)
    assert f"They know {news} already. If it does: bash tools/gm-note.sh remove {again}" \
        in capsys.readouterr().out
    nm.add_fact("Seren is to marry Strake at the last feast of the Steward.", holders=["player"],
                truth="wrong", version_of=news, nowhere=True)
    assert f"may repeat {news}" not in capsys.readouterr().out
