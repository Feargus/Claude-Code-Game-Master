"""The JSON of beat, opening, world-tick and create can follow the command
(<<'EOF' ... EOF), where apostrophes need no escaping. In a '...' argument the
GM couldn't write them and dropped them ("Dolph s stockroom", 2026-11-15)."""

import subprocess
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def _run(*args, stdin=""):
    return subprocess.run(["bash", str(TOOLS / args[0]), *args[1:]], input=stdin,
                          capture_output=True, text=True)


def test_a_beat_after_the_command_keeps_its_apostrophes(isolated_world_state):
    assert _run("gm-campaign.sh", "create", "t").returncode == 0
    assert _run("gm-campaign.sh", "switch", "t").returncode == 0
    r = _run("gm-note.sh", "beat", stdin="[{\"fact\": \"Dolph's thermos rolled under Hex's counter.\"}]")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Dolph's thermos" in _run("gm-note.sh", "recent", "1").stdout
    assert _run("gm-note.sh", "beat", '[{"fact": "The argument still works."}]').returncode == 0


def test_nothing_given_says_how(isolated_world_state):
    _run("gm-campaign.sh", "create", "t")
    _run("gm-campaign.sh", "switch", "t")
    for args in (("gm-note.sh", "beat"), ("gm-session.sh", "opening"),
                 ("gm-session.sh", "world-tick"), ("gm-player.sh", "create")):
        r = _run(*args)
        assert r.returncode == 1 and "<<'EOF'" in r.stdout + r.stderr, (args, r.stdout, r.stderr)
