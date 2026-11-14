"""The opening (gm-session.sh opening): a new campaign's first scene in one go,
all or nothing, made only through the functions play uses."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.opening import Opening, OpeningError, summary
from lib.session_manager import SessionManager
from tests.sheets import npc, player

ROOT = Path(__file__).resolve().parent.parent

SPEC = {
    "time": "2187-10-25 19:00",
    "place": {"name": "Lanternside", "position": "Level 40 of the Spine",
              "description": "A night market under failing holo-ads."},
    "exits": [{"name": "The Lantern noodle stall", "aliases": ["the Lantern"],
               "description": "Six stools and a steaming pot under a tarp."},
              {"name": "The Mercy Line stairwells", "position": "down into the Rust",
               "description": "Wet concrete stairs that smell of rust.",
               "path": "a rusted door"}],
    "npcs": [{"name": "Auntie Ro", "who": "runs the noodle stall", "attitude": "friendly",
              "aliases": ["Ro"], "location": "The Lantern noodle stall"},
             {"name": "Dekker", "who": "a Reclaimer crew boss", "attitude": "hostile"},
             {"name": "Mags Teller", "who": "a fixer", "nowhere": True, "present": False}],
    "plot": {"name": "The Writ", "type": "main",
             "description": "Meridian wants the sleeve back, with its mind.",
             "hook": "Dekker's crew walks into the market with a writ for a sleeve.",
             "npcs": ["Dekker", "Seraphine Halcyon-Vey"], "locations": ["The Chrome"]},
    "developments": [
        {"fact": "Meridian has bought Level 40's debt and is foreclosing Lanternside.",
         "holders": ["street", "Auntie Ro"],
         "clock": {"name": "The Foreclosure", "segments": 4, "due_in": "3d",
                   "consequence": "Lanternside is cleared"}},
        {"fact": "Auntie Ro hid the sleeve in her back room.", "holders": ["Auntie Ro"],
         "consequence": {"text": "Dekker leans on Ro",
                         "triggers": [{"type": "on_location", "match": "the Lantern"}]}},
    ],
}


@pytest.fixture
def world(tmp_path):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    for name, payload in {"campaign-overview.json": {"campaign_name": "C"},
                          "character.json": player("Fearghas"),
                          "npcs.json": {}, "locations.json": {}, "plots.json": {}}.items():
        (camp / name).write_text(json.dumps(payload))
    return str(ws), camp


def _load(camp, name):
    return json.loads((camp / name).read_text(encoding="utf-8"))


def test_the_opening_makes_ordinary_records(world):
    ws, camp = world
    result = Opening(ws).apply(json.loads(json.dumps(SPEC)))

    locations = _load(camp, "locations.json")
    assert locations["The Lantern noodle stall"]["aliases"] == ["the Lantern"]
    assert locations["The Lantern noodle stall"]["position"] == "next to Lanternside"
    assert {"to": "The Mercy Line stairwells", "path": "a rusted door"} in \
        locations["Lanternside"]["connections"]
    assert locations["Lanternside"]["description"].startswith("A night market")

    npcs = _load(camp, "npcs.json")
    assert npcs["Auntie Ro"]["places"]["usual"] == ["The Lantern noodle stall"]
    assert npcs["Dekker"]["places"]["usual"] == ["Lanternside"]  # the place, by default
    assert npcs["Mags Teller"]["places"]["usual"] == []

    overview = _load(camp, "campaign-overview.json")
    assert overview["player_position"]["current_location"] == "Lanternside"
    assert overview["scene"] == {"location": "Lanternside", "present": ["Auntie Ro", "Dekker"]}
    assert overview["game_time"] == "2187-10-25T19:00"
    assert overview["opened"] == "2187-10-25T19:00"

    plot = _load(camp, "plots.json")["The Writ"]
    assert plot["status"] == "active"
    assert plot["events"][-1]["event"] == SPEC["plot"]["hook"]
    clocks = _load(camp, "threat-clocks.json")
    assert clocks["The Foreclosure"]["linked_plot"] == "The Writ"

    facts = [f for items in _load(camp, "facts.json").values() for f in items]
    assert {f["fact"]: f["holders"] for f in facts} == {
        SPEC["developments"][0]["fact"]: ["street", "npc:Auntie Ro"],
        SPEC["developments"][1]["fact"]: ["npc:Auntie Ro"],
        # an attitude becomes a fact the NPC holds about the player
        "friendly": ["npc:Auntie Ro"],
        "hostile": ["npc:Dekker"]}
    triggers = _load(camp, "consequences.json")["active"][0]["triggers"]
    assert triggers == [{"type": "on_location", "match": "location:The Lantern noodle stall"}]

    assert result["horizon"] == ["Seraphine Halcyon-Vey", "The Chrome"]
    text = summary(result)
    assert "Hook: Dekker's crew walks into the market" in text
    assert "On the horizon (named, not built until play walks there): " \
           "Seraphine Halcyon-Vey, The Chrome" in text


def test_the_brief_carries_the_hook_and_horizon_on(world):
    ws, _ = world
    Opening(ws).apply(json.loads(json.dumps(SPEC)))
    ctx = SessionManager(ws).get_full_context()
    assert ("[main] The Writ - latest: Dekker's crew walks into the market with a writ for a "
            "sleeve. · on the horizon (not built yet): Seraphine Halcyon-Vey, The Chrome") in ctx
    assert "PRIMER" not in ctx


def test_a_refused_part_keeps_nothing(world):
    ws, camp = world
    before = {p.name: p.read_bytes() for p in camp.iterdir() if p.is_file()}
    spec = json.loads(json.dumps(SPEC))
    spec["developments"][1]["consequence"]["triggers"][0]["match"] = "Nowhere At All"
    with pytest.raises(OpeningError, match="Nothing of the opening was kept"):
        Opening(ws).apply(spec)
    assert {p.name: p.read_bytes() for p in camp.iterdir() if p.is_file()} == before


def test_refusals(world):
    ws, camp = world
    for broken, why in [({}, "needs a \"place\""),
                        ({"place": "X"}, "needs a \"plot\""),
                        ({"place": "X", "plot": {"name": "P"}}, "needs a \"hook\""),
                        ({"place": "X", "plot": "P", "hook": "h", "room": "Y"}, "Unknown field")]:
        with pytest.raises(OpeningError, match=why):
            Opening(ws).apply(broken)
    bare_exit = json.loads(json.dumps(SPEC))
    del bare_exit["exits"][0]["description"]
    with pytest.raises(OpeningError, match="'The Lantern noodle stall' needs a \"description\""):
        Opening(ws).apply(bare_exit)
    Opening(ws).apply(json.loads(json.dumps(SPEC)))
    with pytest.raises(OpeningError, match="set up already"):
        Opening(ws).apply(json.loads(json.dumps(SPEC)))


def test_needs_a_character_and_a_new_campaign(world):
    ws, camp = world
    (camp / "character.json").unlink()
    with pytest.raises(OpeningError, match="Create the character first"):
        Opening(ws).apply(json.loads(json.dumps(SPEC)))
    (camp / "character.json").write_text(json.dumps(player("Fearghas")))
    (camp / "session-log.md").write_text("## Session Started: x\n\n### Session Ended: y\nDone.\n")
    with pytest.raises(OpeningError, match="Play has begun"):
        Opening(ws).apply(json.loads(json.dumps(SPEC)))


def test_existing_places_npcs_and_plot_are_used_as_they_are(world):
    ws, camp = world
    (camp / "locations.json").write_text(json.dumps({"Lanternside": {"position": "imported"}}))
    (camp / "npcs.json").write_text(json.dumps(
        {"Dekker": npc("Dekker", places=[], identity={"name": "Dekker", "role": "imported"})}))
    (camp / "plots.json").write_text(json.dumps(
        {"The Writ": {"type": "main", "status": "available", "events": []}}))
    with pytest.raises(OpeningError, match="'Lanternside' has no description yet"):
        Opening(ws).apply({"place": "Lanternside", "npcs": ["Dekker"],
                           "plot": "The Writ", "hook": "The crew walks in."})
    Opening(ws).apply({"place": {"name": "Lanternside", "description": "A night market."},
                       "npcs": ["Dekker"], "plot": "The Writ", "hook": "The crew walks in."})
    assert _load(camp, "locations.json")["Lanternside"] == {"position": "imported",
                                                             "description": "A night market."}
    assert _load(camp, "npcs.json")["Dekker"]["identity"]["role"] == "imported"
    assert _load(camp, "campaign-overview.json")["scene"]["present"] == ["Dekker"]
    plot = _load(camp, "plots.json")["The Writ"]
    assert plot["status"] == "active" and plot["events"][-1]["event"] == "The crew walks in."


def test_cli(world):
    ws, _ = world
    def run():
        return subprocess.run([sys.executable, str(ROOT / "lib" / "opening.py"), json.dumps(SPEC)],
                              capture_output=True, text=True, cwd=str(Path(ws).parent))
    r = run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[SUCCESS] The opening is set up" in r.stdout
    r = run()
    assert r.returncode == 1 and "set up already" in r.stderr


def test_the_plot_starts_with_its_hook_and_consequences_say_when(world):
    """Two things play showed: the plot's first beat was the placeholder 'Thread
    seeded', and the opening's consequences read 'triggers: off-screen development'."""
    ws, camp = world
    Opening(ws).apply(json.loads(json.dumps(SPEC)))
    events = [e["event"] for e in _load(camp, "plots.json")["The Writ"]["events"]]
    assert events == [SPEC["plot"]["hook"]]
    con = _load(camp, "consequences.json")["active"][0]
    assert con["trigger"] == "the Lantern"   # the match it waits for
