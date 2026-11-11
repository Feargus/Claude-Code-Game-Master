"""Tests for consequence-provenance-log: why-did-this-fire log + one-beat rollback."""

import json
from pathlib import Path

from lib.consequence_manager import ConsequenceManager


def _path(dcc_world):
    return Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "consequences.json"


def test_firing_writes_provenance(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cm.tick({"location": "Floor 3 - The Over City", "time": "day", "present_npcs": []})
    prov = cm.get_provenance()
    assert any(p["id"] == "c3e61742" for p in prov)
    rec = next(p for p in prov if p["id"] == "c3e61742")
    assert rec["reason"] and rec["fired_at"] and rec["ctx_key"]


def test_rollback_restores_pre_fire_state(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cm.tick({"location": "Floor 3 - The Over City", "time": "day", "present_npcs": []})
    after = json.loads(_path(dcc_world).read_text(encoding="utf-8"))
    sheol_after = next(c for c in after["active"] if c["id"] == "c3e61742")
    assert sheol_after.get("last_fired_key")  # stamped by the fire

    assert cm.rollback_last() is True
    restored = json.loads(_path(dcc_world).read_text(encoding="utf-8"))
    sheol_restored = next(c for c in restored["active"] if c["id"] == "c3e61742")
    assert "last_fired_key" not in sheol_restored  # back to pre-fire


def test_rollback_without_a_beat_is_safe(dcc_world):
    assert ConsequenceManager(dcc_world).rollback_last() is False
