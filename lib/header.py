#!/usr/bin/env python3
"""The header: one line at the top of a reply, printed from the records, never
written from memory (one written by the GM goes stale: "XP 0/100" for a whole
session at 40 XP).

    Bleach Alley · 14:52
    The Back Lanes · 16:55 · right arm critical
    Mama Ossu's · Tuesday, 15 March 2089 · 11:40 · 28 credits · level-up due

- always: the place and the time;
- the date: when the day changed since the header was last shown, or with --full
  (the start of a session);
- credits: when they changed since then, or with --full;
- the worst wound still healing (bruised, injured, critical), while there is one;
- "level-up due" while growth is due.

What was last shown is kept in campaign-overview.json (`header_shown`). The GM runs
`gm-session.sh header` when the line would help, at least every few replies; a reply
without a fresh one has no header.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

WORDS = {1: "bruised", 2: "injured", 3: "critical"}
LABELS = {"head": "head", "chest": "chest", "groin": "groin", "left_arm": "left arm",
          "right_arm": "right arm", "left_leg": "left leg", "right_leg": "right leg"}


def worst_wound(sheet: dict[str, Any]) -> str:
    """'right arm critical', 'left arm, chest injured', or '' (a destroyed limb, for
    good, is on the sheet, not in the header)."""
    zones = ((sheet.get("body") or {}).get("zones") or {})
    healing = {z: int(p.get("wounds", 0)) for z, p in zones.items()
               if 0 < int(p.get("wounds", 0)) < 4}
    if not healing:
        return ""
    worst = max(healing.values())
    return f"{', '.join(LABELS.get(z, z) for z, n in healing.items() if n == worst)} {WORDS[worst]}"


def line(json_ops, full: bool = False) -> str:
    """The header, and what it showed remembered for next time."""
    import growth
    from game_time import current_time
    from time_manager import derive_date
    overview = json_ops.load_json("campaign-overview.json") or {}
    sheet = json_ops.load_json("character.json") or {}
    shown = overview.get("header_shown") or {}
    position = overview.get("player_position") or {}
    parts = [position.get("current_location") or "nowhere yet"]
    now = current_time(json_ops)
    if now is not None:
        day = now.strftime("%Y-%m-%d")
        if full or shown.get("date") != day:
            parts.append(derive_date(now))
        parts.append(f"{now:%H:%M}")
    credits = (sheet.get("possessions") or {}).get("credits")
    if credits is not None and (full or shown.get("credits") != credits):
        from world_bible import currency
        parts.append(f"{credits} {currency(json_ops)}")
    wound = worst_wound(sheet)
    if wound:
        parts.append(wound)
    if sheet and growth.growth_due(sheet):
        parts.append("level-up due")
    overview["header_shown"] = {"date": now.strftime("%Y-%m-%d") if now else "", "credits": credits}
    json_ops.save_json("campaign-overview.json", overview)
    return " · ".join(parts)
