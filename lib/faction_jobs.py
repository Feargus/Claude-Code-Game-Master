#!/usr/bin/env python3
"""Jobs and asks: what the faction bag gives the character to do (decided 2026-11-21).

A **job** is a faction's: one of each faction's 4 bag tokens is a job token
(`job:<id>`). Drawn, it is owed like a turn; the GM plays it by offering the
character a complex action for the faction's plot, in person, by message or by call
(anonymous if the faction wants), with a deadline the character knows:

    bash tools/gm-faction.sh job offer lazarus <<'EOF'
    {"action": "take", "power": "Covert", "who": "Fen", "due": "2d",
     "how": "a call from a clinic number", "note": "bring in a man behind on his lien"}
    EOF

The action is checked as a faction turn's would be, and kept on the faction's record
(`job`) with a time clock, `<id> job`, due at the deadline. Then, one of:

    job done <id>       the character did it: it counts as the faction's success (its
                        plan clock moves one segment), and Standing with it +1
    job failed <id>     the character failed, or the deadline passed (the clock's
                        consequence says so): Standing −1, and the faction does the
                        action itself, rolled as in a turn
    job refused <id>    the character said no: the faction does it itself, at once

A faction never loses its turn: the character can only delay it.

An **ask** is a person's: the bag holds 4 `people` tokens and 2 blanks more, a
faction's share. Drawn, it is owed; `gm-faction.sh ask` plays it: one person is
drawn at random from everyone with an attitude toward the character (hostile ones
too, and the party), living, and the GM brings their request, in person, by message
or by call. A favour is a beat; anything larger is a small side plot.
"""

import contextlib
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

OUTCOMES = ("done", "failed", "refused")
STANDING_STEP = 1


class JobError(ValueError):
    """A job or ask that can't be played. The message says how to fix it."""


def _clock_name(fid: str) -> str:
    return f"{fid} job"


def _base(json_ops) -> str:
    from rule_effects import _base as base
    found = base(json_ops)
    if found is None:
        raise JobError("Not the active campaign: jobs are played in the active campaign.")
    return found


def _name(json_ops, fid: str) -> str:
    import factions
    return factions.known(json_ops).get(fid, {}).get("name", fid)


# ---------- offering ----------

def offer(json_ops, raw_faction, spec: dict[str, Any]) -> list[str]:
    """Offer the character the job a drawn job token owes. Returns the lines."""
    import faction_rules
    import faction_turns
    import factions
    from game_time import STORED_FORMAT, current_time
    from threat_clocks import ThreatClockManager
    from time_manager import TimeError, parse_duration
    fid = factions.FactionManager(json_ops).key(raw_faction)
    table = factions.load(json_ops)
    if table[fid].get("job"):
        raise JobError(f"{_name(json_ops, fid)} has a job out already "
                       f"({_describe(table[fid]['job'])}): gm-faction.sh job done|failed|"
                       f"refused {fid} first.")
    if not isinstance(spec, dict):
        raise JobError('A job is an object: {"action": "take", "power": "Covert", "who": "<npc>", '
                       '"due": "2d", "how": "a call", "note": "…"}.')
    spec = dict(spec)
    due, how = str(spec.pop("due", "") or "").strip(), str(spec.pop("how", "") or "").strip()
    if not due:
        raise JobError('A job has a deadline the character knows: "due": "2d" (or "6h", "1w").')
    try:
        minutes = parse_duration(due)
    except (ValueError, TimeError) as error:
        raise JobError(f'"due": {error}') from error
    try:
        action = faction_turns.check(json_ops, [dict(spec, faction=fid)])[0]
    except faction_turns.TurnError as error:
        raise JobError(str(error)) from error
    if action["action"] not in faction_turns.COMPLEX:
        raise JobError(f"A job is a complex action ({', '.join(faction_turns.COMPLEX)}), "
                       f"not {action['action']}.")
    now = current_time(json_ops)
    if now is None:
        raise JobError("The campaign has no game time yet (gm-time.sh set).")
    settled = faction_rules.settle(json_ops, faction_rules.job_kind(fid))
    base = _base(json_ops)
    with contextlib.redirect_stdout(sys.stderr):
        clock = ThreatClockManager(base).add_clock(
            _clock_name(fid), 1, advance_on="time", due_in_minutes=minutes,
            text=f"{_name(json_ops, fid)}'s job for the character: {action.get('note') or action['action']}",
            consequence=f"The deadline for {_name(json_ops, fid)}'s job has passed: "
                        f"bash tools/gm-faction.sh job failed {fid}")
    table = factions.load(json_ops)
    action["plot"] = action.get("plot") or faction_turns.NO_PLOT     # kept for the roll after
    table[fid]["job"] = {k: v for k, v in {**action, "how": how,
                                           "offered_at": now.strftime(STORED_FORMAT),
                                           "due_at": clock.get("due_at", "")}.items() if v}
    json_ops.save_json(factions.FILE, table)
    when = clock.get("due_at", "").replace("T", " ")
    lines = [f"[SUCCESS] {_name(json_ops, fid)} offers the character a job: {_describe(action)}",
             f"  how: {how or 'in person, by message or by call: say which'}; the deadline, "
             f"which the character knows: {when} (clock {_clock_name(fid)})"]
    if action["plot"] != faction_turns.NO_PLOT:
        lines.append(f"  for its plot {action['plot']}: done, it moves the plan clock "
                     f"{action.get('clock') or '(none to move)'}")
    lines.append(f"  then: bash tools/gm-faction.sh job done|failed|refused {fid}")
    if settled is None:
        lines.append("  (no job token was owed: offered anyway)")
    return lines


def _describe(action: dict[str, Any]) -> str:
    import faction_turns
    head = faction_turns.NAMES[action["action"]]
    if action.get("who"):
        head += f": {str(action['who']).partition(':')[2] or action['who']}"
    parts = [head] + [f"{word} {action[key]}" for key, word in
                      (("rival", "against"), ("at", "at"), ("asset", "for"), ) if action.get(key)]
    return " ".join(parts) + (f" ({action['note']})" if action.get("note") else "")


# ---------- the outcome ----------

def outcome(json_ops, raw_faction, result: str, rng=None) -> list[str]:
    """How the job ended: done, failed (or the deadline passed) or refused."""
    import factions
    from threat_clocks import ThreatClockManager
    if result not in OUTCOMES:
        raise JobError(f"A job ends {', '.join(OUTCOMES)}, not {result!r}.")
    fid = factions.FactionManager(json_ops).key(raw_faction)
    table = factions.load(json_ops)
    job = table[fid].pop("job", None)
    if not job:
        raise JobError(f"{_name(json_ops, fid)} has no job out (gm-faction.sh job offer {fid}).")
    json_ops.save_json(factions.FILE, table)
    with contextlib.redirect_stdout(sys.stderr):
        ThreatClockManager(_base(json_ops)).remove_clock(_clock_name(fid))
    name = _name(json_ops, fid)
    if result == "done":
        lines = [f"[SUCCESS] The character did {name}'s job: {_describe(job)}"]
        lines += _plan_step(json_ops, job)
        lines += _standing(json_ops, fid, +STANDING_STEP, f"did {name}'s job")
        lines.append("  Record what the character did as facts (gm-note.sh beat), as for any "
                     "complex action: the truth for those who saw, versions for the others.")
        return lines
    lines = [f"[SUCCESS] {name}'s job was {'refused' if result == 'refused' else 'not done'}: "
             f"{name} does it itself."]
    if result == "failed":
        lines += _standing(json_ops, fid, -STANDING_STEP, f"failed {name}'s job")
    lines += _act(json_ops, job, rng)
    return lines


def _plan_step(json_ops, job) -> list[str]:
    """The plan clock one segment on, as a faction's own success would move it."""
    import faction_turns
    if job.get("plot", faction_turns.NO_PLOT) == faction_turns.NO_PLOT:
        return ["  not for a plot: no plan clock moves"]
    plot, clock = faction_turns._plan(json_ops, {"faction": job["faction"], "plot": job["plot"]},
                                      f"the job ({job['faction']})")
    r = {"plot": plot, "clock": clock, "effect": 1}
    if clock:
        r["clock_after"] = faction_turns._advance(json_ops, r)
    return [f"  → {line}" for line in faction_turns._plan_lines(r)]


def _standing(json_ops, fid: str, by: int, why: str) -> list[str]:
    import world_rules
    try:
        report = world_rules.change(json_ops, world_rules.STANDING, f"faction:{fid}", by=by,
                                    cause=why)
    except world_rules.RulesError:
        return ["  (this world has no Standing rule: nothing to change)"]
    return [f"  Standing of {_name(json_ops, fid)}: {report.get('before')} → {report.get('after')}"]


def _act(json_ops, job, rng) -> list[str]:
    """The faction does the job itself: its action, rolled as in a faction turn."""
    import faction_turns
    action = {k: job[k] for k in faction_turns.FIELDS if k in job}
    for key in ("rival", "who"):           # stored as ids; the check takes names or ids
        if key in action:
            action[key] = str(action[key]).partition(":")[2] or action[key]
    try:
        return faction_turns.run(json_ops, [action], rng=rng, only=job["faction"], settle=False)
    except faction_turns.TurnError as error:
        return [f"  It can't act as planned now ({error}): give it a turn of its own: "
                f"bash tools/gm-faction.sh turn --only {job['faction']}"]


def job_lines(json_ops, fid: str) -> list[str]:
    """A faction's job out, for its card."""
    import factions
    job = factions.load(json_ops).get(fid, {}).get("job")
    if not job:
        return []
    return [f"  Job out for the character: {_describe(job)}; due {job.get('due_at', '?').replace('T', ' ')}"
            + (f"; {job['how']}" if job.get("how") else "")]


# ---------- asks ----------

def askers(json_ops) -> list[str]:
    """Everyone who could ask: the living NPCs with an attitude toward the character,
    hostile ones and the party included."""
    import facts as fact_file
    from entity_manager import is_dead
    from note_manager import current_attitudes
    npcs = json_ops.load_json("npcs.json") or {}
    held = current_attitudes(fact_file.load(json_ops))
    names = [holder.partition(":")[2] for (holder, about) in held
             if about == "player" and holder.startswith("npc:")]
    return sorted({n for n in names if isinstance(npcs.get(n), dict) and not is_dead(npcs[n])})


def ask(json_ops, rng=None) -> list[str]:
    """Play an owed ask: one person drawn at random, and what the GM does with it."""
    import faction_rules
    import facts as fact_file
    from note_manager import current_attitudes
    people = askers(json_ops)
    if not people:
        raise JobError("Nobody has an attitude toward the character yet, so nobody can ask "
                       "(gm-npc.sh attitude \"<npc>\" \"<adjectives>\").")
    who = (rng or random).choice(people)
    settled = faction_rules.settle(json_ops, faction_rules.PEOPLE)
    feel = current_attitudes(fact_file.load(json_ops)).get((f"npc:{who}", "player"), {})
    lines = [f"ASK: {who} ({feel.get('fact') or 'some feeling'} toward the character) "
             f"wants something of them.",
             "  Bring it in person, by message or by call, at the next quiet moment, from what "
             f"{who} wants and fears (gm-npc.sh show \"{who}\"); a hostile one makes a demand.",
             "  A favour is a beat; anything larger is a small side plot (gm-plot.sh add "
             f"\"<short name>\" --kind side --owner \"{who}\" --goal \"…\").",
             "  If it can't fit this moment, draw again once: bash tools/gm-faction.sh ask --again"]
    if settled is None:
        lines.append("  (no ask was owed: drawn anyway)")
    return lines


def ask_again(json_ops, rng=None) -> list[str]:
    """Another person, for an ask whose first draw didn't fit (no token is settled)."""
    people = askers(json_ops)
    if not people:
        raise JobError("Nobody has an attitude toward the character yet.")
    who = (rng or random).choice(people)
    return [f"ASK (drawn again): {who} wants something of the character."]
