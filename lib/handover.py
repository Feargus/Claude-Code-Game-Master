#!/usr/bin/env python3
"""Handing the story to another character: what a person knows stays theirs.

Facts and consequences name people by id, and the character being played is
`player`. When the player takes over someone else, the ids follow the people,
not the seat:

- the outgoing character (on `--replace`) goes into npcs.json as an NPC sheet
  (sheet.as_npc), and everything that said `player` now says `npc:<their name>`:
  what they knew, what is known about them, the triggers waiting on them;
- a canon character (`--canon`) was `npc:<name>`, and is `player` from now on.
  Their sheet moves from npcs.json to character.json (new_character.py), and they
  leave the scene list.

Used by new_character.py; the GM never calls it directly.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import sheet as sheet_mod


def _swap(ids: List[str], old: str, new: str) -> List[str]:
    """`ids` with `old` replaced by `new`, without duplicates, order kept."""
    out = []
    for cid in ids:
        cid = new if cid == old else cid
        if cid not in out:
            out.append(cid)
    return out


def _learn_match(match: str, old: str, new: str) -> str:
    """An on_learn match with `old` replaced on either side. The stored form is
    "<who> learns <fact id>" or "<who> learns about:<id>" (consequence_manager's
    _learn_target); "about <id>" with a space is read too, and written back in
    the stored form, the one fire_event compares with."""
    who, sep, what = match.partition(" learns ")
    if not sep:
        return match
    if who.strip() == old:
        who = new
    about = what.strip()
    if about.startswith("about:") or about.startswith("about "):
        target = about[len("about"):].lstrip(": ").strip()
        what = f"about:{new if target == old else target}"
    return f"{who}{sep}{what}"


def move_id(json_ops, old: str, new: str) -> List[str]:
    """Rewrite `old` to `new` in the facts (holders, about) and the active
    consequences (triggers, tell effects). Returns notes for the GM about
    anything that no longer makes sense."""
    notes = []
    facts = json_ops.load_json("facts.json") or {}
    changed = 0
    for items in facts.values():
        if not isinstance(items, list):
            continue
        for fact in items:
            if not isinstance(fact, dict):
                continue
            for field in ("holders", "about"):
                if old in (fact.get(field) or []):
                    fact[field] = _swap(fact[field], old, new)
                    changed += 1
    if changed:
        json_ops.save_json("facts.json", facts)

    store = json_ops.load_json("consequences.json") or {}
    changed = 0
    for item in store.get("active", []) if isinstance(store, dict) else []:
        for trigger in item.get("triggers") or []:
            match = trigger.get("match")
            if not isinstance(match, str):
                continue
            if trigger.get("type") == "on_learn":
                rewritten = _learn_match(match, old, new)
            else:
                rewritten = new if match == old else match
            if rewritten != match:
                trigger["match"] = rewritten
                changed += 1
                if trigger.get("type") == "on_npc" and new == "player":
                    notes.append(f"Consequence {item.get('id')} waited for {old} to appear, who "
                                 f"is now the player: resolve or replace it.")
        if item.get("trigger") == old:
            item["trigger"] = new
        for effect in item.get("effects") or []:
            if old in (effect.get("holders") or []):
                effect["holders"] = _swap(effect["holders"], old, new)
                changed += 1
    if changed:
        json_ops.save_json("consequences.json", store)
    return notes


def _former_record(old: Dict[str, Any], npcs: Dict[str, Any]) -> str:
    """Put the outgoing character into npcs.json as an NPC sheet. Returns its key."""
    name = sheet_mod.name(old) or "former character"
    key = name if name not in npcs else f"{name} (former character)"
    npc = sheet_mod.as_npc(old)
    npc["identity"]["name"] = key
    npcs[key] = npc
    return key


def hand_over(json_ops, outgoing: Optional[Dict[str, Any]], canon: Optional[str],
              timestamp: str = "") -> List[str]:
    """Move the ids when the story passes from `outgoing` (the old sheet, or None)
    to the canon NPC `canon` (a key in npcs.json, or None). Returns notes."""
    notes = []
    if outgoing:
        npcs = json_ops.load_json("npcs.json") or {}
        key = _former_record(outgoing, npcs)
        json_ops.save_json("npcs.json", npcs)
        notes += move_id(json_ops, "player", f"npc:{key}")
        notes.append(f"{sheet_mod.name(outgoing)} is npc:{key} now, with what they knew. The new "
                     f"character knows only what they witnessed or were told: "
                     f"gm-note.sh witness / tell.")
    if canon:
        npcs = json_ops.load_json("npcs.json") or {}
        if canon in npcs:
            del npcs[canon]  # the sheet is character.json now
            json_ops.save_json("npcs.json", npcs)
        overview = json_ops.load_json("campaign-overview.json") or {}
        scene = overview.get("scene")
        if isinstance(scene, dict) and canon in (scene.get("present") or []):
            scene["present"] = [n for n in scene["present"] if n != canon]
            json_ops.save_json("campaign-overview.json", overview)
        notes += move_id(json_ops, f"npc:{canon}", "player")
    return notes
