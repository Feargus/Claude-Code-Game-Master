"""The repo's faction rules (lib/faction_rules.py): four powers held by factions and
a Relation held by pairs of factions, the same in every campaign with factions."""

from pathlib import Path

import pytest

from lib import faction_rules as fr
from lib import rule_time
from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager
from lib.factions import FactionManager
from lib.json_ops import JsonOperations

CAMPAIGN = "dungeon-crawler-carl"


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    FactionManager(ops).create("Meridian Group", "A security firm.", aliases=["Meridian"])
    return ops                                    # the bible's four are copied in too


def test_they_come_with_factions(dcc_world, ops):
    names = [r["name"] for r in wr.rules(ops)]
    assert names[-6:] == ["Military", "Economic", "Political", "Covert", "Relation", "Faction turns"]
    for rule in fr.built_ins(ops):                # each a valid rule
        wr.check_rule({k: v for k, v in rule.items() if k != "repo"})
    other = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN / "nowhere"))
    assert fr.built_ins(other) == []              # no factions.json: none


def test_they_cant_be_defined_or_removed(ops):
    with pytest.raises(wr.RulesError, match="the repo's faction rules"):
        wr.define(ops, [{"name": "Military", "block": "counter", "held_by": "faction",
                         "range": [0, 10], "start": 0, "summary": "x", "when": "y"}])
    with pytest.raises(wr.RulesError, match="can't be removed"):
        wr.remove(ops, "Relation")


def test_a_power_has_a_value_and_its_own_resting_point(ops):
    assert fr.power(ops, "meridian-group") == {"Military": 3, "Economic": 3, "Political": 3, "Covert": 3}
    wr.change(ops, "Military", "Meridian", by=4)
    _, rate = rule_time.set_rate(ops, "Military", "Meridian", by=1, toward=8)
    assert rate == {"by": 1, "every": "28d", "toward": 8}
    assert fr.power(ops, "meridian-group")["Military"] == 7


@pytest.mark.parametrize("raw", ["pair:meridian-group+system", "system+meridian-group",
                                 "Meridian + The System / Borant Corp", "pair:faction:system+Meridian"])
def test_a_pair_is_the_same_whichever_comes_first(ops, raw):
    rule = wr.find_rule(ops, "Relation")
    assert wr.resolve_holder(ops, rule, raw) == "pair:meridian-group+system"


@pytest.mark.parametrize("raw, words", [
    ("pair:system+system", "two factions"),
    ("pair:system+nobody", "No faction 'nobody'"),
    ("pair:system", "pair:<one>\\+<other>"),
    ("Meridian", "held by pairs of factions"),
])
def test_a_wrong_pair_is_refused(ops, raw, words):
    with pytest.raises(wr.RulesError, match=words):
        wr.resolve_holder(ops, wr.find_rule(ops, "Relation"), raw)


def test_a_relation_is_named_changed_and_waited_on(ops, dcc_world):
    assert wr.holder_name(ops, "pair:meridian-group+system") == "Meridian Group and The System / Borant Corp"
    cid = ConsequenceManager(dcc_world).add_consequence(
        "Open war on Floor 1.", "y", trigger_type="on_rule", match="Relation:-3@system+Meridian")
    report = wr.change(ops, "Relation", "Meridian+system", by=-3)
    assert report["after"] == -3
    assert cid in [c["id"] for c in report.get("fired") or []]
    assert fr.relations(ops, "system") == {"meridian-group": -3}


def test_a_consequence_can_change_a_relation(ops, dcc_world):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("A truce is signed.", "y", trigger_type="on_fact", match="x",
                             effects=[{"type": "rule", "rate_of": "Relation",
                                       "of": "system+Meridian", "toward": 2}])
    cm.fire(cid)
    stored = wr.entry(ops, wr.find_rule(ops, "Relation"), "pair:meridian-group+system")
    assert stored["rate"]["toward"] == 2                    # it drifts toward the new point
    cid = cm.add_consequence("Steps.", "y", trigger_type="on_fact", match="x",
                             effects=[{"type": "rule", "rate_of": "Relation",
                                       "of": "system+Meridian", "by": 1}])
    fired = cm.fire(cid)
    assert "only its point changes" in " ".join(fired.get("effects_done", []))


def test_power_and_relations_are_on_the_faction_card_not_in_the_rules(ops, dcc_world):
    from lib.cards import Cards
    from lib.session_manager import SessionManager
    m = FactionManager(ops)
    m.set_presence(ops.load_json("campaign-overview.json")["player_position"]["current_location"],
                   ["Meridian=3"])
    wr.change(ops, "Relation", "Meridian+system", by=-2)
    scene = "\n".join(Cards(ops).scene())
    assert "power (0–10, hidden from the player): Military 3, Economic 3, Political 3, Covert 3" in scene
    assert "relations (−5 war … +5 allies; why, as they see it): The System / Borant Corp -2" in scene
    assert "Power (0–10" in m.show("Meridian")
    brief = SessionManager(dcc_world).get_full_context()
    assert "Military (counter" not in brief and "Relation (counter" not in brief


def test_a_tie_says_why(ops):
    from lib.factions import FactionError, load
    m = FactionManager(ops)
    fid, other, before = m.tie("Meridian", "system", "rents it guards, and resents the fee")
    assert (fid, other, before) == ("meridian-group", "system", "")
    assert load(ops)["meridian-group"]["ties"] == {"system": "rents it guards, and resents the fee"}
    lines = "\n".join(fr.card_lines(ops, "meridian-group"))
    assert "The System / Borant Corp not set (rents it guards, and resents the fee)" in lines
    assert fr.ties_without_relation(ops) == [("meridian-group", "system")]
    wr.change(ops, "Relation", "meridian-group+system", to=0)        # 0, chosen: not "not set"
    assert "The System / Borant Corp +0 (rents" in "\n".join(fr.card_lines(ops, "meridian-group"))
    assert fr.ties_without_relation(ops) == []
    assert m.tie("Meridian", "system")[2] == "rents it guards, and resents the fee"   # removed
    assert "ties" not in load(ops)["meridian-group"]
    with pytest.raises(FactionError, match="between two factions"):
        m.tie("Meridian", "Meridian", "x")
    with pytest.raises(FactionError, match="No faction"):
        m.tie("Meridian", "Nobody", "x")


def test_a_relations_rate_says_it_drifts_and_takes_only_a_point(ops):
    """It printed "held at its value (0 every 28d, toward 3)" while it drifted
    (the Long Hull playtest); and --by or --every would have changed nothing."""
    old, new = rule_time.set_rate(ops, "Relation", "meridian-group+system", toward=3)
    assert rule_time.describe(new, "Relation") == (
        "drifts toward +3 by itself (the distance halves in about 21 days)")
    assert "held at its value" not in rule_time.describe(new, "Relation")
    with pytest.raises(wr.RulesError, match="only its point changes"):
        rule_time.set_rate(ops, "Relation", "meridian-group+system", by=1)
    assert rule_time.describe({"by": 0, "every": "28d", "toward": 3}).startswith("held")  # a power
