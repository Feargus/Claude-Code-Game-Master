"""A damaged campaign file stops the command; it is never read as empty.

Reading a file that isn't valid JSON as {} let the next save write over it:
recording one fact into a facts.json cut short left a file with that one fact.
"""

import os
import subprocess
from pathlib import Path

import pytest

from lib.json_ops import JsonFileError, JsonOperations

ROOT = Path(__file__).resolve().parent.parent


def _campaign(world) -> Path:
    return Path(world) / "campaigns" / "dungeon-crawler-carl"


def _cut_short(path: Path) -> bytes:
    """Cut a file in half, as a crash or a bad hand edit might. Returns what is left."""
    data = path.read_bytes()[: path.stat().st_size // 2]
    path.write_bytes(data)
    return data


def test_a_missing_file_is_still_the_default(tmp_path):
    ops = JsonOperations(str(tmp_path))
    assert ops.load_json("nothing.json") == {}
    assert ops.load_json("nothing.json", []) == []


def test_a_file_that_is_not_json_raises_and_names_the_spot(tmp_path):
    (tmp_path / "facts.json").write_text('{"lore": [', encoding="utf-8")
    with pytest.raises(JsonFileError, match=r"facts\.json is not valid JSON .* line 1"):
        JsonOperations(str(tmp_path)).load_json("facts.json")


def test_recording_a_fact_leaves_a_damaged_facts_file_alone(dcc_world):
    facts = _campaign(dcc_world) / "facts.json"
    left = _cut_short(facts)
    result = subprocess.run(
        ["bash", str(ROOT / "tools" / "gm-note.sh"), "lore", "A fact after the damage.",
         "--nowhere"],
        capture_output=True, text=True, env=dict(os.environ, GM_WORLD_STATE_BASE=dcc_world))
    assert result.returncode == 1
    assert "facts.json is not valid JSON" in result.stderr
    assert "Traceback" not in result.stderr             # one plain message
    assert "SUCCESS" not in result.stdout
    assert facts.read_bytes() == left                   # not a byte written


def test_a_damaged_character_stops_the_roll_and_the_credits(dcc_world):
    character = _campaign(dcc_world) / "character.json"
    left = _cut_short(character)
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)
    for command in (["gm-skill-contest.sh", "--active", "Tandy", "Awareness", "ITU", "ITU",
                     "NRV", "--reactive-dc", "12", "a test"],
                    ["gm-player.sh", "credits", "+5"]):
        result = subprocess.run(["bash", str(ROOT / "tools" / command[0]), *command[1:]],
                                capture_output=True, text=True, env=env)
        assert result.returncode == 1, command
        assert "character.json is not valid JSON" in result.stderr, command
    assert character.read_bytes() == left


def test_a_damaged_character_stops_the_brief(isolated_world_state):
    """The brief read character.json by itself and showed "No character found"
    for a damaged one, which sends the GM off to create a new character. It
    only stopped when another part of the brief happened to read the file too
    (a wrong belief, an NPC's fact list), so this campaign has none of those."""
    campaign = isolated_world_state / "campaigns" / "test"
    campaign.mkdir()
    (isolated_world_state / "active-campaign.txt").write_text("test")
    (campaign / "campaign-overview.json").write_text('{"campaign_name": "Test"}')
    (campaign / "character.json").write_text('{"identity": {"name": "Dog')
    result = subprocess.run(["bash", str(ROOT / "tools" / "gm-session.sh"), "context"],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "character.json is not valid JSON" in result.stderr
    assert "No character found" not in result.stdout and "Traceback" not in result.stderr
    assert (campaign / "character.json").read_text() == '{"identity": {"name": "Dog'
