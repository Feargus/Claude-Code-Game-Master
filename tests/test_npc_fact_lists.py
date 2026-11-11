"""What a present NPC knows, and what is known about them, in the brief.

Under each present NPC: "they know" lists facts with them among the holders;
"about them, they don't know" lists facts about them they don't hold. Facts
from before holders existed can't say who knows them: they go under "about
them (old fact ...)" when the same name check gm-note.sh uses finds the NPC.
Being named in a fact is never knowing it (the old `remembers:` lines were).

These tests mutate only the hermetic `dcc_world` copy: they add a present NPC
(in the current scene) plus facts, then read get_full_context().
"""

import json
from pathlib import Path

from lib.session_manager import SessionManager
from tests.scene_helpers import put_in_scene
from tests.sheets import npc


def _load(world, name):
    return json.loads((Path(world) / "campaigns" / "dungeon-crawler-carl" / name).read_text())


def _save(world, name, data):
    (Path(world) / "campaigns" / "dungeon-crawler-carl" / name).write_text(
        json.dumps(data, indent=2))


def _current_location(world):
    overview = _load(world, "campaign-overview.json")
    return overview.get("player_position", {}).get("current_location")


def _add_npc(world, name, location, aliases=None):
    npcs = _load(world, "npcs.json")
    npcs[name] = npc(name, aliases=aliases, places=[location])
    _save(world, "npcs.json", npcs)
    if location == _current_location(world):
        put_in_scene(Path(world) / "campaigns" / "dungeon-crawler-carl", name)


def _add_facts(world, category, texts, **fields):
    """Old-style facts (no holders) unless fields like holders=[...] are given."""
    facts = _load(world, "facts.json")
    facts.setdefault(category, [])
    for t in texts:
        facts[category].append({"fact": t, "timestamp": "2026-08-15T00:00:00Z", **fields})
    _save(world, "facts.json", facts)


OLD = "about them (old fact: who knows it isn't recorded): "


def _npc_block(ctx, npc_name):
    """Lines belonging to one present-NPC entry (header -> next header/blank)."""
    lines = ctx.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(f"{npc_name}:") or ln.startswith(f"{npc_name} ("):
            start = i
            break
    assert start is not None, f"{npc_name} not rendered as a present NPC"
    block = []
    for ln in lines[start + 1:]:
        if ln and not ln.startswith("  "):  # next NPC header or new section
            break
        block.append(ln)
    return "\n".join(block)


def test_fact_naming_present_npc_surfaces_under_that_npc(dcc_world):
    loc = _current_location(dcc_world)
    fact = "Griselda's eyes flicked to the back door — she knows more than she lets on."
    _add_npc(dcc_world, "Griselda", loc)
    _add_facts(dcc_world, "npc_relations", [fact])

    ctx = SessionManager(dcc_world).get_full_context()
    block = _npc_block(ctx, "Griselda")
    assert OLD + fact in block, "an old fact naming the NPC is about them, not known by them"


def test_fact_naming_no_present_npc_is_not_attached(dcc_world):
    loc = _current_location(dcc_world)
    unrelated = "Zoltar the Unseen brooded in a tower far from any living soul."
    _add_npc(dcc_world, "Griselda", loc)
    _add_facts(dcc_world, "npc_relations", [unrelated])

    ctx = SessionManager(dcc_world).get_full_context()
    block = _npc_block(ctx, "Griselda")
    assert unrelated not in block


def test_word_boundary_substring_is_not_a_false_positive(dcc_world):
    loc = _current_location(dcc_world)
    banana = "The crawlers found a crate of Banana rations near the vending machine."
    _add_npc(dcc_world, "Ana", loc)
    _add_facts(dcc_world, "npc_relations", [banana])

    ctx = SessionManager(dcc_world).get_full_context()
    # "Ana" must not match inside "Banana".
    assert banana not in _npc_block(ctx, "Ana")


def test_common_leading_token_is_not_a_false_positive(dcc_world):
    """A multi-token NPC whose first token is a common word must NOT vacuum up
    ordinary lowercase prose that merely starts with that word."""
    loc = _current_location(dcc_world)
    rope = "the old rope frayed against the pier"
    door = "The red door creaked open on rusted hinges."
    _add_npc(dcc_world, "Old Man Withers", loc)
    _add_npc(dcc_world, "Red Sonja", loc)
    _add_facts(dcc_world, "world_events", [rope, door])

    ctx = SessionManager(dcc_world).get_full_context()
    # Neither fact names a real NPC, so it attaches under no one.
    assert rope not in _npc_block(ctx, "Old Man Withers")
    assert rope not in _npc_block(ctx, "Red Sonja")
    assert door not in _npc_block(ctx, "Old Man Withers")
    assert door not in _npc_block(ctx, "Red Sonja")


def test_full_multiword_key_still_attaches(dcc_world):
    """A fact naming the whole NPC key still surfaces under that NPC."""
    loc = _current_location(dcc_world)
    fact = "Old Man Withers cursed the merchant who shorted him."
    _add_npc(dcc_world, "Old Man Withers", loc)
    _add_facts(dcc_world, "npc_relations", [fact])

    ctx = SessionManager(dcc_world).get_full_context()
    assert OLD + fact in _npc_block(ctx, "Old Man Withers")


def test_alias_path_attaches(dcc_world):
    """A fact mentioning an explicit alias attaches under the NPC."""
    loc = _current_location(dcc_world)
    fact = "Aratus the Kothian bargained hard for the caravan's silk."
    _add_npc(dcc_world, "Aratus", loc, aliases=["Aratus the Kothian"])
    _add_facts(dcc_world, "npc_relations", [fact])

    ctx = SessionManager(dcc_world).get_full_context()
    assert OLD + fact in _npc_block(ctx, "Aratus")


# ---------- facts with holders ----------

def test_they_know_what_they_hold(dcc_world):
    _add_npc(dcc_world, "Griselda", _current_location(dcc_world))
    _add_facts(dcc_world, "session_events", ["The vault code is 0451."],
               holders=["player", "npc:Griselda"])
    block = _npc_block(SessionManager(dcc_world).get_full_context(), "Griselda")
    assert "they know: The vault code is 0451." in block


def test_about_them_but_not_known_to_them(dcc_world):
    _add_npc(dcc_world, "Griselda", _current_location(dcc_world))
    _add_facts(dcc_world, "session_events", ["Griselda's brother sold her out."],
               about=["npc:Griselda"], holders=["player"])
    block = _npc_block(SessionManager(dcc_world).get_full_context(), "Griselda")
    assert "about them, they don't know: Griselda's brother sold her out." in block
    assert "they know: Griselda's brother" not in block


def test_named_in_a_new_fact_is_not_knowing_it(dcc_world):
    """A new fact (with holders) that names them but has no `about` for them
    isn't attached by the name check: the about list at write time decides."""
    _add_npc(dcc_world, "Griselda", _current_location(dcc_world))
    _add_facts(dcc_world, "lore", ["Griselda is a common name in the north."], holders=[])
    block = _npc_block(SessionManager(dcc_world).get_full_context(), "Griselda")
    assert "common name" not in block


def test_a_long_list_is_capped_and_disclosed(dcc_world):
    _add_npc(dcc_world, "Griselda", _current_location(dcc_world))
    _add_facts(dcc_world, "lore", [f"Secret number {i}." for i in range(5)],
               holders=["npc:Griselda"])
    sm = SessionManager(dcc_world)
    block = _npc_block(sm.get_full_context(), "Griselda")
    assert block.count("they know:") == 3 and "+2 more facts they know" in block
    assert _npc_block(sm.get_full_context(full=True), "Griselda").count("they know:") == 5
