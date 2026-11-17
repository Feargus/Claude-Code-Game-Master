#!/usr/bin/env python3
"""Results that act: the effects a world rule's results carry out by themselves, and
the on_rule trigger that lets a consequence wait on a value (rules-proposal.md §7).

A counter's result can carry effects, run by the script the moment the result comes
on (`effects`) or goes off (`when_off`), and a line for the GM (`gm`), printed as
"Do now:" because it needs the GM's judgement (a death, a fact, a wound):

    {"from": 6, "off_at": ..., "text": "Panicking ...",
     "effects":  [{"condition": "Panicked"}],
     "when_off": [{"condition": "Panicked", "add": false}],
     "gm": "If they are in a fight, they flee: gm-combat.sh"}

The effects (a fixed list):

    {"change": "<rule>", "by": N}  or  "set": N    a value of a rule; "of": "<holder>"
                                                   for another holder (default: the same)
    {"clock": "<name>", "start": N, "text": "...", "due_in": "3d", "on": "time|event",
     "consequence": "..."}                        start a threat clock (gm-clock.sh)
    {"clock": "<name>", "advance": N}             advance an event clock
    {"condition": "<name>"}  or  "add": false     a condition on the character
    {"credits": N}                                the character's credits

`rate_of`, `tokens` and `state` come with rates, bags and states.

A change made by an effect turns its own results on and off, which may carry effects
in turn: a chain. In one chain a rule's value for a holder changes once (a second
change is stopped, and the output says so), and a chain ends after MAX_STEPS effects.

on_rule: `gm-consequence.sh add ... --trigger-type on_rule --match "Sea level:5"`
fires when the world's sea level reaches 5, from below or above;
`"Patience:0@faction:lull"` names the holder when the rule has several.
"""

import contextlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

KINDS = ("change", "rate_of", "state", "clock", "condition", "credits")
LATER = {"tokens": 8}
FIELDS = {"change": ("change", "axis", "by", "set", "of"),
          "rate_of": ("rate_of", "by", "of"),
          "state": ("state", "to", "of"),
          "clock": ("clock", "start", "advance", "text", "due_in", "on", "consequence"),
          "condition": ("condition", "add"),
          "credits": ("credits",)}
MAX_STEPS = 10


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def kind_of(effect: dict[str, Any]) -> str:
    return next((k for k in KINDS + tuple(LATER) if k in effect), "")


# ---------- checking (when the rules are defined) ----------

def check_shape(result: dict[str, Any], number, problems: list[str]) -> None:
    """The shape of a result's (or a state's) effects, when_off and gm line. `number`
    is the result's number, or a state's name."""
    where = f"result {number}" if isinstance(number, int) else f"state '{number}'"
    for field in ("effects", "when_off"):
        if field not in result:
            continue
        effects = result[field]
        if not isinstance(effects, list):
            problems.append(f"{where}: '{field}' must be a list of effects")
            continue
        for effect in effects:
            problems += [f"{where}, {field}: {p}" for p in _check_one(effect)]
    if "gm" in result and (not isinstance(result["gm"], str) or not result["gm"].strip()):
        problems.append(f"{where}: 'gm' must be a line for the GM")


def _check_one(effect: Any) -> list[str]:
    if not isinstance(effect, dict):
        return ['an effect is an object, e.g. {"change": "Bleed", "by": 1}']
    kind = kind_of(effect)
    if kind in LATER:
        return [f"'{kind}' isn't built yet (rules-proposal.md, step {LATER[kind]})"]
    if not kind:
        return [f"an effect is one of {', '.join(KINDS)}; got {sorted(effect)}"]
    problems = [f"'{field}' has no place in a {kind} effect" for field in effect
                if field not in FIELDS[kind]]
    return problems + CHECKS[kind](effect)


def _check_change(effect) -> list[str]:
    given = [f for f in ("by", "set") if f in effect]
    if len(given) != 1 or not _is_int(effect[given[0]]):
        return ['a change effect has "by": N or "set": N (a whole number)']
    return []


def _check_clock(effect) -> list[str]:
    problems = []
    given = [f for f in ("start", "advance") if f in effect]
    if len(given) != 1 or not _is_int(effect[given[0]]) or effect[given[0]] < 1:
        problems.append('a clock effect has "start": N segments or "advance": N (1 or more)')
    if "advance" in effect and set(effect) - {"clock", "advance"}:
        problems.append("an advance of a clock takes only its name and \"advance\"")
    if effect.get("on", "time") not in ("time", "event"):
        problems.append('a clock is "on": "time" or "event"')
    if "due_in" in effect:
        from time_manager import TimeError, parse_duration
        try:
            parse_duration(str(effect["due_in"]))
        except (ValueError, TimeError) as error:
            problems.append(f"due_in: {error}")
    return problems


def _check_condition(effect) -> list[str]:
    problems = []
    if not isinstance(effect["condition"], str) or not effect["condition"].strip():
        problems.append("a condition effect names the condition")
    if not isinstance(effect.get("add", True), bool):
        problems.append('"add" is true or false')
    return problems


def _check_credits(effect) -> list[str]:
    if not _is_int(effect["credits"]) or effect["credits"] == 0:
        return ['a credits effect is "credits": N, a whole number (negative spends)']
    return []


def _check_state(effect) -> list[str]:
    if not isinstance(effect.get("to"), str) or not effect["to"].strip():
        return ['a state effect has "to": the state to move into']
    return []


def _check_rate_of(effect) -> list[str]:
    if not _is_int(effect.get("by")) or effect["by"] == 0:
        return ['a rate_of effect has "by": N, the steps added to the rate (negative slows it)']
    return []


CHECKS = {"change": _check_change, "rate_of": _check_rate_of, "state": _check_state,
          "clock": _check_clock,
          "condition": _check_condition, "credits": _check_credits}


def outcomes(rule: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(label, the dict that may carry effects) for each of a rule's outcomes: a
    counter's or a roll's results, a plane's regions, a states rule's states."""
    from world_rules import label
    if rule.get("block") == "plane":
        return [(r.get("name"), r) for r in rule.get("regions") or []]
    if rule.get("block") == "states":
        return list((rule.get("states") or {}).items())
    return [(label(rule, r), r) for r in rule.get("results") or []]


def effects_of(rule: dict[str, Any]):
    """(outcome label, field, effect) for every effect of a rule."""
    for name, outcome in outcomes(rule):
        for field in ("effects", "when_off"):
            for effect in outcome.get(field) or []:
                yield name, field, effect


def check_links(rules: list[dict[str, Any]], problems: list[str]) -> None:
    """What the effects name exists and fits: a change names a counter (not its own
    rule), a rate_of a counter with a rate in steps, a state a states rule and one of
    its states, a roll's add a counter; and each can be held by the same holder, or
    the one `of` names."""
    by_name = {r["name"].lower(): r for r in rules}
    for rule in rules:
        if rule.get("add"):
            _link_add(rule, by_name, problems)
        for label, field, effect in effects_of(rule):
            kind = kind_of(effect)
            if kind in LINKS:
                where = f"{rule['name']}, {label}, {field}"
                target = by_name.get(str(effect[kind]).lower())
                if LINKS[kind](effect, rule, target, where, problems):
                    effect[kind] = target["name"]
                    _check_whose(effect, rule, target, where, problems)


def _link_add(rule, by_name, problems) -> None:
    """A roll adds a counter's value."""
    added = by_name.get(str(rule["add"]).lower())
    if added is None or added["block"] != "counter":
        problems.append(f"{rule['name']}: 'add' names no counter ('{rule['add']}')")
    elif not set(rule["held_by"]) <= set(added["held_by"]):
        problems.append(f"{rule['name']}: 'add': {added['name']} is held by "
                        f"{', '.join(added['held_by'])}, not by every holder of {rule['name']}")
    else:
        rule["add"] = added["name"]


def _link_change(effect, rule, target, where, problems) -> bool:
    if target is None or target["block"] not in ("counter", "plane"):
        problems.append(f"{where}: no counter or plane '{effect['change']}' to change")
        return False
    if target["name"] == rule["name"] and "of" not in effect:
        problems.append(f"{where}: a result can't change its own rule")
    if target["block"] == "plane":
        axis = next((a for a in target["axes"] if a.lower() == str(effect.get("axis", "")).lower()), None)
        if axis is None:
            problems.append(f"{where}: {target['name']} is a plane: \"axis\" is one of "
                            f"{', '.join(target['axes'])}")
            return False
        effect["axis"] = axis
        low, high = target["axes"][axis]
    elif "axis" in effect:
        problems.append(f"{where}: {target['name']} has no axes")
        return False
    else:
        low, high = target["range"]
    if "set" in effect and not low <= effect["set"] <= high:
        problems.append(f"{where}: {target['name']} goes from {low} to {high}, not {effect['set']}")
    return True


def _link_rate_of(effect, rule, target, where, problems) -> bool:
    if target is None or not (target.get("rate") or {}).get("by"):
        problems.append(f"{where}: no counter '{effect['rate_of']}' with a rate in steps "
                        f"('by') to change")
        return False
    return True


def _link_state(effect, rule, target, where, problems) -> bool:
    if target is None or target["block"] != "states":
        problems.append(f"{where}: no states rule '{effect['state']}' to move")
        return False
    to = next((s for s in target["states"] if s.lower() == str(effect["to"]).lower()), None)
    if to is None:
        problems.append(f"{where}: {target['name']} has no state '{effect['to']}'")
        return False
    effect["to"] = to
    return True


LINKS = {"change": _link_change, "rate_of": _link_rate_of, "state": _link_state}


def _check_whose(effect, rule, target, where, problems) -> None:
    """The holder an effect changes can hold the target: `of`, or the rule's own."""
    if "of" in effect:
        holder = str(effect["of"]).strip()
        kind = "world" if holder.lower() == "world" else (
            "player" if holder.lower() == "player" else holder.partition(":")[0])
        if kind not in target["held_by"]:
            problems.append(f"{where}: {target['name']} can't be held by '{holder}'")
    elif not set(rule["held_by"]) <= set(target["held_by"]):
        problems.append(f"{where}: {target['name']} is held by "
                        f"{', '.join(target['held_by'])}, not by every holder of "
                        f"{rule['name']}; name whose with \"of\"")


def referring(rules: list[dict[str, Any]], name: str) -> list[str]:
    """The rules whose effects change `name`, or whose roll adds it."""
    return [r["name"] for r in rules if r["name"] != name and (
        r.get("add") == name
        or any(e.get(kind_of(e)) == name for _, _, e in effects_of(r)
               if kind_of(e) in ("change", "rate_of", "state")))]


# ---------- running ----------

def new_chain() -> dict[str, Any]:
    return {"seen": set(), "steps": 0, "character": []}


def _base(json_ops) -> str | None:
    """The world-state folder whose active campaign is `json_ops`'s, or None: clocks
    and consequences are opened through the active campaign."""
    from campaign_manager import CampaignManager
    campaign = Path(json_ops.world_state_dir).resolve()
    base = campaign.parent.parent
    active = CampaignManager(str(base)).get_active_campaign_dir()
    return str(base) if active and Path(active).resolve() == campaign else None


def run(json_ops, effect: dict[str, Any], holder: str, chain: dict[str, Any],
        cause: str) -> dict[str, Any]:
    """Carry out one effect for `holder`. Returns {"line": what was done, "report":
    the change it made (for a change), "fired": consequences it fired}."""
    chain["steps"] += 1
    if chain["steps"] > MAX_STEPS:
        return {"line": f"stopped: a chain ends after {MAX_STEPS} effects"}
    kind = kind_of(effect)
    from time_manager import TimeError
    try:
        if kind == "change":
            return _change(json_ops, effect, holder, chain, cause)
        if kind == "rate_of":
            return _rate_of(json_ops, effect, holder)
        if kind == "state":
            return _state(json_ops, effect, holder, chain, cause)
        with contextlib.redirect_stdout(sys.stderr):    # the managers announce themselves
            if kind == "clock":
                return _clock(json_ops, effect)
            if kind == "condition":
                return _condition(json_ops, effect, chain)
            return _credits(json_ops, effect, chain)
    except (ValueError, OSError, TimeError) as error:
        return {"line": f"not done ({kind}): {error}"}


def _change(json_ops, effect, holder, chain, cause) -> dict[str, Any]:
    import world_rules
    target = world_rules.find_rule(json_ops, effect["change"])
    whose = world_rules.resolve_holder(json_ops, target, effect["of"]) if "of" in effect else holder
    if (target["name"], whose) in chain["seen"]:
        return {"line": f"stopped: {target['name']} of {world_rules.holder_name(json_ops, whose)} "
                        f"changed once already in this chain"}
    report = world_rules.change(json_ops, target["name"], whose, by=effect.get("by"),
                                to=effect.get("set"), cause=cause, chain=chain,
                                axis=effect.get("axis"))
    return {"line": "", "report": report}


def _state(json_ops, effect, holder, chain, cause) -> dict[str, Any]:
    """Move a states rule, by one of its allowed moves only."""
    import rule_states
    import world_rules
    target = world_rules.find_rule(json_ops, effect["state"])
    whose = world_rules.resolve_holder(json_ops, target, effect["of"]) if "of" in effect else holder
    if (target["name"], whose) in chain["seen"]:
        return {"line": f"stopped: {target['name']} of {world_rules.holder_name(json_ops, whose)} "
                        f"changed once already in this chain"}
    try:
        report = rule_states.move(json_ops, target["name"], whose, effect["to"], cause=cause,
                                  chain=chain)
    except world_rules.RulesError as error:
        return {"line": f"not done: {error}"}
    return {"line": "", "states_report": report}


def _rate_of(json_ops, effect, holder) -> dict[str, Any]:
    import rule_time
    import world_rules
    target = world_rules.find_rule(json_ops, effect["rate_of"])
    whose = world_rules.resolve_holder(json_ops, target, effect["of"]) if "of" in effect else holder
    old, new = rule_time.set_rate(json_ops, target["name"], whose, add=effect["by"])
    return {"line": f"{target['name']} ({world_rules.holder_name(json_ops, whose)}): rate "
                    f"{rule_time.describe(old)} → {rule_time.describe(new)}"}


def _clock(json_ops, effect) -> dict[str, Any]:
    base = _base(json_ops)
    if base is None:
        return {"line": f"not done: clock {effect['clock']} (not the active campaign)"}
    from threat_clocks import ThreatClockManager
    clocks = ThreatClockManager(base)
    if "advance" in effect:
        clock = clocks.advance(effect["clock"], effect["advance"])
        if clock is None:
            return {"line": f"not done: no clock '{effect['clock']}' to advance"}
        return {"line": f"clock {effect['clock']} advanced to {clock['current']}/{clock['max']}",
                "fired": clock.get("fired") or []}
    due = None
    if effect.get("due_in"):
        from time_manager import parse_duration
        due = parse_duration(str(effect["due_in"]))
    clocks.add_clock(effect["clock"], effect["start"], advance_on=effect.get("on", "time"),
                     consequence=effect.get("consequence"), text=effect.get("text"),
                     due_in_minutes=due)
    when = f", due in {effect['due_in']}" if effect.get("due_in") else ""
    return {"line": f"clock {effect['clock']} started ({effect['start']} segments{when})"}


def _character(json_ops):
    character = json_ops.load_json("character.json") or {}
    if not character:
        raise ValueError("there is no character yet")
    return character


def _condition(json_ops, effect, chain) -> dict[str, Any]:
    import sheet as sheet_mod
    character = _character(json_ops)
    conditions = sheet_mod.section(character, "status").setdefault("conditions", [])
    name = " ".join(effect["condition"].split())
    have = next((c for c in conditions if c.lower() == name.lower()), None)
    if effect.get("add", True):
        if have:
            return {"line": f"condition {have}: the character has it already"}
        conditions.append(name)
        what = f"condition {name} added"
    else:
        if not have:
            return {"line": f"condition {name}: the character doesn't have it"}
        conditions.remove(have)
        what = f"condition {have} removed"
    json_ops.save_json("character.json", character)
    chain["character"].append(what)
    return {"line": what}


def _credits(json_ops, effect, chain) -> dict[str, Any]:
    import sheet as sheet_mod
    character = _character(json_ops)
    possessions = sheet_mod.section(character, "possessions")
    have = int(possessions.get("credits", 0) or 0)
    if have + effect["credits"] < 0:
        return {"line": f"not done: the character has {have} credits, not the "
                        f"{-effect['credits']} this would take"}
    possessions["credits"] = have + effect["credits"]
    json_ops.save_json("character.json", character)
    what = f"{effect['credits']:+d} credits (now {possessions['credits']})"
    chain["character"].append(what)
    return {"line": what}


# ---------- on_rule ----------

def on_rule_target(json_ops, raw: str) -> tuple[str, str]:
    """The canonical on_rule match ("<rule>:<value>@<holder>", '') for "<rule>:<value>"
    or "<rule>:<value>@<holder>", or ('', why not)."""
    import world_rules
    usage = ('on_rule matches "<rule>:<value>" (e.g. "Sea level:5"), or '
             '"<rule>:<value>@<holder>" when the rule has several holders '
             '("Patience:0@faction:lull").')
    text = " ".join(str(raw or "").split())
    head, _, holder = text.partition("@")
    name, sep, value = head.strip().rpartition(":")
    try:
        rule = world_rules.find_rule(json_ops, name) if sep else None
        if rule is not None and rule["block"] == "states":
            whose = world_rules.resolve_holder(json_ops, rule, holder.strip() or None)
            import rule_states
            return f"{rule['name']}:{rule_states._find_state(rule, value)}@{whose}", ""
        if rule is not None and rule["block"] == "plane":
            whose = world_rules.resolve_holder(json_ops, rule, holder.strip() or None)
            region = next((r["name"] for r in rule["regions"]
                           if r["name"].lower() == value.strip().lower()), None)
            if region is None:
                return "", (f"on_rule: {rule['name']} has no region '{value.strip()}'; its "
                            f"regions: {', '.join(r['name'] for r in rule['regions'])}.")
            return f"{rule['name']}:{region}@{whose}", ""
        if not sep or not value.strip().lstrip("-").isdigit():
            return "", (f"{usage} A states rule: \"<rule>:<state>\" (\"Addiction:hooked\"). "
                        f"Got '{text}'.")
        rule = world_rules.counter(json_ops, name)
        whose = world_rules.resolve_holder(json_ops, rule, holder.strip() or None)
    except world_rules.RulesError as error:
        return "", f"on_rule: {error}"
    low, high = rule["range"]
    if not low <= int(value) <= high:
        return "", f"on_rule: {rule['name']} goes from {low} to {high}, not {value}."
    return f"{rule['name']}:{int(value)}@{whose}", ""


def fire_state(json_ops, rule: str, holder: str, state: str, who: str) -> list[dict[str, Any]]:
    """Fire the on_rule consequences waiting for a holder to enter `state`."""
    base = _base(json_ops)
    if base is None:
        return []
    from consequence_manager import ConsequenceManager
    with contextlib.redirect_stdout(sys.stderr):
        return ConsequenceManager(base).fire_event(
            "on_rule", [f"{rule}:{state}@{holder}"], f"{rule} of {who} became {state}")


def fire_on_rule(json_ops, rule: str, holder: str, before: int, after: int,
                 who: str) -> list[dict[str, Any]]:
    """Fire the on_rule consequences for every value the change reached."""
    if before == after:
        return []
    base = _base(json_ops)
    if base is None:
        return []
    reached = range(before + 1, after + 1) if after > before else range(after, before)
    values = [f"{rule}:{n}@{holder}" for n in reached]
    from consequence_manager import ConsequenceManager
    with contextlib.redirect_stdout(sys.stderr):
        return ConsequenceManager(base).fire_event(
            "on_rule", values, f"{rule} of {who} went from {before} to {after}")
