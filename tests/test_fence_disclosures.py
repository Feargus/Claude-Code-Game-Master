"""Fences become disclosures: tick remainder, world-tick overflow, context +N more."""

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


def test_tick_four_matches_fires_two_discloses_two(tmp_path):
    ws, camp = _campaign(tmp_path)
    cm = ConsequenceManager(ws)
    for i in range(4):
        cm.add_consequence(
            f"payoff {i}", "at Town Square",
            trigger_type="on_location", match="Town Square")
    result = cm.tick({"location": "Town Square", "time": "day", "present_npcs": []})
    assert len(result["fired"]) == 2
    assert len(result["disclosed"]) == 2
    reported = result["fired"] + result["disclosed"]
    assert len({c["id"] for c in reported}) == 4
    assert all("match_reason" in c for c in reported)
    data = json.loads((camp / "consequences.json").read_text(encoding="utf-8"))
    stamped = [c for c in data["active"] if c.get("last_fired_key")]
    assert len(stamped) == 2
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
    assert any("fifth development" in f["fact"] for f in facts["plot_local"])
    err = capsys.readouterr().err
    assert "fifth development" in err
    assert "cap 3" in err
    assert len(wt.last_overflow) == 2
    assert "fifth development" in wt.last_overflow[-1]["text"]


def test_context_remainder_counts_on_every_truncated_section(tmp_path):
    plots = {f"Thread {i}": {"name": f"Thread {i}", "type": "side", "status": "active"}
             for i in range(8)}
    facts = {"plot_local": [{"fact": f"local fact {i}"} for i in range(5)]}
    vocab = [f"term-{i}" for i in range(15)]
    npcs = {
        "Hero": {
            "identity": {"name": "Hero", "role": "the PC's shadow"},
            "status": {"party_member": True},
        }
    }
    bible = {
        "voice": {
            "style": "terse",
            "vocab": vocab,
            "sample_passages": ["The sea remembered.", "The dead walked.",
                                "Night kept the ledger.", "Dawn closed it."],
        }
    }
    sessions = []
    for i in range(5):
        sessions.append(
            f"## Session Started: 2026-01-0{i+1}\n"
            f"### Session Ended: 2026-01-0{i+1}\n"
            f"Session {i+1}: something happened.\n---\n"
        )
    pending = {"active": [
        {"id": f"c{i:02d}", "consequence": f"event {i}", "trigger": "later"}
        for i in range(12)
    ]}
    ws, camp = _campaign(tmp_path, extra={
        "plots.json": plots,
        "facts.json": facts,
        "npcs.json": npcs,
        "world-bible.json": bible,
        "consequences.json": pending,
    })
    (camp / "session-log.md").write_text("".join(sessions), encoding="utf-8")

    ctx = SessionManager(ws).get_full_context()
    remainders = REMAINDER.findall(ctx)
    assert remainders, "truncated context must disclose +N more"
    assert "+2 more threads" in ctx
    assert "+2 more facts" in ctx
    assert "+3 more terms" in ctx
    assert "+2 more sessions" in ctx
    assert "+2 more pending consequences" in ctx
    assert "+1 more sample passages" in ctx

    full = SessionManager(ws).get_full_context(full=True)
    assert not REMAINDER.search(full), "--full lifts every bound; no remainder lines"
