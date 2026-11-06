"""Facts carry an id and the in-game time.

Ids let other records point to a fact (a consequence fired by it, later
holders and versions). The in-game time places it in the story, where the
real-world timestamp only says when the session was played.
"""

import json
from pathlib import Path

from lib.note_manager import NoteManager

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


def _all_facts(world):
    return [f for items in _load(world, "facts.json").values() for f in items]


def test_new_fact_gets_id_and_game_time(dcc_world):
    _save(dcc_world, "facts.json", {})
    _set_game_time(dcc_world, "2187-10-26T05:35")
    fid = NoteManager(dcc_world).add_fact("session_events", "The door was barred")
    entry = _load(dcc_world, "facts.json")["session_events"][0]
    assert fid == "f1"
    assert entry["id"] == "f1"
    assert entry["game_time"] == "2187-10-26T05:35"
    assert entry["timestamp"]


def test_ids_count_up_across_categories(dcc_world):
    _save(dcc_world, "facts.json", {})
    nm = NoteManager(dcc_world)
    assert nm.add_fact("lore", "one") == "f1"
    assert nm.add_fact("plot_local", "two") == "f2"
    assert nm.add_fact("lore", "three") == "f3"


def test_no_game_time_in_campaign_leaves_it_out(dcc_world):
    _save(dcc_world, "facts.json", {})
    _set_game_time(dcc_world, None)
    NoteManager(dcc_world).add_fact("lore", "timeless")
    entry = _load(dcc_world, "facts.json")["lore"][0]
    assert "game_time" not in entry
    assert entry["id"] == "f1"


def test_old_facts_get_ids_in_recorded_order(dcc_world):
    """Facts from before ids existed are numbered oldest first, across categories."""
    _save(dcc_world, "facts.json", {
        "lore": [{"fact": "second", "timestamp": "2026-10-02T00:00:00+00:00"}],
        "session_events": [{"fact": "first", "timestamp": "2026-10-01T00:00:00+00:00"},
                           "a bare string"],
    })
    NoteManager(dcc_world).add_fact("lore", "newest")
    by_text = {f["fact"]: f["id"] for f in _all_facts(dcc_world)}
    # The bare string has no timestamp, so it sorts first.
    assert by_text == {"a bare string": "f1", "first": "f2", "second": "f3", "newest": "f4"}


def test_existing_ids_are_kept(dcc_world):
    _save(dcc_world, "facts.json", {
        "lore": [{"id": "f7", "fact": "kept", "timestamp": "2026-10-01T00:00:00+00:00"},
                 {"fact": "unnumbered", "timestamp": "2026-10-02T00:00:00+00:00"}],
    })
    assert NoteManager(dcc_world).add_fact("lore", "new") == "f9"
    by_text = {f["fact"]: f["id"] for f in _all_facts(dcc_world)}
    assert by_text == {"kept": "f7", "unnumbered": "f8", "new": "f9"}
