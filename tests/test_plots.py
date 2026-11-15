"""Plots (lib/plot_manager.py): a short key as the id; owner, goal and kind;
where it stands; who and what it involves; a summary when it ends. Facts,
consequences, clocks and glossary entries point at their plots, and some links
are inherited. Open plots are sorted most pressing first."""

import json
from pathlib import Path

import pytest

from lib.consequence_manager import ConsequenceManager
from lib.note_manager import NoteManager
from lib.plot_manager import PlotError, PlotManager, check_key, plot_order
from lib.threat_clocks import ThreatClockManager

CAMP = "dungeon-crawler-carl"


def _load(world, name):
    return json.loads((Path(world) / "campaigns" / CAMP / name).read_text(encoding="utf-8"))


@pytest.fixture
def world(dcc_world):
    (Path(dcc_world) / "campaigns" / CAMP / "plots.json").write_text("{}")
    return dcc_world


def test_a_plot_has_a_short_key_and_the_new_fields(world):
    pm = PlotManager(world)
    key = pm.add(" The  Descent ", "Carl has to get Donut down the stairs alive.",
                 owner="Mordecai", goal="keep his crawlers alive", kind="main",
                 involves=["Princess Donut", "Floor 1 Stairs"], stands="The timer runs.")
    assert key == "The Descent"
    p = _load(world, "plots.json")["The Descent"]
    assert p["owner"] == "npc:Mordecai" and p["goal"] == "keep his crawlers alive"
    assert p["involves"] == ["npc:Princess Donut", "location:Floor 1 Stairs"]
    assert p["status"] == "open" and p["stands"] == "The timer runs." and p["kind"] == "main"
    for raw, why in (("The Long and Winding Road Down", "short key"), ("Plot: two", "short key"),
                     ("the descent", "already"), ("Descent", "close to the plot")):
        with pytest.raises(PlotError, match=why):
            pm.add(raw, "x")
    with pytest.raises(PlotError, match="kind is one of"):
        pm.add("Rats", "x", kind="threat")
    with pytest.raises(PlotError, match="No npc"):
        pm.add("Rats", "x", involves=["Nobody Here"])
    assert pm.add("Descent", "another plot", another=True) == "Descent"
    assert check_key("Eleventh Question") == "Eleventh Question"


def test_where_it_stands_who_it_involves_and_how_it_ends(world):
    pm = PlotManager(world)
    pm.add("The Descent", "Down the stairs.")
    pm.add("Mordecai's Debt", "Mordecai owes the dungeon.", kind="background")
    assert pm.set_stands("the descent", "Carl found the stairs.") == ("The Descent", "")
    assert pm.involve("The Descent", ["Carl", "Bone Garden"]) == ["npc:Carl", "location:Bone Garden"]
    assert pm.involve("The Descent", remove=["Carl"]) == ["location:Bone Garden"]
    with pytest.raises(PlotError, match="summary"):
        pm.end("The Descent", "completed", "")
    pm.end("Mordecai's Debt", "completed", "Paid in teeth.", next_plot="The Descent")
    plots = _load(world, "plots.json")
    assert plots["Mordecai's Debt"]["status"] == "completed"
    assert plots["Mordecai's Debt"]["summary"] == "Paid in teeth."
    assert plots["The Descent"]["follows"] == "Mordecai's Debt"
    with pytest.raises(PlotError, match="completed"):
        pm.set_stands("Mordecai's Debt", "x")
    assert plot_order(pm.json_ops) == ["The Descent"]


def test_links_are_stored_on_the_side_where_they_are_made(world, capsys):
    """Facts, consequences, clocks and glossary entries point at their plots;
    some inherit them. A fact with no plot is offered the one that fits."""
    from lib import glossary
    pm = PlotManager(world)
    pm.add("The Descent", "Down the stairs.", involves=["Princess Donut"])
    notes = NoteManager(world)
    fid = notes.add_fact("plot_local", "The stairs are rigged.", plots=["the descent"],
                         nowhere=True)
    assert notes._entry(_load(world, "facts.json"), fid)["plots"] == ["The Descent"]
    assert [f["id"] for f in notes.find(plot="The Descent")] == [fid]
    capsys.readouterr()
    other = notes.add_fact("plot_local", "Donut hissed at the stairs.", nowhere=True)
    assert f'Part of The Descent? bash tools/gm-note.sh plot {other} --add "The Descent"' \
        in capsys.readouterr().out
    assert notes.set_plots(other, add=["The Descent"]) == ["The Descent"]
    assert not notes.add_fact("plot_local", "x", plots=["No Such Plot"], nowhere=True)

    cm = ConsequenceManager(world)
    cid = cm.add_consequence("The stairs collapse", "someone kicks the rig", trigger_type="on_event",
                             match="someone kicks the rig", plots=["The Descent"],
                             effects=[{"type": "start_clock", "name": "Collapse", "segments": 2,
                                       "on": "event", "consequence": "The floor goes"}])
    trigger = notes.add_fact("plot_local", "Carl kicked the rig.", nowhere=True, offer_plot=False)
    cm.fire(cid, by_fact=trigger)
    clocks = ThreatClockManager(world)
    assert clocks.get_clocks()["Collapse"]["plots"] == ["The Descent"]        # from the consequence
    assert notes._entry(_load(world, "facts.json"), trigger)["plots"] == ["The Descent"]
    clocks.advance("Collapse", 2)
    full = [c for c in _load(world, "consequences.json")["active"]
            if c["consequence"].startswith("[Clock — Collapse]")]
    assert full and full[0]["plots"] == ["The Descent"]                        # from the clock
    assert glossary.add(notes.json_ops, "the rig", "A tripwire of chain.", ["The Descent"]) == "the rig"
    assert glossary.glossary(notes.json_ops)["the rig"]["plots"] == ["The Descent"]
    assert "Collapse" in pm.show("The Descent") and "Carl kicked the rig." in pm.show("The Descent")


def test_open_plots_are_sorted_most_pressing_first(world):
    """A fired consequence first, then the current place or someone in the scene,
    then the soonest clock, then the newest fact, then the kind."""
    pm = PlotManager(world)
    here = _load(world, "campaign-overview.json")["player_position"]["current_location"]
    pm.add("Background Noise", "x", kind="background")
    pm.add("Quiet Main", "x", kind="main")
    pm.add("Clocked", "x", kind="mystery")
    pm.add("Right Here", "x", kind="background", involves=[here])
    pm.add("Fired", "x", kind="background")
    from lib.time_manager import TimeManager, parse_time
    TimeManager(world).set_time(parse_time("2187-10-26 04:00"))
    ThreatClockManager(world).add_clock("Soon", 4, due_in_minutes=60, plots=["Clocked"])
    cm = ConsequenceManager(world)
    cid = cm.add_consequence("It happens", "now", trigger_type="on_event", match="now",
                             plots=["Fired"])
    cm.fire(cid, reason="it happened")
    assert plot_order(pm.json_ops) == ["Fired", "Right Here", "Clocked", "Quiet Main",
                                       "Background Noise"]


def test_plot_is_the_field_everywhere(world):
    """The command line says --plot; so do a beat's facts, the opening's and the
    world tick's developments ("plot": a name or a list). "plots" is refused
    with the right name, never silently dropped."""
    from lib.world_tick import WorldTick, WorldTickError
    notes = NoteManager(world)
    PlotManager(world).add("The Descent", "Down the stairs.")
    [fid] = notes.beat([{"fact": "The stairs creak.", "plot": "The Descent"}])
    assert notes._entry(_load(world, "facts.json"), fid)["plots"] == ["The Descent"]
    with pytest.raises(ValueError, match='"plot"'):
        notes.beat([{"fact": "The stairs groan.", "plots": ["The Descent"]}])
    with pytest.raises(WorldTickError, match='"plot"'):
        WorldTick(world).record([{"fact": "Far off, a door.", "plots": ["The Descent"]}])


def test_the_brief_is_ordered_by_plot(world):
    """Under each plot: its clocks, what waits in it, and what the character
    doesn't know of it, with who does; LATEST names a fact shown above by id."""
    from lib.session_manager import SessionManager
    notes = NoteManager(world)
    PlotManager(world).add("The Descent", "Down the stairs.", stands="The timer runs.")
    ThreatClockManager(world).add_clock("Collapse", 3, advance_on="event", plots=["The Descent"])
    ConsequenceManager(world).add_consequence("The stairs give way", "Collapse:2",
                                              triggers=[{"type": "on_clock", "match": "Collapse:2"}],
                                              plots=["The Descent"])
    secret = notes.add_fact("plot_local", "Mordecai rigged the stairs.", holders=["npc:Mordecai"],
                            plots=["The Descent"])
    brief = SessionManager(world).get_full_context()
    block = brief.split("] The Descent: The timer runs.")[1].split("\n---")[0]
    assert "clock Collapse: 0/3" in block and "The stairs give way (when: Collapse:2" in block
    assert f"{secret} Mordecai rigged the stairs. (Mordecai knows)" in block
    latest = brief.split("--- LATEST")[1]
    assert f"newer, above: {secret}" in latest and "rigged" not in latest   # named, not printed again
    assert "KEY FACTS" not in brief and "THREAT CLOCKS" not in brief
