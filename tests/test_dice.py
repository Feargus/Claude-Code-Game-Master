"""Plain dice (lib/dice.py): a notation in, the sum out, nothing else.

The old script read only the start of a notation: "2d6+1d4" rolled 2d6+1, and
anything after a readable start was ignored. It also printed colour codes and
"CRITICAL HIT!" into the GM's context.
"""

import random
import subprocess
import sys
from pathlib import Path

import pytest

from lib.dice import DiceError, roll

DICE = Path(__file__).parent.parent / "lib" / "dice.py"


class Loaded:
    """Every die shows its highest face (or `face`, if it has that many)."""

    def __init__(self, face=None):
        self.face = face

    def randint(self, low, high):
        return high if self.face is None else min(self.face, high)


@pytest.mark.parametrize("notation, expected", [
    ("1d20", 20),
    ("d6", 6),
    ("1d20+5", 25),
    ("1d20-3", 17),
    ("2d6", 12),
    ("2d6+1d4", 16),           # every die is rolled, not only the first kind
    ("2d6+1d4-1", 15),
    ("1d20 + 5", 25),          # spaces
    ("1D20+5", 25),            # case
    ("5+1d6", 11),
    ("1d20-1d4", 16),
])
def test_the_sum_of_every_term(notation, expected):
    assert roll(notation, Loaded()) == expected


def test_each_die_is_rolled_on_its_own():
    assert roll("3d6", Loaded(face=1)) == 3
    rolls = [roll("1d6", random.Random(seed)) for seed in range(200)]
    assert set(rolls) == {1, 2, 3, 4, 5, 6}


@pytest.mark.parametrize("notation", [
    "", "5", "1d20 garbage", "1d20+", "2d6+1x4", "d", "1d", "0d6", "1d1", "1d0",
    "101d6", "1d1001", "1d20++5", "2d20kh1", "1d6.5",
])
def test_what_it_cannot_read_in_full_is_refused(notation):
    with pytest.raises(DiceError):
        roll(notation, Loaded())


def test_the_command_prints_the_sum_and_nothing_else():
    out = subprocess.run([sys.executable, str(DICE), "1d1000+1000"], capture_output=True, text=True)
    assert out.returncode == 0 and out.stderr == ""
    assert out.stdout.strip().isdigit() and 1001 <= int(out.stdout) <= 2000
    assert out.stdout == out.stdout.strip() + "\n"       # one line, no colour codes

    bad = subprocess.run([sys.executable, str(DICE), "2d6+1x4"], capture_output=True, text=True)
    assert bad.returncode == 1 and bad.stdout == "" and "Can't read the dice" in bad.stderr
