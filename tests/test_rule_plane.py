"""The plane (lib/rule_plane.py): two values read together, with
results by region; a change moves one axis; an axis can have a rate."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager
from lib.json_ops import JsonOperations
from lib.time_manager import TimeManager

ROOT = Path(__file__).resolve().parent.parent

HUMANITY = {
    "name": "Humanity", "block": "plane", "held_by": "player",
    "summary": "Machine against what ties you to people.", "when": "Cyberware; time with friends.",
    "axes": {"Chrome": [0, 10], "Anchor": [0, 10]}, "start": {"Chrome": 0, "Anchor": 5},
    "rates": {"Anchor": {"by": 1, "every": "14d", "toward": 0}},
    "regions": [
        {"name": "Steady", "where": "Chrome <= Anchor", "text": "Themselves."},
        {"name": "Drifting", "where": "Chrome > Anchor and Chrome < Anchor + 4", "text": "Cold moments."},
        {"name": "Cyberpsychosis", "where": "chrome >= anchor + 4", "text": "May lash out.",
         "effects": [{"condition": "Unstable"}], "when_off": [{"condition": "Unstable", "add": False}],
         "gm": "Call for a Composure roll at each violent moment."}]}
ALIGNMENT = {
    "name": "Alignment", "block": "plane", "held_by": ["player", "npc"],
    "summary": "What deeds say.", "when": "A deed that keeps or breaks an oath.",
    "axes": {"Law": [-3, 3], "Good": [-3, 3]}, "start": {"Law": 0, "Good": 0},
    "regions": [{"name": "Paladin", "where": "Law >= 2 and Good >= 2", "text": "Blessed."},
                {"name": "Lawful", "where": "Law >= 2", "text": "Officials trust them."}]}
IMPLANT = {"name": "Implants", "block": "counter", "held_by": "player", "range": [0, 5],
           "summary": "Pieces of chrome.", "when": "Each one put in.",
           "results": [{"from": 1, "text": "Chromed.",
                        "effects": [{"change": "Humanity", "axis": "chrome", "by": 2}]}]}


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    wr.define(ops, [HUMANITY, ALIGNMENT, IMPLANT])
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops


def test_regions_come_on_and_go_off_as_an_axis_moves(ops):
    assert wr.entry(ops, wr.find_rule(ops, "Humanity"), "player")["on"] == ["Steady"]
    drift = wr.change(ops, "Humanity", by=7, axis="chrome")
    assert (drift["axis"], drift["before"], drift["after"]) == ("Chrome", 0, 7)
    assert drift["on"] == ["Drifting"] and drift["off"] == ["Steady"]
    psycho = wr.change(ops, "Humanity", by=2, axis="Chrome")
    assert psycho["on"] == ["Cyberpsychosis"] and psycho["character"] == ["condition Unstable added"]
    text = "\n".join(wr.change_lines(ops, psycho))
    assert text.startswith("Humanity (Tandy): Chrome 7 → 9 (now Chrome 9, Anchor 5)\n"
                           "  now in:     Cyberpsychosis: May lash out.")
    assert "    Do now: Call for a Composure roll" in text
    back = wr.change(ops, "Humanity", to=9, axis="Anchor")
    assert back["off"] == ["Cyberpsychosis"] and back["on"] == ["Steady"]
    assert back["character"] == ["condition Unstable removed"]


def test_regions_may_overlap(ops):
    wr.change(ops, "Alignment", "Carl", to=2, axis="Law")
    both = wr.change(ops, "Alignment", "Carl", to=3, axis="Good")
    assert both["on"] == ["Paladin"] and both["still"] == ["Lawful"]


def test_what_a_change_needs(ops):
    with pytest.raises(ValueError, match="name the axis to change, --axis Chrome or --axis Anchor"):
        wr.change(ops, "Humanity", by=1)
    with pytest.raises(ValueError, match="Chrome goes from 0 to 10; 11 is outside"):
        wr.change(ops, "Humanity", to=11, axis="Chrome")
    with pytest.raises(wr.RulesError, match="Implants has no axes"):
        wr.change(ops, "Implants", by=1, axis="Chrome")


def test_an_effect_moves_an_axis(ops):
    report = wr.change(ops, "Implants", by=1)
    nested = report["did"]["from 1"][0]["report"]
    assert (nested["axis"], nested["after"]) == ("Chrome", 2)
    assert "    → Humanity (Tandy): Chrome 0 → 2" in "\n".join(wr.change_lines(ops, report))


def test_an_axis_with_a_rate_moves_by_itself(dcc_world, ops):
    manager = TimeManager(dcc_world)
    manager.advance(28 * 24 * 60, through_all=True)
    assert [(c["axis"], c["before"], c["after"]) for c in manager.rule_changes] == [
        ("Anchor", 5, 4), ("Anchor", 4, 3)]                   # each 14 days, at its moment
    assert wr.entry(ops, wr.find_rule(ops, "Humanity"), "player")["axes"] == {"Chrome": 0, "Anchor": 3}


def test_a_consequence_waits_on_a_region(dcc_world, ops, capsys):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The ripperdoc refuses more work", "cyberpsychosis",
                             trigger_type="on_rule", match="humanity:cyberpsychosis")
    assert cm.add_consequence("x", "y", trigger_type="on_rule", match="Humanity:Saint") == ""
    assert "has no region 'Saint'" in capsys.readouterr().err
    assert wr.change(ops, "Humanity", to=8, axis="Chrome")["fired"] == []      # only Drifting
    assert [c["id"] for c in wr.change(ops, "Humanity", to=9, axis="Chrome")["fired"]] == [cid]


@pytest.mark.parametrize("change, why", [
    ({"axes": {"Chrome": [0, 10]}}, "'axes' are two"),
    ({"start": {"Chrome": 0}}, "'start' gives each axis a value"),
    ({"rates": {"Soul": {"by": 1, "every": "1d"}}}, "'rates' are per axis"),
    ({"rates": {"Anchor": {"by": 1}}}, "axis Anchor: 'rate' needs 'every'"),
    ({"regions": [{"name": "X", "where": "Soul > 2", "text": "x"}]}, "is no comparison of an axis"),
    ({"regions": [{"name": "X", "where": "Chrome > lots", "text": "x"}]}, "neither a number nor an axis"),
    ({"regions": [{"name": "X", "where": "Chrome > 2"}]}, "region 'X' needs a 'text'"),
    ({"regions": [{"name": "X", "where": "Chrome > 2", "text": "a"},
                  {"name": "x", "where": "Chrome > 3", "text": "b"}]}, "two regions are called 'x'"),
])
def test_a_wrong_plane_is_refused(dcc_world, change, why):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    with pytest.raises(wr.RulesError, match=why):
        wr.define(ops, [{**HUMANITY, **change}])


def test_an_effect_on_a_plane_names_its_axis(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    wrong = {**IMPLANT, "results": [{"from": 1, "text": "x",
                                     "effects": [{"change": "Humanity", "by": 1}]}]}
    with pytest.raises(wr.RulesError, match='Humanity is a plane: "axis" is one of Chrome, Anchor'):
        wr.define(ops, [HUMANITY, wrong])


def test_planes_in_the_brief_the_cards_the_summary_and_the_hud(dcc_world, ops):
    wr.change(ops, "Alignment", "Carl", to=2, axis="Law")
    text = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Humanity")))
    assert text.startswith("Humanity (plane: Chrome 0–10 × Anchor 0–10, held by the player)")
    assert "  Rate of Anchor: 1 every 14d toward 0, by itself as game time passes." in text
    assert "  Drifting (Chrome > Anchor and Chrome < Anchor + 4): Cold moments." in text
    assert 'Command: gm-rule.sh change "Humanity" --axis <Chrome|Anchor> +N|-N' in text
    assert "Now, Tandy: Chrome 0, Anchor 5 (Steady)" in text
    from lib.cards import Cards
    assert "  rule: Alignment: Law 2, Good 0 (plane): Lawful: Officials trust them." in \
        Cards(ops).npc_card("Carl")
    assert "Humanity: Steady" in wr.summary(ops)
    assert wr.check_values(ops, "player", {"Humanity": {"chrome": 3}}) == [("Humanity", {"Chrome": 3})]
    wr.change(ops, "Humanity", to=1, axis="Chrome")           # stored: the HUD reads its regions
    root = Path(dcc_world).parent / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "gm-statusline.sh", root / "tools")
    shutil.copytree(dcc_world, root / "world-state")
    hud = subprocess.run(["bash", str(root / "tools" / "gm-statusline.sh")], input="{}",
                         capture_output=True, text=True).stdout
    assert "Humanity: Steady" in re.sub(r"\x1b\[[0-9;]*m", "", hud)


def test_the_command(dcc_world, ops):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), *words],
                              capture_output=True, text=True, env=env)
    moved = run("change", "Humanity", "+3", "--axis", "Chrome")
    assert moved.returncode == 0 and moved.stdout.startswith("Humanity (Tandy): Chrome 0 → 3")
    assert run("set", "Alignment", "Carl", "-2", "--axis", "Good").returncode == 0
    assert wr.load_state(ops)["npc:Carl"]["Alignment"]["axes"] == {"Law": 0, "Good": -2}
    refused = run("change", "Humanity", "+1")
    assert refused.returncode == 1 and "--axis Chrome or --axis Anchor" in refused.stderr
