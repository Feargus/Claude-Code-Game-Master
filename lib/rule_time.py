#!/usr/bin/env python3
"""Rates: a counter that moves by itself as game time passes (rules-proposal.md §4.2).

    "rate": {"by": 1, "every": "90d"}                      +1 every 90 days
    "rate": {"by": 1, "every": "7d", "toward": 5}           pulled 1 a week toward 5,
                                                            from either side, and stays
                                                            there (a stable point)
    "rate": {"by": -1, "every": "7d", "toward": 5}          pushed 1 a week away from 5,
                                                            to the end of the range; at
                                                            exactly 5 it stays, until
                                                            something moves it (a
                                                            tipping point)

With `toward`, the sign of `by` belongs to the point, not to up or down: + pulls,
- pushes, 0 holds (decided 2026-11-18). So an effect `rate_of` that adds -2 to a
pull of 1 turns it into a push: the crowd has tipped over.
    "rate": {"share": 0.5, "every": "1d", "toward": 0}      half the way to 0 a day,
                                                            at least 1 (8 → 4 → 2 → 1 → 0)

Every time game time moves (time_manager.py: gm-time.sh advance and set, and
gm-session.sh move --takes), `apply` moves each holder's value by the whole periods
that have passed, through world_rules.change, so its results, effects and on_rule
consequences follow as for any change. The time a holder's rate counts from is kept
in rule-state.json (`rate_from`); a change by hand doesn't reset it, so a storm's +1
doesn't delay the next rise. The holders: the player and the world when they hold the
rule, and every other holder that has a value (a faction's or a place's rate starts
with its first value: `gm-rule.sh set`).

A holder's own rate (`gm-rule.sh rate`, or the effect `rate_of`) is kept with its
value and replaces the rule's.
"""

import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

MAX_PERIODS = 100_000


def check(rate: Any, low: int, high: int) -> list[str]:
    """Problems with a rule's `rate`."""
    from time_manager import TimeError, parse_duration
    if not isinstance(rate, dict):
        return ['\'rate\' is {"by": N, "every": "90d"} or {"share": 0.5, "every": "1d", "toward": 0}']
    problems = [f"'rate' has no '{k}'" for k in rate if k not in ("by", "share", "every", "toward")]
    try:
        parse_duration(str(rate.get("every", "")))
    except (ValueError, TimeError) as error:
        problems.append(f"'rate' needs 'every', a time such as \"1d\" or \"90d\": {error}")
    if ("by" in rate) == ("share" in rate):
        problems.append("'rate' has either 'by' (steps) or 'share' (a share of the way)")
    if "by" in rate and (not isinstance(rate["by"], int) or isinstance(rate["by"], bool)):
        problems.append("'rate': 'by' is a whole number, e.g. 1 or -1")
    if "share" in rate:
        if not isinstance(rate["share"], (int, float)) or not 0 < rate["share"] <= 1:
            problems.append("'rate': 'share' is more than 0 and at most 1, e.g. 0.5")
        if "toward" not in rate:
            problems.append("'rate': a share needs 'toward', the value it moves to")
    toward = rate.get("toward")
    if toward is not None and (not isinstance(toward, int) or not low <= toward <= high):
        problems.append(f"'rate': 'toward' is a whole number from {low} to {high}")
    return problems


def describe(rate: dict[str, Any]) -> str:
    """'+1 every 90d', '1 every 7d toward 5', '1 every 7d away from 5' or 'half the
    way to 0 every 1d'."""
    if "share" in rate:
        share = {0.5: "half", 0.25: "a quarter", 1: "all"}.get(rate["share"], f"{rate['share']:g} of")
        return f"{share} the way to {rate['toward']} every {rate['every']} (at least 1)"
    if rate.get("toward") is not None:
        if rate["by"] == 0:
            return f"held at its value (0 every {rate['every']}, toward {rate['toward']})"
        way = "toward" if rate["by"] > 0 else "away from"
        return f"{abs(rate['by'])} every {rate['every']} {way} {rate['toward']}"
    return f"{rate['by']:+d} every {rate['every']}"


def step(value: int, rate: dict[str, Any], periods: int, low: int, high: int) -> int:
    """The value after `periods` periods of `rate`."""
    toward = rate.get("toward")
    for _ in range(min(periods, MAX_PERIODS)):
        if "share" in rate:
            gap = toward - value
            if gap == 0:
                break
            value += int(math.copysign(max(1, math.ceil(abs(gap) * rate["share"])), gap))
        else:
            by = rate["by"]
            if toward is None:
                value += by                                       # a drift, up or down
            elif value == toward or by == 0:
                break                                             # at the point, or held
            elif by > 0:                                          # pulled: a step toward
                value = (min(toward, value + by) if value < toward   # it, stopping there
                         else max(toward, value - by))
            else:                                                 # pushed: a step away
                value = value + by if value < toward else value - by
        value = max(low, min(high, value))
    return value


def rate_of(rule: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any] | None:
    return stored.get("rate") or rule.get("rate")


def apply(json_ops, before: datetime | None, after: datetime) -> list[dict[str, Any]]:
    """Let every rule's block move what time moves: rates, states' `after`, bags'
    `draw_every`, budgets' periods. Returns the reports."""
    import world_rules
    if before is None or after <= before:
        return []
    reports = []
    for rule in world_rules.rules(json_ops):
        reports += world_rules.block(rule).apply_time(json_ops, rule, before, after)
    return reports


def set_rate(json_ops, raw_rule, raw_holder=None, by: int | None = None,
             every: str | None = None, add: int | None = None) -> tuple[dict, dict]:
    """A holder's own rate: `by` steps (or `add` to the steps it has) every `every`.
    Returns (the rate before, after)."""
    import world_rules
    from time_manager import TimeError, parse_duration
    rule = world_rules.counter(json_ops, raw_rule)
    if not rule.get("rate") or "by" not in rule["rate"]:
        raise world_rules.RulesError(f"{rule['name']} has no rate in steps ('by') to change.")
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    old = dict(rate_of(rule, stored))
    new = dict(old)
    if by is not None:
        new["by"] = by
    if add is not None:
        new["by"] = old["by"] + add
    if every is not None:
        try:
            parse_duration(every)
        except (ValueError, TimeError) as error:
            raise world_rules.RulesError(f"--every: {error}") from error
        new["every"] = every
    if new == rule["rate"]:
        stored.pop("rate", None)
    else:
        stored["rate"] = new
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)
    world_rules._log(json_ops, holder, rule["name"], f"rate {describe(old)} -> {describe(new)}",
                     "command" if add is None else "an effect")
    return old, new


# ---------- when next (time_walk.py) ----------

def next_period(start: str | None, every: str, after: datetime) -> datetime:
    """The first moment after `after` at which a period counted from `start` (a
    stored time, e.g. a holder's `rate_from`) ends; from `after` itself when nothing
    is stored yet, as the time steps count."""
    from datetime import timedelta

    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    period = timedelta(minutes=parse_duration(every))
    begun = datetime.strptime(start, STORED_FORMAT) if start else after
    return begun + (max(0, (after - begun) // period) + 1) * period


def moves(rate: dict[str, Any], value: int, low: int, high: int) -> bool:
    """Would one period of `rate` change `value`? (A value held at its point, or at
    the end of the range it drifts to, has nothing more to do.)"""
    return step(value, rate, 1, low, high) != value


def next_moment(json_ops, after: datetime) -> tuple[datetime, list[str]] | None:
    """The earliest moment after `after` at which a world rule changes by itself
    (a rate step, a state's `after`, a draw, a refill), with the rules due then."""
    import world_rules
    due: dict[datetime, list[str]] = {}
    for rule in world_rules.rules(json_ops):
        moment = world_rules.block(rule).next_time(json_ops, rule, after)
        if moment is not None:
            due.setdefault(moment, []).append(rule["name"])
    if not due:
        return None
    first = min(due)
    return first, due[first]
