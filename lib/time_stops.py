#!/usr/bin/env python3
"""What stops time, and the timeline of the rest (design-notes.md → "Time stops at
the first event", step 3).

A moment of the time walk (time_manager.TimeManager.advance) stops time when it holds
something to play now:
- a consequence that fires, unless it was created `--offscreen`;
- a time clock that fills;
- a world rule's result with a Do-now line (`gm`) coming on, for a holder who is
  here: the character, the world, the current place, a person present.

Everything else goes into the timeline, printed when time stops or the step ends: a
change for a holder who isn't here (a faction, an NPC elsewhere: off-screen), a result
without a Do-now line (a process such as healing), a draw without one, a refill, a
rate step, a clock's segment. A Do-now line off-screen is kept in full: the GM may
have to act on it (start a clock, record a fact) without narrating it.

`--through "<name>"` (gm-time.sh advance): a rule, a rule's outcome ("The Sky:acid
rain"), a consequence's id or a clock's name that doesn't stop time during this
command; `--through` alone: nothing does (a montage).
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))


class Through:
    """The names given with --through, checked and resolved."""

    def __init__(self, world_state_dir, json_ops, names: list[str] | None, everything=False):
        self.everything = everything
        self.rules, self.outcomes, self.consequences, self.clocks = set(), set(), set(), set()
        self.names = list(names or [])
        problems = [self._add(world_state_dir, json_ops, n) for n in self.names]
        problems = [p for p in problems if p]
        if problems:
            from time_manager import TimeError
            raise TimeError(" ".join(problems) + " No time has passed.")

    def _add(self, world_state_dir, json_ops, raw: str) -> str:
        import world_rules
        from consequence_manager import ConsequenceManager
        from rule_errors import RulesError
        from threat_clocks import ThreatClockManager
        name = " ".join(str(raw).split())
        rule_name, _, value = name.partition(":")
        try:
            rule = world_rules.find_rule(json_ops, rule_name.strip())
        except RulesError:
            rule = None
        if rule and value:
            labels = {str(label).lower(): label for label, _ in world_rules.block(rule).outcomes(rule)}
            if value.strip().lower() not in labels:
                return (f"--through \"{name}\": {rule['name']} has no outcome '{value.strip()}' "
                        f"(it has: {', '.join(map(str, labels.values())) or 'none'}).")
            self.outcomes.add((rule["name"], str(labels[value.strip().lower()])))
            return ""
        if rule:
            self.rules.add(rule["name"])
            return ""
        data = ConsequenceManager(world_state_dir).json_ops.load_json("consequences.json") or {}
        if any(c.get("id") == name for c in data.get("active", [])):
            self.consequences.add(name)
            return ""
        clocks = {k.lower(): k for k in ThreatClockManager(world_state_dir)._load()}
        if name.lower() in clocks:
            self.clocks.add(clocks[name.lower()])
            return ""
        return (f"--through \"{name}\" is no world rule (or \"<rule>:<outcome>\"), waiting "
                f"consequence id or clock.")

    def rule(self, rule: str, label: str) -> bool:
        return self.everything or rule in self.rules or (rule, str(label)) in self.outcomes

    def args(self) -> str:
        """The flags to give again when going on."""
        if self.everything:
            return " --through"
        return "".join(f' --through "{n}"' for n in self.names)


# ---------- what a moment holds ----------

def do_now(report: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Every (rule, holder, outcome, Do-now line) of a rule's report, the chain of
    reports its effects made included."""
    out = []
    gm = report.get("gm")
    if isinstance(gm, dict):                               # a counter's or a plane's results
        out += [(report["rule"], report["holder"], label, line) for label, line in gm.items() if line]
    elif gm:                                               # a state entered
        out.append((report["rule"], report["holder"], report.get("after", ""), gm))
    for draw in report.get("draws") or []:                 # a bag's draws
        if draw.get("gm"):
            out.append((report["rule"], report["holder"], draw["kind"], draw["gm"]))
    for nested in _nested(report):
        out += do_now(nested)
    return out


def fired(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The consequences a rule's report fired (on_rule, a state's, a clock an effect
    advanced), the chain included."""
    out = list(report.get("fired") or [])
    for draw in report.get("draws") or []:
        out += draw.get("fired") or []
    for done in _done(report):
        out += done.get("fired") or []
    for nested in _nested(report):
        out += fired(nested)
    return out


def _done(report):
    for items in (report.get("did") or {}).values():
        yield from items
    for draw in report.get("draws") or []:
        yield from draw.get("did") or []


def _nested(report):
    for done in _done(report):
        if isinstance(done.get("report"), dict):
            yield done["report"]


def here(json_ops, on_the_way: bool = False) -> tuple[str, set[str]]:
    """Where the character is ('' on the way) and the ids of who is with them."""
    from entity_manager import npcs_present
    overview = json_ops.load_json("campaign-overview.json") or {}
    pos = overview.get("player_position") or {}
    place = "" if on_the_way else (pos.get("current_location", "") if isinstance(pos, dict) else "")
    present = npcs_present(json_ops.load_json("npcs.json") or {}, place, overview.get("scene"))
    return place, {f"npc:{name}".lower() for name in present}


def holder_here(holder: str, place: str, present: set[str]) -> bool:
    import sites
    h = str(holder).lower()
    return h in ("player", "world") or h in present or (
        bool(place) and h.startswith("location:") and sites.at(place, h))


def judge(json_ops, moment: dict[str, Any], through: Through, place: str,
          present: set[str]) -> list[tuple[str, Any]]:
    """What in this moment stops time: [("consequence", c) | ("clock", name) |
    ("rule", (rule, holder, outcome, line))]. Through names never stop; with
    --through alone this still says what would have, for the timeline."""
    stops = []
    every = list(moment["fired"])
    for clock in moment["clocks"].values():
        every += clock.get("fired") or []
    for report in moment["rules"]:
        every += fired(report)
    for c in every:
        if not c.get("offscreen") and c.get("id") not in through.consequences:
            stops.append(("consequence", c))
    for name, clock in moment["clocks"].items():
        if clock["current"] >= clock["max"] and name not in through.clocks:
            stops.append(("clock", name))
    for report in moment["rules"]:
        for item in do_now(report):
            rule, holder, label, _ = item
            if holder_here(holder, place, present) and rule not in through.rules \
                    and (rule, str(label)) not in through.outcomes:
                stops.append(("rule", item))
    return stops


# ---------- the timeline ----------

def brief(json_ops, report: dict[str, Any]) -> str:
    """One short line for a rule's report; '' for nothing worth a line (the faction
    bag: what it drew is owed_lines). The repo's own rules carry no hidden mark: the player
    never sees any of them."""
    import faction_rules
    import world_rules
    if report["rule"] == faction_rules.BAG:
        return ""                                  # its turns owed are [DO] lines (owed_lines)
    who = world_rules.holder_name(json_ops, report["holder"])
    head = f"{report['rule']} ({who})"
    hidden = "" if report.get("known", True) or faction_rules.is_built_in(report["rule"]) \
        else f" {world_rules.HIDDEN}"
    if "draws" in report:
        kinds = ", ".join(d["kind"] for d in report["draws"]) or "nothing"
        return f"{head}: drew {kinds}{'; ' + report['empty'] if report.get('empty') else ''}{hidden}"
    if report.get("refilled"):
        return f"{head}: refilled"
    if "axis" in report:
        what = f"{report['axis']} {report['before']} → {report['after']}"
    else:
        what = f"{report.get('before')} → {report.get('after')}"
    texts = _texts(json_ops, report["rule"])
    if report.get("on"):                                   # what came on, in the fiction's words
        what += "; now on: " + "; ".join(f"{label}: {texts.get(str(label), '')}".rstrip(": ")
                                         for label in report["on"])
    if report.get("off"):
        what += f"; off: {', '.join(map(str, report['off']))}"
    return f"{head}: {what}{hidden}"


def owed_lines(json_ops, moments: list[dict[str, Any]]) -> list[str]:
    """[DO] for each turn the faction bag drew in `moments`, with its time and the
    command that plays it."""
    import faction_rules
    import factions
    names = factions.known(json_ops)
    lines = []
    for m in moments:
        for report in m["rules"]:
            if report["rule"] != faction_rules.BAG:
                continue
            for d in report.get("draws") or []:
                if d.get("owed"):
                    what, command = faction_rules.turn_owed(d["kind"], names)
                    lines.append(f"[DO] {what[0].upper()}{what[1:]} (drawn {stamp(m['at'])}); "
                                 f"narrate what the character would notice of it: {command}")
    return lines


def _texts(json_ops, name: str) -> dict[str, str]:
    """Each outcome's text, by its label."""
    import world_rules
    from rule_errors import RulesError
    try:
        rule = world_rules.find_rule(json_ops, name)
    except RulesError:
        return {}
    return {str(label): (o.get("text") or "") for label, o in world_rules.block(rule).outcomes(rule)}


def stamp(moment) -> str:
    return f"{moment:%a %d %b %H:%M}"


def timeline_lines(json_ops, moments: list[dict[str, Any]], place: str, present: set[str],
                   through: Through) -> list[str]:
    """The routine events of `moments`, identical lines grouped with all their times,
    in the order they first happened. Off-screen Do-now lines are kept in full, each
    under its time; the consequences that fired are routine_fired's."""
    grouped: dict[str, list[str]] = {}
    full: list[str] = []
    for m in moments:
        when = stamp(m["at"])
        for name, clock in m["clocks"].items():
            grouped.setdefault(f"Clock {name}: {clock['current']}/{clock['max']}", []).append(when)
        for report in m["rules"]:
            line = brief(json_ops, report)
            if line:
                grouped.setdefault(line, []).append(when)
            for rule, holder, label, line in do_now(report):
                if not holder_here(holder, place, present):
                    full.append(f"  {when}: Do now (off-screen, {rule} {label}): {line}")
    lines = [f"  {text} — {', '.join(times)}" for text, times in grouped.items()]
    return lines + full


def routine_fired(moments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The consequences that fired at the routine moments (off-screen, or gone
    through), each with its time (and "off-screen") added to why it fired."""
    out = []
    for m in moments:
        cons = list(m["fired"]) + [c for clock in m["clocks"].values() for c in clock.get("fired") or []]
        cons += [c for report in m["rules"] for c in fired(report)]
        for c in cons:
            why = str(c.get("match_reason") or "").strip().rstrip(".")
            where = ", off-screen" if c.get("offscreen") else ""
            out.append(dict(c, match_reason=f"{why} ({stamp(m['at'])}{where})".lstrip()))
    return out
