#!/usr/bin/env python3
"""
World Kit: the per-campaign ruleset that sits on top of the generic game core.

A campaign's `ruleset.json` declares what that world adds on top of the standard
rules: its own counters (vitals), its signature systems, its rules prose and
which specialist agents are active. Rolls, wounds and growth (XP, levels, skills
that improve with use) are the same for every campaign. Signature systems on the kit are the
play-time rules surface (rendered in scene context). campaign-overview's
`campaign_rules` is the legacy fallback when the kit has none.

ruleset.json shape:
{
  "name": "Dungeon Crawler Carl",
  "stat_schema": { "vitals": ["hp"] },   # attributes are fixed: the nine in skill_contest
  "active_agents": ["npc-builder"],
  "skills": ["might", "guile"],  # optional; absent → []
  "signature_systems": [ { "name": "...", "summary": "...", "rules": "..." } ],
  "rules_doc": "rules.md"        # optional: campaign-scoped rules prose, loaded on demand
}
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from json_ops import JsonOperations

# The standard rules: what a campaign without its own ruleset.json plays by (a
# world made from one sentence, a new world before its kit is drafted). The rolls, attributes,
# skills and wounds are the repo's (gm-skills, gm-combat); a campaign's
# ruleset only adds on top: its own counters (vitals), signature systems.
# Vitals are those extra counters, so none here.
STANDARD_NAME = "Standard rules"
DEFAULT_RULESET = {
    "name": STANDARD_NAME,
    "stat_schema": {"vitals": []},
    "active_agents": [],
    "rules_doc": None,
}


class WorldKit:
    """Loads a campaign's ruleset.json: what its world adds to the standard rules."""

    def __init__(self, world_state_dir: str = None):
        base = world_state_dir or "world-state"
        cm = CampaignManager(base)
        self.campaign_dir = cm.get_active_campaign_dir()
        self.json_ops = JsonOperations(str(self.campaign_dir))
        self.ruleset = self.json_ops.load_json("ruleset.json") or dict(DEFAULT_RULESET)

    # --- declared configuration ---
    def name(self) -> str:
        return self.ruleset.get("name", STANDARD_NAME)

    def stat_schema(self) -> dict[str, Any]:
        return self.ruleset.get("stat_schema", {})

    def vitals(self) -> list[str]:
        """The campaign's own counters (Drift, corruption, water, ...), on top of
        the standard rules; [] when it declares none. Never 'hp': wounds replaced
        it, and every character has a body (gm-body.sh)."""
        declared = (self.stat_schema() or {}).get("vitals") or []
        return [v for v in declared if str(v).lower() != "hp"]

    def active_agents(self) -> list[str]:
        return self.ruleset.get("active_agents", [])

    def rules_doc_path(self) -> Path | None:
        """Path to the campaign's rules prose (loaded on demand), if declared + present."""
        doc = self.ruleset.get("rules_doc")
        if not doc:
            return None
        p = self.campaign_dir / doc
        return p if p.exists() else None

    def campaign_rules(self) -> dict[str, Any]:
        """World-flavor systems (loot boxes, viewers, ...) from campaign-overview.

        Legacy fallback for scene context when `signature_systems()` is empty.
        """
        overview = self.json_ops.load_json("campaign-overview.json") or {}
        return overview.get("campaign_rules", {})

    def skills(self) -> list[str]:
        """Skill names this kit declares, or [] when the ruleset has none."""
        raw = self.ruleset.get("skills") or []
        if isinstance(raw, dict):
            return [str(k) for k in raw]
        if not isinstance(raw, list):
            return []
        names: list[str] = []
        for item in raw:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        return names

    def signature_systems(self) -> list[dict[str, str]]:
        """Normalize ruleset.signature_systems to a list of {name, summary}.

        Canonical form is a list of `{name, summary, rules?}`. The Conan
        migration case is a dict of name → summary string (or name →
        `{summary, rules}`). Bare strings in a list become name=summary.
        Missing or empty → [].
        """
        return _normalize_signature_systems(self.ruleset.get("signature_systems"))

    def systems(self) -> list[dict[str, Any]]:
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


def _normalize_signature_systems(raw: Any) -> list[dict[str, str]]:
    if not raw:
        return []
    items: list[dict[str, str]] = []
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


def _one_signature_system(name: str, val: Any) -> dict[str, str]:
    if isinstance(val, str):
        return {"name": name, "summary": val}
    if not isinstance(val, dict):
        return {"name": name, "summary": str(val) if val else ""}
    sys_name = str(val.get("name") or name)
    summary = val.get("summary")
    rules = val.get("rules")
    if not isinstance(summary, str):
        summary = "" if summary is None else str(summary)
    entry: dict[str, str] = {"name": sys_name, "summary": summary}
    if not entry["summary"] and rules:
        entry["summary"] = rules if isinstance(rules, str) else str(rules)
    elif rules and rules != entry["summary"]:
        entry["rules"] = rules if isinstance(rules, str) else str(rules)
    return entry


def main():
    import argparse
    import json

    from cli_output import emit, strip_json_flag, wants_json

    parser = argparse.ArgumentParser(description="World Kit info")
    parser.add_argument("action", nargs="?", default="info", choices=["info"])
    json_mode = wants_json()
    parser.parse_args(strip_json_flag(sys.argv[1:]))

    kit = WorldKit()
    info = {
        "name": kit.name(),
        "stat_schema": kit.stat_schema(),
        "active_agents": kit.active_agents(),
        "rules_doc": str(kit.rules_doc_path()) if kit.rules_doc_path() else None,
    }
    if json_mode:
        emit(info, json_mode=True)
    else:
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
