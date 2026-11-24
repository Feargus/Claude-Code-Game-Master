"""Standing: how each faction regards the character (design-notes.md → "Factions",
step 4a). A world rule with a fixed name, a counter held by factions. A faction can
have its own resting point (`gm-rule.sh rate --toward`), a value changes at once
(`gm-rule.sh change`), and a consequence can carry the same rule effects a rule's
results have: change a value, a rate, or move the point.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import rule_time
from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager, describe_effects
from lib.factions import FactionManager
from lib.json_ops import JsonOperations

CAMPAIGN = "dungeon-crawler-carl"
ROOT = Path(__file__).resolve().parent.parent
STANDING = {"name": "Standing", "block": "counter", "held_by": "faction", "known": False,
            "range": [-5, 5], "start": 0, "summary": "How a faction regards the character.",
            "when": "The character helps or crosses a faction.",
            "rate": {"by": 1, "every": "14d", "toward": 0},
            "results": [{"from": -5, "to": -3, "text": "Hostile.",
                         "gm": "They act against the character."}]}


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    FactionManager(ops).create("Meridian Group", "A security firm.", aliases=["Meridian"])
    wr.define(ops, [STANDING])
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops


def _entry(ops):
    return wr.entry(ops, wr.find_rule(ops, "Standing"), "faction:meridian-group")


def test_standing_is_a_counter_held_by_factions(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    for wrong in ({"held_by": "player"}, {"held_by": ["faction", "npc"]}):
        with pytest.raises(wr.RulesError, match="how each faction regards the character"):
            wr.define(ops, [{**STANDING, **wrong}])


def test_a_faction_rests_at_its_own_point(ops):
    old, new = rule_time.set_rate(ops, "Standing", "Meridian", toward=2)
    assert old["toward"] == 0 and new == {"by": 1, "every": "14d", "toward": 2}
    old, new = rule_time.set_rate(ops, "Standing", "Meridian", shift=-1)
    assert new["toward"] == 1
    _, new = rule_time.set_rate(ops, "Standing", "Meridian", shift=9)     # kept in the range
    assert new["toward"] == 5
    with pytest.raises(wr.RulesError, match="from -5 to 5"):
        rule_time.set_rate(ops, "Standing", "Meridian", toward=7)
    assert rule_time.describe(_entry(ops)["rate"]) == "1 every 14d toward 5"


def test_a_change_is_at_once_and_the_drift_brings_it_back(ops, dcc_world):
    from lib.time_manager import TimeManager
    rule_time.set_rate(ops, "Standing", "Meridian", toward=2)
    wr.change(ops, "Standing", "Meridian", by=2)                   # resting where it is
    report = wr.change(ops, "Standing", "Meridian", by=-5)        # a guard killed
    assert report["after"] == -3 and _entry(ops)["on"] == ["from -5 to -3"]
    TimeManager(dcc_world).advance(60 * 24 * 29, through_all=True)    # four weeks, laying low
    assert _entry(ops)["value"] == -1


def test_the_rate_command_takes_a_point(ops, dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)
    done = subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), "rate", "Standing",
                           "Meridian", "--toward", "-2"], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    assert "rate 1 every 14d toward 0 → 1 every 14d toward -2" in done.stdout


def test_a_rule_effect_moves_the_point(ops):
    import lib.rule_effects as fx
    assert fx._check_one({"rate_of": "Standing", "shift": 1}) == []
    assert fx._check_one({"rate_of": "Standing", "toward": 2, "by": 1}) == []
    assert fx._check_one({"rate_of": "Standing", "toward": 2, "shift": 1})       # one or the other
    assert fx._check_one({"rate_of": "Standing", "shift": 0})
    done = fx.run(ops, {"rate_of": "Standing", "shift": -2}, "faction:meridian-group",
                  fx.new_chain(), "test")
    assert "toward -2" in done["line"] and _entry(ops)["rate"]["toward"] == -2


def test_a_consequence_carries_rule_effects(ops, dcc_world):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence(
        "Meridian hears of the dead guard.", "y", trigger_type="on_fact", match="x",
        effects=[{"type": "rule", "change": "standing", "of": "Meridian", "by": -4},
                 {"type": "rule", "rate_of": "Standing", "of": "Meridian", "shift": -1}])
    stored = next(c for c in json.loads((Path(ops.world_state_dir) / "consequences.json")
                                        .read_text())["active"] if c["id"] == cid)
    assert stored["effects"][0] == {"type": "rule", "change": "Standing",
                                    "of": "faction:meridian-group", "by": -4}
    assert describe_effects(stored["effects"]) == ("Standing of faction:meridian-group -4; "
                                                   "Standing of faction:meridian-group: point -1")
    fired = cm.fire(cid)
    done = "\n".join(fired["effects_done"])
    assert "Standing (Meridian Group): 0 → -4" in done and "Do now: They act against" in done
    assert _entry(ops)["value"] == -4 and _entry(ops)["rate"]["toward"] == -1


@pytest.mark.parametrize("effect, words", [
    ({"clock": "x", "start": 2}, "A rule effect is one of"),
    ({"change": "Standing", "by": -1}, "Whose Standing"),
    ({"change": "Nothing", "of": "Meridian", "by": 1}, "Nothing"),
    ({"change": "Standing", "of": "Meridian", "set": 9}, "goes from -5 to 5"),
])
def test_a_consequences_rule_effect_is_checked(ops, dcc_world, effect, words, capsys):
    cid = ConsequenceManager(dcc_world).add_consequence(
        "x happens.", "y", trigger_type="on_fact", match="x", effects=[{"type": "rule", **effect}])
    assert cid == "" and words in capsys.readouterr().err


def test_the_command_line_takes_a_rule_effect(ops, dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)
    done = subprocess.run(
        ["bash", str(ROOT / "tools" / "gm-consequence.sh"), "add", "The Kin hear of the rescue.",
         "y", "--trigger-type", "on_fact", "--match", "x",
         "--rule-effect", '{"rate_of": "Standing", "of": "Meridian", "shift": 1}'],
        capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("[SUCCESS] Added consequence c")
    stored = ops.load_json("consequences.json")["active"][-1]
    assert "Standing of faction:meridian-group: point +1" in describe_effects(stored["effects"])
