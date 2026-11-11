"""on_death: an event trigger checked inside the command that makes the change.

gm-npc.sh kill (and gm-player.sh kill) mark the death and fire every active
consequence waiting on it, exactly once. gm-consequence.sh fire does the same
by hand, for conditions no script can see.
"""

import json
from pathlib import Path

from lib.consequence_manager import ConsequenceManager
from lib.entity_manager import npcs_present
from lib.npc_manager import NPCManager

CAMPAIGN = "dungeon-crawler-carl"


def _cdir(world):
    return Path(world) / "campaigns" / CAMPAIGN


def _load(world, name):
    return json.loads((_cdir(world) / name).read_text(encoding="utf-8"))


def _an_npc(world):
    return next(iter(_load(world, "npcs.json")))


def _active(world):
    return _load(world, "consequences.json")["active"]


def test_on_death_needs_a_known_npc_or_player(dcc_world):
    cm = ConsequenceManager(dcc_world)
    npc = _an_npc(dcc_world)
    assert cm.add_consequence("x", "y", trigger_type="on_death", match="Nobody Atall") == ""
    cid = cm.add_consequence("x", "y", trigger_type="on_death", match=npc.lower())
    stored = next(c for c in _active(dcc_world) if c["id"] == cid)
    assert stored["triggers"] == [{"type": "on_death", "match": f"npc:{npc}"}]  # canonical id
    cid = cm.add_consequence("x", "y", trigger_type="on_death", match="player")
    assert cid


def test_killing_an_npc_fires_its_consequence_once(dcc_world):
    npc = _an_npc(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("His secret goes public", "when he dies",
                             trigger_type="on_death", match=npc)
    other = cm.add_consequence("Unrelated", "never", trigger_type="on_death", match="player")

    result = NPCManager(dcc_world).kill_npc(npc, cause="shot in the alley")
    assert result["success"]
    assert [c["id"] for c in result["fired"]] == [cid]
    assert npc in result["fired"][0]["match_reason"]

    data = _load(dcc_world, "npcs.json")[npc]
    assert data["status"]["state"] == "dead" and data["status"]["cause"] == "shot in the alley"
    # Firing is not resolving: both still active, the fired one logged.
    assert {c["id"] for c in _active(dcc_world)} >= {cid, other}
    prov = _load(dcc_world, "consequences.json")["provenance"]
    assert prov[-1]["id"] == cid

    again = NPCManager(dcc_world).kill_npc(npc)
    assert not again["success"]  # already dead: on_death cannot fire twice


def test_the_dead_are_not_present(dcc_world):
    npc = _an_npc(dcc_world)
    npcs = _load(dcc_world, "npcs.json")
    npcs[npc].get("status", {}).pop("party_member", None)
    scene = {"location": "Alley", "present": [npc]}
    assert npc in npcs_present(npcs, "Alley", scene)
    npcs[npc].setdefault("status", {})["state"] = "dead"
    assert npc not in npcs_present(npcs, "Alley", scene)


def test_a_killed_npc_leaves_the_scene(dcc_world):
    from tests.scene_helpers import put_in_scene
    put_in_scene(_cdir(dcc_world), "Mordecai")
    NPCManager(dcc_world).kill_npc("Mordecai")
    assert "Mordecai" not in _load(dcc_world, "campaign-overview.json")["scene"]["present"]


def test_on_death_is_not_fired_by_the_scene_check(dcc_world):
    """Event triggers never match on moves or time steps."""
    npc = _an_npc(dcc_world)
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("x", "y", trigger_type="on_death", match=npc)
    c = next(c for c in _active(dcc_world) if c["id"] == cid)
    assert cm._matches_now(c, {"location": npc, "present_npcs": [npc]}) == ""


def _short(world, cid):
    """The shortest prefix (at least 4 characters) no other active id shares."""
    others = [c["id"] for c in _active(world) if c["id"] != cid]
    n = 4
    while any(o.startswith(cid[:n]) for o in others):
        n += 1
    return cid[:n]


def test_fire_by_hand_with_a_short_id(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The Fork bargains", "someone is alone with the chip")
    hit = cm.fire(_short(dcc_world, cid), reason="Old Iron kept the chip alone overnight")
    assert hit["id"] == cid
    assert hit["match_reason"] == "Old Iron kept the chip alone overnight"
    assert cid in {c["id"] for c in _active(dcc_world)}  # still active
    assert cm.fire("zzzz") == {}


def test_resolve_accepts_a_short_id(dcc_world):
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("x", "y")
    assert cm.resolve(_short(dcc_world, cid))
    assert cid not in {c["id"] for c in _active(dcc_world)}


def test_player_death_fires_on_death_player(dcc_world):
    from lib.player_manager import PlayerManager
    cm = ConsequenceManager(dcc_world)
    cid = cm.add_consequence("The crew splits the loot", "when he dies",
                             trigger_type="on_death", match="player")
    pm = PlayerManager(dcc_world)
    result = pm.kill_character(cause="fell")
    assert result["success"]
    assert [c["id"] for c in result["fired"]] == [cid]


def _fact(world, fid):
    return next(f for items in _load(world, "facts.json").values() for f in items
                if isinstance(f, dict) and f.get("id") == fid)


def test_npc_kill_records_the_death_as_a_fact(dcc_world):
    npc = _an_npc(dcc_world)
    result = NPCManager(dcc_world).kill_npc(npc, cause="shot in the alley")
    fact = _fact(dcc_world, result["fact"])
    assert fact["fact"] == f"{npc} died: shot in the alley"
    assert fact in _load(dcc_world, "facts.json")["session_events"]


def test_player_kill_records_the_death_as_a_fact(dcc_world):
    from lib.player_manager import PlayerManager
    name = _load(dcc_world, "character.json")["identity"]["name"]
    result = PlayerManager(dcc_world).kill_character()
    assert _fact(dcc_world, result["fact"])["fact"] == f"{name} (the player character) died."
