#!/usr/bin/env python3
"""The roll: a world rule that keeps nothing (rules-proposal.md §3.1).

Dice, plus or minus named amounts, and optionally a holder's value of another rule,
read once from a list of results. A price for power, a first reaction, a guarded
treasure:

    {"name": "The Lease", "block": "roll", "held_by": "player",
     "summary": "...", "when": "...",
     "dice": "1d20",
     "with": {"ordinary night": 0, "deep lease": -2, "Mesh run": -4},
     "add": "Respect",
     "results": [{"from": 15, "text": "Clean."},
                 {"from": 10, "text": "+1 Bleed.", "effects": [{"change": "Bleed", "by": 1}]},
                 {"text": "+2 Bleed, and a memory is gone.", "gm": "Record which, as a fact."}]}

- `with`: named amounts, chosen at each roll (`--with "deep lease"`, repeatable).
- `add`: the holder's value of a counter, added to the total (a reaction shifted by
  Respect).
- `results`: the highest `from` the total reaches applies; one result without `from`
  catches everything below (without one, the lowest result does). A result's effects
  run every time it is rolled (rule_effects.py); its `gm` line is printed.

`held_by` is whose rules the effects change and whose `add` value counts; nothing is
stored but the line in rules.log.
"""

import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

FIELDS = ("dice", "with", "add", "results")
RESULT_FIELDS = ("from", "text", "effects", "gm")


class _Lowest:
    """A die that always rolls 1: to check that a notation can be rolled."""

    @staticmethod
    def randint(a, b):
        return a


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def label(result: dict[str, Any], results: list[dict[str, Any]]) -> str:
    """'15+', or for the result without `from`, 'below 5' (the lowest `from`)."""
    if "from" in result:
        return f"{result['from']}+"
    lowest = [r["from"] for r in results if "from" in r]
    return f"below {min(lowest)}" if lowest else "any"


def check(rule: dict[str, Any], problems: list[str]) -> None:
    """A roll's own fields, checked and tidied (the shared ones are checked by
    world_rules.check_rule)."""
    from dice import DiceError, roll
    try:
        roll(str(rule.get("dice") or ""), _Lowest())
    except DiceError as error:
        problems.append(f"'dice' must be dice to roll, e.g. \"1d20\" or \"2d6\": {error}")
    named = rule.setdefault("with", {})
    if not isinstance(named, dict) or not all(isinstance(k, str) and k.strip() and _is_int(v)
                                              for k, v in named.items()):
        problems.append('\'with\' must be named amounts: {"deep lease": -2, ...}')
    if "add" in rule and (not isinstance(rule["add"], str) or not rule["add"].strip()):
        problems.append("'add' names a counter whose value is added")
    _check_results(rule.get("results"), problems)


def _check_results(results, problems: list[str]) -> None:
    if not isinstance(results, list) or not results:
        problems.append('\'results\' must be a list: [{"from": 15, "text": "..."}, ..., '
                        '{"text": "below all"}]')
        return
    import rule_effects
    seen, catch_all = [], 0
    for number, result in enumerate(results, 1):
        if not isinstance(result, dict):
            problems.append(f'result {number} must be {{"from": N, "text": "..."}}')
            continue
        for field in result:
            if field not in RESULT_FIELDS:
                why = "a roll's result happens once" if field in ("to", "when_off") else \
                    f"a roll's result has {', '.join(RESULT_FIELDS)}"
                problems.append(f"result {number}: no '{field}' ({why})")
        if "from" not in result:
            catch_all += 1
        elif not _is_int(result["from"]):
            problems.append(f"result {number}: 'from' must be a whole number")
        elif result["from"] in seen:
            problems.append(f"two results are from {result['from']}: make them one")
        else:
            seen.append(result["from"])
        if not isinstance(result.get("text"), str) or not result["text"].strip():
            problems.append(f"result {number} needs a 'text': what happens in the fiction")
            continue
        result["text"] = " ".join(result["text"].split())
        rule_effects.check_shape(result, number, problems)
    if catch_all > 1:
        problems.append("only one result can be without 'from' (it catches everything below)")


def pick(rule: dict[str, Any], total: int) -> dict[str, Any]:
    """The result a total lands on."""
    results = rule["results"]
    ranked = sorted((r for r in results if "from" in r), key=lambda r: r["from"], reverse=True)
    for result in ranked:
        if total >= result["from"]:
            return result
    below = [r for r in results if "from" not in r]
    return below[0] if below else ranked[-1]


def roll(json_ops, raw_rule, raw_holder=None, named=(), rng=None) -> dict[str, Any]:
    """Roll a roll rule. Returns {rule, holder, dice, rolled, with: [[name, amount]],
    add: [rule, value] or None, total, result (its label), text, did, gm, fired,
    character}."""
    import rule_effects
    import world_rules
    from dice import roll as roll_dice
    rule = world_rules.find_rule(json_ops, raw_rule)
    if rule["block"] != "roll":
        raise world_rules.RulesError(f"{rule['name']} is a {rule['block']}, not a roll: "
                                     f"gm-rule.sh change \"{rule['name']}\" ...")
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    chosen = []
    by_low = {k.lower(): (k, v) for k, v in rule["with"].items()}
    for raw in named:
        key = " ".join(str(raw).split()).lower()
        if key not in by_low:
            options = ", ".join(f'"{k}"' for k in rule["with"]) or "none"
            raise world_rules.RulesError(f"{rule['name']} has no amount '{raw}'; its amounts: "
                                         f"{options}.")
        chosen.append(list(by_low[key]))
    rolled = roll_dice(rule["dice"], rng if rng is not None else random)
    total = rolled + sum(amount for _, amount in chosen)
    added = None
    if rule.get("add"):
        other = world_rules.find_rule(json_ops, rule["add"])
        value = int(world_rules.entry(json_ops, other, holder).get("value", other["start"]))
        added = [other["name"], value]
        total += value
    result = pick(rule, total)
    where = label(result, rule["results"])
    parts = [f"{rule['dice']} {rolled}"] + [f"{n} {a:+d}" for n, a in chosen]
    if added:
        parts.append(f"{added[0]} {added[1]:+d}")
    world_rules._log(json_ops, holder, rule["name"], f"rolled {', '.join(parts)} = {total}: "
                     f"{where}", "command")
    chain = rule_effects.new_chain()
    done = [rule_effects.run(json_ops, effect, holder, chain, f"effect of {rule['name']} {where}")
            for effect in result.get("effects") or []]
    return {"rule": rule["name"], "holder": holder, "dice": rule["dice"], "rolled": rolled,
            "with": chosen, "add": added, "total": total, "result": where,
            "text": result["text"], "did": done, "gm": result.get("gm", ""),
            "character": list(chain["character"])}


def roll_lines(json_ops, report: dict[str, Any]) -> list[str]:
    """A roll as the GM reads it: the dice, what was added, the result and what its
    effects did."""
    import world_rules
    who = world_rules.holder_name(json_ops, report["holder"])
    parts = [f"{report['dice']} {report['rolled']}"]
    parts += [f"{name} {amount:+d}" for name, amount in report["with"]]
    if report["add"]:
        parts.append(f"{report['add'][0]} {report['add'][1]:+d}")
    lines = [f"{report['rule']} ({who}): {', '.join(parts)} → {report['total']}",
             f"  {report['result']}: {report['text']}"]
    lines += world_rules.done_lines(json_ops, report["did"], "")
    if report["gm"]:
        lines.append(f"    Do now: {report['gm']}")
    if report["character"]:
        lines.append(f"Changed on the character: {'; '.join(report['character'])}.")
    return lines


def rule_lines(rule: dict[str, Any]) -> list[str]:
    """A roll in full, for the brief and `show`."""
    import world_rules
    lines = [f"{rule['name']} (roll {rule['dice']}, held by {world_rules._kinds(rule)}): "
             f"{rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    if rule["with"]:
        lines.append("  With: " + ", ".join(f"{k} {v:+d}" for k, v in rule["with"].items()))
    if rule.get("add"):
        lines.append(f"  Adds the holder's {rule['add']}.")
    ranked = sorted(rule["results"], key=lambda r: r.get("from", float("-inf")), reverse=True)
    for result in ranked:
        lines.append(f"  {label(result, rule['results'])}: {result['text']}")
    holder = "" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"'
    amounts = ' [--with "<amount>"]...' if rule["with"] else ""
    lines.append(f'  Command: gm-rule.sh roll "{rule["name"]}"{holder}{amounts}')
    return lines
