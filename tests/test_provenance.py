"""The log of why each consequence fired (gm-consequence.sh log)."""

import json
from pathlib import Path

from lib.consequence_manager import ConsequenceManager


def _path(dcc_world):
    return Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "consequences.json"


def test_firing_is_logged_with_its_reason(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cm.tick({"location": "Floor 3 - The Over City", "time": "day", "present_npcs": []})
    rec = next(p for p in cm.get_provenance() if p["id"] == "c3e61742")
    assert rec["reason"] and rec["fired_at"]
    stored = json.loads(_path(dcc_world).read_text(encoding="utf-8"))
    sheol = next(c for c in stored["active"] if c["id"] == "c3e61742")
    assert sheol["fired"]["reason"] == rec["reason"]          # the consequence says so too
    assert "_snapshot" not in stored                          # there is no rollback: git is the undo
