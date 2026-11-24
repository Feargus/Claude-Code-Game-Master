"""The roll (lib/rule_roll.py): dice plus named amounts, and
optionally a holder's value of a counter, read from a list of results; its effects
run every time it is rolled. It keeps nothing."""

import os
import subprocess
from pathlib import Path

import pytest

from lib import rule_roll
from lib import world_rules as wr
from lib.json_ops import JsonOperations

ROOT = Path(__file__).resolve().parent.parent

BLEED = {"name": "Bleed", "block": "counter", "held_by": "player", "range": [0, 6],
         "summary": "Leaked work.", "when": "After a Lease.",
         "results": [{"from": 2, "text": "Intrusions."}]}
LEASE = {"name": "The Lease", "block": "roll", "held_by": "player",
         "summary": "Leasing your mind costs something.", "when": "Each lease.",
         "dice": "1d20", "with": {"ordinary night": 0, "deep lease": -2, "Mesh run": -4},
         "results": [
             {"from": 15, "text": "Clean."},
             {"from": 10, "text": "+1 Bleed.", "effects": [{"change": "Bleed", "by": 1}]},
             {"from": 5, "text": "+1 Bleed and a stranger's memory.",
              "effects": [{"change": "Bleed", "by": 1}], "gm": "Invent the memory."},
             {"text": "+2 Bleed and a memory gone.", "effects": [{"change": "Bleed", "by": 2}],
              "gm": "Pick one that matters; record it as a fact."}]}
RESPECT = {"name": "Respect", "block": "counter", "held_by": "faction", "range": [-3, 3],
           "start": 0, "summary": "How a gang regards the character.", "when": "Deeds."}
WELCOME = {"name": "Street welcome", "block": "roll", "held_by": "faction",
           "summary": "How a gang's people meet the character.", "when": "First contact.",
           "dice": "2d6", "add": "respect",
           "results": [{"from": 8, "text": "Neutral."}, {"from": 5, "text": "Wary."}]}


class Fixed:
    """Dice that roll `face` (clamped into the die)."""

    def __init__(self, face):
        self.face = face

    def randint(self, a, b):
        return min(max(self.face, a), b)


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    wr.define(ops, [BLEED, LEASE, RESPECT, WELCOME])
    return ops


def test_a_roll_reads_its_results_and_carries_out_their_effects(ops):
    report = rule_roll.roll(ops, "the lease", named=["Deep Lease"], rng=Fixed(13))
    assert (report["rolled"], report["total"], report["result"]) == (13, 11, "10+")
    assert report["did"][0]["report"]["after"] == 1                  # Bleed +1
    text = "\n".join(rule_roll.roll_lines(ops, report))
    assert text.startswith("The Lease (Tandy): 1d20 13, deep lease -2 → 11\n  10+: +1 Bleed.")
    assert "    → Bleed (Tandy): 0 → 1" in text
    low = rule_roll.roll(ops, "The Lease", named=["Mesh run"], rng=Fixed(3))
    assert (low["total"], low["result"], low["gm"]) == (-1, "below 5",
                                                         "Pick one that matters; record it as a fact.")
    assert "Do now: Pick one that matters" in "\n".join(rule_roll.roll_lines(ops, low))
    assert wr.entry(ops, wr.find_rule(ops, "Bleed"), "player")["value"] == 3
    assert "rolled 1d20 3, Mesh run -4 = -1: below 5" in (Path(ops.world_state_dir) / "rules.log").read_text()


def test_a_roll_can_add_a_holders_value(ops):
    wr.change(ops, "Respect", "faction:crawlers", by=2)
    welcome = rule_roll.roll(ops, "Street welcome", "The Crawlers", rng=Fixed(3))
    assert welcome["add"] == ["Respect", 2] and welcome["total"] == 8 and welcome["result"] == "8+"
    cold = rule_roll.roll(ops, "Street welcome", "faction:system", rng=Fixed(1))
    assert cold["total"] == 2 and cold["result"] == "5+"              # no catch-all: the lowest
    assert "Respect +0" in "\n".join(rule_roll.roll_lines(ops, cold))


def test_what_a_roll_is_not(ops):
    for call, why in ((lambda: rule_roll.roll(ops, "The Lease", named=["a nap"]), "no amount 'a nap'"),
                      (lambda: rule_roll.roll(ops, "Bleed"), "Bleed is a counter, not a roll"),
                      (lambda: wr.change(ops, "The Lease", by=1), "The Lease is a roll: it has no value"),
                      (lambda: wr.set_known(ops, "The Lease"), "is a roll")):
        with pytest.raises(ValueError, match=why):   # RulesError, under either module name
            call()
    from lib.rule_effects import on_rule_target
    assert "is a roll" in on_rule_target(ops, "The Lease:5")[1]


@pytest.mark.parametrize("change, why", [
    ({"dice": "a handful"}, "'dice' must be dice to roll"),
    ({"with": {"deep": "lots"}}, "'with' must be named amounts"),
    ({"results": []}, "'results' must be a list"),
    ({"results": [{"text": "a"}, {"text": "b"}]}, "only one result can be without 'from'"),
    ({"results": [{"from": 5, "to": 9, "text": "a"}]}, "no 'to' .a roll's result happens once"),
    ({"results": [{"from": 5, "text": "a"}, {"from": 5, "text": "b"}]}, "two results are from 5"),
    ({"add": "The Lease"}, "'add' names no counter"),
    ({"results": [{"from": 5, "text": "a", "effects": [{"change": "The Lease", "by": 1}]}]},
     "no counter or plane 'The Lease' to change"),
])
def test_a_wrong_roll_is_refused(dcc_world, change, why):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    with pytest.raises(wr.RulesError, match=why):
        wr.define(ops, [BLEED, {**LEASE, **change}])


def test_the_brief_shows_a_roll_in_full(dcc_world, ops):
    from lib.session_manager import SessionManager
    brief = SessionManager(dcc_world).get_full_context()
    section = brief.split("--- YOUR WORLD'S RULES (follow exactly) ---", 1)[1]
    assert "The Lease (roll 1d20, held by the player): Leasing your mind costs something." in section
    assert "  With: ordinary night +0, deep lease -2, Mesh run -4" in section
    assert "  15+: Clean.\n  10+: +1 Bleed.\n  5+: +1 Bleed and a stranger's memory.\n" \
           "  below 5: +2 Bleed and a memory gone." in section
    assert 'Command: gm-rule.sh roll "The Lease" [--with "<amount>"]...' in section
    assert "Adds the holder's Respect." in section
    assert "The Lease" not in wr.summary(ops)                        # nothing kept


def test_the_command(dcc_world, ops):
    out = subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), "roll", "The Lease",
                          "--with", "deep lease"], capture_output=True, text=True,
                         env=dict(os.environ, GM_WORLD_STATE_BASE=dcc_world))
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("The Lease (Tandy): 1d20 ") and ", deep lease -2 → " in out.stdout
