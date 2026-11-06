"""gm-clock.sh due: move a time clock's due time.

The start stays and the clock is recomputed at once: brought forward it may
fill (and fire) now; pushed back it keeps what it has and waits, since clocks
never empty.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from lib.consequence_manager import ConsequenceManager
from lib.threat_clocks import ThreatClockManager
from lib.time_manager import TimeManager

NOW = datetime(2187, 10, 26, 6, 0)


@pytest.fixture
def tcm(dcc_world):
    TimeManager(dcc_world).set_time(NOW)
    m = ThreatClockManager(dcc_world)
    m.add_clock("Foreclosure", 4, due_in_minutes=4 * 24 * 60)  # one segment a day
    return m


def _clock(m):
    return m.get_clocks()["Foreclosure"]


def test_earlier_and_later_shift_the_due_time(tcm):
    tcm.move_due("Foreclosure", shift_minutes=-24 * 60)
    assert _clock(tcm)["due_at"] == "2187-10-29T06:00"
    tcm.move_due("Foreclosure", shift_minutes=12 * 60)
    assert _clock(tcm)["due_at"] == "2187-10-29T18:00"
    assert _clock(tcm)["starts_at"] == "2187-10-26T06:00"


def test_due_in_counts_from_now_and_due_is_absolute(tcm):
    tcm.move_due("Foreclosure", due_in_minutes=6 * 60)
    assert _clock(tcm)["due_at"] == "2187-10-26T12:00"
    tcm.move_due("Foreclosure", due_at=datetime(2187, 11, 1, 8, 0))
    assert _clock(tcm)["due_at"] == "2187-11-01T08:00"


def test_bringing_it_forward_fills_and_fires_at_once(tcm, dcc_world):
    TimeManager(dcc_world).set_time(datetime(2187, 10, 27, 6, 0))  # 1/4
    cid = ConsequenceManager(dcc_world).add_consequence(
        "Bailiffs at the door", "x", trigger_type="on_clock", match="Foreclosure:2")
    # Started a day ago; now due in one more day, so it is half done: 2/4.
    out = tcm.move_due("Foreclosure", due_in_minutes=24 * 60)
    assert out["current"] == 2
    assert [c["id"] for c in out["fired"]] == [cid]
    # Due time already passed: full on the spot.
    out = tcm.move_due("Foreclosure", due_at=datetime(2187, 10, 27, 0, 0))
    assert out["current"] == 4


def test_pushing_it_back_never_empties_it(tcm, dcc_world):
    TimeManager(dcc_world).set_time(datetime(2187, 10, 28, 6, 0))  # 2/4
    out = tcm.move_due("Foreclosure", shift_minutes=30 * 24 * 60)
    assert out["current"] == 2 and out["fired"] == []


def test_refusals(tcm, dcc_world):
    with pytest.raises(ValueError, match="exactly one"):
        tcm.move_due("Foreclosure")
    with pytest.raises(ValueError, match="exactly one"):
        tcm.move_due("Foreclosure", due_in_minutes=60, shift_minutes=60)
    with pytest.raises(ValueError, match="No clock"):
        tcm.move_due("Nope", shift_minutes=60)
    with pytest.raises(ValueError, match="before that"):
        tcm.move_due("Foreclosure", due_at=datetime(2187, 10, 25, 0, 0))
    tcm.add_clock("Hunt", 3, advance_on="event")
    with pytest.raises(ValueError, match="event clock"):
        tcm.move_due("Hunt", shift_minutes=60)
    tcm.move_due("Foreclosure", due_at=datetime(2187, 10, 26, 7, 0))
    TimeManager(dcc_world).set_time(datetime(2187, 10, 26, 8, 0))
    with pytest.raises(ValueError, match="already full"):
        tcm.move_due("Foreclosure", shift_minutes=60)


def test_cli(tcm, dcc_world):
    root = Path(__file__).resolve().parent.parent
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(root / "lib" / "threat_clocks.py"), "due", "Foreclosure", *a],
        capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    r = run("--earlier", "1d")
    assert r.returncode == 0, r.stderr
    assert "Foreclosure: [○○○○] 0/4" in r.stdout and "due 06:00" in r.stdout
    r = run("--earlier", "1d", "--later", "2h")
    assert r.returncode == 1 and "exactly one" in r.stderr
    r = run("--json", "--later", "1d")
    assert json.loads(r.stdout)["data"]["due_at"] == "2187-10-30T06:00"
