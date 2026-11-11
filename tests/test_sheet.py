"""The one sheet format (lib/sheet.py), shared by the player, NPCs and mobs, as
decided with the user on 2026-11-11: sections one level deep, look in three prose
fields, personality with the Big Five as signed numbers, items as gear (seen) and
inventory (hidden); what a person knows, feels or hides is facts, not fields."""

import pytest

from lib import sheet as S


def test_the_kinds_share_one_set_of_sections():
    assert S.ALLOWED["npc"] and set(S.ALLOWED["player"]) <= set(S.SECTIONS)
    assert set(S.ALLOWED["mob"]) <= set(S.ALLOWED["npc"])
    for kind in S.KINDS:
        assert S.check(S.blank(kind, "X"), kind)["identity"]["name"] == "X"


@pytest.mark.parametrize("sheet, kind, why", [
    ({"identity": {"name": "X"}, "mood": {}}, "npc", "Unknown section 'mood'"),
    ({"identity": {"name": "X"}, "places": {"usual": []}}, "player", "no 'places' section"),
    ({"identity": {"name": "X"}, "look": {"hair": "red"}}, "npc", "no field 'hair'"),
    ({"identity": {"name": "X"}, "look": {"style": 3}}, "npc", "is a text"),
    ({"identity": {}}, "npc", "needs identity.name"),
    ({"identity": {"name": "X"}}, "mob", "needs stats.attributes"),
    ({"identity": {"name": "X"}, "status": {"state": "dying"}}, "npc", "alive or dead"),
    ({"identity": {"name": "X"}, "stats": {"attributes": {"DEX": 12}}}, "npc", "Unknown attribute"),
])
def test_check_names_the_problem(sheet, kind, why):
    with pytest.raises(S.SheetError, match=why):
        S.check(sheet, kind)


def test_big_five_is_ocean_with_signed_numbers():
    assert S.check_big_five("o+1, c -2 e3 a-1 n2") == "O1 C-2 E3 A-1 N2"
    assert S.check_big_five("O0 C0 E0 A0 N0") == "O0 C0 E0 A0 N0"   # the average person
    for bad in ("ENTJ", "O1 C-2 E3 A-1", "O4 C0 E0 A0 N0", "C0 O0 E0 A0 N0", "O1 C1 E1 A1 N1 X"):
        with pytest.raises(S.SheetError, match="Big Five"):
            S.check_big_five(bad)


def test_set_fields_by_flag_and_clear_with_empty():
    sheet = S.blank("npc", "Ro")
    assert S.set_fields(sheet, {"style": "apron, broth steam", "big-five": "o0 c2 e1 a1 n-1",
                                "goal": "keep the street fed"}) == [
        "look.style", "personality.big_five", "status.goal"]
    assert sheet["personality"]["big_five"] == "O0 C2 E1 A1 N-1"
    S.set_fields(sheet, {"style": ""})
    assert "look" not in sheet
    with pytest.raises(S.SheetError, match="No field 'mood'"):
        S.set_fields(sheet, {"mood": "watchful"})


def test_items_gear_is_seen_inventory_is_not():
    sheet = S.blank("player", "Lullaby")
    S.add_item(sheet, "gear", "pipe")
    S.add_item(sheet, "gear", "holdout pistol", concealed=True)
    S.add_item(sheet, "inventory", "the stolen chip")
    assert S.visible_items(sheet) == ["pipe"]
    assert S.remove_item(sheet, "chip") == {"name": "the stolen chip", "place": "inventory"}
    with pytest.raises(S.SheetError, match="Carried: pipe, holdout pistol"):
        S.remove_item(sheet, "chip")
    with pytest.raises(S.SheetError, match="gear or inventory"):
        S.add_item(sheet, "pockets", "x")


def test_a_player_becomes_an_npc_and_an_npc_a_player():
    player = S.blank("player", "Lullaby")
    player["stats"]["luck"] = {"current": 3, "max": 7}
    npc = S.check(S.as_npc(player), "npc")
    assert "luck" not in npc["stats"] and npc["status"]["former_player_character"] is True
    assert npc["body"]["wounds"] == 3 and "luck" in player["stats"]      # the original is untouched
    base = S.from_npc({"identity": {"name": "Tod"}, "look": {"style": "oil"},
                       "places": {"usual": ["The Pens"]}, "status": {"goal": "x"}})
    assert set(base) == {"identity", "look"}


def test_describe_shows_what_is_filled_in():
    sheet = S.blank("npc", "Ro")
    S.set_fields(sheet, {"role": "noodle cook", "voice": "Sit. Eat."})
    S.add_item(sheet, "gear", "cleaver", note="always sharp")
    lines = S.describe(sheet)
    assert "role: noodle cook" in lines and "voice: Sit. Eat." in lines
    assert "gear: cleaver (always sharp)" in lines
    assert not any(line.startswith("name:") for line in lines)
