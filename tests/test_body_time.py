"""Wounds and luck that come back as time passes (lib/body_time.py), and the care that
speeds it up (lib/body.py treat): half-lives of 2, 4 and 8 days for
a bruise, an injury and a critical wound, luck 1 week a point; lying still, first aid
and a doctor's treatment each count the time double; a critical wound needs a doctor
or a medpack."""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib import body
from lib import body_time as bt
from lib.json_ops import JsonOperations

CAMPAIGN = "dungeon-crawler-carl"
T0 = datetime(2187, 10, 26, 4, 30)


def _sheet(**wounds):
    sheet = {"body": {"zones": {}}, "stats": {"luck": {"current": 7, "max": 7}},
             "items": {"gear": ["medpack", {"name": "knife"}], "inventory": []}}
    for zone, n in wounds.items():
        body.body(sheet)[zone]["wounds"] = n
    return sheet


def _share_healed(wounds, days, care=(), n=4000):
    rng, healed = random.Random(7), 0
    for _ in range(n):
        part = {"wounds": wounds, "care": list(care)}
        healed += bt.heal_zone(part, days, rng) > 0
    return healed / n


# ---------- treatment ----------

def test_treatment_marks_the_zones_and_says_how_long_it_takes():
    sheet = _sheet(left_arm=1, chest=2)
    lines = body.treat(sheet, ["left arm", "chest"])
    assert body.body(sheet)["chest"]["care"] == ["first aid"]
    assert lines[-1] == "It takes 20 minutes: bash tools/gm-time.sh advance 20m"   # 5 + 15
    body.treat(sheet, ["chest"], doctor=True)
    assert body.body(sheet)["chest"]["care"] == ["first aid", "doctor"]


def test_a_critical_wound_needs_a_doctor_or_a_medpack():
    sheet = _sheet(head=3, right_leg=3, left_leg=2)
    with pytest.raises(body.BodyError, match="critical wound"):
        body.treat(sheet, ["head"])
    lines = body.treat(sheet, ["head", "right leg", "left leg"], supply="Medpack")
    assert lines[0] == "medpack used up" and sheet["items"]["gear"] == [{"name": "knife"}]
    assert body.body(sheet)["head"]["care"] == ["first aid", "supplied"]
    assert lines[-1].startswith("It takes 60 minutes")                 # 30 + 30 + 15, at most 60
    with pytest.raises(body.BodyError, match="no 'medpack'"):
        body.treat(_sheet(head=3) | {"items": {}}, ["head"], supply="medpack")


def test_what_treatment_refuses():
    with pytest.raises(body.BodyError, match="no wound"):
        body.treat(_sheet(), ["chest"])
    with pytest.raises(body.BodyError, match="destroyed"):
        body.treat(_sheet(left_arm=4), ["left arm"], doctor=True)


def test_a_new_wound_undoes_the_care():
    sheet = _sheet(chest=1)
    body.treat(sheet, ["chest"], doctor=True)
    body.hit(sheet, "chest", 1, rng=random.Random(1))
    assert "care" not in body.body(sheet)["chest"]


# ---------- healing ----------

def test_a_wound_heals_on_its_half_life():
    assert _share_healed(1, 2) == pytest.approx(0.5, abs=0.03)          # a bruise, 2 days
    assert _share_healed(2, 4) == pytest.approx(0.5, abs=0.03)          # an injury, 4 days
    # a doctor's treatment counts the time 4 times over: a bruise in half a day
    assert _share_healed(1, 0.5 * 4) == pytest.approx(0.5, abs=0.03)


def test_one_long_step_heals_like_many_short_ones():
    rng = random.Random(3)
    long_steps = sum(bt.heal_zone({"wounds": 2}, 6, rng) for _ in range(3000)) / 3000
    short = 0
    for _ in range(1000):
        part = {"wounds": 2}
        for _ in range(48):                                             # 6 days, 3 hours at a time
            short += bt.heal_zone(part, 6 / 48, rng)
    assert long_steps == pytest.approx(short / 1000, abs=0.06)


def test_a_critical_wound_heals_only_with_a_doctor_or_a_medpack():
    assert _share_healed(3, 1000) == 0
    assert _share_healed(3, 1000, care=["first aid", "supplied"]) == 1
    part = {"wounds": 3, "care": ["first aid", "doctor"]}
    assert bt.heal_zone(part, 1000, random.Random(1)) == 3 and "care" not in part   # all the way


def test_luck_comes_back_a_point_at_a_time():
    rng, back = random.Random(5), 0
    for _ in range(2000):
        sheet = {"stats": {"luck": {"current": 3, "max": 7}}}
        bt._luck(sheet, 7, rng)                                         # a week: half of the 4
        back += sheet["stats"]["luck"]["current"] - 3
    assert back / 2000 == pytest.approx(2, abs=0.1)


# ---------- as time passes ----------

def _wounded(dcc_world, **wounds):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))
    sheet = ops.load_json("character.json")
    for zone, n in wounds.items():
        body.body(sheet)[zone]["wounds"] = n
    sheet.setdefault("stats", {})["luck"] = {"current": 2, "max": 7}
    ops.save_json("character.json", sheet)
    overview = ops.load_json("campaign-overview.json")
    overview["game_time"] = "2187-10-26T04:30"
    ops.save_json("campaign-overview.json", overview)
    return ops


def test_time_passing_heals_and_says_so(dcc_world):
    from lib.time_manager import TimeManager
    ops = _wounded(dcc_world, left_arm=1, head=3)
    manager = TimeManager(dcc_world)
    manager.advance(120 * 24 * 60, through_all=True, resting=True)      # four months in bed
    sheet = ops.load_json("character.json")
    assert sheet["body"]["zones"]["left_arm"]["wounds"] == 0
    assert sheet["body"]["zones"]["head"]["wounds"] == 3                # critical: no doctor, no medpack
    healed = [line for m in manager.moments for line in m["healed"]]
    assert "left arm: bruised → healed" in healed
    assert sheet["stats"]["luck"]["current"] == 7


def test_resting_counts_double_and_a_journey_never_rests(dcc_world):
    from lib.time_manager import TimeManager
    _wounded(dcc_world, chest=1)
    manager = TimeManager(dcc_world)
    manager.advance(60, through_all=True, resting=True, on_the_way=True)
    assert manager.resting is False
    assert bt.recover(JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN)),
                      T0, T0 - timedelta(hours=1)) == []                # no time, nothing
