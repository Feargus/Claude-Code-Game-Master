"""A faction turn (lib/faction_turns.py): the GM gives one action per faction, the
script checks them all, rolls them against the state at the start of the turn, and
applies every change together."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import faction_rules as fr
from lib import faction_turns as ft
from lib import world_rules as wr
from lib.factions import FactionManager, load, presence
from lib.json_ops import JsonOperations

CAMPAIGN = "dungeon-crawler-carl"
ROOT = Path(__file__).resolve().parent.parent


class Dice:
    """Dice that roll what they are told, in order."""
    def __init__(self, *rolls):
        self.rolls = list(rolls)

    def randint(self, low, high):
        return self.rolls.pop(0)


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    m = FactionManager(ops)
    m.create("Meridian Group", "A security firm.", aliases=["Meridian"])
    here = ops.load_json("campaign-overview.json")["player_position"]["current_location"]
    m.set_presence(here, ["Meridian=2", "system=3"])
    return ops


def _here(ops):
    return ops.load_json("campaign-overview.json")["player_position"]["current_location"]


def _power(ops, fid, name):
    return fr.power(ops, fid)[name]


@pytest.mark.parametrize("margin, push, strike, seize", [
    (-3, 0, None, None), (-2, 1, None, None), (-1, 1, None, None), (0, 1, 1, 1),
    (2, 1, 2, 1), (3, 2, 2, 2), (4, 2, 3, 2),
])
def test_the_bands(margin, push, strike, seize):
    assert ft.band(margin, ft.PUSH) == push
    assert ft.band(margin, ft.STRIKE) == strike
    assert ft.band(margin, ft.SEIZE) == seize


def test_build_up_and_reinforce(ops):
    lines = ft.apply(ops, ft.resolve(ops, ft.check(ops, [
        {"faction": "Meridian", "action": "build", "power": "Covert"},
        {"faction": "system", "action": "reinforce", "power": "Political", "at": _here(ops)},
    ]), Dice(6, 5)))
    assert _power(ops, "meridian-group", "Covert") == 6            # 3 + 3 on a 6
    assert presence(ops, _here(ops))["system"] == 5                 # 3 + 2 on a 5
    text = "\n".join(lines)
    assert "Meridian Group: Build up (Covert): d6 6" in text and "Covert: 3 → 6" in text


def test_everything_is_judged_from_the_start_of_the_turn(ops):
    """Meridian builds Military while the System pushes it: the push rolls against
    Meridian's Military before the build (3), not after."""
    results = ft.resolve(ops, ft.check(ops, [
        {"faction": "Meridian", "action": "build", "power": "Military"},
        {"faction": "system", "action": "push", "power": "Military", "rival": "Meridian",
         "at": _here(ops)},
    ]), Dice(6, 4, 4))
    push = results[1]
    assert push["against"] == 3 and push["margin"] == 0 and push["effect"] == 1
    ft.apply(ops, results)
    assert _power(ops, "meridian-group", "Military") == 6
    assert presence(ops, _here(ops))["meridian-group"] == 1


def test_a_strike_costs_and_hits_hard(ops):
    wr.change(ops, "Military", "Meridian", by=4)                    # 7 against 3
    ft.apply(ops, ft.resolve(ops, ft.check(ops, [
        {"faction": "Meridian", "action": "strike", "power": "Military", "rival": "system",
         "at": _here(ops)}]), Dice(3, 3)))                           # margin +4: -3
    assert presence(ops, _here(ops))["system"] == 0
    assert _power(ops, "meridian-group", "Military") == 5           # cost 2


def test_a_failed_complex_action_costs_more(ops):
    lines = ft.apply(ops, ft.resolve(ops, ft.check(ops, [
        {"faction": "Meridian", "action": "strike", "power": "Military", "rival": "system",
         "at": _here(ops)}]), Dice(1, 6)))
    assert _power(ops, "meridian-group", "Military") == 0           # 3 - 3
    assert presence(ops, _here(ops))["system"] == 3
    assert "it fails (cost 3)" in "\n".join(lines)


def test_seize_takes_a_place_or_an_asset(ops):
    FactionManager(ops).asset("system", "The Ratings Board", "Decides who gets airtime.")
    ft.apply(ops, ft.resolve(ops, ft.check(ops, [
        {"faction": "Meridian", "action": "seize", "power": "Covert", "rival": "system",
         "asset": "the ratings board"}]), Dice(4, 4)))
    assert [a["name"] for a in load(ops)["meridian-group"]["assets"]] == ["The Ratings Board"]
    assert "assets" not in load(ops)["system"]


def test_prepare_moves_the_plan_clock_and_its_portents(ops, dcc_world):
    from lib.consequence_manager import ConsequenceManager
    from lib.plot_manager import PlotManager
    from lib.threat_clocks import ThreatClockManager
    PlotManager(dcc_world).add("Hostile Takeover", "Meridian buys the floor.", owner="Meridian",
                               goal="own every guard post")
    ThreatClockManager(dcc_world).add_clock("Takeover", 3, advance_on="event",
                                            plots=["Hostile Takeover"], text="the buy-out")
    cid = ConsequenceManager(dcc_world).add_consequence(
        "Rumour: Meridian is hiring.", "y", trigger_type="on_clock", match="Takeover:1",
        offscreen=True)
    lines = ft.run(ops, [{"faction": "Meridian", "action": "prepare"}], Dice())
    text = "\n".join(lines)
    assert "plan clock Takeover (Hostile Takeover): 1/3" in text and f"[{cid}]" in text
    assert "Not acting this turn: " in text and "system" in text.split("Not acting")[1]


def test_enact_needs_a_full_plan_clock(ops, dcc_world):
    from lib.plot_manager import PlotManager
    from lib.threat_clocks import ThreatClockManager
    PlotManager(dcc_world).add("Hostile Takeover", "x", owner="Meridian", goal="y")
    ThreatClockManager(dcc_world).add_clock("Takeover", 1, advance_on="event", plots=["Hostile Takeover"])
    with pytest.raises(ft.TurnError, match="has no full plan clock yet"):
        ft.check(ops, [{"faction": "Meridian", "action": "enact", "power": "Political"}])
    ft.run(ops, [{"faction": "Meridian", "action": "prepare"}], Dice())
    lines = ft.run(ops, [{"faction": "Meridian", "action": "enact", "power": "Political"}], Dice(6, 1))
    assert "the plan succeeds: gm-plot.sh complete \"Hostile Takeover\"" in "\n".join(lines)


@pytest.mark.parametrize("action, words", [
    ({"faction": "Meridian", "action": "dance"}, "the action is one of"),
    ({"faction": "Meridian", "action": "build", "power": "Charm"}, "\"power\" is one of"),
    ({"faction": "Meridian", "action": "push", "power": "Military", "at": "x"}, "name the rival"),
    ({"faction": "Meridian", "action": "push", "power": "Military", "rival": "Meridian",
      "at": "x"}, "not its own rival"),
    ({"faction": "system", "action": "push", "power": "Military", "rival": "crawlers",
      "at": "@here"}, "crawlers has no presence"),
    ({"faction": "Meridian", "action": "prepare"}, "which plot"),
    ({"faction": "Meridian", "action": "seize", "power": "Covert", "rival": "system",
      "asset": "The Moon"}, "has no asset"),
])
def test_what_a_turn_refuses(ops, action, words):
    action = {k: (_here(ops) if v == "@here" else v) for k, v in action.items()}
    with pytest.raises(ft.TurnError, match=words):
        ft.check(ops, [action])


def test_one_action_per_faction_and_nothing_changes_on_a_problem(ops):
    with pytest.raises(ft.TurnError, match="acts twice") as error:
        ft.check(ops, [{"faction": "Meridian", "action": "build", "power": "Covert"},
                       {"faction": "meridian", "action": "build", "power": "Military"}])
    assert "Nothing was changed" in str(error.value)


def test_a_complex_action_needs_the_power_to_pay(ops):
    wr.change(ops, "Covert", "Meridian", by=-2)
    with pytest.raises(ft.TurnError, match="costs 2 Covert power"):
        ft.check(ops, [{"faction": "Meridian", "action": "spy", "power": "Covert", "rival": "system"}])


def test_the_command(ops, dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)
    turn = json.dumps([{"faction": "Meridian", "action": "build", "power": "Economic",
                        "note": "new contracts"}])
    done = subprocess.run(["bash", str(ROOT / "tools" / "gm-faction.sh"), "turn"], input=turn,
                          capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    assert "Meridian Group: Build up (Economic) (new contracts): d6" in done.stdout
    bad = subprocess.run(["bash", str(ROOT / "tools" / "gm-faction.sh"), "turn"],
                         input='[{"faction": "Meridian", "action": "dance"}]',
                         capture_output=True, text=True, env=env)
    assert bad.returncode == 1 and bad.stderr.startswith("[ERROR]")
