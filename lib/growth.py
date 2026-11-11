#!/usr/bin/env python3
"""Character growth: skills that improve with use, XP, and when a level is due.

The rules (gm-growth has the GM's side):
- Learning by use: after every skill contest the player's skill earns learnings
  from the final quality: within ±2 three, ±5 two, ±10 one, beyond nothing.
  You learn at the edge of your ability; a walkover or a hopeless attempt teaches
  nothing. Reaching skill N costs 3 × N learnings (untrained counts as 0, so the
  first point costs 3) and grants 10 × N XP.
- XP: from skill gains, defeated enemies (wounds² × 10) and achievements
  (20 / 50 / 100 % of the current level's span). Level N needs 100 × N² XP in
  total, unbounded.
- XP only makes growth due; the level on the sheet rises when the growth is
  applied (`gm-player.sh grow`), at a quiet moment in the story.
- Every award is written to the campaign's xp.log, a few readable lines each.

Functions here change the character dict they are given; callers load and save.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

LOG_FILE = "xp.log"
LEARNING_BANDS = ((2, 3), (5, 2), (10, 1))      # |quality| up to → learnings
LEARNINGS_PER_RANK = 3                            # reaching skill N costs 3 × N
XP_PER_RANK = 10                                  # gaining skill N grants 10 × N XP
XP_PER_WOUND_SQUARED = 10                         # a defeated enemy: wounds² × 10
ACHIEVEMENT_SHARE = {"small": 0.2, "medium": 0.5, "large": 1.0}


def xp_for_level(level: int) -> int:
    """Total XP that level `level` needs: 100 × level²."""
    return 100 * max(0, int(level)) ** 2


def level_for_xp(xp: int) -> int:
    """The level `xp` total XP reach."""
    level = 0
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def xp_total(character: Dict[str, Any]) -> int:
    xp = character.get("xp", 0)
    return int(xp.get("current", 0) if isinstance(xp, dict) else xp or 0)


def growth_due(character: Dict[str, Any]) -> int:
    """How many levels the character's XP has reached beyond the level applied."""
    return max(0, level_for_xp(xp_total(character)) - int(character.get("level", 0) or 0))


def learnings(quality: int) -> int:
    """What one contest teaches the player's skill: close results teach most."""
    for limit, count in LEARNING_BANDS:
        if abs(int(quality)) <= limit:
            return count
    return 0


def _set_xp(character: Dict[str, Any], total: int) -> None:
    level = int(character.get("level", 0) or 0)
    character["xp"] = {"current": total, "next_level": xp_for_level(level + 1)}


def _log(campaign_dir: Path, lines: List[str]) -> None:
    with (Path(campaign_dir) / LOG_FILE).open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")


def _game_time(campaign_dir: Path) -> str:
    import json
    path = Path(campaign_dir) / "campaign-overview.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8")).get("game_time") or ""
    except (OSError, ValueError):
        stored = ""
    return stored.replace("T", " ") if stored else "no game time"


def add_xp(campaign_dir: Path, character: Dict[str, Any], amount: int, source: str,
           reason: str = "") -> Dict[str, Any]:
    """Book `amount` XP, log it, and report whether growth is now due.
    Returns {"xp", "total", "due", "newly_due"}."""
    before_due = growth_due(character)
    total = xp_total(character) + int(amount)
    _set_xp(character, total)
    due = growth_due(character)
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    head = f"{when} · game {_game_time(campaign_dir)}"
    lines = [head, f"{int(amount):+d} XP  {source}" + (f": {reason}" if reason else ""),
             f"total {total} · level {character.get('level', 0)}"
             + (f" · growth due: {due} level{'s' if due != 1 else ''}" if due else "")]
    _log(campaign_dir, lines)
    return {"xp": int(amount), "total": total, "due": due, "newly_due": due > before_due}


def log_growth(campaign_dir: Path, character: Dict[str, Any], what: str) -> None:
    """Record an applied level-up in the same log."""
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    _log(campaign_dir, [f"{when} · game {_game_time(campaign_dir)}",
                        f"growth applied: level {character.get('level')}: {what}"])


def learn(campaign_dir: Path, character: Dict[str, Any], skill: str,
          quality: int) -> List[Dict[str, Any]]:
    """Practice from one contest: add learnings to `skill`, raise it while they
    reach 3 × N, book 10 × N XP per point gained. Returns the gains as
    [{"skill", "value", "xp"}]; [] when nothing was gained."""
    gained = learnings(quality)
    if not gained or not skill or skill.lower() == "default":
        return []
    skills = character.setdefault("skills", {})
    key = next((k for k in skills if k.lower() == skill.lower()), None)
    if key is None:
        try:
            from stat_block import canon_skills
            key = next((k for k in canon_skills() if k.lower() == skill.lower()), skill)
        except (OSError, ImportError):
            key = skill
    practice = character.setdefault("practice", {})
    pkey = next((k for k in practice if k.lower() == key.lower()), key)
    points = int(practice.pop(pkey, 0)) + gained
    value = int(skills.get(key, 0)) if key in skills else 0
    gains = []
    while points >= LEARNINGS_PER_RANK * (max(value, 0) + 1):
        value = max(value, 0) + 1
        points -= LEARNINGS_PER_RANK * value
        skills[key] = value
        gains.append({"skill": key, "value": value, "xp": XP_PER_RANK * value})
    practice[key] = points
    for gain in gains:
        add_xp(campaign_dir, character, gain["xp"], "skill",
               f"{gain['skill']} rose to {gain['value']} through use")
    return gains


def fight_xp(wounds: int) -> int:
    """XP for defeating an enemy that takes `wounds` wounds: wounds² × 10."""
    return XP_PER_WOUND_SQUARED * max(0, int(wounds)) ** 2


def achievement_xp(character: Dict[str, Any], size: str) -> int:
    """XP for an achievement: a share of the current level's span (the XP from
    this level to the next). Raises ValueError for an unknown size."""
    if size not in ACHIEVEMENT_SHARE:
        raise ValueError(f"Size is one of {', '.join(ACHIEVEMENT_SHARE)}, not {size!r}.")
    level = int(character.get("level", 0) or 0)
    span = xp_for_level(level + 1) - xp_for_level(level)
    return round(span * ACHIEVEMENT_SHARE[size])
