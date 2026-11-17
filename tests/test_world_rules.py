"""The world's rules (lib/world_rules.py, 2026-11-17): rules defined once in
ruleset.json, values per holder in rule-state.json. Step 1: counters, holders,
known and hidden, the command."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import world_rules as wr
from lib.json_ops import JsonOperations

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = "dungeon-crawler-carl"

BLEED = {"name": "Bleed", "block": "counter", "held_by": "player", "range": [0, 6],
         "summary": "How much of other people's work has leaked into your head.",
         "when": "After every Lease roll.",
         "results": [{"from": 2, "text": "Intrusions."}, {"from": 4, "text": "Lost time."},
                     {"from": 6, "text": "Overwritten."}]}
PATIENCE = {"name": "Patience", "block": "counter", "held_by": "faction", "known": False,
            "range": [0, 5], "start": 5, "summary": "What a faction will still put up with.",
            "when": "-1 for each slight.",
            "results": [{"from": 0, "to": 1, "text": "Warnings."},
                        {"from": 0, "to": 0, "text": "They act."}]}
HEAT = {"name": "Heat", "block": "counter", "held_by": ["location", "npc"], "range": [0, 10],
        "summary": "Attention from the law.", "when": "+2 for a fight there.", "results": []}
SEA = {"name": "Sea level", "block": "counter", "held_by": "world", "range": [0, 10],
       "start": 2, "summary": "How far the sea has risen.", "when": "Storms.",
       "results": [{"from": 3, "text": "The docks flood."}]}


def _ops(dcc_world):
    return JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))


@pytest.fixture
def ops(dcc_world):
    ops = _ops(dcc_world)
    wr.define(ops, [BLEED, PATIENCE, HEAT, SEA])
    return ops


# ---------- defining ----------

def test_rules_are_defined_once_and_checked(ops):
    assert [r["name"] for r in wr.rules(ops)] == ["Bleed", "Patience", "Heat", "Sea level"]
    bleed = wr.find_rule(ops, " bleed ")
    assert bleed["held_by"] == ["player"] and bleed["start"] == 0 and bleed["known"] is True
    ruleset = ops.load_json("ruleset.json")
    assert ruleset["name"] == "Dungeon Crawler Carl"                    # what was there stays
    with pytest.raises(wr.RulesError, match="did you mean: Bleed"):
        wr.find_rule(ops, "Bleeed")


@pytest.mark.parametrize("change, why", [
    ({"name": "A: b"}, "short key"),
    ({"name": "One two three four"}, "short key"),
    ({"block": "plane"}, "isn't built yet .* step 7"),
    ({"block": "meter"}, "'block' must be one of"),
    ({"held_by": "god"}, "'held_by' must be one of"),
    ({"range": [6, 0]}, "'range' must be"),
    ({"start": 9}, "'start' must be a whole number from 0 to 6"),
    ({"summary": ""}, "'summary' must be a sentence"),
    ({"when": None}, "'when' must be a sentence"),
    ({"rate": {"by": 1}}, "'rate' isn't built yet .* step 5"),
    ({"colour": "red"}, "unknown field 'colour'; a counter has"),
    ({"results": [{"from": 9, "text": "x"}]}, "result 1 needs 'from'"),
    ({"results": [{"from": 2, "to": 1, "text": "x"}]}, "'to' must be"),
    ({"results": [{"from": 2}]}, "needs a 'text'"),
    ({"results": [{"from": 2, "text": "x", "off_at": 0}]}, "'off_at' in result 1 isn't built yet"),
    ({"results": [{"from": 2, "text": "x"}, {"from": 2, "text": "y"}]}, "two results are from 2"),
])
def test_a_wrong_rule_is_refused_with_the_reason(dcc_world, change, why):
    with pytest.raises(wr.RulesError, match=why):
        wr.define(_ops(dcc_world), [{**BLEED, **change}])


def test_define_is_all_or_nothing(dcc_world):
    ops = _ops(dcc_world)
    with pytest.raises(wr.RulesError, match="Nothing was saved"):
        wr.define(ops, [BLEED, {**SEA, "start": 99}])
    assert wr.rules(ops) == []
    with pytest.raises(wr.RulesError, match="given twice"):
        wr.define(ops, [BLEED, {**BLEED, "name": "BLEED"}])


def test_a_replaced_rule_keeps_its_values(ops):
    wr.change(ops, "Bleed", by=5)
    assert wr.define(ops, [{**BLEED, "name": "bleed", "range": [0, 3],
                                    "results": [{"from": 2, "text": "Intrusions."}]}]) == [("Bleed", "replaced")]
    stored = wr.load_state(ops)["player"]["Bleed"]
    assert stored["value"] == 3 and stored["on"] == ["from 2"]          # into the new range
    assert wr.find_rule(ops, "Bleed")["range"] == [0, 3]


def test_remove_takes_the_values_with_it(ops):
    wr.change(ops, "Patience", "faction:crawlers", by=-1)
    assert wr.remove(ops, "patience") == 1
    assert "faction:crawlers" not in wr.load_state(ops)
    assert [r["name"] for r in wr.rules(ops)] == ["Bleed", "Heat", "Sea level"]


def test_plain_rule_lines(ops):
    assert wr.set_plain(ops, ["Credits are zeds.", "  ", "A meal  costs 1."]) == [
        "Credits are zeds.", "A meal costs 1."]
    assert wr.plain_rules(ops) == ["Credits are zeds.", "A meal costs 1."]


# ---------- holders ----------

def test_holders(ops):
    bleed, patience, heat, sea = (wr.find_rule(ops, n) for n in ("Bleed", "Patience", "Heat",
                                                                 "Sea level"))
    assert wr.resolve_holder(ops, bleed) == "player"                   # the only holder
    assert wr.resolve_holder(ops, bleed, "Tandy") == "player"          # the character's name
    assert wr.resolve_holder(ops, sea) == "world"
    assert wr.resolve_holder(ops, patience, "faction:system") == "faction:system"
    assert wr.resolve_holder(ops, patience, "The Showrunners") == "faction:showrunners"
    assert wr.resolve_holder(ops, heat, "Carl") == "npc:Carl"
    assert wr.resolve_holder(ops, heat, "Bone Garden") == "location:Bone Garden"
    for rule, raw, why in ((patience, None, "Whose Patience"),
                           (patience, "Carl", "held by factions; 'Carl' is npc:Carl"),
                           (patience, "faction:elves", "No faction 'elves'.*crawlers"),
                           (bleed, "Carl", "held by the player"),
                           (heat, "Nobody Atall", "Nothing called")):
        with pytest.raises(wr.RulesError, match=why):
            wr.resolve_holder(ops, rule, raw)
    assert wr.holder_name(ops, "faction:system") == "The System / Borant Corp"
    assert wr.holder_name(ops, "player") == "Tandy"


# ---------- values ----------

def test_a_counter_turns_its_results_on_and_off(ops):
    assert wr.entry(ops, wr.find_rule(ops, "Sea level"), "world")["value"] == 2   # its start
    up = wr.change(ops, "Bleed", by=3)
    assert (up["before"], up["after"], up["on"], up["off"], up["still"]) == (
        0, 3, ["from 2"], [], [])
    top = wr.change(ops, "Bleed", by=9)
    assert top["after"] == 6 and top["stopped"] and top["on"] == ["from 4", "from 6"]
    assert top["still"] == ["from 2"]                                   # cumulative
    down = wr.change(ops, "Bleed", to=1)
    assert down["off"] == ["from 2", "from 4", "from 6"] and not down["stopped"]
    with pytest.raises(wr.RulesError, match="goes from 0 to 6; 9 is outside"):
        wr.change(ops, "Bleed", to=9)
    lines = "\n".join(wr.change_lines(ops, top))
    assert "Bleed (Tandy): 3 → 6 (its highest)" in lines
    assert "now on:   from 4: Lost time." in lines and "still on: from 2: Intrusions." in lines
    log = (Path(ops.world_state_dir) / "rules.log").read_text()
    assert log.count("\tplayer\tBleed: ") == 3 and "3 -> 6\tby command" in log


def test_a_result_with_a_to_holds_only_in_its_range(ops):
    first = wr.change(ops, "Patience", "faction:crawlers", by=-4)
    assert first["on"] == ["from 0 to 1"] and first["known"] is False
    second = wr.change(ops, "Patience", "faction:crawlers", by=-1)
    assert second["on"] == ["at 0"] and second["still"] == ["from 0 to 1"]
    back = wr.change(ops, "Patience", "faction:crawlers", by=2)
    assert set(back["off"]) == {"at 0", "from 0 to 1"}
    assert wr.entry(ops, wr.find_rule(ops, "Patience"), "faction:system")["value"] == 5


def test_hidden_values_are_marked_and_can_be_revealed_per_holder(ops):
    hidden = wr.change(ops, "Patience", "faction:crawlers", by=-1)
    assert wr.HIDDEN in wr.change_lines(ops, hidden)[0]
    wr.set_known(ops, "Patience", "faction:crawlers", known=True)
    assert wr.change(ops, "Patience", "faction:crawlers", by=-1)["known"] is True
    assert wr.change(ops, "Patience", "faction:system", by=-1)["known"] is False  # only that one
    wr.set_known(ops, "Bleed", known=False)
    text = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Bleed")))
    assert "Now, Tandy: 0 (no result) " + wr.HIDDEN in text


def test_a_rule_in_full(ops):
    wr.change(ops, "Heat", "Carl", by=2)
    text = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Heat")))
    assert text.startswith("Heat (counter 0–10, held by places, NPCs): Attention from the law.")
    assert "When: +2 for a fight there." in text and "Now, Carl: 2 (no result)" in text
    sea = "\n".join(wr.rule_lines(ops, wr.find_rule(ops, "Sea level")))
    assert "Now, the world: 2 (no result)" in sea and "from 3: The docks flood." in sea


# ---------- the command ----------

def test_the_command(dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words, given=None):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-rule.sh"), *words],
                              capture_output=True, text=True, env=env, input=given)

    done = run("define", given=json.dumps([BLEED, PATIENCE]))
    assert done.returncode == 0 and "[SUCCESS] Bleed: added" in done.stdout, done.stderr
    up = run("change", "Bleed", "+2")
    assert up.returncode == 0 and "Bleed (Tandy): 0 → 2" in up.stdout
    assert run("change", "Bleed", "-1").returncode == 0                # a negative amount
    assert "from 2" in run("set", "Bleed", "5").stdout
    bare = run("change", "Bleed", "3")
    assert bare.returncode == 1 and "[ERROR] A change is +N or -N" in bare.stderr
    acted = run("change", "Patience", "The Crawlers", "-5", "--json")
    data = json.loads(acted.stdout)
    assert data["ok"] and data["data"]["holder"] == "faction:crawlers" and data["data"]["after"] == 0
    assert "Now, The Crawlers: 0" in run("show", "Patience").stdout
    assert run("reveal", "Patience", "faction:crawlers").returncode == 0
    plain = run("plain", given="Credits are gold.\n\nA room costs 2.\n")
    assert plain.returncode == 0 and "2 plain rule lines" in plain.stdout
    listed = run("list").stdout
    assert listed.startswith("- Credits are gold.\n- A room costs 2.\nBleed (counter")
    wrong = run("define", given="[{\"name\": \"X\", \"block\": \"bag\"}]")
    assert wrong.returncode == 1 and "isn't built yet" in wrong.stderr
    assert run("remove", "Patience").returncode == 0
    state = json.loads((Path(dcc_world) / "campaigns" / CAMPAIGN / "rule-state.json").read_text())
    assert state == {"player": {"Bleed": {"value": 5, "on": ["from 2", "from 4"]}}}
