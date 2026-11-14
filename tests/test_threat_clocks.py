"""Tests for threat-clocks-choice-beats: named segmented pressure clocks."""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from lib.session_manager import SessionManager
from lib.threat_clocks import ThreatClockManager
from lib.time_manager import TimeManager, parse_time


def _active(dcc_world):
    p = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "consequences.json"
    return json.loads(p.read_text(encoding="utf-8")).get("active", [])


def test_filled_clock_is_a_pending_beat(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Doom", 2, advance_on="event")
    assert m.pending_beats() == {}
    m.advance("Doom", 2)
    assert "Doom" in m.pending_beats()


def test_add_advance_and_fill(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Floor Collapse", segments=4, advance_on="event")
    assert not m.is_full("Floor Collapse")
    m.advance("Floor Collapse", 3)
    assert not m.is_full("Floor Collapse")
    m.advance("Floor Collapse", 5)  # clamps at max
    c = m.get_clocks()["Floor Collapse"]
    assert c["current"] == 4
    assert m.is_full("Floor Collapse")
    assert "Floor Collapse" in m.full_clocks()


def test_advance_unknown_clock_returns_none(dcc_world):
    assert ThreatClockManager(dcc_world).advance("nope") is None


def test_remove_clock(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Doom", 6)
    assert m.remove_clock("Doom") is True
    assert "Doom" not in m.get_clocks()


def test_no_clocks_is_valid_tone_respecting(dcc_world):
    # A campaign that wants no doom clock simply has none.
    assert ThreatClockManager(dcc_world).get_clocks() == {}


def test_clocks_surface_in_session_context(dcc_world):
    ThreatClockManager(dcc_world).add_clock("Floor Collapse", segments=4, advance_on="event")
    ThreatClockManager(dcc_world).advance("Floor Collapse", 2)
    ctx = SessionManager(dcc_world).get_full_context()
    assert "THREAT CLOCKS" in ctx
    assert "Floor Collapse" in ctx and "2/4" in ctx


def _start_time(dcc_world, text="2187-10-26 10:00"):
    TimeManager(dcc_world).set_time(parse_time(text))
    return parse_time(text)


def test_time_clock_fills_evenly_until_due(dcc_world):
    now = _start_time(dcc_world)
    m = ThreatClockManager(dcc_world)
    m.add_clock("Siege", segments=4, due_in_minutes=4 * 24 * 60)
    assert m.update_time_clocks(now + timedelta(hours=23)) == {}
    assert "Siege" in m.update_time_clocks(now + timedelta(days=1))
    assert m.get_clocks()["Siege"]["current"] == 1
    m.update_time_clocks(now + timedelta(days=2, hours=12))
    assert m.get_clocks()["Siege"]["current"] == 2
    m.update_time_clocks(now + timedelta(days=4))
    assert m.is_full("Siege")


def test_update_leaves_event_clocks_alone(dcc_world):
    now = _start_time(dcc_world)
    m = ThreatClockManager(dcc_world)
    m.add_clock("Ritual", segments=3, advance_on="event")
    assert m.update_time_clocks(now + timedelta(weeks=5)) == {}
    assert m.get_clocks()["Ritual"]["current"] == 0
    assert "due_at" not in m.get_clocks()["Ritual"]


def test_default_due_time_is_one_day_per_segment(dcc_world):
    _start_time(dcc_world)
    m = ThreatClockManager(dcc_world)
    m.add_clock("Siege", segments=3)
    assert m.get_clocks()["Siege"]["starts_at"] == "2187-10-26T10:00"
    assert m.get_clocks()["Siege"]["due_at"] == "2187-10-29T10:00"


def test_due_at_a_fixed_time(dcc_world):
    _start_time(dcc_world)
    m = ThreatClockManager(dcc_world)
    m.add_clock("Auction", segments=2, due_at=parse_time("2187-10-26 20:00"))
    assert m.get_clocks()["Auction"]["due_at"] == "2187-10-26T20:00"


def test_due_in_needs_a_game_time(dcc_world):
    with pytest.raises(ValueError, match="no game time"):
        ThreatClockManager(dcc_world).add_clock("Siege", segments=4, due_in_minutes=60)


def test_an_old_clock_gets_one_day_per_empty_segment(dcc_world):
    """Clocks from before the wall clock: 3 of 4 filled means full one day from now."""
    m = ThreatClockManager(dcc_world)
    m.json_ops.save_json(m.clocks_file, {"Old": {"current": 3, "max": 4, "advance_on": "time"}})
    now = parse_time("2187-10-26 04:30")
    assert m.update_time_clocks(now) == {}
    clock = m.get_clocks()["Old"]
    assert (clock["current"], clock["starts_at"], clock["due_at"]) == (
        3, "2187-10-23T04:30", "2187-10-27T04:30")
    m.update_time_clocks(now + timedelta(days=1))
    assert m.is_full("Old")


def test_clocks_never_empty_when_time_goes_back(dcc_world):
    now = _start_time(dcc_world)
    m = ThreatClockManager(dcc_world)
    m.add_clock("Siege", segments=4)
    m.update_time_clocks(now + timedelta(days=2))
    m.update_time_clocks(now)
    assert m.get_clocks()["Siege"]["current"] == 2


def test_a_full_clock_stays_out_of_updates(dcc_world):
    now = _start_time(dcc_world)
    m = ThreatClockManager(dcc_world)
    m.add_clock("Doom", segments=1)
    assert "Doom" in m.update_time_clocks(now + timedelta(days=1))
    # A full clock is a pending beat, not a re-ticking counter.
    assert "Doom" not in m.update_time_clocks(now + timedelta(days=9))


def test_context_shows_when_a_time_clock_is_due(dcc_world):
    _start_time(dcc_world)
    ThreatClockManager(dcc_world).add_clock("Siege", segments=4)
    ctx = SessionManager(dcc_world).get_full_context()
    assert "Siege: [○○○○] 0/4, due 10:00, Tuesday, 30 October 2187" in ctx


def test_a_clock_needs_a_segment_and_a_known_mode(dcc_world):
    m = ThreatClockManager(dcc_world)
    for bad in ({"segments": 0}, {"segments": -2}, {"segments": 3, "advance_on": "events"}):
        with pytest.raises(ValueError):
            m.add_clock("Bad", **bad)
    assert "Bad" not in m.get_clocks()


def test_a_time_clock_is_not_advanced_by_hand(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Eviction", 4)
    with pytest.raises(ValueError, match="time clock"):
        m.advance("Eviction")
    assert m.get_clocks()["Eviction"]["current"] == 0
    m.add_clock("Hunt", 4, advance_on="event")
    with pytest.raises(ValueError):
        m.advance("Hunt", 0)


def test_clocks_are_listed_most_urgent_first():
    """Full first, then time clocks by due time, then event clocks, fullest first;
    the brief and gm-clock.sh used to list them in the order they were made."""
    from lib.threat_clocks import ThreatClockManager
    clocks = {
        "Foreclosure": {"current": 3, "max": 4, "advance_on": "time", "due_at": "2187-10-27T04:30"},
        "Vendetta": {"current": 1, "max": 4, "advance_on": "event"},
        "Slow scrub": {"current": 0, "max": 4, "advance_on": "time", "due_at": "2187-10-26T07:15"},
        "Tracker": {"current": 2, "max": 3, "advance_on": "event"},
        "Raid": {"current": 2, "max": 2, "advance_on": "time", "due_at": "2187-10-26T05:00"},
    }
    order = [name for name, _ in ThreatClockManager.by_urgency(clocks)]
    assert order == ["Raid", "Slow scrub", "Foreclosure", "Tracker", "Vendetta"]
    assert ThreatClockManager.render(clocks).splitlines()[0].startswith("Raid:")


def test_adding_a_clock_twice_is_refused_and_keeps_its_progress(dcc_world):
    """`gm-clock.sh add` with an existing name silently replaced the clock, so a
    clock at 3/4 was back at 0/4. The name is compared without regard to case."""
    m = ThreatClockManager(dcc_world)
    m.add_clock("Hunt", 4, advance_on="event")
    m.advance("Hunt", 3)
    with pytest.raises(ValueError, match="exists already"):
        m.add_clock("hunt", 6, advance_on="event")
    assert m.get_clocks() == {"Hunt": {"current": 3, "max": 4, "advance_on": "event"}}


def test_a_clock_has_a_short_name_and_a_text(dcc_world):
    """The name is the key triggers and commands use; what the clock is about is
    its text. A description as the name is refused, and says where it goes."""
    m = ThreatClockManager(dcc_world)
    with pytest.raises(ValueError, match="short key"):
        m.add_clock("Slow scrub (stops if the flush needle is removed)", 4)
    with pytest.raises(ValueError, match="short key"):
        m.add_clock("Hunt:2", 4)
    m.add_clock("Slow  scrub", 4, advance_on="event",
                text="Stops if the flush needle is removed with fine tools")
    clock = m.get_clocks()["Slow scrub"]
    assert clock["text"] == "Stops if the flush needle is removed with fine tools"
    assert "Slow scrub: [○○○○] 0/4 (on event) — Stops if the flush" in m.render(m.get_clocks())


def test_a_clock_is_found_by_its_name_in_any_case_or_by_its_text(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Tracker", 3, advance_on="event", text="The tracker closes in")
    assert m.advance("tracker")["current"] == 1
    assert m.advance("clock:Tracker")["current"] == 2
    assert m.advance("The tracker closes in")["current"] == 3
    assert m.is_full("TRACKER")
    assert m.advance("Trakcer") is None


def test_rewording_a_clock_keeps_its_name_and_its_progress(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Tracker", 3, advance_on="event", text="The tracker closes in")
    m.advance("Tracker")
    m.set_text("tracker", "The tracker has the scent")
    assert m.get_clocks() == {"Tracker": {"text": "The tracker has the scent", "current": 1,
                                          "max": 3, "advance_on": "event"}}
    m.set_text("Tracker", "")
    assert "text" not in m.get_clocks()["Tracker"]
    with pytest.raises(ValueError):
        m.set_text("Nobody", "x")
