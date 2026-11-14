#!/usr/bin/env python3
"""
Generic, system-agnostic game core.

NO D&D 5e assumptions live here: no fixed ability names, no level-20 cap, no spell
slots. The core provides only the universal primitives every world runs on:

  - conditions:  add_condition / remove_condition on a list
  - the signature-system calculators a World Kit names per world

Signature systems are BESPOKE PER WORLD (a World Kit configures them). dice.py is
the only RNG. Rolls, harm and growth are not here: an action is a skill contest
(skill_contest.py), harm is wounds (body.py), and XP, levels and skills that
improve with use are the same for every campaign (growth.py).
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import random

from dice import roll

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


# ------------------------------------------- signature-system primitives
#
# Four world-agnostic building blocks a World Kit instantiates and NAMES per
# world — a corruption meter, a Warp price, a morale reaction, a cursed-hoard
# payoff. Each is a PURE CALCULATOR: it reads no files
# and writes none, takes all its content (names, thresholds, dice) as arguments,
# and returns a plain dict for the caller to persist. Nothing here is book-
# specific; the kit supplies the flavor. Rolls are seedable via `rng` (any object
# with `randint(a, b)`, e.g. random.Random(seed)) so tests are deterministic;
# without one they reuse the module dice roller.


def _roll_total(notation: str, rng: Any = None) -> int:
    """Total of a roll (dice.py). `rng` (e.g. random.Random) makes it
    deterministic; without one, the global RNG.

    Config dice here are bare 'NdM' (1d20, 2d6); the modifier travels separately.
    """
    return roll(notation, rng if rng is not None else random)


def _rung_for(rungs: list[dict[str, Any]], value: int, key: str) -> dict[str, Any] | None:
    """Pick the rung with the greatest `key` still ≤ value; below all, the lowest."""
    ordered = sorted(rungs or [], key=lambda r: r[key])
    chosen = ordered[0] if ordered else None
    for r in ordered:
        if value >= r[key]:
            chosen = r
        else:
            break
    return chosen


def named_track(current: int, delta: int, config: dict[str, Any]) -> dict[str, Any]:
    """A meter with threshold consequences (corruption, doom, heat, ...).

    config = {"max": int, "thresholds": [{"at": int, "consequence": str}, ...]}.
    Applies delta, clamping the result to [0, max]. Deterministic (no roll).

    Returns {"before", "after", "max", "crossed", "at_max"} where `crossed` is the
    threshold dicts this delta newly passed through in EITHER direction (before <
    at ≤ after climbing, or after < at ≤ before falling), sorted by `at`.
    """
    max_v = int(config.get('max', 0))
    before = int(current)
    after = max(0, min(max_v, before + int(delta)))
    lo, hi = min(before, after), max(before, after)
    crossed = [t for t in (config.get('thresholds') or [])
               if lo < int(t['at']) <= hi]
    crossed.sort(key=lambda t: int(t['at']))
    return {'before': before, 'after': after, 'max': max_v,
            'crossed': crossed, 'at_max': after >= max_v}


def price_roll(severity: int, config: dict[str, Any], rng: Any = None) -> dict[str, Any]:
    """The cost a marked action exacts from the actor (a Warp roll, a debt, a scar).

    config = {"ladder": [{"min_roll": int, "cost": str}, ...], "dice": "1d20",
    "modifier": int}. Rolls dice + modifier − severity (higher severity => a lower
    total => a WORSE rung), then reads the ladder rung whose `min_roll` the total
    reaches (below the cheapest rung, it lands on the worst one).

    Returns {"roll", "total", "severity", "cost", "rung"} (rung is the chosen dict).
    """
    roll = _roll_total(config.get('dice', '1d20'), rng)
    total = roll + int(config.get('modifier', 0)) - int(severity)
    rung = _rung_for(config.get('ladder') or [], total, 'min_roll')
    return {'roll': roll, 'total': total, 'severity': int(severity),
            'cost': (rung or {}).get('cost'), 'rung': rung}


def reaction_roll(track_value: int, config: dict[str, Any], rng: Any = None) -> dict[str, Any]:
    """An NPC's opening disposition, shifted by a track/reputation value.

    config = {"dice": "2d6", "tiers": [{"min": int, "reaction": str}, ...],
    "modifier": int}. Rolls dice + modifier + track_value and maps the total to the
    tier whose `min` it reaches (below the lowest tier, it lands on the worst one).

    Returns {"roll", "total", "track_value", "reaction", "tier"} (tier is the dict).
    """
    roll = _roll_total(config.get('dice', '2d6'), rng)
    total = roll + int(config.get('modifier', 0)) + int(track_value)
    tier = _rung_for(config.get('tiers') or [], total, 'min')
    return {'roll': roll, 'total': total, 'track_value': int(track_value),
            'reaction': (tier or {}).get('reaction'), 'tier': tier}


def guarded_payoff(config: dict[str, Any], rng: Any = None) -> dict[str, Any]:
    """Rolled BEFORE a marked treasure is taken — does the hoard bite back?

    config = {"dice": "1d20", "clean_at": int, "guardian_at": int} with
    clean_at > guardian_at. High roll walks away clean; a middling roll wakes the
    guardian; a low roll attaches the curse.

    Returns {"roll", "outcome"} where outcome is
    "clean" | "guardian_wakes" | "curse_attaches".
    """
    roll = _roll_total(config.get('dice', '1d20'), rng)
    if roll >= int(config.get('clean_at', 0)):
        outcome = 'clean'
    elif roll >= int(config.get('guardian_at', 0)):
        outcome = 'guardian_wakes'
    else:
        outcome = 'curse_attaches'
    return {'roll': roll, 'outcome': outcome}


# ------------------------------------------------------------ self-check
#
# `uv run python lib/game_core.py` exercises the signature-system primitives at
# their edges and fails loudly (AssertionError) if a contract breaks. `_Fixed`
# is a loaded die (its face clamps into range) so best/worst rolls are exact
# without depending on a seed's luck; random.Random proves seedable determinism.

class _Fixed:
    """A loaded die: rng.randint(a, b) always returns `face`, clamped to [a, b]."""

    def __init__(self, face: int):
        self.face = face

    def randint(self, a: int, b: int) -> int:
        return min(max(self.face, a), b)


def _demo() -> None:
    # named_track — empty track: no movement, nothing crossed.
    cfg_t = {'max': 100, 'thresholds': [{'at': 50, 'consequence': 'corrupted'},
                                        {'at': 100, 'consequence': 'lost'}]}
    empty = named_track(0, 0, cfg_t)
    assert empty == {'before': 0, 'after': 0, 'max': 100, 'crossed': [], 'at_max': False}, empty

    # delta past max clamps and reports at_max, crossing both thresholds upward.
    up = named_track(40, 90, cfg_t)
    assert up['after'] == 100 and up['at_max'] is True, up
    assert [t['at'] for t in up['crossed']] == [50, 100], up

    # downward delta crosses on the way back down; clamps at 0.
    down = named_track(60, -80, cfg_t)
    assert down['after'] == 0 and down['at_max'] is False, down
    assert [t['at'] for t in down['crossed']] == [50], down

    # price_roll — worst and best rung, deterministic via loaded die.
    cfg_p = {'dice': '1d20', 'modifier': 0,
             'ladder': [{'min_roll': 0, 'cost': 'a piece of your soul'},
                        {'min_roll': 10, 'cost': 'a lasting scar'},
                        {'min_roll': 18, 'cost': 'nothing but a nosebleed'}]}
    worst = price_roll(severity=5, config=cfg_p, rng=_Fixed(1))   # 1 - 5 = -4 -> bottom rung
    assert worst['cost'] == 'a piece of your soul' and worst['total'] == -4, worst
    best = price_roll(severity=0, config=cfg_p, rng=_Fixed(20))   # 20 -> top rung
    assert best['cost'] == 'nothing but a nosebleed' and best['rung']['min_roll'] == 18, best

    # reaction_roll — both extremes (hostile floor, allied ceiling).
    cfg_r = {'dice': '2d6', 'modifier': 0,
             'tiers': [{'min': -99, 'reaction': 'hostile'},
                       {'min': 7, 'reaction': 'neutral'},
                       {'min': 12, 'reaction': 'helpful'}]}
    hostile = reaction_roll(track_value=-10, config=cfg_r, rng=_Fixed(1))   # 2 - 10 = -8
    assert hostile['reaction'] == 'hostile', hostile
    helpful = reaction_roll(track_value=5, config=cfg_r, rng=_Fixed(6))     # 12 + 5 = 17
    assert helpful['reaction'] == 'helpful' and helpful['total'] == 17, helpful

    # guarded_payoff — each of the three outcomes.
    cfg_g = {'dice': '1d20', 'clean_at': 15, 'guardian_at': 8}
    assert guarded_payoff(cfg_g, rng=_Fixed(20))['outcome'] == 'clean'
    assert guarded_payoff(cfg_g, rng=_Fixed(10))['outcome'] == 'guardian_wakes'
    assert guarded_payoff(cfg_g, rng=_Fixed(1))['outcome'] == 'curse_attaches'

    # seedable determinism: the same seed reproduces the same roll.
    import random
    a = price_roll(2, cfg_p, rng=random.Random(1234))
    b = price_roll(2, cfg_p, rng=random.Random(1234))
    assert a == b, (a, b)

    print('[game_core] signature-system primitives self-check OK')


if __name__ == '__main__':
    _demo()
