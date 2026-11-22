#!/usr/bin/env python3
"""States: a world rule whose value is a named state, with the moves allowed between
them (the gm-rules skill). Addiction, a corporation's alert, a contact's trust:

    {"name": "Addiction", "block": "states", "held_by": ["player", "npc"],
     "summary": "...", "when": "A dose: gm-rule.sh move Addiction user (or hooked).",
     "start": "clean",
     "states": {
       "clean":  {"text": "No pull.", "moves": {"user": "a dose"}},
       "user":   {"text": "A taste for it.", "moves": {"hooked": "Need reaches 5", "clean": "a month without"},
                  "after": {"30d": "clean"}},
       "hooked": {"text": "Every scene without a dose: -1 to every roll.",
                  "moves": {"withdrawal": "a day without", "hooked": "a dose (the day starts again)"},
                  "after": {"1d": "withdrawal"},
                  "effects": [{"condition": "Hooked"}], "when_off": [{"condition": "Hooked", "add": false}]},
       ...}}

- `moves`: the states it can go to, each with its cause in words. `gm-rule.sh move`
  refuses any other move and lists the allowed ones; a state with no moves is final.
  Moving into the state it is in (if allowed) starts its time again.
- `after`: time spent in the state moves it on by itself (rule_time.apply, as game
  time passes), counted from when it was entered; several can follow at once.
- A state's `effects` run when it is entered, its `when_off` when it is left, its `gm`
  line is printed on entering (rule_effects.py), and on_rule consequences wait on it
  ("Addiction:hooked@npc:Precious Adeyemi").
- `gm-rule.sh set` puts a holder into a state whatever the moves (a correction, a
  starting value); the effects run as for a move.

Stored per holder: {"state": "hooked", "entered": "<game time>", "since": "<game time>"}.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

FIELDS = ("start", "states")
HOLDS = True
STATE_FIELDS = ("text", "moves", "after", "effects", "when_off", "gm")


def check(rule: dict[str, Any], problems: list[str]) -> None:
    """A states rule's own fields, checked and tidied."""
    import rule_effects
    from time_manager import TimeError, parse_duration
    states = rule.get("states")
    if not isinstance(states, dict) or not states:
        problems.append('\'states\' is {"<state>": {"text": "...", "moves": {"<state>": "<cause>"}}, ...}')
        return
    if rule.get("start") not in states:
        problems.append(f"'start' is one of the states: {', '.join(states)}")
    for name, state in states.items():
        if not isinstance(state, dict):
            problems.append(f"state '{name}' is {{\"text\": \"...\", \"moves\": {{...}}}}")
            continue
        problems += [f"state '{name}' has no '{k}'" for k in state if k not in STATE_FIELDS]
        if not isinstance(state.get("text"), str) or not state["text"].strip():
            problems.append(f"state '{name}' needs a 'text': what it means in the fiction")
        else:
            state["text"] = " ".join(state["text"].split())
        moves = state.setdefault("moves", {})
        if not isinstance(moves, dict) or not all(isinstance(c, str) and c.strip()
                                                  for c in moves.values()):
            problems.append(f"state '{name}': 'moves' is {{\"<state>\": \"<its cause>\"}}")
        else:
            problems += [f"state '{name}': it moves to '{t}', which is no state"
                         for t in moves if t not in states]
        after = state.get("after")
        if after is not None:
            if not isinstance(after, dict) or len(after) != 1:
                problems.append(f"state '{name}': 'after' is one {{\"<time>\": \"<state>\"}}")
            else:
                (when, target), = after.items()
                try:
                    parse_duration(when)
                except (ValueError, TimeError) as error:
                    problems.append(f"state '{name}': 'after': {error}")
                if target not in states or target == name:
                    problems.append(f"state '{name}': 'after' moves to another state, not '{target}'")
        rule_effects.check_shape(state, name, problems)


def _rule(json_ops, raw):
    import world_rules
    rule = world_rules.find_rule(json_ops, raw)
    if rule["block"] != "states":
        raise world_rules.RulesError(f"{rule['name']} is a {rule['block']}: it has no states "
                                     f"to move between.")
    return rule


def _find_state(rule, raw) -> str:
    import world_rules
    wanted = " ".join(str(raw or "").split()).lower()
    for name in rule["states"]:
        if name.lower() == wanted:
            return name
    raise world_rules.RulesError(f"{rule['name']} has no state '{raw}'; its states: "
                                 f"{', '.join(rule['states'])}.")


def allowed(rule, current: str) -> str:
    moves = rule["states"][current].get("moves") or {}
    if not moves:
        return f"'{current}' is final: there is no way out of it"
    return "from it: " + "; ".join(f"{t} ({cause})" for t, cause in moves.items())


def move(json_ops, raw_rule, raw_holder, raw_state, cause: str = "command", chain=None,
         force: bool = False, when: str | None = None) -> dict[str, Any]:
    """Move a holder into a state: one of the current state's moves, or any state
    with `force` (a correction, a start, time). `when` is the game time it happened
    (default now). Returns {rule, holder, before, after, did, gm, fired, known,
    character}, like world_rules.change."""
    import rule_effects
    import world_rules
    rule = _rule(json_ops, raw_rule)
    holder = world_rules.resolve_holder(json_ops, rule, raw_holder)
    target = _find_state(rule, raw_state)
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    before = stored.get("state", rule["start"])
    if not force and target not in (rule["states"][before].get("moves") or {}):
        raise world_rules.RulesError(f"{rule['name']} ({world_rules.holder_name(json_ops, holder)}) "
                                     f"can't move from '{before}' to '{target}': "
                                     f"{allowed(rule, before)}.")
    now = when or world_rules._now_game(json_ops)
    stored["state"] = target
    if now:
        stored["entered"] = stored["since"] = now
    state.setdefault(holder, {})[rule["name"]] = stored
    world_rules.save_state(json_ops, state)
    world_rules._log(json_ops, holder, rule["name"], f"{before} -> {target}", cause)
    top = chain is None
    chain = rule_effects.new_chain() if top else chain
    chain["seen"].add((rule["name"], holder))
    report = {"rule": rule["name"], "holder": holder, "before": before, "after": target,
              "known": world_rules.is_known(rule, stored), "did": {}, "gm": ""}
    pairs = [] if before == target else [(before, "when_off")]
    pairs.append((target, "effects"))
    for name, field in pairs:
        done = [rule_effects.run(json_ops, effect, holder, chain, f"effect of {rule['name']} {name}")
                for effect in rule["states"][name].get(field) or []]
        if done:
            report["did"][f"{name} {field}"] = done
    report["gm"] = rule["states"][target].get("gm", "")
    report["fired"] = rule_effects.fire_state(json_ops, rule["name"], holder, target,
                                              world_rules.holder_name(json_ops, holder))
    if top:
        report["character"] = list(chain["character"])
    return report


def move_lines(json_ops, report: dict[str, Any], indent: str = "") -> list[str]:
    """A move as the GM reads it."""
    import world_rules
    rule = world_rules.find_rule(json_ops, report["rule"])
    who = world_rules.holder_name(json_ops, report["holder"])
    mark = "" if report["known"] else f"  {world_rules.HIDDEN}"
    again = " (again: its time starts anew)" if report["before"] == report["after"] else ""
    lines = [f"{indent}{rule['name']} ({who}): {report['before']} → {report['after']}{again}{mark}",
             f"{indent}  now: {report['after']}: {rule['states'][report['after']]['text']}"]
    for done in report["did"].values():
        lines += world_rules.done_lines(json_ops, done, indent)
    if report["gm"]:
        lines.append(f"{indent}    Do now: {report['gm']}")
    lines += world_rules._fired_lines(report.get("fired"), indent + "  ")
    nxt = rule["states"][report["after"]]
    if not nxt.get("moves"):
        lines.append(f"{indent}  '{report['after']}' is final.")
    if report.get("character"):
        lines.append(f"{indent}Changed on the character: {'; '.join(report['character'])}.")
    return lines


def rule_lines(json_ops, rule: dict[str, Any], holders=None) -> list[str]:
    """A states rule in full, with where it stands for `holders`."""
    import world_rules
    hidden = "" if rule.get("known", True) else f"; {world_rules.HIDDEN}"
    lines = [f"{rule['name']} (states, held by {world_rules._kinds(rule)}{hidden}): "
             f"{rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    for name, state in rule["states"].items():
        moves = "; ".join(f"→ {t} ({c})" for t, c in (state.get("moves") or {}).items()) or "final"
        after = ""
        if state.get("after"):
            (when, target), = state["after"].items()
            after = f"; after {when}: → {target}"
        start = " (the start)" if name == rule["start"] else ""
        lines.append(f"  {name}{start}: {state['text']} Moves: {moves}{after}")
    holder = "" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"'
    lines.append(f'  Command: gm-rule.sh move "{rule["name"]}"{holder} <state>')
    state = world_rules.load_state(json_ops)
    if holders is None:
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    for holder in holders:
        stored = world_rules.entry(json_ops, rule, holder, state)
        since = f" (since {stored['entered']})" if stored.get("entered") else ""
        mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
        lines.append(f"  Now, {world_rules.holder_name(json_ops, holder)}: {stored['state']}{since}{mark}")
    return lines


def apply_time(json_ops, rule: dict[str, Any], before: datetime, after: datetime) -> list[dict]:
    """Move every holder whose state's `after` time has passed (several in a row if
    enough time passed). Returns the moves' reports."""
    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    state = world_rules.load_state(json_ops)
    holders = [h for h in ("player", "world") if h in rule["held_by"]]
    holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    reports = []
    for holder in holders:
        for _ in range(len(rule["states"])):                  # at most once through each
            stored = world_rules.entry(json_ops, rule, holder)
            current = rule["states"][stored["state"]]
            if not current.get("after"):
                break
            entered = (datetime.strptime(stored["entered"], STORED_FORMAT)
                       if stored.get("entered") else before)
            (wait, target), = current["after"].items()
            due = entered + timedelta(minutes=parse_duration(wait))
            if due > after:
                if not stored.get("entered"):                # start counting now
                    all_state = world_rules.load_state(json_ops)
                    all_state.setdefault(holder, {})[rule["name"]] = dict(
                        stored, entered=before.strftime(STORED_FORMAT))
                    world_rules.save_state(json_ops, all_state)
                break
            reports.append(move(json_ops, rule["name"], holder, target, force=True,
                                cause=f"time: {wait} in '{stored['state']}'",
                                when=due.strftime(STORED_FORMAT)))
    return reports


# ---------- the block interface (world_rules.BLOCKS) ----------

def default(rule: dict[str, Any]) -> dict[str, Any]:
    return {"state": rule["start"]}


def outcomes(rule: dict[str, Any]) -> list[tuple[str, dict]]:
    return list((rule.get("states") or {}).items())


def holder_line(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    import world_rules
    mark = "" if world_rules.is_known(rule, stored) else f" {world_rules.HIDDEN}"
    return (f"{rule['name']}: {stored['state']} (states): "
            f"{rule['states'][stored['state']]['text']}{mark}")


def summary(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    return f"{rule['name']}: {stored['state']}"


def start(json_ops, rule: dict[str, Any], value) -> str:
    return _find_state(rule, value)


def set_start(json_ops, rule, holder, value, cause) -> list[dict]:
    return [move(json_ops, rule["name"], holder, value, cause=cause, force=True)]


def on_redefine(rule: dict[str, Any], stored: dict[str, Any]) -> str:
    """A holder's state must still exist in the redefined rule."""
    if stored.get("state") not in rule["states"]:
        return f"its state '{stored.get('state')}' is gone: keep that state, or move them first"
    return ""


report_lines = move_lines


def next_time(json_ops, rule: dict[str, Any], after: datetime):
    """When a holder's state's `after` next moves them on."""
    import world_rules
    from game_time import STORED_FORMAT
    from time_manager import parse_duration
    times = []
    for holder in world_rules.holders_of(json_ops, rule):
        stored = world_rules.entry(json_ops, rule, holder)
        current = rule["states"][stored["state"]]
        if current.get("after"):
            (wait, _), = current["after"].items()
            entered = (datetime.strptime(stored["entered"], STORED_FORMAT)
                       if stored.get("entered") else after)
            times.append(entered + timedelta(minutes=parse_duration(wait)))
    return min(times, default=None)
