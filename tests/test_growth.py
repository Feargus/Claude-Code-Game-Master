"""Character growth (growth.py): skills learn from use, XP, the log, when a level
is due. The numbers are the user's (2026-11-11): close results teach (±2: 3,
±5: 2, ±10: 1), skill N costs 3 × N learnings and grants 10 × N XP, level N
needs 100 × N² XP."""

import json
import random

import pytest

from lib import growth


def test_the_numbers():
    assert [growth.learnings(q) for q in (0, -2, 3, -5, 6, 10, -11, 30)] == [3, 3, 2, 2, 1, 1, 0, 0]
    assert [growth.xp_for_level(n) for n in range(5)] == [0, 100, 400, 900, 1600]
    assert [growth.level_for_xp(x) for x in (0, 99, 100, 399, 400, 2500)] == [0, 0, 1, 1, 2, 5]
    assert growth.fight_xp(6) == 360 and growth.fight_xp(2) == 40
    assert growth.achievement_xp({"progress": {"level": 1}}, "medium") == 150  # half of 100 → 400
    assert growth.achievement_xp({"progress": {"level": 0}}, "large") == 100
    with pytest.raises(ValueError, match="small, medium, large"):
        growth.achievement_xp({}, "huge")


def test_learning_raises_skills_and_books_xp(tmp_path):
    character = {"identity": {"name": "Lullaby"}, "progress": {"level": 0},
                 "stats": {"skills": {"Brawling": 2}}}
    # Brawling 3 costs 9 learnings: three close results.
    assert growth.learn(tmp_path, character, "brawling", 1) == []
    assert growth.learn(tmp_path, character, "Brawling", -2) == []
    gains = growth.learn(tmp_path, character, "Brawling", 0)
    assert gains == [{"skill": "Brawling", "value": 3, "xp": 30}]
    assert character["stats"]["skills"]["Brawling"] == 3
    assert character["progress"]["practice"]["Brawling"] == 0
    assert character["progress"]["xp"] == 30 and growth.next_level_xp(character) == 100
    # Untrained: the first point costs 3, and the canon spelling is used.
    assert growth.learn(tmp_path, character, "long guns", 2)[0] == {
        "skill": "Long guns", "value": 1, "xp": 10}
    assert growth.learn(tmp_path, character, "Tech", 25) == []          # a blowout teaches nothing
    assert "Tech" not in character["progress"]["practice"]
    log = (tmp_path / growth.LOG_FILE).read_text()
    assert "+30 XP  skill: Brawling rose to 3 through use" in log
    assert "total 40 · level 0" in log


def test_xp_makes_growth_due_but_does_not_level(tmp_path):
    character = {"identity": {"name": "Lullaby"}, "progress": {"level": 0, "xp": 50}}
    result = growth.add_xp(tmp_path, character, 400, "fight", "defeated Mastiff (6 wounds)")
    assert result == {"xp": 400, "total": 450, "due": 2, "newly_due": True}
    assert character["progress"]["level"] == 0 and growth.growth_due(character) == 2
    entry = (tmp_path / growth.LOG_FILE).read_text()
    assert "+400 XP  fight: defeated Mastiff (6 wounds)\ntotal 450 · level 0 · growth due: 2 levels" in entry
