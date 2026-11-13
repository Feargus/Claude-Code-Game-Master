#!/usr/bin/env python3
"""Plain dice: roll a notation and print the sum, nothing else.

    dice.py "1d20+5"        a die plus a constant (the usual case)
    dice.py "2d6"           several dice of one size
    dice.py "d6"            one die
    dice.py "2d6+1d4-1"     dice of different sizes and constants, added or subtracted

Skill contests don't use this (skill_contest.py rolls its own dice). It is for the
rolls a campaign's own rules name, and for pure chance (a d6 with the odds set
before the roll). Anything it can't read in full is refused, never half-rolled.
"""

import random
import re
import sys

MAX_DICE = 100      # per term
MAX_SIDES = 1000

# One signed term: dice ("2d6", "d20") or a constant ("5").
_TERM = re.compile(r"([+-])(?:(\d*)d(\d+)|(\d+))")


class DiceError(ValueError):
    """A notation that can't be rolled. The message says what is allowed."""


def roll(notation: str, rng=random) -> int:
    """The sum of a roll of `notation`. `rng` is anything with randint(a, b), so
    tests can load the dice. Raises DiceError for a notation it can't read."""
    text = "".join(str(notation).lower().split())
    bad = DiceError(f"Can't read the dice '{notation}'. Use e.g. 1d20, 1d20+5, 2d6, d6 "
                    f"or 2d6+1d4-1.")
    if not text:
        raise bad
    if text[0] not in "+-":
        text = "+" + text

    total, position, dice_rolled = 0, 0, 0
    for term in _TERM.finditer(text):
        if term.start() != position:      # something between two terms wasn't read
            raise bad
        position = term.end()
        sign = 1 if term.group(1) == "+" else -1
        if term.group(4) is not None:     # a constant
            total += sign * int(term.group(4))
            continue
        count, sides = int(term.group(2) or 1), int(term.group(3))
        if not 1 <= count <= MAX_DICE:
            raise DiceError(f"Roll 1 to {MAX_DICE} dice at a time, not {count}.")
        if not 2 <= sides <= MAX_SIDES:
            raise DiceError(f"A die has 2 to {MAX_SIDES} sides, not {sides}.")
        total += sign * sum(rng.randint(1, sides) for _ in range(count))
        dice_rolled += count
    if position != len(text) or not dice_rolled:
        raise bad
    return total


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: dice.py "<dice>"   e.g. 1d20, 1d20+5, 2d6, d6, 2d6+1d4-1',
              file=sys.stderr)
        return 1
    try:
        print(roll(sys.argv[1]))
    except DiceError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
