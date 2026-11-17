#!/usr/bin/env python3
"""Rates: a counter that moves by itself as game time passes (rules-proposal.md §4.2).

    "rate": {"by": 1, "every": "90d"}                      +1 every 90 days
    "rate": {"by": 1, "every": "7d", "toward": 5}           and stops at 5
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
from datetime import datetime, timedelta
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
    """'+1 every 90d (toward 5)' or 'half the way to 0 every 1d'."""
    if "share" in rate:
        share = {0.5: "half", 0.25: "a quarter", 1: "all"}.get(rate["share"], f"{rate['share']:g} of")
        return f"{share} the way to {rate['toward']} every {rate['every']} (at least 1)"
    toward = f" (toward {rate['toward']})" if rate.get("toward") is not None else ""
    return f"{rate['by']:+d} every {rate['every']}{toward}"


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
            if value == toward:
                break                                             # there: it stays
            nxt = value + rate["by"]
            if toward is not None and (value < toward <= nxt or nxt <= toward < value):
                nxt = toward                                      # it stops there
            value = nxt
        value = max(low, min(high, value))
    return value


def rate_of(rule: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any] | None:
    return stored.get("rate") or rule.get("rate")


def apply(json_ops, before: datetime | None, after: datetime) -> list[dict[str, Any]]:
    """Move every rated value by the periods passed. Returns the changes' reports."""
    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    if before is None or after <= before:
        return []
    reports = []
    for rule in world_rules.rules(json_ops):
        if rule["block"] == "states":
            import rule_states
            reports += rule_states.apply_time(json_ops, rule, before, after)
            continue
        if rule["block"] == "plane":
            reports += _apply_plane(json_ops, rule, before, after)
            continue
        if rule["block"] == "bag":
            import rule_bag
            reports += rule_bag.apply_time(json_ops, rule, before, after)
            continue
        if rule["block"] != "counter" or not rule.get("rate"):
            continue
        state = world_rules.load_state(json_ops)
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
        for holder in holders:
            state = world_rules.load_state(json_ops)
            stored = dict(world_rules.entry(json_ops, rule, holder, state))
            rate = rate_of(rule, stored)
            if not rate or rate.get("by") == 0:
                continue
            every = timedelta(minutes=parse_duration(rate["every"]))
            start = (datetime.strptime(stored["rate_from"], STORED_FORMAT)
                     if stored.get("rate_from") else before)
            periods = max(0, (after - start) // every)
            stored["rate_from"] = (start + periods * every).strftime(STORED_FORMAT)
            state.setdefault(holder, {})[rule["name"]] = stored
            world_rules.save_state(json_ops, state)
            low, high = rule["range"]
            value = int(stored.get("value", rule["start"]))
            new = step(value, rate, periods, low, high)
            if new != value:
                reports.append(world_rules.change(
                    json_ops, rule["name"], holder, to=new,
                    cause=f"its rate ({describe(rate)}), {periods} "
                          f"period{'s' if periods != 1 else ''}"))
    return reports


def _apply_plane(json_ops, rule: dict[str, Any], before: datetime, after: datetime) -> list:
    """A plane's axes with a rate move as a counter's value does; each axis counts its
    own periods (`rate_from` per axis)."""
    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    reports = []
    rates = rule.get("rates") or {}
    if not rates:
        return []
    state = world_rules.load_state(json_ops)
    holders = [h for h in ("player", "world") if h in rule["held_by"]]
    holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    for holder in holders:
        for axis, rate in rates.items():
            state = world_rules.load_state(json_ops)
            stored = dict(world_rules.entry(json_ops, rule, holder, state))
            starts = dict(stored.get("rate_from") or {})
            every = timedelta(minutes=parse_duration(rate["every"]))
            start = datetime.strptime(starts[axis], STORED_FORMAT) if starts.get(axis) else before
            periods = max(0, (after - start) // every)
            starts[axis] = (start + periods * every).strftime(STORED_FORMAT)
            stored["rate_from"] = starts
            state.setdefault(holder, {})[rule["name"]] = stored
            world_rules.save_state(json_ops, state)
            low, high = rule["axes"][axis]
            value = stored["axes"][axis]
            new = step(value, rate, periods, low, high)
            if new != value:
                reports.append(world_rules.change(
                    json_ops, rule["name"], holder, to=new, axis=axis,
                    cause=f"its rate ({describe(rate)}), {periods} "
                          f"period{'s' if periods != 1 else ''}"))
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
