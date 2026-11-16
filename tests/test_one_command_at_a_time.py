"""Commands take turns: one at a time per campaign (tools/common.sh).

Every command reads a file, changes it and writes it back. Six `gm-note.sh`
started together used to leave five facts on disk: one command printed
[SUCCESS] for a fact that another's write had erased, and one failed because
both used the same temporary file. Claude Code starts independent commands side
by side, so this happened in play.
"""

import fcntl
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = "dungeon-crawler-carl"
COMMANDS = 12


def _start(world, tool, *args, **env):
    return subprocess.Popen(["bash", str(ROOT / "tools" / tool), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env=dict(os.environ, GM_WORLD_STATE_BASE=world, **env))


def _run(world, tool, *args, **env):
    p = _start(world, tool, *args, **env)
    out, err = p.communicate(timeout=120)
    return p.returncode, out, err


def _fact_texts(world):
    facts = json.loads((Path(world) / "campaigns" / CAMPAIGN / "facts.json")
                       .read_text(encoding="utf-8"))
    return [f["fact"] for items in facts.values() for f in items if isinstance(f, dict)]


# "flock": the program most systems have. "no-such-program": none, as on macOS,
# so lib/command_lock.py takes the lock.
@pytest.mark.parametrize("flock", ["flock", "no-such-program"])
def test_commands_started_together_all_record_their_fact(dcc_world, flock):
    started = [_start(dcc_world, "gm-note.sh", "session_events", f"At once, fact {n}.",
                      "--secret", "--nowhere", GM_FLOCK=flock) for n in range(COMMANDS)]
    results = [(p.communicate(timeout=120), p.returncode) for p in started]
    for (out, err), code in results:
        assert code == 0 and "Recorded fact" in out, out + err
    ids = [out.split("Recorded fact ")[1].split()[0] for (out, _), _ in results]
    assert len(set(ids)) == COMMANDS                            # no id given twice
    texts = _fact_texts(dcc_world)
    assert all(f"At once, fact {n}." in texts for n in range(COMMANDS))


def test_a_wrapper_that_calls_wrappers_does_not_wait_for_itself(dcc_world):
    # gm-time.sh runs gm-consequence.sh afterwards, inside its own turn.
    code, out, err = _run(dcc_world, "gm-time.sh", "set", "2187-10-26 04:30", GM_LOCK_WAIT="3")
    assert code == 0 and "Time set" in out and "REACTIVITY" in out, out + err


def test_a_command_gives_up_after_waiting_and_changes_nothing(dcc_world):
    locks = Path(dcc_world) / "locks"
    locks.mkdir(exist_ok=True)
    with open(locks / f"{CAMPAIGN}.lock", "w") as held:         # another command, still running
        fcntl.flock(held, fcntl.LOCK_EX)
        code, out, err = _run(dcc_world, "gm-note.sh", "session_events", "Never recorded.",
                              "--secret", "--nowhere", GM_LOCK_WAIT="1")
        assert code == 1 and "Another command" in err and out == "", out + err
        assert "Never recorded." not in _fact_texts(dcc_world)
        # gm-recall.sh changes no records: it neither waits nor makes others wait.
        code, out, err = _run(dcc_world, "gm-recall.sh", "status", GM_LOCK_WAIT="1")
        assert code == 0 and "Another command" not in err, out + err
    code, out, err = _run(dcc_world, "gm-note.sh", "session_events", "Recorded afterwards.",
                          "--secret", "--nowhere", GM_LOCK_WAIT="1")
    assert code == 0, out + err                                  # the lock went with its holder
