#!/usr/bin/env python3
"""The character's body and luck recover as game time passes (decided 2026-11-21).

Every missing point comes back on a half-life: within a time Δt it does with
probability 1 − 2^(−Δt/T). That is memoryless, so one long time step and many short
ones give the same odds, and it works with whole numbers. It runs at every time step
(time_manager.py), never stops time, and what came back goes into the timeline.

- **Wounds:** a zone heals one box at a time, from the top down: a critical wound
  (3) becomes an injury, an injury (2) a bruise, a bruise (1) nothing. Half-lives
  before care: HALF_LIFE_DAYS. Time counts more with care, the factors multiplied:
  lying still (asleep, or in a hospital bed: `gm-time.sh advance … --rest`) ×2, first
  aid ×2, a doctor's treatment ×2 more (body.treat). A critical wound heals only
  after a doctor's treatment or first aid with a medpack or the like; without it, it
  stays critical. A destroyed zone never heals. The care ends when the zone has
  healed or is wounded again.
- **Luck:** each spent point comes back on its own, half-life LUCK_HALF_LIFE_DAYS;
  rest doesn't speed it up.

The numbers are first guesses, to revise in play.
"""

import math
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

HALF_LIFE_DAYS = {1: 2, 2: 4, 3: 8}        # bruise, injured, critical; before care
LUCK_HALF_LIFE_DAYS = 7
REST, FIRST_AID, DOCTOR = 2, 2, 2          # how much faster the time counts
CRITICAL = 3


def _care_factor(part: dict[str, Any]) -> int:
    import body
    care = part.get("care") or []
    return (FIRST_AID if body.FIRST_AID in care else 1) * (DOCTOR if body.DOCTOR in care else 1)


def _can_heal(part: dict[str, Any]) -> bool:
    import body
    care = part.get("care") or []
    return part["wounds"] < CRITICAL or body.DOCTOR in care or body.SUPPLIED in care


def heal_zone(part: dict[str, Any], days: float, rng) -> int:
    """Let `days` of (care-weighted) time pass for one zone: one box after the other,
    each after an exponentially distributed wait (memoryless, so what is left of one
    step's wait isn't carried over). Returns how many boxes healed."""
    import body
    healed = 0
    while 0 < part["wounds"] < body.FLESH_BOXES and _can_heal(part):
        rate = math.log(2) / HALF_LIFE_DAYS[part["wounds"]]
        wait = rng.expovariate(rate)
        if wait > days:
            break
        days -= wait
        part["wounds"] -= 1
        healed += 1
    if not part["wounds"]:
        part.pop("care", None)
    return healed


def recover(json_ops, before, after, resting: bool = False, rng=None) -> list[str]:
    """Let the time from `before` to `after` pass for the character's body and luck;
    saves the sheet. Returns what came back, a line each."""
    import body
    from entity_manager import is_dead
    if before is None or after <= before:
        return []
    sheet = json_ops.load_json("character.json") or {}
    if not sheet or is_dead(sheet):
        return []
    rng = rng or random
    days = (after - before).total_seconds() / 86400
    lines = []
    for zone, part in ((sheet.get("body") or {}).get("zones") or {}).items():
        if not 0 < part.get("wounds", 0) < body.FLESH_BOXES:
            continue
        was = part["wounds"]
        if heal_zone(part, days * (REST if resting else 1) * _care_factor(part), rng):
            now = part["wounds"]
            lines.append(f"{zone.replace('_', ' ')}: {_word(was)} → {_word(now)}")
    lines += _luck(sheet, days, rng)
    if lines:
        json_ops.save_json("character.json", sheet)
    return lines


def _word(wounds: int) -> str:
    return {0: "healed", 1: "bruised", 2: "injured", 3: "critical"}[wounds]


def _luck(sheet: dict[str, Any], days: float, rng) -> list[str]:
    luck = (sheet.get("stats") or {}).get("luck")
    if not isinstance(luck, dict):
        return []
    missing = int(luck.get("max", 0)) - int(luck.get("current", 0))
    if missing <= 0:
        return []
    chance = 1 - 2 ** (-days / LUCK_HALF_LIFE_DAYS)
    back = sum(1 for _ in range(missing) if rng.random() < chance)
    if not back:
        return []
    luck["current"] = int(luck["current"]) + back
    return [f"luck: {luck['current'] - back} → {luck['current']} of {luck['max']}"]
