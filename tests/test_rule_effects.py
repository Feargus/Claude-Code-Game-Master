"""Results that act (lib/rule_effects.py, 2026-11-17, step 3): a result's effects run
when it comes on (when_off when it goes off), a change they make turns its own
results on in a chain, a rule changes once per chain, and a consequence can wait on
a value (on_rule)."""

import os
import subprocess
from pathlib import Path

import pytest

from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager
from lib.json_ops import JsonOperations

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = "dungeon-crawler-carl"


def _counter(name, held_by="player", results=(), **more):
    return {"name": name, "block": "counter", "held_by": held_by, "range": [0, 6],
            "summary": f"{name}.", "when": "When it happens.", "results": list(results), **more}


STRESS = _counter("Stress", results=[
    {"from": 4, "text": "Shaking.",
     "effects": [{"change": "Panic", "by": 2}, {"condition": "Shaken"}, {"credits": 40}],
     "when_off": [{"condition": "Shaken", "add": False}],
     "gm": "Ask for a Composure roll at the next loud noise."}])
PANIC = _counter("Panic", results=[{"from": 2, "text": "Panicking.",
                                    "effects": [{"change": "Stress", "by": 1}]}])
PATIENCE = _counter("Patience", held_by="faction", start=5, results=[
    {"from": 0, "to": 0, "text": "They act.",
     "effects": [{"clock": "Retaliation", "start": 3, "text": "They come for the character",
                  "due_in": "3d"}]}])
SEA = _counter("Sea level", held_by="world", start=2)


def _ops(dcc_world):
    return JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))


@pytest.fixture
def ops(dcc_world):
    ops = _ops(dcc_world)
    wr.define(ops, [STRESS, PANIC, PATIENCE, SEA])
    return ops


def _character(ops):
    return ops.load_json("character.json")


# ---------- checking ----------

@pytest.mark.parametrize("effects, why", [
    ([{"wobble": 1}], "an effect is one of change, rate_of, state, tokens, clock, condition, credits"),
    ([{"tokens": "The Job", "add": {"trouble": 1}}], "no bag 'The Job' to add tokens to"),
    ([{"rate_of": "Panic", "by": 1}], "no counter 'Panic' with a rate in steps"),
    ([{"change": "Panic"}], 'a change effect has "by": N or "set": N'),
    ([{"change": "Panic", "by": 1, "colour": 2}], "'colour' has no place in a change effect"),
    ([{"clock": "X"}], 'a clock effect has "start": N segments or "advance": N'),
    ([{"clock": "X", "start": 2, "due_in": "soon"}], "due_in:"),
    ([{"credits": 0}], 'a credits effect is "credits": N'),
    ([{"change": "Nothing", "by": 1}], "no counter or plane 'Nothing' to change"),
    ([{"change": "Stress", "by": 1}], "a result can't change its own rule"),
    ([{"change": "Panic", "set": 9}], "Panic goes from 0 to 6, not 9"),
    ([{"change": "Patience", "by": -1}], "name whose with \"of\""),
    ([{"change": "Patience", "by": -1, "of": "player"}], "Patience can't be held by 'player'"),
])
def test_wrong_effects_are_refused_when_defined(dcc_world, effects, why):
    stress = _counter("Stress", results=[{"from": 4, "text": "x", "effects": effects}])
    with pytest.raises(wr.RulesError, match=why):
        wr.define(_ops(dcc_world), [stress, PANIC, PATIENCE])


def test_a_rule_other_rules_change_cant_be_removed(ops):
    with pytest.raises(wr.RulesError, match="changed by the effects of Stress"):
        wr.remove(ops, "Panic")


# ---------- running ----------

def test_a_result_coming_on_carries_out_its_effects_in_a_chain(ops):
    start = _character(ops)["possessions"]["credits"]
    report = wr.change(ops, "Stress", by=4)
    assert report["after"] == 4 and report["on"] == ["from 4"]
    done = report["did"]["from 4"]
    panic = done[0]["report"]
    assert (panic["rule"], panic["before"], panic["after"], panic["on"]) == ("Panic", 0, 2, ["from 2"])
    # Panic's own effect would change Stress again: stopped, a rule changes once a chain
    assert "Stress of Tandy changed once already" in panic["did"]["from 2"][0]["line"]
    assert done[1]["line"] == "condition Shaken added"
    assert done[2]["line"] == f"+40 credits (now {start + 40})"
    assert report["character"] == ["condition Shaken added", f"+40 credits (now {start + 40})"]
    character = _character(ops)
    assert "Shaken" in character["status"]["conditions"]
    assert character["possessions"]["credits"] == start + 40
    text = "\n".join(wr.change_lines(ops, report))
    assert "  now on:   from 4: Shaking.\n    → Panic (Tandy): 0 → 2" in text
    assert "    Do now: Ask for a Composure roll at the next loud noise." in text
    assert text.endswith(f"Changed on the character: condition Shaken added; +40 credits "
                         f"(now {start + 40}).")
    log = (Path(ops.world_state_dir) / "rules.log").read_text()
    assert "Panic: 0 -> 2\tby effect of Stress from 4" in log


def test_a_result_going_off_runs_when_off(ops):
    wr.change(ops, "Stress", by=4)
    report = wr.change(ops, "Stress", to=1)
    assert report["off"] == ["from 4"] and report["did"]["from 4"][0]["line"] == "condition Shaken removed"
    assert "Shaken" not in _character(ops)["status"]["conditions"]
    assert report["character"] == ["condition Shaken removed"]


def test_an_effect_that_cant_be_done_says_why(ops):
    character = _character(ops)
    character["possessions"]["credits"] = 5
    ops.save_json("character.json", character)
    rules = [_counter("Debt", results=[{"from": 1, "text": "Pay.", "effects": [{"credits": -10}]}])]
    wr.define(ops, rules)
    report = wr.change(ops, "Debt", by=1)
    assert report["did"]["from 1"][0]["line"] == ("not done: the character has 5 credits, "
                                                  "not the 10 this would take")
    assert _character(ops)["possessions"]["credits"] == 5 and not report["character"]


def test_conditions_and_credits_are_the_characters_only(ops):
    """A rule held by NPCs too: when an NPC reaches the result, its condition and
    credits are not given to the character (hard-country trial, 2026-11-18)."""
    wr.define(ops, [_counter("Lungs", held_by=["player", "npc"], results=[
        {"from": 4, "text": "Short of breath.",
         "effects": [{"condition": "Short of breath"}, {"credits": -5}]}])])
    start = _character(ops)["possessions"]["credits"]
    report = wr.change(ops, "Lungs", "Carl", by=4)
    lines = [d["line"] for d in report["did"]["from 4"]]
    assert lines == [f"not done ({kind}): Carl is not the character, and only the character "
                     f"has {what}; play it from the result's text"
                     for kind, what in (("condition", "conditions"), ("credits", "credits"))]
    character = _character(ops)
    assert "Short of breath" not in (character["status"].get("conditions") or [])
    assert character["possessions"]["credits"] == start and not report["character"]
    mine = wr.change(ops, "Lungs", "player", by=4)
    assert [d["line"] for d in mine["did"]["from 4"]][0] == "condition Short of breath added"


def test_an_effect_starts_and_advances_clocks(ops):
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"                 # a duration needs a game time
    ops.save_json("campaign-overview.json", overview)
    report = wr.change(ops, "Patience", "faction:crawlers", to=0)
    assert report["did"]["at 0"][0]["line"] == "clock Retaliation started (3 segments, due in 3d)"
    clocks = ops.load_json("threat-clocks.json")
    assert clocks["Retaliation"]["max"] == 3
    # a clock started for someone other than the character says whose it is
    assert clocks["Retaliation"]["text"] == f"For {wr.holder_name(ops, 'faction:crawlers')}: They come for the character"
    again = wr.change(ops, "Patience", "faction:system", to=0)
    assert again["did"]["at 0"][0]["line"].startswith("not done (clock): A clock 'Retaliation' exists")
    wr.define(ops, [_counter("Rumour", results=[
        {"from": 1, "text": "Talk.", "effects": [{"clock": "Gossip", "advance": 1}]}])])
    with_no_clock = wr.change(ops, "Rumour", by=1)
    assert with_no_clock["did"]["from 1"][0]["line"] == "not done: no clock 'Gossip' to advance"


# ---------- on_rule ----------

def test_a_consequence_waits_on_a_value(dcc_world, ops, capsys):
    cm = ConsequenceManager(dcc_world)
    flood = cm.add_consequence("The hospital evacuates its lower wards", "the sea reaches 5",
                               trigger_type="on_rule", match="sea level:5")
    act = cm.add_consequence("The Crawlers send someone", "their patience runs out",
                             trigger_type="on_rule", match="Patience:0 @ The Crawlers")
    stored = {c["id"]: c["triggers"][0]["match"] for c in ops.load_json("consequences.json")["active"]
              if c["id"] in (flood, act)}
    assert stored[flood] == "Sea level:5@world" and stored[act] == "Patience:0@faction:crawlers"
    for bad, why in (("Sea level", "on_rule matches"), ("Sea level:11", "goes from 0 to 6"),
                     ("Patience:0", "Whose Patience"), ("Tide:2", "No rule 'Tide'")):
        assert cm.add_consequence("x", "y", trigger_type="on_rule", match=bad) == ""
        assert why in capsys.readouterr().err
    rise = wr.change(ops, "Sea level", by=4)                         # 2 → 6 passes 5
    assert [c["id"] for c in rise["fired"]] == [flood]
    assert "[FIRED] c" in "\n".join(wr.change_lines(ops, rise))
    assert wr.change(ops, "Sea level", to=4)["fired"] == []          # fires once
    assert wr.change(ops, "Patience", "faction:system", to=0)["fired"] == []   # another faction
    assert [c["id"] for c in wr.change(ops, "Patience", "faction:crawlers", by=-5)["fired"]] == [act]


def test_the_command_prints_the_chain(dcc_world, ops):
    out = subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), "change", "Stress", "+4"],
                         capture_output=True, text=True,
                         env=dict(os.environ, GM_WORLD_STATE_BASE=dcc_world))
    assert out.returncode == 0, out.stderr
    assert "→ Panic (Tandy): 0 → 2" in out.stdout
    assert "Changed on the character: condition Shaken added" in out.stdout
    back = subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), "change", "Stress", "-4"],
                          capture_output=True, text=True,
                          env=dict(os.environ, GM_WORLD_STATE_BASE=dcc_world))
    assert "Changed on the character: condition Shaken removed" in back.stdout
