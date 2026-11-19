#!/usr/bin/env python3
"""
World Kit: the per-campaign ruleset that sits on top of the generic game core.

A campaign's `ruleset.json` declares what that world adds on top of the standard
rules: its name, its own rules (world_rules.py: `rules` and `plain_rules`, made
with gm-rule.sh define), the skills it declares, and which specialist agents are
active. Rolls, wounds and growth (XP, levels, skills that improve with use) are the
same for every campaign.

ruleset.json shape:
{
  "name": "Dungeon Crawler Carl",
  "active_agents": ["npc-builder"],
  "skills": ["might", "guile"],  # optional; absent → []
  "rules": [ {"name": "Bleed", "block": "counter", ...} ],   # world_rules.py
  "plain_rules": ["Credits are zeds.", ...]
}
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from json_ops import JsonOperations

# The standard rules: what a campaign without its own ruleset.json plays by (a
# world made from one sentence, a new world before its kit is drafted). The rolls, attributes,
# skills and wounds are the repo's (gm-skills, gm-combat); a campaign's
# ruleset only adds on top: its own rules.
STANDARD_NAME = "Standard rules"
DEFAULT_RULESET = {
    "name": STANDARD_NAME,
    "active_agents": [],
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

    def active_agents(self) -> list[str]:
        return self.ruleset.get("active_agents", [])

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
        "active_agents": kit.active_agents(),
        "rules": [r.get("name") for r in kit.ruleset.get("rules") or [] if isinstance(r, dict)],
    }
    if json_mode:
        emit(info, json_mode=True)
    else:
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
