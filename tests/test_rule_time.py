"""A counter's options (2026-11-17, step 5): a rate that moves it as game time passes
(lib/rule_time.py), hysteresis (a result's off_at), overflow with lasting marks, and
streaks."""

import os
import subprocess
from pathlib import Path

import pytest

from lib import world_rules as wr
from lib.json_ops import JsonOperations
from lib.time_manager import TimeManager

ROOT = Path(__file__).resolve().parent.parent


def _counter(name, held_by="player", **more):
    rule = {"name": name, "block": "counter", "held_by": held_by, "range": [0, 10],
            "summary": f"{name}.", "when": "When it happens.", "results": []}
    rule.update(more)
    return rule


SEA = _counter("Sea level", "world", start=2, rate={"by": 1, "every": "90d"},
               results=[{"from": 3, "text": "The docks flood."}])
PATIENCE = _counter("Patience", "faction", start=5, range=[0, 5],
                    rate={"by": 1, "every": "7d", "toward": 5})
HEAT = _counter("Heat", "location", rate={"share": 0.5, "every": "1d", "toward": 0})
STORMS = _counter("Storms", "world", results=[
    {"from": 3, "text": "A stormy year.", "effects": [{"rate_of": "Sea level", "by": 1}]}])
PANIC = _counter("Panic", range=[0, 8], results=[
    {"from": 6, "off_at": 2, "text": "Panicking.", "effects": [{"condition": "Panicked"}],
     "when_off": [{"condition": "Panicked", "add": False}]}])
STRESS = _counter("Stress", range=[0, 8], overflow={
    "at": 8, "back_to": 0, "marks": ["a stammer", "night terrors"], "limit": 2,
    "at_limit": "The character is done with this life: they retire."})
MOMENTUM = _counter("Momentum", range=[0, 5], streak=True,
                    results=[{"from": 3, "text": "On a roll."}])


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    wr.define(ops, [SEA, PATIENCE, HEAT, STORMS, PANIC, STRESS, MOMENTUM])
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops


def _value(ops, rule, holder):
    return wr.entry(ops, wr.find_rule(ops, rule), holder)["value"]


def _days(dcc_world, n):
    manager = TimeManager(dcc_world)
    manager.advance(n * 24 * 60)
    return manager.rule_changes


# ---------- rates ----------

def test_a_rate_moves_a_value_by_whole_periods(dcc_world, ops):
    assert _days(dcc_world, 89) == [] and _value(ops, "Sea level", "world") == 2
    assert wr.load_state(ops)["world"]["Sea level"]["rate_from"] == "2187-10-26T04:30"
    wr.change(ops, "Sea level", by=1)                       # a storm: doesn't reset the rate
    changes = _days(dcc_world, 2)                           # 91 days since the rate began
    assert [(c["rule"], c["before"], c["after"]) for c in changes] == [("Sea level", 3, 4)]
    assert _value(ops, "Sea level", "world") == 4
    assert "by its rate (+1 every 90d), 1 period" in (Path(ops.world_state_dir) / "rules.log").read_text()
    _days(dcc_world, 180)
    assert _value(ops, "Sea level", "world") == 6


def test_toward_stops_there_and_only_holders_with_a_value_move(dcc_world, ops):
    wr.change(ops, "Patience", "faction:crawlers", to=1)
    _days(dcc_world, 30)                                    # 4 periods: 1 → 5, and no further
    assert _value(ops, "Patience", "faction:crawlers") == 5
    assert "faction:system" not in wr.load_state(ops)


def test_toward_pulls_or_pushes_from_either_side(dcc_world, ops):
    """With `toward`, + pulls and - pushes, whichever side the value is on (the
    hard-country trial's Exposure, "by 1 toward 0", climbed away from 0; decided
    2026-11-18)."""
    from lib import rule_time

    def step(value, by, toward, periods, low=0, high=20):
        return rule_time.step(value, {"by": by, "every": "1d", "toward": toward}, periods, low, high)
    # a mood, -5 to 5, its point at 0
    assert step(3, 1, 0, 2, -5, 5) == 1 and step(-3, 1, 0, 5, -5, 5) == 0
    assert step(3, -1, 0, 9, -5, 5) == 5 and step(-3, -1, 0, 9, -5, 5) == -5
    assert step(0, -1, 0, 9, -5, 5) == 0                     # on the knife-edge: it stays
    # a crowd's temper, 0 to 20, its point at 10
    assert step(13, 1, 10, 9) == 10 and step(7, 2, 10, 1) == 9
    assert step(13, -1, 10, 3) == 16 and step(7, -1, 10, 9) == 0
    assert step(13, 0, 10, 9) == 13                          # held
    # Exposure, 0 to 6, its point at the edge: a pull heals, a push is a drift up
    assert step(3, 1, 0, 2, 0, 6) == 1 and step(3, -1, 0, 9, 0, 6) == 6
    assert rule_time.describe({"by": 1, "every": "7d", "toward": 0}) == "1 every 7d toward 0"
    assert rule_time.describe({"by": -1, "every": "7d", "toward": 0}) == "1 every 7d away from 0"
    assert rule_time.describe({"by": 1, "every": "90d"}) == "+1 every 90d"


def test_a_rate_of_effect_can_tip_a_pull_into_a_push(dcc_world, ops):
    wr.change(ops, "Patience", "faction:crawlers", to=3)
    from lib import rule_time
    rule_time.set_rate(ops, "Patience", "faction:crawlers", by=-1)
    _days(dcc_world, 14)                                     # 2 periods: pushed from 5, down
    assert _value(ops, "Patience", "faction:crawlers") == 1


def test_a_share_moves_part_of_the_way(dcc_world, ops):
    wr.change(ops, "Heat", "Bone Garden", to=8)
    _days(dcc_world, 2)
    assert _value(ops, "Heat", "location:Bone Garden") == 2  # 8 → 4 → 2
    _days(dcc_world, 3)
    assert _value(ops, "Heat", "location:Bone Garden") == 0  # 2 → 1 → 0, and stays


def test_a_rate_can_be_changed_for_one_holder(dcc_world, ops):
    report = wr.change(ops, "Storms", by=3)
    assert report["did"]["from 3"][0]["line"] == ("Sea level (the world): rate +1 every 90d → "
                                                  "+2 every 90d")
    assert wr.load_state(ops)["world"]["Sea level"]["rate"]["by"] == 2
    assert "its own rate: +2 every 90d" in "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Sea level")))
    _days(dcc_world, 90)
    assert _value(ops, "Sea level", "world") == 4
    from lib import rule_time
    assert rule_time.set_rate(ops, "Sea level", by=1)[1] == SEA["rate"]
    assert "rate" not in wr.load_state(ops)["world"]["Sea level"]       # the rule's again
    with pytest.raises(ValueError, match="no rate in steps"):
        rule_time.set_rate(ops, "Heat", "Bone Garden", by=1)


# ---------- hysteresis, overflow, streaks ----------

def test_hysteresis_keeps_a_result_on_until_off_at(ops):
    assert wr.change(ops, "Panic", to=4)["on"] == []          # never reached 6: not on
    on = wr.change(ops, "Panic", to=6)
    assert on["on"] == ["from 6"] and on["character"] == ["condition Panicked added"]
    assert wr.change(ops, "Panic", to=3)["still"] == ["from 6"]
    off = wr.change(ops, "Panic", to=2)
    assert off["off"] == ["from 6"] and off["character"] == ["condition Panicked removed"]
    assert "from 6 (off only at 2): Panicking." in "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Panic")))


def test_overflow_leaves_a_lasting_mark(ops):
    report = wr.change(ops, "Stress", by=9)
    assert (report["before"], report["after"], report["overflow"]["at"]) == (0, 0, 8)
    text = "\n".join(wr.change_lines(ops, report))
    assert text.startswith("Stress (Tandy): 0 → 8 → 0\n  overflow at 8, back to 0: a lasting "
                           "mark is due. Suggested: a stammer; night terrors; or write one.")
    assert 'gm-rule.sh mark "Stress" "<the mark>"' in text
    first = wr.mark(ops, "Stress", None, "night terrors")
    assert first["marks"] == ["night terrors"] and first["at_limit"] == ""
    with pytest.raises(wr.RulesError, match="No mark is due"):
        wr.mark(ops, "Stress", None, "a fear of lifts")
    wr.change(ops, "Stress", to=8)
    second = wr.mark(ops, "Stress", None, "a fear of lifts")
    assert second["at_limit"] == "The character is done with this life: they retire."
    line = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Stress")))
    assert "Overflow at 8: back to 0, and a lasting mark (e.g. a stammer; night terrors). " \
           "At 2 marks: The character is done" in line
    assert "Now, Tandy: 0 (no result); marks: night terrors; a fear of lifts" in line


def test_a_streak_breaks(ops):
    wr.change(ops, "Momentum", by=3)
    broken = wr.break_streak(ops, "Momentum")
    assert (broken["before"], broken["after"], broken["off"]) == (3, 0, ["from 3"])
    with pytest.raises(wr.RulesError, match="Panic is no streak"):
        wr.break_streak(ops, "Panic")


@pytest.mark.parametrize("change, why", [
    ({"rate": {"by": 1, "every": "soon"}}, "'rate' needs 'every'"),
    ({"rate": {"share": 0.5, "every": "1d"}}, "a share needs 'toward'"),
    ({"rate": {"by": 1, "share": 0.5, "every": "1d"}}, "either 'by' .steps. or 'share'"),
    ({"rate": {"by": 1, "every": "1d", "toward": 99}}, "'toward' is a whole number from 0 to 10"),
    ({"overflow": {"at": 8, "back_to": 8}}, "'back_to' is a whole number from 0 to 7"),
    ({"overflow": {"at": 8, "limit": 3}}, "'limit' is a number of marks .* with 'at_limit'"),
    ({"streak": "yes"}, "'streak' is true or false"),
    ({"results": [{"from": 6, "to": 7, "off_at": 2, "text": "x"}]}, "and not with 'to'"),
])
def test_wrong_options_are_refused(dcc_world, change, why):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    with pytest.raises(wr.RulesError, match=why):
        wr.define(ops, [_counter("Strain", **change)])


def test_time_prints_what_the_rates_did(dcc_world, ops):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)
    out = subprocess.run(["bash", str(ROOT / "tools" / "gm-time.sh"), "advance", "91d"],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert "Sea level (the world): 2 → 3\n  now on:   from 3: The docks flood." in out.stdout
    rate = subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), "rate", "Sea level",
                           "--by", "3"], capture_output=True, text=True, env=env)
    assert rate.stdout.strip() == ("[SUCCESS] Sea level (the world): rate +1 every 90d → "
                                   "+3 every 90d")
