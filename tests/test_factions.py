"""Factions (lib/factions.py, design-notes.md → "Factions", step 1).

factions.json, keyed by a short id: `faction:<id>` is a real id from then on, for
what a fact is about, who holds it, who learns it, and world rules held by factions.
The record only describes the faction; an older campaign's factions are the world
bible's, and the first `create` copies them in.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import world_rules as wr
from lib.consequence_manager import ConsequenceManager
from lib.factions import FactionError, FactionManager, known, load, make_id
from lib.json_ops import JsonOperations
from lib.note_manager import NoteManager
from lib.world_ids import WorldIds

CAMPAIGN = "dungeon-crawler-carl"
ROOT = Path(__file__).resolve().parent.parent
PATIENCE = {"name": "Patience", "block": "counter", "held_by": "faction", "known": False,
            "range": [0, 5], "start": 5, "summary": "What a faction will still put up with.",
            "when": "The character crosses a faction."}


@pytest.fixture
def ops(dcc_world):
    return JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN))


@pytest.fixture
def borant(ops):
    """The fixture's bible factions, plus Meridian, created as a new one."""
    m = FactionManager(ops)
    m.create("Meridian Group", "A security firm that rents out its guards by the hour.",
             kind="security company", impulses=["Sell fear, then sell the cure."],
             values=["Never leaves a contract unpaid."], aliases=["Meridian"], tags=["Corp"])
    return m


def test_an_id_comes_from_the_name():
    assert make_id("Lull Corporation") == "lull-corporation"
    assert make_id("The Caprock Combine") == "caprock-combine"
    assert make_id("The") == "the"


def test_the_first_faction_copies_the_bibles_in(ops, dcc_world):
    assert not (Path(ops.world_state_dir) / "factions.json").exists()
    assert set(known(ops)) == {"crawlers", "system", "showrunners", "npcs"}   # from the bible
    m = FactionManager(ops)
    fid = m.create("Meridian Group", "A security firm.", aliases=["Meridian"])
    assert fid == "meridian-group"
    assert "started from the world bible's factions" in m.notes[0]
    table = load(ops)
    assert set(table) == {"crawlers", "system", "showrunners", "npcs", "meridian-group"}
    assert table["system"]["name"] == "The System / Borant Corp"
    assert table[fid] == {"name": "Meridian Group", "aliases": ["Meridian"],
                          "description": "A security firm."}


def test_the_record_only_describes_the_faction(borant, ops):
    row = load(ops)["meridian-group"]
    assert row == {"name": "Meridian Group", "aliases": ["Meridian"], "kind": "security company",
                   "description": "A security firm that rents out its guards by the hour.",
                   "impulses": ["Sell fear, then sell the cure."],
                   "values": ["Never leaves a contract unpaid."], "tags": ["corp"]}


@pytest.mark.parametrize("raw", ["faction:meridian-group", "Meridian Group", "meridian",
                                 "faction:Meridian", "the Meridian Group"])
def test_a_faction_is_found_by_id_name_or_alias(borant, ops, raw):
    assert WorldIds(ops).resolve(raw) == ("faction:meridian-group", "")


def test_an_unknown_faction_is_refused_with_close_matches(borant, ops):
    cid, error = WorldIds(ops).resolve("faction:Meridan Group")
    assert cid == "" and "did you mean: faction:meridian-group" in error


@pytest.mark.parametrize("name, description, fid, words", [
    ("Meridian Groups", "x", "", "close to faction:meridian-group"),
    ("Mordecai", "x", "", "already names npc:Mordecai"),
    ("Grey Hands", "", "", "needs a description"),
    ("Grey Hands", "x", "Grey Hands", "lowercase letters"),
    ("Grey Hands", "x", "system", "There is a faction 'system' already"),
])
def test_what_create_refuses(borant, name, description, fid, words):
    with pytest.raises(FactionError, match=words):
        borant.create(name, description, fid)


def test_a_close_name_is_another_faction_with_another(borant, ops):
    assert borant.create("Meridian Groups", "A splinter.", another=True) == "meridian-groups"


def test_an_alias_is_checked(borant):
    with pytest.raises(FactionError, match="own name"):
        borant.create("Grey Hands", "x", aliases=["the grey hands"])
    with pytest.raises(FactionError, match="already names faction:meridian-group"):
        borant.create("Grey Hands", "x", aliases=["Meridian"])


def test_leader_and_successor_are_npcs(borant, ops):
    fid, before = borant.set_field("Meridian", "leader", ["mordecai"])
    assert before is None and load(ops)[fid]["leader"] == "npc:Mordecai"
    with pytest.raises(FactionError, match="known NPC"):
        borant.set_field("Meridian", "successor", ["Nobody Here"])


def test_set_replaces_a_field_and_returns_the_old_value(borant, ops):
    fid, before = borant.set_field("Meridian", "impulses", ["Buy the rival.", "Hire the best."])
    assert before == ["Sell fear, then sell the cure."]
    assert load(ops)[fid]["impulses"] == ["Buy the rival.", "Hire the best."]
    borant.set_field("Meridian", "tags", [])                     # nothing given: cleared
    assert "tags" not in load(ops)[fid]
    borant.set_field("Meridian", "name", ["Meridian Security"])  # the id stays
    assert WorldIds(ops).resolve("Meridian Security") == ("faction:meridian-group", "")
    with pytest.raises(FactionError, match="fields are"):
        borant.set_field("Meridian", "goal", ["x"])
    with pytest.raises(FactionError, match="can't be empty"):
        borant.set_field("Meridian", "description", [])


def test_assets_are_named_with_a_note(borant, ops):
    borant.asset("Meridian", "The Armoury", "Two floors of rented guns.")
    borant.asset("Meridian", "the armoury", "Three floors now.")      # the same one
    assert load(ops)["meridian-group"]["assets"] == [{"name": "The Armoury",
                                                      "note": "Three floors now."}]
    borant.asset("Meridian", "The Armoury", remove=True)
    assert "assets" not in load(ops)["meridian-group"]
    with pytest.raises(FactionError, match="no asset"):
        borant.asset("Meridian", "The Vault", remove=True)


def test_facts_name_hold_and_teach_a_faction(borant, ops, dcc_world):
    notes = NoteManager(dcc_world)
    fid = notes.add_fact("Meridian guards were seen at the stairs.", holders=["faction:meridian"])
    fact = next(f for f in json.loads((Path(ops.world_state_dir) / "facts.json").read_text())
                if f["id"] == fid)
    assert fact["about"] == ["faction:meridian-group"]           # found in the text
    assert fact["holders"] == ["faction:meridian-group"]
    secret = notes.add_fact("Carl hid the key.", secret=True)
    waiting = ConsequenceManager(dcc_world).add_consequence(
        "The System knows.", "y", trigger_type="on_learn", match=f"faction:system learns {secret}")
    notes.tell(secret, ["faction:system"])
    assert [c["id"] for c in notes.last_fired] == [waiting]


def test_a_public_fact_is_learned_by_the_factions_too(borant, dcc_world):
    notes = NoteManager(dcc_world)
    fid = notes.add_fact("The stairwell collapsed.", secret=True)
    waiting = ConsequenceManager(dcc_world).add_consequence(
        "Meridian hears of it.", "y", trigger_type="on_learn",
        match=f"faction:meridian-group learns {fid}")
    notes.tell(fid, ["public"])
    assert waiting in [c["id"] for c in notes.last_fired]


def test_world_rules_find_the_factions_in_the_file(borant, ops):
    wr.define(ops, [PATIENCE])
    patience = wr.find_rule(ops, "Patience")
    assert wr.resolve_holder(ops, patience, "Meridian") == "faction:meridian-group"
    assert wr.resolve_holder(ops, patience, "faction:crawlers") == "faction:crawlers"  # copied in
    assert wr.holder_name(ops, "faction:meridian-group") == "Meridian Group"
    wr.change(ops, "Patience", "Meridian", by=-2)
    shown = borant.show("Meridian")
    assert "Patience" in shown and "3" in shown


def test_show_lists_what_it_knows_by_id(borant, dcc_world):
    fid = NoteManager(dcc_world).add_fact("The contract is forged.",
                                          holders=["faction:meridian-group"])
    shown = borant.show("meridian")
    assert shown.startswith("Meridian Group (faction:meridian-group)")
    assert f"Knows: {fid}" in shown and "Never leaves a contract unpaid." in shown


def test_the_command_line(dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-faction.sh"), *words],
                              capture_output=True, text=True, env=env)

    made = run("create", "Grey Hands", "--description", "Pickpockets of the third floor.",
               "--impulse", "Take what isn't nailed down.", "--tag", "gang", "--id", "grey")
    assert made.returncode == 0 and "[SUCCESS] Faction faction:grey" in made.stdout, made.stderr
    assert "[NOTE]" in made.stdout                                 # the bible's copied in
    assert run("alias", "grey", "the Hands").returncode == 0
    listed = run("list").stdout
    assert "faction:grey — Grey Hands: Pickpockets" in listed and "faction:system" in listed
    changed = run("set", "the Hands", "kind", "gang")
    assert changed.returncode == 0 and "faction:grey kind set" in changed.stdout
    bad = run("show", "Nobody")
    assert bad.returncode == 1 and bad.stderr.startswith("[ERROR]") and not bad.stdout


def test_an_older_campaign_lists_and_shows_the_bibles_factions(ops):
    m = FactionManager(ops)
    assert "faction:system — The System / Borant Corp" in "\n".join(m.list_lines())
    assert "From the world bible" in m.list_lines()[-1]
    assert m.show("The Crawlers").startswith("The Crawlers (faction:crawlers)")
    assert not (Path(ops.world_state_dir) / "factions.json").exists()     # reading writes nothing
    m.set_field("crawlers", "kind", ["the contestants"])                  # a change copies them in
    assert load(ops)["crawlers"]["kind"] == "the contestants" and "system" in load(ops)
    assert "started from the world bible's factions" in m.notes[0]


# ---------- step 2: members ----------

def _cards(ops):
    from lib.cards import Cards
    return Cards(ops)


def _npcs(ops):
    return json.loads((Path(ops.world_state_dir) / "npcs.json").read_text())


def test_joining_puts_the_membership_on_the_sheet(borant, ops):
    done = borant.join("Meridian", "Mordecai")
    assert done["npc"] == "Mordecai" and not done["changed"]
    assert _npcs(ops)["Mordecai"]["identity"]["factions"] == [{"id": "meridian-group"}]
    borant.join("system", "Mordecai", secret=True)
    assert _npcs(ops)["Mordecai"]["identity"]["factions"][1] == {"id": "system", "secret": True}
    card = "\n".join(_cards(ops).npc_card("Mordecai"))
    assert "member of: Meridian Group; The System / Borant Corp (SECRET: only its members know" in card
    assert "Members: Mordecai" in borant.show("Meridian")
    assert "Mordecai (secret: only its members know)" in borant.show("system")


def test_a_membership_is_joined_once_and_its_secret_can_change(borant, ops):
    borant.join("Meridian", "Mordecai")
    with pytest.raises(FactionError, match="a member of Meridian Group already"):
        borant.join("Meridian", "Mordecai")
    assert borant.join("Meridian", "Mordecai", secret=True)["changed"]
    assert _npcs(ops)["Mordecai"]["identity"]["factions"] == [{"id": "meridian-group", "secret": True}]
    borant.join("Meridian", "Mordecai", secret=False)
    assert _npcs(ops)["Mordecai"]["identity"]["factions"] == [{"id": "meridian-group"}]


def test_only_npcs_join(borant):
    with pytest.raises(FactionError, match="Only NPCs belong to factions"):
        borant.join("Meridian", "player")


def test_a_member_knows_what_the_faction_knows(borant, ops, dcc_world):
    notes = NoteManager(dcc_world)
    fid = notes.add_fact("Meridian pays the Showrunners.", holders=["faction:meridian-group"])
    borant.join("Meridian", "Mordecai")
    card = "\n".join(_cards(ops).npc_card("Mordecai"))
    assert fid in card                                            # one "they know" list
    assert fid in [f["id"] for f in notes.find(held_by=["Mordecai"])]
    assert notes.tell(fid, ["Mordecai"]) == []                    # knew it already
    assert _cards(ops).npc_card("Carl") and fid not in "\n".join(_cards(ops).npc_card("Carl"))


def test_joining_is_learning(borant, dcc_world):
    notes = NoteManager(dcc_world)
    first = notes.add_fact("The guards are bribable.", holders=["faction:meridian-group"])
    second = notes.add_fact("The vault code is 0451.", holders=["faction:meridian-group"])
    cm = ConsequenceManager(dcc_world)
    one = cm.add_consequence("Mordecai sells it.", "y", trigger_type="on_learn",
                             match=f"npc:Mordecai learns {first}")
    two = cm.add_consequence("Mordecai opens the vault.", "y", trigger_type="on_learn",
                             match=f"npc:Mordecai learns {second}")
    done = borant.join("Meridian", "Mordecai")
    assert done["learned"] == [first, second]
    assert {c["id"] for c in done["fired"]} == {one, two}


def test_what_a_faction_learns_its_living_members_learn(borant, ops, dcc_world):
    borant.join("Meridian", "Mordecai")
    borant.join("Meridian", "Carl")
    npcs = _npcs(ops)
    npcs["Carl"].setdefault("status", {})["state"] = "dead"
    (Path(ops.world_state_dir) / "npcs.json").write_text(json.dumps(npcs))
    notes = NoteManager(dcc_world)
    fid = notes.add_fact("The stairs are mined.", secret=True)
    cm = ConsequenceManager(dcc_world)
    alive = cm.add_consequence("Mordecai warns Carl.", "y", trigger_type="on_learn",
                               match=f"npc:Mordecai learns {fid}")
    dead = cm.add_consequence("Carl hears.", "y", trigger_type="on_learn",
                              match=f"npc:Carl learns {fid}")
    notes.tell(fid, ["faction:meridian-group"])
    fired = {c["id"] for c in notes.last_fired}
    assert alive in fired and dead not in fired


def test_leaving_loses_what_only_the_faction_knew(borant, dcc_world):
    notes = NoteManager(dcc_world)
    theirs = notes.add_fact("The client is Borant.", holders=["faction:meridian-group"])
    own = notes.add_fact("Mordecai owes Carl.", holders=["npc:Mordecai", "faction:meridian-group"])
    borant.join("Meridian", "Mordecai")
    assert borant.leave("Meridian", "Mordecai")["lost"] == [theirs]
    found = [f["id"] for f in notes.find(held_by=["Mordecai"])]
    assert own in found and theirs not in found
    with pytest.raises(FactionError, match="no member"):
        borant.leave("Meridian", "Mordecai")


def test_a_leader_is_a_member(borant, ops):
    borant.set_field("Meridian", "leader", ["Mordecai"])
    assert _npcs(ops)["Mordecai"]["identity"]["factions"] == [{"id": "meridian-group"}]
    assert "Mordecai is its leader, so a member now." in borant.notes


def test_a_leader_who_becomes_the_character_leads_no_more(borant, ops):
    from lib.handover import move_id
    borant.set_field("Meridian", "leader", ["Mordecai"])
    notes = move_id(ops, "npc:Mordecai", "player")
    assert "leader" not in load(ops)["meridian-group"]
    assert any("was the leader of faction:meridian-group" in n for n in notes)


def test_npc_create_joins_factions(borant, dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-npc.sh"), *words],
                              capture_output=True, text=True, env=env)

    bad = run("create", "Ilse Varga", "a guard", "--nowhere", "--faction", "Nobody")
    assert bad.returncode == 1 and "No faction" in bad.stderr
    assert "Ilse Varga" not in _npcs(JsonOperations(str(Path(dcc_world) / "campaigns" / CAMPAIGN)))
    made = run("create", "Ilse Varga", "a guard", "--nowhere", "--faction", "Meridian",
               "--secret-faction", "system")
    assert made.returncode == 0, made.stderr
    assert "npc:Ilse Varga joined faction:meridian-group" in made.stdout
    assert "joined faction:system (secret" in made.stdout


def test_an_older_campaigns_factions_are_copied_in_on_demand(ops):
    cid, error = WorldIds(ops).resolve("faction:crawlers")
    assert cid == "" and "gm-faction.sh from-bible" in error
    from lib.factions import _from_bible
    m = FactionManager(ops)
    _from_bible(m)
    assert WorldIds(ops).resolve("faction:crawlers") == ("faction:crawlers", "")
    with pytest.raises(FactionError, match="copied in"):
        _from_bible(m)


# ---------- step 3: plots and the brief ----------

def _plots(dcc_world):
    from lib.plot_manager import PlotManager
    return PlotManager(dcc_world)


def _here(ops):
    overview = json.loads((Path(ops.world_state_dir) / "campaign-overview.json").read_text())
    return overview["player_position"]["current_location"]


def test_a_faction_owns_and_is_in_plots(borant, dcc_world):
    plots = _plots(dcc_world)
    key = plots.add("Hostile Takeover", "Meridian buys the floor.", owner="Meridian",
                    goal="own every guard post on Floor 1", involves=["faction:system"])
    stored = plots.plots()[key]
    assert stored["owner"] == "faction:meridian-group" and stored["involves"] == ["faction:system"]
    assert "Meridian Group wants: own every guard post on Floor 1" in plots.show(key)
    assert "Wants: own every guard post on Floor 1 (plot Hostile Takeover, open)" in borant.show("Meridian")
    assert "In plots: Hostile Takeover" in borant.show("system")
    plots.involve(key, ["The Crawlers"], [])
    assert plots.plots()[key]["involves"] == ["faction:system", "faction:crawlers"]


def test_the_brief_names_a_faction_owner(borant, dcc_world):
    from lib.session_manager import SessionManager
    _plots(dcc_world).add("Hostile Takeover", "Meridian buys the floor.", owner="Meridian",
                          goal="own every guard post")
    assert "Meridian Group wants: own every guard post" in SessionManager(dcc_world).get_full_context()


def test_a_faction_with_a_member_here_gets_a_card(borant, ops, dcc_world):
    from tests.scene_helpers import put_in_scene
    _plots(dcc_world).add("Hostile Takeover", "Meridian buys the floor.", owner="Meridian",
                          goal="own every guard post")
    borant.join("Meridian", "Mordecai", secret=True)
    put_in_scene(ops.world_state_dir, "Mordecai")
    scene = "\n".join(_cards(ops).scene())
    assert "FACTION Meridian Group (faction:meridian-group; security company)" in scene
    assert "members here: Mordecai (SECRET member: only its members know)" in scene
    assert "impulses: Sell fear, then sell the cure." in scene
    assert "values: Never leaves a contract unpaid." in scene
    assert "wants (its plots, above): Hostile Takeover" in scene
    assert "FACTION The System" not in scene                       # nobody of theirs here


def test_a_faction_tied_to_the_place_by_a_plot_gets_a_card(borant, ops, dcc_world):
    _plots(dcc_world).add("Hostile Takeover", "Meridian buys the floor.", owner="Meridian",
                          goal="own every guard post", involves=[f"location:{_here(ops)}"])
    scene = "\n".join(_cards(ops).scene())
    assert "FACTION Meridian Group" in scene and "tied to this place by: Hostile Takeover" in scene


# ---------- step 4a: presence ----------

def test_presence_is_written_on_the_place(borant, ops):
    place = _here(ops)
    key, here = borant.set_presence(place, ["Meridian=4", "system=0"])
    assert key == place and here == {"meridian-group": 4, "system": 0}
    stored = json.loads((Path(ops.world_state_dir) / "locations.json").read_text())[place]
    assert stored["presence"] == {"meridian-group": 4, "system": 0}
    _, here = borant.set_presence(place, [], remove=["system"])
    assert here == {"meridian-group": 4}
    assert "Presence: " + place + " 4" in borant.show("Meridian")


@pytest.mark.parametrize("given, words", [
    (["Meridian=6"], "from 0 \\(not there\\) to 5"),
    (["Meridian"], "<faction>=N"),
    (["Nobody=2"], "No faction"),
])
def test_presence_is_checked(borant, ops, given, words):
    with pytest.raises(FactionError, match=words):
        borant.set_presence(_here(ops), given)


def test_a_present_faction_gets_a_card_and_zero_means_not_here(borant, ops):
    borant.set_presence(_here(ops), ["Meridian=3", "system=0"])
    scene = "\n".join(_cards(ops).scene())
    assert "Presence (0–5): Meridian Group 3; not here: The System / Borant Corp" in scene
    assert "FACTION Meridian Group" in scene and "presence here: 3" in scene
    assert "FACTION The System" not in scene


def test_a_faction_with_eyes_here_is_a_hint_when_a_fact_is_recorded(borant, ops, dcc_world, capsys):
    borant.set_presence(_here(ops), ["Meridian=4", "system=3"])
    notes = NoteManager(dcc_world)
    fid = notes.add_fact("Carl kicks the vending machine open.")
    out = capsys.readouterr().out
    assert (f"Meridian Group has eyes here (presence 4): if they'd see it, "
            f"bash tools/gm-note.sh tell {fid} faction:meridian-group") in out
    assert "The System" not in out.split("eyes here")[0].splitlines()[-1]    # 3 is no eyes
    notes.add_fact("Carl hides the key in his boot.", secret=True)
    assert "eyes here" not in capsys.readouterr().out                       # a secret: nobody saw
    held = load(ops)                                                        # nothing automatic
    assert fid not in borant.show("Meridian") and held


def test_the_presence_command(borant, ops, dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-location.sh"), "presence", *words],
                              capture_output=True, text=True, env=env)

    done = run(_here(ops), "Meridian=2", "crawlers=5")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == f"{_here(ops)}: The Crawlers 5, Meridian Group 2"
    assert run(_here(ops)).stdout.strip() == f"{_here(ops)}: The Crawlers 5, Meridian Group 2"
    bad = run(_here(ops), "Meridian=9")
    assert bad.returncode == 1 and bad.stderr.startswith("[ERROR]")


# ---------- found in the review (2026-11-19) ----------

def test_a_dead_leader_is_marked_and_the_successor_named(borant, ops, dcc_world):
    from lib.factions import succession
    from lib.npc_manager import NPCManager
    borant.set_field("Meridian", "leader", ["Mordecai"])
    borant.set_field("Meridian", "successor", ["Carl"])
    NPCManager(dcc_world).kill_npc("Mordecai", "test")
    assert "Leader: Mordecai (dead)" in borant.show("Meridian")
    notes = succession(ops, "npc:Mordecai")
    assert notes and "Carl takes over" in notes[0] and "set meridian-group leader" in notes[0]
    assert "name another successor" in succession(ops, "npc:Carl")[0]


def test_a_bible_only_campaign_is_told_to_copy_its_factions(ops):
    from lib import faction_turns as ft
    from lib import world_rules as wr
    with pytest.raises(ft.TurnError, match="from-bible"):
        ft.check(ops, [{"faction": "crawlers", "action": "build", "power": "Military"}])
    with pytest.raises(wr.RulesError, match="comes with the factions.*from-bible"):
        wr.find_rule(ops, "Military")
