#!/usr/bin/env python3
"""Reading the campaign's game time: the one place that knows where it is kept.

`game_time` in campaign-overview.json holds the in-game date and time as text,
e.g. "2187-10-26T04:30" (STORED_FORMAT). Changing it is time_manager.py's job;
this module only reads it, and imports nothing of the game's, so every script
can import it at the top (time_manager.py and threat_clocks.py import each
other, which is why each script used to read the time by itself).
"""

from datetime import datetime
from typing import Optional

STORED_FORMAT = "%Y-%m-%dT%H:%M"
OVERVIEW = "campaign-overview.json"


def stored_time(json_ops) -> str:
    """The game time as stored ("2187-10-26T04:30"), or '' if the campaign has
    none yet. `json_ops` is a JsonOperations on the campaign's folder."""
    return str((json_ops.load_json(OVERVIEW) or {}).get("game_time") or "")


def current_time(json_ops) -> Optional[datetime]:
    """The game time as a datetime, or None if the campaign has none yet."""
    stored = stored_time(json_ops)
    return datetime.strptime(stored, STORED_FORMAT) if stored else None
