"""Pending consequences show their effects (what the script does when one fires),
in the brief and in gm-consequence.sh check, so the GM sees that a firing starts a
clock or spreads a fact before deciding anything about it."""

import subprocess
import sys
from pathlib import Path

from lib.consequence_manager import ConsequenceManager, describe_effects
from lib.note_manager import NoteManager
from lib.session_manager import SessionManager

ROOT = Path(__file__).resolve().parent.parent


def test_describe_effects():
    assert describe_effects(None) == ""
    assert describe_effects([{"type": "start_clock", "name": "Vendetta", "segments": 3,
                              "on": "event", "consequence": "The brothers come"}]) == (
        "starts clock 'Vendetta' (3 segments, advanced by hand), "
        "and when it is full: The brothers come")
    assert describe_effects([{"type": "start_clock", "name": "Fork", "segments": 4,
                              "on": "time", "due_in": "1d"}]) == (
        "starts clock 'Fork' (4 segments, full 1d after it fires)")
    assert describe_effects([{"type": "start_clock", "name": "Raid", "segments": 1,
                              "on": "time", "due": "2187-10-27 04:00"}]) == (
        "starts clock 'Raid' (1 segment, full at 2187-10-27 04:00)")
    assert describe_effects([{"type": "start_clock", "name": "Slow", "segments": 2,
                              "on": "time"}]) == (
        "starts clock 'Slow' (2 segments, full 2 days after it fires)")
    assert describe_effects([{"type": "tell", "fact": "f42", "holders": ["npc:Wren", "street"]},
                             {"type": "start_clock", "name": "X", "segments": 1, "on": "event"}]) == (
        "tells f42 to npc:Wren, street; starts clock 'X' (1 segment, advanced by hand)")


def test_brief_and_check_show_effects(dcc_world):
    fid = NoteManager(dcc_world).add_fact("plot_local", "The vault code is 4471.", secret=True)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence(
        "The crew hears of the job", "the job goes loud",
        effects=[{"type": "start_clock", "name": "Vendetta", "segments": 3, "on": "event"},
                 {"type": "tell", "fact": fid, "holders": ["street"]}])
    then = (f"when it fires, starts clock 'Vendetta' (3 segments, advanced by hand); "
            f"tells {fid} to street")
    assert then in SessionManager(dcc_world).get_full_context()
    out = subprocess.run([sys.executable, str(ROOT / "lib" / "consequence_manager.py"), "check"],
                         capture_output=True, text=True, cwd=str(Path(dcc_world).parent)).stdout
    assert f"[{cid}]" in out and then in out
