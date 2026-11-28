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
    rules.log        every change, with its cause

A rule says who can hold it (`held_by`): the player, NPCs, factions, places or the
world. Each holder has its own value, which starts at the rule's `start` and is
written to rule-state.json once it is set or changes. Holders are written as the
facts write them (player, npc:<key>, location:<key>), plus `faction:<id>` (a faction
of the world bible's factions graph, until factions have records) and `world`.

The building blocks, one module each (the gm-rules skill describes them for the GM):
    counter   one number in a range; results by range, cumulative unless `to` is given;
              options: a rate, hysteresis (`off_at`), overflow (lasting marks), streak
              (rule_counter.py; rates: rule_time.py)
    roll      dice plus named amounts (and a holder's value of a counter), read from a
              list of results; keeps nothing (rule_roll.py)
    states    named states and the moves allowed between them; time can move them on
              (rule_states.py)
    plane     two values read together; results by region (rule_plane.py)
    bag       tokens drawn and added to; the odds are what is in it (rule_bag.py)
    budget    a fixed amount split among named parts, refilled (rule_budget.py)
Results that act, and on_rule: rule_effects.py.

Every block module provides the same names, which this module dispatches to (BLOCKS):
FIELDS, HOLDS (whether it keeps a value per holder), check, default, outcomes,
rule_lines, holder_line, summary, start, set_start, on_redefine, apply_time,
next_time (when time next moves it: time_walk.py), report_lines.

A value is known (the default: the HUD may show it, the narration make it plain) or
hidden (the GM sees it, the player only its signs; every output marks it).

    gm-rule.sh list | show "<rule>" [holder]
    gm-rule.sh change "<rule>" [holder] +N|-N   ·   set "<rule>" [holder] N   (a plane: --axis)
    gm-rule.sh roll "<rule>" [holder] [--with "<amount>"]...
    gm-rule.sh move "<rule>" [holder] <state>   (set: any state, a correction)
    gm-rule.sh draw "<bag>" [holder] [N]   ·   put|take "<bag>" [holder] <kind> N   ·   refill
    gm-rule.sh split "<budget>" [holder] <part>=N ...   ·   refill "<budget>" [holder]
    gm-rule.sh reveal|hide "<rule>" [holder]   ·   break "<rule>" [holder]
    gm-rule.sh mark "<rule>" [holder] "<mark>"   ·   rate "<rule>" [holder] --by N [--every 90d]
    gm-rule.sh define <<'EOF' [...rules...] EOF   ·   plain <<'EOF' lines EOF   ·   remove "<rule>"
"""

import difflib
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

RULESET = "ruleset.json"
STATE = "rule-state.json"
LOG = "rules.log"

HOLDER_KINDS = ("player", "npc", "faction", "location", "world", "pair")   # pair: two factions
STANDING = "Standing"    # how each faction regards the character: every campaign has it,
                         # and scripts read it by this name (design-notes.md, "Factions")
BLOCKS = {"counter": "rule_counter", "roll": "rule_roll", "states": "rule_states",
          "plane": "rule_plane", "bag": "rule_bag", "budget": "rule_budget"}
COMMON_FIELDS = ("name", "block", "held_by", "known", "summary", "when", "notes")
MAX_NAME_WORDS = 3
MAX_NAME_CHARS = 30
HIDDEN = "[HIDDEN: show only its signs]"
# What the GM does with a rule of each block, for refusals that point the way.
HOW = {"counter": 'gm-rule.sh change "{name}" [holder] +N|-N',
       "roll": 'gm-rule.sh roll "{name}"',
       "states": 'gm-rule.sh move "{name}" [holder] <state>',
       "plane": 'gm-rule.sh change "{name}" [holder] --axis <axis> +N|-N',
       "bag": 'gm-rule.sh draw "{name}" [holder]',
       "budget": 'gm-rule.sh split "{name}" [holder] <part>=N ...'}


from rule_errors import RulesError  # noqa: E402  (one class, however this module is imported)


def block(which):
    """The module of a block: a rule, or a block's name."""
    name = which["block"] if isinstance(which, dict) else which
    return importlib.import_module(BLOCKS[name])


# ---------- the rules ----------

def own_rules(json_ops) -> list[dict[str, Any]]:
    """The campaign's own rules, in the order they were defined (ruleset.json)."""
    value = (json_ops.load_json(RULESET) or {}).get("rules") or []
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def rules(json_ops) -> list[dict[str, Any]]:
    """The campaign's own rules, then the repo's faction rules when it has factions
    (faction_rules.py: power, Relation, the faction bag)."""
    import faction_rules
    return own_rules(json_ops) + faction_rules.built_ins(json_ops)


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
    import faction_rules
    if faction_rules.is_built_in(wanted):
        raise RulesError(f"No rule '{raw}' here: it comes with the factions, and this "
                         f"campaign has none yet (gm-faction.sh create).")
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
    """Fields that aren't `allowed`."""
    for field in fields:
        if field not in allowed:
            problems.append(f"unknown field '{field}'{where}; {what} has {', '.join(allowed)}")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_rule(raw: Any) -> dict[str, Any]:
    """A rule as given, checked and tidied; RulesError lists every problem."""
    if not isinstance(raw, dict):
        raise RulesError('A rule is an object: {"name": "...", "block": "counter", ...}.')
    rule = json.loads(json.dumps(raw))                         # a copy, plain JSON
    rule["name"] = _name(rule.get("name"))
    kind = rule.get("block")
    if kind not in BLOCKS:
        raise RulesError(f"{rule['name']}: 'block' must be one of {', '.join(BLOCKS)}, "
                         f"not {kind!r}.")
    problems = []
    _unknown(rule, COMMON_FIELDS + block(kind).FIELDS, "", f"a {kind}", problems)
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
    block(kind).check(rule, problems)
    if rule["name"].lower() == STANDING.lower() and (kind != "counter" or rule.get("held_by") != ["faction"]):
        problems.append(f"{STANDING} is how each faction regards the character, and scripts read "
                        f"it by that name: a counter held by factions (\"held_by\": \"faction\")")
    if problems:
        raise RulesError(f"{rule['name']}: " + "; ".join(problems) + ".")
    return rule


def _ruleset(json_ops) -> dict[str, Any]:
    return json_ops.load_json(RULESET) or {}


def define(json_ops, given: Any) -> list[tuple[str, str]]:
    """Add rules, or replace those of the same name: all or nothing. Returns
    [(name, "added" | "replaced")]. A replaced rule keeps its holders' values (each
    block's on_redefine fits them in); its block can't change while values exist."""
    given = [given] if isinstance(given, dict) else given
    if not isinstance(given, list) or not given:
        raise RulesError("Give the rules as a list: [{\"name\": \"...\", ...}, ...].")
    checked, problems = [], []
    for raw in given:
        try:
            checked.append(check_rule(raw))
        except RulesError as error:
            problems.append(str(error))
    import faction_rules
    problems += [f"{r['name']} is one of the repo's faction rules (faction_rules.py): it "
                 f"can't be defined here; set values with gm-rule.sh set." for r in checked
                 if faction_rules.is_built_in(r["name"])]
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
    rule_effects.check_links(checked + [r for r in have if r["name"].lower() not in new]
                             + faction_rules.built_ins(json_ops), problems)
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
    are fitted to it by its block, or the replacement is refused."""
    holders = [h for h, values in state.items() if old["name"] in values]
    if old.get("block") != rule["block"] and holders:
        raise RulesError(f"{rule['name']} is a {old.get('block')} with values "
                         f"({', '.join(holders)}); it can't become a {rule['block']}. "
                         f"Remove it first (gm-rule.sh remove), or give the new rule "
                         f"another name. Nothing was saved.")
    rule["name"] = old["name"]                                     # the key stays as it was
    lost = []
    for holder in holders:
        why = block(rule).on_redefine(rule, state[holder][rule["name"]])
        if why:
            lost.append(f"{holder} ({why})")
    if lost:
        raise RulesError(f"{rule['name']}: the new rule doesn't fit what some holders have: "
                         f"{', '.join(lost)}. Nothing was saved.")
    return rule


def remove(json_ops, raw) -> int:
    """Remove a rule and all its values. Returns how many holders had one."""
    rule = find_rule(json_ops, raw)
    if rule.get("repo"):
        raise RulesError(f"{rule['name']} is one of the repo's faction rules: it can't be removed.")
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
    """{id: name} of the campaign's factions: factions.json, or for an older campaign
    without it, the world bible's factions graph (factions.py)."""
    import factions as faction_file
    return {fid: str(f.get("name") or fid) for fid, f in faction_file.known(json_ops).items()}


def _faction(json_ops, text: str) -> str:
    """'faction:<id>' for a faction's id, name or alias, or ''."""
    import factions as faction_file
    low = text.lower()
    for fid, f in faction_file.known(json_ops).items():
        if low in [fid.lower(), str(f.get("name") or "").lower(),
                   *(str(a).lower() for a in f.get("aliases") or [])]:
            return f"faction:{fid}"
    return ""


def _kinds(rule) -> str:
    words = {"player": "the player", "npc": "NPCs", "faction": "factions",
             "location": "places", "world": "the world", "pair": "pairs of factions"}
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
    elif "pair" in held and (kind.strip().lower() == "pair" or "+" in text):
        found = _pair(json_ops, rest if kind.strip().lower() == "pair" else text)
    elif sep and kind.strip().lower() == "faction":
        found = _faction(json_ops, rest.strip())
        if not found:
            known = ", ".join(f"{i} ({n})" for i, n in factions(json_ops).items()) or "none yet"
            raise RulesError(f"No faction '{rest.strip()}'. The factions: {known}.")
    else:
        from world_ids import WorldIds
        faction = "" if sep else _faction(json_ops, text)
        cid, error = WorldIds(json_ops).resolve(text)
        if faction and cid and faction != cid:
            raise RulesError(f"'{text}' fits several: {faction}, {cid}. Give the kind.")
        found = faction or cid
        if not found:
            raise RulesError(error or f"Nothing called '{text}'.")
    found_kind = found.partition(":")[0]
    if found_kind not in held:
        raise RulesError(f"{rule['name']} is held by {_kinds(rule)}; '{text}' is {found}.")
    return found


def _pair(json_ops, text: str) -> str:
    """`pair:<a>+<b>` for "kin+hardtop", "The Kin + Hardtop Holdings", "faction:kin+…"."""
    import faction_rules
    sides = [s.strip() for s in text.split("+")]
    if len(sides) != 2 or not all(sides):
        raise RulesError(f"A pair of factions is written \"pair:<one>+<other>\" (\"pair:kin+"
                         f"hardtop\"); got '{text}'.")
    found = []
    for side in sides:
        bare = side.partition(":")[2] if side.lower().startswith("faction:") else side
        fid = _faction(json_ops, bare)
        if not fid:
            known = ", ".join(f"{i} ({n})" for i, n in factions(json_ops).items()) or "none yet"
            raise RulesError(f"No faction '{bare}'. The factions: {known}.")
        found.append(fid.partition(":")[2])
    if found[0] == found[1]:
        raise RulesError(f"A pair is two factions, not {found[0]} twice.")
    return faction_rules.pair_id(*found)


def holder_name(json_ops, holder: str) -> str:
    """How a holder is named in the output: the character's name, a faction's name,
    an NPC's name, "the street", "everyone". Without json_ops, by the keys."""
    if holder == "player":
        from sheet import name as sheet_name
        found = sheet_name(json_ops.load_json("character.json") or {}) if json_ops else ""
        return found or "the character"
    words = {"world": "the world", "street": "the street", "public": "everyone"}
    if holder in words:
        return words[holder]
    kind, _, key = holder.partition(":")
    names = factions(json_ops) if json_ops and kind in ("faction", "pair") else {}
    if kind == "faction":
        return names.get(key, key)
    if kind == "pair":
        import faction_rules
        a, b = faction_rules.pair_sides(holder)
        return f"{names.get(a, a)} and {names.get(b, b)}"
    return key or holder


# ---------- values ----------

def load_state(json_ops) -> dict[str, dict[str, Any]]:
    value = json_ops.load_json(STATE) or {}
    return value if isinstance(value, dict) else {}


def save_state(json_ops, state: dict[str, dict[str, Any]]) -> None:
    json_ops.save_json(STATE, state)


def holders_of(json_ops, rule: dict[str, Any], state=None) -> list[str]:
    """Who has a value of `rule`: the player and the world when they hold it (their
    value exists from the start), then every other holder with a stored value."""
    state = load_state(json_ops) if state is None else state
    holders = [h for h in ("player", "world") if h in rule["held_by"]]
    return holders + [h for h, values in state.items() if rule["name"] in values and h not in holders]


def entry(json_ops, rule: dict[str, Any], holder: str, state=None) -> dict[str, Any]:
    """Where `rule` stands for `holder` (the block's default if nothing is stored)."""
    state = load_state(json_ops) if state is None else state
    stored = (state.get(holder) or {}).get(rule["name"])
    return stored if stored else block(rule).default(rule)


def is_known(rule: dict[str, Any], stored: dict[str, Any]) -> bool:
    return bool(stored.get("known", rule.get("known", True)))


def counter(json_ops, raw) -> dict[str, Any]:
    """The rule `raw` names, which must be a counter (it has a value to change)."""
    rule = find_rule(json_ops, raw)
    if rule["block"] != "counter":
        how = HOW[rule["block"]].format(name=rule["name"])
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
    """Change a counter by `by`, or set it `to` a value (rule_counter.change); a plane
    moves one `axis` (rule_plane.change). The results it turns on and off carry out
    their effects, then the on_rule consequences fire."""
    rule = find_rule(json_ops, raw_rule)
    if rule["block"] == "plane":
        import rule_plane
        return rule_plane.change(json_ops, rule, resolve_holder(json_ops, rule, raw_holder),
                                 axis, by=by, to=to, cause=cause, chain=chain)
    if axis is not None:
        raise RulesError(f"{rule['name']} has no axes: --axis is for a plane.")
    rule = counter(json_ops, raw_rule)
    import rule_counter
    return rule_counter.change(json_ops, rule, resolve_holder(json_ops, rule, raw_holder),
                               by=by, to=to, cause=cause, chain=chain)


def mark(json_ops, raw_rule, raw_holder, text: str) -> dict[str, Any]:
    """Record the lasting mark an overflow left (rule_counter.mark)."""
    import rule_counter
    rule = counter(json_ops, raw_rule)
    return rule_counter.mark(json_ops, rule, resolve_holder(json_ops, rule, raw_holder), text)


def break_streak(json_ops, raw_rule, raw_holder=None) -> dict[str, Any]:
    """A failure ends a streak: back to its start."""
    rule = counter(json_ops, raw_rule)
    if not rule.get("streak"):
        raise RulesError(f"{rule['name']} is no streak; to set it back: gm-rule.sh set.")
    return change(json_ops, rule["name"], raw_holder, to=rule["start"], cause="the streak broke")


def set_known(json_ops, raw_rule, raw_holder=None, known: bool = True) -> tuple[str, str]:
    """Make one holder's value known (`reveal`) or hidden (`hide`)."""
    rule = find_rule(json_ops, raw_rule)
    if not block(rule).HOLDS:
        raise RulesError(f"{rule['name']} is a {rule['block']}: it keeps no value to hide.")
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
    """A change as the GM reads it (a counter's or a plane's)."""
    which = "rule_plane" if "axis" in report else "rule_counter"
    return importlib.import_module(which).change_lines(json_ops, report, indent)


def report_lines(json_ops, report: dict[str, Any]) -> list[str]:
    """Any block's report (from a time step), as the GM reads it."""
    return block(find_rule(json_ops, report["rule"])).report_lines(json_ops, report)


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
    from consequence_manager import fired_lines
    return [line for c in fired or [] for line in fired_lines(c, indent)]


def rule_lines(json_ops, rule: dict[str, Any], holders=None) -> list[str]:
    """A rule in full: what it is, its words, its outcomes, its command, and where it
    stands for `holders` (default: every holder with a value, plus the player or the
    world when they hold it)."""
    return block(rule).rule_lines(json_ops, rule, holders)


def has_effect(stored: dict[str, Any]) -> bool:
    """Whether a holder's value does anything now. A rule with results keeps the
    ones on (`on`): none is the neutral value, whatever the number. Rules without
    results (states, bag, budget) always count."""
    return "on" not in stored or bool(stored["on"])


def brief_lines(json_ops) -> list[str]:
    """YOUR WORLD'S RULES in the brief: the plain lines, then each rule in full with
    where it stands for the character, the world and the factions, those whose value
    does something (has_effect; gm-rule.sh show has them all). NPCs' and places'
    values are on their cards."""
    lines = [f"- {line}" for line in plain_rules(json_ops)]
    state = load_state(json_ops)
    for rule in rules(json_ops):
        if rule.get("repo"):                  # power and Relation: on the faction cards
            continue
        if not block(rule).HOLDS:
            lines += rule_lines(json_ops, rule)
            continue
        holders = [h for h in ("player", "world") if h in rule["held_by"]]
        holders += sorted(h for h, values in state.items()
                          if h.startswith("faction:") and rule["name"] in values)
        holders = [h for h in holders if has_effect(entry(json_ops, rule, h, state))]
        lines += rule_lines(json_ops, rule, holders)
        if {"npc", "location"} & set(rule["held_by"]):
            lines.append(f"  The values of people and places are on their cards "
                         f"(all: gm-rule.sh show \"{rule['name']}\").")
    return lines


def holder_lines(json_ops, holder: str) -> list[str]:
    """The rules a holder has a value of, a line each with what is on now in full: for
    a person's or a place's card."""
    state = load_state(json_ops)
    return [block(rule).holder_line(rule, stored) for rule in rules(json_ops)
            if (stored := (state.get(holder) or {}).get(rule["name"])) and block(rule).HOLDS
            and not rule.get("repo")]         # power and Relation: faction_rules.card_lines


def summary(json_ops, holder: str = "player") -> str:
    """'Bleed 4/6, Addiction: hooked (hidden)': a holder's values on one line, or ''."""
    parts = []
    state = load_state(json_ops)
    for rule in rules(json_ops):
        if holder.partition(":")[0] not in rule["held_by"] or not block(rule).HOLDS:
            continue
        stored = entry(json_ops, rule, holder, state)
        hidden = "" if is_known(rule, stored) else " (hidden)"
        parts.append(block(rule).summary(rule, stored) + hidden)
    return ", ".join(parts)


def check_values(json_ops, holder: str, given: Any) -> list[tuple[str, Any]]:
    """Starting values {rule: value} for `holder` (`player` at character creation),
    each checked by its block: [(rule name, value)], or RulesError."""
    if not given:
        return []
    if not isinstance(given, dict):
        raise RulesError('The rules\' starting values are an object: {"Bleed": 2}.')
    checked = []
    for raw, value in given.items():
        rule = find_rule(json_ops, raw)
        if holder.partition(":")[0] not in rule["held_by"]:
            raise RulesError(f"{rule['name']} is held by {_kinds(rule)}, not by {holder}.")
        checked.append((rule["name"], block(rule).start(json_ops, rule, value)))
    return checked


def set_values(json_ops, holder: str, checked: list[tuple[str, Any]], cause: str) -> list[dict]:
    """Set values checked by check_values. Returns the reports."""
    reports = []
    for name, value in checked:
        rule = find_rule(json_ops, name)
        reports += block(rule).set_start(json_ops, rule, holder, value, cause)
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


def _block_of(json_ops, words) -> str:
    try:
        return find_rule(json_ops, words[0])["block"]
    except (RulesError, IndexError):
        return ""


def _stdin_text() -> str:
    return "" if sys.stdin.isatty() else sys.stdin.read()


def _cmd_list(ops, args):
    found = rules(ops)
    lines = [f"- {line}" for line in plain_rules(ops)]
    for rule in found:
        lines += rule_lines(ops, rule)
    return ({"rules": found, "plain_rules": plain_rules(ops), "state": load_state(ops)},
            "\n".join(lines) or "This campaign has no rules of its own (gm-rule.sh define).")


def _cmd_show(ops, args):
    name, holder, _ = _rule_and_holder(args.words, False)
    rule = find_rule(ops, name)
    holders = [resolve_holder(ops, rule, holder)] if holder else None
    return ({"rule": rule, "state": {h: v[rule["name"]] for h, v in load_state(ops).items()
                                     if rule["name"] in v}},
            "\n".join(rule_lines(ops, rule, holders)))


def _cmd_change(ops, args):
    if args.action == "set" and _block_of(ops, args.words) == "states":
        return _cmd_move(ops, args)
    name, holder, value = _rule_and_holder(args.words, True)
    if args.action == "change":
        report = change(ops, name, holder, by=_amount(value), axis=args.axis)
    else:
        if not value.lstrip("-").isdigit():
            raise RulesError(f"A value is a whole number; got '{value}'.")
        report = change(ops, name, holder, to=int(value), axis=args.axis)
    return report, "\n".join(change_lines(ops, report))


def _cmd_move(ops, args):
    import rule_states
    name, holder, value = _rule_and_holder(args.words, True)
    report = rule_states.move(ops, name, holder, value, force=args.action == "set",
                              cause="command" if args.action == "move" else "set")
    return report, "\n".join(rule_states.move_lines(ops, report))


def _cmd_roll(ops, args):
    import rule_roll
    name, holder, _ = _rule_and_holder(args.words, False)
    report = rule_roll.roll(ops, name, holder, args.named)
    return report, "\n".join(rule_roll.roll_lines(ops, report))


def _cmd_split(ops, args):
    import rule_budget
    words = args.words
    first = [i for i, word in enumerate(words) if "=" in word]
    head = words[:first[0]] if first else words
    name, holder, _ = _rule_and_holder(head, False)
    report = rule_budget.split(ops, name, holder, words[len(head):])
    return report, "\n".join(rule_budget.split_lines(ops, report))


def _cmd_refill(ops, args):
    name, holder, _ = _rule_and_holder(args.words, False)
    if _block_of(ops, args.words) == "budget":
        import rule_budget
        report = rule_budget.refill(ops, name, holder)
        return report, rule_budget.refill_line(ops, report)
    import rule_bag
    report = rule_bag.refill(ops, name, holder)
    return report, rule_bag.put_line(ops, report)


def _cmd_draw(ops, args):
    import rule_bag
    words, count = args.words, 1
    if len(words) > 1 and words[-1].isdigit():
        count, words = int(words[-1]), words[:-1]
    name, holder, _ = _rule_and_holder(words, False)
    report = rule_bag.draw(ops, name, holder, count)
    return report, "\n".join(rule_bag.draw_lines(ops, report))


def _cmd_put(ops, args):
    import rule_bag
    words = args.words
    if len(words) < 3 or not words[-1].isdigit():
        raise RulesError(f'Give "<bag>" [holder] <kind> N: gm-rule.sh {args.action} "The Job" trouble 1.')
    amount = int(words[-1]) * (1 if args.action == "put" else -1)
    name, holder, kind = _rule_and_holder(words[:-1], True)
    report = rule_bag.put(ops, name, holder, kind, amount)
    return report, rule_bag.put_line(ops, report)


def _cmd_break(ops, args):
    name, holder, _ = _rule_and_holder(args.words, False)
    report = break_streak(ops, name, holder)
    return report, "\n".join(change_lines(ops, report))


def _cmd_mark(ops, args):
    name, holder, text = _rule_and_holder(args.words, True)
    done = mark(ops, name, holder, text)
    message = f"[SUCCESS] {done['rule']} ({holder_name(ops, done['holder'])}): marks " \
              f"{'; '.join(done['marks'])}"
    if done["at_limit"]:
        message += f"\nDo now: {done['at_limit']}"
    return done, message


def _cmd_rate(ops, args):
    import rule_time
    name, holder, _ = _rule_and_holder(args.words, False)
    if args.by is None and args.every is None and args.toward is None and args.shift is None:
        raise RulesError("Give the new rate: --by N, --every <time>, --toward N or --shift N.")
    old, new = rule_time.set_rate(ops, name, holder, by=args.by, every=args.every,
                                  toward=args.toward, shift=args.shift)
    rule = find_rule(ops, name)
    who = holder_name(ops, resolve_holder(ops, rule, holder))
    return ({"before": old, "after": new},
            f"[SUCCESS] {rule['name']} ({who}): rate {rule_time.describe(old, rule['name'])} → "
            f"{rule_time.describe(new, rule['name'])}")


def _cmd_known(ops, args):
    name, holder, _ = _rule_and_holder(args.words, False)
    rule, who = set_known(ops, name, holder, known=args.action == "reveal")
    state = "known: the HUD may show it" if args.action == "reveal" else \
        "hidden: the player sees only its signs"
    return ({"rule": rule, "holder": who, "known": args.action == "reveal"},
            f"[SUCCESS] {rule} ({holder_name(ops, who)}) is {state}.")


def _cmd_define(ops, args):
    from cli_output import json_input
    try:
        given = json_input(None, "the rules")
    except ValueError as error:
        raise RulesError(str(error)) from error
    done = define(ops, given)
    return ({"defined": [{"name": n, "how": h} for n, h in done]},
            "\n".join(f"[SUCCESS] {n}: {h}" for n, h in done))


def _cmd_plain(ops, args):
    kept = set_plain(ops, _stdin_text().splitlines())
    return {"plain_rules": kept}, f"[SUCCESS] {len(kept)} plain rule lines."


def _cmd_remove(ops, args):
    name = find_rule(ops, args.rule)["name"]
    dropped = remove(ops, name)
    return ({"removed": name, "values": dropped},
            f"[SUCCESS] {name} removed, with {dropped} holders' values.")


COMMANDS = {"list": _cmd_list, "show": _cmd_show, "change": _cmd_change, "set": _cmd_change,
            "move": _cmd_move, "roll": _cmd_roll, "split": _cmd_split, "refill": _cmd_refill,
            "draw": _cmd_draw, "put": _cmd_put, "take": _cmd_put, "break": _cmd_break,
            "mark": _cmd_mark, "rate": _cmd_rate, "reveal": _cmd_known, "hide": _cmd_known,
            "define": _cmd_define, "plain": _cmd_plain, "remove": _cmd_remove}


def _parser():
    import argparse
    parser = argparse.ArgumentParser(description="The world's own rules")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="every rule, and where it stands")
    for action, words in (("show", "<rule> [holder]"),
                          ("change", "<rule> [holder] +N|-N  (a plane: --axis <axis>)"),
                          ("set", "<rule> [holder] N  (a plane: --axis; states: a state)"),
                          ("reveal", "<rule> [holder]"), ("hide", "<rule> [holder]"),
                          ("break", "<rule> [holder]"), ("move", "<rule> [holder] <state>"),
                          ("mark", "<rule> [holder] <the mark>"),
                          ("draw", "<bag> [holder] [N]"), ("refill", "<bag or budget> [holder]"),
                          ("split", "<budget> [holder] <part>=N ..."),
                          ("put", "<bag> [holder] <kind> N"), ("take", "<bag> [holder] <kind> N")):
        p = sub.add_parser(action, help=words)
        p.add_argument("words", nargs="+")
        if action in ("change", "set"):
            p.add_argument("--axis")
    p = sub.add_parser("roll", help='<rule> [holder] [--with "<amount>"]...')
    p.add_argument("words", nargs="+")
    p.add_argument("--with", action="append", dest="named", default=[])
    p = sub.add_parser("rate", help="<rule> [holder] --by N [--every 90d] [--toward N | --shift N]")
    p.add_argument("words", nargs="+")
    p.add_argument("--by", type=int)
    p.add_argument("--every")
    point = p.add_mutually_exclusive_group()
    point.add_argument("--toward", type=int, help="this holder's own point")
    point.add_argument("--shift", type=int, help="move this holder's point by N")
    sub.add_parser("define", help="add or replace rules: the JSON list after the command")
    sub.add_parser("plain", help="the plain rule lines, one per line, after the command")
    sub.add_parser("remove", help="remove a rule and its values").add_argument("rule")
    return parser


def _parse(argv=None):
    """The command line, with the words on either side of an option: the brief prints
    `change "<rule>" --axis <axis> +N`, and argparse alone takes only the words before
    `--axis` and refuses the rest."""
    parser = _parser()
    args, rest = parser.parse_known_args(argv)
    if rest and hasattr(args, "words") and not any(r.startswith("--") for r in rest):
        args.words += rest
    elif rest:
        parser.error(f"unrecognized arguments: {' '.join(rest)}")
    return args


def main() -> int:
    from campaign_manager import CampaignManager
    from cli_output import emit_error
    from json_ops import JsonOperations

    args = _parse()
    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        return emit_error("No active campaign.")
    ops = JsonOperations(str(campaign))
    try:
        data, message = COMMANDS[args.action](ops, args)
    except RulesError as error:
        return emit_error(str(error))
    if message:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
