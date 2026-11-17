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
    counter   one number in a range; results by range, cumulative unless `to` is given
    roll, plane, bag, budget, states: later steps

A value is known (the default: the HUD may show it, the narration make it plain) or
hidden (the GM sees it, the player only its signs; every output marks it).

    gm-rule.sh list | show "<rule>" [holder]
    gm-rule.sh change "<rule>" [holder] +N|-N   ·   set "<rule>" [holder] N
    gm-rule.sh reveal|hide "<rule>" [holder]
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
BLOCKS = ("counter",)
LATER_BLOCKS = {"roll": 4, "states": 6, "plane": 7, "bag": 8, "budget": 9}
COMMON_FIELDS = ("name", "block", "held_by", "known", "summary", "when", "notes")
BLOCK_FIELDS = {"counter": ("range", "start", "results")}
RESULT_FIELDS = {"counter": ("from", "to", "text", "effects", "when_off", "gm")}
LATER_FIELDS = {"rate": 5, "overflow": 5, "streak": 5,
                "off_at": 5}
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
    low, high = rule["range"]
    for holder in holders:
        stored = state[holder][rule["name"]]
        stored["value"] = max(low, min(high, int(stored.get("value", rule["start"]))))
        stored["on"] = results_on(rule, stored["value"])
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


def results_on(rule: dict[str, Any], value: int) -> list[str]:
    """The labels of the counter results that hold at `value`: each from its `from`
    upward (cumulative), or only up to its `to`."""
    return [result_label(r) for r in rule.get("results") or []
            if r["from"] <= value and value <= r.get("to", value)]


def entry(json_ops, rule: dict[str, Any], holder: str, state=None) -> dict[str, Any]:
    """Where `rule` stands for `holder` (the rule's start if nothing is stored)."""
    state = load_state(json_ops) if state is None else state
    stored = (state.get(holder) or {}).get(rule["name"])
    if stored:
        return stored
    return {"value": rule["start"], "on": results_on(rule, rule["start"])}


def is_known(rule: dict[str, Any], stored: dict[str, Any]) -> bool:
    return bool(stored.get("known", rule.get("known", True)))


def _result(rule, label) -> dict[str, Any]:
    return next(r for r in rule.get("results") or [] if result_label(r) == label)


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
           to: int | None = None, cause: str = "command", chain=None) -> dict[str, Any]:
    """Change a counter by `by`, or set it `to` a value. A change that goes past the
    range stops at its end; a set outside it is refused. The results it turns on and
    off carry out their effects (rule_effects.py; `chain` is the chain this change is
    part of), then the on_rule consequences fire. Returns what happened:
    {rule, holder, before, after, stopped, on, off, still, known, did, gm, fired,
    character (what changed on the character, for the whole chain)}."""
    rule = find_rule(json_ops, raw_rule)
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
    old_on = list(stored.get("on") or results_on(rule, before))
    new_on = results_on(rule, after)
    stored.update(value=after, on=new_on)
    now = _now_game(json_ops)
    if now:
        stored["since"] = now
    state.setdefault(holder, {})[rule["name"]] = stored
    save_state(json_ops, state)
    _log(json_ops, holder, rule["name"], f"{before} -> {after}", cause)
    report = {"rule": rule["name"], "holder": holder, "before": before, "after": after,
              "stopped": by is not None and before + by != after,
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
    report["fired"] = rule_effects.fire_on_rule(json_ops, rule["name"], holder, before, after,
                                                holder_name(json_ops, holder))
    if top:
        report["character"] = list(chain["character"])
    return report


def set_known(json_ops, raw_rule, raw_holder=None, known: bool = True) -> tuple[str, str]:
    """Make one holder's value known (`reveal`) or hidden (`hide`)."""
    rule = find_rule(json_ops, raw_rule)
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
    rule = find_rule(json_ops, report["rule"])
    who = holder_name(json_ops, report["holder"])
    top = ""
    if report["stopped"]:
        top = " (its highest)" if report["after"] == rule["range"][1] else " (its lowest)"
    lines = [f"{indent}{rule['name']} ({who}): {report['before']} → {report['after']}{top}"
             + ("" if report["known"] else f"  {HIDDEN}")]
    for kind, labels in (("now on", report["on"]), ("now off", report["off"]),
                         ("still on", report["still"])):
        for label in labels:
            lines.append(f"{indent}  {kind + ':':9s} {label}: {_result(rule, label)['text']}")
            for done in (report.get("did") or {}).get(label, []):
                if done.get("report"):
                    nested = change_lines(json_ops, done["report"], indent + "      ")
                    nested[0] = f"{indent}    → {nested[0].lstrip()}"
                    lines += nested
                if done.get("line"):
                    lines.append(f"{indent}    → {done['line']}")
                lines += _fired_lines(done.get("fired"), indent + "    ")
            if kind == "now on" and (report.get("gm") or {}).get(label):
                lines.append(f"{indent}    Do now: {report['gm'][label]}")
    lines += _fired_lines(report.get("fired"), indent + "  ")
    if report.get("character"):
        lines.append(f"{indent}Changed on the character: {'; '.join(report['character'])}.")
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
    low, high = rule["range"]
    hidden = "" if rule.get("known", True) else f"; {HIDDEN}"
    lines = [f"{rule['name']} ({rule['block']} {low}–{high}, held by {_kinds(rule)}{hidden}): "
             f"{rule['summary']}",
             f"  When: {rule['when']}"]
    if rule.get("notes"):
        lines.append(f"  Notes: {rule['notes']}")
    for result in rule.get("results") or []:
        lines.append(f"  {result_label(result)}: {result['text']}")
    lines.append(command_line(rule))
    state = load_state(json_ops)
    if holders is None:
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += [h for h, values in state.items() if rule["name"] in values and h not in holders]
    for holder in holders:
        stored = entry(json_ops, rule, holder, state)
        on = ", ".join(stored.get("on") or []) or "no result"
        mark = "" if is_known(rule, stored) else f" {HIDDEN}"
        lines.append(f"  Now, {holder_name(json_ops, holder)}: {stored.get('value')} ({on}){mark}")
    return lines


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
        if not stored:
            continue
        low, high = rule["range"]
        on = [f"{label}: {_result(rule, label)['text']}" for label in stored.get("on") or []]
        mark = "" if is_known(rule, stored) else f" {HIDDEN}"
        lines.append(f"{rule['name']} {stored.get('value')} ({rule['block']} {low}–{high}): "
                     + ("; ".join(on) or "no result") + mark)
    return lines


def summary(json_ops, holder: str = "player") -> str:
    """'Bleed 4/6, Stress 2/8 (hidden)': a holder's values on one line, or ''."""
    parts = []
    state = load_state(json_ops)
    for rule in rules(json_ops):
        if holder.partition(":")[0] not in rule["held_by"]:
            continue
        stored = entry(json_ops, rule, holder, state)
        hidden = "" if is_known(rule, stored) else " (hidden)"
        parts.append(f"{rule['name']} {stored.get('value')}/{rule['range'][1]}{hidden}")
    return ", ".join(parts)


def check_values(json_ops, holder: str, given: Any) -> list[tuple[str, int]]:
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
        low, high = rule["range"]
        if not _is_int(value) or not low <= value <= high:
            raise RulesError(f"{rule['name']} goes from {low} to {high}; {value!r} is not a "
                             f"whole number in it.")
        checked.append((rule["name"], value))
    return checked


def set_values(json_ops, holder: str, checked: list[tuple[str, int]], cause: str) -> list[dict]:
    """Set values checked by check_values. Returns the reports."""
    return [change(json_ops, name, holder, to=value, cause=cause) for name, value in checked]


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
    for action, words in (("show", "<rule> [holder]"), ("change", "<rule> [holder] +N|-N"),
                          ("set", "<rule> [holder] N"), ("reveal", "<rule> [holder]"),
                          ("hide", "<rule> [holder]")):
        sub.add_parser(action, help=words).add_argument("words", nargs="+")
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
        elif args.action in ("change", "set"):
            name, holder, value = _rule_and_holder(args.words, True)
            if args.action == "change":
                report = change(ops, name, holder, by=_amount(value))
            else:
                if not value.lstrip("-").isdigit():
                    raise RulesError(f"A value is a whole number; got '{value}'.")
                report = change(ops, name, holder, to=int(value))
            emit(report, "\n".join(change_lines(ops, report)), json_mode)
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
