#!/usr/bin/env python3
"""
In-game time: one real date and time, advanced by durations.

`game_time` in campaign-overview.json is the single source of truth, e.g.
"2187-10-26T04:30", on the real (Gregorian) calendar. The words the rest of the
system reads, `time_of_day` and `current_date`, are derived from it on every
change, so the GM never writes them by hand. The GM estimates how long something
takes; this script does the arithmetic, the same way the dice script does.

Every change, `advance` or `set`, recomputes the time clocks from the new time
(see threat_clocks.py).
"""

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from json_ops import JsonOperations
from threat_clocks import ThreatClockManager

# (first hour of the day, word), in order. Same words as validators.py. Midnight
# wraps around 00:00, so it appears at both ends; "Small hours" keeps the night
# from being cut in two.
TIMES_OF_DAY = [
    (0, "Midnight"),
    (1, "Small hours"),
    (5, "Dawn"),
    (7, "Morning"),
    (11, "Noon"),
    (13, "Afternoon"),
    (17, "Evening"),
    (19, "Dusk"),
    (21, "Night"),
    (23, "Midnight"),
]

# Spelled out rather than taken from the system locale, so the date always reads
# the same.
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")

MINUTES_PER_UNIT = {
    "m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1,
    "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60,
    "d": 1440, "day": 1440, "days": 1440,
    "w": 10080, "week": 10080, "weeks": 10080,
}
_DURATION_PART = re.compile(r"(\d+)\s*([a-z]+)")

STORED_FORMAT = "%Y-%m-%dT%H:%M"


class TimeError(Exception):
    """A time command that can't be carried out. The message says how to fix it."""


def parse_duration(text: str) -> int:
    """Turn "10m", "4h", "2 days" or "1h 30m" into minutes. Refuses to guess."""
    cleaned = str(text).strip().lower().replace(",", " ")
    parts = _DURATION_PART.findall(cleaned)
    leftover = _DURATION_PART.sub(" ", cleaned).replace(" and ", " ").strip()
    if not parts or leftover:
        raise TimeError(f"Can't read the duration '{text}'. Use e.g. 10m, 4h, 2d, 1w or \"1h 30m\".")

    minutes = 0
    for number, unit in parts:
        if unit not in MINUTES_PER_UNIT:
            raise TimeError(f"Unknown unit '{unit}' in '{text}'. Use m, h, d or w.")
        minutes += int(number) * MINUTES_PER_UNIT[unit]
    if minutes <= 0:
        raise TimeError("A duration must be longer than zero.")
    return minutes


def parse_time(text: str) -> datetime:
    """Read an absolute time such as "2187-10-26 04:30"."""
    try:
        return datetime.fromisoformat(str(text).strip()).replace(second=0, microsecond=0)
    except ValueError:
        raise TimeError(f"Can't read the time '{text}'. Use \"YYYY-MM-DD HH:MM\".")


def derive_time_of_day(moment: datetime) -> str:
    return [word for start, word in TIMES_OF_DAY if start <= moment.hour][-1]


def hours_of(word: str) -> str:
    """The hours a time-of-day word covers on the game clock: "11:00–12:59" for
    Noon, "23:00–00:59" for Midnight (it wraps around 00:00); '' if unknown."""
    spans = [(start, TIMES_OF_DAY[i + 1][0] if i + 1 < len(TIMES_OF_DAY) else 24)
             for i, (start, w) in enumerate(TIMES_OF_DAY)
             if w.lower() == str(word).strip().lower()]
    if not spans:
        return ""
    if len(spans) == 2 and spans[0][0] == 0 and spans[-1][1] == 24:  # across midnight
        spans = [(spans[-1][0], spans[0][1])]
    start, end = spans[0]
    return f"{start:02d}:00–{(end - 1) % 24:02d}:59"


def all_hours() -> str:
    """Every time-of-day word with its hours, for help texts and errors."""
    words = list(dict.fromkeys(w for _, w in TIMES_OF_DAY))
    return ", ".join(f"{w.lower()} {hours_of(w)}" for w in words)


def derive_date(moment: datetime) -> str:
    return f"{DAYS[moment.weekday()]}, {moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def describe(moment: datetime) -> str:
    return f"{moment:%H:%M} ({derive_time_of_day(moment)}), {derive_date(moment)}"


class TimeManager:
    """Read and change a campaign's game time."""

    def __init__(self, world_state_dir: Optional[str] = None):
        self.world_state_dir = world_state_dir
        manager = CampaignManager(world_state_dir) if world_state_dir else CampaignManager()
        self.campaign_dir = manager.get_active_campaign_dir()
        if self.campaign_dir is None:
            raise TimeError("No active campaign. Run /new-game or /import first.")
        self.json_ops = JsonOperations(str(self.campaign_dir))

    def get_game_time(self) -> Optional[datetime]:
        stored = (self.json_ops.load_json("campaign-overview.json") or {}).get("game_time")
        return datetime.strptime(stored, STORED_FORMAT) if stored else None

    def _write(self, moment: datetime) -> None:
        data = self.json_ops.load_json("campaign-overview.json") or {}
        data["game_time"] = moment.strftime(STORED_FORMAT)
        data["time_of_day"] = derive_time_of_day(moment)
        data["current_date"] = derive_date(moment)
        if not self.json_ops.save_json("campaign-overview.json", data):
            raise TimeError("Failed to save the time.")

    def _update_clocks(self, moment: datetime) -> Dict[str, Dict]:
        return ThreatClockManager(self.world_state_dir).update_time_clocks(moment)

    def set_time(self, moment: datetime) -> Dict[str, Dict]:
        """Set the time outright. Returns the time clocks that moved."""
        self._write(moment)
        return self._update_clocks(moment)

    def advance(self, minutes: int) -> Dict[str, Dict]:
        """Let time pass. Returns the time clocks that moved."""
        before = self.get_game_time()
        if before is None:
            raise TimeError("The campaign has no game time yet. "
                            "Set it once with: gm-time.sh set \"YYYY-MM-DD HH:MM\"")
        after = before + timedelta(minutes=minutes)
        self._write(after)
        return self._update_clocks(after)


def print_clocks(moved: Dict[str, Dict]) -> None:
    from consequence_manager import print_fired
    for name, clock in moved.items():
        print(f"Clock {name}: {clock['current']}/{clock['max']}")
        if clock["current"] >= clock["max"]:
            print(f"⚠ {name} is FULL — a dramatic beat is due"
                  + (f": {clock['consequence']}" if clock.get("consequence") else ""))
    print_fired([c for clock in moved.values() for c in clock.get("fired", [])])


def main(argv) -> int:
    usage = ("Usage: time_manager.py show | advance <duration> | set \"YYYY-MM-DD HH:MM\"")
    action = argv[0] if argv else "show"
    value = " ".join(argv[1:])
    try:
        manager = TimeManager()
        if action == "advance" and value:
            moved = manager.advance(parse_duration(value))
            print(f"Time: {describe(manager.get_game_time())}")
            print_clocks(moved)
        elif action == "set" and value:
            moved = manager.set_time(parse_time(value))
            print(f"Time set: {describe(manager.get_game_time())}")
            print_clocks(moved)
        elif action == "show" and not value:
            moment = manager.get_game_time()
            print(f"Time: {describe(moment)}" if moment else
                  "No game time yet. Set it once with: gm-time.sh set \"YYYY-MM-DD HH:MM\"")
        else:
            print(usage, file=sys.stderr)
            return 1
    except TimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
