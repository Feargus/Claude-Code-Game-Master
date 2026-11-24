"""The bag (lib/rule_bag.py): tokens drawn, kept out or put back,
added and taken; drawn by itself as time passes; a drawn token's result acts."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib import rule_bag
from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager
from lib.json_ops import JsonOperations
from lib.time_manager import TimeManager

ROOT = Path(__file__).resolve().parent.parent

JOB = {"name": "The Job", "block": "bag", "held_by": ["world", "location"], "known": True,
       "summary": "How far the crew's luck holds.", "when": "Each risky step: draw.",
       "tokens": {"clean": 2, "trouble": 1}, "draw": "keep out",
       "results": {"clean": {"text": "As planned."},
                   "trouble": {"text": "Something goes wrong.", "gm": "An alarm, a guard, a door."}},
       "when_empty": "The luck has run out: the job goes loud now."}
SEA = {"name": "Sea level", "block": "counter", "held_by": "world", "range": [0, 10], "start": 2,
       "rate": {"by": 1, "every": "90d"}, "summary": "The sea.", "when": "By itself."}
MELT = {"name": "The Melt", "block": "bag", "held_by": "world", "known": False,
        "summary": "What each year does to the ice.", "when": "Drawn by itself once a year.",
        "tokens": {"calm year": 6, "warm year": 3, "collapse": 1}, "draw": "put back",
        "draw_every": "360d",
        "results": {"calm year": {"text": "The sea keeps its pace."},
                    "warm year": {"text": "Faster this year.",
                                  "effects": [{"rate_of": "Sea level", "by": 1}]},
                    "collapse": {"text": "A shelf goes.",
                                 "effects": [{"change": "Sea level", "by": 2},
                                             {"tokens": "The Melt", "add": {"Collapse": 1}}]}}}
MISTAKES = {"name": "Mistakes", "block": "counter", "held_by": "world", "range": [0, 9],
            "summary": "Failed rolls on the job.", "when": "Each failed roll.",
            "results": [{"from": 1, "text": "Sloppy.",
                         "effects": [{"tokens": "The Job", "add": {"trouble": 1}}]}]}


class Fixed:
    """Draws the token at `index` of the bag (clamped)."""

    def __init__(self, index):
        self.index = index

    def randint(self, a, b):
        return min(max(self.index, a), b)


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    (Path(ops.world_state_dir) / "factions.json").unlink()   # no faction bag drawing too
    wr.define(ops, [JOB, SEA, MELT, MISTAKES])
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops


def _tokens(ops, rule="The Job", holder="world"):
    return wr.entry(ops, wr.find_rule(ops, rule), holder)["tokens"]


def test_tokens_kept_out_change_the_odds_until_the_bag_is_empty(ops):
    first = rule_bag.draw(ops, "The Job", "world", rng=Fixed(99))      # the last token: trouble
    assert [d["kind"] for d in first["draws"]] == ["trouble"] and first["left"] == {"clean": 2, "trouble": 0}
    text = "\n".join(rule_bag.draw_lines(ops, first))
    assert text.startswith("The Job (the world): drew trouble (left: 2 clean, 0 trouble)\n"
                           "  trouble: Something goes wrong.\n    Do now: An alarm, a guard, a door.")
    rest = rule_bag.draw(ops, "The Job", "world", count=3, rng=Fixed(0))
    assert [d["kind"] for d in rest["draws"]] == ["clean", "clean"]
    assert rest["empty"] == "The luck has run out: the job goes loud now."
    assert "  Empty: The luck has run out" in "\n".join(rule_bag.draw_lines(ops, rest))
    assert wr.load_state(ops)["world"]["The Job"]["drawn"] == ["trouble", "clean", "clean"]
    nothing = rule_bag.draw(ops, "The Job", "world")
    assert nothing["draws"] == [] and nothing["empty"]


def test_put_take_and_refill(ops):
    assert rule_bag.put(ops, "The Job", "world", "Trouble", 2)["after"] == {"clean": 2, "trouble": 3}
    with pytest.raises(ValueError, match="has 2 clean, not 5 to take out"):
        rule_bag.put(ops, "The Job", "world", "clean", -5)
    with pytest.raises(ValueError, match="no tokens 'luck'"):
        rule_bag.put(ops, "The Job", "world", "luck", 1)
    rule_bag.draw(ops, "The Job", "world", rng=Fixed(0))
    back = rule_bag.refill(ops, "The Job", "world")
    assert back["after"] == {"clean": 2, "trouble": 1} and wr.load_state(ops)["world"]["The Job"]["drawn"] == []


def test_a_bag_drawn_by_itself_and_its_effects(dcc_world, ops):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The ice shelf goes on the news", "a collapse",
                             trigger_type="on_rule", match="The Melt:COLLAPSE")
    import random
    random.seed(4)
    manager = TimeManager(dcc_world)
    manager.advance(720 * 24 * 60, through_all=True)                         # two years: two draws
    draws = [r for r in manager.rule_changes if r["rule"] == "The Melt"]
    assert len(draws) == 2 and all(len(d["draws"]) == 1 for d in draws)   # each at its moment
    at = [m["at"] for m in manager.moments if any(r["rule"] == "The Melt" for r in m["rules"])]
    assert (at[1] - at[0]).days == 360
    assert _tokens(ops, "The Melt")["calm year"] == 6           # put back
    report = rule_bag.draw(ops, "The Melt", rng=Fixed(99))      # the last token: collapse
    assert report["draws"][0]["kind"] == "collapse"
    did = report["draws"][0]["did"]
    assert did[0]["report"]["rule"] == "Sea level"
    assert did[1]["line"] == "The Melt (the world): +1 collapse (now 6 calm year, 3 warm year, 2 collapse)"
    assert cid in [c["id"] for c in report["draws"][0]["fired"]]
    warm = rule_bag.draw(ops, "The Melt", rng=Fixed(6))         # a warm year
    assert warm["draws"][0]["did"][0]["line"].startswith("Sea level (the world): rate +1")


def test_a_counter_adds_tokens(ops):
    report = wr.change(ops, "Mistakes", by=1)
    assert report["did"]["from 1"][0]["line"] == "The Job (the world): +1 trouble (now 2 clean, 2 trouble)"


@pytest.mark.parametrize("change, why", [
    ({"tokens": {}}, "'tokens' are kinds and how many"),
    ({"tokens": {"clean": -1}}, "'tokens' are kinds and how many"),
    ({"draw": "shake"}, "'draw' is \"keep out\" or \"put back\""),
    ({"draw_every": "yearly"}, "'draw_every':"),
    ({"results": {"clean": {"text": "x"}}}, "one result for each kind of token: clean, trouble"),
    ({"results": {"clean": {"text": "x"}, "trouble": {}}}, "the result of 'trouble' needs a 'text'"),
])
def test_a_wrong_bag_is_refused(dcc_world, change, why):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    with pytest.raises(wr.RulesError, match=why):
        wr.define(ops, [{**JOB, **change}])


def test_a_tokens_effect_names_a_bag_and_its_kinds(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    for effect, why in (({"tokens": "The Job", "add": {"luck": 1}}, "The Job has no tokens luck"),
                        ({"tokens": "Sea level", "add": {"x": 1}}, "no bag 'Sea level'"),
                        ({"tokens": "The Job", "add": {"trouble": 0}}, "N 1 or more")):
        wrong = {**MISTAKES, "results": [{"from": 1, "text": "x", "effects": [effect]}]}
        with pytest.raises(wr.RulesError, match=why):
            wr.define(ops, [JOB, SEA, wrong])


def test_bags_in_the_brief_the_cards_the_summary_and_the_hud(dcc_world, ops):
    text = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "The Melt")))
    assert text.startswith("The Melt (bag: 6 calm year, 3 warm year, 1 collapse, drawn put back, "
                           "held by the world; " + wr.HIDDEN)
    assert "  Drawn by itself every 360d of game time." in text
    assert 'Command: gm-rule.sh draw "The Melt" [N]; put|take "The Melt" <kind> N' in text
    rule_bag.put(ops, "The Job", "Bone Garden", "trouble", 1)
    from lib.cards import Cards
    assert "Rule here: The Job: 2 clean, 2 trouble (bag)" in Cards(ops).location_card("Bone Garden")
    assert wr.check_values(ops, "location:Bone Garden", {"The Job": {"clean": 5}}) == [
        ("The Job", {"tokens": {"clean": 5}})]
    player_bag = {**JOB, "name": "Nerve", "held_by": "player"}
    wr.define(ops, [player_bag])
    assert "Nerve: 2 clean, 1 trouble" in wr.summary(ops)
    root = Path(dcc_world).parent / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "gm-statusline.sh", root / "tools")
    shutil.copytree(dcc_world, root / "world-state")
    hud = subprocess.run(["bash", str(root / "tools" / "gm-statusline.sh")], input="{}",
                         capture_output=True, text=True).stdout
    assert "Nerve: 2 clean 1 trouble" in re.sub(r"\x1b\[[0-9;]*m", "", hud)


def test_the_command(dcc_world, ops):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), *words],
                              capture_output=True, text=True, env=env)
    drew = run("draw", "The Job", "world", "2")
    assert drew.returncode == 0 and drew.stdout.startswith("The Job (the world): drew ")
    assert run("put", "The Job", "world", "trouble", "3").stdout.startswith(
        "The Job (the world): +3 trouble")
    took = run("take", "The Job", "world", "trouble", "9")
    assert took.returncode == 1 and "to take out" in took.stderr
    assert run("refill", "The Job", "world").returncode == 0
    assert wr.load_state(ops)["world"]["The Job"]["tokens"] == {"clean": 2, "trouble": 1}
