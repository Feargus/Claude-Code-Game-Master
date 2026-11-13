"""Tests for `gm-player.sh create`: the sheet (sheet.py's sections) with its
defaults, and the wiring (overwrite guard, --replace archiving, the overview,
canon NPCs)."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.campaign_manager import CampaignManager
from lib.new_character import CharacterCreator

ROOT = Path(__file__).resolve().parent.parent
ATTRIBUTES = ("STR", "AGI", "DFT", "VIG", "LOG", "ITU", "NRV", "PRS", "EMP")
COMMON = ("Brawling", "Throwing", "Evasion", "Guard", "Endurance", "Composure", "Athletics",
          "Acrobatics", "Stealth", "Awareness", "Investigation", "Insight", "Persuasion",
          "Deception")
RULESET = {
    "stat_schema": {"vitals": ["drift"]},
    "systems": [{"primitive": "named_track", "name": "Drift", "config": {"max": 10}}],
}


@pytest.fixture
def campaign(isolated_world_state):
    directory = isolated_world_state / "campaigns" / "test"
    directory.mkdir()
    (isolated_world_state / "active-campaign.txt").write_text("test")
    (directory / "ruleset.json").write_text(json.dumps(RULESET))
    return directory


def _named(name, **sections):
    return dict(sections, identity=dict(sections.get("identity") or {}, name=name))


def _create(*args, data=None):
    words = [json.dumps(data)] if data is not None else []
    return subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh"), "create", *words, *args, "--json"],
                          capture_output=True, text=True, env=os.environ)


def _ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["data"]


def _error(result):
    assert result.returncode == 1
    return json.loads(result.stdout)["error"]


def _sheet(campaign):
    return json.loads((campaign / "character.json").read_text())


# --- The sheet ---

def test_a_name_alone_gets_every_default(campaign):
    sheet = _ok(_create(data=_named("Mara")))
    assert sheet == _sheet(campaign)
    assert set(sheet) == {"identity", "stats", "body", "items", "possessions", "progress", "status"}
    assert sheet["progress"] == {"level": 0, "xp": 0, "practice": {}}
    assert sheet["stats"]["attributes"] == {a: 12 for a in ATTRIBUTES}
    assert sheet["stats"]["luck"] == {"current": 7, "max": 7}
    assert sheet["possessions"] == {"credits": 20}
    assert sheet["stats"]["skills"] == {name: 0 for name in COMMON}
    assert sheet["stats"]["traits"] == {} and sheet["stats"]["perks"] == {}
    assert set(sheet["body"]["zones"]) == {"head", "chest", "groin", "left_arm", "right_arm",
                                           "left_leg", "right_leg"}
    assert sheet["status"] == {"state": "alive", "conditions": []}
    assert sheet["items"] == {"gear": [], "inventory": []}


def test_the_campaigns_counters_come_from_its_ruleset(campaign):
    assert _ok(_create(data=_named("Mara")))["stats"]["counters"] == {"drift": {"current": 0, "max": 10}}


def test_a_counter_without_a_track_is_a_plain_number(campaign):
    (campaign / "ruleset.json").write_text(json.dumps(dict(RULESET, stat_schema={"vitals": ["heat"]})))
    sheet = _ok(_create(data=_named("Mara", stats={"counters": {"heat": 2}})))
    assert sheet["stats"]["counters"] == {"heat": 2}


def test_given_values_are_kept_whatever_they_are(campaign):
    sheet = _ok(_create(data=_named(
        "Mara", identity={"race": "AI", "role": "anything at all"},
        look={"physique": "tall", "style": "chrome and denim", "presence": "fills a room"},
        personality={"big_five": "o1 c-2 e3 a-1 n2", "voice": "clipped"},
        stats={"attributes": {"agi": 18, "LOG": 6}, "skills": {"Piloting": 5}, "luck": 1,
               "traits": {"Vat-grown": "+2 Endurance, -2 Composure"}},
        progress={"level": 2})))
    assert sheet["identity"] == {"name": "Mara", "race": "AI", "role": "anything at all"}
    assert sheet["look"]["style"] == "chrome and denim"
    assert sheet["personality"]["big_five"] == "O1 C-2 E3 A-1 N2"
    assert sheet["stats"]["attributes"]["AGI"] == 18 and sheet["stats"]["attributes"]["LOG"] == 6
    assert sheet["stats"]["skills"] == dict({n: 0 for n in COMMON}, Piloting=5)
    assert sheet["stats"]["luck"] == {"current": 1, "max": 1}
    assert sheet["progress"]["level"] == 2


def test_common_skills_start_at_zero_unless_raised_or_left_out(campaign):
    """The user's rule (2026-11-11): everyday skills are on every sheet, at 0 or more;
    the rest stays off it (untrained, −3). No negative value ever lands on the sheet."""
    sheet = _ok(_create(data=dict(_named("Mara", stats={"skills": {"brawling": 4, "long guns": 2}}),
                                  untrained=["deception"])))
    skills = sheet["stats"]["skills"]
    assert skills["Brawling"] == 4 and skills["Long guns"] == 2   # canon spelling
    assert skills["Guard"] == 0 and "Deception" not in skills and "Handguns" not in skills
    assert min(skills.values()) >= 0
    assert "untrained" not in sheet


def test_armor_cyberware_and_items(campaign):
    sheet = _ok(_create(data=_named(
        "Mara",
        body={"armor": [{"name": "Long coat", "zones": {"chest": 1, "left_arm": 1}},
                        {"name": "Vest", "zones": {"chest": 2}}],
              "cyberware": [{"name": "Cybereye", "zone": "head", "effect": "zoom"}]},
        items={"gear": ["pistol", {"name": "holdout", "concealed": True}],
               "inventory": ["lockpicks"]})))
    armor = sheet["body"]["armor"]
    assert [a["name"] for a in armor] == ["Long coat", "Vest"]   # outermost first
    assert armor[1]["zones"]["chest"] == {"boxes": 2, "damage": 0}
    assert sheet["body"]["cyberware"][0]["boxes"] == 1
    assert sheet["items"]["gear"] == [{"name": "pistol"}, {"name": "holdout", "concealed": True}]
    assert sheet["items"]["inventory"] == [{"name": "lockpicks"}]


def test_left_out_attributes_are_named_in_the_human_output(campaign):
    result = subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh"), "create",
                             json.dumps(_named("Mara", stats={"attributes": {"AGI": 14}}))],
                            capture_output=True, text=True, env=os.environ)
    assert "Mara enters the world" in result.stdout
    assert "default d12: STR, DFT" in result.stdout


@pytest.mark.parametrize("data, message", [
    ({}, "identity.name"),
    ({"name": "Mara"}, "identity.name"),   # the old flat format
    (_named("Mara", stats={"attributes": {"DEX": 12}}), "Unknown attribute"),
    (_named("Mara", stats={"attributes": {"AGI": 1}}), "die size"),
    (_named("Mara", body={"cyberware": [{"name": "Tail", "zone": "tail"}]}), "Unknown zone"),
    (_named("Mara", stats={"skills": {"default": 2}}), "not a skill"),
    (_named("Mara", stats={"skills": {"Handguns": -1}}), "Leave an untrained skill off the sheet"),
    (dict(_named("Mara"), untrained=["Handguns"]), "not a common skill"),
    (dict(_named("Mara", stats={"skills": {"Brawling": 1}}), untrained=["brawling"]), "both"),
    (_named("Mara", personality={"big_five": "ENTJ"}), "Big Five"),
    (_named("Mara", look={"hair": "red"}), "no field 'hair'"),
    (_named("Mara", secret={"x": 1}), "Unknown section"),
])
def test_refusals_leave_no_sheet(campaign, data, message):
    assert message in _error(_create(data=data))
    assert not (campaign / "character.json").exists()


# --- The wiring ---

def test_an_existing_character_is_not_overwritten(campaign):
    _ok(_create(data=_named("Mara")))
    assert "already plays" in _error(_create(data=_named("Vex")))
    assert _sheet(campaign)["identity"]["name"] == "Mara"


def test_replace_archives_the_old_character(campaign):
    _ok(_create(data=_named("Mara")))
    _ok(_create("--replace", data=_named("Vex")))
    assert _sheet(campaign)["identity"]["name"] == "Vex"
    assert json.loads((campaign / "fallen" / "mara.json").read_text())["identity"]["name"] == "Mara"
    npcs = json.loads((campaign / "npcs.json").read_text())
    assert npcs["Mara"]["status"]["former_player_character"] is True   # an NPC now


def test_the_overview_records_the_character(campaign):
    _ok(_create(data=_named("Mara")))
    overview = json.loads((campaign / "campaign-overview.json").read_text())
    assert overview["current_character"] == "Mara"


def test_canon_takes_the_npcs_sheet_and_leaves_npcs_json(dcc_world):
    env = {**os.environ, "GM_WORLD_STATE_BASE": str(dcc_world)}
    camp = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"
    before = json.loads((camp / "npcs.json").read_text())["Mordecai"]
    result = subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh"), "create",
                             json.dumps({"identity": {"role": "game guide"}}),
                             "--canon", "mordecai", "--replace", "--json"],
                            capture_output=True, text=True, env=env)
    sheet = _ok(result)
    assert sheet["identity"]["name"] == "Mordecai" and sheet["identity"]["role"] == "game guide"
    assert sheet.get("look") == before.get("look")                    # carried over
    assert "Mordecai" not in json.loads((camp / "npcs.json").read_text())


def test_canon_unknown_npc_is_refused(campaign):
    assert "Nobody" in _error(_create("--canon", "Nobody", data=_named("Nobody")))


def test_creating_a_character_moves_nothing(isolated_world_state):
    """The opening (gm-session.sh opening) comes after the character, so creating
    one leaves the position as it is (it used to re-seed an import's opening)."""
    cm = CampaignManager()
    cdir = cm.create("Hyboria", "Hyboria")
    assert cm.set_active("Hyboria")
    ov = json.loads((cdir / "campaign-overview.json").read_text())
    ov["player_position"] = {"current_location": "The Tigress"}
    (cdir / "campaign-overview.json").write_text(json.dumps(ov), encoding="utf-8")
    assert CharacterCreator().create(_named("Conan", identity={"background": "a pirate"}))["success"]
    ov = json.loads((cdir / "campaign-overview.json").read_text())
    assert ov["player_position"] == {"current_location": "The Tigress"}
    assert "opening_hook" not in ov


# ---------- aliases: the shorter names the story uses ----------

def _npcs(campaign, **npcs):
    (campaign / "npcs.json").write_text(json.dumps(
        {name: {"identity": dict({"name": name}, **identity)} for name, identity in npcs.items()}))


def test_a_name_of_several_words_needs_its_aliases(campaign):
    """"Dogen" for Dogen Mabuchi was unknown to facts, triggers and rolls: the
    player's aliases can only be given at creation, and nothing asked for them."""
    refused = CharacterCreator().create(_named("Dogen Mabuchi"))
    assert not refused["success"] and '"aliases"' in refused["error"] and '["Dogen"]' in refused["error"]
    assert not (campaign / "character.json").exists()

    made = CharacterCreator().create(_named("Dogen Mabuchi", identity={"aliases": ["Dogen", " Dogen "]}))
    assert made["success"] and made["character"]["identity"]["aliases"] == ["Dogen"]


def test_no_shorter_name_is_an_answer_and_one_word_needs_none(campaign):
    made = CharacterCreator().create(_named("Old Iron", identity={"aliases": []}))
    assert made["success"] and "aliases" not in made["character"]["identity"]
    assert CharacterCreator().create(_named("Tandy"), replace=True)["success"]


def test_an_alias_that_names_someone_else_is_refused(campaign):
    _npcs(campaign, **{"Mama Seo": {"aliases": ["Seo"]}})
    for alias, why in [("Seo", "already names npc:Mama Seo"), ("player", "a word ids use"),
                       ("Dogen Mabuchi", "own name")]:
        refused = CharacterCreator().create(_named("Dogen Mabuchi", identity={"aliases": [alias]}))
        assert not refused["success"] and why in refused["error"], (alias, refused["error"])


def test_a_canon_character_keeps_the_npcs_aliases(campaign):
    _npcs(campaign, **{"Mama Seo": {"aliases": ["Seo"]}, "Tomas Reyes": {}})
    made = CharacterCreator().create({}, canon="Mama Seo")
    assert made["success"] and made["character"]["identity"]["aliases"] == ["Seo"]
    refused = CharacterCreator().create({}, canon="Tomas Reyes", replace=True)
    assert not refused["success"] and '["Tomas"]' in refused["error"]


def test_aliases_are_corrected_with_the_alias_command(campaign):
    from lib.player_manager import PlayerManager
    from lib.world_ids import WorldIds
    _npcs(campaign, **{"Mama Seo": {"aliases": ["Seo"]}})
    CharacterCreator().create(_named("Dogen Mabuchi", identity={"aliases": []}))
    manager = PlayerManager()
    assert manager.change_aliases(["Dogen", "the Dog"], [])["aliases"] == ["Dogen", "the Dog"]
    assert not manager.change_aliases(["Seo"], [])["success"]
    assert manager.change_aliases([], ["the dog"])["aliases"] == ["Dogen"]
    ids = WorldIds(manager.json_ops)
    assert ids.resolve("dogen") == ("player", "")
    assert ids.mentioned("Juniper told Dogen about the key.") == ["player"]
