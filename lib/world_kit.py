#!/usr/bin/env python3
"""
World Kit: the per-campaign ruleset that sits on top of the generic game core.

A campaign's `ruleset.json` declares HOW that world plays — its stat schema, its
progression model, and which specialist agents are active —
without baking D&D 5e into the engine. The WorldKit loads it and drives play
through `game_core`, so a Dune kit and a Dungeon Crawler Carl kit run the same
core with entirely different rules. Signature systems on the kit are the
play-time rules surface (rendered in scene context). campaign-overview's
`campaign_rules` is the legacy fallback when the kit has none.

ruleset.json shape:
{
  "name": "Dungeon Crawler Carl",
  "kit": "custom",
  "stat_schema": { "attributes": ["str","con","dex","int"], "vitals": ["hp"] },
  "progression": { "model": "resource-axis", "resource": "viewers",
                   "tiers": [1000000, 1000000000] },
  "active_agents": ["npc-builder"],
  "skills": ["might", "guile"],  # optional; absent → []
  "signature_systems": [ { "name": "...", "summary": "...", "rules": "..." } ],
  "rules_doc": "rules.md"        # optional: campaign-scoped rules prose, loaded on demand
}
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from json_ops import JsonOperations
from campaign_manager import CampaignManager
from game_core import make_progression


DEFAULT_RULESET = {
    "name": "Generic Adventure",
    "kit": "custom",
    "stat_schema": {"attributes": [], "vitals": ["hp"]},
    "progression": {"model": "milestone"},
    "active_agents": [],
    "rules_doc": None,
}


class WorldKit:
    """Loads a campaign's ruleset.json and drives play through the generic core."""

    def __init__(self, world_state_dir: str = None):
        base = world_state_dir or "world-state"
        cm = CampaignManager(base)
        self.campaign_dir = cm.get_active_campaign_dir()
        self.json_ops = JsonOperations(str(self.campaign_dir))
        self.ruleset = self.json_ops.load_json("ruleset.json") or dict(DEFAULT_RULESET)
        prog = self.ruleset.get("progression", {}) or {}
        if isinstance(prog, str):          # shorthand: "progression": "milestone"
            prog = {"model": prog}
        self.progression = make_progression(
            prog.get("model", "milestone"),
            **{k: v for k, v in prog.items() if k != "model"},
        )

    # --- declared configuration ---
    def name(self) -> str:
        return self.ruleset.get("name", "Generic Adventure")

    def kit(self) -> str:
        """Kit identity: 'dnd5e' unlocks the D&D mechanics skills.

        Anything else (default 'custom') runs the generic core + this ruleset.
        Legacy rulesets without the field are 'custom' — the safe reading, since
        loading 5e mechanics into a bespoke world is the failure this prevents.
        """
        return self.ruleset.get("kit", "custom")

    def stat_schema(self) -> Dict[str, Any]:
        return self.ruleset.get("stat_schema", {})

    def vitals(self) -> List[str]:
        """Vital tracks this world declares ('hp' plus kit vitals: vigor,
        corruption, water, ...).

        A kit that declares none — no `stat_schema`, an empty list, or no ruleset at
        all — gets ['hp']. Every world has a body; returning nothing here would make
        an under-declared kit refuse plain damage.
        """
        return (self.stat_schema() or {}).get("vitals") or ["hp"]

    def progression_model(self) -> str:
        prog = self.ruleset.get("progression") or {}
        if isinstance(prog, str):
            return prog
        return prog.get("model", "milestone")

    def active_agents(self) -> List[str]:
        return self.ruleset.get("active_agents", [])

    def rules_doc_path(self) -> Optional[Path]:
        """Path to the campaign's rules prose (loaded on demand), if declared + present."""
        doc = self.ruleset.get("rules_doc")
        if not doc:
            return None
        p = self.campaign_dir / doc
        return p if p.exists() else None

    def campaign_rules(self) -> Dict[str, Any]:
        """World-flavor systems (loot boxes, viewers, ...) from campaign-overview.

        Legacy fallback for scene context when `signature_systems()` is empty.
        """
        overview = self.json_ops.load_json("campaign-overview.json") or {}
        return overview.get("campaign_rules", {})

    def skills(self) -> List[str]:
        """Skill names this kit declares, or [] when the ruleset has none."""
        raw = self.ruleset.get("skills") or []
        if isinstance(raw, dict):
            return [str(k) for k in raw]
        if not isinstance(raw, list):
            return []
        names: List[str] = []
        for item in raw:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        return names

    def signature_systems(self) -> List[Dict[str, str]]:
        """Normalize ruleset.signature_systems to a list of {name, summary}.

        Canonical form is a list of `{name, summary, rules?}`. The Conan
        migration case is a dict of name → summary string (or name →
        `{summary, rules}`). Bare strings in a list become name=summary.
        Missing or empty → [].
        """
        return _normalize_signature_systems(self.ruleset.get("signature_systems"))

    def systems(self) -> List[Dict[str, Any]]:
        """Executable signature-system primitives instantiated by this kit.

        Each entry is ``{primitive, name, config}`` where ``primitive`` names a
        game_core calculator (named_track / price_roll / reaction_roll /
        guarded_payoff) and ``config`` skins it for this world. Distinct from
        ``signature_systems`` (prose flavor): these are the dice the GM rolls.
        Malformed entries (no primitive or no name) are dropped.
        """
        raw = self.ruleset.get("systems") or []
        if not isinstance(raw, list):
            return []
        return [s for s in raw
                if isinstance(s, dict) and s.get("primitive") and s.get("name")]

    # --- play, driven through the generic core ---
    def advance_progression(self, state: Dict[str, Any], **kw) -> Dict[str, Any]:
        return self.progression.advance(state, **kw)

    def level(self, state: Dict[str, Any]) -> int:
        return self.progression.level(state)


def _normalize_signature_systems(raw: Any) -> List[Dict[str, str]]:
    if not raw:
        return []
    items: List[Dict[str, str]] = []
    if isinstance(raw, dict):
        for name, val in raw.items():
            items.append(_one_signature_system(str(name), val))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                items.append({"name": item, "summary": item})
            elif isinstance(item, dict):
                name = item.get("name") or item.get("title") or ""
                items.append(_one_signature_system(str(name), item))
    return [s for s in items if s.get("name") or s.get("summary")]


def _one_signature_system(name: str, val: Any) -> Dict[str, str]:
    if isinstance(val, str):
        return {"name": name, "summary": val}
    if not isinstance(val, dict):
        return {"name": name, "summary": str(val) if val else ""}
    sys_name = str(val.get("name") or name)
    summary = val.get("summary")
    rules = val.get("rules")
    if not isinstance(summary, str):
        summary = "" if summary is None else str(summary)
    entry: Dict[str, str] = {"name": sys_name, "summary": summary}
    if not entry["summary"] and rules:
        entry["summary"] = rules if isinstance(rules, str) else str(rules)
    elif rules and rules != entry["summary"]:
        entry["rules"] = rules if isinstance(rules, str) else str(rules)
    return entry


def main():
    import argparse
    import json
    from cli_output import wants_json, strip_json_flag, emit

    parser = argparse.ArgumentParser(description="World Kit info")
    parser.add_argument("action", nargs="?", default="info", choices=["info"])
    json_mode = wants_json()
    parser.parse_args(strip_json_flag(sys.argv[1:]))

    kit = WorldKit()
    info = {
        "name": kit.name(),
        "kit": kit.kit(),
        "stat_schema": kit.stat_schema(),
        "progression_model": kit.progression_model(),
        "active_agents": kit.active_agents(),
        "rules_doc": str(kit.rules_doc_path()) if kit.rules_doc_path() else None,
    }
    if json_mode:
        emit(info, json_mode=True)
    else:
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
