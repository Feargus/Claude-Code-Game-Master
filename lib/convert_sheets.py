#!/usr/bin/env python3
"""TEMPORARY: convert a campaign's sheets from the old formats to sheet.py's.

Converts character.json, npcs.json and mobs.json in a campaign folder, in place,
and prints what it did with every field that has no place in the new format.
Once the old campaigns are retired, this script goes (decided 2026-11-11).

    uv run python lib/convert_sheets.py <campaign folder> [--dry-run]

What goes where:
- the 11 look fields are joined into look.physique / style / presence;
- class -> identity.role; an NPC's description -> role (short) or background;
- alignment, ideals, bonds -> personality.values; flaws -> personality.fears;
- features -> traits (without an effect); equipment -> items.inventory (hidden:
  the old list didn't say what others can see);
- campaign counters (Drift) -> stats.counters;
- an NPC's events, and an attitude other than neutral, become facts the NPC holds
  about the player (category npc_memories, no game time); mood is dropped.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import sheet as sheet_mod

PHYSIQUE = ("sex", "age", "race", "species", "size", "face", "eyes", "hair")
STYLE = ("clothing", "gear")
PRESENCE = ("demeanor",)
PLAYER_DROP = ("id", "hp", "ac", "notes", "current_location", "saves", "max_hp", "speed")


def _join(fields: Dict[str, Any], keys) -> str:
    return "; ".join(str(fields[k]).strip() for k in keys if str(fields.get(k) or "").strip())


def _look(old: Dict[str, Any]) -> Dict[str, str]:
    va = old.get("visual_appearance") or {}
    look = {"physique": _join(va, PHYSIQUE), "style": _join(va, STYLE),
            "presence": _join(va, PRESENCE)}
    return {k: v for k, v in look.items() if v}


def _clean(section: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in section.items() if v not in (None, "", [], {})}


def _is_new(data: Dict[str, Any]) -> bool:
    return isinstance(data, dict) and isinstance(data.get("identity"), dict)


def convert_player(old: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    if _is_new(old):
        return old, []
    dropped = []
    values = "; ".join(str(old[k]) for k in ("alignment", "ideals", "bonds")
                       if old.get(k) and not isinstance(old[k], (dict, list)))
    traits = old.get("traits") if isinstance(old.get("traits"), dict) else {}
    traits = dict(traits, **{str(f): "" for f in old.get("features") or [] if str(f) not in traits})
    xp = old.get("xp", 0)
    known = {"name", "race", "class", "background", "alignment", "ideals", "bonds", "flaws",
             "visual_appearance", "stats", "attributes", "skills", "traits", "perks", "luck",
             "features", "body", "armor", "cyberware", "equipment", "inventory", "credits",
             "level", "xp", "practice", "status", "cause", "died_at", "died_game_time",
             "conditions", "personality", *PLAYER_DROP}
    counters = {k: v for k, v in old.items() if k not in known}
    new = {
        "identity": _clean({"name": old.get("name", ""), "race": old.get("race", ""),
                            "role": old.get("class", ""), "background": old.get("background", "")}),
        "look": _look(old),
        "personality": _clean({"values": values, "fears": old.get("flaws") or ""}),
        "stats": _clean({"attributes": old.get("attributes") or old.get("stats") or {},
                         "skills": old.get("skills") or {}, "traits": traits,
                         "perks": old.get("perks") or {}, "luck": old.get("luck") or {},
                         "counters": counters}),
        "body": {"zones": old.get("body") or {}, "armor": old.get("armor") or [],
                 "cyberware": old.get("cyberware") or []},
        # The old list didn't say what others can see: hidden (inventory) is the safe side.
        "items": _clean({"inventory": [sheet_mod.item(str(i)) for i in
                                       list(old.get("equipment") or []) + list(old.get("inventory") or [])]}),
        "possessions": {"credits": int(old.get("credits") or 0)},
        "progress": _clean({"level": int(old.get("level") or 0),
                            "xp": int(xp.get("current", 0) if isinstance(xp, dict) else xp or 0),
                            "practice": old.get("practice") or {}}),
        "status": _clean({"state": "dead" if old.get("status") == "dead" else "alive",
                          "cause": old.get("cause") or "", "died_at": old.get("died_at") or "",
                          "conditions": list(old.get("conditions") or [])}),
    }
    new["progress"].setdefault("level", 0)
    new = {k: v for k, v in new.items() if v or k in ("identity", "stats", "body")}
    for key in PLAYER_DROP:
        if old.get(key) not in (None, "", [], {}):
            dropped.append(f"{key}: {json.dumps(old[key])[:80]}")
    return sheet_mod.check(new, "player"), dropped


def convert_npc(name: str, old: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """(sheet, memories as fact texts, dropped fields)."""
    if _is_new(old):
        return old, [], []
    description = str(old.get("description") or "")
    short = len(description) <= 80
    voice = old.get("voice") or ""
    if not voice and old.get("context"):
        voice = " / ".join(str(line) for line in old["context"][:3])
    tags = old.get("tags") or {}
    new = {
        "identity": _clean({"name": name, "aliases": old.get("aliases") or [],
                            "role": description if short else "",
                            "background": "" if short else description}),
        "look": _look(old),
        "personality": _clean({"voice": voice}),
        "stats": _clean({"attributes": old.get("attributes") or {},
                         "skills": old.get("skills") or {}}),
        "body": _clean({"wounds": old.get("wounds")}),
        "places": {"usual": list(tags.get("locations") or [])},
        "status": _clean({"state": "dead" if old.get("status") == "dead" else "alive",
                          "cause": old.get("cause") or "", "died_at": old.get("died_at") or "",
                          "died_game_time": old.get("died_game_time") or "",
                          "conditions": list(old.get("conditions") or []),
                          "goal": old.get("goal") or "",
                          "party_member": bool(old.get("is_party_member")) or None,
                          "former_player_character": bool(old.get("former_player_character")
                                                          or old.get("became_pc")) or None}),
    }
    new["status"] = {k: v for k, v in new["status"].items() if v is not None}
    new = {k: v for k, v in new.items() if v or k == "identity"}
    memories = [e.get("event") if isinstance(e, dict) else str(e)
                for e in old.get("events") or []]
    attitude = str(old.get("attitude") or "").strip()
    if attitude and attitude != "neutral":
        memories.insert(0, f"{name} is {attitude} toward the player.")
    dropped = [f"{k}: {json.dumps(old[k])[:80]}" for k in
               ("current_mood", "character_sheet", "interview_show", "secret")
               if old.get(k)]
    return sheet_mod.check(new, "npc"), [m for m in memories if m], dropped


def convert_mob(name: str, old: Dict[str, Any]) -> Dict[str, Any]:
    if _is_new(old):
        return old
    new = {"identity": _clean({"name": name, "background": old.get("note") or ""}),
           "stats": {"attributes": old.get("attributes") or {}, "skills": old.get("skills") or {}},
           "body": {"wounds": int(old.get("wounds") or 1)}}
    return sheet_mod.check(new, "mob")


def _add_memories(folder: Path, memories: Dict[str, List[str]]) -> int:
    path = folder / "facts.json"
    facts = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    numbers = [int(f["id"][1:]) for items in facts.values() if isinstance(items, list)
               for f in items if isinstance(f, dict) and str(f.get("id", "")).startswith("f")
               and str(f["id"])[1:].isdigit()]
    next_id = max(numbers, default=0) + 1
    added = 0
    for name, texts in memories.items():
        for text in texts:
            facts.setdefault("npc_memories", []).append({
                "id": f"f{next_id}", "fact": text, "about": [f"npc:{name}", "player"],
                "holders": [f"npc:{name}"], "converted": "from the NPC's events in npcs.json"})
            next_id += 1
            added += 1
    if added:
        path.write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return added


def convert_campaign(folder: Path, dry_run: bool = False) -> List[str]:
    report = []
    character_path = folder / "character.json"
    if character_path.exists():
        old = json.loads(character_path.read_text(encoding="utf-8"))
        if old:
            new, dropped = convert_player(old)
            report.append(f"character.json: {sheet_mod.name(new)}")
            report += [f"  dropped {d}" for d in dropped]
            if not dry_run:
                character_path.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    npcs_path = folder / "npcs.json"
    if npcs_path.exists():
        npcs = json.loads(npcs_path.read_text(encoding="utf-8")) or {}
        converted, memories = {}, {}
        for name, old in npcs.items():
            new, mems, dropped = convert_npc(name, old)
            converted[name] = new
            if mems:
                memories[name] = mems
            report += [f"  {name}: dropped {d}" for d in dropped]
        report.insert(len(report), f"npcs.json: {len(converted)} NPCs, "
                      f"{sum(len(m) for m in memories.values())} memories to facts")
        if not dry_run:
            npcs_path.write_text(json.dumps(converted, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
            _add_memories(folder, memories)
    mobs_path = folder / "mobs.json"
    if mobs_path.exists():
        mobs = json.loads(mobs_path.read_text(encoding="utf-8")) or {}
        converted = {name: convert_mob(name, old) for name, old in mobs.items()}
        report.append(f"mobs.json: {len(converted)} mobs")
        if not dry_run:
            mobs_path.write_text(json.dumps(converted, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", nargs="+", help="campaign folder(s)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for folder in args.folder:
        print(f"== {folder}")
        for line in convert_campaign(Path(folder), args.dry_run):
            print(line)


if __name__ == "__main__":
    main()
