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
             {"name": "Mags Teller", "who": "a fixer", "nowhere": True, "present": False},
             {"name": "Seraphine Halcyon-Vey", "who": "the sleeve's first owner",
              "nowhere": True, "present": False}],
    "plot": {"name": "The Writ", "kind": "main",
             "description": "Meridian wants the sleeve back, with its mind.",
             "hook": "Dekker's crew walks into the market with a writ for a sleeve.",
             "owner": "Dekker", "goal": "bring the sleeve back to Meridian",
             "involves": ["Dekker", "Seraphine Halcyon-Vey", "Lanternside"]},
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
    assert plot["status"] == "open" and plot["stands"] == SPEC["plot"]["hook"]
    assert plot["owner"] == "npc:Dekker" and plot["goal"] == "bring the sleeve back to Meridian"
    assert plot["involves"] == ["npc:Dekker", "npc:Seraphine Halcyon-Vey", "location:Lanternside"]
    clocks = _load(camp, "threat-clocks.json")
    assert clocks["The Foreclosure"]["plots"] == ["The Writ"]        # the opening's plot
    assert all(f.get("plots") == ["The Writ"] for f in _load(camp, "facts.json") if not f.get("attitude"))

    facts = _load(camp, "facts.json")
    assert {f["fact"]: f["holders"] for f in facts} == {
        SPEC["developments"][0]["fact"]: ["street", "npc:Auntie Ro"],
        SPEC["developments"][1]["fact"]: ["npc:Auntie Ro"],
        # an attitude becomes a fact the NPC holds about the player
        "friendly": ["npc:Auntie Ro"],
        "hostile": ["npc:Dekker"]}
    triggers = _load(camp, "consequences.json")["active"][0]["triggers"]
    assert triggers == [{"type": "on_location", "match": "location:The Lantern noodle stall"}]

    assert result["horizon"] == ["Dekker", "Seraphine Halcyon-Vey"]   # no look or personality yet
    text = summary(result)
    assert "Hook: Dekker's crew walks into the market" in text
    assert "On the horizon (named, not built until play walks there): " \
           "Dekker, Seraphine Halcyon-Vey" in text


def test_the_brief_carries_the_hook_and_horizon_on(world):
    ws, _ = world
    Opening(ws).apply(json.loads(json.dumps(SPEC)))
    ctx = SessionManager(ws).get_full_context()
    assert "[main] The Writ: Dekker's crew walks into the market with a writ for a sleeve." in ctx
    assert "  Dekker wants: bring the sleeve back to Meridian" in ctx
    assert "  still sketches (named, not built): Dekker, Seraphine Halcyon-Vey" in ctx
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
    Opening(ws).apply(json.loads(json.dumps(SPEC)))
    with pytest.raises(OpeningError, match="set up already"):
        Opening(ws).apply(json.loads(json.dumps(SPEC)))


def test_existing_places_npcs_and_plot_are_used_as_they_are(world):
    ws, camp = world
    (camp / "locations.json").write_text(json.dumps({"Lanternside": {"position": "imported"}}))
    (camp / "npcs.json").write_text(json.dumps(
        {"Dekker": npc("Dekker", places=[], identity={"name": "Dekker", "role": "imported"})}))
    (camp / "plots.json").write_text(json.dumps(
        {"The Writ": {"kind": "main", "status": "open", "description": "Meridian wants it."}}))
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
    assert plot["status"] == "open" and plot["stands"] == "The crew walks in."


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
    assert _load(camp, "plots.json")["The Writ"]["stands"] == SPEC["plot"]["hook"]
    con = _load(camp, "consequences.json")["active"][0]
    from consequence_manager import when_words
    assert "trigger" not in con
    assert when_words(con) == "at The Lantern noodle stall"   # what it waits for, in words


def test_a_consequence_may_wait_on_a_clock_given_later(world):
    """Both playtest openings (2026-11-14) were refused because a consequence on
    "<clock>:1" came before the development that makes the clock. The clocks
    are made first now, whatever the order."""
    from lib.world_tick import WorldTick
    ws, _ = world
    applied, written = WorldTick(ws).record([
        {"fact": "A thug is told to find the driver.",
         "consequence": {"text": "The thug asks at the garage",
                         "triggers": [{"type": "on_clock", "match": "Repossession:1"}]}},
        {"fact": "The convoy is hired.",
         "clock": {"name": "Repossession", "text": "The convoy comes", "segments": 4,
                   "on": "event"}}])
    assert written["clocks"] == ["Repossession"] and len(written["consequences"]) == 1
    assert applied[1]["clock"] == "Repossession"


def test_a_place_named_after_another_and_a_needless_alias(world):
    """The playtests' first openings failed on these (2026-11-09 to 11-19): "the
    Underpass" as an alias of The Underpass threw everything away, and a refused
    close name ("Orchid Room service alley" beside The Orchid Room) gave the command
    line's --another, not the entry's key. The alias is left out with a note now, and
    the refusal names "another": true."""
    ws, camp = world
    spec = json.loads(json.dumps(SPEC))
    spec["place"]["aliases"] = ["lanternside"]
    spec["exits"][1]["name"] = "Lanternside stairwells"
    with pytest.raises(OpeningError, match='add "another": true to its entry'):
        Opening(ws).apply(json.loads(json.dumps(spec)))
    spec["exits"][1]["another"] = True
    result = Opening(ws).apply(spec)
    assert any("'lanternside' is not kept as an alias" in n for n in result["notes"])
    assert "aliases" not in _load(camp, "locations.json")["Lanternside"]


def test_the_opening_names_tied_factions_with_no_relation(world):
    """Once, as play begins: a tie with no Relation written (unset is not 0)."""
    from lib import world_rules
    from lib.factions import FactionManager
    from lib.json_ops import JsonOperations
    ws, camp = world
    ops = JsonOperations(str(camp))
    m = FactionManager(ops)
    m.create("The Tenders", "Priests of the machine.", fid="tenders")
    m.create("The Houses", "The pleasure-houses.", fid="houses")
    m.create("The Wardens", "The deck militia.", fid="wardens")
    m.tie("tenders", "houses", "useful sinners")
    m.tie("wardens", "tenders", "masters who pay in sermons")
    world_rules.change(ops, "Relation", "tenders+wardens", to=3)
    text = summary(Opening(ws).apply(json.loads(json.dumps(SPEC))))
    assert "Tied but no Relation set: The Houses and The Tenders" in text
    assert "Relation\" \"houses+tenders\" N" in text
    assert "The Tenders and The Wardens" not in text
