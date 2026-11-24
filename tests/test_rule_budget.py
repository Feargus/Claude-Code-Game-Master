"""The budget (lib/rule_budget.py): a fixed amount split among
named parts, all of it at once; each part's effects run once per `per` units; spent
until refilled, by hand or each period."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib import rule_budget
from lib import world_rules as wr
from lib.json_ops import JsonOperations
from lib.time_manager import TimeManager

ROOT = Path(__file__).resolve().parent.parent

DOWNTIME = {"name": "Downtime", "block": "budget", "held_by": "player", "amount": 7,
            "unit": "days", "summary": "A week between jobs.", "when": "Between jobs.",
            "parts": {"healing": {"text": "One wound heals a step.",
                                  "gm": "gm-body.sh heal for each day."},
                      "work": {"text": "40 credits a day.", "effects": [{"credits": 40}]},
                      "training": {"text": "A practice of a skill.", "per": 2}}}
SOLDIERS = {"name": "Soldiers", "block": "budget", "held_by": "faction", "amount": 10,
            "unit": "soldiers", "period": {"every": "7d"}, "summary": "A gang's fighters.",
            "when": "Each week, by the gang's goals.",
            "parts": {"turf": {"text": "Holds the blocks."}, "raids": {"text": "A raid.", "per": 2}}}


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    wr.define(ops, [DOWNTIME, SOLDIERS])
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops


def test_a_split_uses_it_all_and_each_part_acts(ops):
    start = ops.load_json("character.json")["possessions"]["credits"]
    report = rule_budget.split(ops, "Downtime", None, ["healing=3", "Work=2", "training=2"])
    assert report["split"] == {"healing": 3, "work": 2, "training": 2}
    work = next(p for p in report["parts"] if p["part"] == "work")
    assert work["times"] == 2 and [d["line"] for d in work["did"]] == [
        f"+40 credits (now {start + 40})", f"+40 credits (now {start + 80})"]
    assert next(p for p in report["parts"] if p["part"] == "training")["times"] == 1
    text = "\n".join(rule_budget.split_lines(ops, report))
    assert text.startswith("Downtime (Tandy): 7 days split: healing 3, work 2, training 2\n"
                           "  healing (3 days): One wound heals a step.\n"
                           "    Do now: gm-body.sh heal for each day.")
    assert "  training (2 days, 1 times): A practice of a skill." in text
    assert text.endswith(f"Changed on the character: +40 credits (now {start + 40}); "
                         f"+40 credits (now {start + 80}).")
    with pytest.raises(ValueError, match="is spent for now: gm-rule.sh refill"):
        rule_budget.split(ops, "Downtime", None, ["work=7"])
    rule_budget.refill(ops, "Downtime")
    assert rule_budget.split(ops, "Downtime", None, ["work=7"])["split"]["healing"] == 0


@pytest.mark.parametrize("words, why", [
    (["work=3"], "splits 7 days; these add up to 3. Use all of it"),
    (["work=3", "sleep=4"], "'sleep=4' is no <part>=N"),
    (["work"], "'work' is no <part>=N"),
])
def test_a_wrong_split_is_refused(ops, words, why):
    with pytest.raises(ValueError, match=why):
        rule_budget.split(ops, "Downtime", None, words)


def test_a_budget_with_a_period_refills_by_itself(dcc_world, ops):
    rule_budget.split(ops, "Soldiers", "faction:crawlers", ["turf=6", "raids=4"])
    manager = TimeManager(dcc_world)
    manager.advance(6 * 24 * 60, through_all=True)
    assert manager.rule_changes == []
    manager.advance(2 * 24 * 60, through_all=True)
    assert [(r["rule"], r["holder"]) for r in manager.rule_changes] == [("Soldiers", "faction:crawlers")]
    assert not wr.load_state(ops)["faction:crawlers"]["Soldiers"]["spent"]


@pytest.mark.parametrize("change, why", [
    ({"amount": 0}, "'amount' is how much there is to split"),
    ({"period": "weekly"}, "'period' is \"by hand\" or"),
    ({"period": {"every": "soon"}}, "'period':"),
    ({"parts": {}}, "'parts' is"),
    ({"parts": {"work": {"text": "x", "per": 0}}}, "'per' is how many units buy it once"),
    ({"parts": {"work": {"text": "x", "when_off": []}}}, "a part has no when_off"),
    ({"parts": {"work": {}}}, "part 'work' needs a 'text'"),
])
def test_a_wrong_budget_is_refused(dcc_world, change, why):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    with pytest.raises(wr.RulesError, match=why):
        wr.define(ops, [{**DOWNTIME, **change}])


def test_budgets_in_the_brief_the_cards_the_summary_and_the_hud(dcc_world, ops):
    text = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Downtime")))
    assert text.startswith("Downtime (budget: 7 days, refilled by hand, held by the player)")
    assert "  training (each 2 days): A practice of a skill." in text
    assert "  work (each of the days): 40 credits a day." in text
    assert 'Command: gm-rule.sh split "Downtime" healing=N work=N training=N (all 7)' in text
    assert "Now, Tandy: 7 days to split" in text
    assert "Downtime: 7 days to split" in wr.summary(ops)
    rule_budget.split(ops, "Soldiers", "The Crawlers", ["turf=10"])
    soldiers = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Soldiers"), ["faction:crawlers"]))
    assert "Now, The Crawlers: spent (turf 10)" in soldiers
    with pytest.raises(ValueError, match="no starting value"):
        wr.check_values(ops, "player", {"Downtime": 3})
    root = Path(dcc_world).parent / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "gm-statusline.sh", root / "tools")
    shutil.copytree(dcc_world, root / "world-state")
    hud = subprocess.run(["bash", str(root / "tools" / "gm-statusline.sh")], input="{}",
                         capture_output=True, text=True).stdout
    assert "Downtime: 7 days" in re.sub(r"\x1b\[[0-9;]*m", "", hud)


def test_the_command(dcc_world, ops):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), *words],
                              capture_output=True, text=True, env=env)
    done = run("split", "Downtime", "work=4", "healing=3")
    assert done.returncode == 0 and done.stdout.startswith("Downtime (Tandy): 7 days split")
    again = run("split", "Downtime", "work=7")
    assert again.returncode == 1 and "is spent for now" in again.stderr
    assert run("refill", "Downtime").stdout.strip() == "Downtime (Tandy): refilled, 7 days to split"
    assert run("split", "Soldiers", "The Crawlers", "turf=8", "raids=2").returncode == 0
    assert wr.load_state(ops)["faction:crawlers"]["Soldiers"]["split"] == {"turf": 8, "raids": 2}
