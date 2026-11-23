#!/usr/bin/env python3
"""A faction turn (design-notes.md → "Factions", "Faction turns and power").

The GM plays the factions, the script referees. In `/gm world` the GM writes one
action for each faction, mostly from its current plot, and gives them all at once:

    bash tools/gm-faction.sh turn <<'EOF'
    [{"faction": "kin", "action": "build", "power": "Political", "note": "door to door"},
     {"faction": "hardtop", "action": "push", "power": "Economic", "rival": "kin",
      "at": "Culvert Street"},
     {"faction": "almanac", "action": "deal", "power": "Political", "rival": "kin"}]
    EOF

Every action is judged from the state at the start of the turn; the script rolls them
all, then applies every change together, so nobody gains by acting first. A defender
acts only through its power in the roll.

Simple actions (numbers only, never a cost):
    build      +1 power on d6 1-3, +2 on 4-5, +3 on 6
    reinforce  +1 presence at a place (or 1 at a new one), +2 on 5-6; at most 5
    push       a rival's presence there: margin -3 or worse nothing, -2..+2 -1, +3 -2
Complex actions (the GM records their facts and narrates what leaves a trace; they
cost 2 of the power used, 3 if they fail; a margin below 0 fails). One that succeeds
for the faction's plot moves its plan clock one segment (decided 2026-11-20, in place
of Prepare and Enact): it counts for the faction's own open plot, or the one named in
"plot", and for none with "plot": "none". A full plan clock fires its consequence,
the plan's success, like any clock's.
    strike     a rival's presence there: 0..+1 -1, +2..+3 -2, +4 or better -3
    seize      a named asset of the rival, or a place: 0..+2 own +1 and rival -1, +3 ±2
    take       kidnap, arrest, blackmail someone ("who"); against the faction that
               protects them, or nobody (the world: d6 + 2)
    spy        learn a fact the rival holds
    expose     push a fact about the rival up the ladder
    deal       a pact, truce or bribe with another faction

A full turn needs an action from every faction. `--only <faction>`: that one faction
takes its turn and nobody else (a turn drawn for
one faction, later from a bag of tokens).

The contest: d6 + the actor's power against d6 + the rival's same power; the
difference is the margin.
"""

import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

SIMPLE = ("build", "reinforce", "push")
COMPLEX = ("strike", "seize", "take", "spy", "expose", "deal")
NAMES = {"build": "Build up", "reinforce": "Reinforce", "push": "Push back",
         "strike": "Strike", "seize": "Seize", "take": "Take someone", "spy": "Spy",
         "expose": "Expose", "deal": "Deal"}
NO_PLOT = "none"        # "plot": "none": a complex action that isn't for the faction's plot
FIELDS = ("faction", "action", "power", "rival", "at", "asset", "who", "plot", "note")
NEEDS_RIVAL = ("push", "strike", "seize", "spy", "expose", "deal")   # take: optional
NEEDS_PLACE = ("reinforce", "push", "strike")
COST, COST_FAILED = 2, 3
WORLD = 2               # what a take against nobody in particular rolls against (d6 + 2)
BUILD = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3}
PUSH = [(-99, 0), (-2, 1), (3, 2)]
STRIKE = [(-99, None), (0, 1), (2, 2), (4, 3)]
SEIZE = [(-99, None), (0, 1), (3, 2)]
MAX_PRESENCE = 5


class TurnError(ValueError):
    """A turn that can't be played. The message lists every problem; nothing changed."""


def band(margin: int, table) -> int | None:
    return [v for lo, v in table if margin >= lo][-1]


# ---------- checking ----------

def check(json_ops, actions: Any) -> list[dict[str, Any]]:
    """The actions, checked and made canonical (ids, names); TurnError lists every
    problem at once."""
    if isinstance(actions, dict):
        actions = [actions]
    if not isinstance(actions, list) or not actions:
        raise TurnError('A turn is a list of actions: [{"faction": "<id>", "action": "build", '
                        '"power": "Military"}, ...], one per faction.')
    from factions import FactionManager, from_bible, has_file
    if not has_file(json_ops):
        raise TurnError("This campaign's factions are still in its world bible: bash tools/"
                        "gm-faction.sh from-bible copies them into factions.json, which brings "
                        "their power and the faction bag." if from_bible(json_ops) else
                        "This campaign has no factions yet (gm-faction.sh create).")
    m = FactionManager(json_ops)
    problems, out, seen = [], [], set()
    for i, raw in enumerate(actions, 1):
        where = f"action {i}"
        try:
            a = _check_one(json_ops, m, raw, where)
        except (TurnError, ValueError) as error:
            problems.append(str(error))
            continue
        if a["faction"] in seen:
            problems.append(f"{where}: {a['faction']} acts twice; one action per faction a turn.")
        seen.add(a["faction"])
        out.append(a)
    if problems:
        raise TurnError(" ".join(problems) + " Nothing was changed.")
    return out


def _check_one(json_ops, m, raw, where) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TurnError(f"{where}: an action is an object with \"faction\" and \"action\".")
    unknown = [k for k in raw if k not in FIELDS]
    if unknown:
        raise TurnError(f"{where}: no field {', '.join(unknown)} (fields: {', '.join(FIELDS)}).")
    a = {k: v for k, v in raw.items() if v not in (None, "")}
    a["faction"] = m.key(a.get("faction"))
    kind = str(a.get("action", "")).strip().lower()
    if kind not in SIMPLE + COMPLEX:
        raise TurnError(f"{where}: the action is one of {', '.join(SIMPLE + COMPLEX)}, not '{kind}'.")
    a["action"] = kind
    who = f"{where} ({a['faction']}, {kind})"
    a["power"] = _power(a.get("power"), who)
    _check_rival(m, a, who)
    _check_target(json_ops, m, a, who)
    if kind in SIMPLE and "plot" in a:
        raise TurnError(f"{who}: only a complex action moves a plot; leave out \"plot\".")
    if kind in COMPLEX:
        a["plot"], a["clock"] = _plan(json_ops, a, who)
        import faction_rules
        have = faction_rules.power(json_ops, a["faction"])[a["power"]]
        if have < COST:
            raise TurnError(f"{who}: it costs {COST} {a['power']} power, and "
                            f"{a['faction']} has {have}.")
    return a


def _check_rival(m, a, who) -> None:
    if a["action"] in NEEDS_RIVAL and "rival" not in a:
        raise TurnError(f"{who}: name the rival (\"rival\": \"<faction>\").")
    if "rival" in a:
        a["rival"] = m.key(a["rival"])
        if a["rival"] == a["faction"]:
            raise TurnError(f"{who}: a faction is not its own rival.")


def _check_target(json_ops, m, a, who) -> None:
    """Where (a place), what (an asset) or whom (a person) the action is aimed at."""
    kind = a["action"]
    if kind in NEEDS_PLACE or (kind == "seize" and "asset" not in a):
        a["at"] = _place(m, a.get("at"), who)
        if kind != "reinforce":
            _rival_there(json_ops, a, who)
    if kind == "seize" and "asset" in a:
        a["asset"] = _asset(json_ops, a, who)
    if kind == "take":
        cid, error = m._ids().resolve_as(str(a.get("who") or ""), ("npc",))
        if error:
            raise TurnError(f"{who}: \"who\" is taken? {error}")
        a["who"] = cid


def _power(raw, who) -> str:
    import faction_rules
    found = next((p for p in faction_rules.POWERS if p.lower() == str(raw or "").strip().lower()), None)
    if found is None:
        raise TurnError(f"{who}: \"power\" is one of {', '.join(faction_rules.POWERS)}.")
    return found


def _place(m, raw, who) -> str:
    cid, error = m._ids().resolve_as(str(raw or ""), ("location",))
    if error:
        raise TurnError(f"{who}: \"at\" names the place. {error}")
    return cid.partition(":")[2]


def _rival_there(json_ops, a, who) -> None:
    from factions import presence
    if presence(json_ops, a["at"]).get(a["rival"], 0) < 1:
        raise TurnError(f"{who}: {a['rival']} has no presence at {a['at']} to take from.")


def _asset(json_ops, a, who) -> str:
    from factions import load
    assets = load(json_ops)[a["rival"]].get("assets") or []
    found = next((x["name"] for x in assets if x["name"].lower() == str(a["asset"]).lower()), None)
    if found is None:
        raise TurnError(f"{who}: {a['rival']} has no asset '{a['asset']}' (it has: "
                        f"{', '.join(x['name'] for x in assets) or 'none'}).")
    return found


def _plan(json_ops, a, who) -> tuple[str | None, str | None]:
    """The plot a complex action is for, and its plan clock (an event clock of the
    plot that isn't full): (None, None) for "plot": "none" or a faction with no open
    plot of its own; (plot, None) for a plot with no plan clock left to move."""
    from plot_manager import plot_order, resolve_plots
    plots = json_ops.load_json("plots.json") or {}
    if str(a.get("plot", "")).strip().lower() == NO_PLOT:
        return None, None
    if a.get("plot"):
        keys, errors = resolve_plots(json_ops, [a["plot"]])
        if errors:
            raise TurnError(f"{who}: {errors[0]}")
        key = keys[0]
    else:
        owned = [k for k in plot_order(json_ops, plots)
                 if plots[k].get("owner") == f"faction:{a['faction']}"
                 and plots[k].get("status", "open") == "open"]
        if not owned:
            return None, None
        if len(owned) > 1:
            raise TurnError(f"{who}: which plot is it for? {a['faction']} has {len(owned)} open "
                            f"plots of its own: {', '.join(owned)}; give \"plot\" (or "
                            f"\"plot\": \"{NO_PLOT}\").")
        key = owned[0]
    clocks = json_ops.load_json("threat-clocks.json") or {}
    fit = [n for n, c in clocks.items() if isinstance(c, dict) and key in (c.get("plots") or [])
           and c.get("advance_on") == "event"
           and int(c.get("current", 0)) < int(c.get("max", 1))]
    return key, (fit[0] if fit else None)


# ---------- resolving ----------

def resolve(json_ops, actions: list[dict[str, Any]], rng=None) -> list[dict[str, Any]]:
    """Roll every action against the state at the start of the turn. Each gets
    "dice", "margin" (contested), "effect" (a number, or None for a failure)."""
    import faction_rules
    rng = rng or random.Random()
    d6 = lambda: rng.randint(1, 6)    # noqa: E731
    power = {fid: faction_rules.power(json_ops, fid) for fid in {a["faction"] for a in actions}
             | {a["rival"] for a in actions if "rival" in a}}
    out = []
    for a in actions:
        r = dict(a)
        kind = a["action"]
        if kind == "build":
            r["dice"] = [d6()]
            r["effect"] = BUILD[r["dice"][0]]
        elif kind == "reinforce":
            r["dice"] = [d6()]
            r["effect"] = 2 if r["dice"][0] >= 5 else 1
        else:
            mine, theirs = d6(), d6()
            against = power[a["rival"]][a["power"]] if "rival" in a else WORLD
            r["dice"], r["against"] = [mine, theirs], against
            r["own"] = power[a["faction"]][a["power"]]
            r["margin"] = mine + r["own"] - (theirs + against)
            table = {"push": PUSH, "strike": STRIKE, "seize": SEIZE}.get(kind)
            r["effect"] = band(r["margin"], table) if table else (1 if r["margin"] >= 0 else None)
        out.append(r)
    return out


# ---------- applying ----------

def apply(json_ops, results: list[dict[str, Any]]) -> list[str]:
    """Carry out every result together; the lines for the GM."""
    powers, places = _deltas(results)
    relations = _relation_deltas(json_ops, results, places)     # from the state at the start
    changed_powers = _apply_powers(json_ops, powers)
    changed_places = _apply_places(json_ops, places)
    changed_relations = _apply_relations(json_ops, relations)
    for r in results:
        if r["action"] in COMPLEX and r["effect"] is not None and r.get("clock"):
            r["clock_after"] = _advance(json_ops, r)
        if r["action"] == "seize" and "asset" in r and r["effect"]:
            _move_asset(json_ops, r)
    lines = ["FACTION TURN (contests: d6 + power against d6 + the rival's same power)"]
    for r in results:
        lines += _lines(json_ops, r, changed_powers, changed_places)
    lines += _relation_lines(json_ops, changed_relations)
    return lines


# ---------- relations (decided 2026-11-21) ----------
#
# A hostile action that succeeds costs the Relation of the two factions 1 (a push,
# strike or seizure against the rival, a kidnapping of someone it protects, an
# exposure; a spy who is caught); a deal that succeeds gains 1. Taking presence from a
# rival at a place also moves how the others there see the one who did it:
#     ΔR(A, C) = L · (P_C / 5) · (1/2 − R(C, B) / 5)
# L the presence B lost, P_C C's presence there, R(C, B) how C stands with B: B's
# enemies are pleased, neutrals a little (order restored), B's real friends sour.

HOSTILE = ("push", "strike", "seize", "take", "expose")
DEAL_GAIN, HOSTILE_COST = 1, -1


def _relation_deltas(json_ops, results, places) -> dict[tuple[str, str], float]:
    """{(a, b): change} for every pair this turn moves, judged from the state at the
    start of the turn (before `places`, the presence changes, are applied)."""
    import faction_rules
    import factions
    out: dict[tuple[str, str], float] = {}

    def add(a, b, by):
        if a != b and by:
            key = tuple(sorted((a, b)))
            out[key] = out.get(key, 0.0) + by

    for r in results:
        kind, fid, rival = r["action"], r["faction"], r.get("rival")
        if not rival:
            continue
        if kind == "deal" and r["effect"] is not None:
            add(fid, rival, DEAL_GAIN)
        elif (kind in HOSTILE and r["effect"]) or (kind == "spy" and r["effect"] is None):
            add(fid, rival, HOSTILE_COST)
        if kind in ("push", "strike", "seize") and r["effect"] and "at" in r:
            here = factions.presence(json_ops, r["at"])
            lost = min(here.get(rival, 0), int(r["effect"]))
            for other, p in here.items():
                if other in (fid, rival) or p <= 0 or lost <= 0:
                    continue
                weight = 0.5 - faction_rules.relation_exact(
                    json_ops, faction_rules.pair_id(other, rival)) / 5
                add(fid, other, lost * p / 5 * weight)
    return out


def _apply_relations(json_ops, deltas) -> dict[tuple[str, str], tuple[float, float]]:
    import faction_rules
    return {(a, b): faction_rules.add_relation(json_ops, a, b, by, "a faction turn")
            for (a, b), by in deltas.items()}


def _relation_lines(json_ops, changed) -> list[str]:
    if not changed:
        return []
    import factions
    names = factions.known(json_ops)
    name = lambda f: names.get(f, {}).get("name", f)     # noqa: E731
    return ["Relations (−5 war … +5 allies, kept to two decimals; hidden from the player):"] + [
        f"  {name(a)} and {name(b)}: {before:+.2f} → {after:+.2f}"
        for (a, b), (before, after) in sorted(changed.items())]


def _deltas(results) -> tuple[dict, dict]:
    """The sums of all changes: {(faction, power): N}, {(place, faction): N}."""
    powers: dict[tuple[str, str], int] = {}
    places: dict[tuple[str, str], int] = {}

    def add(table, key, by):
        table[key] = table.get(key, 0) + by

    for r in results:
        kind, fid, effect = r["action"], r["faction"], r["effect"]
        if kind == "build":
            add(powers, (fid, r["power"]), effect)
        if kind in COMPLEX:
            r["cost"] = COST if effect is not None else COST_FAILED
            add(powers, (fid, r["power"]), -r["cost"])
        if not effect or "at" not in r:
            continue
        if kind in ("reinforce", "seize"):
            add(places, (r["at"], fid), effect)
        if kind in ("push", "strike", "seize"):
            add(places, (r["at"], r["rival"]), -effect)
    return powers, places


def _apply_powers(json_ops, deltas) -> dict[tuple[str, str], tuple[int, int, list]]:
    import world_rules
    done = {}
    for (fid, name), by in deltas.items():
        if by:
            report = world_rules.change(json_ops, name, f"faction:{fid}", by=by, cause="a faction turn")
            done[(fid, name)] = (report["before"], report["after"], report.get("fired") or [])
    return done


def _apply_places(json_ops, deltas) -> dict[tuple[str, str], tuple[int, int]]:
    import factions
    places = json_ops.load_json("locations.json") or {}
    done = {}
    for (place, fid), by in deltas.items():
        here = factions.presence(json_ops, place)
        before = here.get(fid, 0)
        after = max(0, min(MAX_PRESENCE, before + by))
        here[fid] = after
        places[place]["presence"] = dict(sorted(here.items(), key=lambda x: -x[1]))
        json_ops.save_json("locations.json", places)
        done[(place, fid)] = (before, after)
    return done


def _lines(json_ops, r, powers, places) -> list[str]:
    import factions
    from consequence_manager import AFTER_FIRING
    names = factions.known(json_ops)
    name = lambda f: names.get(f, {}).get("name", f)     # noqa: E731
    kind, fid = r["action"], r["faction"]
    head = f"{name(fid)}: {NAMES[kind]}" + (f" ({r['power']})" if "power" in r else "")
    if "rival" in r:
        head += f" against {name(r['rival'])}"
    if r.get("at"):
        head += f" at {r['at']}"
    if r.get("note"):
        head += f" ({r['note']})"
    if "margin" in r:
        head += (f": {r['dice'][0]}+{r['own']} against {r['dice'][1]}+{r['against']}"
                 + ("" if "rival" in r else " (the world)") + f", margin {r['margin']:+d}")
    elif r.get("dice"):
        head += f": d6 {r['dice'][0]}"
    lines = [head]
    more = _what(r, name, powers, places, json_ops)
    if kind in COMPLEX:
        more = _plan_lines(r) + more
    lines += [f"  → {line}" for line in more]
    if r.get("at") and r["at"] == _here(json_ops):
        lines.append(f"  HERE: {_character(json_ops)} is at {r['at']} and sees it happen: narrate "
                     f"what shows (patrols arriving, a shop shut, smoke, a fight in the street).")
    for (f, p), (before, after, fired) in powers.items():
        if f == fid and p == r.get("power") and kind in COMPLEX + ("build",):
            lines.append(f"  {possessive(name(f))} {p}: {before} → {after}")
            lines += [f"  {c['id']} {c['consequence']} ({AFTER_FIRING})" for c in fired]
    return lines


def possessive(name: str) -> str:
    """"Hardtop's", "The Afters'"."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def _here(json_ops) -> str:
    pos = (json_ops.load_json("campaign-overview.json") or {}).get("player_position") or {}
    return pos.get("current_location", "") if isinstance(pos, dict) else ""


def _character(json_ops) -> str:
    from sheet import name
    return name(json_ops.load_json("character.json") or {}) or "the character"


def _what(r, name, powers, places, json_ops) -> list[str]:
    kind = r["action"]
    if kind == "build":
        return [f"{r['power']} +{r['effect']}"]
    if kind in ("reinforce", "push", "strike", "seize") and "at" in r and r["effect"]:
        who = r["faction"] if kind == "reinforce" else r["rival"]
        before, after = places[(r["at"], who)]
        out = [f"{possessive(name(who))} presence at {r['at']}: {before} → {after}"]
        if kind == "seize":
            b, a = places[(r["at"], r["faction"])]
            out.append(f"{possessive(name(r['faction']))} presence at {r['at']}: {b} → {a}")
        return out + (_record(r, name) if kind in COMPLEX else [])
    if kind == "push":
        return ["nothing changes this time"]
    if r["effect"] is None:
        return [f"it fails (cost {r['cost']})"] + _record(r, name)
    if kind == "seize":
        return [f"{r['asset']} now belongs to {name(r['faction'])}"] + _record(r, name)
    return [_SUCCEEDS[kind].format(who=r.get("who", ""), rival=name(r.get("rival", "")),
                                   rival_id=r.get("rival", ""), mine=r["faction"],
                                   plot=r.get("plot", ""))] + _record(r, name)


_SUCCEEDS = {
    "take": "{who} is in their hands: where they are held is a fact; a thread the character can pull",
    "spy": "they learn something {rival} knows: gm-note.sh tell <fact id> faction:{mine} "
           "(what {rival} knows: gm-note.sh find --held-by faction:{rival_id})",
    "expose": "a fact about {rival} climbs the ladder: gm-note.sh tell <fact id> street (or public)",
    "deal": "a deal with {rival}: its terms as consequences that move the Relation's resting point "
            "or drift for a while (--rule-effect rate_of)",
}


def _record(r, name) -> list[str]:
    return ["Record its facts (gm-note.sh beat): the truth for "
            f"{name(r['faction'])}, versions (partial, wrong) for the others; narrate only what leaves a trace."]


def _advance(json_ops, r) -> dict[str, Any] | None:
    """The plan clock one segment on (its on_clock consequences fire: the portents)."""
    import contextlib

    from rule_effects import _base
    from threat_clocks import ThreatClockManager
    base = _base(json_ops)
    if base is None:
        return None
    with contextlib.redirect_stdout(sys.stderr):
        return ThreatClockManager(base).advance(r["clock"])


def _plan_lines(r) -> list[str]:
    """What a complex action did to its plot's plan clock."""
    if not r.get("plot"):
        return []
    if not r.get("clock"):
        return [f"for {r['plot']}, which has no plan clock to move: give it one "
                f"(gm-clock.sh add \"<short name>\" 4 --on event --consequence \"<the plan "
                f"succeeds>\" --plot \"{r['plot']}\")"]
    if r["effect"] is None:
        return [f"plan clock {r['clock']} ({r['plot']}) doesn't move"]
    clock = r.get("clock_after")
    if clock is None:
        return ["plan clock: not moved, not the active campaign"]
    out = [f"plan clock {r['clock']} ({r['plot']}): {clock['current']}/{clock['max']}"]
    out += [f"{c['id']} {c['consequence']} (fired)" for c in clock.get("fired") or []]
    if clock["current"] >= clock["max"]:
        out.append(f"the plan succeeds: play out its consequence, then gm-plot.sh complete "
                   f"\"{r['plot']}\" \"<what came of it>\" --next \"<the bigger plot that "
                   f"replaces it>\"")
    return out


def _move_asset(json_ops, r) -> None:
    from factions import FILE, load
    table = load(json_ops)
    theirs = table[r["rival"]].get("assets") or []
    item = next(x for x in theirs if x["name"] == r["asset"])
    table[r["rival"]]["assets"] = [x for x in theirs if x is not item]
    if not table[r["rival"]]["assets"]:
        del table[r["rival"]]["assets"]
    table[r["faction"]].setdefault("assets", []).append(item)
    json_ops.save_json(FILE, table)


def idle(json_ops, actions: list[dict[str, Any]]) -> list[str]:
    """The factions that didn't act this turn."""
    from factions import load
    acted = {a["faction"] for a in actions}
    return [fid for fid in load(json_ops) if fid not in acted]


def run(json_ops, actions, rng=None, only: str | None = None, settle: bool = True) -> list[str]:
    """Check, roll and apply a whole turn; the lines for the GM. `only`: one faction
    takes its turn alone, and the actions must be its one action."""
    checked = check(json_ops, actions)
    if only is not None:
        from factions import FactionManager
        fid = FactionManager(json_ops).key(only)
        if [a["faction"] for a in checked] != [fid]:
            raise TurnError(f"--only {fid}: give its one action, and no other faction's. "
                            f"Nothing was changed.")
    else:
        missing = idle(json_ops, checked)
        if missing:
            raise TurnError(f"In a full turn every faction acts: no action for "
                            f"{', '.join(missing)} (one that lies low builds up). For one "
                            f"faction alone: --only <faction>. Nothing was changed.")
    lines = apply(json_ops, resolve(json_ops, checked, rng))
    if not settle:                  # a job the faction does itself: the job token is settled
        return lines
    import faction_rules
    paid = faction_rules.settle(json_ops, checked[0]["faction"] if only is not None else faction_rules.JOKER)
    if paid:
        when = paid["at"].replace("T", " ")
        lines.append(f"(This was the turn owed since {when or '?'}"
                     + (f": give its facts the time it happened, --when \"{when}\" (in a beat: "
                        f"\"when\": \"{when}\").)" if when else ".)"))
    return lines
