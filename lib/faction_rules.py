#!/usr/bin/env python3
"""The repo's own world rules for factions (design-notes.md → "Factions", "Faction
turns and power"): every campaign with factions has them, the same everywhere.

- Power: four counters held by factions, 0 to 10: Military, Economic, Political,
  Covert. A faction acts with one of them, and a contest compares the same power on
  both sides (faction_turns.py).
- Relation: one counter held by a pair of factions (`pair:hardtop+kin`), −5 to +5,
  the same both ways.
- Faction turns: a bag held by the world that drives the factions as game time
  passes (design-notes.md, "The faction bag"). It holds 4 tokens per faction, 2
  blanks per faction and a joker; one is drawn every 6 h + 25 h ÷ the number of
  factions, without replacement; with fewer than 4 tokens per faction left it gets
  one per faction, half as many blanks and a joker if it has none. A drawn faction
  token is owed: that faction takes a turn at the next pause (`gm-faction.sh turn
  --only`); a joker owes a full turn. Its tokens and pace follow the factions there
  are now.

They are world rules like any other (values in rule-state.json, `gm-rule.sh change`,
`set`, `rate --toward`, `on_rule`, `--rule-effect`), but defined here, not in the
campaign's ruleset: they can't be defined or removed there. Their rate holds by
default (`by` 0); a faction or a pair gets its own drift and resting point with
`gm-rule.sh rate "<rule>" <holder> --by 1 --toward N`. They show on the faction cards,
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
BLANK, JOKER = "blank", "joker"            # the bag's other kinds: no faction may take these ids
NAMES = {r["name"].lower() for r in _RULES} | {BAG.lower()}


def bag_rule(table: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The faction bag for these factions ({id: record})."""
    n = len(table)
    minutes = round((6 + 25 / n) * 60)
    results = {fid: {"text": f"{row.get('name', fid)} takes a turn.", "owed": True}
               for fid, row in table.items()}
    results[BLANK] = {"text": "Nothing stirs."}
    results[JOKER] = {"text": "Every faction takes a turn at once.", "owed": True}
    return {"name": BAG, "block": "bag", "held_by": ["world"], "known": False,
            "tokens": {**dict.fromkeys(table, 4), BLANK: 2 * n, JOKER: 1},
            "draw": "keep out", "draw_every": f"{minutes}m", "results": results,
            "top_up": {"below": 4 * n, "add": {**dict.fromkeys(table, 1), BLANK: n // 2},
                       "if_none": [JOKER]},
            "summary": "Who of the factions acts next: a drawn faction owes a turn, a joker a "
                       "turn for all, a blank nothing.",
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


def card_lines(json_ops, fid: str) -> list[str]:
    """'power (hidden from the player): Military 6, …' and 'relations: …' for a card."""
    import factions
    names = factions.known(json_ops)
    lines = ["power (0–10, hidden from the player): "
             + ", ".join(f"{k} {v}" for k, v in power(json_ops, fid).items())]
    rel = relations(json_ops, fid)
    if rel:
        lines.append("relations (−5 war … +5 allies): " + ", ".join(
            f"{names.get(o, {}).get('name', o)} {v:+d}" for o, v in sorted(rel.items(), key=lambda x: x[1])))
    return lines
