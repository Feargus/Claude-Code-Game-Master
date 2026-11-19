"""Tests for bible-confirm-gate: a freshly drafted world isn't playable until approved."""

import json
from pathlib import Path

from lib.world_bible import WorldBible


def _bible_path(dcc_world):
    return Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "world-bible.json"


def test_legacy_bible_without_flag_is_playable(dcc_world):
    # The hand-authored DCC bible has no `confirmed` flag -> treated as confirmed.
    wb = WorldBible(dcc_world)
    assert wb.is_confirmed() is True and wb.is_playable() is True


def test_freshly_drafted_world_is_gated(dcc_world):
    p = _bible_path(dcc_world)
    data = json.loads(p.read_text(encoding="utf-8"))
    data["confirmed"] = False  # simulate a fresh auto-draft
    p.write_text(json.dumps(data), encoding="utf-8")
    wb = WorldBible(dcc_world)
    assert wb.is_confirmed() is False
    assert wb.is_playable() is False


def test_confirm_makes_it_playable(dcc_world):
    p = _bible_path(dcc_world)
    data = json.loads(p.read_text(encoding="utf-8"))
    data["confirmed"] = False
    p.write_text(json.dumps(data), encoding="utf-8")

    wb = WorldBible(dcc_world)
    assert wb.confirm() is True
    assert WorldBible(dcc_world).is_playable() is True  # reload -> confirmed persisted


def test_review_summary_presents_the_draft(dcc_world):
    s = WorldBible(dcc_world).review_summary()
    assert s["name"] == "Dungeon Crawler Carl"
    assert s["voice_style"] and s["factions"] and s["rules"] == []
    from lib import world_rules
    from lib.json_ops import JsonOperations
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    world_rules.define(ops, [{"name": "Viewers", "block": "counter", "held_by": "player",
                              "range": [0, 10], "summary": "The audience.", "when": "Spectacle."}])
    assert WorldBible(dcc_world).review_summary()["rules"] == ["Viewers"]


def test_no_bible_is_playable(tmp_path):
    # A campaign with no world-bible (e.g. /new-game) has nothing to confirm.
    import shutil
    src = Path(__file__).resolve().parent / "fixtures" / "world-state"
    dest = tmp_path / "world-state"
    shutil.copytree(src, dest)
    (dest / "campaigns" / "dungeon-crawler-carl" / "world-bible.json").unlink()
    assert WorldBible(str(dest)).is_playable() is True
