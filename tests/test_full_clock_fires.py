"""Tests for full-clock-fires.

A threat clock stores what happens when the countdown runs out. At runtime that
text was only ever echoed in a print, so a filled clock was a line the GM might
notice rather than a beat that arrived. These assert it fires into the
consequence engine exactly once.
"""

from datetime import datetime

from lib.consequence_manager import ConsequenceManager
from lib.threat_clocks import ThreatClockManager
from lib.time_manager import TimeManager

DOOM = "The floor collapses and the level is lost."


def _active(world):
    data = ConsequenceManager(world).json_ops.load_json("consequences.json") or {}
    return [c.get("consequence", "") for c in data.get("active", [])]


def _fired(world, needle=DOOM):
    return [c for c in _active(world) if needle in c]


def test_filling_a_clock_fires_its_consequence(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Floor Collapse", 2, advance_on="event", consequence=DOOM)
    m.advance("Floor Collapse")
    assert _fired(dcc_world) == []  # not full yet

    m.advance("Floor Collapse")
    fired = _fired(dcc_world)
    assert len(fired) == 1
    assert "[Clock — Floor Collapse]" in fired[0]


def test_a_full_clock_does_not_fire_twice(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Floor Collapse", 1, advance_on="event", consequence=DOOM)
    m.advance("Floor Collapse")
    m.advance("Floor Collapse")
    m.advance("Floor Collapse")
    m.update_time_clocks(datetime(2200, 1, 1))
    assert len(_fired(dcc_world)) == 1


def test_time_passing_fires_the_clock_it_fills(dcc_world):
    TimeManager(dcc_world).set_time(datetime(2187, 10, 26, 10, 0))
    m = ThreatClockManager(dcc_world)
    m.add_clock("Pulse", 1, advance_on="time", consequence=DOOM)
    m.update_time_clocks(datetime(2187, 10, 27, 10, 0))
    assert len(_fired(dcc_world)) == 1
    m.update_time_clocks(datetime(2187, 10, 28, 10, 0))
    assert len(_fired(dcc_world)) == 1


def test_clock_without_a_consequence_fires_nothing(dcc_world):
    m = ThreatClockManager(dcc_world)
    before = len(_active(dcc_world))
    m.add_clock("Quiet Countdown", 1, advance_on="event")
    m.advance("Quiet Countdown")
    assert len(_active(dcc_world)) == before


def test_reset_below_full_lets_it_fire_again(dcc_world):
    """A recurring countdown must be able to run out more than once."""
    m = ThreatClockManager(dcc_world)
    m.add_clock("Pulse", 1, advance_on="event", consequence=DOOM)
    m.advance("Pulse")
    assert len(_fired(dcc_world)) == 1

    clocks = m._load()
    clocks["Pulse"]["current"] = 0
    m.json_ops.save_json(m.clocks_file, clocks)
    m.advance("Pulse")
    assert len(_fired(dcc_world)) == 2


def test_cli_add_accepts_a_consequence(dcc_world):
    """add_clock always took one; the parser could not pass it."""
    m = ThreatClockManager(dcc_world)
    m.add_clock("Seeded", 3, consequence=DOOM, linked_plot="The Descent")
    stored = m.get_clocks()["Seeded"]
    assert stored["consequence"] == DOOM
    assert stored["linked_plot"] == "The Descent"


def test_firing_keeps_stdout_parseable(dcc_world, capsys):
    """The fire happens inside advance/a time update, whose --json output is parsed."""
    m = ThreatClockManager(dcc_world)
    m.add_clock("Doom", 1, advance_on="event", consequence=DOOM)
    capsys.readouterr()
    m.advance("Doom")
    out = capsys.readouterr()
    assert out.out.strip() == "", f"fire leaked onto stdout: {out.out!r}"
    assert "[Clock — Doom]" in out.err


def test_the_clocks_consequence_fires_at_once_and_does_not_wait(dcc_world):
    """It used to be saved with a free-text trigger, i.e. waiting on an event that
    had already happened; every fact recorded afterwards asked about it."""
    m = ThreatClockManager(dcc_world)
    m.add_clock("Doom", 2, advance_on="event", consequence=DOOM)
    m.advance("Doom")
    fired = m.advance("Doom")["fired"]
    assert len(fired) == 1 and DOOM in fired[0]["consequence"]
    assert fired[0]["match_reason"] == "clock Doom reached 2/2"
    cm = ConsequenceManager(dcc_world)
    assert not any(DOOM in c["consequence"] for c in cm.waiting_on_event())
