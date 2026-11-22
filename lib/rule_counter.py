#!/usr/bin/env python3
"""The counter: one number in a range (the gm-rules skill), with its options: a
rate (rule_time.py), hysteresis (a result's `off_at`), overflow (lasting marks) and
streak.

    {"name": "Bleed", "block": "counter", "held_by": "player", "range": [0, 6], "start": 0,
     "summary": "...", "when": "...",
     "results": [{"from": 2, "text": "Intrusions."},
                 {"from": 6, "off_at": 2, "text": "...", "effects": [...], "when_off": [...], "gm": "..."},
                 {"from": 0, "to": 1, "text": "only at 0 and 1"}],
     "rate": {"by": 1, "every": "90d", "toward": 5},
     "overflow": {"at": 8, "back_to": 0, "marks": ["..."], "limit": 3, "at_limit": "..."},
     "streak": true}

A result holds from its `from` upward (cumulative), or only up to its `to`; one with
`off_at`, once on, stays on until the value falls back to it. Stored per holder:
{"value": 4, "on": ["from 2", "from 4"], "since": ..., "rate_from": ..., "marks": [...]}.

Like every block module, it provides what world_rules.py dispatches to: FIELDS, HOLDS,
check, default, outcomes, rule_lines, holder_line, summary, start, set_start,
on_redefine, apply_time, report_lines.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

FIELDS = ("range", "start", "results", "rate", "overflow", "streak")
RESULT_FIELDS = ("from", "to", "off_at", "text", "effects", "when_off", "gm")
HOLDS = True


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ---------- checking ----------

def check(rule: dict, problems: list[str]) -> None:
    _check_range_and_results(rule, problems)
    if not problems:
        _check_options(rule, problems)


def _check_range_and_results(rule: dict, problems: list[str]) -> None:
    span = rule.get("range")
    if not (isinstance(span, list) and len(span) == 2 and all(_is_int(v) for v in span)
            and span[0] < span[1]):
        problems.append("'range' must be [lowest, highest], two whole numbers, e.g. [0, 6]")
        return
    low, high = span
    start = rule.setdefault("start", low)
    if not _is_int(start) or not low <= start <= high:
        problems.append(f"'start' must be a whole number from {low} to {high}")
    results = rule.setdefault("results", [])
    if not isinstance(results, list):
        problems.append('\'results\' must be a list: [{"from": 2, "text": "..."}, ...]')
        return
    labels = []
    for number, result in enumerate(results, 1):
        problem = _check_result(result, number, low, high)
        if problem:
            problems += problem
            continue
        label = result_label(result)
        if label in labels:
            problems.append(f"two results are {label}: make them one")
        labels.append(label)


def _check_result(result, number: int, low: int, high: int) -> list[str]:
    import rule_effects
    import world_rules
    if not isinstance(result, dict):
        return [f'result {number} must be {{"from": N, "text": "..."}}']
    problems = []
    world_rules._unknown(result, RESULT_FIELDS, f" in result {number}", "a result", problems)
    if not _is_int(result.get("from")) or not low <= result["from"] <= high:
        return problems + [f"result {number} needs 'from', a whole number from {low} to {high}"]
    if "to" in result and (not _is_int(result["to"]) or not result["from"] <= result["to"] <= high):
        return problems + [f"result {number}: 'to' must be a whole number from "
                           f"{result['from']} to {high}"]
    if "off_at" in result and ("to" in result or not _is_int(result["off_at"])
                               or not low <= result["off_at"] < result["from"]):
        return problems + [f"result {number}: 'off_at' is where it goes off again, a whole "
                           f"number from {low} to {result['from'] - 1}, and not with 'to'"]
    if not isinstance(result.get("text"), str) or not result["text"].strip():
        return problems + [f"result {number} needs a 'text': what happens in the fiction"]
    result["text"] = " ".join(result["text"].split())
    rule_effects.check_shape(result, number, problems)
    return problems


def _check_options(rule: dict, problems: list[str]) -> None:
    """A counter's rate, overflow and streak."""
    low, high = rule["range"]
    if "rate" in rule:
        import rule_time
        problems += rule_time.check(rule["rate"], low, high)
    ov = rule.get("overflow")
    if ov is not None:
        problems += _check_overflow(ov, low, high)
    if not isinstance(rule.get("streak", False), bool):
        problems.append("'streak' is true or false")


def _check_overflow(ov, low: int, high: int) -> list[str]:
    if not isinstance(ov, dict):
        return ['\'overflow\' is {"at": N, "back_to": M, "marks": [...], "limit": K, "at_limit": "..."}']
    problems = [f"'overflow' has no '{k}'" for k in ov
                if k not in ("at", "back_to", "marks", "limit", "at_limit")]
    if not _is_int(ov.get("at")) or not low < ov["at"] <= high:
        problems.append(f"'overflow': 'at' is a whole number from {low + 1} to {high}")
    elif not _is_int(ov.setdefault("back_to", low)) or not low <= ov["back_to"] < ov["at"]:
        problems.append(f"'overflow': 'back_to' is a whole number from {low} to {ov['at'] - 1}")
    if not isinstance(ov.setdefault("marks", []), list) or \
            not all(isinstance(m, str) and m.strip() for m in ov["marks"]):
        problems.append("'overflow': 'marks' is a list of suggested marks")
    if "limit" in ov and (not _is_int(ov["limit"]) or ov["limit"] < 1
                          or not isinstance(ov.get("at_limit"), str) or not ov["at_limit"].strip()):
        problems.append("'overflow': 'limit' is a number of marks (1 or more), with "
                        "'at_limit', what happens then")
    return problems


# ---------- results ----------

def result_label(result: dict[str, Any]) -> str:
    """'from 2', 'from 2 to 3' or 'at 0': how a result is named in the output and stored in `on`."""
    if result.get("to") == result["from"]:
        return f"at {result['from']}"
    if "to" in result:
        return f"from {result['from']} to {result['to']}"
    return f"from {result['from']}"


def results_on(rule: dict[str, Any], value: int, before=()) -> list[str]:
    """The labels of the results that hold at `value`: each from its `from` upward
    (cumulative), or only up to its `to`. One with `off_at` (hysteresis), once on (in
    `before`), stays on until the value falls to its `off_at`."""
    on = []
    for r in rule.get("results") or []:
        label = result_label(r)
        in_range = r["from"] <= value <= r.get("to", value)
        held_on = "off_at" in r and label in before and value > r["off_at"]   # hysteresis
        if in_range or held_on:
            on.append(label)
    return on


def outcomes(rule: dict[str, Any]) -> list[tuple[str, dict]]:
    return [(result_label(r), r) for r in rule.get("results") or []]


def _result(rule, name) -> dict[str, Any]:
    return next(r for r in rule.get("results") or [] if result_label(r) == name)


def default(rule: dict[str, Any]) -> dict[str, Any]:
    return {"value": rule["start"], "on": results_on(rule, rule["start"])}


# ---------- changing ----------

def change(json_ops, rule: dict[str, Any], holder: str, by=None, to=None,
           cause: str = "command", chain=None) -> dict[str, Any]:
    """Change the counter by `by`, or set it `to` a value. A change that goes past the
    range stops at its end; a set outside it is refused; reaching an overflow's `at`
    goes back to `back_to` with a mark due. The results it turns on and off carry out
    their effects (rule_effects.py; `chain` is the chain this change is part of), then
    the on_rule consequences fire. Returns {rule, holder, before, after, stopped,
    overflow, on, off, still, known, did, gm, fired, character}."""
    import rule_effects
    import world_rules
    low, high = rule["range"]
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    before = int(stored.get("value", rule["start"]))
    if to is not None:
        if not low <= to <= high:
            raise world_rules.RulesError(f"{rule['name']} goes from {low} to {high}; {to} is outside.")
        after = to
    elif by is not None:
        after = max(low, min(high, before + by))
    else:
        raise world_rules.RulesError("Say how much: +N or -N, or set a value.")
    stopped = by is not None and before + by != after
    ov, overflow, reached = rule.get("overflow"), None, after
    if ov and before < ov["at"] <= after:                 # a lasting mark, and back down
        reached, after = ov["at"], ov["back_to"]
        stored["marks_due"] = int(stored.get("marks_due", 0)) + 1
        overflow = {"at": ov["at"], "back_to": after, "suggested": ov.get("marks") or [],
                    "marks": list(stored.get("marks") or []), "due": stored["marks_due"]}
    old_on = list(stored.get("on") or results_on(rule, before))
    new_on = results_on(rule, after, old_on)
    stored.update(value=after, on=new_on)
    now = world_rules._now_game(json_ops)
    if now:
        stored["since"] = now
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)
    path = f"{before} -> {reached} -> {after} (overflow)" if overflow else f"{before} -> {after}"
    world_rules._log(json_ops, holder, rule["name"], path, cause)
    report = {"rule": rule["name"], "holder": holder, "before": before, "after": after,
              "stopped": stopped and not overflow, "overflow": overflow,
              "on": [r for r in new_on if r not in old_on],
              "off": [r for r in old_on if r not in new_on],
              "still": [r for r in new_on if r in old_on],
              "known": world_rules.is_known(rule, stored), "did": {}, "gm": {}}
    top = chain is None
    chain = rule_effects.new_chain() if top else chain
    chain["seen"].add((rule["name"], holder))
    for label, field in [(r, "when_off") for r in report["off"]] + [(r, "effects") for r in report["on"]]:
        result = _result(rule, label)
        done = [rule_effects.run(json_ops, effect, holder, chain, f"effect of {rule['name']} {label}")
                for effect in result.get(field) or []]
        if done:
            report["did"][label] = done
        if field == "effects" and result.get("gm"):
            report["gm"][label] = result["gm"]
    report["fired"] = rule_effects.fire_on_rule(json_ops, rule["name"], holder, before, reached,
                                                world_rules.holder_name(json_ops, holder))
    if top:
        report["character"] = list(chain["character"])
    return report


def mark(json_ops, rule: dict[str, Any], holder: str, text: str) -> dict[str, Any]:
    """Record the lasting mark an overflow left. Returns {rule, holder, mark, marks,
    at_limit (what happens now, when the marks reach the limit, else '')}."""
    import world_rules
    ov = rule.get("overflow")
    if not ov:
        raise world_rules.RulesError(f"{rule['name']} has no overflow, so it leaves no marks.")
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    if int(stored.get("marks_due", 0)) < 1:
        raise world_rules.RulesError(f"No mark is due: {rule['name']} leaves one each time it "
                                     f"reaches {ov['at']}.")
    text = " ".join(str(text or "").split())
    if not text:
        raise world_rules.RulesError("Say what the mark is, e.g. \"night terrors\".")
    stored["marks"] = list(stored.get("marks") or []) + [text]
    stored["marks_due"] = int(stored["marks_due"]) - 1
    if not stored["marks_due"]:
        del stored["marks_due"]
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)
    world_rules._log(json_ops, holder, rule["name"], f"mark: {text}", "command")
    at_limit = ov.get("at_limit", "") if ov.get("limit") and len(stored["marks"]) >= ov["limit"] else ""
    return {"rule": rule["name"], "holder": holder, "mark": text, "marks": stored["marks"],
            "at_limit": at_limit}


# ---------- showing ----------

def change_lines(json_ops, report: dict[str, Any], indent: str = "") -> list[str]:
    """A change as the GM reads it: the values, then the results it turned on and off,
    each followed by what its effects did, its line for the GM, the consequences it
    fired, and at the end of a chain what changed on the character."""
    import world_rules
    rule = world_rules.find_rule(json_ops, report["rule"])
    who = world_rules.holder_name(json_ops, report["holder"])
    top = ""
    if report["stopped"]:
        top = " (its highest)" if report["after"] == rule["range"][1] else " (its lowest)"
    ov = report.get("overflow")
    path = f"{report['before']} → {ov['at']} → {report['after']}" if ov else \
        f"{report['before']} → {report['after']}"
    lines = [f"{indent}{rule['name']} ({who}): {path}{top}"
             + ("" if report["known"] else f"  {world_rules.HIDDEN}")]
    if ov:
        offer = f" Suggested: {'; '.join(ov['suggested'])}; or write one." if ov["suggested"] else ""
        lines.append(f"{indent}  overflow at {ov['at']}, back to {ov['back_to']}: a lasting mark "
                     f"is due.{offer} Then: gm-rule.sh mark \"{rule['name']}\""
                     + ("" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"')
                     + ' "<the mark>"')
    for kind, labels in (("now on", report["on"]), ("now off", report["off"]),
                         ("still on", report["still"])):
        for name in labels:
            lines.append(f"{indent}  {kind + ':':9s} {name}: {_result(rule, name)['text']}")
            lines += world_rules.done_lines(json_ops, (report.get("did") or {}).get(name, []), indent)
            if kind == "now on" and (report.get("gm") or {}).get(name):
                lines.append(f"{indent}    Do now: {report['gm'][name]}")
    lines += world_rules._fired_lines(report.get("fired"), indent + "  ")
    if report.get("character"):
        lines.append(f"{indent}Changed on the character: {'; '.join(report['character'])}.")
    return lines


report_lines = change_lines


def rule_lines(json_ops, rule: dict[str, Any], holders=None) -> list[str]:
    """The counter in full, with where it stands for `holders`."""
    import world_rules
    low, high = rule["range"]
    hidden = "" if rule.get("known", True) else f"; {world_rules.HIDDEN}"
    lines = [f"{rule['name']} (counter {low}–{high}, held by {world_rules._kinds(rule)}{hidden}): "
             f"{rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    lines += _option_lines(rule)
    for result in rule.get("results") or []:
        off = f" (off only at {result['off_at']})" if "off_at" in result else ""
        lines.append(f"  {result_label(result)}{off}: {result['text']}")
    holder = "" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"'
    lines.append(f'  Command: gm-rule.sh change "{rule["name"]}"{holder} +N|-N')
    state = world_rules.load_state(json_ops)
    for holder in world_rules.holders_of(json_ops, rule, state) if holders is None else holders:
        stored = world_rules.entry(json_ops, rule, holder, state)
        on = ", ".join(stored.get("on") or []) or "no result"
        mark_ = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
        lines.append(f"  Now, {world_rules.holder_name(json_ops, holder)}: {stored.get('value')} "
                     f"({on}){_extras(stored, rule)}{mark_}")
    return lines


def _option_lines(rule: dict[str, Any]) -> list[str]:
    """A counter's rate, overflow and streak, in words."""
    lines = []
    if rule.get("rate"):
        import rule_time
        lines.append(f"  Rate: {rule_time.describe(rule['rate'], rule['name'])}, by itself as game "
                     f"time passes.")
    ov = rule.get("overflow")
    if ov:
        marks = f" (e.g. {'; '.join(ov['marks'])})" if ov.get("marks") else ""
        limit = f" At {ov['limit']} marks: {ov['at_limit']}" if ov.get("limit") else ""
        lines.append(f"  Overflow at {ov['at']}: back to {ov['back_to']}, and a lasting mark"
                     f"{marks}.{limit}")
    if rule.get("streak"):
        lines.append(f"  Streak: a failure breaks it (gm-rule.sh break \"{rule['name']}\").")
    return lines


def _extras(stored: dict[str, Any], rule: dict[str, Any]) -> str:
    """A holder's marks, marks due and own rate, after its value."""
    parts = []
    if stored.get("marks"):
        parts.append(f"marks: {'; '.join(stored['marks'])}")
    if stored.get("marks_due"):
        parts.append(f"{stored['marks_due']} mark due")
    if stored.get("rate"):
        import rule_time
        parts.append(f"its own rate: {rule_time.describe(stored['rate'], rule['name'])}")
    return f"; {', '.join(parts)}" if parts else ""


def holder_line(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    """The counter on a person's or a place's card, with the results on now in full."""
    import world_rules
    low, high = rule["range"]
    on = [f"{label}: {_result(rule, label)['text']}" for label in stored.get("on") or []]
    mark_ = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
    return (f"{rule['name']} {stored.get('value')} (counter {low}–{high}): "
            + ("; ".join(on) or "no result") + _extras(stored, rule) + mark_)


def summary(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    return f"{rule['name']} {stored.get('value')}/{rule['range'][1]}"


# ---------- starting values, redefinition, time ----------

def start(json_ops, rule: dict[str, Any], value) -> int:
    import world_rules
    low, high = rule["range"]
    if not _is_int(value) or not low <= value <= high:
        raise world_rules.RulesError(f"{rule['name']} goes from {low} to {high}; {value!r} is "
                                     f"not a whole number in it.")
    return value


def set_start(json_ops, rule: dict[str, Any], holder: str, value, cause: str) -> list[dict]:
    return [change(json_ops, rule, holder, to=value, cause=cause)]


def on_redefine(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    """Keep a holder's value under a redefined rule: moved into its new range."""
    low, high = rule["range"]
    stored["value"] = max(low, min(high, int(stored.get("value", rule["start"]))))
    stored["on"] = results_on(rule, stored["value"], stored.get("on") or ())
    return ""


def apply_time(json_ops, rule: dict[str, Any], before, after) -> list[dict]:
    """A rate moves each holder's value by the whole periods passed (rule_time.py)."""
    from datetime import datetime, timedelta

    import rule_time
    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    if not rule.get("rate"):
        return []
    reports = []
    for holder in world_rules.holders_of(json_ops, rule):
        state = world_rules.load_state(json_ops)
        stored = dict(world_rules.entry(json_ops, rule, holder, state))
        rate = rule_time.rate_of(rule, stored)
        if not rate or rate.get("by") == 0:
            continue
        every = timedelta(minutes=parse_duration(rate["every"]))
        begun = datetime.strptime(stored["rate_from"], STORED_FORMAT) if stored.get("rate_from") else before
        periods = max(0, (after - begun) // every)
        stored["rate_from"] = (begun + periods * every).strftime(STORED_FORMAT)
        state.setdefault(holder, {})[rule["name"]] = stored
        world_rules.save_state(json_ops, state)
        low, high = rule["range"]
        value = int(stored.get("value", rule["start"]))
        new = rule_time.step(value, rate, periods, low, high)
        if new != value:
            reports.append(change(json_ops, rule, holder, to=new,
                                  cause=f"its rate ({rule_time.describe(rate)}), {periods} "
                                        f"period{'s' if periods != 1 else ''}"))
    return reports


def next_time(json_ops, rule: dict[str, Any], after):
    """When a rate next moves a holder's value (None: no rate, or nothing to move)."""
    import rule_time
    import world_rules
    if not rule.get("rate"):
        return None
    times = []
    for holder in world_rules.holders_of(json_ops, rule):
        stored = world_rules.entry(json_ops, rule, holder)
        rate = rule_time.rate_of(rule, stored)
        value = int(stored.get("value", rule["start"]))
        if rate and rate.get("by") != 0 and rule_time.moves(rate, value, *rule["range"]):
            times.append(rule_time.next_period(stored.get("rate_from"), rate["every"], after))
    return min(times, default=None)
