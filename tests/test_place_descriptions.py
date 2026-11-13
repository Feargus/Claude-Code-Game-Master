"""A place is on disk before it is narrated (2026-11-13).

In the Tidewater playtest the Kettle was added with a position only, while Mama
Seo described it in the story ("coffins they rent by the week, stacked eight
high"): nothing of that was saved, so a later visit would reinvent it. Now a new
place needs a description, a move refuses a place with none (before any travel
time passes), and the brief shows the current place's description to narrate from.
"""

import json
import os
import subprocess
from pathlib import Path

from lib.location_manager import LocationManager
from lib.session_manager import SessionManager

ROOT = Path(__file__).resolve().parent.parent
CAMP = ("campaigns", "dungeon-crawler-carl")


def _tool(dcc_world, tool, *args):
    return subprocess.run(["bash", str(ROOT / "tools" / tool), *args],
                          capture_output=True, text=True,
                          env={**os.environ, "GM_WORLD_STATE_BASE": str(dcc_world)})


def _load(dcc_world, name):
    return json.loads(Path(dcc_world, *CAMP, name).read_text())


def test_a_new_place_needs_a_description(dcc_world, capsys):
    locations = LocationManager(dcc_world)
    assert not locations.add_location("The Kettle", "two streets down", "  ")
    assert "needs a description" in capsys.readouterr().out
    assert "The Kettle" not in _load(dcc_world, "locations.json")
    assert locations.add_location("The Kettle", "two streets down",
                                  "A capsule hostel, coffins stacked eight high.")
    assert _load(dcc_world, "locations.json")["The Kettle"]["description"].startswith("A capsule")


def test_the_command_takes_the_description(dcc_world):
    result = _tool(dcc_world, "gm-location.sh", "add", "The Kettle", "two streets down")
    assert result.returncode != 0 and "<description>" in result.stdout
    result = _tool(dcc_world, "gm-location.sh", "add", "The Kettle", "two streets down",
                   "A capsule hostel.", "--alias", "the Kettle hostel")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _load(dcc_world, "locations.json")["The Kettle"]["description"] == "A capsule hostel."


def test_describe_replaces_by_alias_and_shows_the_old_text(dcc_world, capsys):
    locations = LocationManager(dcc_world)
    locations.add_location("The Kettle", "two streets down", "A capsule hostel.",
                           aliases=["the Kettle hostel"])
    capsys.readouterr()
    assert not locations.set_description("The Kettle", "")
    assert locations.set_description("the Kettle hostel", "A capsule hostel, eight high.")
    out = capsys.readouterr().out
    assert "It was: A capsule hostel." in out
    assert _load(dcc_world, "locations.json")["The Kettle"]["description"].endswith("eight high.")


def test_a_move_to_an_unknown_place_is_refused_before_time_passes(dcc_world):
    _tool(dcc_world, "gm-time.sh", "set", "2187-10-26 22:00")
    before = _load(dcc_world, "campaign-overview.json")
    result = _tool(dcc_world, "gm-session.sh", "move", "The Kettle", "--takes", "20m")
    assert result.returncode != 0
    assert "gm-location.sh add" in result.stderr
    after = _load(dcc_world, "campaign-overview.json")
    assert after["game_time"] == before["game_time"] == "2187-10-26T22:00"
    assert after["player_position"] == before["player_position"]
    assert "The Kettle" not in _load(dcc_world, "locations.json")


def test_a_move_to_an_undescribed_place_is_refused(dcc_world):
    assert not _load(dcc_world, "locations.json")["Bone Garden"].get("description")
    result = _tool(dcc_world, "gm-session.sh", "move", "Bone Garden", "--takes", "5m")
    assert result.returncode != 0
    assert 'gm-location.sh describe "Bone Garden"' in result.stderr


def test_a_move_by_alias_goes_to_the_place(dcc_world):
    LocationManager(dcc_world).add_location("The Kettle", "two streets down",
                                            "A capsule hostel.", aliases=["the Kettle hostel"])
    SessionManager(dcc_world).move_party("the Kettle hostel")
    overview = _load(dcc_world, "campaign-overview.json")
    assert overview["player_position"]["current_location"] == "The Kettle"
    assert overview["scene"]["location"] == "The Kettle"
    assert list(_load(dcc_world, "locations.json")).count("the Kettle hostel") == 0


def test_the_brief_shows_the_place_and_its_exits(dcc_world):
    LocationManager(dcc_world).add_location("The Kettle", "two streets down",
                                            "Coffins rented by the week, stacked eight high.")
    SessionManager(dcc_world).move_party("The Kettle")
    brief = SessionManager(dcc_world).get_full_context()
    assert "Here: Coffins rented by the week, stacked eight high." in brief
    assert "Exits: Warehouse Street Level (traveled)" in brief


def test_the_brief_asks_for_a_missing_description(dcc_world):
    brief = SessionManager(dcc_world).get_full_context()
    assert 'Here: (no description yet: write one before narrating the place' in brief


def test_gm_note_takes_an_optional_add(dcc_world):
    result = _tool(dcc_world, "gm-note.sh", "add", "plot_local", "The Kettle smells of feet.",
                   "--secret")
    assert result.returncode == 0, result.stdout + result.stderr
    facts = _load(dcc_world, "facts.json")
    assert "add" not in facts
    assert facts["plot_local"][-1]["fact"] == "The Kettle smells of feet."
