"""holders: who knows a fact.

In a scene the default is the player plus the NPCs present (party members and
the scene list; never the dead). --holders replaces
the default, --secret means nobody (a GM-only secret), and `gm-note.sh tell`
adds holders later. Off-screen facts from /gm world default to nobody. A place
can't be a holder.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.note_manager import NoteManager
from lib.world_tick import WorldTick, WorldTickError

CAMPAIGN = "dungeon-crawler-carl"
PARTY = ["player", "npc:Carl", "npc:Princess Donut", "npc:Mongo"]  # the fixture's scene


def _cdir(world):
    return Path(world) / "campaigns" / CAMPAIGN


def _fact(world, fid):
    facts = json.loads((_cdir(world) / "facts.json").read_text(encoding="utf-8"))
    return next(f for f in facts
                if isinstance(f, dict) and f.get("id") == fid)


def _edit_npcs(world, change):
    p = _cdir(world) / "npcs.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    change(data)
    p.write_text(json.dumps(data))


def test_default_is_the_player_and_who_is_present(dcc_world, capsys):
    fid = NoteManager(dcc_world).add_fact("The crate was empty")
    assert _fact(dcc_world, fid)["holders"] == PARTY
    assert "[CHECK] holders: player, npc:Carl" in capsys.readouterr().out


def test_npcs_in_the_scene_count_and_the_dead_do_not(dcc_world):
    from tests.scene_helpers import put_in_scene
    put_in_scene(_cdir(dcc_world), "Mordecai")
    _edit_npcs(dcc_world, lambda npcs: npcs["Mongo"].update(status="dead"))
    fid = NoteManager(dcc_world).add_fact("x")
    holders = _fact(dcc_world, fid)["holders"]
    assert "npc:Mordecai" in holders and "npc:Mongo" not in holders


def test_holders_replace_the_default(dcc_world):
    fid = NoteManager(dcc_world).add_fact("x", holders=["Mordecai", "street"])
    assert _fact(dcc_world, fid)["holders"] == ["npc:Mordecai", "street"]


def test_also_adds_to_the_default(dcc_world):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("x", also=["Mordecai", "Carl"])
    assert _fact(dcc_world, fid)["holders"] == PARTY + ["npc:Mordecai"]
    assert nm.add_fact("x", also=["Carl"], holders=["Carl"]) == ""
    assert nm.add_fact("x", also=["Carl"], secret=True) == ""


def test_secret_means_nobody(dcc_world, capsys):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("The vault code is 0451", secret=True)
    assert _fact(dcc_world, fid)["holders"] == []
    assert "[CHECK] holders: nobody (secret)" in capsys.readouterr().out
    assert nm.add_fact("x", holders=["Carl"], secret=True) == ""


def test_a_place_cannot_know(dcc_world, capsys):
    assert NoteManager(dcc_world).add_fact("x", holders=["location:Bone Garden"]) == ""
    assert "a place can't know" in capsys.readouterr().err


def test_tell_adds_only_the_new(dcc_world):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("x", secret=True)
    assert nm.tell(fid, ["Mordecai", "public"]) == ["npc:Mordecai", "public"]
    assert nm.tell(fid, ["npc:mordecai", "Carl"]) == ["npc:Carl"]   # Mordecai knew already
    assert _fact(dcc_world, fid)["holders"] == ["npc:Mordecai", "public", "npc:Carl"]
    assert nm.tell(fid, ["Carl"]) == []
    with pytest.raises(ValueError, match="No fact"):
        nm.tell("f9999", ["Carl"])
    with pytest.raises(ValueError, match="place"):
        nm.tell(fid, ["Bone Garden"])


def test_tell_works_on_old_facts_without_holders(dcc_world):
    facts_file = _cdir(dcc_world) / "facts.json"
    facts = json.loads(facts_file.read_text(encoding="utf-8"))
    facts.append({"id": "f900", "fact": "old", "timestamp": "2026-01-01"})
    facts_file.write_text(json.dumps(facts))
    assert NoteManager(dcc_world).tell("f900", ["Carl"]) == ["npc:Carl"]


def test_world_tick_defaults_to_nobody_but_takes_holders(dcc_world):
    applied = WorldTick(dcc_world).apply([
        {"fact": "Mordecai sold the map."},
        {"fact": "The Butcher heard of it.", "holders": ["npc:The Butcher", "street"]}])
    assert _fact(dcc_world, applied[0]["fact"])["holders"] == []
    assert _fact(dcc_world, applied[1]["fact"])["holders"] == ["npc:The Butcher", "street"]


def test_world_tick_refuses_a_bad_holder_and_keeps_nothing(dcc_world):
    before = (_cdir(dcc_world) / "facts.json").read_text(encoding="utf-8")
    with pytest.raises(WorldTickError, match="holders"):
        WorldTick(dcc_world).apply([{"fact": "a"}, {"fact": "b", "holders": ["Bone Garden"]}])
    assert (_cdir(dcc_world) / "facts.json").read_text(encoding="utf-8") == before


def test_cli(dcc_world):
    root = Path(__file__).resolve().parent.parent
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(root / "lib" / "note_manager.py"), *a],
        capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    r = run("add", "The code is 0451", "--secret")
    assert r.returncode == 0, r.stderr
    fid = r.stdout.split("[SUCCESS] Recorded ")[1].split()[0]
    r = run("tell", fid, "Mordecai", "street")
    assert r.returncode == 0 and f"[SUCCESS] Told {fid} to npc:Mordecai, street" in r.stdout
    r = run("tell", fid, "Mordecai")
    assert f"they knew {fid} already" in r.stdout
    r = run("add", "Carl saw it", "--holders", "Carl", "--holders", "player")
    assert r.returncode == 0 and "[CHECK] holders: npc:Carl, player" in r.stdout


# --- where it happened: here only if someone here knows it ---------------------

HERE = "location:Warehouse Street Level"     # the fixture's current place


def test_a_fact_someone_here_knows_happened_here(dcc_world):
    nm = NoteManager(dcc_world)
    assert _fact(dcc_world, nm.add_fact("The crate was empty"))["at"] == HERE
    assert _fact(dcc_world, nm.add_fact("Carl kept the key", holders=["Carl"]))["at"] == HERE
    assert _fact(dcc_world, nm.add_fact("The flaw is in the lock", secret=True))["at"] == HERE
    assert _fact(dcc_world, nm.add_fact("The floor collapses at dawn",
                                        holders=["public"]))["at"] == HERE


def test_a_fact_nobody_here_knows_happened_elsewhere(dcc_world, capsys):
    """Teo's errand while Ish slept (What Remains, f38-f40) was put in Ish's flat:
    none of its holders was there. Such a fact gets no place, and the check line
    says how to give it one."""
    nm = NoteManager(dcc_world)
    capsys.readouterr()
    fid = nm.add_fact("Mordecai sold the map to a stranger", holders=["Mordecai"])
    assert "at" not in _fact(dcc_world, fid)
    assert (f"at: nowhere, since none of its holders is here; if it happened at a known "
            f"place: bash tools/gm-note.sh at {fid} \"<place>\"") in capsys.readouterr().out
    given = nm.add_fact("Mordecai hid the map", holders=["Mordecai"], at="Bone Garden")
    assert _fact(dcc_world, given)["at"] == "location:Bone Garden"


def test_a_faction_holds_it_through_a_member_here(dcc_world):
    _edit_npcs(dcc_world, lambda npcs: npcs["Carl"].setdefault("identity", {}).update(
        factions=[{"id": "crawlers"}]))
    nm = NoteManager(dcc_world)
    assert _fact(dcc_world, nm.add_fact("The crawlers chose a leader",
                                        holders=["faction:crawlers"]))["at"] == HERE
    assert "at" not in _fact(dcc_world, nm.add_fact("The showrunners chose a theme",
                                                    holders=["faction:showrunners"]))


def test_where_a_fact_happened_can_be_changed(dcc_world):
    nm = NoteManager(dcc_world)
    fid = nm.add_fact("Mordecai sold the map to a stranger", holders=["Mordecai"])
    assert nm.set_at(fid, "Bone Garden") == (None, "location:Bone Garden")
    assert nm.set_at(fid, nowhere=True) == ("location:Bone Garden", None)
    assert "at" not in _fact(dcc_world, fid)
    with pytest.raises(ValueError, match="Give the place, or --nowhere"):
        nm.set_at(fid)
    with pytest.raises(ValueError, match="at: "):
        nm.set_at(fid, "Nowhere Known")
    env = {"GM_WORLD_STATE_BASE": str(dcc_world), "PATH": "/usr/bin:/bin"}
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root / "lib" / "note_manager.py"), "at", fid,
                        "Bone Garden"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout == f"[SUCCESS] {fid} happened at location:Bone Garden (was: nowhere)\n"
