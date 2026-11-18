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
