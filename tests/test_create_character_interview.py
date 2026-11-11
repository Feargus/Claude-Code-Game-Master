"""Tests for the character-creation interview text (`/create-character`) and the
routes that lead to it."""

import json
import re
from pathlib import Path

from lib.schemas import validate_character

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
    for heading in ("## Who", "## The default character", "## The entries", "## Save"):
        assert heading in text
    assert "gm-player.sh create" in text and "--canon" in text and "--replace" in text
    assert "save-json" not in text and "onboard" not in text


def test_the_interview_suggests_defaults_but_never_forces_them():
    """The user's defaults (2026-11-11): the GM knows the numbers and improvises
    within ±20%; fast is the default, slow goes entry by entry."""
    text = _cmd()
    assert "d12" in text and "d18" not in text
    assert "whatever they want" in text and "±20%" in text
    assert "Fast (the default)" in text and "Slow" in text
    assert "you offer 3, the player picks 1 or 2" in text
    assert "you offer 4, the player picks 2" in text


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
    ok, errs = validate_character(_sheet(world))
    assert ok, errs


def test_a_new_campaign_asks_how_to_make_the_world():
    """The user's flow (2026-11-11): the world together, from one sentence (setting
    and lore only, the repo's rules) or from a book; then the character fast or
    slow. The one-shot (which saved the character before its campaign existed) and
    the import's "no one yet" are gone."""
    commands = ROOT / ".claude" / "commands"
    gm = (commands / "gm.md").read_text(encoding="utf-8")
    assert "How do we make the world?" in gm and "From one sentence" in gm
    assert "ONE-SHOT" not in gm and "one-shot" not in gm.lower()
    assert "no one yet" not in (commands / "import.md").read_text(encoding="utf-8")
    new_game = (commands / "new-game.md").read_text(encoding="utf-8")
    quick = new_game[new_game.index("## QUICK WORLD"):]
    assert '"signature_systems": []' in quick and "no `ruleset.json`" in quick
    assert "gm-session.sh opening" in quick and "/create-character" in quick
