#!/usr/bin/env python3
"""The world's rules: a campaign's own mechanics, built from a few building blocks.

A campaign adds its own rules to the shared ones (skill contests, wounds, growth):
Bleed, a sea level, a gang's patience. Each rule is one building block with this
world's numbers and words:

    ruleset.json     "rules": the rules, written when the world is made (`define`),
                     and "plain_rules": rule lines that are no mechanic (prices)
    rule-state.json  where each rule stands now, per holder:
                     {"player": {"Bleed": {"value": 4, "on": ["from 2", "from 4"], ...}},
                      "faction:lull": {"Patience": {"value": 1}}, "world": {...}}
    rules.log        every change, with its cause (per machine, like skill-contest.log)

A rule says who can hold it (`held_by`): the player, NPCs, factions, places or the
world. Each holder has its own value, which starts at the rule's `start` and is
written to rule-state.json once it is set or changes. Holders are written as the
facts write them (player, npc:<key>, location:<key>), plus `faction:<id>` (a faction
of the world bible's factions graph, until factions have records) and `world`.

Building blocks (rules-proposal.md in the campaign repo has the plan):
    counter   one number in a range; results by range, cumulative unless `to` is given;
              options: a rate (rule_time.py), hysteresis (a result's `off_at`), overflow
              (lasting marks), streak
    roll      dice plus named amounts (and a holder's value of a counter), read from a
              list of results; keeps nothing (rule_roll.py)
    states    named states and the moves allowed between them; time can move them on
              (rule_states.py)
    plane     two values read together; results by region (rule_plane.py)
    bag       tokens drawn and added to; the odds are what is in it (rule_bag.py)
    budget    a fixed amount split among named parts, refilled (rule_budget.py)

A value is known (the default: the HUD may show it, the narration make it plain) or
hidden (the GM sees it, the player only its signs; every output marks it).

    gm-rule.sh list | show "<rule>" [holder]
    gm-rule.sh change "<rule>" [holder] +N|-N   ·   set "<rule>" [holder] N
    gm-rule.sh roll "<rule>" [holder] [--with "<amount>"]...
    gm-rule.sh move "<rule>" [holder] <state>   (set: any state, a correction)
    gm-rule.sh draw "<bag>" [holder] [N]   ·   put|take "<bag>" [holder] <kind> N   ·   refill
    gm-rule.sh split "<budget>" [holder] <part>=N ...   ·   refill "<budget>" [holder]
    gm-rule.sh reveal|hide "<rule>" [holder]   ·   break "<rule>" [holder]
    gm-rule.sh mark "<rule>" [holder] "<mark>"   ·   rate "<rule>" [holder] --by N [--every 90d]
    gm-rule.sh define <<'EOF' [...rules...] EOF   ·   plain <<'EOF' lines EOF   ·   remove "<rule>"
"""

import difflib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

RULESET = "ruleset.json"
STATE = "rule-state.json"
LOG = "rules.log"
BIBLE = "world-bible.json"

HOLDER_KINDS = ("player", "npc", "faction", "location", "world")
BLOCKS = ("counter", "roll", "states", "plane", "bag", "budget")
LATER_BLOCKS: dict[str, int] = {}
COMMON_FIELDS = ("name", "block", "held_by", "known", "summary", "when", "notes")
BLOCK_FIELDS = {"counter": ("range", "start", "results", "rate", "overflow", "streak"),
                "roll": ("dice", "with", "add", "results"),
                "states": ("start", "states"),
                "plane": ("axes", "start", "rates", "regions"),
                "bag": ("tokens", "draw", "draw_every", "results", "when_empty"),
                "budget": ("amount", "unit", "period", "parts")}
RESULT_FIELDS = {"counter": ("from", "to", "off_at", "text", "effects", "when_off", "gm")}
LATER_FIELDS: dict[str, int] = {}     # fields of a later step: "isn't built yet (step N)"
MAX_NAME_WORDS = 3
MAX_NAME_CHARS = 30
HIDDEN = "[HIDDEN: show only its signs]"


class RulesError(ValueError):
    """A rule or a change that can't be made. The message says how to fix it."""


# ---------- the rules ----------

def rules(json_ops) -> list[dict[str, Any]]:
    """The campaign's rules, in the order they were defined."""
    value = (json_ops.load_json(RULESET) or {}).get("rules") or []
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def plain_rules(json_ops) -> list[str]:
    value = (json_ops.load_json(RULESET) or {}).get("plain_rules") or []
    return [str(v) for v in value] if isinstance(value, list) else []


def find_rule(json_ops, raw) -> dict[str, Any]:
    """The rule `raw` names (case and spacing ignored), or RulesError with close names."""
    wanted = " ".join(str(raw or "").split()).lower()
    found = rules(json_ops)
    for rule in found:
        if rule["name"].lower() == wanted:
            return rule
    names = [r["name"] for r in found]
    if not names:
        raise RulesError(f"No rule '{raw}': this campaign has no rules of its own yet "
                         f"(gm-rule.sh define).")
    close = difflib.get_close_matches(wanted, [n.lower() for n in names], n=3, cutoff=0.6)
    if close:
        hint = f"; did you mean: {', '.join(n for n in names if n.lower() in close)}?"
    else:
        hint = f". The rules: {', '.join(names)}."
    raise RulesError(f"No rule '{raw}'{hint}")


def _name(raw) -> str:
    name = " ".join(str(raw or "").split())
    if not name:
        raise RulesError('A rule needs a name, a short key such as "Bleed" or "Sea level".')
    if ":" in name or len(name.split()) > MAX_NAME_WORDS or len(name) > MAX_NAME_CHARS:
        raise RulesError(f"A rule's name is a short key, one to {MAX_NAME_WORDS} words and at "
                         f"most {MAX_NAME_CHARS} characters, without a colon: commands and "
                         f"triggers use it, so it never changes. What the rule is about goes "
                         f"into its summary. Got '{name}'.")
    return name


def _text(rule: dict, field: str, problems: list[str], required: bool = True) -> None:
    value = rule.get(field)
    if value is None and not required:
        return
    if not isinstance(value, str) or not value.strip():
        problems.append(f"'{field}' must be a sentence"
                        + (" (what the rule is about)" if field == "summary" else "")
                        + (" (when the GM uses it)" if field == "when" else ""))
    else:
        rule[field] = " ".join(value.split())


def _unknown(fields, allowed, where: str, what: str, problems: list[str]) -> None:
    """Fields that aren't `allowed`: those of a later step say so."""
    for field in fields:
        if field in allowed:
            continue
        if field in LATER_FIELDS:
            problems.append(f"'{field}'{where} isn't built yet (rules-proposal.md, step "
                            f"{LATER_FIELDS[field]})")
        else:
            problems.append(f"unknown field '{field}'{where}; {what} has {', '.join(allowed)}")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_counter(rule: dict, problems: list[str]) -> None:
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
        where = f" in result {number}"
        if not isinstance(result, dict):
            problems.append(f'result {number} must be {{"from": N, "text": "..."}}')
            continue
        _unknown(result, RESULT_FIELDS["counter"], where, "a result", problems)
        if not _is_int(result.get("from")) or not low <= result["from"] <= high:
            problems.append(f"result {number} needs 'from', a whole number from {low} to {high}")
            continue
        if "to" in result and (not _is_int(result["to"]) or not result["from"] <= result["to"] <= high):
            problems.append(f"result {number}: 'to' must be a whole number from "
                            f"{result['from']} to {high}")
            continue
        if "off_at" in result and ("to" in result or not _is_int(result["off_at"])
                                   or not low <= result["off_at"] < result["from"]):
            problems.append(f"result {number}: 'off_at' is where it goes off again, a whole "
                            f"number from {low} to {result['from'] - 1}, and not with 'to'")
            continue
        if not isinstance(result.get("text"), str) or not result["text"].strip():
            problems.append(f"result {number} needs a 'text': what happens in the fiction")
            continue
        result["text"] = " ".join(result["text"].split())
        import rule_effects
        rule_effects.check_shape(result, number, problems)
        label = result_label(result)
        if label in labels:
            problems.append(f"two results are {label}: make them one")
        labels.append(label)


def _check_counter_options(rule: dict, problems: list[str]) -> None:
    """A counter's rate, overflow and streak."""
    low, high = rule["range"]
    if "rate" in rule:
        import rule_time
        problems += rule_time.check(rule["rate"], low, high)
    ov = rule.get("overflow")
    if ov is not None:
        if not isinstance(ov, dict):
            problems.append('\'overflow\' is {"at": N, "back_to": M, "marks": [...], '
                            '"limit": K, "at_limit": "..."}')
        else:
            problems += [f"'overflow' has no '{k}'" for k in ov
                         if k not in ("at", "back_to", "marks", "limit", "at_limit")]
            if not _is_int(ov.get("at")) or not low < ov["at"] <= high:
                problems.append(f"'overflow': 'at' is a whole number from {low + 1} to {high}")
            elif not _is_int(ov.setdefault("back_to", low)) or not low <= ov["back_to"] < ov["at"]:
                problems.append(f"'overflow': 'back_to' is a whole number from {low} to {ov['at'] - 1}")
            if not isinstance(ov.setdefault("marks", []), list) or \
                    not all(isinstance(m, str) and m.strip() for m in ov["marks"]):
                problems.append("'overflow': 'marks' is a list of suggested marks")
            if "limit" in ov and (not _is_int(ov["limit"]) or ov["limit"] < 1
                                  or not isinstance(ov.get("at_limit"), str)
                                  or not ov["at_limit"].strip()):
                problems.append("'overflow': 'limit' is a number of marks (1 or more), with "
                                "'at_limit', what happens then")
    if not isinstance(rule.get("streak", False), bool):
        problems.append("'streak' is true or false")


def check_rule(raw: Any) -> dict[str, Any]:
    """A rule as given, checked and tidied; RulesError lists every problem."""
    if not isinstance(raw, dict):
        raise RulesError('A rule is an object: {"name": "...", "block": "counter", ...}.')
    rule = json.loads(json.dumps(raw))                         # a copy, plain JSON
    rule["name"] = _name(rule.get("name"))
    problems = []
    block = rule.get("block")
    if block in LATER_BLOCKS:
        raise RulesError(f"{rule['name']}: the block '{block}' isn't built yet "
                         f"(rules-proposal.md, step {LATER_BLOCKS[block]}). Built: "
                         f"{', '.join(BLOCKS)}.")
    if block not in BLOCKS:
        raise RulesError(f"{rule['name']}: 'block' must be one of "
                         f"{', '.join(BLOCKS + tuple(LATER_BLOCKS))}, not {block!r}.")
    _unknown(rule, COMMON_FIELDS + BLOCK_FIELDS[block], "", f"a {block}", problems)
    held = rule.get("held_by")
    held = [held] if isinstance(held, str) else held
    if not isinstance(held, list) or not held or any(h not in HOLDER_KINDS for h in held):
        problems.append(f"'held_by' must be one of {', '.join(HOLDER_KINDS)}, or a list of them")
    else:
        rule["held_by"] = list(dict.fromkeys(held))
    if not isinstance(rule.setdefault("known", True), bool):
        problems.append("'known' must be true or false")
    _text(rule, "summary", problems)
    _text(rule, "when", problems)
    _text(rule, "notes", problems, required=False)
    if block == "counter":
        _check_counter(rule, problems)
        if not problems:
            _check_counter_options(rule, problems)
    elif block == "roll":
        import rule_roll
        rule_roll.check(rule, problems)
    elif block == "states":
        import rule_states
        rule_states.check(rule, problems)
    elif block == "plane":
        import rule_plane
        rule_plane.check(rule, problems)
    elif block == "bag":
        import rule_bag
        rule_bag.check(rule, problems)
    elif block == "budget":
        import rule_budget
        rule_budget.check(rule, problems)
    if problems:
        raise RulesError(f"{rule['name']}: " + "; ".join(problems) + ".")
    return rule


def _ruleset(json_ops) -> dict[str, Any]:
    ruleset = json_ops.load_json(RULESET) or {}
    if not ruleset.get("name"):
        bible = json_ops.load_json(BIBLE) or {}
        ruleset["name"] = bible.get("name") or Path(json_ops.world_state_dir).name
    return ruleset


def define(json_ops, given: Any) -> list[tuple[str, str]]:
    """Add rules, or replace those of the same name: all or nothing. Returns
    [(name, "added" | "replaced")]. A replaced rule keeps its holders' values
    (clamped into a new range); its block can't change while values exist."""
    given = [given] if isinstance(given, dict) else given
    if not isinstance(given, list) or not given:
        raise RulesError("Give the rules as a list: [{\"name\": \"...\", ...}, ...].")
    checked, problems = [], []
    for raw in given:
        try:
            checked.append(check_rule(raw))
        except RulesError as error:
            problems.append(str(error))
    names = [r["name"].lower() for r in checked]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        problems.append(f"Each rule once: {', '.join(twice)} given twice.")
    if problems:
        raise RulesError(" ".join(problems) + " Nothing was saved.")
    ruleset = _ruleset(json_ops)
    have = [r for r in ruleset.get("rules") or [] if isinstance(r, dict)]
    import rule_effects  # what the effects name must exist, then or now
    new = {r["name"].lower() for r in checked}
    rule_effects.check_links(checked + [r for r in have if r["name"].lower() not in new], problems)
    if problems:
        raise RulesError(" ".join(problems) + " Nothing was saved.")
    state = load_state(json_ops)
    done = []
    for rule in checked:
        index = next((i for i, r in enumerate(have) if r["name"].lower() == rule["name"].lower()), None)
        if index is None:
            have.append(rule)
            done.append((rule["name"], "added"))
        else:
            have[index] = _replace(have[index], rule, state)
            done.append((have[index]["name"], "replaced"))
    ruleset["rules"] = have
    json_ops.save_json(RULESET, ruleset)
    if state:
        save_state(json_ops, state)
    return done


def _replace(old: dict[str, Any], rule: dict[str, Any], state: dict) -> dict[str, Any]:
    """`rule` in place of `old`, under the old key; the holders' values (in `state`)
    are kept, moved into a new range."""
    holders = [h for h, values in state.items() if old["name"] in values]
    if old.get("block") != rule["block"] and holders:
        raise RulesError(f"{rule['name']} is a {old.get('block')} with values "
                         f"({', '.join(holders)}); it can't become a {rule['block']}. "
                         f"Remove it first (gm-rule.sh remove), or give the new rule "
                         f"another name. Nothing was saved.")
    rule["name"] = old["name"]                                     # the key stays as it was
    if rule["block"] == "states":
        lost = [f"{h} ({state[h][rule['name']].get('state')})" for h in holders
                if state[h][rule["name"]].get("state") not in rule["states"]]
        if lost:
            raise RulesError(f"{rule['name']}: the new rule lacks the states some holders are "
                             f"in: {', '.join(lost)}. Keep those states, or move them first. "
                             f"Nothing was saved.")
    if rule["block"] == "plane":
        import rule_plane
        for holder in holders:
            stored = state[holder][rule["name"]]
            old = stored.get("axes") or {}
            stored["axes"] = {a: max(lo, min(hi, int(old.get(a, rule["start"][a]))))
                              for a, (lo, hi) in rule["axes"].items()}
            stored["on"] = rule_plane.regions_on(rule, stored["axes"])
        return rule
    if rule["block"] == "budget":
        for holder in holders:
            stored = state[holder][rule["name"]]
            if stored.get("split"):
                stored["split"] = {p: n for p, n in stored["split"].items() if p in rule["parts"]}
        return rule
    if rule["block"] == "bag":
        for holder in holders:
            stored = state[holder][rule["name"]]
            old = stored.get("tokens") or {}
            stored["tokens"] = {k: int(old.get(k, n)) for k, n in rule["tokens"].items()}
        return rule
    if rule["block"] != "counter":
        return rule
    low, high = rule["range"]
    for holder in holders:
        stored = state[holder][rule["name"]]
        stored["value"] = max(low, min(high, int(stored.get("value", rule["start"]))))
        stored["on"] = results_on(rule, stored["value"], stored.get("on") or ())
    return rule


def remove(json_ops, raw) -> int:
    """Remove a rule and all its values. Returns how many holders had one."""
    rule = find_rule(json_ops, raw)
    import rule_effects
    using = rule_effects.referring(rules(json_ops), rule["name"])
    if using:
        raise RulesError(f"{rule['name']} is changed by the effects of {', '.join(using)}: "
                         f"change or remove those first.")
    ruleset = _ruleset(json_ops)
    ruleset["rules"] = [r for r in ruleset.get("rules") or [] if r.get("name") != rule["name"]]
    json_ops.save_json(RULESET, ruleset)
    state = load_state(json_ops)
    dropped = 0
    for holder in list(state):
        if state[holder].pop(rule["name"], None) is not None:
            dropped += 1
        if not state[holder]:
            del state[holder]
    save_state(json_ops, state)
    _log(json_ops, "-", rule["name"], "removed, with its values", "command")
    return dropped


def set_plain(json_ops, lines) -> list[str]:
    """Replace the plain rule lines (what is no mechanic: prices, customs)."""
    kept = [" ".join(str(line).split()) for line in lines or [] if str(line).strip()]
    ruleset = _ruleset(json_ops)
    ruleset["plain_rules"] = kept
    json_ops.save_json(RULESET, ruleset)
    return kept


# ---------- holders ----------

def factions(json_ops) -> dict[str, str]:
    """{id: name} of the world bible's factions graph."""
    graph = (json_ops.load_json(BIBLE) or {}).get("factions") or {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    out = {}
    for node in nodes or []:
        if isinstance(node, dict) and str(node.get("id") or "").strip():
            out[str(node["id"]).strip()] = str(node.get("name") or node["id"]).strip()
    return out


def _faction(json_ops, text: str) -> str:
    """'faction:<id>' for a faction's id or name, or ''."""
    low = text.lower()
    for fid, name in factions(json_ops).items():
        if low in (fid.lower(), name.lower()):
            return f"faction:{fid}"
    return ""


def _kinds(rule) -> str:
    words = {"player": "the player", "npc": "NPCs", "faction": "factions",
             "location": "places", "world": "the world"}
    return ", ".join(words[k] for k in rule["held_by"])


def resolve_holder(json_ops, rule: dict[str, Any], raw=None) -> str:
    """The holder `raw` names, as the rule allows it; without `raw`, the player
    or the world when the rule has only that one."""
    held = rule["held_by"]
    text = " ".join(str(raw or "").split())
    if not text:
        if held in (["player"], ["world"]):
            return held[0]
        raise RulesError(f"Whose {rule['name']}? It is held by {_kinds(rule)}: name one, "
                         f"e.g. gm-rule.sh show \"{rule['name']}\" \"<name>\".")
    low = text.lower()
    kind, sep, rest = text.partition(":")
    if low == "world":
        found = "world"
    elif sep and kind.strip().lower() == "faction":
        found = _faction(json_ops, rest.strip())
        if not found:
            known = ", ".join(f"{i} ({n})" for i, n in factions(json_ops).items()) or "none yet"
            raise RulesError(f"No faction '{rest.strip()}' in the world bible's factions: {known}.")
    else:
        from world_ids import WorldIds
        faction = "" if sep else _faction(json_ops, text)
        cid, error = WorldIds(json_ops).resolve(text)
        if faction and cid:
            raise RulesError(f"'{text}' fits several: {faction}, {cid}. Give the kind.")
        found = faction or cid
        if not found:
            raise RulesError(error or f"Nothing called '{text}'.")
    found_kind = found.partition(":")[0]
    if found_kind not in held:
        raise RulesError(f"{rule['name']} is held by {_kinds(rule)}; '{text}' is {found}.")
    return found


def holder_name(json_ops, holder: str) -> str:
    """How a holder is named in the output: the character's name, a faction's name."""
    if holder == "player":
        from sheet import name as sheet_name
        return sheet_name(json_ops.load_json("character.json") or {}) or "the character"
    if holder == "world":
        return "the world"
    kind, _, key = holder.partition(":")
    if kind == "faction":
        return factions(json_ops).get(key, key)
    return key


# ---------- values ----------

def load_state(json_ops) -> dict[str, dict[str, Any]]:
    value = json_ops.load_json(STATE) or {}
    return value if isinstance(value, dict) else {}


def save_state(json_ops, state: dict[str, dict[str, Any]]) -> None:
    json_ops.save_json(STATE, state)


def result_label(result: dict[str, Any]) -> str:
    """'from 2', 'from 2 to 3' or 'at 0': how a result is named in the output and stored in `on`."""
    if result.get("to") == result["from"]:
        return f"at {result['from']}"
    if "to" in result:
        return f"from {result['from']} to {result['to']}"
    return f"from {result['from']}"


def results_on(rule: dict[str, Any], value: int, before=()) -> list[str]:
    """The labels of the counter results that hold at `value`: each from its `from`
    upward (cumulative), or only up to its `to`. One with `off_at` (hysteresis), once
    on (in `before`), stays on until the value falls to its `off_at`."""
    on = []
    for r in rule.get("results") or []:
        label = result_label(r)
        in_range = r["from"] <= value <= r.get("to", value)
        held_on = "off_at" in r and label in before and value > r["off_at"]   # hysteresis
        if in_range or held_on:
            on.append(label)
    return on


def entry(json_ops, rule: dict[str, Any], holder: str, state=None) -> dict[str, Any]:
    """Where `rule` stands for `holder` (the rule's start if nothing is stored)."""
    state = load_state(json_ops) if state is None else state
    stored = (state.get(holder) or {}).get(rule["name"])
    if stored:
        return stored
    if rule["block"] == "states":
        return {"state": rule["start"]}
    if rule["block"] == "plane":
        import rule_plane
        return {"axes": dict(rule["start"]), "on": rule_plane.regions_on(rule, rule["start"])}
    if rule["block"] == "bag":
        return {"tokens": dict(rule["tokens"]), "drawn": []}
    if rule["block"] == "budget":
        return {"spent": False}
    return {"value": rule["start"], "on": results_on(rule, rule["start"])}


def is_known(rule: dict[str, Any], stored: dict[str, Any]) -> bool:
    return bool(stored.get("known", rule.get("known", True)))


def label(rule: dict[str, Any], result: dict[str, Any]) -> str:
    """How a result of `rule` is named, whatever the block."""
    if rule["block"] == "roll":
        import rule_roll
        return rule_roll.label(result, rule["results"])
    if rule["block"] == "plane":
        return result["name"]
    return result_label(result)


def _result(rule, name) -> dict[str, Any]:
    return next(r for r in rule.get("results") or [] if label(rule, r) == name)


def counter(json_ops, raw) -> dict[str, Any]:
    """The rule `raw` names, which must be a counter (it has a value to change)."""
    rule = find_rule(json_ops, raw)
    if rule["block"] != "counter":
        how = {"roll": f'gm-rule.sh roll "{rule["name"]}"',
               "states": f'gm-rule.sh move "{rule["name"]}" [holder] <state>',
               "plane": f'gm-rule.sh change "{rule["name"]}" [holder] --axis <axis> +N|-N',
               "bag": f'gm-rule.sh draw "{rule["name"]}" [holder]',
               "budget": f'gm-rule.sh split "{rule["name"]}" [holder] <part>=N ...'}.get(
            rule["block"], f'gm-rule.sh show "{rule["name"]}"')
        raise RulesError(f"{rule['name']} is a {rule['block']}: it has no value to change ({how}).")
    return rule


def _now_game(json_ops) -> str:
    from game_time import stored_time
    return stored_time(json_ops)


def _log(json_ops, holder: str, rule: str, what: str, cause: str) -> None:
    """One line per change in rules.log: when (real and game time), who, what, why."""
    path = Path(json_ops.world_state_dir) / LOG
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", encoding="utf-8") as log:
        log.write(f"{stamp}\tgame {_now_game(json_ops) or '-'}\t{holder}\t{rule}: {what}\t"
                  f"by {cause}\n")


def change(json_ops, raw_rule, raw_holder=None, by: int | None = None,
           to: int | None = None, cause: str = "command", chain=None,
           axis: str | None = None) -> dict[str, Any]:
    """Change a counter by `by`, or set it `to` a value. A change that goes past the
    range stops at its end; a set outside it is refused. The results it turns on and
    off carry out their effects (rule_effects.py; `chain` is the chain this change is
    part of), then the on_rule consequences fire. Returns what happened:
    {rule, holder, before, after, stopped, on, off, still, known, did, gm, fired,
    character (what changed on the character, for the whole chain)}. A plane moves
    one `axis` (rule_plane.change)."""
    rule = find_rule(json_ops, raw_rule)
    if rule["block"] == "plane":
        import rule_plane
        return rule_plane.change(json_ops, rule, resolve_holder(json_ops, rule, raw_holder),
                                 axis, by=by, to=to, cause=cause, chain=chain)
    if axis is not None:
        raise RulesError(f"{rule['name']} has no axes: --axis is for a plane.")
    rule = counter(json_ops, raw_rule)
    holder = resolve_holder(json_ops, rule, raw_holder)
    low, high = rule["range"]
    state = load_state(json_ops)
    stored = dict(entry(json_ops, rule, holder, state))
    before = int(stored.get("value", rule["start"]))
    if to is not None:
        if not low <= to <= high:
            raise RulesError(f"{rule['name']} goes from {low} to {high}; {to} is outside.")
        after = to
    elif by is not None:
        after = max(low, min(high, before + by))
    else:
        raise RulesError("Say how much: +N or -N, or set a value.")
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
    now = _now_game(json_ops)
    if now:
        stored["since"] = now
    state.setdefault(holder, {})[rule["name"]] = stored
    save_state(json_ops, state)
    path = f"{before} -> {reached} -> {after} (overflow)" if overflow else f"{before} -> {after}"
    _log(json_ops, holder, rule["name"], path, cause)
    report = {"rule": rule["name"], "holder": holder, "before": before, "after": after,
              "stopped": stopped and not overflow, "overflow": overflow,
              "on": [r for r in new_on if r not in old_on],
              "off": [r for r in old_on if r not in new_on],
              "still": [r for r in new_on if r in old_on],
              "known": is_known(rule, stored)}
    import rule_effects
    top = chain is None
    chain = rule_effects.new_chain() if top else chain
    chain["seen"].add((rule["name"], holder))
    report["did"], report["gm"] = {}, {}
    for label, field in [(r, "when_off") for r in report["off"]] + [(r, "effects") for r in report["on"]]:
        result = _result(rule, label)
        done = [rule_effects.run(json_ops, effect, holder, chain,
                                 f"effect of {rule['name']} {label}")
                for effect in result.get(field) or []]
        if done:
            report["did"][label] = done
        if field == "effects" and result.get("gm"):
            report["gm"][label] = result["gm"]
    report["fired"] = rule_effects.fire_on_rule(json_ops, rule["name"], holder, before, reached,
                                                holder_name(json_ops, holder))
    if top:
        report["character"] = list(chain["character"])
    return report


def mark(json_ops, raw_rule, raw_holder, text: str) -> dict[str, Any]:
    """Record the lasting mark an overflow left (the GM picks one of the suggestions,
    or writes one). Returns {rule, holder, mark, marks, at_limit (what happens now,
    when the marks reach the limit, else '')}."""
    rule = counter(json_ops, raw_rule)
    ov = rule.get("overflow")
    if not ov:
        raise RulesError(f"{rule['name']} has no overflow, so it leaves no marks.")
    holder = resolve_holder(json_ops, rule, raw_holder)
    state = load_state(json_ops)
    stored = dict(entry(json_ops, rule, holder, state))
    if int(stored.get("marks_due", 0)) < 1:
        raise RulesError(f"No mark is due: {rule['name']} leaves one each time it reaches "
                         f"{ov['at']}.")
    text = " ".join(str(text or "").split())
    if not text:
        raise RulesError("Say what the mark is, e.g. \"night terrors\".")
    stored["marks"] = list(stored.get("marks") or []) + [text]
    stored["marks_due"] = int(stored["marks_due"]) - 1
    if not stored["marks_due"]:
        del stored["marks_due"]
    state.setdefault(holder, {})[rule["name"]] = stored
    save_state(json_ops, state)
    _log(json_ops, holder, rule["name"], f"mark: {text}", "command")
    at_limit = ov.get("at_limit", "") if ov.get("limit") and len(stored["marks"]) >= ov["limit"] else ""
    return {"rule": rule["name"], "holder": holder, "mark": text, "marks": stored["marks"],
            "at_limit": at_limit}


def break_streak(json_ops, raw_rule, raw_holder=None) -> dict[str, Any]:
    """A failure ends a streak: back to its start."""
    rule = counter(json_ops, raw_rule)
    if not rule.get("streak"):
        raise RulesError(f"{rule['name']} is no streak; to set it back: gm-rule.sh set.")
    return change(json_ops, rule["name"], raw_holder, to=rule["start"], cause="the streak broke")


def set_known(json_ops, raw_rule, raw_holder=None, known: bool = True) -> tuple[str, str]:
    """Make one holder's value known (`reveal`) or hidden (`hide`)."""
    rule = counter(json_ops, raw_rule)
    holder = resolve_holder(json_ops, rule, raw_holder)
    state = load_state(json_ops)
    stored = dict(entry(json_ops, rule, holder, state))
    if known == rule.get("known", True):
        stored.pop("known", None)
    else:
        stored["known"] = known
    state.setdefault(holder, {})[rule["name"]] = stored
    save_state(json_ops, state)
    _log(json_ops, holder, rule["name"], "revealed" if known else "hidden", "command")
    return rule["name"], holder


# ---------- showing ----------

def change_lines(json_ops, report: dict[str, Any], indent: str = "") -> list[str]:
    """A change as the GM reads it: the values, then the results it turned on and off,
    each followed by what its effects did (a change they made, indented under it),
    its line for the GM, the consequences it fired, and at the end of a chain what
    changed on the character."""
    if "axis" in report:
        import rule_plane
        return rule_plane.change_lines(json_ops, report, indent)
    rule = find_rule(json_ops, report["rule"])
    who = holder_name(json_ops, report["holder"])
    top = ""
    if report["stopped"]:
        top = " (its highest)" if report["after"] == rule["range"][1] else " (its lowest)"
    ov = report.get("overflow")
    path = f"{report['before']} → {ov['at']} → {report['after']}" if ov else \
        f"{report['before']} → {report['after']}"
    lines = [f"{indent}{rule['name']} ({who}): {path}{top}"
             + ("" if report["known"] else f"  {HIDDEN}")]
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
            lines += done_lines(json_ops, (report.get("did") or {}).get(name, []), indent)
            if kind == "now on" and (report.get("gm") or {}).get(name):
                lines.append(f"{indent}    Do now: {report['gm'][name]}")
    lines += _fired_lines(report.get("fired"), indent + "  ")
    if report.get("character"):
        lines.append(f"{indent}Changed on the character: {'; '.join(report['character'])}.")
    return lines


def done_lines(json_ops, done: list[dict[str, Any]], indent: str) -> list[str]:
    """What a result's effects did, under it: a change they made (indented, with its
    own results), or a line, and the consequences they fired."""
    lines = []
    for one in done:
        if one.get("report") or one.get("states_report"):
            if one.get("report"):
                nested = change_lines(json_ops, one["report"], indent + "      ")
            else:
                import rule_states
                nested = rule_states.move_lines(json_ops, one["states_report"], indent + "      ")
            nested[0] = f"{indent}    → {nested[0].lstrip()}"
            lines += nested
        if one.get("line"):
            lines.append(f"{indent}    → {one['line']}")
        lines += _fired_lines(one.get("fired"), indent + "    ")
    return lines


def _fired_lines(fired, indent: str) -> list[str]:
    if not fired:
        return []
    from consequence_manager import AFTER_FIRING
    lines = []
    for c in fired:
        lines.append(f"{indent}[REACTIVITY] fired [{c['id']}] {c['consequence']}")
        lines.append(f"{indent}    ↳ fired because: {c.get('match_reason', '')} ({AFTER_FIRING})")
        lines += [f"{indent}    ↳ {line}" for line in c.get("effects_done") or []]
    return lines


def rule_lines(json_ops, rule: dict[str, Any], holders=None) -> list[str]:
    """A rule in full: what it is, its words, its results, and where it stands for
    `holders` (default: every holder with a value, plus the player or the world when
    they hold it)."""
    if rule["block"] == "roll":
        import rule_roll
        return rule_roll.rule_lines(rule)
    if rule["block"] == "states":
        import rule_states
        return rule_states.rule_lines(json_ops, rule, holders)
    if rule["block"] == "plane":
        import rule_plane
        return rule_plane.rule_lines(json_ops, rule, holders)
    if rule["block"] == "bag":
        import rule_bag
        return rule_bag.rule_lines(json_ops, rule, holders)
    if rule["block"] == "budget":
        import rule_budget
        return rule_budget.rule_lines(json_ops, rule, holders)
    low, high = rule["range"]
    hidden = "" if rule.get("known", True) else f"; {HIDDEN}"
    lines = [f"{rule['name']} ({rule['block']} {low}–{high}, held by {_kinds(rule)}{hidden}): "
             f"{rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    lines += _option_lines(rule)
    for result in rule.get("results") or []:
        off = f" (off only at {result['off_at']})" if "off_at" in result else ""
        lines.append(f"  {result_label(result)}{off}: {result['text']}")
    lines.append(command_line(rule))
    state = load_state(json_ops)
    if holders is None:
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    for holder in holders:
        stored = entry(json_ops, rule, holder, state)
        on = ", ".join(stored.get("on") or []) or "no result"
        mark = "" if is_known(rule, stored) else f" {HIDDEN}"
        lines.append(f"  Now, {holder_name(json_ops, holder)}: {stored.get('value')} ({on})"
                     f"{_extras(stored)}{mark}")
    return lines


def _option_lines(rule: dict[str, Any]) -> list[str]:
    """A counter's rate, overflow and streak, in words."""
    lines = []
    if rule.get("rate"):
        import rule_time
        lines.append(f"  Rate: {rule_time.describe(rule['rate'])}, by itself as game time passes.")
    ov = rule.get("overflow")
    if ov:
        marks = f" (e.g. {'; '.join(ov['marks'])})" if ov.get("marks") else ""
        limit = f" At {ov['limit']} marks: {ov['at_limit']}" if ov.get("limit") else ""
        lines.append(f"  Overflow at {ov['at']}: back to {ov['back_to']}, and a lasting mark"
                     f"{marks}.{limit}")
    if rule.get("streak"):
        lines.append(f"  Streak: a failure breaks it (gm-rule.sh break \"{rule['name']}\").")
    return lines


def _extras(stored: dict[str, Any]) -> str:
    """A holder's marks, marks due and own rate, after its value."""
    parts = []
    if stored.get("marks"):
        parts.append(f"marks: {'; '.join(stored['marks'])}")
    if stored.get("marks_due"):
        parts.append(f"{stored['marks_due']} mark due")
    if stored.get("rate"):
        import rule_time
        parts.append(f"its own rate: {rule_time.describe(stored['rate'])}")
    return f"; {', '.join(parts)}" if parts else ""


def command_line(rule: dict[str, Any]) -> str:
    """How the GM changes the rule."""
    holder = "" if rule["held_by"] in (["player"], ["world"]) else ' "<holder>"'
    return f'  Command: gm-rule.sh change "{rule["name"]}"{holder} +N|-N'


def brief_lines(json_ops) -> list[str]:
    """YOUR WORLD'S RULES in the brief: the plain lines, then each rule in full with
    where it stands for the character, the world and the factions. NPCs' and
    places' values are on their cards."""
    lines = [f"- {line}" for line in plain_rules(json_ops)]
    state = load_state(json_ops)
    for rule in rules(json_ops):
        if rule["block"] == "roll":
            lines += rule_lines(json_ops, rule)
            continue
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += sorted(h for h, values in state.items()
                          if h.startswith("faction:") and rule["name"] in values)
        lines += rule_lines(json_ops, rule, holders)
        if {"npc", "location"} & set(rule["held_by"]):
            lines.append(f"  The values of people and places are on their cards "
                         f"(all: gm-rule.sh show \"{rule['name']}\").")
    return lines


def holder_lines(json_ops, holder: str) -> list[str]:
    """The rules a holder has a value of, each on a line with the results on now in
    full: for a person's or a place's card."""
    lines = []
    state = load_state(json_ops)
    for rule in rules(json_ops):
        stored = (state.get(holder) or {}).get(rule["name"])
        if stored and rule["block"] == "plane":
            import rule_plane
            lines.append(rule_plane.holder_line(rule, stored))
            continue
        if stored and rule["block"] == "bag":
            import rule_bag
            lines.append(rule_bag.holder_line(rule, stored))
            continue
        if stored and rule["block"] == "budget":
            import rule_budget
            lines.append(rule_budget.holder_line(rule, stored))
            continue
        if stored and rule["block"] == "states":
            mark = "" if is_known(rule, stored) else f" {HIDDEN}"
            lines.append(f"{rule['name']}: {stored['state']} (states): "
                         f"{rule['states'][stored['state']]['text']}{mark}")
            continue
        if not stored or rule["block"] != "counter":
            continue
        low, high = rule["range"]
        on = [f"{label}: {_result(rule, label)['text']}" for label in stored.get("on") or []]
        mark = "" if is_known(rule, stored) else f" {HIDDEN}"
        lines.append(f"{rule['name']} {stored.get('value')} ({rule['block']} {low}–{high}): "
                     + ("; ".join(on) or "no result") + _extras(stored) + mark)
    return lines


def summary(json_ops, holder: str = "player") -> str:
    """'Bleed 4/6, Stress 2/8 (hidden)': a holder's values on one line, or ''."""
    parts = []
    state = load_state(json_ops)
    for rule in rules(json_ops):
        if holder.partition(":")[0] not in rule["held_by"] or rule["block"] == "roll":
            continue
        stored = entry(json_ops, rule, holder, state)
        if rule["block"] in ("states", "plane", "bag", "budget"):
            import rule_bag
            import rule_budget
            hidden = "" if is_known(rule, stored) else " (hidden)"
            if rule["block"] == "states":
                shown = stored["state"]
            elif rule["block"] == "budget":
                shown = rule_budget.summary(rule, stored)
            elif rule["block"] == "bag":
                shown = rule_bag.contents(stored["tokens"])
            else:
                shown = (", ".join(stored.get("on") or [])
                         or ", ".join(f"{a} {v}" for a, v in stored["axes"].items()))
            parts.append(f"{rule['name']}: {shown}{hidden}")
            continue
        hidden = "" if is_known(rule, stored) else " (hidden)"
        parts.append(f"{rule['name']} {stored.get('value')}/{rule['range'][1]}{hidden}")
    return ", ".join(parts)


def check_values(json_ops, holder: str, given: Any) -> list[tuple[str, Any]]:
    """Starting values {rule: value} for `holder` (`player` at character creation),
    checked: [(rule name, value)], or RulesError."""
    if not given:
        return []
    if not isinstance(given, dict):
        raise RulesError('The rules\' starting values are an object: {"Bleed": 2}.')
    checked = []
    for raw, value in given.items():
        rule = find_rule(json_ops, raw)
        if holder.partition(":")[0] not in rule["held_by"]:
            raise RulesError(f"{rule['name']} is held by {_kinds(rule)}, not by {holder}.")
        if rule["block"] == "states":
            import rule_states
            checked.append((rule["name"], rule_states._find_state(rule, value)))
            continue
        if rule["block"] == "budget":
            raise RulesError(f"{rule['name']} is a budget: it has no starting value (it starts "
                             f"full: gm-rule.sh split).")
        if rule["block"] == "bag":
            if not isinstance(value, dict):
                raise RulesError(f"{rule['name']} is a bag: give its tokens, e.g. "
                                 f"{json.dumps(rule['tokens'])}.")
            import rule_bag
            checked.append((rule["name"], {"tokens": {rule_bag._kind(rule, k): n
                                                      for k, n in value.items()}}))
            continue
        if rule["block"] == "plane":
            import rule_plane
            if not isinstance(value, dict):
                raise RulesError(f"{rule['name']} is a plane: give its axes, e.g. "
                                 f"{json.dumps(rule['start'])}.")
            point = {}
            for axis, number in value.items():
                axis = rule_plane.find_axis(rule, axis)
                low, high = rule["axes"][axis]
                if not _is_int(number) or not low <= number <= high:
                    raise RulesError(f"{rule['name']}'s {axis} goes from {low} to {high}, "
                                     f"not {number!r}.")
                point[axis] = number
            checked.append((rule["name"], point))
            continue
        rule = counter(json_ops, rule["name"])
        low, high = rule["range"]
        if not _is_int(value) or not low <= value <= high:
            raise RulesError(f"{rule['name']} goes from {low} to {high}; {value!r} is not a "
                             f"whole number in it.")
        checked.append((rule["name"], value))
    return checked


def set_values(json_ops, holder: str, checked: list[tuple[str, Any]], cause: str) -> list[dict]:
    """Set values checked by check_values. Returns the reports."""
    import rule_states
    reports = []
    for name, value in checked:
        if isinstance(value, str):
            reports.append(rule_states.move(json_ops, name, holder, value, cause=cause, force=True))
        elif isinstance(value, dict) and "tokens" in value:
            import rule_bag
            reports.append(rule_bag.set_tokens(json_ops, name, holder, value["tokens"], cause))
        elif isinstance(value, dict):
            reports += [change(json_ops, name, holder, to=v, axis=a, cause=cause)
                        for a, v in value.items()]
        else:
            reports.append(change(json_ops, name, holder, to=value, cause=cause))
    return reports


def move_holder(json_ops, old: str, new: str) -> list[str]:
    """Give `old`'s values to `new` (a character hand-over: the outgoing character
    becomes an NPC, a canon NPC becomes the player). Values of rules `new` can't
    hold are dropped. Returns notes for the GM."""
    state = load_state(json_ops)
    values = state.pop(old, None)
    if not values:
        return []
    kind = new.partition(":")[0]
    by_name = {r["name"]: r for r in rules(json_ops)}
    kept = {n: v for n, v in values.items() if n in by_name and kind in by_name[n]["held_by"]}
    dropped = [n for n in values if n not in kept]
    if kept:
        state.setdefault(new, {}).update(kept)
    save_state(json_ops, state)
    for name in values:
        _log(json_ops, old, name, f"moved to {new}" if name in kept else "dropped", "hand-over")
    notes = []
    if dropped:
        notes.append(f"{', '.join(dropped)} can't be held by {kind}s; {old}'s values of "
                     f"them are gone.")
    return notes


# ---------- the command line ----------

def _amount(text: str) -> int:
    if not text or text[0] not in "+-" or not text[1:].isdigit():
        raise RulesError(f"A change is +N or -N (e.g. +1); got '{text}'. To give a value: "
                         f"gm-rule.sh set \"<rule>\" [holder] N.")
    return int(text)


def _rule_and_holder(args: list[str], with_value: bool) -> tuple[str, str | None, str | None]:
    """<rule> [holder] [value] from the words given."""
    need = 2 if with_value else 1
    if len(args) < need or len(args) > need + 1:
        shape = '"<rule>" [holder]' + (" <value>" if with_value else "")
        raise RulesError(f"Give {shape}.")
    value = args[-1] if with_value else None
    rest = args[:-1] if with_value else args
    return rest[0], (rest[1] if len(rest) > 1 else None), value


def emit_bag(json_ops, action: str, words: list[str], json_mode: bool) -> None:
    """gm-rule.sh draw / refill / put / take."""
    import rule_bag
    from cli_output import emit
    if action == "draw":
        count = 1
        if len(words) > 1 and words[-1].isdigit():
            count, words = int(words[-1]), words[:-1]
        name, holder, _ = _rule_and_holder(words, False)
        report = rule_bag.draw(json_ops, name, holder, count)
        emit(report, "\n".join(rule_bag.draw_lines(json_ops, report)), json_mode)
        return
    if action == "refill":
        name, holder, _ = _rule_and_holder(words, False)
        report = rule_bag.refill(json_ops, name, holder)
    else:
        if len(words) < 3 or not words[-1].isdigit():
            raise RulesError(f'Give "<bag>" [holder] <kind> N: gm-rule.sh {action} "The Job" trouble 1.')
        amount = int(words[-1]) * (1 if action == "put" else -1)
        name, holder, kind = _rule_and_holder(words[:-1], True)
        report = rule_bag.put(json_ops, name, holder, kind, amount)
    emit(report, rule_bag.put_line(json_ops, report), json_mode)


def _is_block(json_ops, words, block: str) -> bool:
    try:
        return find_rule(json_ops, words[0])["block"] == block
    except (RulesError, IndexError):
        return False


def _is_states(json_ops, words) -> bool:
    return _is_block(json_ops, words, "states")


def _stdin_text() -> str:
    return "" if sys.stdin.isatty() else sys.stdin.read()


def main() -> int:
    import argparse

    from campaign_manager import CampaignManager
    from cli_output import emit, emit_error, json_input, strip_json_flag, wants_json
    from json_ops import JsonOperations

    json_mode = wants_json()
    parser = argparse.ArgumentParser(description="The world's own rules")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="every rule, and where it stands")
    for action, words in (("show", "<rule> [holder]"),
                          ("change", "<rule> [holder] +N|-N  (a plane: --axis <axis>)"),
                          ("set", "<rule> [holder] N  (a plane: --axis; states: a state)"),
                          ("reveal", "<rule> [holder]"),
                          ("hide", "<rule> [holder]"), ("break", "<rule> [holder]"),
                          ("move", "<rule> [holder] <state>"),
                          ("mark", "<rule> [holder] <the mark>")):
        p = sub.add_parser(action, help=words)
        p.add_argument("words", nargs="+")
        if action in ("change", "set"):
            p.add_argument("--axis")
    p = sub.add_parser("roll", help='<rule> [holder] [--with "<amount>"]...')
    p.add_argument("words", nargs="+")
    p.add_argument("--with", action="append", dest="named", default=[])
    for action, words in (("draw", "<bag> [holder] [N]"), ("refill", "<bag or budget> [holder]"),
                          ("split", "<budget> [holder] <part>=N ..."),
                          ("put", "<bag> [holder] <kind> N"), ("take", "<bag> [holder] <kind> N")):
        sub.add_parser(action, help=words).add_argument("words", nargs="+")
    p = sub.add_parser("rate", help="<rule> [holder] --by N [--every 90d]")
    p.add_argument("words", nargs="+")
    p.add_argument("--by", type=int)
    p.add_argument("--every")
    sub.add_parser("define", help="add or replace rules: the JSON list after the command")
    sub.add_parser("plain", help="the plain rule lines, one per line, after the command")
    sub.add_parser("remove", help="remove a rule and its values").add_argument("rule")
    args = parser.parse_args(strip_json_flag()[1:])

    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        return emit_error("No active campaign.", json_mode)
    ops = JsonOperations(str(campaign))
    try:
        if args.action == "list":
            found = rules(ops)
            lines = [f"- {line}" for line in plain_rules(ops)]
            for rule in found:
                lines += rule_lines(ops, rule)
            emit({"rules": found, "plain_rules": plain_rules(ops), "state": load_state(ops)},
                 "\n".join(lines) or "This campaign has no rules of its own (gm-rule.sh define).",
                 json_mode)
        elif args.action == "show":
            name, holder, _ = _rule_and_holder(args.words, False)
            rule = find_rule(ops, name)
            holders = [resolve_holder(ops, rule, holder)] if holder else None
            emit({"rule": rule, "state": {h: v[rule["name"]] for h, v in load_state(ops).items()
                                          if rule["name"] in v}},
                 "\n".join(rule_lines(ops, rule, holders)), json_mode)
        elif args.action == "move" or (args.action == "set" and _is_states(ops, args.words)):
            import rule_states
            name, holder, value = _rule_and_holder(args.words, True)
            report = rule_states.move(ops, name, holder, value, force=args.action == "set",
                                      cause="command" if args.action == "move" else "set")
            emit(report, "\n".join(rule_states.move_lines(ops, report)), json_mode)
        elif args.action in ("change", "set"):
            name, holder, value = _rule_and_holder(args.words, True)
            if args.action == "change":
                report = change(ops, name, holder, by=_amount(value), axis=args.axis)
            else:
                if not value.lstrip("-").isdigit():
                    raise RulesError(f"A value is a whole number; got '{value}'.")
                report = change(ops, name, holder, to=int(value), axis=args.axis)
            emit(report, "\n".join(change_lines(ops, report)), json_mode)
        elif args.action == "roll":
            import rule_roll
            name, holder, _ = _rule_and_holder(args.words, False)
            report = rule_roll.roll(ops, name, holder, args.named)
            emit(report, "\n".join(rule_roll.roll_lines(ops, report)), json_mode)
        elif args.action == "split" or (args.action == "refill" and _is_block(ops, args.words, "budget")):
            import rule_budget
            words = args.words
            first = [i for i, word in enumerate(words) if "=" in word]
            head = words[:first[0]] if first else words
            name, holder, _ = _rule_and_holder(head, False)
            if args.action == "split":
                report = rule_budget.split(ops, name, holder, words[len(head):])
                emit(report, "\n".join(rule_budget.split_lines(ops, report)), json_mode)
            else:
                report = rule_budget.refill(ops, name, holder)
                emit(report, rule_budget.refill_line(ops, report), json_mode)
        elif args.action in ("draw", "refill", "put", "take"):
            emit_bag(ops, args.action, args.words, json_mode)
        elif args.action == "break":
            name, holder, _ = _rule_and_holder(args.words, False)
            report = break_streak(ops, name, holder)
            emit(report, "\n".join(change_lines(ops, report)), json_mode)
        elif args.action == "mark":
            name, holder, text = _rule_and_holder(args.words, True)
            done = mark(ops, name, holder, text)
            message = f"[SUCCESS] {done['rule']} ({holder_name(ops, done['holder'])}): marks " \
                      f"{'; '.join(done['marks'])}"
            if done["at_limit"]:
                message += f"\nDo now: {done['at_limit']}"
            emit(done, message, json_mode)
        elif args.action == "rate":
            import rule_time
            name, holder, _ = _rule_and_holder(args.words, False)
            if args.by is None and args.every is None:
                raise RulesError("Give the new rate: --by N, and/or --every <time>.")
            old, new = rule_time.set_rate(ops, name, holder, by=args.by, every=args.every)
            rule = find_rule(ops, name)
            who = holder_name(ops, resolve_holder(ops, rule, holder))
            emit({"before": old, "after": new},
                 f"[SUCCESS] {rule['name']} ({who}): rate {rule_time.describe(old)} → "
                 f"{rule_time.describe(new)}", json_mode)
        elif args.action in ("reveal", "hide"):
            name, holder, _ = _rule_and_holder(args.words, False)
            rule, who = set_known(ops, name, holder, known=args.action == "reveal")
            state = "known: the HUD may show it" if args.action == "reveal" else \
                "hidden: the player sees only its signs"
            emit({"rule": rule, "holder": who, "known": args.action == "reveal"},
                 f"[SUCCESS] {rule} ({holder_name(ops, who)}) is {state}.", json_mode)
        elif args.action == "define":
            try:
                given = json_input(None, "the rules")
            except ValueError as error:
                raise RulesError(str(error)) from error
            done = define(ops, given)
            emit({"defined": [{"name": n, "how": h} for n, h in done]},
                 "\n".join(f"[SUCCESS] {n}: {h}" for n, h in done), json_mode)
        elif args.action == "plain":
            kept = set_plain(ops, _stdin_text().splitlines())
            emit({"plain_rules": kept}, f"[SUCCESS] {len(kept)} plain rule lines.", json_mode)
        else:
            name = find_rule(ops, args.rule)["name"]
            dropped = remove(ops, name)
            emit({"removed": name, "values": dropped},
                 f"[SUCCESS] {name} removed, with {dropped} holders' values.", json_mode)
    except RulesError as error:
        return emit_error(str(error), json_mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
