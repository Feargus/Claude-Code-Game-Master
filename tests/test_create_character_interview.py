"""Tests for the character-creation interview text (`/create-character`) and the
routes that lead to it."""

import json
import re
from pathlib import Path

from lib.schemas import validate_character
from lib.world_kit import WorldKit

from tests.test_kit_vitals import HYBORIAN_RULESET, _make_world, _save, _sheet

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / ".claude" / "commands" / "create-character.md"
VA_KEYS = ("sex", "age", "race", "species", "hair", "face", "eyes",
           "clothing", "gear", "demeanor", "size")


def _cmd():
    return COMMAND.read_text(encoding="utf-8")


def test_there_is_no_create_character_agent_any_more():
    """An agent can't interview the player; the GM runs the command itself."""
    assert not (ROOT / ".claude" / "agents" / "create-character.md").exists()


def test_the_interview_has_its_steps_and_saves_with_create():
    text = _cmd()
    for heading in ("## Start", "## Steps", "## Save"):
        assert heading in text
    assert "gm-player.sh create" in text and "--canon" in text and "--replace" in text
    assert "save-json" not in text and "onboard" not in text


def test_the_interview_suggests_defaults_but_never_forces_them():
    text = _cmd()
    assert "d12" in text and "d18" in text
    assert "whatever they want" in text


def test_no_5e_left_in_the_interview():
    lower = _cmd().lower()
    for word in ("spell slot", "hit die", "standard array", "point buy", "cantrip",
                 "get_races", "get_spells", "bonds", "ideals", "flaws"):
        assert word not in lower, word


def test_no_ascii_art_and_phone_friendly():
    lower = _cmd().lower()
    assert "phone-friendly" in lower and "ascii art" not in lower


def test_the_save_example_is_a_valid_new_sheet():
    blobs = [json.loads(m.group(1)) for m in re.finditer(r"create '(\{.*?\})'", _cmd())]
    assert blobs, "expected a create example"
    for blob in blobs:
        assert "hp" not in blob and "ac" not in blob
        assert set(blob["attributes"]) == {"STR", "AGI", "DFT", "VIG", "LOG", "ITU", "NRV", "PRS", "EMP"}
        assert all(key in blob["visual_appearance"] for key in VA_KEYS)


def test_claude_md_death_protocol_routes_new_characters_to_the_interview():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = text.index("SWAP")
    swap = text[start:text.index("## Action Router", start)]
    assert "/create-character" in swap and "create '<json>' --replace" in swap
    assert "--canon" in swap


def test_gm_player_banner_is_kit_neutral():
    text = (ROOT / "tools" / "gm-player.sh").read_text(encoding="utf-8")
    assert "D&D Player Character Manager" not in text
    assert "Player Character Manager" in text


def test_a_sheet_without_race_or_class_saves_and_validates(tmp_path):
    world = _make_world(tmp_path, "conan-live", {k: v for k, v in HYBORIAN_RULESET.items() if k != "kit"})
    r = _save(world, {"name": "Nameless", "attributes": {"STR": 14, "AGI": 11, "VIG": 13}})
    assert r.returncode == 0, r.stdout + r.stderr
    ok, errs = validate_character(_sheet(world), WorldKit(str(world)))
    assert ok, errs
