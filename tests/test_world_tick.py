"""Off-screen developments (/gm world): a fact each, plus optional follow-ups.

A development is something that happened, recorded as a fact. It may also set
something in motion: a consequence with a real trigger, and/or a threat clock.
The tick is all-or-nothing, warns past an advisory cap, and rolls back whole.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.world_tick import WorldTick, WorldTickError

CAMPAIGN = "dungeon-crawler-carl"


def _load(world, name):
    p = Path(world) / "campaigns" / CAMPAIGN / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _active(world):
    return _load(world, "consequences.json").get("active", [])


def _fact_texts(world):
    return [f["fact"] for items in _load(world, "facts.json").values()
            for f in items if isinstance(f, dict)]


DEVS = [
    {"fact": "Meridian has posted foreclosure notices across Level 40."},
    {"fact": "Dekker has hired a tracker who hunts the grey sleeve.",
     "consequence": {"text": "The tracker finds Fearghas",
                     "triggers": [{"type": "on_location", "match": "Old Iron's Yard"}]},
     "clock": {"name": "The tracker closes in", "segments": 3, "on": "event",
               "consequence": "The tracker finds Fearghas"}},
    {"fact": "Auntie Ro kept her stall shut for a day.", "category": "npc_relations"},
]


def test_every_development_becomes_a_fact(dcc_world):
    applied = WorldTick(dcc_world).apply(DEVS)
    assert [a["text"] for a in applied] == [d["fact"] for d in DEVS]
    facts = _load(dcc_world, "facts.json")
    assert any(f["fact"] == DEVS[0]["fact"] for f in facts["plot_local"])  # default category
    assert any(f["fact"] == DEVS[2]["fact"] for f in facts["npc_relations"])
    assert all(a["fact"].startswith("f") for a in applied)


def test_follow_ups_are_set_up(dcc_world):
    applied = WorldTick(dcc_world).apply(DEVS)
    tracker = applied[1]
    con = next(c for c in _active(dcc_world) if c["id"] == tracker["consequence"])
    assert con["triggers"] == [{"type": "on_location", "match": "Old Iron's Yard"}]
    assert tracker["clock"] == "The tracker closes in"
    assert "The tracker closes in" in _load(dcc_world, "threat-clocks.json")
    assert "consequence" not in applied[0] and "clock" not in applied[0]


def test_a_consequence_without_triggers_is_refused_and_nothing_kept(dcc_world):
    before_facts = _fact_texts(dcc_world)
    before_active = len(_active(dcc_world))
    bad = DEVS[:1] + [{"fact": "x", "consequence": {"text": "something, sometime"}}]
    with pytest.raises(WorldTickError, match="needs \"triggers\""):
        WorldTick(dcc_world).apply(bad)
    assert _fact_texts(dcc_world) == before_facts
    assert len(_active(dcc_world)) == before_active


def test_a_development_without_a_fact_is_refused(dcc_world):
    with pytest.raises(WorldTickError, match="needs a \"fact\""):
        WorldTick(dcc_world).apply([{"consequence": {"text": "x", "triggers": []}}])


def test_a_refused_trigger_undoes_the_whole_tick(dcc_world):
    """Validation passes, but add_consequence refuses the trigger: earlier parts are undone."""
    before_facts = _fact_texts(dcc_world)
    bad = DEVS[:2] + [{"fact": "y", "consequence": {
        "text": "z", "triggers": [{"type": "on_time", "match": "2187-10-27"}]}}]
    with pytest.raises(WorldTickError):
        WorldTick(dcc_world).apply(bad)
    assert _fact_texts(dcc_world) == before_facts
    assert "The tracker closes in" not in _load(dcc_world, "threat-clocks.json")


def test_cap_is_advisory(dcc_world, capsys):
    devs = [{"fact": f"development {i}"} for i in range(5)]
    wt = WorldTick(dcc_world)
    applied = wt.apply(devs, cap=3)
    assert len(applied) == 5
    err = capsys.readouterr().err
    assert "cap 3" in err and "development 4" in err
    assert len(wt.last_overflow) == 2


def test_disabled_is_a_noop(dcc_world):
    before = _fact_texts(dcc_world)
    assert WorldTick(dcc_world).apply(DEVS, enabled=False) == []
    assert _fact_texts(dcc_world) == before


def test_rollback_removes_facts_consequences_and_clocks(dcc_world):
    before_facts = _fact_texts(dcc_world)
    before_active = len(_active(dcc_world))
    wt = WorldTick(dcc_world)
    wt.apply(DEVS)
    assert wt.history()
    assert wt.rollback_last() is True
    assert _fact_texts(dcc_world) == before_facts
    assert len(_active(dcc_world)) == before_active
    assert "The tracker closes in" not in _load(dcc_world, "threat-clocks.json")


def test_rollback_without_a_tick_is_safe(dcc_world):
    assert WorldTick(dcc_world).rollback_last() is False


def test_waiting_leaves_out_the_ticks_own_consequences(dcc_world):
    wt = WorldTick(dcc_world)
    applied = wt.apply([{"fact": "a", "consequence": {
        "text": "own", "triggers": [{"type": "on_event", "match": "someone talks"}]}}])
    assert applied[0]["consequence"] not in {c["id"] for c in wt.waiting(applied)}


def _cli(world, *args):
    root = Path(__file__).resolve().parent.parent
    return subprocess.run([sys.executable, str(root / "lib" / "world_tick.py"), *args, "--json"],
                          capture_output=True, text=True, cwd=str(Path(world).parent))


def test_cli_apply_and_rollback(dcc_world):
    r = _cli(dcc_world, "apply", json.dumps([{"fact": "a rumor spreads"}]))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] and len(out["data"]["applied"]) == 1
    assert "waiting_on_event" in out["data"]
    r = _cli(dcc_world, "rollback")
    assert json.loads(r.stdout)["data"]["rolled_back"] is True


def test_cli_refusal_says_nothing_was_kept(dcc_world):
    r = _cli(dcc_world, "apply", json.dumps([{"consequence": {"text": "x"}}]))
    assert r.returncode == 1
    assert "Nothing from this tick was kept" in r.stdout
