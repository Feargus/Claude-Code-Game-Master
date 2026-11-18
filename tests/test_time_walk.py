"""When things next change by themselves (lib/time_walk.py, 2026-11-18, step 1 of
"Time stops at the first event"): each source says when it next changes, and that
is the moment the time step first changes it."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib import rule_time, time_walk
from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager
from lib.json_ops import JsonOperations
from lib.threat_clocks import ThreatClockManager
from lib.time_manager import next_time_of_day

START = datetime(2187, 10, 26, 4, 30)


def _counter(name, held_by="player", **more):
    return {"name": name, "block": "counter", "held_by": held_by, "range": [0, 10],
            "summary": f"{name}.", "when": "When it happens.", "results": [], **more}


SEA = _counter("Sea level", "world", start=2, rate={"by": 1, "every": "90d"})
CALM = _counter("Calm", start=5, rate={"by": 1, "every": "1d", "toward": 5})   # at its point
SKY = {"name": "Sky", "block": "bag", "held_by": "world", "summary": "The sky.",
       "when": "Drawn every 4 hours.", "tokens": {"clear": 3, "acid": 1}, "draw": "put back",
       "draw_every": "4h", "results": {"clear": {"text": "Clear."}, "acid": {"text": "Acid."}}}
HABIT = {"name": "Habit", "block": "states", "held_by": "player", "summary": "A habit.",
         "when": "When used.", "start": "clean",
         "states": {"clean": {"text": "Clean.", "moves": {"user": "a first dose"}},
                    "user": {"text": "Using.", "moves": {"clean": "quits"}, "after": {"2d": "clean"}}}}
WEEK = {"name": "Week", "block": "budget", "held_by": "player", "summary": "A week.",
        "when": "Each week.", "amount": 7, "unit": "days", "period": {"every": "7d"},
        "parts": {"work": {"text": "Work."}, "rest": {"text": "Rest."}}}


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = START.strftime("%Y-%m-%dT%H:%M")
    ops.save_json("campaign-overview.json", overview)
    ops.save_json("threat-clocks.json", {})                       # only this test's clocks
    ops.save_json("consequences.json", {"active": [], "resolved": []})
    return ops


def test_each_block_says_when_time_next_moves_it(ops):
    wr.define(ops, [SEA, CALM, SKY, HABIT, WEEK])
    rules = {r["name"]: r for r in wr.rules(ops)}

    def nxt(name, after=START):
        return wr.block(rules[name]).next_time(ops, rules[name], after)
    assert nxt("Sea level") == START + timedelta(days=90)
    assert nxt("Calm") is None                                     # held at its point
    assert nxt("Sky") == START + timedelta(hours=4)
    assert nxt("Habit") is None                                    # "clean" has no after
    from lib import rule_states
    rule_states.move(ops, "Habit", "player", "user", cause="test", when="2187-10-26T04:30")
    assert nxt("Habit") == START + timedelta(days=2)
    assert nxt("Week") is None                                     # not spent: nothing to refill
    assert rule_time.next_moment(ops, START) == (START + timedelta(hours=4), ["Sky"])


def test_the_moment_is_when_the_time_step_first_changes_it(ops):
    """Just before the moment the step changes nothing; at it, it does; and the next
    moment is a period later."""
    wr.define(ops, [SKY])
    first, _ = rule_time.next_moment(ops, START)
    assert rule_time.apply(ops, START, first - timedelta(minutes=1)) == []
    assert len(rule_time.apply(ops, first - timedelta(minutes=1), first)) == 1
    assert rule_time.next_moment(ops, first)[0] == first + timedelta(hours=4)


def test_walking_from_moment_to_moment_ends_where_one_jump_does(dcc_world, ops):
    wr.define(ops, [_counter("Rust", start=0, rate={"by": 1, "every": "5h"})])
    end, moment, steps = START + timedelta(days=2), START, 0
    while True:
        nxt = rule_time.next_moment(ops, moment)
        if nxt is None or nxt[0] > end:
            break
        rule_time.apply(ops, moment, nxt[0])
        moment, steps = nxt[0], steps + 1
    rule_time.apply(ops, moment, end)
    walked = wr.entry(ops, wr.find_rule(ops, "Rust"), "player")["value"]
    assert steps == 9 and walked == 9                              # 48 h / 5 h
    wr.define(ops, [_counter("Rust", start=0, rate={"by": 1, "every": "5h"})])
    state = wr.load_state(ops)
    state.pop("player", None)
    wr.save_state(ops, state)
    rule_time.apply(ops, START, end)
    assert wr.entry(ops, wr.find_rule(ops, "Rust"), "player")["value"] == walked


def test_a_time_clock_says_when_it_reaches_its_next_segment(dcc_world, ops):
    clocks = ThreatClockManager(dcc_world)
    clocks.add_clock("Tracker", 4, due_at=START + timedelta(days=4))
    moment, names = clocks.next_moment(START)
    assert (moment, names) == (START + timedelta(days=1), ["Tracker"])
    clocks.update_time_clocks(moment - timedelta(minutes=1))
    assert clocks._load()["Tracker"]["current"] == 0
    clocks.update_time_clocks(moment)
    assert clocks._load()["Tracker"]["current"] == 1
    assert clocks.next_moment(moment)[0] == START + timedelta(days=2)
    clocks.update_time_clocks(START + timedelta(days=4))
    assert clocks.next_moment(START + timedelta(days=4)) is None   # full


def test_the_time_of_day_counts_only_when_a_consequence_waits_on_it(dcc_world, ops):
    assert next_time_of_day(START, []) is None
    assert next_time_of_day(START, ["Morning"]) == (datetime(2187, 10, 26, 7, 0), "Morning")
    assert next_time_of_day(START, ["dusk", "dawn"]) == (datetime(2187, 10, 26, 5, 0), "Dawn")
    assert next_time_of_day(START, ["midnight"]) == (datetime(2187, 10, 26, 23, 0), "Midnight")
    # it holds now: the consequence is due at once
    assert next_time_of_day(START, ["small hours"]) == (START + timedelta(minutes=1), "Small hours")
    assert time_walk.next_moment(dcc_world, ops, START) is None    # nothing waits on time
    ConsequenceManager(dcc_world).add_consequence(
        "The market opens", "morning", trigger_type="on_time", match="morning")
    assert time_walk.next_moment(dcc_world, ops, START) == (datetime(2187, 10, 26, 7, 0), ["morning"])


def test_the_first_of_everything(dcc_world, ops):
    wr.define(ops, [SKY])
    ThreatClockManager(dcc_world).add_clock("Tracker", 1, due_at=START + timedelta(hours=4))
    moment, due = time_walk.next_moment(dcc_world, ops, START)
    assert moment == START + timedelta(hours=4) and due == ["clock Tracker", "rule Sky"]


# ---------- step 2: the walk ----------

def _set_time(ops, moment):
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = moment.strftime("%Y-%m-%dT%H:%M")
    ops.save_json("campaign-overview.json", overview)


def test_a_long_step_fires_a_time_of_day_on_the_way_and_a_clock_at_its_time(dcc_world, ops):
    """todo.md: `advance 10h` from 03:53 never fired an on_time morning consequence,
    and a clock due at 04:05 was only reported at 13:53."""
    from lib.time_manager import TimeManager
    _set_time(ops, datetime(2187, 10, 26, 3, 53))
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The market opens", "morning", trigger_type="on_time", match="morning")
    ThreatClockManager(dcc_world).add_clock("Tracker", 1, due_at=datetime(2187, 10, 26, 4, 5),
                                            consequence="The tracker arrives")
    manager = TimeManager(dcc_world)
    manager.advance(10 * 60)
    at = {m["at"]: m for m in manager.moments}
    assert at[datetime(2187, 10, 26, 4, 5)]["clocks"]["Tracker"]["current"] == 1
    assert [c["id"] for c in at[datetime(2187, 10, 26, 7, 0)]["fired"]] == [cid]
    assert manager.get_game_time() == datetime(2187, 10, 26, 13, 53)


def test_the_output_gives_each_moment_its_time(dcc_world, ops):
    import subprocess
    _set_time(ops, datetime(2187, 10, 26, 3, 53))
    ConsequenceManager(dcc_world).add_consequence("The market opens", "morning",
                                                  trigger_type="on_time", match="morning")
    env = dict(__import__("os").environ, GM_WORLD_STATE_BASE=str(dcc_world))
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(["bash", str(root / "tools/gm-time.sh"), "advance", "10h"],
                         capture_output=True, text=True, env=env, cwd=root).stdout
    assert out.startswith("Time: 13:53 (Afternoon), Friday, 26 October 2187 (from 03:53")
    assert "\nAt 07:00 (Morning), Friday, 26 October 2187:\n[REACTIVITY] fired these 1" in out
