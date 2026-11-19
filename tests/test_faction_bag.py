"""The faction bag (lib/faction_rules.py, "Faction turns"; the bag's top_up and owed,
lib/rule_bag.py): drawn as game time passes; a drawn faction owes a turn, played at
the next pause with gm-faction.sh turn --only."""

import random
from pathlib import Path

import pytest

from lib import faction_rules as fr
from lib import faction_turns as ft
from lib import rule_bag
from lib import world_rules as wr
from lib.factions import FactionError, FactionManager
from lib.json_ops import JsonOperations

CAMPAIGN = "dungeon-crawler-carl"


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    FactionManager(ops).create("Meridian Group", "A security firm.", aliases=["Meridian"])
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops                                            # 5 factions: the bible's 4 + Meridian


def _stored(ops):
    return wr.entry(ops, wr.find_rule(ops, fr.BAG), "world")


def test_the_bag_follows_the_factions(ops):
    rule = wr.find_rule(ops, fr.BAG)
    assert rule["tokens"] == {"crawlers": 4, "system": 4, "showrunners": 4, "npcs": 4,
                              "meridian-group": 4, "blank": 10, "joker": 1}
    assert rule["draw_every"] == "660m"                   # 6 h + 25 h / 5 = 11 h
    assert rule["top_up"] == {"below": 20, "add": {"crawlers": 1, "system": 1, "showrunners": 1,
                                                    "npcs": 1, "meridian-group": 1, "blank": 2},
                              "if_none": ["joker"]}
    wr.check_rule({k: v for k, v in rule.items() if k != "repo"})        # a valid bag
    FactionManager(ops).create("Grey Hands", "Pickpockets.", fid="grey")
    rule = wr.find_rule(ops, fr.BAG)
    assert rule["tokens"]["grey"] == 4 and rule["draw_every"] == "610m"  # 6 h + 25 h / 6


def test_no_faction_may_take_a_token_kinds_id(ops):
    with pytest.raises(FactionError, match="kind of token in the faction bag"):
        FactionManager(ops).create("The Joker", "A clown gang.", fid="joker")


def test_top_up_counts_what_is_in_the_bag():
    rule = {"top_up": {"below": 5, "add": {"a": 1, "blank": 1}, "if_none": ["joker"]}}
    tokens = {"a": 2, "blank": 2, "joker": 0}
    assert rule_bag.top_up(rule, tokens) == {"a": 1, "blank": 1, "joker": 1}
    assert tokens == {"a": 3, "blank": 3, "joker": 1}
    assert rule_bag.top_up(rule, tokens) == {}             # 7 is not fewer than 5


def test_a_drawn_faction_owes_a_turn_and_playing_it_settles_it(ops):
    wr.find_rule(ops, fr.BAG)
    rng = random.Random(4)
    report = rule_bag.draw(ops, fr.BAG, "world", count=12, rng=rng)
    owed = fr.owed(ops)
    kinds = [d["kind"] for d in report["draws"]]
    assert [o["kind"] for o in owed] == [k for k in kinds if k != "blank"]
    assert all(o["at"] == "2187-10-26T04:30" for o in owed)
    first = next(o["kind"] for o in owed if o["kind"] != "joker")
    lines = "\n".join(fr.owed_lines(ops))
    assert "FACTION TURNS OWED" in lines and f"turn --only {first}" in lines
    done = ft.run(ops, [{"faction": first, "action": "build", "power": "Covert"}],
                  random.Random(1), only=first)
    assert done[-1].startswith("(This was the turn owed since 2187-10-26 04:30: give its facts")
    assert '--when "2187-10-26 04:30"' in done[-1]
    assert len(fr.owed(ops)) == len(owed) - 1


def test_the_bag_refills_before_it_runs_low(ops):
    rule_bag.draw(ops, fr.BAG, "world", count=40, rng=random.Random(2))
    tokens = _stored(ops)["tokens"]
    assert sum(tokens.values()) >= 19                      # topped up below 20, never empty
    assert tokens["joker"] <= 1


def test_time_draws_the_bag_without_stopping(ops, dcc_world):
    from lib.time_manager import TimeManager
    manager = TimeManager(dcc_world)
    manager.advance(3 * 24 * 60, through_all=True)         # three days: 6 draws at 11 h
    assert len(_stored(ops)["drawn"]) == 6
    assert not any(s for m in manager.moments for s in m["stops"]
                   if s[0] == "rule" and s[1][0] == fr.BAG)


def test_the_owed_turns_are_in_the_brief(ops, dcc_world):
    from lib.session_manager import SessionManager
    rule_bag.draw(ops, fr.BAG, "world", count=6, rng=random.Random(4))
    brief = SessionManager(dcc_world).get_full_context()
    if fr.owed(ops):
        assert "FACTION TURNS OWED" in brief
    assert "Faction turns (bag" not in brief               # the bag itself is the repo's


def test_a_new_faction_gets_its_full_share_at_once(ops):
    rule_bag.draw(ops, fr.BAG, "world", count=3, rng=random.Random(2))
    before = dict(_stored(ops)["tokens"])
    m = FactionManager(ops)
    m.create("Grey Hands", "Pickpockets.", fid="grey")
    after = _stored(ops)["tokens"]
    assert after["grey"] == 4 and after["blank"] == before["blank"] + 2
    assert "grey gets its share of the bag" in m.notes[-1]


def test_the_timeline_names_who_owes_a_turn_and_leaves_out_blanks(ops):
    from lib.time_stops import brief
    report = {"rule": fr.BAG, "holder": "world", "known": False,
              "draws": [{"kind": "blank"}, {"kind": "meridian-group", "owed": True}]}
    assert brief(ops, report) == "Faction turns: Meridian Group owes a turn"
    assert brief(ops, {**report, "draws": [{"kind": "blank"}]}) == ""
