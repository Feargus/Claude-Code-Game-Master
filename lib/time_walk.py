#!/usr/bin/env python3
"""The walk through a time step (design-notes.md → "Time stops at the first event").

A time step is not one jump: every source of change says when it next changes, and
the step goes from one such moment to the next, so that each clock, rule and
consequence sees the time at which it happens. The sources:

- time clocks: the moment each reaches its next segment (threat_clocks.py);
- the world's rules: a rate step, a state's `after`, a draw, a refill (each block's
  `next_time`, gathered by rule_time.next_moment);
- the time-of-day words that a waiting consequence is on (`on_time`): the next start
  of their hours (time_manager.next_time_of_day).

`next_moment` is the earliest of them. (Step 1 of the design: the walk itself and
the stops follow.)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def next_moment(world_state_dir, json_ops, after: datetime) -> tuple[datetime, list[str]] | None:
    """The earliest moment after `after` at which something changes by itself, with
    what is due then ("clock Tracker", "rule The Sky", "morning"); None if nothing is
    waiting on time."""
    import rule_time
    from consequence_manager import ConsequenceManager
    from threat_clocks import ThreatClockManager
    from time_manager import next_time_of_day
    due: dict[datetime, list[str]] = {}
    clocks = ThreatClockManager(world_state_dir).next_moment(after)
    if clocks:
        due.setdefault(clocks[0], []).extend(f"clock {name}" for name in clocks[1])
    rules = rule_time.next_moment(json_ops, after)
    if rules:
        due.setdefault(rules[0], []).extend(f"rule {name}" for name in rules[1])
    word = next_time_of_day(after, ConsequenceManager(world_state_dir).waiting_time_words())
    if word:
        due.setdefault(word[0], []).append(word[1].lower())
    if not due:
        return None
    first = min(due)
    return first, due[first]
