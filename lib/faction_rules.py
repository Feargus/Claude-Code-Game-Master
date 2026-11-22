#!/usr/bin/env python3
"""The repo's own world rules for factions (design-notes.md → "Factions", "Faction
turns and power"): every campaign with factions has them, the same everywhere.

- Power: four counters held by factions, 0 to 10: Military, Economic, Political,
  Covert. A faction acts with one of them, and a contest compares the same power on
  both sides (faction_turns.py).
- Relation: one counter held by a pair of factions (`pair:hardtop+kin`), −5 to +5,
  the same both ways.
- Faction turns: a bag held by the world that drives the factions as game time
  passes (design-notes.md, "The faction bag"). Per faction it holds 3 tokens of its
  own, 1 job token (`job:<id>`) and 2 blanks; the character's people have a
  faction's share too, 4 `people` tokens and 2 blanks; and there is a joker. One is
  drawn every 6 h + 25 h ÷ the number of factions, without replacement; with fewer
  than 4 tokens per faction and the people left it gets one of each faction's, one
  people, half as many blanks, and a joker and a faction's job token if it has none
  left. Every drawn token but a blank is owed, played at the next pause: a faction
  token a turn (`gm-faction.sh turn --only`), a job token a job offered to the
  character (`gm-faction.sh job offer`), a people token an ask (`gm-faction.sh ask`,
  faction_jobs.py), a joker a full turn. Its tokens and pace follow the factions
  there are now.

They are world rules like any other (values in rule-state.json, `gm-rule.sh change`,
`set`, `rate --toward`, `on_rule`, `--rule-effect`), but defined here, not in the
campaign's ruleset: they can't be defined or removed there. A power's rate holds by
default (`by` 0); a faction gets its own drift and resting point with
`gm-rule.sh rate "<power>" faction:<id> --by 1 --toward N`. A Relation always drifts
toward its resting point by itself (`drift`, below), so only its point is set:
`gm-rule.sh rate "Relation" <a>+<b> --toward N`. They show on the faction cards,
not in the brief's YOUR WORLD'S RULES.
"""

import copy
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

POWERS = ("Military", "Economic", "Political", "Covert")
RELATION = "Relation"
_HOLD = {"by": 0, "every": "28d"}          # held; a holder's own rate gives drift

_FLAVOUR = {
    "Military": "armed force: fighters, guns, guards, the will to use them",
    "Economic": "money and trade: shops, wages, contracts, what can be bought",
    "Political": "standing and persuasion: allies, officials, votes, permits, the crowd",
    "Covert": "the quiet work: informants, spies, thieves, blackmail, planted lies",
}

_RULES = [
    {"name": name, "block": "counter", "held_by": ["faction"], "known": False,
     "range": [0, 10], "start": 3, "results": [],
     "rate": {**_HOLD, "toward": 3},
     "summary": f"A faction's {name.lower()} power: {_FLAVOUR[name]}.",
     "when": "A faction turn (gm-faction.sh turn); a strike, a theft or a deal that hits it.",
     "repo": True}
    for name in POWERS
] + [
    {"name": RELATION, "block": "counter", "held_by": ["pair"], "known": False,
     "range": [-5, 5], "start": 0, "results": [],
     "rate": {**_HOLD, "toward": 0},
     "summary": "How two factions stand with each other, the same both ways: "
                "−5 open war, 0 nothing between them, +5 allies.",
     "when": "One faction harms, helps or deals with another.",
     "repo": True},
]
BAG = "Faction turns"
BLANK, JOKER, PEOPLE = "blank", "joker", "people"   # the bag's other kinds: no faction may take these ids
JOB = "job:"                               # a faction's job token: "job:<id>"
OWN_TOKENS, JOB_TOKENS, BLANKS = 3, 1, 2   # per faction, and per the people (4 people tokens)


def job_kind(fid: str) -> str:
    return f"{JOB}{fid}"


def job_faction(kind: str) -> str:
    """The faction of a job token, or ''."""
    return kind[len(JOB):] if kind.startswith(JOB) else ""
NAMES = {r["name"].lower() for r in _RULES} | {BAG.lower()}


def bag_rule(table: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The faction bag for these factions ({id: record})."""
    n = len(table)
    minutes = round((6 + 25 / n) * 60)
    results = {fid: {"text": f"{row.get('name', fid)} takes a turn.", "owed": True}
               for fid, row in table.items()}
    results.update({job_kind(fid): {"text": f"{row.get('name', fid)} has a job for the character.",
                                    "owed": True} for fid, row in table.items()})
    results[PEOPLE] = {"text": "Someone the character knows wants something of them.", "owed": True}
    results[BLANK] = {"text": "Nothing stirs."}
    results[JOKER] = {"text": "Every faction takes a turn at once.", "owed": True}
    jobs = [job_kind(fid) for fid in table]
    return {"name": BAG, "block": "bag", "held_by": ["world"], "known": False,
            "tokens": {**dict.fromkeys(table, OWN_TOKENS), **dict.fromkeys(jobs, JOB_TOKENS),
                       PEOPLE: OWN_TOKENS + JOB_TOKENS, BLANK: BLANKS * (n + 1), JOKER: 1},
            "draw": "keep out", "draw_every": f"{minutes}m", "results": results,
            "top_up": {"below": 4 * (n + 1),
                       "add": {**dict.fromkeys(table, 1), PEOPLE: 1, BLANK: (n + 1) // 2},
                       "if_none": [JOKER, *jobs]},
            "summary": "Who acts next: a drawn faction owes a turn, its job token a job offered "
                       "to the character, a people token an ask from someone the character "
                       "knows, a joker a turn for all, a blank nothing.",
            "when": "By itself as game time passes; play what is owed at the next pause.",
            "repo": True}


def built_ins(json_ops) -> list[dict[str, Any]]:
    """The repo's faction rules, for a campaign that has factions (factions.json)."""
    import factions
    if not factions.has_file(json_ops):
        return []
    table = factions.load(json_ops)
    return copy.deepcopy(_RULES) + ([bag_rule(table)] if table else [])


# ---------- what is owed ----------

def owed(json_ops) -> list[dict[str, str]]:
    """The faction turns drawn and not played yet, oldest first."""
    import rule_bag
    import world_rules
    try:
        return rule_bag.owed(json_ops, BAG, "world")
    except world_rules.RulesError:
        return []


def settle(json_ops, kind: str) -> dict[str, str] | None:
    """A faction (or the joker) has played the turn it was owed: the oldest one goes."""
    import rule_bag
    import world_rules
    try:
        return rule_bag.settle(json_ops, BAG, "world", kind)
    except world_rules.RulesError:
        return None


def owed_lines(json_ops) -> list[str]:
    """For the pauses: who owes a turn, and how to play it."""
    import factions
    queue = owed(json_ops)
    if not queue:
        return []
    names = factions.known(json_ops)
    when = lambda o: o["at"].replace("T", " ") if o.get("at") else "?"    # noqa: E731
    lines = [f"FACTION TURNS OWED ({len(queue)}; the world goes on: play them now, oldest first):"]
    for o in queue:
        if o["kind"] == JOKER:
            lines.append(f"  joker, drawn {when(o)}: every faction acts: bash tools/gm-faction.sh turn")
        elif o["kind"] == PEOPLE:
            lines.append(f"  an ask, drawn {when(o)}: someone the character knows wants "
                         f"something: bash tools/gm-faction.sh ask")
        elif job_faction(o["kind"]):
            fid = job_faction(o["kind"])
            name = names.get(fid, {}).get("name", fid)
            lines.append(f"  {name}'s job, drawn {when(o)}: offer the character a complex action "
                         f"for its plot, with a deadline: bash tools/gm-faction.sh job offer {fid} "
                         f"(the JSON after it: the action as in a turn, \"due\", \"how\")")
        else:
            name = names.get(o["kind"], {}).get("name", o["kind"])
            lines.append(f"  {name}, drawn {when(o)}: bash tools/gm-faction.sh turn --only {o['kind']}")
    return lines


def is_built_in(name: str) -> bool:
    return " ".join(str(name or "").split()).lower() in NAMES


# ---------- pairs ----------

def pair_id(a: str, b: str) -> str:
    """`pair:<a>+<b>`, the ids sorted: the same pair whichever is named first."""
    return "pair:" + "+".join(sorted((a, b)))


def pair_sides(holder: str) -> tuple[str, str]:
    a, _, b = holder.partition(":")[2].partition("+")
    return a, b


# ---------- reading ----------

def power(json_ops, fid: str) -> dict[str, int]:
    """{power: value} of a faction (a value never set is the rule's start)."""
    import world_rules
    state = world_rules.load_state(json_ops)
    return {name: world_rules.entry(json_ops, world_rules.find_rule(json_ops, name),
                                    f"faction:{fid}", state).get("value")
            for name in POWERS}


def relations(json_ops, fid: str) -> dict[str, int]:
    """{other faction id: value} of the pairs with a value written."""
    import world_rules
    out = {}
    for holder, values in world_rules.load_state(json_ops).items():
        if holder.startswith("pair:") and RELATION in values and fid in pair_sides(holder):
            a, b = pair_sides(holder)
            out[b if a == fid else a] = values[RELATION].get("value")
    return out


def relation(json_ops, a: str, b: str) -> int:
    import world_rules
    rule = world_rules.find_rule(json_ops, RELATION)
    return world_rules.entry(json_ops, rule, pair_id(a, b)).get("value")


def ties_without_relation(json_ops) -> list[tuple[str, str]]:
    """Pairs of factions with a tie (either side's) but no Relation written: unset
    is not 0 (a value chosen), so the opening names them (opening.py)."""
    import factions
    import world_rules
    state = world_rules.load_state(json_ops)
    missing = set()
    for fid, record in factions.known(json_ops).items():
        for other in (record.get("ties") or {}):
            if RELATION not in state.get(pair_id(fid, other), {}):
                missing.add(tuple(sorted((fid, other))))
    return sorted(missing)


def card_lines(json_ops, fid: str) -> list[str]:
    """'power (hidden from the player): Military 6, …' and 'relations: …' for a card."""
    import factions
    names = factions.known(json_ops)
    lines = ["power (0–10, hidden from the player): "
             + ", ".join(f"{k} {v}" for k, v in power(json_ops, fid).items())]
    rel = relations(json_ops, fid)
    ties = (names.get(fid) or {}).get("ties") or {}
    others = sorted(set(rel) | set(ties), key=lambda o: (rel.get(o, 0), o))
    if others:                                 # a tie with no Relation written: "not set", not 0
        lines.append("relations (−5 war … +5 allies; why, as they see it): " + "; ".join(
            f"{names.get(o, {}).get('name', o)} "
            + (f"{rel[o]:+d}" if rel.get(o) is not None else "not set")
            + (f" ({ties[o]})" if ties.get(o) else "") for o in others))
    return lines


# ---------- relations: a decimal value, and the drift (decided 2026-11-21) ----------
#
# A Relation is a whole number like every counter (results, the log, gm-rule.sh), but
# moves in fractions: a faction turn adds 0.8, the drift a little at every time step.
# The decimal value is kept beside it (`exact`); the whole number follows its
# rounding through world_rules.change, so the log and on_rule consequences work as
# for any change. A change by hand (gm-rule.sh) wins: an `exact` that no longer
# rounds to the value is dropped.

RELAX_DAYS = 30          # the drift's time constant: R → R0 + (R − R0)·e^(−Δt/τ)


def drift_words(point) -> str:
    """How a Relation moves by itself, in words (rule_time.describe)."""
    import math
    half = round(RELAX_DAYS * math.log(2))
    return (f"drifts toward {point:+d}" if isinstance(point, int) else f"drifts toward {point}") \
        + f" by itself (the distance halves in about {half} days)"


def _whole(x: float) -> int:
    """Rounded half away from zero, so +0.5 and −0.5 are alike."""
    import math
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def relation_exact(json_ops, holder: str) -> float:
    """The decimal value of a pair's Relation (`pair:<a>+<b>`)."""
    import world_rules
    stored = world_rules.entry(json_ops, world_rules.find_rule(json_ops, RELATION), holder)
    value = int(stored.get("value", 0))
    exact = stored.get("exact")
    return float(exact) if isinstance(exact, (int, float)) and _whole(exact) == value else float(value)


def _resting(json_ops, holder: str) -> int:
    import rule_time
    import world_rules
    rule = world_rules.find_rule(json_ops, RELATION)
    rate = rule_time.rate_of(rule, world_rules.entry(json_ops, rule, holder)) or {}
    return int(rate.get("toward", 0) or 0)


def set_relation(json_ops, holder: str, exact: float, cause: str) -> dict[str, Any] | None:
    """Give a pair's Relation a new decimal value (kept within −5..5). Returns the
    whole number's change report when it moved, else None."""
    import world_rules
    rule = world_rules.find_rule(json_ops, RELATION)
    low, high = rule["range"]
    exact = max(low, min(high, float(exact)))
    value = int(world_rules.entry(json_ops, rule, holder).get("value", rule["start"]))
    report = None
    if _whole(exact) != value:
        report = world_rules.change(json_ops, RELATION, holder, by=_whole(exact) - value, cause=cause)
    state = world_rules.load_state(json_ops)
    stored = dict(world_rules.entry(json_ops, rule, holder, state))
    stored["exact"] = exact
    state.setdefault(holder, {})[RELATION] = stored
    world_rules.save_state(json_ops, state)
    return report


def add_relation(json_ops, a: str, b: str, by: float, cause: str) -> tuple[float, float]:
    """Move the Relation of factions `a` and `b` by `by` (a fraction is fine).
    Returns (before, after), decimal."""
    holder = pair_id(a, b)
    before = relation_exact(json_ops, holder)
    set_relation(json_ops, holder, before + by, cause)
    return before, relation_exact(json_ops, holder)


def drift(json_ops, before, after) -> list[dict[str, Any]]:
    """Every pair's Relation relaxes toward its resting point for the time passed:
    R0 + (R − R0)·e^(−Δt/τ), τ = RELAX_DAYS. Returns the change reports of the whole
    numbers that moved."""
    import math

    import world_rules
    if before is None or after <= before:
        return []
    try:
        world_rules.find_rule(json_ops, RELATION)
    except world_rules.RulesError:
        return []                                  # no factions here
    factor = math.exp(-(after - before).total_seconds() / 86400 / RELAX_DAYS)
    reports = []
    for holder, values in world_rules.load_state(json_ops).items():
        if not holder.startswith("pair:") or RELATION not in values:
            continue
        now, point = relation_exact(json_ops, holder), _resting(json_ops, holder)
        if now == point:
            continue
        report = set_relation(json_ops, holder, point + (now - point) * factor,
                              f"drift toward {point:+d}")
        if report:
            reports.append(report)
    return reports
