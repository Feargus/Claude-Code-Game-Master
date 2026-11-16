"""Fact lookups stay short: 10 by default, and a longer list ends with how to
narrow it (2026-11-15)."""

import subprocess
from pathlib import Path

from lib.note_manager import NoteManager

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def _run(*args):
    return subprocess.run(["bash", str(TOOLS / "gm-note.sh"), *args], capture_output=True, text=True)


def test_long_lists_say_how_to_narrow_them(isolated_world_state):
    subprocess.run(["bash", str(TOOLS / "gm-campaign.sh"), "create", "t"], capture_output=True)
    subprocess.run(["bash", str(TOOLS / "gm-campaign.sh"), "switch", "t"], capture_output=True)
    notes = NoteManager()
    for i in range(12):
        notes.add_fact(f"Thing {i} happened.", holders=["player"])
    recent = _run("recent").stdout.strip().splitlines()
    assert len(recent) == 11 and recent[-1].startswith("+2 older: narrow it with gm-note.sh find --about")
    found = _run("find", "--text", "happened").stdout.strip().splitlines()
    assert len(found) == 11 and found[-1] == "+2 more: add another filter, or --limit 0 for all"
    assert len(_run("find", "--text", "happened", "--limit", "0").stdout.strip().splitlines()) == 12
