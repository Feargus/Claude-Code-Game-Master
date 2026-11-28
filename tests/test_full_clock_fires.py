"""A clock's outcome is a consequence, made with the clock and waiting on its last
segment: shown, compared, fired and resolved like any other, and it fires once,
when the clock fills. A clock only counts."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.threat_clocks import ThreatClockManager
from lib.time_manager import TimeManager

DOOM = "The floor collapses and the level is lost."
ROOT = Path(__file__).resolve().parent.parent


def _store(world):
    return ConsequenceManager(world).json_ops.load_json("consequences.json") or {}


def _doom(world):
    return [c for c in _store(world).get("active", []) if DOOM in c.get("consequence", "")]


def test_the_outcome_is_a_consequence_from_the_start(dcc_world):
    from lib.plot_manager import PlotManager
    PlotManager(dcc_world).add("Deep Descent", "Down.", another=True)
    m = ThreatClockManager(dcc_world)
    made = m.add_clock("Floor Collapse", 2, advance_on="event", consequence=DOOM,
                       plots=["Deep Descent"])
    [outcome] = _doom(dcc_world)
    assert made["outcome"] == outcome["id"] and not outcome.get("fired")
    assert outcome["triggers"] == [{"type": "on_clock", "match": "clock:Floor Collapse:2"}]
    assert outcome["plots"] == ["Deep Descent"]
    assert "consequence" not in m.get_clocks()["Floor Collapse"]     # a clock only counts


def test_filling_the_clock_fires_its_outcome_once(dcc_world):
    m = ThreatClockManager(dcc_world)
    m.add_clock("Floor Collapse", 2, advance_on="event", consequence=DOOM)
    assert m.advance("Floor Collapse")["fired"] == []                # not full yet
    fired = m.advance("Floor Collapse")["fired"]
    assert [c["consequence"] for c in fired] == [DOOM]
    assert fired[0]["match_reason"] == "clock Floor Collapse at 2/2"
    assert m.advance("Floor Collapse")["fired"] == []
    m.update_time_clocks(datetime(2200, 1, 1))
    [outcome] = _doom(dcc_world)
    assert outcome["fired"]


def test_time_passing_fires_the_clock_it_fills(dcc_world):
    TimeManager(dcc_world).set_time(datetime(2187, 10, 26, 10, 0))
    m = ThreatClockManager(dcc_world)
    m.add_clock("Pulse", 1, advance_on="time", consequence=DOOM)
    moved = m.update_time_clocks(datetime(2187, 10, 27, 10, 0))
    assert [c["consequence"] for c in moved["Pulse"]["fired"]] == [DOOM]
    assert m.update_time_clocks(datetime(2187, 10, 28, 10, 0)) == {}


def test_a_clock_without_an_outcome_makes_none(dcc_world):
    before = len(_store(dcc_world).get("active", []))
    m = ThreatClockManager(dcc_world)
    assert "outcome" not in m.add_clock("Quiet Countdown", 1, advance_on="event")
    m.advance("Quiet Countdown")
    assert len(_store(dcc_world).get("active", [])) == before


def test_making_and_filling_keep_stdout_to_the_command(dcc_world, capsys):
    """The outcome's own "Added consequence" line doesn't leak into gm-clock.sh's
    output, and a fill prints nothing by itself: the command prints the [FIRED]."""
    m = ThreatClockManager(dcc_world)
    m.add_clock("Doom", 1, advance_on="event", consequence=DOOM)
    m.advance("Doom")
    assert capsys.readouterr().out.strip() == ""


def test_removing_a_clock_removes_what_waits_on_it(dcc_world):
    m = ThreatClockManager(dcc_world)
    cm = ConsequenceManager(dcc_world)
    outcome = m.add_clock("Doom", 3, advance_on="event", consequence=DOOM)["outcome"]
    sign = cm.add_consequence("Dust falls from the ceiling", trigger_type="on_clock",
                              match="Doom:1")
    either = cm.add_consequence("The crawlers flee", triggers=[
        {"type": "on_clock", "match": "Doom:2"}, {"type": "on_time", "match": "night"}])
    gone = cm.add_consequence("A crack opens", trigger_type="on_clock", match="Doom:2")
    cm.fire(gone)                                         # what has fired stays
    assert sorted(m.remove_clock("Doom")) == sorted([outcome, sign])
    left = {c["id"]: c for c in _store(dcc_world)["active"]}
    assert outcome not in left and sign not in left and gone in left
    assert left[either]["triggers"] == [{"type": "on_time", "match": "night"}]
    assert m.remove_clock("Doom") is None


def test_the_command(dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=str(dcc_world))

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-clock.sh"), *words],
                              capture_output=True, text=True, env=env)
    made = run("add", "Doom", "2", "--on", "event", "--consequence", DOOM)
    assert made.returncode == 0, made.stderr
    [outcome] = _doom(dcc_world)
    assert made.stdout.splitlines()[0] == f"[SUCCESS] Added clock Doom, with its outcome {outcome['id']}"
    removed = run("remove", "Doom")
    assert removed.stdout.strip() == f"[SUCCESS] Removed clock Doom, and what waited on it: {outcome['id']}"
