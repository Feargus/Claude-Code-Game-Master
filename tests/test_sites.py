"""Sites and their locations (lib/sites.py): "The Gilt House#The Kitchens" is a
location in the site The Gilt House. What is at the site counts in each location;
a move within a site prints only the place's own lines and adds no connection."""

import json
import os
import subprocess
from pathlib import Path

from lib import sites
from lib.consequence_manager import ConsequenceManager
from lib.location_manager import LocationManager
from lib.note_manager import NoteManager

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = "dungeon-crawler-carl"
HOUSE = "The Gilt House"
KITCHENS = f"{HOUSE}#The Kitchens"
SALON = f"{HOUSE}#The Salon"


def _camp(world) -> Path:
    return Path(world) / "campaigns" / CAMPAIGN


def _house(world):
    lm = LocationManager(world)
    assert lm.add_location(HOUSE, "off the promenade", "A house of silk and mirrors.")
    assert lm.add_location(KITCHENS, "below the salon", "Copper pots and a scrubbed table.")
    assert lm.add_location(SALON, "the ground floor", "Low couches, a dais.")


def _move(world, *args):
    return subprocess.run(["bash", str(ROOT / "tools" / "gm-session.sh"), "move", *args],
                          capture_output=True, text=True, cwd=ROOT,
                          env={**os.environ, "GM_WORLD_STATE_BASE": str(world), "GM_EMBEDDER": "off"})


def test_the_names():
    assert sites.site_of(KITCHENS) == HOUSE and sites.site_of(HOUSE) == HOUSE
    assert sites.own_name(f"location:{KITCHENS}") == "The Kitchens"
    assert sites.at(KITCHENS, HOUSE) and sites.at(f"location:{KITCHENS}", f"location:{HOUSE}")
    assert not sites.at(HOUSE, KITCHENS) and not sites.at(SALON, KITCHENS)
    assert not sites.at("The Gilt Houseboat", HOUSE)
    assert sites.same_site(SALON, KITCHENS) and not sites.same_site(SALON, "The Docks")


def test_a_location_needs_its_site_and_one_level(dcc_world, capsys):
    lm = LocationManager(dcc_world)
    assert not lm.add_location("Nowhere#Room", "x", "y")
    assert "No site 'Nowhere'" in capsys.readouterr().out
    _house(dcc_world)
    assert not lm.add_location(f"{KITCHENS}#Pantry", "x", "y")
    assert 'one "#" at most' in capsys.readouterr().out
    assert lm.add_location("The Iron House", "x", "A forge.")
    assert lm.add_location("The Iron House#The Kitchens", "x", "Soot and stew.")  # every House may


def test_a_location_is_found_by_its_own_name_and_in_a_fact(dcc_world):
    _house(dcc_world)
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("Carl stole a ladle in The Kitchens.", at="The Kitchens")
    fact = json.loads((_camp(dcc_world) / "facts.json").read_text())[-1]
    assert fact["id"] == fid and fact["at"] == f"location:{KITCHENS}"
    assert f"location:{KITCHENS}" in fact["about"]
    assert [f["id"] for f in nm.find(at=HOUSE)] == [fid]                # the site holds it
    assert nm.find(at=SALON) == []


def test_a_move_within_the_site_prints_its_own_lines_and_connects_nothing(dcc_world):
    _house(dcc_world)
    subprocess.run(["bash", str(ROOT / "tools" / "gm-time.sh"), "set", "2187-10-26 22:00"],
                   capture_output=True, cwd=ROOT, env={**os.environ, "GM_WORLD_STATE_BASE": str(dcc_world)})
    r = _move(dcc_world, "The Kitchens")
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith(f"[SUCCESS] Moved to {KITCHENS}\n")
    assert f"\n{HOUSE}: A house of silk and mirrors." in r.stdout        # the site card
    assert r.stdout.rstrip().endswith("The Kitchens: Copper pots and a scrubbed table.")
    r = _move(dcc_world, "The Salon", "--takes", "1m")
    assert r.returncode == 0, r.stderr
    lines = [line for line in r.stdout.splitlines() if line]
    assert lines[0].startswith(f"[SUCCESS] Moved to {SALON}, ")
    assert lines[-1] == "The Salon: Low couches, a dais." and HOUSE + ":" not in r.stdout
    places = json.loads((_camp(dcc_world) / "locations.json").read_text())
    assert places[SALON]["connections"] == [] and places[KITCHENS]["connections"] == []
    assert any(c["to"] == HOUSE for c in places["Warehouse Street Level"]["connections"])


def test_a_trigger_on_the_site_fires_in_its_locations(dcc_world):
    _house(dcc_world)
    cm = ConsequenceManager(dcc_world)
    house = cm.add_consequence("The Matron sends for Carl", trigger_type="on_location", match=HOUSE)
    salon = cm.add_consequence("Music starts", trigger_type="on_location", match=SALON)
    r = _move(dcc_world, "The Kitchens")
    assert f"[FIRED] {house} " in r.stdout and salon not in r.stdout
    assert f"[FIRED] {salon} " in _move(dcc_world, "The Salon").stdout
