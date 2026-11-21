"""Tests for the character-creation interview text (`/create-character`) and the
routes that lead to it."""

import json
import re
from pathlib import Path

from lib.schemas import validate_character

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / ".claude" / "commands" / "create-character.md"


def _cmd():
    return COMMAND.read_text(encoding="utf-8")


HYBORIAN_RULESET = {"name": "The Hyborian Age", "active_agents": []}
NEW_CHARACTER = Path(__file__).resolve().parent.parent / "lib" / "new_character.py"


def _make_world(tmp_path, slug, ruleset):
    world = tmp_path / "world-state"
    campaign = world / "campaigns" / slug
    campaign.mkdir(parents=True)
    (world / "active-campaign.txt").write_text(slug, encoding="utf-8")
    (campaign / "ruleset.json").write_text(json.dumps(ruleset), encoding="utf-8")
    return world


def _save(world, payload):
    """Run `create` against `world`."""
    import os
    import subprocess
    import sys
    return subprocess.run(
        [sys.executable, str(NEW_CHARACTER), json.dumps(payload), "--replace"],
        capture_output=True, text=True, env={**os.environ, "GM_WORLD_STATE_BASE": str(world)},
    )


def _sheet(world):
    slug = (world / "active-campaign.txt").read_text(encoding="utf-8").strip()
    return json.loads((world / "campaigns" / slug / "character.json").read_text(encoding="utf-8"))


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
    blobs = [json.loads(m.group(1)) for m in re.finditer(r"create <<'EOF'\n(\{.*?\})\nEOF", _cmd())]
    assert blobs, "expected a create example"
    for blob in blobs:
        assert "hp" not in blob and "ac" not in blob
        assert set(blob["stats"]["attributes"]) == {"STR", "AGI", "DFT", "VIG", "LOG", "ITU", "NRV", "PRS", "EMP"}
        assert set(blob["look"]) == {"physique", "style", "presence"}
        assert set(blob) - {"untrained"} <= {"identity", "look", "personality", "stats", "body",
                                             "items", "possessions"}


def test_the_death_protocol_routes_new_characters_to_the_interview():
    text = (ROOT / ".claude" / "skills" / "gm-death" / "SKILL.md").read_text(encoding="utf-8")
    swap = text[text.index("Swap in the new character"):]
    assert "/create-character" in swap and "create --replace" in swap
    assert "--canon" in swap


def test_gm_player_banner_is_kit_neutral():
    text = (ROOT / "tools" / "gm-player.sh").read_text(encoding="utf-8")
    assert "D&D Player Character Manager" not in text
    assert "Player Character Manager" in text


def test_a_sheet_without_race_or_class_saves_and_validates(tmp_path):
    world = _make_world(tmp_path, "conan-live", HYBORIAN_RULESET)
    r = _save(world, {"identity": {"name": "Nameless"},
                      "stats": {"attributes": {"STR": 14, "AGI": 11, "VIG": 13}}})
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
    assert "no rules of its own but `Standing`" in quick          # 2026-11-20: and the factions
    assert "Phase C steps 3–5" in quick and "Phase E" in quick     # frame, then the cast
    assert quick.index("**The character:** Phase D") < quick.index("**The character's world:** Phase E")
    assert "gm-session.sh opening" in quick and "/create-character" in quick


def test_the_character_comes_before_the_cast_and_brings_the_main_plot():
    """The order decided 2026-11-21: the world's frame, then the character, then
    the people and plots around them. "Someone from this world" is a role, never a
    named person (the cast doesn't exist yet and would be spoiled); the interview
    asks the character's trouble, which becomes the main plot; a faction's plot
    touches the character only indirectly."""
    commands = ROOT / ".claude" / "commands"
    interview = (commands / "create-character.md").read_text(encoding="utf-8")
    assert "**A role from this world**" in interview and "**six** roles" in interview
    assert "Never a named person" in interview and "their trouble" in interview
    new_game = (commands / "new-game.md").read_text(encoding="utf-8")
    for later in ("## PHASE D — THE CHARACTER", "## PHASE E — THE CHARACTER'S WORLD"):
        assert new_game.index("## PHASE C — THE KIT AND THE FRAME") < new_game.index(later)
    assert "touches the character only indirectly" in new_game
    assert "touches the character only indirectly" in (commands / "gm.md").read_text(encoding="utf-8")
