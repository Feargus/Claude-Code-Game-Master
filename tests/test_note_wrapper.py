"""gm-note.sh: whatever isn't a subcommand is a fact to record.

So a mistyped subcommand, or the form from before 2026-11-16 with a category in
front, must be refused rather than recorded: "gm-note.sh get f1" once recorded
"f1" in a category called `get`.
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


def test_a_fact_is_recorded_and_subcommands_are_not(dcc_world):
    r = _run(dcc_world, "The drop is at dawn", "--secret")
    assert r.returncode == 0, r.stderr
    assert "[SUCCESS] Recorded fact " in r.stdout and " in " not in r.stdout.splitlines()[0]
    fid = r.stdout.split("Recorded fact ")[1].split()[0].rstrip(":")
    assert _facts(dcc_world)[-1]["id"] == fid and "category" not in _facts(dcc_world)[-1]
    before = _facts(dcc_world)
    r = _run(dcc_world, "truth", fid, "partial")
    assert r.returncode == 0 and "[PARTIAL]" in r.stdout, r.stdout + r.stderr
    r = _run(dcc_world, "find", "--text", "dawn")
    assert r.returncode == 0 and "The drop is at dawn" in r.stdout
    assert len(_facts(dcc_world)) == len(before)          # `truth` and `find` recorded nothing


def test_the_old_form_and_single_words_are_refused(dcc_world):
    before = _facts(dcc_world)
    r = _run(dcc_world, "session_events", "Wren paid off Dekker")       # a category in front
    assert r.returncode == 1 and "no category any more" in r.stderr and r.stdout == ""
    r = _run(dcc_world, "add", "lore", "The moon is a ship", "--secret")
    assert r.returncode == 1 and "no category any more" in r.stderr
    for word in ("fnd", "categories", "session_events"):     # a slip, a removed command, a category
        r = _run(dcc_world, word)
        assert r.returncode == 1 and "is one word" in r.stderr and "find" in r.stderr, word
    r = _run(dcc_world, "get", "lore")               # gone: it printed facts.json raw
    assert r.returncode == 1 and "gm-note.sh recent" in r.stderr and r.stdout == ""
    r = _run(dcc_world, "find", "--category", "lore")
    assert r.returncode != 0
    assert _facts(dcc_world) == before


def test_a_beat_or_a_development_with_a_category_is_refused(dcc_world):
    before = _facts(dcc_world)
    r = _run(dcc_world, "beat", json.dumps([{"fact": "Carl waved.", "category": "session_events"}]))
    assert r.returncode == 1 and "no category any more" in r.stderr
    r = subprocess.run(["bash", str(ROOT / "tools" / "gm-session.sh"), "world-tick",
                        json.dumps([{"fact": "It rained on Floor 3.", "category": "lore"}])],
                       capture_output=True, text=True,
                       env=dict(os.environ, GM_WORLD_STATE_BASE=dcc_world))
    assert r.returncode == 1 and "no category any more" in r.stdout + r.stderr
    assert _facts(dcc_world) == before
