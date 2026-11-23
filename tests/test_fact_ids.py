"""Facts carry an id and the in-game time.

Ids let other records point to a fact (a consequence fired by it, later
holders and versions). The in-game time places it in the story, where the
real-world timestamp only says when the session was played.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.note_manager import NoteManager, fact_file

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = "dungeon-crawler-carl"


def _campaign_dir(world):
    return Path(world) / "campaigns" / CAMPAIGN


def _load(world, name):
    return json.loads((_campaign_dir(world) / name).read_text())


def _save(world, name, data):
    (_campaign_dir(world) / name).write_text(json.dumps(data))


def _set_game_time(world, value):
    overview = _load(world, "campaign-overview.json")
    if value is None:
        overview.pop("game_time", None)
    else:
        overview["game_time"] = value
    _save(world, "campaign-overview.json", overview)


def test_new_fact_gets_id_and_game_time(dcc_world):
    _save(dcc_world, "facts.json", [])
    _set_game_time(dcc_world, "2187-10-26T05:35")
    fid = NoteManager(dcc_world).add_fact("The door was barred")
    entry = _load(dcc_world, "facts.json")[0]
    assert fid == "f1"
    assert entry["id"] == "f1"
    assert entry["game_time"] == "2187-10-26T05:35"
    assert entry["timestamp"]


def test_the_file_is_one_list_in_id_order(dcc_world):
    """facts.json is a plain list (lib/facts.py); a file made empty is no facts."""
    _save(dcc_world, "facts.json", {})
    nm = NoteManager(dcc_world)
    assert [nm.add_fact("one"), nm.add_fact("two"), nm.add_fact("three")] == ["f1", "f2", "f3"]
    assert [(f["id"], f["fact"]) for f in _load(dcc_world, "facts.json")] == [
        ("f1", "one"), ("f2", "two"), ("f3", "three")]
    assert "category" not in _load(dcc_world, "facts.json")[0]


def test_no_game_time_in_campaign_leaves_it_out(dcc_world):
    _save(dcc_world, "facts.json", [])
    _set_game_time(dcc_world, None)
    NoteManager(dcc_world).add_fact("timeless")
    entry = _load(dcc_world, "facts.json")[0]
    assert "game_time" not in entry
    assert entry["id"] == "f1"


def test_a_new_id_follows_the_highest(dcc_world):
    _save(dcc_world, "facts.json", [{"id": "f7", "fact": "kept"}, {"id": "f3", "fact": "older"}])
    assert NoteManager(dcc_world).add_fact("new") == "f8"


def test_everything_but_the_text_is_given_by_name(dcc_world):
    """The old call, add_fact("<category>", "<fact>"), must not record the category
    as the fact."""
    with pytest.raises(TypeError):
        NoteManager(dcc_world).add_fact("session_events", "The door was barred")


def test_a_file_by_category_is_refused_with_the_reason(dcc_world):
    """The form used until 2026-11-16. Those campaigns were retired, not converted;
    the command says so instead of failing somewhere inside."""
    old = {"lore": [{"id": "f1", "fact": "The moon is a ship."}], "session_events": []}
    _save(dcc_world, "facts.json", old)
    with pytest.raises(fact_file.FactsError, match="by category"):
        NoteManager(dcc_world).add_fact("A new fact")
    assert _load(dcc_world, "facts.json") == old                 # left as it was
    result = subprocess.run(["bash", str(ROOT / "tools" / "gm-session.sh"), "context"],
                            capture_output=True, text=True,
                            env=dict(os.environ, GM_WORLD_STATE_BASE=dcc_world))
    assert result.returncode == 1 and "Traceback" not in result.stderr
    assert "[ERROR]" in result.stderr and "start a new campaign" in result.stderr
