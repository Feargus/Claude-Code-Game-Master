"""Tests for the skill contest: dice, quality, luck, name lookup and refusals.

ScriptedDice replaces the random numbers with a fixed list, so every test knows
exactly what was rolled.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.skill_contest import (
    ContestError,
    apply_luck,
    build_parser,
    format_result,
    resolve_contest,
    roll_attribute,
    run_contest,
)

REPO = Path(__file__).resolve().parent.parent


class ScriptedDice:
    """Stands in for `random`: hands out the given numbers in order."""

    def __init__(self, *numbers):
        self.numbers = list(numbers)

    def randint(self, low, high):
        number = self.numbers.pop(0)
        assert low <= number <= high, f"{number} can't come up on a d{high}"
        return number


def _side(attributes=("DFT", "AGI", "ITU"), size=10, skill_value=0, advantages=(),
          disadvantages=(), is_player=False):
    return {"attributes": list(attributes), "dice_sizes": dict.fromkeys(attributes, size),
            "skill_value": skill_value, "advantages": list(advantages),
            "disadvantages": list(disadvantages), "is_player": is_player}


@pytest.fixture
def campaign(isolated_world_state):
    """A tiny campaign with the player, one named NPC and one campaign mob."""
    directory = isolated_world_state / "campaigns" / "test"
    directory.mkdir()
    (isolated_world_state / "active-campaign.txt").write_text("test")
    sheets = {
        "character.json": {
            "identity": {"name": "Fearghas"}, "progress": {"level": 2, "xp": 0},
            "stats": {"attributes": {"DFT": 14, "AGI": 12, "ITU": 10},
                      "skills": {"Long guns": 2}, "luck": {"current": 3, "max": 3}},
            "body": {"zones": {}},
        },
        "npcs.json": {
            "Dekker": {"identity": {"name": "Dekker"},
                       "stats": {"attributes": {"AGI": 8, "ITU": 8, "NRV": 8},
                                 "skills": {"Evasion": 1}}},
            "Auntie Ro": {"identity": {"name": "Auntie Ro", "role": "No stats yet."}},
        },
        "mobs.json": {"cockroach": {"identity": {"name": "cockroach"},
                                    "stats": {"attributes": {"default": 4, "AGI": 10},
                                              "skills": {"default": -3, "Evasion": 3}},
                                    "body": {"wounds": 1}}},
    }
    for filename, data in sheets.items():
        (directory / filename).write_text(json.dumps(data))
    return directory


def _args(*words):
    return build_parser().parse_args(list(words))


SHOOT = ("--active", "Fearghas", "Long guns", "DFT", "AGI", "ITU")
DODGE = ("--reactive", "Dekker", "Evasion", "AGI", "ITU", "NRV")


# --- Dice ---

def test_plain_roll_keeps_every_die():
    assert roll_attribute(ScriptedDice(3, 7), 10, 2)["kept"] == [3, 7]


def test_advantage_drops_the_lowest():
    assert roll_attribute(ScriptedDice(3, 7, 5), 10, 2, advantages=1)["kept"] == [5, 7]


def test_disadvantage_drops_the_highest():
    assert roll_attribute(ScriptedDice(3, 7, 5), 10, 2, disadvantages=1)["kept"] == [3, 5]


def test_mixed_advantage_and_disadvantage_keep_the_middle():
    assert roll_attribute(ScriptedDice(1, 9, 5), 10, 1, 1, 1)["kept"] == [5]


def test_advantage_affects_every_die_of_that_attribute():
    """STR twice with advantage: three dice, keep the best two."""
    dice = ScriptedDice(2, 8, 6, 4)
    active = _side(("STR", "STR", "VIG"), advantages=[{"attribute": "STR", "label": "rested"}])
    result = resolve_contest(dice, active, {"dc": 0}, [])
    assert active["dice"]["STR"]["kept"] == [6, 8]
    assert result["active_total"] == 6 + 8 + 4


def test_mixed_die_sizes_are_all_rolled():
    """The bug in dice.py: `1d14+1d14+1d12+4` lost two of its dice."""
    active = _side(("STR", "STR", "VIG"), skill_value=4)
    active["dice_sizes"] = {"STR": 14, "VIG": 12}
    result = resolve_contest(ScriptedDice(14, 14, 12), active, {"dc": 0}, [])
    assert result["active_total"] == 44


# --- Quality ---

def test_quality_is_active_minus_reactive_plus_mods():
    mods = [{"value": 2, "label": "feint"}, {"value": -3, "label": "darkness"}]
    dice = ScriptedDice(5, 5, 5, 4, 4, 4)
    result = resolve_contest(dice, _side(skill_value=3), _side(skill_value=1), mods)
    assert result["quality"] == (15 + 3) - (12 + 1) - 1


def test_reactive_dc():
    result = resolve_contest(ScriptedDice(6, 6, 6), _side(), {"dc": 18}, [])
    assert result["quality"] == 0


def test_active_dc_is_good_for_the_hazard_when_positive():
    """A poison of 18 against a roll of 12: the poison works."""
    result = resolve_contest(ScriptedDice(4, 4, 4), {"dc": 18}, _side(), [])
    assert result["quality"] == 6


# --- Luck ---

def test_luck_rescues_the_narrowest_loss_of_an_active_player():
    assert apply_luck(-1, "active", 1) == 0


def test_luck_rescues_the_narrowest_loss_of_a_reactive_player():
    assert apply_luck(0, "reactive", 1) == -1


@pytest.mark.parametrize("quality, role, luck", [
    (-2, "active", 3),     # lost by too much
    (0, "active", 3),      # already won
    (-1, "reactive", 3),   # already won
    (1, "reactive", 3),    # lost by too much
    (-1, "active", 0),     # no luck left
    (-1, None, 3),         # no player involved
])
def test_luck_stays_out_of_everything_else(quality, role, luck):
    assert apply_luck(quality, role, luck) is None


def test_format_mentions_luck_only_when_spent():
    assert format_result({"quality": 7, "lucky": False}) == "quality: 7"
    assert format_result({"quality": 0, "lucky": True}) == "quality: 0 (lucky)"


# --- Full contests, with files ---

def test_player_against_npc_uses_both_sheets(campaign):
    dice = ScriptedDice(10, 8, 6, 3, 3, 3)
    result = run_contest(_args(*SHOOT, *DODGE), dice)
    assert result["active_total"] == 10 + 8 + 6 + 2
    assert result["reactive_total"] == 3 + 3 + 3 + 1


def test_sheet_die_sizes_limit_the_roll(campaign):
    """Dekker's dice are d8: a 9 is impossible, and ScriptedDice would object."""
    with pytest.raises(AssertionError):
        run_contest(_args(*SHOOT, *DODGE), ScriptedDice(1, 1, 1, 9, 1, 1))


def test_names_ignore_case(campaign):
    run_contest(_args("--active", "fearghas", "long guns", "dft", "agi", "itu",
                      "--reactive-dc", "10", "door"), ScriptedDice(5, 5, 5))


def test_campaign_mob_and_default_die(campaign):
    """cockroach sets AGI, and the rest come from its default of 4."""
    args = _args(*SHOOT, "--reactive", "cockroach", "Evasion", "AGI", "ITU", "NRV")
    result = run_contest(args, ScriptedDice(5, 5, 5, 9, 4, 4))
    assert result["reactive_total"] == 9 + 4 + 4 + 3


def test_repo_mob(campaign):
    args = _args(*SHOOT, "--reactive", "rat", "Evasion", "AGI", "ITU", "NRV")
    result = run_contest(args, ScriptedDice(5, 5, 5, 12, 10, 8))
    assert result["reactive_total"] == 12 + 10 + 8 + 2


def test_luck_is_spent_from_the_sheet(campaign):
    args = _args(*SHOOT, "--reactive-dc", "18", "door")
    result = run_contest(args, ScriptedDice(5, 5, 5))  # 15 + 2 against 18
    assert result["quality"] == 0 and result["lucky"]
    sheet = json.loads((campaign / "character.json").read_text())
    assert sheet["stats"]["luck"] == {"current": 2, "max": 3}


def test_missing_luck_field_counts_as_none_left(campaign):
    sheet = json.loads((campaign / "character.json").read_text())
    del sheet["stats"]["luck"]
    (campaign / "character.json").write_text(json.dumps(sheet))
    result = run_contest(_args(*SHOOT, "--reactive-dc", "18", "door"), ScriptedDice(5, 5, 5))
    assert result["quality"] == -1


def test_npcs_never_spend_luck(campaign):
    args = _args("--active", "Dekker", "Evasion", "AGI", "ITU", "NRV",
                 "--reactive-dc", "13", "door")
    result = run_contest(args, ScriptedDice(4, 4, 3))  # 11 + 1 against 13
    assert result["quality"] == -1 and not result["lucky"]


def _log_blocks(campaign):
    """The log's rolls, each as {label: value}. A blank line separates them."""
    text = (campaign / "skill-contest.log").read_text()
    blocks = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        blocks.append({k: v if k == "time" else json.loads(v) for k, v in lines.items()})
    return blocks


def test_every_roll_is_logged_with_its_dice_and_labels(campaign):
    run_contest(_args(*SHOOT, *DODGE, "--mod", "-2", "darkness"), ScriptedDice(1, 2, 3, 4, 5, 6))
    entry = _log_blocks(campaign)[0]
    assert entry["active"]["dice"]["DFT"]["rolled"] == [1]
    assert entry["reactive"]["skill"] == "Evasion"
    assert entry["mods"] == [{"value": -2, "label": "darkness"}]
    assert "quality" in entry["result"]


def test_log_gives_each_part_its_own_line_and_separates_rolls(campaign):
    for _ in range(2):
        run_contest(_args(*SHOOT, *DODGE), ScriptedDice(1, 2, 3, 4, 5, 6))
    blocks = _log_blocks(campaign)
    assert len(blocks) == 2
    assert list(blocks[1]) == ["time", "active", "reactive", "mods", "result"]


def test_a_missing_skill_counts_minus_three_and_is_logged_as_untrained(campaign):
    args = _args("--active", "Fearghas", "Handguns", "DFT", "AGI", "ITU",
                 "--reactive-dc", "10", "door")
    result = run_contest(args, ScriptedDice(5, 5, 5))
    assert result["active_total"] == 15 - 3
    entry = _log_blocks(campaign)[0]
    assert entry["active"]["skill"] == "Handguns"
    assert entry["active"]["untrained"] is True


def test_a_mob_has_its_common_skills_at_zero_without_listing_them(campaign):
    """The street thug (repo mob) lists no Awareness and no Netrunning: common 0, untrained −3."""
    for skill, anchor, value, untrained in (("Awareness", "ITU", 0, False),
                                            ("Netrunning", "LOG", -3, True)):
        args = _args("--active", "street thug", skill, anchor, anchor, anchor,
                     "--reactive-dc", "10", "noise")
        result = run_contest(args, ScriptedDice(5, 5, 5))
        assert result["active_total"] == 15 + value
        assert _log_blocks(campaign)[-1]["active"]["untrained"] is untrained


def test_a_listed_skill_is_logged_as_trained(campaign):
    run_contest(_args(*SHOOT, "--reactive-dc", "10", "door"), ScriptedDice(5, 5, 5))
    assert _log_blocks(campaign)[0]["active"]["untrained"] is False


def test_a_sheet_can_set_its_own_untrained_value(campaign):
    args = _args(*SHOOT, "--reactive", "cockroach", "Tech", "LOG", "ITU", "NRV")
    result = run_contest(args, ScriptedDice(5, 5, 5, 3, 3, 3))
    assert result["reactive_total"] == 9 - 3


def test_default_is_not_a_skill(campaign):
    """A skill called "default" is never looked up as the sheet's default."""
    args = _args(*SHOOT, "--reactive", "cockroach", "default", "AGI", "ITU", "NRV")
    with pytest.raises(ContestError, match="'default' is not a skill"):
        run_contest(args, ScriptedDice(5, 5, 5, 3, 3, 3))


def test_advantage_reasons_are_logged(campaign):
    args = _args(*SHOOT, *DODGE, "--active-adv", "dft", "rested",
                 "--active-adv", "DFT", "stim", "--reactive-dis", "ITU", "surprised")
    run_contest(args, ScriptedDice(*[1] * 9))
    entry = _log_blocks(campaign)[0]
    assert entry["active"]["advantages"] == [{"attribute": "DFT", "label": "rested"},
                                             {"attribute": "DFT", "label": "stim"}]
    assert entry["reactive"]["disadvantages"] == [{"attribute": "ITU", "label": "surprised"}]
    assert len(entry["active"]["dice"]["DFT"]["rolled"]) == 3


# --- Refusals ---

@pytest.mark.parametrize("words, message", [
    (("--active-dc", "10", "a", "--reactive-dc", "10", "b"), "Both sides are DCs"),
    (("--active-dc", "10", "gas", *DODGE, "--active-adv", "STR", "rested"), "A DC doesn't roll"),
    (("--active", "Nobody", "Tech", "DFT", "LOG", "ITU", *DODGE), "Unknown name"),
    (("--active", "Auntie Ro", "Tech", "DFT", "LOG", "ITU", *DODGE), "no stats yet"),
    (("--active", "Fearghas", "Long guns", "DEX", "AGI", "ITU", *DODGE), "Unknown attribute"),
    (("--active", "Fearghas", "Long guns", "DFT", "NRV", "ITU", *DODGE), "no usable die"),
    ((*SHOOT, *DODGE, "--active-adv", "STR", "rested"), "isn't rolling it"),
    ((*SHOOT, *DODGE, "--mod", "lots", "feint"), "whole number"),
    ((*SHOOT, "--reactive", "Fearghas", "Long guns", "DFT", "AGI", "ITU"), "both sides"),
])
def test_refusals(campaign, words, message):
    with pytest.raises(ContestError, match=message):
        run_contest(_args(*words), ScriptedDice(*[1] * 12))


def test_a_refused_contest_leaves_no_trace(campaign):
    with pytest.raises(ContestError):
        run_contest(_args("--active", "Nobody", "Tech", "DFT", "LOG", "ITU", *DODGE))
    assert not (campaign / "skill-contest.log").exists()


# --- The real command ---

def _run(*words):
    return subprocess.run(["bash", str(REPO / "tools" / "gm-skill-contest.sh"), *words],
                          capture_output=True, text=True, env=os.environ)


def test_wrapper_prints_only_the_quality(campaign):
    result = _run(*SHOOT, *DODGE, "--active-adv", "DFT", "rested", "--mod", "-2", "darkness",
                  "--mod", "+1", "good feint")
    assert result.returncode == 0, result.stderr
    words = result.stdout.split()
    assert words[0] == "quality:" and int(words[1]) is not None


def test_wrapper_reports_errors_on_stderr(campaign):
    result = _run("--active", "Nobody", "Tech", "DFT", "LOG", "ITU", *DODGE)
    assert result.returncode == 1
    assert "Unknown name" in result.stderr and result.stdout == ""


# --- Learning by use (growth.py) ---

def test_the_player_learns_from_close_contests(campaign):
    """A close result teaches (here quality 0 after luck: 3 learnings); a blowout
    teaches nothing; the output stays the quality alone."""
    result = run_contest(_args(*SHOOT, "--reactive-dc", "18", "door"), ScriptedDice(5, 5, 5))
    assert result["quality"] == 0 and result["learned"] == []
    sheet = json.loads((campaign / "character.json").read_text())
    assert sheet["progress"]["practice"] == {"Long guns": 3} and sheet["stats"]["skills"]["Long guns"] == 2
    run_contest(_args(*SHOOT, "--reactive-dc", "18", "door"), ScriptedDice(14, 12, 10))
    assert json.loads((campaign / "character.json").read_text())["progress"]["practice"] == {"Long guns": 3}
    assert format_result(result) == "quality: 0 (lucky)"


def test_enough_learnings_raise_the_skill_and_grant_xp(campaign):
    sheet = json.loads((campaign / "character.json").read_text())
    sheet["progress"]["practice"] = {"Long guns": 7}
    (campaign / "character.json").write_text(json.dumps(sheet))
    result = run_contest(_args(*SHOOT, *DODGE), ScriptedDice(4, 4, 4, 4, 4, 4))  # 12+2 vs 12+1
    assert result["learned"] == [{"skill": "Long guns", "value": 3, "xp": 30}]
    sheet = json.loads((campaign / "character.json").read_text())
    assert sheet["stats"]["skills"]["Long guns"] == 3 and sheet["progress"]["xp"] == 30
    assert "+30 XP  skill: Long guns rose to 3" in (campaign / "xp.log").read_text()


def test_an_alias_or_a_first_name_finds_the_player_and_npcs(campaign):
    """Every other command resolves names through world_ids.py; the contest only
    took the exact key, so "Ro" and "Dek" were unknown."""
    path = campaign / "npcs.json"
    npcs = json.loads(path.read_text())
    npcs["Dekker"]["identity"]["aliases"] = ["Dek"]
    npcs["Captain Ilse Varga"] = {"identity": {"name": "Captain Ilse Varga"},
                               "stats": {"attributes": {"default": 8}}}
    path.write_text(json.dumps(npcs))
    character = json.loads((campaign / "character.json").read_text())
    character["identity"]["aliases"] = ["Grey"]
    (campaign / "character.json").write_text(json.dumps(character))

    args = _args("--active", "grey", "Long guns", "DFT", "AGI", "ITU",
                 "--reactive", "dek", "Evasion", "AGI", "ITU", "NRV")
    run_contest(args, ScriptedDice(5, 5, 5, 4, 4, 4))
    block = _log_blocks(campaign)[-1]
    assert block["active"]["name"] == "Fearghas" and block["active"]["is_player"]
    assert block["reactive"]["name"] == "Dekker"      # the log names the sheet

    args = _args(*SHOOT, "--reactive", "ilse varga", "Evasion", "AGI", "ITU", "NRV")   # no title
    run_contest(args, ScriptedDice(5, 5, 5, 4, 4, 4))
    assert _log_blocks(campaign)[-1]["reactive"]["name"] == "Captain Ilse Varga"


def test_an_unknown_name_gets_close_matches_and_the_commands(campaign):
    with pytest.raises(ContestError) as refused:
        run_contest(_args(*SHOOT, "--reactive", "Dekkar", "Evasion", "AGI", "ITU", "NRV"),
                    ScriptedDice(5, 5, 5))
    message = str(refused.value)
    assert "did you mean: npc:Dekker" in message
    assert "gm-npc.sh create" in message and "npcs.json" not in message
    with pytest.raises(ContestError, match="Mobs like it: cockroach"):
        run_contest(_args(*SHOOT, "--reactive", "cockroch", "Evasion", "AGI", "ITU", "NRV"),
                    ScriptedDice(5, 5, 5))


def test_the_player_can_be_called_player(campaign):
    run_contest(_args("--active", "player", "Long guns", "DFT", "AGI", "ITU",
                      "--reactive-dc", "10", "door"), ScriptedDice(5, 5, 5))
    assert _log_blocks(campaign)[-1]["active"]["name"] == "Fearghas"
    with pytest.raises(ContestError, match=r"The player is 'Fearghas' \(or just: player\)"):
        run_contest(_args("--active", "Fergus", "Long guns", "DFT", "AGI", "ITU",
                          "--reactive-dc", "10", "door"), ScriptedDice(5, 5, 5))


# --- The skill must exist, and its anchor must be rolled (skills.py) ---

def test_a_name_that_is_no_skill_is_refused_and_teaches_nothing(campaign):
    """"Lockpicking" (the skill is Larceny) used to roll as untrained without a
    word; four close rolls later the sheet had Lockpicking 1 and 10 XP."""
    before = (campaign / "character.json").read_text()
    with pytest.raises(ContestError) as refused:
        run_contest(_args("--active", "Fearghas", "Lockpicking", "DFT", "DFT", "ITU",
                          "--reactive-dc", "15", "cheap lock"), ScriptedDice(5, 5, 5))
    message = str(refused.value)
    assert "No skill 'Lockpicking'" in message and "Larceny" in message
    assert "improvised-skills.md" in message and "## Lockpicking" in message
    assert (campaign / "character.json").read_text() == before
    assert not (campaign / "skill-contest.log").exists()


def test_a_skill_is_rolled_and_logged_as_the_list_spells_it(campaign):
    """However it is typed, it is the skill on the sheet: "long  GUNS" has value 2."""
    result = run_contest(_args("--active", "Fearghas", "long  GUNS", "DFT", "AGI", "ITU",
                               "--reactive-dc", "18", "door"), ScriptedDice(5, 5, 5))
    assert result["active_total"] == 15 + 2
    assert _log_blocks(campaign)[0]["active"]["skill"] == "Long guns"
    sheet = json.loads((campaign / "character.json").read_text())
    assert list(sheet["progress"]["practice"]) == ["Long guns"]


def test_a_roll_without_the_skills_anchor_is_refused(campaign):
    with pytest.raises(ContestError, match="Long guns is anchored on DFT"):
        run_contest(_args("--active", "Fearghas", "Long guns", "AGI", "AGI", "ITU", *DODGE),
                    ScriptedDice(*[1] * 6))
    with pytest.raises(ContestError, match="Evasion is anchored on AGI"):     # either side
        run_contest(_args(*SHOOT, "--reactive", "Dekker", "Evasion", "ITU", "ITU", "NRV"),
                    ScriptedDice(*[1] * 6))
    assert not (campaign / "skill-contest.log").exists()


def test_an_improvised_skill_of_the_campaign_rolls(campaign):
    (campaign / "improvised-skills.md").write_text(
        "# Improvised skills\n\n## Ratcatching\n\n*Anchor: AGI · Status: improvised*\n\n"
        "Catching small fast things alive.\n\n- A grab: **AGI**, DFT, ITU\n", encoding="utf-8")
    args = _args("--active", "Fearghas", "ratcatching", "AGI", "DFT", "ITU",
                 "--reactive-dc", "13", "a rat")
    result = run_contest(args, ScriptedDice(5, 5, 5))
    assert result["active_total"] == 15 - 3                     # untrained until learned
    assert _log_blocks(campaign)[0]["active"]["skill"] == "Ratcatching"
    with pytest.raises(ContestError, match="Ratcatching is anchored on AGI"):
        run_contest(_args("--active", "Fearghas", "Ratcatching", "DFT", "DFT", "ITU",
                          "--reactive-dc", "13", "a rat"), ScriptedDice(5, 5, 5))


def test_an_improvised_skill_needs_an_anchor_and_a_banned_one_is_refused(campaign):
    (campaign / "improvised-skills.md").write_text(
        "## Ratcatching\nstatus: improvised\n\n## Mind reading\n*Anchor: EMP · Status: banned*\n"
        "\n## Larceny\n*Anchor: STR · Status: improvised*\n", encoding="utf-8")
    with pytest.raises(ContestError, match="Ratcatching has no anchor yet"):
        run_contest(_args("--active", "Fearghas", "Ratcatching", "AGI", "DFT", "ITU",
                          "--reactive-dc", "13", "a rat"), ScriptedDice(5, 5, 5))
    with pytest.raises(ContestError, match="'Mind reading' is banned"):
        run_contest(_args("--active", "Fearghas", "Mind reading", "DFT", "AGI", "ITU",
                          "--reactive-dc", "13", "a guard"), ScriptedDice(5, 5, 5))
    # A campaign can't redefine a canon skill: Larceny stays anchored on DFT.
    with pytest.raises(ContestError, match="Larceny is anchored on DFT"):
        run_contest(_args("--active", "Fearghas", "Larceny", "AGI", "AGI", "ITU",
                          "--reactive-dc", "13", "a lock"), ScriptedDice(5, 5, 5))
