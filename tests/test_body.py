"""Tests for wounds, armor and cyberware.

PickBoxes replaces the random choice of a box, so every test knows where a wound lands.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.body import (
    BodyError,
    add_armor,
    add_cyberware,
    heal,
    hit,
    note,
    picture,
    remove,
    repair,
    show,
    summary,
)

REPO = Path(__file__).resolve().parent.parent


class PickBoxes:
    """Stands in for `random`: picks the flesh box (None) or the named item, in order."""

    def __init__(self, *picks):
        self.picks = list(picks)

    def choice(self, boxes):
        pick = self.picks.pop(0)
        for box in boxes:
            if (box is None and pick is None) or (box is not None and box["name"] == pick):
                return box
        raise AssertionError(f"{pick!r} isn't one of the empty boxes")


class AlwaysFlesh:
    """Stands in for `random`: every wound lands in the flesh."""

    def choice(self, boxes):
        assert None in boxes, "no empty flesh box left"
        return None


FLESH = AlwaysFlesh()


def _wounds(sheet, zone):
    return sheet["body"][zone]["wounds"]


# --- Flesh ---

def test_a_new_sheet_gets_every_zone():
    sheet = {}
    hit(sheet, "head", 1, FLESH)
    assert set(sheet["body"]) == {"head", "chest", "groin", "left_arm", "right_arm",
                                  "left_leg", "right_leg"}


def test_wounds_add_up_and_name_their_effect():
    sheet = {}
    assert hit(sheet, "right_arm", 2, FLESH) == [
        "right_arm: wound 1 of 4, bruise, no effect",
        "right_arm: wound 2 of 4, injured",
    ]


def test_the_fourth_wound_destroys_and_kills_in_head_chest_groin():
    sheet = {}
    assert hit(sheet, "left_leg", 4, FLESH)[-1] == "left_leg: wound 4 of 4, destroyed"
    assert hit(sheet, "chest", 4, FLESH)[-1] == "chest: wound 4 of 4, dead"


def test_wounds_beyond_destroyed_are_reported_not_counted():
    sheet = {}
    events = hit(sheet, "left_arm", 6, FLESH)
    assert _wounds(sheet, "left_arm") == 4
    assert events[-1] == "left_arm is already destroyed"


def test_zone_names_may_use_spaces_and_capitals():
    sheet = {}
    hit(sheet, "Left Arm", 1, FLESH)
    assert _wounds(sheet, "left_arm") == 1


def test_unknown_zone_is_refused():
    with pytest.raises(BodyError, match="Unknown zone"):
        hit({}, "tail", 1, FLESH)


def test_healing_empties_boxes_but_never_below_zero():
    sheet = {}
    hit(sheet, "groin", 2, FLESH)
    heal(sheet, "groin", 5)
    assert _wounds(sheet, "groin") == 0


def test_a_destroyed_zone_never_heals():
    sheet = {}
    hit(sheet, "right_leg", 4, FLESH)
    with pytest.raises(BodyError, match="never heals"):
        heal(sheet, "right_leg", 1)


def test_notes_are_set_and_cleared():
    sheet = {}
    note(sheet, "left_arm", "lost at the elbow")
    assert sheet["body"]["left_arm"]["note"] == "lost at the elbow"
    note(sheet, "left_arm", "")
    assert "note" not in sheet["body"]["left_arm"]


# --- Armor ---

def test_armor_absorbs_first_and_is_used_up():
    sheet = {}
    add_armor(sheet, "Long coat", ["chest:2"])
    hit(sheet, "chest", 3, FLESH)
    assert sheet["armor"][0]["zones"]["chest"] == {"boxes": 2, "damage": 2}
    assert _wounds(sheet, "chest") == 1


def test_armor_only_covers_its_zones():
    sheet = {}
    add_armor(sheet, "Helmet", ["head:2"])
    hit(sheet, "chest", 1, FLESH)
    assert _wounds(sheet, "chest") == 1


def test_newest_armor_is_the_outer_layer():
    sheet = {}
    add_armor(sheet, "Vest", ["chest:1"])
    add_armor(sheet, "Coat", ["chest:1"])
    hit(sheet, "chest", 1, FLESH)
    coat, vest = sheet["armor"]
    assert coat["zones"]["chest"]["damage"] == 1 and vest["zones"]["chest"]["damage"] == 0


def test_dr_stops_wounds_without_damaging_the_armor():
    sheet = {}
    add_armor(sheet, "Riot plate", ["chest:3"], dr=1)
    assert hit(sheet, "chest", 1, FLESH) == ["DR stopped 1 wound"]
    hit(sheet, "chest", 2, FLESH)
    assert sheet["armor"][0]["zones"]["chest"]["damage"] == 1


def test_repair_restores_every_box():
    sheet = {}
    add_armor(sheet, "Coat", ["chest:2", "left_arm:1"])
    hit(sheet, "chest", 2, FLESH)
    repair(sheet, "coat")
    assert sheet["armor"][0]["zones"]["chest"]["damage"] == 0


def test_armor_needs_zone_and_boxes():
    with pytest.raises(BodyError, match="ZONE:BOXES"):
        add_armor({}, "Coat", ["chest"])
    with pytest.raises(BodyError, match="1 or more"):
        add_armor({}, "Coat", ["chest:0"])


# --- Cyberware ---

def test_a_wound_can_land_in_chrome_instead_of_flesh():
    sheet = {}
    add_cyberware(sheet, "Cybereye", "head", 1)
    events = hit(sheet, "head", 1, PickBoxes("Cybereye"))
    assert events == ["Cybereye took the wound, 0 left, stopped working"]
    assert _wounds(sheet, "head") == 0


def test_every_empty_box_is_a_candidate():
    """A 4-box flesh zone plus a 3-box arm: 7 empty boxes to choose from."""
    sheet = {}
    add_cyberware(sheet, "Chrome arm", "right_arm", 3)
    seen = []

    class Spy:
        def choice(self, boxes):
            seen.append(len(boxes))
            return boxes[0]

    hit(sheet, "right_arm", 1, Spy())
    assert seen == [7]


def test_broken_chrome_is_no_longer_a_candidate():
    sheet = {}
    add_cyberware(sheet, "Cybereye", "head", 1)
    hit(sheet, "head", 1, PickBoxes("Cybereye"))
    with pytest.raises(AssertionError, match="isn't one of the empty boxes"):
        hit(sheet, "head", 1, PickBoxes("Cybereye"))


def test_the_fourth_flesh_wound_destroys_however_much_chrome_is_left():
    sheet = {}
    add_cyberware(sheet, "Chrome arm", "left_arm", 3)
    hit(sheet, "left_arm", 4, FLESH)
    assert _wounds(sheet, "left_arm") == 4
    assert sheet["cyberware"][0]["damage"] == 0


def test_names_are_unique_and_remove_works_for_both_kinds():
    sheet = {}
    add_armor(sheet, "Coat", ["chest:1"])
    with pytest.raises(BodyError, match="already on the sheet"):
        add_cyberware(sheet, "coat", "head", 1)
    add_cyberware(sheet, "Cybereye", "head", 1)
    remove(sheet, "Coat")
    remove(sheet, "Cybereye")
    assert sheet["armor"] == [] and sheet["cyberware"] == []
    with pytest.raises(BodyError, match="No armor or cyberware"):
        remove(sheet, "Coat")


# --- The picture ---

def test_picture_shows_bars_circles_crosses_and_diamonds():
    sheet = {}
    add_armor(sheet, "Coat", ["chest:2"])
    add_cyberware(sheet, "Cybereye", "head", 1)
    hit(sheet, "chest", 3, FLESH)
    hit(sheet, "left_arm", 4, FLESH)
    lines = picture(sheet).split("\n")
    assert len(lines) == 3
    assert lines[0].strip() == "head ○○○ ◇"
    assert "l.arm ✖" in lines[1] and "chest ▮▮ ●○○" in lines[1] and "r.arm ○○○" in lines[1]
    assert "l.leg ○○○" in lines[2] and "groin ○○○" in lines[2]


def test_show_lists_notes_armor_and_cyberware():
    sheet = {}
    note(sheet, "left_arm", "lost at the elbow")
    add_armor(sheet, "Coat", ["chest:2"])
    add_cyberware(sheet, "Jack", "head", 1, "+1 Netrunning")
    text = show(sheet)
    assert "left_arm: lost at the elbow" in text
    assert "armor: Coat (chest 2/2)" in text
    assert "cyberware: Jack (head, 1/1, working, +1 Netrunning)" in text


def test_summary_names_wounded_zones_and_broken_chrome():
    sheet = {}
    assert summary(sheet) == "unhurt"
    hit(sheet, "left_arm", 4, FLESH)
    hit(sheet, "chest", 2, FLESH)
    add_cyberware(sheet, "Cybereye", "head", 1)
    hit(sheet, "head", 1, PickBoxes("Cybereye"))
    assert summary(sheet) == "chest injured, l.arm destroyed, Cybereye broken"


# --- The real command ---

@pytest.fixture
def campaign(isolated_world_state):
    directory = isolated_world_state / "campaigns" / "test"
    directory.mkdir()
    (isolated_world_state / "active-campaign.txt").write_text("test")
    (directory / "character.json").write_text(json.dumps({"name": "Fearghas", "level": 2}))
    return directory


def _run(*words):
    return subprocess.run(["bash", str(REPO / "tools" / "gm-body.sh"), *words],
                          capture_output=True, text=True, env=os.environ)


def test_wrapper_saves_to_the_sheet(campaign):
    result = _run("armor", "Long coat", "chest:2", "left_arm:1")
    assert result.returncode == 0, result.stderr
    result = _run("hit", "chest", "1")
    assert "Long coat absorbed a wound on the chest, 1 left there" in result.stdout
    sheet = json.loads((campaign / "character.json").read_text())
    assert sheet["armor"][0]["zones"]["chest"]["damage"] == 1
    assert sheet["name"] == "Fearghas"


def test_wrapper_reports_errors_on_stderr(campaign):
    result = _run("hit", "tail")
    assert result.returncode == 1
    assert "Unknown zone" in result.stderr and result.stdout == ""
