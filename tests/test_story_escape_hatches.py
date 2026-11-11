"""Tests for story-escape-hatches: the code informs the GM, it never vetoes the story.

The two image locks can be skipped for the one beat where the campaign's style or
a character's stored look is deliberately wrong.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from lib.image_gen import build_prompt, save_chronicler
from lib.player_manager import PlayerManager

ROOT = Path(__file__).resolve().parent.parent


def _sheet(dcc_world):
    return json.loads(
        (Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "character.json")
        .read_text(encoding="utf-8"))


# --- image prompt locks -------------------------------------------------------

STYLE = "In the style of a Bayeux-tapestry embroidery but depicting a neon megacity"


def _campaign_with_style_and_appearance(dcc_world):
    campaign = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"
    char_path = campaign / "character.json"
    char = json.loads(char_path.read_text())
    char["look"] = {"physique": "male, late 20s, short brown hair, stubbled",
                    "style": "boxer shorts, barefoot, spiked gauntlet",
                    "presence": "scrappy"}
    char_path.write_text(json.dumps(char))
    save_chronicler(style=STYLE, campaign_dir=campaign)
    return campaign, char["identity"]["name"]


def test_both_locks_fire_by_default(dcc_world):
    campaign, name = _campaign_with_style_and_appearance(dcc_world)
    out = build_prompt(f"{name} kicks in the door", [name], campaign)
    assert "boxer shorts" in out and STYLE in out


def test_no_appearance_lock_skips_only_the_appearance(dcc_world):
    campaign, name = _campaign_with_style_and_appearance(dcc_world)
    out = build_prompt(f"{name} transformed into a crow", [name], campaign,
                       appearance_lock=False)
    assert "boxer shorts" not in out
    assert STYLE in out


def test_no_style_lock_skips_only_the_style(dcc_world):
    campaign, name = _campaign_with_style_and_appearance(dcc_world)
    out = build_prompt(f"{name} dreams of the surface", [name], campaign,
                       style_lock=False)
    assert STYLE not in out
    assert "boxer shorts" in out


def test_both_locks_off_leaves_the_prompt_untouched(dcc_world):
    campaign, name = _campaign_with_style_and_appearance(dcc_world)
    prompt = f"{name} as a stained-glass saint"
    assert build_prompt(prompt, [name], campaign,
                        style_lock=False, appearance_lock=False) == prompt
