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


def _plan(dcc_world, segments=3, consequence=None, plot="Hostile Takeover"):
    from lib.plot_manager import PlotManager
    from lib.threat_clocks import ThreatClockManager
    PlotManager(dcc_world).add(plot, "own every guard post", owner="Meridian")
    ThreatClockManager(dcc_world).add_clock("Takeover", segments, advance_on="event",
                                            plots=[plot], text="the buy-out",
                                            consequence=consequence)


TAKE = {"faction": "Meridian", "action": "take", "power": "Covert", "who": "Mordecai"}


def _rich(ops):
    """Covert enough for several complex actions in a row (each costs 2 or 3)."""
    wr.change(ops, "Covert", "faction:meridian-group", by=3, cause="a test")   # 6


def _clock(dcc_world):
    return json.loads((Path(dcc_world) / "campaigns" / CAMPAIGN / "threat-clocks.json")
                      .read_text())["Takeover"]["current"]


def test_a_complex_action_for_the_plot_moves_its_plan_clock_and_portents(ops, dcc_world):
    from lib.consequence_manager import ConsequenceManager
    _plan(dcc_world)
    cid = ConsequenceManager(dcc_world).add_consequence(
        "Rumour: Meridian is hiring.", "y", trigger_type="on_clock", match="Takeover:1",
        offscreen=True)
    text = "\n".join(ft.run(ops, [TAKE], Dice(6, 1), only="Meridian"))   # 6+3 against 1+2
    assert "plan clock Takeover (Hostile Takeover): 1/3" in text and f"[{cid}]" in text


def test_a_failed_action_or_one_not_for_the_plot_moves_nothing(ops, dcc_world):
    _plan(dcc_world)
    _rich(ops)
    text = "\n".join(ft.run(ops, [TAKE], Dice(1, 6), only="Meridian"))
    assert "plan clock Takeover (Hostile Takeover) doesn't move" in text
    text = "\n".join(ft.run(ops, [dict(TAKE, plot="none")], Dice(6, 1), only="Meridian"))
    assert "plan clock" not in text
    assert _clock(dcc_world) == 0


def test_a_full_plan_clock_fires_the_plans_success(ops, dcc_world):
    _plan(dcc_world, segments=1, consequence="Meridian owns every guard post")
    text = "\n".join(ft.run(ops, [TAKE], Dice(6, 1), only="Meridian"))
    assert "Meridian owns every guard post (fired)" in text
    assert "the plan succeeds: play out its consequence, then gm-plot.sh complete " \
           "\"Hostile Takeover\"" in text


def test_which_plot_an_action_is_for(ops, dcc_world):
    _rich(ops)
    text = "\n".join(ft.run(ops, [TAKE], Dice(6, 1), only="Meridian"))
    assert "plan clock" not in text                                  # no plot of its own
    from lib.plot_manager import PlotManager
    PlotManager(dcc_world).add("Hostile Takeover", "y", owner="Meridian")
    text = "\n".join(ft.run(ops, [TAKE], Dice(6, 1), only="Meridian"))
    assert "for Hostile Takeover, which has no plan clock to move" in text
    PlotManager(dcc_world).add("Second Front", "z", owner="Meridian")
    with pytest.raises(ft.TurnError, match="which plot is it for"):
        ft.check(ops, [TAKE])
    assert ft.check(ops, [dict(TAKE, plot="Second Front")])[0]["plot"] == "Second Front"


@pytest.mark.parametrize("action, words", [
    ({"faction": "Meridian", "action": "dance"}, "the action is one of"),
    ({"faction": "Meridian", "action": "build", "power": "Charm"}, "\"power\" is one of"),
    ({"faction": "Meridian", "action": "push", "power": "Military", "at": "x"}, "name the rival"),
    ({"faction": "Meridian", "action": "push", "power": "Military", "rival": "Meridian",
      "at": "x"}, "not its own rival"),
    ({"faction": "system", "action": "push", "power": "Military", "rival": "crawlers",
      "at": "@here"}, "crawlers has no presence"),
    ({"faction": "Meridian", "action": "build", "power": "Covert", "plot": "x"},
     "only a complex action moves a plot"),
    ({"faction": "Meridian", "action": "prepare"}, "the action is one of"),
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
    done = subprocess.run(["bash", str(ROOT / "tools" / "gm-faction.sh"), "turn", "--only",
                           "Meridian"], input=turn,
                          capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    assert "Meridian Group: Build up (Economic) (new contracts): d6" in done.stdout
    bad = subprocess.run(["bash", str(ROOT / "tools" / "gm-faction.sh"), "turn"],
                         input='[{"faction": "Meridian", "action": "dance"}]',
                         capture_output=True, text=True, env=env)
    assert bad.returncode == 1 and bad.stderr.startswith("[ERROR]")


def test_every_faction_acts_or_one_alone(ops):
    with pytest.raises(ft.TurnError, match="every faction acts: no action for") as error:
        ft.run(ops, [{"faction": "Meridian", "action": "build", "power": "Covert"}], Dice(1))
    assert "crawlers" in str(error.value) and "--only" in str(error.value)
    lines = ft.run(ops, [{"faction": "Meridian", "action": "build", "power": "Covert"}], Dice(1),
                   only="meridian")
    assert lines[1].startswith("Meridian Group: Build up (Covert)")
    with pytest.raises(ft.TurnError, match="--only meridian-group: give its one action"):
        ft.run(ops, [{"faction": "system", "action": "build", "power": "Covert"}], Dice(1),
               only="Meridian")


def test_a_change_where_the_character_is_says_so(ops):
    lines = ft.apply(ops, ft.resolve(ops, ft.check(ops, [
        {"faction": "system", "action": "reinforce", "power": "Military", "at": _here(ops)},
        {"faction": "Meridian", "action": "build", "power": "Covert"}]), Dice(1, 1)))
    text = "\n".join(lines)
    assert f"HERE: Tandy is at {_here(ops)} and sees it happen" in text
    assert text.count("HERE:") == 1                                 # not for the build


def test_the_possessive():
    assert ft.possessive("Hardtop Holdings") == "Hardtop Holdings'"
    assert ft.possessive("The Kin") == "The Kin's"


def test_take_needs_no_rival(ops, dcc_world):
    results = ft.resolve(ops, ft.check(ops, [
        {"faction": "Meridian", "action": "take", "power": "Covert", "who": "Mordecai"}]), Dice(3, 4))
    assert results[0]["against"] == 2 and results[0]["margin"] == 0 and results[0]["effect"] == 1


def test_campaigns_behind_a_symlink(dcc_world, tmp_path):
    """world-state/campaigns may be a link to a folder elsewhere (the campaigns kept
    in their own repository): the active campaign is still found, so a complex
    action moves its plan clock instead of saying "not the active campaign"."""
    from lib.plot_manager import PlotManager
    from lib.rule_effects import _base
    from lib.threat_clocks import ThreatClockManager
    elsewhere = tmp_path / "elsewhere" / "campaigns"
    elsewhere.parent.mkdir()
    (Path(dcc_world) / "campaigns").rename(elsewhere)
    (Path(dcc_world) / "campaigns").symlink_to(elsewhere)
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    assert _base(ops) == str(Path(dcc_world).absolute())

    FactionManager(ops).create("Meridian Group", "A security firm.", aliases=["Meridian"])
    PlotManager(dcc_world).add("Hostile Takeover", "own every guard post", owner="Meridian")
    ThreatClockManager(dcc_world).add_clock("Takeover", 3, advance_on="event",
                                            plots=["Hostile Takeover"], text="the buy-out")
    lines = ft.run(ops, [TAKE], Dice(6, 1), only="Meridian")
    assert "plan clock Takeover (Hostile Takeover): 1/3" in "\n".join(lines)
