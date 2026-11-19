#!/usr/bin/env python3
"""The repo's own world rules for factions (design-notes.md → "Factions", "Faction
turns and power"): every campaign with factions has them, the same everywhere.

- Power: four counters held by factions, 0 to 10: Military, Economic, Political,
  Covert. A faction acts with one of them, and a contest compares the same power on
  both sides (faction_turns.py).
- Relation: one counter held by a pair of factions (`pair:hardtop+kin`), −5 to +5,
  the same both ways.

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
NAMES = {r["name"].lower() for r in _RULES}


def built_ins(json_ops) -> list[dict[str, Any]]:
    """The repo's faction rules, for a campaign that has factions (factions.json)."""
    import factions
    return copy.deepcopy(_RULES) if factions.has_file(json_ops) else []


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
