#!/usr/bin/env python3
"""The bag: tokens of named kinds, drawn and added to (rules-proposal.md §3.4). The
odds are whatever is in the bag: a job's luck that runs out as things go wrong, the
years of the melt.

    {"name": "The Job", "block": "bag", "held_by": "world", "known": true,
     "summary": "...", "when": "Each risky step of a job: draw. A failed roll: add trouble.",
     "tokens": {"clean": 8, "trouble": 2},
     "draw": "keep out",
     "draw_every": "360d",
     "results": {"clean": {"text": "The step goes as planned."},
                 "trouble": {"text": "Something goes wrong.", "effects": [...], "gm": "..."}},
     "when_empty": "The luck has run out: the job goes loud now."}

- `draw`: "keep out" (a drawn token stays out until the bag is refilled, so the odds
  change) or "put back".
- `draw_every`: the bag is drawn by itself as game time passes, once per period.
- `results`: one per kind; a drawn token's effects run, its gm line is printed, and
  on_rule waits on a kind ("The Melt:collapse").
- Commands: `gm-rule.sh draw "<bag>" [holder] [N]`, `put`/`take "<bag>" [holder]
  <kind> N`, `refill` (back to `tokens`). The effect `tokens` adds or removes.

Stored per holder: {"tokens": {"clean": 5, "trouble": 3}, "drawn": ["clean", ...]}.
"""

import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

FIELDS = ("tokens", "draw", "draw_every", "results", "when_empty")
HOLDS = True
RESULT_FIELDS = ("text", "effects", "gm")
DRAWS = ("keep out", "put back")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check(rule: dict[str, Any], problems: list[str]) -> None:
    """A bag's own fields, checked and tidied."""
    import rule_effects
    from time_manager import TimeError, parse_duration
    tokens = rule.get("tokens")
    if not isinstance(tokens, dict) or not tokens or not all(
            isinstance(k, str) and k.strip() and _is_int(n) and n >= 0 for k, n in tokens.items()):
        problems.append('\'tokens\' are kinds and how many of each: {"clean": 8, "trouble": 2}')
        return
    if rule.setdefault("draw", "keep out") not in DRAWS:
        problems.append(f"'draw' is \"keep out\" or \"put back\", not {rule['draw']!r}")
    if "draw_every" in rule:
        try:
            parse_duration(str(rule["draw_every"]))
        except (ValueError, TimeError) as error:
            problems.append(f"'draw_every': {error}")
    if "when_empty" in rule and (not isinstance(rule["when_empty"], str) or not rule["when_empty"].strip()):
        problems.append("'when_empty' says what happens when the bag is empty")
    results = rule.get("results")
    if not isinstance(results, dict) or set(results) != set(tokens):
        problems.append(f"'results' has one result for each kind of token: {', '.join(tokens)}")
        return
    for kind, result in results.items():
        if not isinstance(result, dict):
            problems.append(f"the result of '{kind}' is {{\"text\": \"...\"}}")
            continue
        problems += [f"the result of '{kind}' has no '{k}'" for k in result if k not in RESULT_FIELDS]
        if not isinstance(result.get("text"), str) or not result["text"].strip():
            problems.append(f"the result of '{kind}' needs a 'text': what happens in the fiction")
        else:
            result["text"] = " ".join(result["text"].split())
        rule_effects.check_shape(result, kind, problems)


def _rule(json_ops, raw):
    import world_rules
    rule = world_rules.find_rule(json_ops, raw)
    if rule["block"] != "bag":
        raise world_rules.RulesError(f"{rule['name']} is a {rule['block']}, not a bag.")
    return rule


def _kind(rule, raw) -> str:
    import world_rules
    for kind in rule["tokens"]:
        if kind.lower() == " ".join(str(raw or "").split()).lower():
            return kind
    raise world_rules.RulesError(f"{rule['name']} has no tokens '{raw}'; its kinds: "
                                 f"{', '.join(rule['tokens'])}.")


def contents(tokens: dict[str, int]) -> str:
    return ", ".join(f"{n} {k}" for k, n in tokens.items()) or "empty"


def _save(json_ops, rule, holder, stored) -> None:
    import world_rules
    state = world_rules.load_state(json_ops)
    now = world_rules._now_game(json_ops)
    if now:
        stored["since"] = now
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)


def draw(json_ops, raw_rule, raw_holder=None, count: int = 1, rng=None,
         cause: str = "command", chain=None) -> dict[str, Any]:
    """Draw `count` tokens, one after the other. Returns {rule, holder, draws: [{kind,
    text, did, gm, fired}], empty (the when_empty text, if the bag ran out), left,
    known, character}."""
    import rule_effects
    import world_rules
    rule = _rule(json_ops, raw_rule)
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    if not _is_int(count) or count < 1:
        raise world_rules.RulesError("Draw at least one token.")
    rng = rng if rng is not None else random
    top = chain is None
    chain = rule_effects.new_chain() if top else chain
    report = {"rule": rule["name"], "holder": holder, "draws": [], "empty": ""}
    for _ in range(count):
        stored = dict(world_rules.entry(json_ops, rule, holder))
        tokens = dict(stored["tokens"])
        pool = [k for k, n in tokens.items() for _ in range(n)]
        if not pool:
            report["empty"] = rule.get("when_empty") or "The bag is empty."
            break
        kind = pool[rng.randint(0, len(pool) - 1)]
        if rule["draw"] == "keep out":
            tokens[kind] -= 1
        stored["tokens"] = tokens
        stored["drawn"] = list(stored.get("drawn") or []) + [kind]
        _save(json_ops, rule, holder, stored)
        world_rules._log(json_ops, holder, rule["name"], f"drew {kind} (left: {contents(tokens)})", cause)
        result = rule["results"][kind]
        done = [rule_effects.run(json_ops, effect, holder, chain, f"effect of {rule['name']} {kind}")
                for effect in result.get("effects") or []]
        report["draws"].append({"kind": kind, "text": result["text"], "did": done,
                                "gm": result.get("gm", ""),
                                "fired": rule_effects.fire_state(
                                    json_ops, rule["name"], holder, kind,
                                    world_rules.holder_name(json_ops, holder))})
    stored = world_rules.entry(json_ops, rule, holder)
    if not report["empty"] and rule["draw"] == "keep out" and not any(stored["tokens"].values()):
        report["empty"] = rule.get("when_empty") or "The bag is empty."
    report["left"] = dict(stored["tokens"])
    report["known"] = world_rules.is_known(rule, stored)
    if top:
        report["character"] = list(chain["character"])
    return report


def draw_lines(json_ops, report: dict[str, Any], indent: str = "") -> list[str]:
    import world_rules
    who = world_rules.holder_name(json_ops, report["holder"])
    mark = "" if report["known"] else f"  {world_rules.HIDDEN}"
    drew = ", ".join(d["kind"] for d in report["draws"]) or "nothing"
    lines = [f"{indent}{report['rule']} ({who}): drew {drew} (left: {contents(report['left'])}){mark}"]
    for one in report["draws"]:
        lines.append(f"{indent}  {one['kind']}: {one['text']}")
        lines += world_rules.done_lines(json_ops, one["did"], indent)
        if one["gm"]:
            lines.append(f"{indent}    Do now: {one['gm']}")
        lines += world_rules._fired_lines(one.get("fired"), indent + "  ")
    if report["empty"]:
        lines.append(f"{indent}  Empty: {report['empty']}")
    if report.get("character"):
        lines.append(f"{indent}Changed on the character: {'; '.join(report['character'])}.")
    return lines


def put(json_ops, raw_rule, raw_holder, raw_kind, amount: int, cause: str = "command") -> dict:
    """Add (`amount` > 0) or remove tokens of a kind. Removing more than there are
    is refused. Returns {rule, holder, kind, amount, before, after (the contents)}."""
    import world_rules
    rule = _rule(json_ops, raw_rule)
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    kind = _kind(rule, raw_kind)
    stored = dict(world_rules.entry(json_ops, rule, holder))
    tokens = dict(stored["tokens"])
    if tokens.get(kind, 0) + amount < 0:
        raise world_rules.RulesError(f"{rule['name']} has {tokens.get(kind, 0)} {kind}, not "
                                     f"{-amount} to take out.")
    before = dict(tokens)
    tokens[kind] = tokens.get(kind, 0) + amount
    stored["tokens"] = tokens
    _save(json_ops, rule, holder, stored)
    world_rules._log(json_ops, holder, rule["name"], f"{amount:+d} {kind} (now {contents(tokens)})", cause)
    return {"rule": rule["name"], "holder": holder, "kind": kind, "amount": amount,
            "before": before, "after": tokens}


def set_tokens(json_ops, raw_rule, raw_holder, given: dict, cause: str) -> dict:
    """Put a holder's bag at the given counts (a starting value); kinds not given
    keep theirs."""
    import world_rules
    rule = _rule(json_ops, raw_rule)
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    stored = dict(world_rules.entry(json_ops, rule, holder))
    before = dict(stored["tokens"])
    tokens = dict(before)
    for raw, n in given.items():
        if not _is_int(n) or n < 0:
            raise world_rules.RulesError(f"{rule['name']}: {raw} must be a count, 0 or more.")
        tokens[_kind(rule, raw)] = n
    stored["tokens"] = tokens
    _save(json_ops, rule, holder, stored)
    world_rules._log(json_ops, holder, rule["name"], f"set: {contents(tokens)}", cause)
    return {"rule": rule["name"], "holder": holder, "before": before, "after": tokens}


def refill(json_ops, raw_rule, raw_holder=None) -> dict:
    """Back to the rule's tokens; the drawn ones are forgotten."""
    import world_rules
    rule = _rule(json_ops, raw_rule)
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    stored = dict(world_rules.entry(json_ops, rule, holder))
    before = dict(stored["tokens"])
    stored.update(tokens=dict(rule["tokens"]), drawn=[])
    _save(json_ops, rule, holder, stored)
    world_rules._log(json_ops, holder, rule["name"], f"refilled: {contents(rule['tokens'])}", "command")
    return {"rule": rule["name"], "holder": holder, "before": before, "after": dict(rule["tokens"])}


def put_line(json_ops, report: dict) -> str:
    import world_rules
    who = world_rules.holder_name(json_ops, report["holder"])
    what = f"{report['amount']:+d} {report['kind']}" if "kind" in report else "refilled"
    return f"{report['rule']} ({who}): {what} (now {contents(report['after'])})"


def rule_lines(json_ops, rule: dict[str, Any], holders=None) -> list[str]:
    import world_rules
    hidden = "" if rule.get("known", True) else f"; {world_rules.HIDDEN}"
    lines = [f"{rule['name']} (bag: {contents(rule['tokens'])}, drawn {rule['draw']}, held by "
             f"{world_rules._kinds(rule)}{hidden}): {rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    if rule.get("draw_every"):
        lines.append(f"  Drawn by itself every {rule['draw_every']} of game time.")
    for kind, result in rule["results"].items():
        lines.append(f"  {kind}: {result['text']}")
    if rule.get("when_empty"):
        lines.append(f"  Empty: {rule['when_empty']}")
    holder = "" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"'
    lines.append(f'  Command: gm-rule.sh draw "{rule["name"]}"{holder} [N]; put|take '
                 f'"{rule["name"]}"{holder} <kind> N; refill "{rule["name"]}"{holder}')
    state = world_rules.load_state(json_ops)
    if holders is None:
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    for holder in holders:
        stored = world_rules.entry(json_ops, rule, holder, state)
        drawn = f"; drawn: {', '.join(stored['drawn'])}" if stored.get("drawn") else ""
        mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
        lines.append(f"  Now, {world_rules.holder_name(json_ops, holder)}: "
                     f"{contents(stored['tokens'])}{drawn}{mark}")
    return lines


def holder_line(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    import world_rules
    mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
    return f"{rule['name']}: {contents(stored['tokens'])} (bag){mark}"


def apply_time(json_ops, rule: dict[str, Any], before, after) -> list[dict]:
    """A bag with `draw_every` is drawn once per whole period passed (counted from
    each holder's `draw_from`). Returns the draws' reports."""
    from datetime import datetime, timedelta

    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    if not rule.get("draw_every"):
        return []
    every = timedelta(minutes=parse_duration(rule["draw_every"]))
    state = world_rules.load_state(json_ops)
    holders = [h for h in ("player", "world") if h in rule["held_by"]]
    holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    reports = []
    for holder in holders:
        state = world_rules.load_state(json_ops)
        stored = dict(world_rules.entry(json_ops, rule, holder, state))
        start = datetime.strptime(stored["draw_from"], STORED_FORMAT) if stored.get("draw_from") else before
        periods = max(0, (after - start) // every)
        stored["draw_from"] = (start + periods * every).strftime(STORED_FORMAT)
        state.setdefault(holder, {})[rule["name"]] = stored
        world_rules.save_state(json_ops, state)
        if periods:
            reports.append(draw(json_ops, rule["name"], holder, count=min(periods, 1000),
                                cause=f"time: drawn every {rule['draw_every']}"))
    return reports


# ---------- the block interface (world_rules.BLOCKS) ----------

def default(rule: dict[str, Any]) -> dict[str, Any]:
    return {"tokens": dict(rule["tokens"]), "drawn": []}


def outcomes(rule: dict[str, Any]) -> list[tuple[str, dict]]:
    results = rule.get("results")
    return list(results.items()) if isinstance(results, dict) else []


def summary(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    return f"{rule['name']}: {contents(stored['tokens'])}"


def start(json_ops, rule: dict[str, Any], value) -> dict[str, Any]:
    """Starting counts: {"clean": 5}; kinds left out keep the rule's."""
    import json

    import world_rules
    if not isinstance(value, dict):
        raise world_rules.RulesError(f"{rule['name']} is a bag: give its tokens, e.g. "
                                     f"{json.dumps(rule['tokens'])}.")
    return {"tokens": {_kind(rule, k): n for k, n in value.items()}}


def set_start(json_ops, rule, holder, value, cause) -> list[dict]:
    return [set_tokens(json_ops, rule["name"], holder, value["tokens"], cause)]


def on_redefine(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    """Keep a holder's tokens of the kinds the rule still has; new kinds start full."""
    old = stored.get("tokens") or {}
    stored["tokens"] = {k: int(old.get(k, n)) for k, n in rule["tokens"].items()}
    return ""


report_lines = draw_lines


def next_time(json_ops, rule: dict[str, Any], after):
    """When a bag with `draw_every` is next drawn for a holder."""
    import rule_time
    import world_rules
    if not rule.get("draw_every"):
        return None
    return min((rule_time.next_period(world_rules.entry(json_ops, rule, h).get("draw_from"),
                                      rule["draw_every"], after)
                for h in world_rules.holders_of(json_ops, rule)), default=None)
