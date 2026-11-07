"""Tests for npc-innerlife-schema: additive goal/current_mood/voice/bonds.

What an NPC hides is a fact they hold, not a field (the `secret` field is gone)."""

import json
from pathlib import Path

from lib.npc_manager import NPCManager
from lib.session_manager import SessionManager


def _npcs(dcc_world):
    return Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "npcs.json"


def test_set_and_get_inner_life(dcc_world):
    cm = NPCManager(dcc_world)
    assert cm.set_inner_life("Mordecai", goal="protect the guild",
                             secret="he was once a crawler", current_mood="wary")
    il = cm.get_inner_life("Mordecai")
    assert il["goal"] == "protect the guild"
    assert "secret" not in il                       # no longer a field
    assert il["current_mood"] == "wary"


def test_defaults_for_npc_without_inner_life(dcc_world):
    il = NPCManager(dcc_world).get_inner_life("Carl")
    assert il["current_mood"] == "neutral" and il["goal"] == "" and il["bonds"] == {}


def test_get_is_read_only(dcc_world):
    before = _npcs(dcc_world).read_text(encoding="utf-8")
    NPCManager(dcc_world).get_inner_life("Carl")
    assert _npcs(dcc_world).read_text(encoding="utf-8") == before


def test_shift_mood_persists(dcc_world):
    cm = NPCManager(dcc_world)
    cm.shift_mood("Carl", "furious")
    assert NPCManager(dcc_world).get_inner_life("Carl")["current_mood"] == "furious"


def test_context_surfaces_inner_life(dcc_world):
    NPCManager(dcc_world).set_inner_life("Carl", goal="reach Floor 4", current_mood="determined")
    ctx = SessionManager(dcc_world).get_full_context()
    assert "wants: reach Floor 4" in ctx
    assert "mood: determined" in ctx


def test_inner_life_is_additive_legacy_npcs_still_load(dcc_world):
    # Existing NPCs without inner-life fields still load + keep their original data.
    data = json.loads(_npcs(dcc_world).read_text(encoding="utf-8"))
    assert "Mordecai" in data and "description" in data["Mordecai"]
