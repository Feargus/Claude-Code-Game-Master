#!/usr/bin/env python3
"""The budget: a fixed amount split among named parts, refilled each period
(rules-proposal.md §3.5). A week of downtime, a gang's soldiers:

    {"name": "Downtime", "block": "budget", "held_by": "player",
     "summary": "...", "when": "Between jobs, when the character lies low for a week.",
     "amount": 7, "unit": "days", "period": "by hand",
     "parts": {"healing":  {"text": "One wound heals a step.", "gm": "gm-body.sh heal ..."},
               "work":     {"text": "40 credits.", "effects": [{"credits": 40}]},
               "training": {"text": "A practice of a skill.", "per": 2}}}

- `split`: `gm-rule.sh split Downtime healing=3 work=2 training=2` must use the whole
  amount; parts left out get 0. Each part's effects run once per `per` units (default
  1: work=2 pays twice), its text and gm line are printed with its units.
- After a split the budget is spent until it is refilled: by hand
  (`gm-rule.sh refill`) or, with `"period": {"every": "7d"}`, by itself as game time
  passes.

Stored per holder: {"spent": true, "split": {"healing": 3, ...}, "period_from": ...}.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

FIELDS = ("amount", "unit", "period", "parts")
PART_FIELDS = ("text", "per", "effects", "gm")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check(rule: dict[str, Any], problems: list[str]) -> None:
    import rule_effects
    from time_manager import TimeError, parse_duration
    if not _is_int(rule.get("amount")) or rule["amount"] < 1:
        problems.append("'amount' is how much there is to split, a whole number, 1 or more")
    if not isinstance(rule.setdefault("unit", "units"), str) or not rule["unit"].strip():
        problems.append("'unit' names what is split, e.g. \"days\" or \"soldiers\"")
    period = rule.setdefault("period", "by hand")
    if period != "by hand":
        if not isinstance(period, dict) or set(period) != {"every"}:
            problems.append('\'period\' is "by hand" or {"every": "7d"}')
        else:
            try:
                parse_duration(str(period["every"]))
            except (ValueError, TimeError) as error:
                problems.append(f"'period': {error}")
    parts = rule.get("parts")
    if not isinstance(parts, dict) or not parts:
        problems.append('\'parts\' is {"<part>": {"text": "what each unit buys"}, ...}')
        return
    for name, part in parts.items():
        if not isinstance(part, dict):
            problems.append(f"part '{name}' is {{\"text\": \"...\"}}")
            continue
        problems += [f"part '{name}' has no '{k}'" for k in part if k not in PART_FIELDS]
        if not isinstance(part.get("text"), str) or not part["text"].strip():
            problems.append(f"part '{name}' needs a 'text': what its units buy")
        else:
            part["text"] = " ".join(part["text"].split())
        if not _is_int(part.setdefault("per", 1)) or part["per"] < 1:
            problems.append(f"part '{name}': 'per' is how many units buy it once, 1 or more")
        if "when_off" in part:
            problems.append(f"part '{name}': a part has no when_off")
        rule_effects.check_shape(part, name, problems)


def _rule(json_ops, raw):
    import world_rules
    rule = world_rules.find_rule(json_ops, raw)
    if rule["block"] != "budget":
        raise world_rules.RulesError(f"{rule['name']} is a {rule['block']}, not a budget.")
    return rule


def parse_split(rule, words) -> dict[str, int]:
    """{"healing": 3, ...} from "healing=3" words, checked against the amount."""
    import world_rules
    names = {p.lower(): p for p in rule["parts"]}
    split = dict.fromkeys(rule["parts"], 0)
    for word in words:
        part, sep, number = str(word).partition("=")
        if not sep or not number.strip().isdigit() or part.strip().lower() not in names:
            raise world_rules.RulesError(f"'{word}' is no <part>=N; {rule['name']}'s parts: "
                                         f"{', '.join(rule['parts'])}.")
        split[names[part.strip().lower()]] += int(number)
    total = sum(split.values())
    if total != rule["amount"]:
        raise world_rules.RulesError(f"{rule['name']} splits {rule['amount']} {rule['unit']}; "
                                     f"these add up to {total}. Use all of it.")
    return split


def split(json_ops, raw_rule, raw_holder, words, cause: str = "command") -> dict[str, Any]:
    """Split the budget. Refused while it is spent. Returns {rule, holder, split,
    parts: [{part, units, times, text, did, gm}], known, character}."""
    import rule_effects
    import world_rules
    rule = _rule(json_ops, raw_rule)
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    if stored.get("spent"):
        how = ("gm-rule.sh refill" if rule["period"] == "by hand"
               else f"it refills by itself every {rule['period']['every']}, or gm-rule.sh refill")
        raise world_rules.RulesError(f"{rule['name']} ({world_rules.holder_name(json_ops, holder)}) "
                                     f"is spent for now: {how}.")
    shares = parse_split(rule, words)
    stored.update(spent=True, split=shares)
    now = world_rules._now_game(json_ops)
    if now:
        stored["since"] = now
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)
    world_rules._log(json_ops, holder, rule["name"],
                     "split " + ", ".join(f"{p} {n}" for p, n in shares.items() if n), cause)
    chain = rule_effects.new_chain()
    parts = []
    for name, units in shares.items():
        if not units:
            continue
        part = rule["parts"][name]
        times = units // part["per"]
        done = [rule_effects.run(json_ops, effect, holder, chain, f"effect of {rule['name']} {name}")
                for _ in range(times) for effect in part.get("effects") or []]
        parts.append({"part": name, "units": units, "times": times, "text": part["text"],
                      "did": done, "gm": part.get("gm", "")})
    return {"rule": rule["name"], "holder": holder, "split": shares, "parts": parts,
            "known": world_rules.is_known(rule, stored), "character": list(chain["character"])}


def split_lines(json_ops, report: dict[str, Any]) -> list[str]:
    import world_rules
    rule = world_rules.find_rule(json_ops, report["rule"])
    who = world_rules.holder_name(json_ops, report["holder"])
    mark = "" if report["known"] else f"  {world_rules.HIDDEN}"
    used = ", ".join(f"{p} {n}" for p, n in report["split"].items() if n)
    lines = [f"{rule['name']} ({who}): {rule['amount']} {rule['unit']} split: {used}{mark}"]
    for one in report["parts"]:
        per = rule["parts"][one["part"]]["per"]
        times = f", {one['times']} times" if per > 1 else ""
        lines.append(f"  {one['part']} ({one['units']} {rule['unit']}{times}): {one['text']}")
        lines += world_rules.done_lines(json_ops, one["did"], "")
        if one["gm"]:
            lines.append(f"    Do now: {one['gm']}")
    if report["character"]:
        lines.append(f"Changed on the character: {'; '.join(report['character'])}.")
    return lines


def refill(json_ops, raw_rule, raw_holder=None, cause: str = "command") -> dict[str, Any]:
    import world_rules
    rule = _rule(json_ops, raw_rule)
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    stored["spent"] = False
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)
    world_rules._log(json_ops, holder, rule["name"], "refilled", cause)
    return {"rule": rule["name"], "holder": holder, "refilled": True}


def refill_line(json_ops, report) -> str:
    import world_rules
    rule = world_rules.find_rule(json_ops, report["rule"])
    return (f"{rule['name']} ({world_rules.holder_name(json_ops, report['holder'])}): refilled, "
            f"{rule['amount']} {rule['unit']} to split")


def _now(rule, stored) -> str:
    if not stored.get("spent"):
        return f"{rule['amount']} {rule['unit']} to split"
    last = ", ".join(f"{p} {n}" for p, n in (stored.get("split") or {}).items() if n)
    return f"spent ({last})"


def rule_lines(json_ops, rule: dict[str, Any], holders=None) -> list[str]:
    import world_rules
    hidden = "" if rule.get("known", True) else f"; {world_rules.HIDDEN}"
    period = "refilled by hand" if rule["period"] == "by hand" else \
        f"refilled every {rule['period']['every']}"
    lines = [f"{rule['name']} (budget: {rule['amount']} {rule['unit']}, {period}, held by "
             f"{world_rules._kinds(rule)}{hidden}): {rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    for name, part in rule["parts"].items():
        each = f"each {part['per']} {rule['unit']}" if part["per"] > 1 else f"each of the {rule['unit']}"
        lines.append(f"  {name} ({each}): {part['text']}")
    holder = "" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"'
    example = " ".join(f"{p}=N" for p in rule["parts"])
    lines.append(f'  Command: gm-rule.sh split "{rule["name"]}"{holder} {example} '
                 f'(all {rule["amount"]}); refill "{rule["name"]}"{holder}')
    state = world_rules.load_state(json_ops)
    if holders is None:
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    for holder in holders:
        stored = world_rules.entry(json_ops, rule, holder, state)
        mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
        lines.append(f"  Now, {world_rules.holder_name(json_ops, holder)}: {_now(rule, stored)}{mark}")
    return lines


def holder_line(rule, stored) -> str:
    import world_rules
    mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
    return f"{rule['name']}: {_now(rule, stored)} (budget){mark}"


def summary(rule, stored) -> str:
    return _now(rule, stored)


def apply_time(json_ops, rule: dict[str, Any], before, after) -> list[dict]:
    """A budget with a period refills by itself once a whole period has passed (from
    each holder's `period_from`). Returns the refills' reports."""
    from datetime import datetime, timedelta

    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    if rule["period"] == "by hand":
        return []
    every = timedelta(minutes=parse_duration(rule["period"]["every"]))
    state = world_rules.load_state(json_ops)
    holders = [h for h in ("player", "world") if h in rule["held_by"]]
    holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    reports = []
    for holder in holders:
        state = world_rules.load_state(json_ops)
        stored = dict(world_rules.entry(json_ops, rule, holder, state))
        start = datetime.strptime(stored["period_from"], STORED_FORMAT) if stored.get("period_from") else before
        periods = max(0, (after - start) // every)
        stored["period_from"] = (start + periods * every).strftime(STORED_FORMAT)
        state.setdefault(holder, {})[rule["name"]] = stored
        world_rules.save_state(json_ops, state)
        if periods and stored.get("spent"):
            reports.append(refill(json_ops, rule["name"], holder,
                                  cause=f"time: every {rule['period']['every']}"))
    return reports
