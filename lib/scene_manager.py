#!/usr/bin/env python3
"""Who is in the current scene (gm-scene.sh).

The scene list lives in campaign-overview.json next to the location it belongs
to: {"scene": {"location": "Old Iron's Yard", "present": ["Old Iron", "Tally"]}}.
Party members are always present and never listed. Every move resets the list,
so only the party comes along; a list stored for another location counts as
empty. Location tags only say where an NPC is usually found.

Presence is read by entity_manager.npcs_present: the session brief's NPC block,
on_npc triggers, a fact's default holders, the ready-threads nudge.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from entity_manager import is_dead, is_party_member, npcs_present, npcs_usually_at
from json_ops import JsonOperations

OVERVIEW = "campaign-overview.json"


class SceneManager:
    def __init__(self, world_state_dir: str = None):
        manager = CampaignManager(world_state_dir) if world_state_dir else CampaignManager()
        campaign_dir = manager.get_active_campaign_dir()
        if campaign_dir is None:
            raise RuntimeError("No active campaign. Run /new-game or /import first.")
        self.json_ops = JsonOperations(str(campaign_dir))

    def _overview(self) -> dict:
        return self.json_ops.load_json(OVERVIEW) or {}

    def location(self) -> str:
        pos = self._overview().get("player_position") or {}
        return pos.get("current_location", "") if isinstance(pos, dict) else ""

    def _npcs(self) -> dict:
        return self.json_ops.load_json("npcs.json") or {}

    def _listed(self, overview: dict) -> list[str]:
        """The stored list, if it belongs to the current location."""
        scene = overview.get("scene") or {}
        pos = overview.get("player_position") or {}
        here = pos.get("current_location", "") if isinstance(pos, dict) else ""
        if str(scene.get("location", "")).lower() != str(here).lower():
            return []
        return list(scene.get("present") or [])

    def _save(self, overview: dict, listed: list[str]) -> None:
        pos = overview.get("player_position") or {}
        overview["scene"] = {"location": pos.get("current_location", ""), "present": listed}
        self.json_ops.save_json(OVERVIEW, overview)

    def present(self) -> dict[str, dict]:
        overview = self._overview()
        return npcs_present(self._npcs(), self.location(), overview.get("scene"))

    def usually_here(self) -> list[str]:
        """NPCs tagged with this place who aren't in the scene."""
        here = self.present()
        return [n for n in npcs_usually_at(self._npcs(), self.location()) if n not in here]

    def _resolve(self, names) -> tuple[list[str], list[str]]:
        """(NPC keys, errors), through the shared resolver."""
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        keys, errors = [], []
        for raw in names:
            raw = str(raw).strip()
            cid, error = ids.resolve(raw if raw.lower().startswith("npc:") else f"npc:{raw}")
            if error:
                errors.append(error)
            elif cid[4:] not in keys:
                keys.append(cid[4:])
        return keys, errors

    def enter(self, names) -> dict[str, list[str]]:
        """NPCs join the scene. Returns {"entered", "already"}; raises ValueError
        (and changes nothing) for an unknown or dead NPC."""
        keys, errors = self._resolve(names)
        npcs = self._npcs()
        errors += [f"{k} is dead." for k in keys if is_dead(npcs[k])]
        if errors:
            raise ValueError("; ".join(errors))
        overview = self._overview()
        listed = self._listed(overview)
        already = [k for k in keys if k in listed or is_party_member(npcs[k])]
        entered = [k for k in keys if k not in already]
        if entered:
            self._save(overview, listed + entered)
        return {"entered": entered, "already": already}

    def leave(self, names, strict: bool = True) -> list[str]:
        """NPCs leave the scene. Returns those who left. A party member can't
        leave this way (gm-npc.sh demote). `strict=False` ignores unknown names."""
        keys, errors = self._resolve(names)
        if errors and strict:
            raise ValueError("; ".join(errors))
        npcs = self._npcs()
        party = [k for k in keys if is_party_member(npcs[k])]
        if party and strict:
            raise ValueError(f"{', '.join(party)}: party members are always present; "
                             f"gm-npc.sh demote first.")
        overview = self._overview()
        listed = self._listed(overview)
        gone = [k for k in keys if k in listed]
        if gone:
            self._save(overview, [k for k in listed if k not in gone])
        return gone

    def reset(self) -> None:
        """A move: the new scene starts with only the party."""
        self._save(self._overview(), [])

    def describe(self) -> str:
        here = self.present()
        lines = [f"Scene: {self.location() or '(no location)'}",
                 f"Present: {', '.join(here) if here else 'nobody but the player'}"]
        usual = self.usually_here()
        if usual:
            lines.append(f"Usually found here, not in the scene: {', '.join(usual)} "
                         f"(if one is actually here: gm-scene.sh enter <name>)")
        return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    action = args[0] if args else "show"
    try:
        sm = SceneManager()
        if action == "show" and len(args) <= 1:
            print(sm.describe())
        elif action == "enter" and args[1:]:
            result = sm.enter(args[1:])
            if result["entered"]:
                print(f"Entered: {', '.join(result['entered'])}")
            if result["already"]:
                print(f"Already here: {', '.join(result['already'])}")
            print(sm.describe())
        elif action == "leave" and args[1:]:
            gone = sm.leave(args[1:])
            print(f"Left: {', '.join(gone)}" if gone else "Nobody left: they weren't in the scene.")
            print(sm.describe())
        else:
            print("Usage: scene_manager.py [show] | enter <npc>... | leave <npc>...", file=sys.stderr)
            return 1
    except (RuntimeError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
