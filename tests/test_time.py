"""Tests for in-game time: durations, derived words, and time clocks following the time."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from lib.threat_clocks import ThreatClockManager
from lib.time_manager import (
    TIMES_OF_DAY,
    TimeError,
    TimeManager,
    derive_date,
    derive_time_of_day,
    parse_duration,
    parse_time,
)

ROOT = Path(__file__).resolve().parent.parent


# --- Durations ---

@pytest.mark.parametrize("text, minutes", [
    ("10m", 10),
    ("2h", 120),
    ("1h 30m", 90),
    ("2 days", 2880),
    ("1w", 10080),
    ("3 hours and 15 minutes", 195),
])
def test_durations_become_minutes(text, minutes):
    assert parse_duration(text) == minutes


@pytest.mark.parametrize("text", ["", "soon", "10", "5 fortnights", "0m", "2h and a bit"])
def test_unreadable_durations_are_refused_not_guessed(text):
    with pytest.raises(TimeError):
        parse_duration(text)


# --- Derived words ---

@pytest.mark.parametrize("clock, word", [
    ("00:00", "Midnight"),
    ("00:59", "Midnight"),
    ("01:00", "Small hours"),
    ("04:59", "Small hours"),
    ("05:00", "Dawn"),
    ("07:00", "Morning"),
    ("10:59", "Morning"),
    ("11:00", "Noon"),
    ("13:00", "Afternoon"),
    ("17:00", "Evening"),
    ("19:00", "Dusk"),
    ("21:00", "Night"),
    ("22:59", "Night"),
    ("23:00", "Midnight"),
])
def test_time_of_day_words(clock, word):
    assert derive_time_of_day(parse_time(f"2187-10-26 {clock}")) == word


def test_date_reads_like_a_date():
    assert derive_date(datetime(2187, 10, 26)) == "Friday, 26 October 2187"


def test_unreadable_time_is_refused():
    with pytest.raises(TimeError):
        parse_time("late October")


# --- Advancing a campaign ---

def test_advance_needs_a_time_to_start_from(dcc_world):
    with pytest.raises(TimeError, match="no game time yet"):
        TimeManager(dcc_world).advance(10)


def test_set_writes_the_time_and_both_words(dcc_world):
    TimeManager(dcc_world).set_time(parse_time("2187-10-26 19:30"))
    overview = json.loads((Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"
                           / "campaign-overview.json").read_text())
    assert overview["game_time"] == "2187-10-26T19:30"
    assert overview["time_of_day"] == "Dusk"
    assert overview["current_date"] == "Friday, 26 October 2187"


def test_a_short_walk_leaves_a_four_day_clock_alone(dcc_world):
    manager = TimeManager(dcc_world)
    manager.set_time(parse_time("2187-10-26 10:00"))
    ThreatClockManager(dcc_world).add_clock("Siege", segments=4, advance_on="time")
    assert manager.advance(parse_duration("1h")) == {}
    assert ThreatClockManager(dcc_world).get_clocks()["Siege"]["current"] == 0


def test_a_day_fills_one_segment_of_a_four_day_clock(dcc_world):
    manager = TimeManager(dcc_world)
    manager.set_time(parse_time("2187-10-26 23:30"))
    ThreatClockManager(dcc_world).add_clock("Siege", segments=4, advance_on="time")
    ThreatClockManager(dcc_world).add_clock("Rumor", segments=4, advance_on="event")
    manager.advance(parse_duration("1h"))  # crossing midnight alone is not a day
    manager.advance(parse_duration("23h"))
    clocks = ThreatClockManager(dcc_world).get_clocks()
    assert clocks["Siege"]["current"] == 1
    assert clocks["Rumor"]["current"] == 0


def test_set_moves_clocks_forward_but_never_back(dcc_world):
    manager = TimeManager(dcc_world)
    manager.set_time(parse_time("2187-10-26 10:00"))
    ThreatClockManager(dcc_world).add_clock("Siege", segments=4, advance_on="time")
    assert "Siege" in manager.set_time(parse_time("2187-10-28 10:00"))
    manager.set_time(parse_time("2187-10-26 10:00"))
    assert ThreatClockManager(dcc_world).get_clocks()["Siege"]["current"] == 2


# --- The real command ---

def _gm_time(dcc_world, *args):
    return subprocess.run(["bash", str(ROOT / "tools" / "gm-time.sh"), *args],
                          capture_output=True, text=True,
                          env={**os.environ, "GM_WORLD_STATE_BASE": str(dcc_world)})


def test_command_sets_advances_and_shows(dcc_world):
    assert _gm_time(dcc_world, "set", "2187-10-26 04:30").returncode == 0
    result = _gm_time(dcc_world, "advance", "1h", "30m")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "06:00 (Dawn), Friday, 26 October 2187" in result.stdout
    assert "06:00 (Dawn)" in _gm_time(dcc_world).stdout


def test_command_rejects_the_old_form(dcc_world):
    result = _gm_time(dcc_world, "Dusk", "Day of Ash")
    assert result.returncode == 1
    assert "Usage" in result.stdout


def test_command_explains_a_bad_duration(dcc_world):
    _gm_time(dcc_world, "set", "2187-10-26 04:30")
    result = _gm_time(dcc_world, "advance", "a while")
    assert result.returncode == 1
    assert "Can't read the duration" in result.stderr


def test_every_derived_word_is_a_valid_time_of_day():
    from lib.validators import Validators
    for _, word in TIMES_OF_DAY:
        assert Validators.validate_time_of_day(word)[0], word
