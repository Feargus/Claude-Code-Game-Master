"""Relations that move by themselves, faction jobs and asks:
lib/faction_rules.py (the bag, the decimal Relation and its drift), lib/faction_turns.py
(what a turn does to Relations) and lib/faction_jobs.py (jobs and asks)."""

import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib import faction_jobs as fj
from lib import faction_rules as fr
from lib import faction_turns as ft
from lib import world_rules as wr
from lib.factions import FactionManager
from lib.json_ops import JsonOperations

CAMPAIGN = "dungeon-crawler-carl"
STANDING = {"name": "Standing", "block": "counter", "held_by": "faction", "known": False,
            "range": [-5, 5], "start": 0, "summary": "How a faction regards the character.",
            "when": "The character helps or crosses a faction.", "results": []}


class Dice:
    def __init__(self, *rolls):
        self.rolls = list(rolls)

    def randint(self, low, high):
        return self.rolls.pop(0)

    def choice(self, seq):
        return seq[0]


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    m = FactionManager(ops)
    m.create("Meridian Group", "A security firm.", aliases=["Meridian"])
    here = overview["player_position"]["current_location"]
    m.set_presence(here, ["Meridian=2", "system=3", "crawlers=4", "showrunners=5"])
    return ops


def _here(ops):
    return ops.load_json("campaign-overview.json")["player_position"]["current_location"]


def _exact(ops, a, b):
    return fr.relation_exact(ops, fr.pair_id(a, b))


# ---------- relations ----------

def test_a_strike_moves_the_relations_of_everyone_there(ops):
    fr.add_relation(ops, "crawlers", "system", -5, "a test")       # the crawlers hate the system
    fr.add_relation(ops, "showrunners", "system", 5, "a test")     # the showrunners love it
    # Meridian strikes the system: 6+3 against 1+3, margin +5: presence 3 → 0, a loss of 3
    lines = "\n".join(ft.run(ops, [{"faction": "Meridian", "action": "strike", "power": "Military",
                                    "rival": "system", "at": _here(ops)}], Dice(6, 1), only="Meridian"))
    assert _exact(ops, "meridian-group", "system") == -1             # the victim
    # ΔR = L · P/5 · (1/2 − R(C, B)/5): the crawlers (4, hating it) 3·0.8·1.5 = 3.6,
    # the showrunners (5, its friends) 3·1·(−0.5) = −1.5
    assert _exact(ops, "meridian-group", "crawlers") == pytest.approx(3.6)
    assert _exact(ops, "meridian-group", "showrunners") == pytest.approx(-1.5)
    assert wr.entry(ops, wr.find_rule(ops, fr.RELATION),
                    fr.pair_id("meridian-group", "crawlers"))["value"] == 4   # rounded
    assert "Relations (−5 war … +5 allies" in lines and "+0.00 → +3.60" in lines


def test_a_neutral_neighbour_is_a_little_pleased_and_a_deal_gains(ops):
    ft.run(ops, [{"faction": "Meridian", "action": "push", "power": "Economic", "rival": "system",
                  "at": _here(ops)}], Dice(6, 1), only="Meridian")      # margin +5: −2 presence
    assert _exact(ops, "meridian-group", "crawlers") == pytest.approx(2 * 0.8 * 0.5)
    ft.run(ops, [{"faction": "Meridian", "action": "deal", "power": "Political", "rival": "crawlers"}],
           Dice(6, 1), only="Meridian")
    assert _exact(ops, "meridian-group", "crawlers") == pytest.approx(1.8)


def test_a_change_by_hand_wins_over_the_decimal_value(ops):
    fr.add_relation(ops, "crawlers", "system", 1.4, "a test")
    wr.change(ops, fr.RELATION, fr.pair_id("crawlers", "system"), by=2)
    assert _exact(ops, "crawlers", "system") == 3.0


def test_relations_relax_toward_their_resting_point(ops):
    fr.add_relation(ops, "crawlers", "system", 4, "a test")
    t0 = datetime(2187, 10, 26, 4, 30)
    fr.drift(ops, t0, t0 + timedelta(days=30))
    assert _exact(ops, "crawlers", "system") == pytest.approx(4 * math.exp(-1))
    for _ in range(30 * 24):                                        # an hour at a time: the same
        fr.drift(ops, t0, t0 + timedelta(hours=1))
    assert _exact(ops, "crawlers", "system") == pytest.approx(4 * math.exp(-2))
    import lib.rule_time as rule_time
    rule_time.set_rate(ops, fr.RELATION, fr.pair_id("crawlers", "system"), toward=-2)
    fr.drift(ops, t0, t0 + timedelta(days=3000))
    assert _exact(ops, "crawlers", "system") == pytest.approx(-2)


def test_time_passing_moves_them(ops, dcc_world):
    from lib.time_manager import TimeManager
    fr.add_relation(ops, "crawlers", "system", 4, "a test")
    TimeManager(dcc_world).advance(30 * 24 * 60, through_all=True)
    assert _exact(ops, "crawlers", "system") == pytest.approx(4 * math.exp(-1), abs=1e-6)


# ---------- jobs ----------

def _job(ops, dcc_world, **more):
    from lib.plot_manager import PlotManager
    from lib.threat_clocks import ThreatClockManager
    wr.define(ops, [STANDING])
    PlotManager(dcc_world).add("Hostile Takeover", "own every guard post", owner="Meridian")
    ThreatClockManager(dcc_world).add_clock("Takeover", 3, advance_on="event",
                                            plots=["Hostile Takeover"], text="the buy-out")
    return fj.offer(ops, "Meridian", {"action": "take", "power": "Covert", "who": "Mordecai",
                                      "due": "2d", "how": "an anonymous call", **more})


def _standing(ops):
    return wr.entry(ops, wr.find_rule(ops, "Standing"), "faction:meridian-group")["value"]


def test_a_job_done_moves_the_plan_and_standing(ops, dcc_world):
    lines = "\n".join(_job(ops, dcc_world))
    assert "Meridian Group offers the character a job: Take someone: Mordecai" in lines
    assert "an anonymous call" in lines and "2187-10-28 04:30" in lines
    assert ops.load_json("threat-clocks.json")["meridian-group job"]["due_at"] == "2187-10-28T04:30"
    assert "Job out for the character" in FactionManager(ops).show("Meridian")
    lines = "\n".join(fj.outcome(ops, "Meridian", "done"))
    assert "plan clock Takeover (Hostile Takeover): 1/3" in lines
    assert _standing(ops) == 1
    assert "meridian-group job" not in (ops.load_json("threat-clocks.json") or {})
    with pytest.raises(fj.JobError, match="has no job out"):
        fj.outcome(ops, "Meridian", "done")


def test_a_failed_job_costs_standing_and_the_faction_does_it_itself(ops, dcc_world):
    _job(ops, dcc_world)
    lines = "\n".join(fj.outcome(ops, "Meridian", "failed", rng=Dice(6, 1)))
    assert _standing(ops) == -1
    assert "FACTION TURN" in lines and "Take someone (Covert)" in lines
    assert "plan clock Takeover (Hostile Takeover): 1/3" in lines        # it did it, and for its plan


def test_a_refused_job_is_done_by_the_faction_without_a_cost(ops, dcc_world):
    _job(ops, dcc_world, plot="none")
    lines = "\n".join(fj.outcome(ops, "Meridian", "refused", rng=Dice(6, 1)))
    assert _standing(ops) == 0 and "FACTION TURN" in lines and "plan clock" not in lines


def test_the_deadline_passing_says_the_job_failed(ops, dcc_world):
    from lib.time_manager import TimeManager
    _job(ops, dcc_world)
    manager = TimeManager(dcc_world)
    manager.advance(3 * 24 * 60, through_all=True)
    fired = [c["consequence"] for m in manager.moments
             for c in m["fired"] + [f for clock in m["clocks"].values() for f in clock.get("fired", [])]]
    assert any("gm-faction.sh job failed meridian-group" in c for c in fired)


def test_a_job_is_a_complex_action_with_a_deadline(ops, dcc_world):
    wr.define(ops, [STANDING])
    with pytest.raises(fj.JobError, match="deadline"):
        fj.offer(ops, "Meridian", {"action": "take", "power": "Covert", "who": "Mordecai"})
    with pytest.raises(fj.JobError, match="complex action"):
        fj.offer(ops, "Meridian", {"action": "build", "power": "Covert", "due": "1d"})


def test_the_bag_owes_jobs_and_asks(ops):
    import lib.rule_bag as rule_bag
    rule_bag.draw(ops, fr.BAG, "world", count=60, rng=random.Random(3))
    lines = "\n".join(fr.owed_lines(ops))
    assert "has a job for the character" in lines and "gm-faction.sh job offer" in lines
    assert "(an ask), drawn" in lines and "gm-faction.sh ask" in lines


# ---------- asks ----------

def test_an_ask_draws_one_of_the_people_with_an_attitude(ops, dcc_world):
    import lib.rule_bag as rule_bag
    from lib.note_manager import NoteManager
    with pytest.raises(fj.JobError, match="Nobody has an attitude"):
        fj.ask(ops)
    notes = NoteManager(dcc_world)
    notes.set_attitude("Mordecai", "fond, exasperated")
    assert fj.askers(ops) == ["Mordecai"]
    rule_bag.put(ops, fr.BAG, "world", "people", 0)
    state = wr.load_state(ops)
    state["world"][fr.BAG]["owed"] = [{"kind": "people", "at": "2187-10-26T04:30"}]
    wr.save_state(ops, state)
    lines = "\n".join(fj.ask(ops, rng=Dice()))
    assert lines.startswith("ASK: Mordecai (fond, exasperated toward the character)")
    assert "--kind side" in lines
    assert fr.owed(ops) == []
