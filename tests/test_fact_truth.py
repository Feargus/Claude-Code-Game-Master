"""truth and version_of: wrong and partial versions of a fact.

A missing `truth` means true. `partial` is true but leaves things out; `wrong`
is plain wrong. `version_of` points at the fullest true version, never at a
version of it (so the truth is always one step away) and never at a wrong
fact. Wherever a fact's text reaches the GM it is marked, and the brief lists
what the player character gets wrong next to the truth.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.note_manager import NoteManager, fact_text
from lib.session_manager import SessionManager
from lib.world_tick import WorldTick, WorldTickError

CAMPAIGN = "dungeon-crawler-carl"


def _fact(world, fid):
    facts = json.loads((Path(world) / "campaigns" / CAMPAIGN / "facts.json").read_text(encoding="utf-8"))
    return next(f for items in facts.values() for f in items
                if isinstance(f, dict) and f.get("id") == fid)


@pytest.fixture
def message(dcc_world):
    """The decryption example: the truth held by nobody, a misreading held by the player."""
    nm = NoteManager(dcc_world)
    true = nm.add_fact("plot_local", "The message names the drop: the back room, dawn.", secret=True)
    wrong = nm.add_fact("plot_local", "The message names the drop: Pier 9 at midnight.",
                        holders=["player"], truth="wrong", version_of=true)
    return nm, true, wrong


def test_fact_text_marks_wrong_and_partial():
    assert fact_text({"fact": "x"}) == "x"
    assert fact_text({"fact": "x", "truth": "wrong", "version_of": "f4"}) == "[WRONG; the truth is f4] x"
    assert fact_text({"fact": "x", "truth": "wrong"}) == "[WRONG] x"
    assert fact_text({"fact": "x", "truth": "partial", "version_of": "f4"}) == "[PARTIAL; fuller: f4] x"


def test_recording_a_wrong_version(message, capsys):
    nm, true, wrong = message
    entry = _fact(nm.world_state_dir, wrong)
    assert entry["truth"] == "wrong" and entry["version_of"] == true
    assert "truth" not in _fact(nm.world_state_dir, true)
    nm.add_fact("lore", "Another misreading", truth="wrong", version_of=true)
    assert f"[WRONG; the truth is {true}]" in capsys.readouterr().out


def test_a_version_of_a_version_points_at_the_root(message, capsys):
    nm, true, wrong = message
    # f(wrong) isn't a valid target (it's wrong); a partial version of the truth is.
    part = nm.add_fact("lore", "The message names a drop.", holders=["street"],
                       truth="partial", version_of=true)
    third = nm.add_fact("lore", "Something about a drop.", holders=["public"],
                        truth="partial", version_of=part)
    assert _fact(nm.world_state_dir, third)["version_of"] == true
    assert f"{part} is itself a version of {true}; pointing at {true}" in capsys.readouterr().out


def test_pointing_at_a_wrong_version_points_at_its_truth(message, capsys):
    nm, true, wrong = message
    fid = nm.add_fact("lore", "The drop is at Pier 8", truth="wrong", version_of=wrong)
    assert _fact(nm.world_state_dir, fid)["version_of"] == true
    assert f"pointing at {true}" in capsys.readouterr().out


def test_refusals(message, capsys):
    nm, true, wrong = message
    rumour = nm.add_fact("lore", "Mordecai is a spy", truth="wrong")       # wrong, no truth behind
    assert nm.add_fact("lore", "x", truth="partial", version_of=rumour) == ""
    assert "marked wrong" in capsys.readouterr().err
    assert nm.add_fact("lore", "x", truth="wrong", version_of="f9999") == ""
    assert nm.add_fact("lore", "x", version_of=true) == ""                       # needs a truth
    assert "give --truth too" in capsys.readouterr().err
    assert nm.add_fact("lore", "x", truth="maybe") == ""


def test_set_truth_later(dcc_world):
    nm = NoteManager(dcc_world)
    rumour = nm.add_fact("lore", "Mordecai is a spy.", holders=["street"])
    entry = nm.set_truth(rumour, "wrong")                      # a wrong rumour needs no truth
    assert entry["truth"] == "wrong" and "version_of" not in entry
    assert "truth" not in nm.set_truth(rumour, "true")
    true = nm.add_fact("lore", "Mordecai works for the guild.", secret=True)
    entry = nm.set_truth(rumour, "wrong", version_of=true)
    assert entry["version_of"] == true
    with pytest.raises(ValueError, match="their truth"):
        nm.set_truth(true, "wrong")                            # others point at it
    with pytest.raises(ValueError, match="itself"):
        nm.set_truth(true, "partial", version_of=true)
    assert "version_of" not in nm.set_truth(rumour, "wrong", keep_version=False)


def test_the_brief_marks_and_lists_wrong_beliefs(message):
    nm, true, wrong = message
    nm.add_fact("plot_local", "The guild pays in scrip.", holders=["player"], truth="partial")
    ctx = SessionManager(nm.world_state_dir).get_full_context()
    assert f"[WRONG; the truth is {true}] The message names the drop: Pier 9" in ctx   # KEY FACTS
    i = ctx.index("GETS WRONG")
    section = ctx[i:ctx.index("\n---", i)]
    assert f"{wrong} (believes): The message names the drop: Pier 9 at midnight." in section
    assert f"→ truth, {true}: The message names the drop: the back room, dawn." in section
    assert "(knows only part): The guild pays in scrip." in section


def test_a_present_npc_who_believes_it_wrongly(message):
    from tests.scene_helpers import put_in_scene
    nm, true, wrong = message
    put_in_scene(Path(nm.world_state_dir) / "campaigns" / CAMPAIGN, "Mordecai")
    nm.tell(wrong, ["Mordecai"])
    ctx = SessionManager(nm.world_state_dir).get_full_context()
    assert f"they know: [WRONG; the truth is {true}] The message names the drop: Pier 9" in ctx


def test_world_tick_plants_a_lie(dcc_world):
    nm = NoteManager(dcc_world)
    true = nm.add_fact("lore", "The guild bombed the depot.", secret=True)
    applied = WorldTick(dcc_world).apply([
        {"fact": "A gas leak destroyed the depot.", "holders": ["public"],
         "truth": "wrong", "version_of": true}])
    assert _fact(dcc_world, applied[0]["fact"])["truth"] == "wrong"
    rumour = nm.add_fact("lore", "The depot was haunted.", truth="wrong")
    with pytest.raises(WorldTickError, match="marked wrong"):
        WorldTick(dcc_world).apply([{"fact": "y", "truth": "wrong", "version_of": rumour}])


def test_cli(dcc_world):
    root = Path(__file__).resolve().parent.parent
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(root / "lib" / "note_manager.py"), *a],
        capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    r = run("add", "lore", "The drop is at dawn", "--secret")
    true = r.stdout.split("Recorded fact ")[1].split()[0]
    r = run("add", "lore", "The drop is at midnight", "--holders", "player",
            "--truth", "wrong", "--version-of", true)
    assert r.returncode == 0, r.stderr
    wrong = r.stdout.split("Recorded fact ")[1].split()[0]
    r = run("truth", wrong, "partial")
    assert r.returncode == 0 and f"{wrong}: [PARTIAL; fuller: {true}]" in r.stdout
    r = run("truth", true, "wrong")
    assert r.returncode == 1 and "their truth" in r.stderr


def test_a_secret_is_marked_wherever_its_text_shows(dcc_world):
    assert fact_text({"fact": "x", "holders": []}) == "[SECRET] x"
    assert fact_text({"fact": "x"}) == "x"                        # old fact: not recorded
    assert fact_text({"fact": "x", "holders": ["player"]}) == "x"
    nm = NoteManager(dcc_world)
    nm.add_fact("plot_local", "The vault code is 0451.", secret=True)
    ctx = SessionManager(dcc_world).get_full_context()
    assert "- [SECRET] The vault code is 0451." in ctx            # KEY FACTS
