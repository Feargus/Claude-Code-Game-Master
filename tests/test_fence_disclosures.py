"""Fences become disclosures: world-tick overflow, context +N more. (A tick has no
fence: every match fires.)"""

import json
import re
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.session_manager import SessionManager
from lib.world_tick import WorldTick

REMAINDER = re.compile(r"\+\d+ more")


def _campaign(tmp_path, extra=None):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    overview = {"campaign_name": "C", "player_position": {"current_location": "Town Square"}}
    (camp / "campaign-overview.json").write_text(json.dumps(overview))
    (camp / "locations.json").write_text(json.dumps({"Town Square": {}}))
    extra = extra or {}
    for name, payload in extra.items():
        (camp / name).write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
    return str(ws), camp


def test_tick_four_matches_fires_all_four(tmp_path):
    ws, camp = _campaign(tmp_path)
    cm = ConsequenceManager(ws)
    for i in range(4):
        cm.add_consequence(
            f"payoff {i}", "at Town Square",
            trigger_type="on_location", match="Town Square")
    result = cm.tick({"location": "Town Square", "time": "day", "present_npcs": []})
    assert len({c["id"] for c in result["fired"]}) == 4
    assert all("match_reason" in c for c in result["fired"])
    data = json.loads((camp / "consequences.json").read_text(encoding="utf-8"))
    stamped = [c for c in data["active"] if c.get("fired")]
    assert len(stamped) == 4
    fired_ids = {c["id"] for c in result["fired"]}
    assert {c["id"] for c in stamped} == fired_ids


def test_world_tick_applies_five_and_warns_on_overflow(dcc_world, capsys):
    devs = [
        {"fact": "A rival crew claims Floor 3 territory"},
        {"fact": "Mordecai sends word of a new threat"},
        {"fact": "Viewer interest spikes around the party"},
        {"fact": "An old ally resurfaces"},
        {"fact": "A fifth development that exceeds the cap"},
    ]
    wt = WorldTick(dcc_world)
    applied = wt.apply(devs, cap=3)
    assert len(applied) == 5
    facts = json.loads((Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "facts.json"
                        ).read_text(encoding="utf-8"))
    assert any("fifth development" in f["fact"] for f in facts)
    err = capsys.readouterr().err
    assert "fifth development" in err
    assert "cap 3" in err
    assert len(wt.last_overflow) == 2
    assert "fifth development" in wt.last_overflow[-1]["text"]


def test_context_remainder_counts_on_every_truncated_section(tmp_path):
    """The brief cuts one list: what the character doesn't know of a plot, at
    five, with the command for the rest. Plots, terms and consequences are all
    listed; there is no --full (2026-11-15)."""
    plots = {f"Thread {i}": {"description": f"thread {i}", "kind": "main", "status": "open"}
             for i in range(8)}
    facts = [{"id": f"f{i}", "fact": f"secret fact {i}", "holders": [],
              "plots": ["Thread 0"]} for i in range(1, 8)]
    vocab = [f"term-{i}" for i in range(15)]
    bible = {"voice": {"style": "terse", "vocab": vocab,
                       "sample_passages": ["The sea remembered.", "The dead walked.",
                                           "Night kept the ledger.", "Dawn closed it."]}}
    pending = {"active": [{"id": f"c{i:02d}", "consequence": f"event {i}", "trigger": "later"}
                          for i in range(12)]}
    ws, _ = _campaign(tmp_path, extra={"plots.json": plots, "facts.json": facts,
                                       "world-bible.json": bible, "consequences.json": pending})
    ctx = SessionManager(ws).get_full_context()
    assert all(f"] Thread {i}:" in ctx for i in range(8))
    assert '+ 2 more: gm-note.sh find --plot "Thread 0" --hidden' in ctx
    assert "secret fact 7" in ctx                            # the five under the plot ...
    assert all(ctx.count(f"secret fact {i}") == 1 for i in range(1, 8))   # ... each printed once
    assert "term-14" in ctx
    assert all(f"event {i} (when: later)" in ctx for i in range(12))
    assert "Dawn closed it." not in ctx                      # three sample passages
