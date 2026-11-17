#!/usr/bin/env python3
"""
Generic, system-agnostic game core.

NO D&D 5e assumptions live here: no fixed ability names, no level-20 cap, no spell
slots. The core provides only the universal primitives every world runs on:

  - conditions:  add_condition / remove_condition on a list

A world's own rules (Bleed, a sea level, a gang's patience) are world_rules.py:
the building blocks, defined per campaign in its ruleset. dice.py is the only RNG.
Rolls, harm and growth are not here: an action is a skill contest
(skill_contest.py), harm is wounds (body.py), and XP, levels and skills that
improve with use are the same for every campaign (growth.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# ---------------------------------------------------------------- conditions

def add_condition(conditions: list[str], condition: str) -> list[str]:
    """Add a condition (idempotent). Returns a new list."""
    out = list(conditions or [])
    if condition and condition not in out:
        out.append(condition)
    return out


def remove_condition(conditions: list[str], condition: str) -> list[str]:
    """Remove a condition if present. Returns a new list."""
    return [c for c in (conditions or []) if c != condition]
