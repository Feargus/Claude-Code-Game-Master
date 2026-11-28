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
from lib.factions import FactionError, FactionManager, known
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
    ids = ["crawlers", "system", "showrunners", "npcs", "meridian-group"]
    # 3 of each faction's own and 1 job token; the people a faction's share; 2 blanks each
    assert rule["tokens"] == {**dict.fromkeys(ids, 3), **{f"job:{f}": 1 for f in ids},
                              "people": 4, "blank": 12, "joker": 1}
    assert rule["draw_every"] == "660m"                   # 6 h + 25 h / 5 = 11 h
    assert rule["top_up"] == {"below": 24, "add": {**dict.fromkeys(ids, 1), "people": 1, "blank": 3},
                              "if_none": ["joker", *(f"job:{f}" for f in ids)]}
    wr.check_rule({k: v for k, v in rule.items() if k != "repo"})        # a valid bag
    FactionManager(ops).create("Grey Hands", "Pickpockets.", fid="grey")
    rule = wr.find_rule(ops, fr.BAG)
    assert rule["tokens"]["grey"] == 3 and rule["tokens"]["job:grey"] == 1
    assert rule["draw_every"] == "610m"                   # 6 h + 25 h / 6


def test_no_faction_may_take_a_token_kinds_id(ops):
    for fid in ("joker", "people"):
        with pytest.raises(FactionError, match="kind of token in the faction bag"):
            FactionManager(ops).create("The Joker", "A clown gang.", fid=fid)


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
    first = next(o["kind"] for o in owed if o["kind"] in known(ops))
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
    assert sum(tokens.values()) >= 23                      # topped up below 24, never empty
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
    assert after["grey"] == 3 and after["job:grey"] == 1 and after["blank"] == before["blank"] + 2
    assert "grey gets its share of the bag" in m.notes[-1]


def test_each_turn_drawn_is_a_do_line_with_its_command(ops):
    from datetime import datetime

    from lib.time_stops import brief, owed_lines
    at = datetime(2187, 10, 26, 5, 40)
    report = {"rule": fr.BAG, "holder": "world", "known": False,
              "draws": [{"kind": "blank"}, {"kind": "meridian-group", "owed": True}]}
    assert brief(ops, report) == ""                        # not in the routine timeline
    assert owed_lines(ops, [{"at": at, "rules": [report]}]) == [
        "[DO] Meridian Group owes a turn (drawn Fri 26 Oct 05:40); narrate what the character "
        "would notice of it: bash tools/gm-faction.sh turn --only meridian-group"]
    blanks = {**report, "draws": [{"kind": "blank"}]}
    assert owed_lines(ops, [{"at": at, "rules": [blanks]}]) == []
    jobs = {**report, "draws": [{"kind": "job:meridian-group", "owed": True},
                                {"kind": "people", "owed": True}]}
    lines = owed_lines(ops, [{"at": at, "rules": [jobs]}])
    assert lines[0].startswith("[DO] Meridian Group has a job for the character")
    assert ("(drawn Fri 26 Oct 05:40): when a moment fits (in person, by message or by call), "
            "offer them a complex action") in lines[0]
    assert "notice" not in lines[0] and "bash tools/gm-faction.sh job offer meridian-group" in lines[0]
    assert lines[1].endswith(": bash tools/gm-faction.sh ask")


def _owe(ops, *kinds):
    """Faction turns owed, as the bag leaves them: drawn at 05:40."""
    state = ops.load_json("rule-state.json") or {}
    bag = state.setdefault("world", {}).setdefault(fr.BAG, {})
    bag["owed"] = [{"kind": k, "at": "2187-10-26T05:40"} for k in kinds]
    ops.save_json("rule-state.json", state)
    return fr.owed(ops)


def test_on_a_journey_a_job_or_an_ask_waits_for_the_arrival(ops):
    from datetime import datetime

    from lib.time_stops import owed_lines
    report = {"rule": fr.BAG, "holder": "world", "known": False,
              "draws": [{"kind": "job:meridian-group", "owed": True}, {"kind": "people", "owed": True},
                        {"kind": "meridian-group", "owed": True}]}
    lines = owed_lines(ops, [{"at": datetime(2187, 10, 26, 5, 40), "rules": [report]}], journey=True)
    assert len(lines) == 1 and lines[0].startswith("[DO] Meridian Group owes a turn")


def test_a_turn_still_owed_comes_back_a_job_at_a_move(ops):
    """In the What Remains playtest a job passed over once was forgotten for the rest
    of the session. A faction's own turn comes back each time time passes; a job or
    an ask at a move, when a new scene may fit it."""
    from lib.time_stops import still_owed_lines
    before = _owe(ops, "meridian-group", "job:meridian-group")
    assert still_owed_lines(ops, before) == [
        "[DO] Still owed: Meridian Group owes a turn (drawn Fri 26 Oct 05:40); narrate what "
        "the character would notice of it: bash tools/gm-faction.sh turn --only meridian-group"]
    fr.settle(ops, "meridian-group")                           # played: it doesn't come back
    assert still_owed_lines(ops, before) == []


def test_the_owed_command(ops, dcc_world):
    import os
    import subprocess
    env = dict(os.environ, GM_WORLD_STATE_BASE=str(dcc_world))
    tool = Path(__file__).resolve().parent.parent / "tools" / "gm-faction.sh"

    def run(*words):
        return subprocess.run(["bash", str(tool), *words], capture_output=True, text=True,
                              env=env).stdout
    assert run("owed") == "No faction turn is owed.\n"
    assert run("owed", "--arrival") == ""                      # a move says nothing then
    _owe(ops, "meridian-group", "job:meridian-group")
    assert [ln[:40] for ln in run("owed").splitlines()] == [
        "[DO] Meridian Group owes a turn (drawn F", "[DO] Meridian Group has a job for the ch"]
    assert run("owed", "--arrival").startswith("[DO] Meridian Group has a job for the character")
