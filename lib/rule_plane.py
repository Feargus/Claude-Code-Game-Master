#!/usr/bin/env python3
"""The plane: two values read together (rules-proposal.md §3.3). Its results belong
to regions of the plane, not to each axis alone: much chrome is fine with a strong
anchor, and cyberpsychosis without one.

    {"name": "Humanity", "block": "plane", "held_by": "player",
     "summary": "...", "when": "Chrome: each piece of cyberware. Anchor: time with the people who matter.",
     "axes": {"Chrome": [0, 10], "Anchor": [0, 10]},
     "start": {"Chrome": 0, "Anchor": 5},
     "rates": {"Anchor": {"by": -1, "every": "14d", "toward": 0}},
     "regions": [
       {"name": "Steady", "where": "Chrome <= Anchor", "text": "..."},
       {"name": "Cyberpsychosis", "where": "Chrome >= Anchor + 4", "text": "...",
        "effects": [...], "when_off": [...], "gm": "..."}]}

- `where`: comparisons joined by "and", each an axis, then <, <=, >, >= or ==, then a
  number or the other axis plus or minus a number ("Law >= 2 and Good <= -2"). Regions
  may overlap; every region a point is in is on.
- A change moves one axis: `gm-rule.sh change "Humanity" --axis Chrome +1`, or the
  effect {"change": "Humanity", "axis": "Chrome", "by": 1}. The regions it enters run
  their effects, those it leaves their when_off; on_rule waits on a region
  ("Humanity:Cyberpsychosis").
- `rates`: an axis can move by itself as game time passes, like a counter's rate.

Stored per holder: {"axes": {"Chrome": 3, "Anchor": 6}, "on": ["Steady"], ...}.
"""

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

FIELDS = ("axes", "start", "rates", "regions")
HOLDS = True
REGION_FIELDS = ("name", "where", "text", "effects", "when_off", "gm")
_COMPARE = re.compile(r"^\s*(?P<left>[^<>=]+?)\s*(?P<op><=|>=|==|<|>)\s*(?P<right>.+?)\s*$")
_RIGHT = re.compile(r"^(?P<axis>.+?)\s*(?P<sign>[+-])\s*(?P<num>\d+)$")
OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
       ">=": lambda a, b: a >= b, "==": lambda a, b: a == b}


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse(where: str, axes) -> list[tuple]:
    """[(axis, op, (other axis or None, number))] for a region's `where`, or ValueError."""
    names = {a.lower(): a for a in axes}
    parts = []
    for piece in re.split(r"\s+and\s+", str(where).strip(), flags=re.IGNORECASE):
        m = _COMPARE.match(piece)
        if not m or m["left"].strip().lower() not in names:
            raise ValueError(f"'{piece}' is no comparison of an axis ({', '.join(axes)})")
        right = m["right"].strip()
        if re.fullmatch(r"-?\d+", right):
            other = (None, int(right))
        elif right.lower() in names:
            other = (names[right.lower()], 0)
        else:
            r = _RIGHT.match(right)
            if not r or r["axis"].strip().lower() not in names:
                raise ValueError(f"'{right}' is neither a number nor an axis plus or minus a number")
            other = (names[r["axis"].strip().lower()],
                     int(r["num"]) * (1 if r["sign"] == "+" else -1))
        parts.append((names[m["left"].strip().lower()], m["op"], other))
    return parts


def inside(region: dict[str, Any], point: dict[str, int], axes) -> bool:
    for axis, op, (other, number) in parse(region["where"], axes):
        right = (point[other] if other else 0) + number
        if not OPS[op](point[axis], right):
            return False
    return True


def regions_on(rule: dict[str, Any], point: dict[str, int]) -> list[str]:
    return [r["name"] for r in rule["regions"] if inside(r, point, rule["axes"])]


def check(rule: dict[str, Any], problems: list[str]) -> None:
    """A plane's own fields, checked and tidied."""
    import rule_effects
    import rule_time
    axes = rule.get("axes")
    if not (isinstance(axes, dict) and len(axes) == 2 and all(
            isinstance(span, list) and len(span) == 2 and all(_is_int(v) for v in span)
            and span[0] < span[1] for span in axes.values())):
        problems.append('\'axes\' are two: {"Chrome": [0, 10], "Anchor": [0, 10]}')
        return
    start = rule.setdefault("start", {a: span[0] for a, span in axes.items()})
    if not isinstance(start, dict) or set(start) != set(axes) or not all(
            _is_int(start[a]) and axes[a][0] <= start[a] <= axes[a][1] for a in axes):
        problems.append(f"'start' gives each axis a value in its range: {', '.join(axes)}")
    rates = rule.get("rates", {})
    if not isinstance(rates, dict) or set(rates) - set(axes):
        problems.append(f"'rates' are per axis: {{\"{next(iter(axes))}\": {{\"by\": 1, \"every\": \"7d\"}}}}")
    else:
        for axis, rate in rates.items():
            problems += [f"axis {axis}: {p}" for p in rule_time.check(rate, *axes[axis])]
    regions = rule.get("regions")
    if not isinstance(regions, list) or not regions:
        problems.append('\'regions\' is a list: [{"name": "Steady", "where": "Chrome <= Anchor", "text": "..."}]')
        return
    names = []
    for region in regions:
        if not isinstance(region, dict) or not str(region.get("name") or "").strip():
            problems.append("every region has a 'name'")
            continue
        name = region["name"] = " ".join(region["name"].split())
        problems += [f"region '{name}' has no '{k}'" for k in region if k not in REGION_FIELDS]
        if name.lower() in names:
            problems.append(f"two regions are called '{name}'")
        names.append(name.lower())
        try:
            parse(region.get("where", ""), axes)
        except ValueError as error:
            problems.append(f"region '{name}': 'where': {error}")
        if not isinstance(region.get("text"), str) or not region["text"].strip():
            problems.append(f"region '{name}' needs a 'text': what it means in the fiction")
        else:
            region["text"] = " ".join(region["text"].split())
        rule_effects.check_shape(region, name, problems)


def find_axis(rule, raw) -> str:
    import world_rules
    for axis in rule["axes"]:
        if axis.lower() == str(raw or "").strip().lower():
            return axis
    raise world_rules.RulesError(f"{rule['name']} is a plane: name the axis to change, "
                                 f"--axis {' or --axis '.join(rule['axes'])}.")


def point(json_ops, rule, holder, state=None) -> dict[str, int]:
    import world_rules
    return dict(world_rules.entry(json_ops, rule, holder, state)["axes"])


def change(json_ops, rule: dict[str, Any], holder: str, axis, by=None, to=None,
           cause: str = "command", chain=None) -> dict[str, Any]:
    """Move one axis by `by`, or set it `to` a value. Like world_rules.change: the
    regions entered run their effects, those left their when_off, then on_rule."""
    import rule_effects
    import world_rules
    axis = find_axis(rule, axis)
    low, high = rule["axes"][axis]
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    here = dict(stored["axes"])
    before = here[axis]
    if to is not None:
        if not low <= to <= high:
            raise world_rules.RulesError(f"{rule['name']}'s {axis} goes from {low} to {high}; "
                                         f"{to} is outside.")
        after = to
    elif by is not None:
        after = max(low, min(high, before + by))
    else:
        raise world_rules.RulesError("Say how much: +N or -N, or set a value.")
    old_on = list(stored.get("on") or regions_on(rule, here))
    here[axis] = after
    new_on = regions_on(rule, here)
    stored.update(axes=here, on=new_on)
    now = world_rules._now_game(json_ops)
    if now:
        stored["since"] = now
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)
    world_rules._log(json_ops, holder, rule["name"], f"{axis} {before} -> {after}", cause)
    report = {"rule": rule["name"], "holder": holder, "axis": axis, "before": before,
              "after": after, "point": here, "stopped": by is not None and before + by != after,
              "on": [r for r in new_on if r not in old_on],
              "off": [r for r in old_on if r not in new_on],
              "still": [r for r in new_on if r in old_on],
              "known": world_rules.is_known(rule, stored), "did": {}, "gm": {}}
    top = chain is None
    chain = rule_effects.new_chain() if top else chain
    chain["seen"].add((rule["name"], holder))
    by_name = {r["name"]: r for r in rule["regions"]}
    for name, field in [(r, "when_off") for r in report["off"]] + [(r, "effects") for r in report["on"]]:
        done = [rule_effects.run(json_ops, effect, holder, chain, f"effect of {rule['name']} {name}")
                for effect in by_name[name].get(field) or []]
        if done:
            report["did"][name] = report["did"].get(name, []) + done
        if field == "effects" and by_name[name].get("gm"):
            report["gm"][name] = by_name[name]["gm"]
    report["fired"] = []
    for name in report["on"]:
        report["fired"] += rule_effects.fire_state(json_ops, rule["name"], holder, name,
                                                   world_rules.holder_name(json_ops, holder))
    if top:
        report["character"] = list(chain["character"])
    return report


def change_lines(json_ops, report: dict[str, Any], indent: str = "") -> list[str]:
    import world_rules
    rule = world_rules.find_rule(json_ops, report["rule"])
    who = world_rules.holder_name(json_ops, report["holder"])
    at = ", ".join(f"{a} {v}" for a, v in report["point"].items())
    mark = "" if report["known"] else f"  {world_rules.HIDDEN}"
    lines = [f"{indent}{rule['name']} ({who}): {report['axis']} {report['before']} → "
             f"{report['after']} (now {at}){mark}"]
    by_name = {r["name"]: r for r in rule["regions"]}
    for kind, names in (("now in", report["on"]), ("now out of", report["off"]),
                        ("still in", report["still"])):
        for name in names:
            lines.append(f"{indent}  {kind + ':':11s} {name}: {by_name[name]['text']}")
            lines += world_rules.done_lines(json_ops, report["did"].get(name, []), indent)
            if kind == "now in" and report["gm"].get(name):
                lines.append(f"{indent}    Do now: {report['gm'][name]}")
    lines += world_rules._fired_lines(report.get("fired"), indent + "  ")
    if report.get("character"):
        lines.append(f"{indent}Changed on the character: {'; '.join(report['character'])}.")
    return lines


def rule_lines(json_ops, rule: dict[str, Any], holders=None) -> list[str]:
    import rule_time
    import world_rules
    hidden = "" if rule.get("known", True) else f"; {world_rules.HIDDEN}"
    axes = " × ".join(f"{a} {lo}–{hi}" for a, (lo, hi) in rule["axes"].items())
    lines = [f"{rule['name']} (plane: {axes}, held by {world_rules._kinds(rule)}{hidden}): "
             f"{rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    for axis, rate in (rule.get("rates") or {}).items():
        lines.append(f"  Rate of {axis}: {rule_time.describe(rate)}, by itself as game time passes.")
    for region in rule["regions"]:
        lines.append(f"  {region['name']} ({region['where']}): {region['text']}")
    holder = "" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"'
    lines.append(f'  Command: gm-rule.sh change "{rule["name"]}"{holder} --axis '
                 f'<{"|".join(rule["axes"])}> +N|-N')
    state = world_rules.load_state(json_ops)
    if holders is None:
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    for holder in holders:
        stored = world_rules.entry(json_ops, rule, holder, state)
        at = ", ".join(f"{a} {v}" for a, v in stored["axes"].items())
        on = ", ".join(stored.get("on") or []) or "no region"
        mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
        lines.append(f"  Now, {world_rules.holder_name(json_ops, holder)}: {at} ({on}){mark}")
    return lines


def holder_line(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    import world_rules
    at = ", ".join(f"{a} {v}" for a, v in stored["axes"].items())
    by_name = {r["name"]: r for r in rule["regions"]}
    on = "; ".join(f"{n}: {by_name[n]['text']}" for n in stored.get("on") or [] if n in by_name)
    mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
    return f"{rule['name']}: {at} (plane): {on or 'no region'}{mark}"


# ---------- the block interface (world_rules.BLOCKS) ----------

def default(rule: dict[str, Any]) -> dict[str, Any]:
    return {"axes": dict(rule["start"]), "on": regions_on(rule, rule["start"])}


def outcomes(rule: dict[str, Any]) -> list[tuple[str, dict]]:
    return [(r.get("name"), r) for r in rule.get("regions") or []]


def summary(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    shown = ", ".join(stored.get("on") or []) or ", ".join(f"{a} {v}" for a, v in stored["axes"].items())
    return f"{rule['name']}: {shown}"


def start(json_ops, rule: dict[str, Any], value) -> dict[str, int]:
    """A starting point: {"Chrome": 3}, axes left out keep their start."""
    import json

    import world_rules
    if not isinstance(value, dict):
        raise world_rules.RulesError(f"{rule['name']} is a plane: give its axes, e.g. "
                                     f"{json.dumps(rule['start'])}.")
    point = {}
    for axis, number in value.items():
        axis = find_axis(rule, axis)
        low, high = rule["axes"][axis]
        if not _is_int(number) or not low <= number <= high:
            raise world_rules.RulesError(f"{rule['name']}'s {axis} goes from {low} to {high}, "
                                         f"not {number!r}.")
        point[axis] = number
    return point


def set_start(json_ops, rule, holder, value, cause) -> list[dict]:
    return [change(json_ops, rule, holder, axis, to=number, cause=cause)
            for axis, number in value.items()]


def on_redefine(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    """Keep a holder's point: each axis moved into its new range."""
    old = stored.get("axes") or {}
    stored["axes"] = {a: max(lo, min(hi, int(old.get(a, rule["start"][a]))))
                      for a, (lo, hi) in rule["axes"].items()}
    stored["on"] = regions_on(rule, stored["axes"])
    return ""


def apply_time(json_ops, rule: dict[str, Any], before, after) -> list[dict]:
    """The axes with a rate move as a counter's value does; each axis counts its own
    periods (`rate_from` per axis)."""
    from datetime import datetime, timedelta

    import rule_time
    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    rates = rule.get("rates") or {}
    reports = []
    for holder in world_rules.holders_of(json_ops, rule) if rates else []:
        for axis, rate in rates.items():
            state = world_rules.load_state(json_ops)
            stored = dict(world_rules.entry(json_ops, rule, holder, state))
            starts = dict(stored.get("rate_from") or {})
            every = timedelta(minutes=parse_duration(rate["every"]))
            begun = datetime.strptime(starts[axis], STORED_FORMAT) if starts.get(axis) else before
            periods = max(0, (after - begun) // every)
            starts[axis] = (begun + periods * every).strftime(STORED_FORMAT)
            stored["rate_from"] = starts
            state.setdefault(holder, {})[rule["name"]] = stored
            world_rules.save_state(json_ops, state)
            low, high = rule["axes"][axis]
            value = stored["axes"][axis]
            new = rule_time.step(value, rate, periods, low, high)
            if new != value:
                reports.append(change(json_ops, rule, holder, axis, to=new,
                                      cause=f"its rate ({rule_time.describe(rate)}), {periods} "
                                            f"period{'s' if periods != 1 else ''}"))
    return reports


report_lines = change_lines
