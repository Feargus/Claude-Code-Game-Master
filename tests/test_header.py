"""The header (lib/header.py, gm-session.sh header): one line printed from the records,
decided 2026-11-21. Always the place and the time; the date and credits when they
changed since it was last shown (or --full); the worst wound still healing; a
level-up due."""

from pathlib import Path

from lib import header
from lib.json_ops import JsonOperations

CAMPAIGN = "dungeon-crawler-carl"


def _ops(dcc_world, xp=0):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    overview["player_position"]["current_location"] = "Bleach Alley"
    ops.save_json("campaign-overview.json", overview)
    sheet = ops.load_json("character.json")
    sheet["progress"] = {"level": 0, "xp": xp}
    sheet["possessions"]["credits"] = 28
    ops.save_json("character.json", sheet)
    return ops


def _set(ops, name, change):
    data = ops.load_json(name)
    change(data)
    ops.save_json(name, data)


def test_only_what_changed_besides_place_and_time(dcc_world):
    ops = _ops(dcc_world)
    assert header.line(ops, full=True) == "Bleach Alley · Friday, 26 October 2187 · 04:30 · 28 credits"
    assert header.line(ops) == "Bleach Alley · 04:30"
    _set(ops, "character.json", lambda s: s["possessions"].update(credits=3))
    _set(ops, "campaign-overview.json", lambda o: o.update(game_time="2187-10-27T09:15"))
    assert header.line(ops) == "Bleach Alley · Saturday, 27 October 2187 · 09:15 · 3 credits"
    assert header.line(ops) == "Bleach Alley · 09:15"


def test_the_worst_wound_and_a_level_up(dcc_world):
    ops = _ops(dcc_world, xp=150)
    header.line(ops, full=True)

    def hurt(sheet):
        zones = sheet.setdefault("body", {}).setdefault("zones", {})
        zones["left_arm"] = {"wounds": 1}
        zones["chest"] = {"wounds": 2}
        zones["right_leg"] = {"wounds": 2}
        zones["left_leg"] = {"wounds": 4}              # destroyed: on the sheet, not here
    _set(ops, "character.json", hurt)
    assert header.line(ops) == "Bleach Alley · 04:30 · chest, right leg injured · level-up due"


def test_amounts_are_in_the_worlds_money(dcc_world, capsys):
    """The bible's `currency` (plural) names the money wherever an amount is shown;
    without it, credits. The data and the commands stay `credits`."""
    from lib.player_manager import PlayerManager
    from lib.world_bible import currency, validate_bible
    ops = _ops(dcc_world)
    assert currency(ops) == "credits"
    _set(ops, "world-bible.json", lambda b: b.update(currency="tallies"))
    assert currency(ops) == "tallies"
    assert header.line(ops, full=True).endswith(" · 28 tallies")
    PlayerManager(dcc_world).modify_credits(9)
    out = capsys.readouterr().out
    assert out == "[SUCCESS] 37 tallies now\n"
    assert ops.load_json("character.json")["possessions"]["credits"] == 37
    bible = ops.load_json("world-bible.json")
    assert validate_bible({**bible, "currency": " "})[1][-1].startswith("currency is the word")
