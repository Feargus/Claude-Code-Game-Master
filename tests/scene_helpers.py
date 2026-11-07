"""Put NPCs into the current scene of a test campaign (see lib/scene_manager.py).

Presence is the scene list, not location tags, so a test that wants an NPC
"here" writes it the way gm-scene.sh enter does.
"""

import json
from pathlib import Path


def put_in_scene(campaign_dir, *names):
    p = Path(campaign_dir) / "campaign-overview.json"
    overview = json.loads(p.read_text(encoding="utf-8"))
    here = (overview.get("player_position") or {}).get("current_location", "")
    scene = overview.get("scene") or {}
    present = list(scene.get("present") or []) if scene.get("location") == here else []
    overview["scene"] = {"location": here, "present": present + [n for n in names if n not in present]}
    p.write_text(json.dumps(overview, indent=2), encoding="utf-8")
