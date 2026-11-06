"""A consequence can have several structured triggers; any one fires it.

Before, a consequence had one trigger_type + match, so "at the Yard, or when
Wren is present" needed two linked entries resolved by hand.
"""

import json
import subprocess
import sys
from pathlib import Path

from lib.consequence_manager import ConsequenceManager

ROOT = Path(__file__).resolve().parent.parent


def _consq_path(world):
    return Path(world) / "campaigns" / "dungeon-crawler-carl" / "consequences.json"


def _entry(world, cid):
    data = json.loads(_consq_path(world).read_text(encoding="utf-8"))
    return next(c for c in data["active"] if c["id"] == cid)


TWO = [{"type": "on_location", "match": "Yard"}, {"type": "on_npc", "match": "Wren"}]


def test_stores_a_list_of_triggers(dcc_world):
    cid = ConsequenceManager(dcc_world).add_consequence(
        "Priests come asking", "at the Yard or when Wren is around", triggers=TWO)
    assert _entry(dcc_world, cid)["triggers"] == TWO


def test_any_one_trigger_fires_it(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("Priests come asking", "free text", triggers=TWO)
    c = _entry(dcc_world, cid)
    at_yard = {"location": "Old Iron's Yard", "present_npcs": []}
    with_wren = {"location": "The Lantern", "present_npcs": ["Wren"]}
    neither = {"location": "The Lantern", "present_npcs": ["Auntie Ro"]}
    assert cm._evaluate_trigger(c, at_yard)[0] == 1.0
    score, reason = cm._evaluate_trigger(c, with_wren)
    assert score == 1.0 and "Wren" in reason
    assert cm._evaluate_trigger(c, neither)[0] == 0.0


def test_single_shorthand_and_list_combine(dcc_world):
    cid = ConsequenceManager(dcc_world).add_consequence(
        "x", "y", trigger_type="on_time", match="night", triggers=TWO[:1])
    assert _entry(dcc_world, cid)["triggers"] == [
        {"type": "on_location", "match": "Yard"}, {"type": "on_time", "match": "night"}]


def test_old_single_trigger_entries_still_fire(dcc_world):
    cm = ConsequenceManager(dcc_world)
    old = {"id": "old1", "consequence": "c", "trigger": "t",
           "trigger_type": "on_location", "match": "Yard"}
    assert cm.structured_triggers(old) == [{"type": "on_location", "match": "Yard"}]
    assert cm._evaluate_trigger(old, {"location": "Old Iron's Yard"})[0] == 1.0


def test_refuses_a_bad_trigger_in_the_list(dcc_world):
    cm = ConsequenceManager(dcc_world)
    assert cm.add_consequence("x", "y", triggers=[TWO[0], {"type": "on_time", "match": "2187-10-26"}]) == ""
    assert cm.add_consequence("x", "y", triggers=[{"type": "on_location", "match": ""}]) == ""
    assert cm.add_consequence("x", "y", triggers=[{"type": "on_whim", "match": "z"}]) == ""


def _cli(world, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "lib" / "consequence_manager.py"), "add", *args, "--json"],
        capture_output=True, text=True, cwd=str(Path(world).parent))


def test_cli_pairs_repeated_flags_in_order(dcc_world):
    r = _cli(dcc_world, "Priests come asking", "free text",
             "--trigger-type", "on_location", "--match", "Yard",
             "--trigger-type", "on_npc", "--match", "Wren")
    assert r.returncode == 0, r.stdout + r.stderr
    cid = json.loads(r.stdout)["data"]["id"]
    assert _entry(dcc_world, cid)["triggers"] == TWO


def test_cli_refuses_unpaired_flags(dcc_world):
    r = _cli(dcc_world, "x", "y", "--trigger-type", "on_location",
             "--trigger-type", "on_npc", "--match", "Wren")
    assert r.returncode == 1
    assert "exactly one --match per --trigger-type" in r.stdout
