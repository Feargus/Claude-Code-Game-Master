"""gm-note.sh routes its subcommands to note_manager.py.

Everything that isn't a subcommand is a category, so a subcommand the wrapper
forgot to route was recorded as a fact ("gm-note.sh get f1" recorded "f1" in a
category called `get`).
"""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(world, *args):
    return subprocess.run(["bash", str(ROOT / "tools" / "gm-note.sh"), *args],
                          capture_output=True, text=True,
                          env=dict(os.environ, GM_WORLD_STATE_BASE=world))


def _facts(world):
    return json.loads((Path(world) / "campaigns" / "dungeon-crawler-carl" / "facts.json")
                      .read_text(encoding="utf-8"))


def test_subcommands_are_not_recorded_as_facts(dcc_world):
    r = _run(dcc_world, "lore", "The drop is at dawn", "--secret")
    assert r.returncode == 0, r.stderr
    fid = r.stdout.split("Recorded fact ")[1].split()[0]
    before = _facts(dcc_world)
    r = _run(dcc_world, "truth", fid, "partial")
    assert r.returncode == 0 and "[PARTIAL]" in r.stdout, r.stdout + r.stderr
    r = _run(dcc_world, "find", "--category", "lore", "--text", "dawn")
    assert r.returncode == 0 and "[SECRET] The drop is at dawn" in r.stdout
    r = _run(dcc_world, "get", "lore")               # gone: it printed facts.json raw
    assert r.returncode == 1 and "gm-note.sh recent" in r.stderr and r.stdout == ""
    assert _run(dcc_world, "categories").returncode == 0
    assert set(_facts(dcc_world)) == set(before)          # no `truth` or `get` category
