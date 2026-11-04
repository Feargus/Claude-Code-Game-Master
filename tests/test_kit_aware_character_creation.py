"""Tests for character creation: one path for every world (no D&D branch); saves
warn on the 10/10 HP fallback and do not require 5e race/class.
"""

import json
import re
from pathlib import Path

from lib.schemas import validate_character
from lib.world_kit import WorldKit

from tests.test_kit_vitals import (
    CONAN,
    HYBORIAN_RULESET,
    _make_world,
    _save,
    _sheet,
)

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / ".claude" / "commands" / "create-character.md"
AGENT = ROOT / ".claude" / "agents" / "create-character.md"
VA_KEYS = (
    "sex", "age", "race", "species", "hair", "face", "eyes",
    "clothing", "gear", "demeanor", "size",
)

# Live Conan bug: ruleset has NO kit field.
CONAN_LIVE_RULESET = {k: v for k, v in HYBORIAN_RULESET.items() if k != "kit"}


def _cmd():
    return COMMAND.read_text(encoding="utf-8")


def _agent():
    return AGENT.read_text(encoding="utf-8")


def _section(text, start, end):
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def _generic(text):
    return _section(text, "## Steps", "## Shared")


def _save_json_blobs(text):
    blobs = []
    for m in re.finditer(r"save-json '(\{.*?\})'", text):
        blobs.append(json.loads(m.group(1)))
    return blobs


def test_command_and_agent_have_one_path_and_no_dnd5e_branch():
    for text in (_cmd(), _agent()):
        assert "## Steps" in text
        assert "dnd5e branch" not in text
        assert "stat_schema" in _generic(text)
        assert "attributes" in _generic(text)
        assert "vitals" in _generic(text)


def test_generic_spine_never_mentions_5e_races_classes_or_spell_slots():
    for text in (_cmd(), _agent()):
        generic = _generic(text).lower()
        assert "spell slot" not in generic
        assert "spell slots" not in generic
        assert "hit die" not in generic
        assert "get_races.py" not in generic
        assert "get_classes.py" not in generic
        assert "get_spells.py" not in generic
        assert "cantrip" not in generic
        assert "standard array" not in generic
        assert "point buy" not in generic


def test_no_ascii_art_or_ascii_interface_mandate():
    for text in (_cmd(), _agent()):
        lower = text.lower()
        assert "ascii interface" not in lower
        assert "ascii art" not in lower
        assert "ascii-art" not in lower
        assert "phone-friendly" in lower


def test_save_json_examples_include_hp_and_visual_appearance():
    for text in (_cmd(), _agent()):
        blobs = _save_json_blobs(text)
        assert blobs, "expected at least one save-json JSON example"
        for blob in blobs:
            assert "hp" in blob, blob.keys()
            va = blob.get("visual_appearance")
            assert isinstance(va, dict), blob.keys()
            for key in VA_KEYS:
                assert key in va, key


def test_claude_md_death_protocol_routes_new_character_kit_aware():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = text.index("SWAP")
    swap = text[start:text.index("## Action Router", start)]
    assert "create-character" in swap
    assert "kit-aware" in swap.lower()
    assert "5e wizard" in swap.lower()


def test_gm_player_banner_is_kit_neutral():
    text = (ROOT / "tools" / "gm-player.sh").read_text(encoding="utf-8")
    assert "D&D Player Character Manager" not in text
    assert "Player Character management for D&D campaign" not in text
    assert "Player Character Manager" in text


def test_custom_kit_sheet_without_race_class_saves_and_validates(tmp_path):
    world = _make_world(tmp_path, "conan-live", CONAN_LIVE_RULESET)

    payload = {
        "name": "Nameless",
        "level": 1,
        "attributes": {"might": 14, "guile": 11, "grit": 13},
        "hp": {"current": 20, "max": 20},
    }
    r = _save(world, payload)
    assert r.returncode == 0, r.stdout + r.stderr
    sheet = _sheet(world)
    ok, errs = validate_character(sheet, WorldKit(str(world)))
    assert ok, errs


def test_save_warnings_on_10_10_fallback(tmp_path):
    world = _make_world(tmp_path, "conan-live", CONAN_LIVE_RULESET)
    payload = {k: v for k, v in CONAN.items() if k != "hp"}
    # No race/class either — custom kit must not require them.
    payload.pop("race", None)
    payload.pop("class", None)
    r = _save(world, payload)
    assert r.returncode == 0, r.stdout + r.stderr
    result = json.loads(r.stdout)
    assert _sheet(world)["hp"] == {"current": 10, "max": 10}
    warnings = result["warnings"]
    assert isinstance(warnings, list) and warnings
    assert any("10/10" in w for w in warnings)
