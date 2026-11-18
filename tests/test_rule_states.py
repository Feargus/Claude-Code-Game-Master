"""States (lib/rule_states.py, 2026-11-17, step 6): a value that is a named state,
moved only along its allowed moves, on by time spent in a state, with effects on
entering and leaving, and consequences that wait on a state."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import rule_states
from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager
from lib.json_ops import JsonOperations
from lib.time_manager import TimeManager

ROOT = Path(__file__).resolve().parent.parent

ADDICTION = {
    "name": "Addiction", "block": "states", "held_by": ["player", "npc"], "start": "clean",
    "summary": "A drug's hold on someone.", "when": "A dose: gm-rule.sh move Addiction user.",
    "states": {
        "clean": {"text": "No pull.", "moves": {"user": "a dose"}},
        "user": {"text": "A taste for it.", "moves": {"hooked": "Need reaches 5", "clean": "a month without"},
                 "after": {"30d": "clean"}},
        "hooked": {"text": "-1 to every roll without a dose.",
                   "moves": {"withdrawal": "a day without", "hooked": "a dose (the day starts again)"},
                   "after": {"1d": "withdrawal"},
                   "effects": [{"condition": "Hooked"}],
                   "when_off": [{"condition": "Hooked", "add": False}],
                   "gm": "Play the craving in every quiet moment."},
        "withdrawal": {"text": "Shakes, sweats.", "moves": {"recovering": "the week sat through",
                                                            "hooked": "a dose"},
                       "after": {"7d": "recovering"}},
        "recovering": {"text": "Clean, and it knows where they live.", "moves": {"user": "a dose"},
                       "after": {"90d": "clean"}},
    }}
ALERT = {
    "name": "Alert", "block": "states", "held_by": "faction", "start": "asleep",
    "summary": "How alert a corporation is.", "when": "After a job against them.",
    "states": {"asleep": {"text": "Routine.", "moves": {"watching": "a trace"}},
               "watching": {"text": "Logs read.", "moves": {"lockdown": "a breach"}},
               "lockdown": {"text": "Everything changed."}}}
NEED = {"name": "Need", "block": "counter", "held_by": ["player", "npc"], "range": [0, 5],
        "summary": "The craving.", "when": "Each day without a dose.",
        "results": [{"from": 5, "text": "It has them.",
                     "effects": [{"state": "addiction", "to": "HOOKED"}]}]}


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    wr.define(ops, [ADDICTION, ALERT, NEED])
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops


def _state(ops, holder="player", rule="Addiction"):
    return wr.entry(ops, wr.find_rule(ops, rule), holder)["state"]


def test_states_move_only_along_their_moves(ops):
    assert _state(ops) == "clean"
    with pytest.raises(ValueError, match="can't move from 'clean' to 'hooked': from it: user .a dose."):
        rule_states.move(ops, "Addiction", "player", "hooked")
    rule_states.move(ops, "Addiction", "player", "User")
    report = rule_states.move(ops, "Addiction", "player", "hooked")
    assert (report["before"], report["after"]) == ("user", "hooked")
    assert report["character"] == ["condition Hooked added"]
    text = "\n".join(rule_states.move_lines(ops, report))
    assert text.startswith("Addiction (Tandy): user → hooked\n  now: hooked: -1 to every roll")
    assert "    Do now: Play the craving in every quiet moment." in text
    again = rule_states.move(ops, "Addiction", "player", "hooked")
    assert "(again: its time starts anew)" in rule_states.move_lines(ops, again)[0]
    assert again["character"] == []                             # has it already: no change
    forced = rule_states.move(ops, "Addiction", "player", "clean", force=True)
    assert forced["character"] == ["condition Hooked removed"]
    rule_states.move(ops, "Alert", "faction:system", "watching")
    final = rule_states.move(ops, "Alert", "faction:system", "lockdown")
    assert "'lockdown' is final." in "\n".join(rule_states.move_lines(ops, final))
    with pytest.raises(ValueError, match="'lockdown' is final"):
        rule_states.move(ops, "Alert", "faction:system", "asleep")


def test_time_in_a_state_moves_it_on(dcc_world, ops):
    rule_states.move(ops, "Addiction", "Carl", "user")
    rule_states.move(ops, "Addiction", "Carl", "hooked")
    manager = TimeManager(dcc_world)
    manager.advance(9 * 24 * 60, through_all=True)                           # hooked 1d → withdrawal 7d → recovering
    moves = [(r["before"], r["after"]) for r in manager.rule_changes]
    assert moves == [("hooked", "withdrawal"), ("withdrawal", "recovering")]
    stored = wr.load_state(ops)["npc:Carl"]["Addiction"]
    assert stored["state"] == "recovering" and stored["entered"] == "2187-11-03T04:30"  # day 1 + 7
    assert "time: 7d in 'withdrawal'" in (Path(ops.world_state_dir) / "rules.log").read_text()


def test_a_counter_can_move_a_state(ops):
    stuck = wr.change(ops, "Need", "player", to=5)                       # from clean: not one of its moves
    assert stuck["did"]["from 5"][0]["line"].startswith("not done: Addiction (Tandy) can't move")
    wr.change(ops, "Need", "player", to=0)
    rule_states.move(ops, "Addiction", "player", "user")
    moved = wr.change(ops, "Need", "player", to=5)
    assert moved["did"]["from 5"][0]["states_report"]["after"] == "hooked"
    text = "\n".join(wr.change_lines(ops, moved))
    assert "    → Addiction (Tandy): user → hooked" in text
    assert moved["character"] == ["condition Hooked added"]


def test_a_consequence_waits_on_a_state(dcc_world, ops, capsys):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("Carl's dealer raises the price", "Carl is hooked",
                             trigger_type="on_rule", match="addiction:HOOKED@Carl")
    stored = next(c for c in ops.load_json("consequences.json")["active"] if c["id"] == cid)
    assert stored["triggers"][0]["match"] == "Addiction:hooked@npc:Carl"
    assert cm.add_consequence("x", "y", trigger_type="on_rule", match="Addiction:numb@Carl") == ""
    assert "has no state 'numb'" in capsys.readouterr().err
    rule_states.move(ops, "Addiction", "Carl", "user")
    assert [c["id"] for c in rule_states.move(ops, "Addiction", "Carl", "hooked")["fired"]] == [cid]


@pytest.mark.parametrize("change, why", [
    ({"start": "sober"}, "'start' is one of the states"),
    ({"states": {}}, "'states' is"),
    ({"states": {"clean": {"text": "x", "moves": {"high": "a dose"}}}}, "moves to 'high', which is no state"),
    ({"states": {"clean": {"moves": {}}}}, "needs a 'text'"),
    ({"states": {"clean": {"text": "x", "after": {"1d": "clean"}}}}, "'after' moves to another state"),
    ({"states": {"clean": {"text": "x", "after": {"soon": "x"}}}}, "'after':"),
    ({"states": {"clean": {"text": "x", "colour": 1}}}, "state 'clean' has no 'colour'"),
    ({"states": {"clean": {"text": "x", "effects": [{"state": "Alert", "to": "asleep"}]}}},
     "Alert is held by faction, not by every holder of Addiction"),
    ({"states": {"clean": {"text": "x", "effects": [{"state": "Alert", "to": "dozing", "of": "faction:system"}]}}},
     "Alert has no state 'dozing'"),
])
def test_a_wrong_states_rule_is_refused(dcc_world, change, why):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    with pytest.raises(wr.RulesError, match=why):
        wr.define(ops, [ALERT, {**ADDICTION, "start": "clean", **change}])


def test_a_state_in_use_cant_be_dropped(ops):
    rule_states.move(ops, "Addiction", "player", "user")
    fewer = {**ADDICTION, "states": {"clean": ADDICTION["states"]["clean"]}}
    fewer["states"]["clean"] = {"text": "No pull."}
    with pytest.raises(wr.RulesError, match=r"doesn't fit what some holders have: player \(its state 'user' is gone"):
        wr.define(ops, [fewer, {**NEED, "results": []}])


def test_states_in_the_brief_the_cards_and_the_hud(dcc_world, ops):
    rule_states.move(ops, "Addiction", "player", "user")
    rule_states.move(ops, "Addiction", "Carl", "user")
    text = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Addiction")))
    assert text.startswith("Addiction (states, held by the player, NPCs): A drug's hold on someone.")
    assert "  hooked: -1 to every roll without a dose. Moves: → withdrawal (a day without); " \
           "→ hooked (a dose (the day starts again)); after 1d: → withdrawal" in text
    assert "  clean (the start): No pull." in text
    assert 'Command: gm-rule.sh move "Addiction" "<holder>" <state>' in text
    assert "Now, Tandy: user (since 2187-10-26T04:30)" in text
    from lib.cards import Cards
    assert "  rule: Addiction: user (states): A taste for it." in Cards(ops).npc_card("Carl")
    assert "Addiction: user" in wr.summary(ops)
    hud = subprocess.run(["jq", "-r", "-s", "."], input="{}", capture_output=True, text=True)
    assert hud.returncode == 0                                  # jq is there for the HUD


def test_starting_values_and_the_command(dcc_world, ops):
    assert wr.check_values(ops, "player", {"addiction": "Hooked"}) == [("Addiction", "hooked")]
    with pytest.raises(ValueError, match="has no state 'high'"):
        wr.check_values(ops, "player", {"Addiction": "high"})
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), *words],
                              capture_output=True, text=True, env=env)
    refused = run("move", "Addiction", "Tandy", "hooked")
    assert refused.returncode == 1 and "can't move from 'clean'" in refused.stderr
    assert run("move", "Addiction", "Tandy", "user").stdout.startswith("Addiction (Tandy): clean → user")
    assert run("set", "Addiction", "Tandy", "recovering").returncode == 0          # any state
    assert json.loads(run("show", "Addiction", "--json").stdout)["data"]["state"]["player"][
        "state"] == "recovering"
    assert "is a states" in run("change", "Addiction", "Tandy", "+1").stderr
