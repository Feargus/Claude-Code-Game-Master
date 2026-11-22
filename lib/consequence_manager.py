#!/usr/bin/env python3
"""
Consequence management module for GM tools
Handles tracking future events and consequences
"""

import sys
import uuid
from pathlib import Path
from typing import Any

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import facts as fact_file
from entity_manager import EntityManager, npcs_present
from game_time import STORED_FORMAT


class ConsequenceManager(EntityManager):
    """The campaign's consequences: things waiting to happen.

    A consequence is in one of three states:
      waiting    in `active`, no `fired`: its triggers are checked;
      fired      in `active`, with `fired` (why, and when in the game): it happened
                 and is to be played out. It matches no trigger any more, so it
                 fires once, whatever its triggers and however long it stays;
      resolved   moved to `resolved`: played out.
    `rearm` puts a fired one back to waiting (the moment was wrong).
    """

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self.consequences_file = "consequences.json"
        self._ensure_file()

    def _ensure_file(self):
        """Ensure consequences file has proper structure"""
        data = self.json_ops.load_json(self.consequences_file)
        if not isinstance(data, dict) or 'active' not in data:
            data = {'active': [], 'resolved': []}
            self.json_ops.save_json(self.consequences_file, data)

    # Structured trigger types the reactivity engine can evaluate automatically.
    TRIGGER_TYPES = ('on_location', 'on_npc', 'on_time', 'on_fact', 'on_death', 'on_clock',
                     'on_learn', 'on_rule')
    # Event triggers fire once, inside the command that makes the change
    # (fire_event), never on the scene check that moves and time steps run.
    # on_fact is the GM's: semantic recall names the consequences a recorded
    # fact may trigger (recall_notes.py), and the GM fires one by hand.
    EVENT_TRIGGER_TYPES = ('on_death', 'on_fact', 'on_clock', 'on_learn', 'on_rule')
    # A trigger either matches or not. There is no word matching: free-text
    # conditions are on_fact triggers, judged by the GM.
    # Triggers whose match is an id (world_ids.py), checked when added and
    # compared exactly: (the kinds it may be, what to do if it doesn't exist).
    ID_TRIGGERS = {
        'on_location': (('location',), "a known place; add a new one with gm-location.sh add"),
        'on_npc': (('npc',), "a known NPC; create a new one with gm-npc.sh create"),
        'on_death': (('player', 'npc'),
                     "the player or a known NPC; create a new one with gm-npc.sh create"),
    }

    def add_consequence(self, description: str, trigger: str,
                        trigger_type: str = None, match: str = None,
                        triggers: list[dict[str, str]] = None,
                        effects: list[dict[str, Any]] = None, plots=None,
                        offscreen: bool = False) -> str:
        """
        Add a new consequence.

        Free-text `trigger` is always kept (human-readable). Without structured
        triggers it becomes the consequence's on_fact trigger: the event it waits
        for, judged by the GM when facts are recorded. STRUCTURED triggers, any one
        of which fires it:
          triggers:     list of {"type": one of TRIGGER_TYPES, "match": value compared
                        against world state (location/npc/time/event keyword)}
          trigger_type, match: shorthand for a single trigger (added to `triggers`)
        Structured fields are additive; legacy consequences omit them.

        `effects` are carried out by the script each time it fires (see EFFECT_TYPES):
          {"type": "start_clock", "name", "segments", "on" (time|event, default time),
           "due_in" ("3d") or "due" ("YYYY-MM-DD HH:MM"), "consequence" (optional)}
          {"type": "tell", "fact", "holders"}
          {"type": "rule", <a world rule's effect>}: change, rate_of, state or tokens
           (rule_effects.py), with "of" its holder, e.g. {"type": "rule", "change":
           "Standing", "of": "faction:police", "by": -3}
        A due_in counts from when the consequence fires.

        Returns the consequence ID, or "" if refused.
        """
        triggers = [dict(t) for t in (triggers or [])]
        if trigger_type:
            triggers.append({'type': trigger_type, 'match': match})
        if not triggers and str(trigger or '').strip():
            triggers = [{'type': 'on_fact', 'match': str(trigger).strip()}]
        for t in triggers:
            if t.get('type') not in self.TRIGGER_TYPES:
                print(f"[ERROR] Unknown trigger type '{t.get('type')}'. Use one of: "
                      f"{', '.join(self.TRIGGER_TYPES)}", file=sys.stderr)
                return ""
            if not t.get('match'):
                print(f"[ERROR] Trigger {t['type']} needs a --match value.", file=sys.stderr)
                return ""
            if t['type'] in self.ID_TRIGGERS:
                kinds, what = self.ID_TRIGGERS[t['type']]
                from world_ids import WorldIds
                cid, error = WorldIds(self.json_ops).resolve_as(t['match'], kinds)
                if error:
                    print(f"[ERROR] {t['type']}: {error} It matches {what}.", file=sys.stderr)
                    return ""
                t['match'] = cid
            if t['type'] == 'on_learn':
                canonical, error = self._learn_target(t['match'])
                if error:
                    print(f"[ERROR] {error}", file=sys.stderr)
                    return ""
                t['match'] = canonical
            if t['type'] == 'on_clock':
                canonical, error = self._clock_target(t['match'])
                if error:
                    print(f"[ERROR] {error}", file=sys.stderr)
                    return ""
                t['match'] = canonical
            if t['type'] == 'on_rule':      # a world rule's value (rule_effects.py)
                from rule_effects import on_rule_target
                canonical, error = on_rule_target(self.json_ops, t['match'])
                if error:
                    print(f"[ERROR] {error}", file=sys.stderr)
                    return ""
                t['match'] = canonical
            if t['type'] == 'on_time':
                ok, _ = self.validators.validate_time_of_day(t['match'])
                if not ok:
                    from time_manager import all_hours
                    print(f"[ERROR] on_time matches a time-of-day word, which means its hours on the "
                          f"game clock ({all_hours()}), not '{t['match']}'. For a "
                          f"deadline at a date and time, use a clock: gm-clock.sh add \"<name>\" 1 "
                          f"--due \"YYYY-MM-DD HH:MM\" --consequence \"<what happens>\"", file=sys.stderr)
                    return ""

        effects = [dict(e) for e in (effects or [])]
        for e in effects:
            error = self._check_effect(e)
            if error:
                print(f"[ERROR] {error}", file=sys.stderr)
                return ""
        from plot_manager import resolve_plots
        plot_keys, errors = resolve_plots(self.json_ops, plots)
        if errors:
            print(f"[ERROR] {' '.join(errors)}", file=sys.stderr)
            return ""

        data = self.json_ops.load_json(self.consequences_file)

        consequence_id = str(uuid.uuid4())[:8]
        consequence = {
            'id': consequence_id,
            'consequence': description,
            'trigger': trigger,
            'created': self.json_ops.get_timestamp()
        }
        if triggers:
            consequence['triggers'] = triggers
        if effects:
            consequence['effects'] = effects
        if plot_keys:
            consequence['plots'] = plot_keys
        if offscreen:                        # happens where the character isn't: never stops time
            consequence['offscreen'] = True

        if 'active' not in data:
            data['active'] = []
        data['active'].append(consequence)

        if self.json_ops.save_json(self.consequences_file, data):
            then = describe_effects(effects)
            print(f"[SUCCESS] Added consequence [{consequence_id}]: {description} "
                  f"(triggers: {trigger}{'; when it fires, ' + then if then else ''})"
                  + (" (off-screen: it doesn't stop time)" if offscreen else ""))
            return consequence_id
        return ""

    def check_pending(self, world_state: dict[str, Any] = None) -> list[dict[str, Any]]:
        """
        Pending consequences.

        - No world_state  -> the raw active list (legacy accessor).
        - With world_state -> every consequence a state trigger MATCHES now, each
          annotated with `match_reason`.

        world_state keys (all optional): location (str, a locations.json key),
        present_npcs (list[str], npcs.json keys), game_time ("YYYY-MM-DDTHH:MM"),
        time (str, the time-of-day word, used when there is no game_time),
        events (list[str]), date (str).

        A consequence that has fired matches nothing (see the class).
        """
        data = self.json_ops.load_json(self.consequences_file)
        active = data.get('active', [])

        if world_state is None:
            return active

        matched = []
        for c in active:
            reason = '' if c.get('fired') else self._matches_now(c, world_state)
            if reason:
                hit = dict(c)
                hit['match_reason'] = reason
                matched.append(hit)
        return matched

    EFFECT_TYPES = ('start_clock', 'tell', 'rule')
    RULE_EFFECTS = ('change', 'rate_of', 'state', 'tokens')    # what a rule effect may be

    def _check_effect(self, effect: dict[str, Any]) -> str:
        """Why `effect` can't be carried out, or '' if it can. Fills in defaults
        and makes names canonical."""
        if effect.get('type') not in self.EFFECT_TYPES:
            return (f"Unknown effect '{effect.get('type')}'. Use one of: "
                    f"{', '.join(self.EFFECT_TYPES)}")
        if effect['type'] == 'tell':
            return self._check_tell(effect)
        if effect['type'] == 'rule':
            return self._check_rule(effect)
        return self._check_start_clock(effect)

    def _check_rule(self, effect: dict[str, Any]) -> str:
        """rule: a world rule's effect (change, rate_of, state, tokens), checked as a
        rule's own are; "of" is resolved to its holder (needed unless the rule is
        held only by the player or the world)."""
        import rule_effects
        import world_rules
        from rule_errors import RulesError
        inner = {k: v for k, v in effect.items() if k != 'type'}
        kind = rule_effects.kind_of(inner)
        if kind not in self.RULE_EFFECTS:
            return (f"A rule effect is one of {', '.join(self.RULE_EFFECTS)} (a world rule's "
                    f"effect, gm-rules skill); got {sorted(inner)}. A clock: --starts-clock.")
        problems = [f"rule effect: {p}" for p in rule_effects._check_one(inner)]
        try:
            target = world_rules.find_rule(self.json_ops, inner[kind])
            if not problems and rule_effects.LINKS[kind](inner, {"name": "", "held_by": []},
                                                         target, "rule effect", problems):
                inner[kind] = target["name"]
                inner["of"] = world_rules.resolve_holder(self.json_ops, target, inner.get("of"))
        except RulesError as error:
            problems.append(str(error))
        if problems:
            return "; ".join(problems)
        effect.update(inner)
        return ''

    def _rule(self, e: dict[str, Any]) -> list[str]:
        import rule_effects
        import world_rules
        inner = {k: v for k, v in e.items() if k != 'type'}
        done = rule_effects.run(self.json_ops, inner, inner['of'], rule_effects.new_chain(),
                                "a consequence")
        report = done.get('report') or done.get('states_report')
        lines = [done['line']] if done.get('line') else []
        if isinstance(report, dict):
            lines += world_rules.report_lines(self.json_ops, report)
        for c in done.get('fired') or []:
            lines.append(f"that fired [{c['id']}] {c['consequence']}")
        return lines

    def _check_tell(self, effect: dict[str, Any]) -> str:
        """tell: {"fact": <id>, "holders": [...]}: who learns which fact."""
        from world_ids import WorldIds
        fact = str(effect.get('fact', '')).strip()
        if not fact or not self._find_fact(fact):
            return f"tell: no fact '{fact}'."
        raw = effect.get('holders') or []
        holders, errors = WorldIds(self.json_ops).resolve_all(
            [raw] if isinstance(raw, str) else raw, holders=True)
        if errors:
            return "tell: " + "; ".join(errors)
        if not holders:
            return "tell: who learns it? Give --to <holder>."
        effect['fact'], effect['holders'] = fact, holders
        return ''

    @staticmethod
    def _check_start_clock(effect: dict[str, Any]) -> str:
        from threat_clocks import check_name
        from time_manager import TimeError, parse_duration, parse_time
        try:
            effect['name'] = check_name(effect.get('name'))
        except ValueError as error:
            return f"start_clock: {error}"
        try:
            effect['segments'] = int(effect.get('segments', 1))
        except (TypeError, ValueError):
            return f"start_clock: segments must be a whole number, not {effect.get('segments')!r}."
        if effect['segments'] < 1:
            return "start_clock: a clock needs at least 1 segment."
        effect.setdefault('on', 'time')
        if effect['on'] not in ('time', 'event'):
            return f"start_clock: 'on' is time or event, not {effect['on']!r}."
        if effect.get('due') and effect.get('due_in'):
            return "start_clock: give due or due_in, not both."
        if (effect.get('due') or effect.get('due_in')) and effect['on'] != 'time':
            return "start_clock: only a time clock has a due time."
        try:
            if effect.get('due_in'):
                parse_duration(effect['due_in'])
            if effect.get('due'):
                parse_time(effect['due'])
        except TimeError as error:
            return f"start_clock: {error}"
        return ''

    def _carry_out(self, hits: list[dict[str, Any]]) -> None:
        """Carry out the effects of consequences that just fired.

        Called after consequences.json is saved. Each hit gets `effects_done`: what
        happened, in words. A clock that already exists is left as it is, so a
        consequence that fires again doesn't restart its clock. A `tell` adds the
        holders through gm-note.sh's own path, so their on_learn consequences
        fire too (and are named in `effects_done`); someone who knew already
        learns nothing, which is what ends a chain.
        """
        for hit in hits:
            done = []
            for e in hit.get('effects') or []:
                if e.get('type') == 'start_clock':
                    done.append(self._start_clock(e, hit.get('plots')))
                elif e.get('type') == 'tell':
                    done.extend(self._tell(e))
                elif e.get('type') == 'rule':
                    done.extend(self._rule(e))
            if done:
                hit['effects_done'] = done

    def _tell(self, e: dict[str, Any]) -> list[str]:
        from note_manager import NoteManager
        try:
            notes = NoteManager(self.base_dir) if self.base_dir else NoteManager()
            new = notes.tell(e['fact'], e.get('holders') or [])
        except (RuntimeError, ValueError) as error:
            return [f"could not tell {e.get('fact')}: {error}"]
        if not new:
            return [f"{', '.join(e.get('holders') or [])} knew {e['fact']} already"]
        lines = [f"{', '.join(new)} now know(s) {e['fact']}"]
        for c in notes.last_fired:
            lines.append(f"that fired [{c['id']}] {c['consequence']}")
            lines += [f"  {line}" for line in c.get('effects_done', [])]
        return lines

    def _start_clock(self, e: dict[str, Any], plots=None) -> str:
        """Start the clock an effect names; it belongs to the consequence's plots."""
        from threat_clocks import ThreatClockManager
        from time_manager import parse_duration, parse_time
        tcm = ThreatClockManager(self.base_dir)
        name = e['name']
        if any(k.lower() == name.lower() for k in tcm.get_clocks()):
            return f"clock {name} is already running; left as it is"
        try:
            clock = tcm.add_clock(
                name, e.get('segments', 1), advance_on=e.get('on', 'time'),
                consequence=e.get('consequence'), text=e.get('text'), plots=plots,
                due_at=parse_time(e['due']) if e.get('due') else None,
                due_in_minutes=parse_duration(e['due_in']) if e.get('due_in') else None)
        except ValueError as error:
            return f"could not start clock {name}: {error}"
        return (f"started clock {name} (0/{clock['max']}, on {clock['advance_on']}"
                f"{tcm.due_text(clock)})")

    def _learn_target(self, raw: str):
        """The canonical on_learn match: ("<who> learns <fact id>" or
        "<who> learns about:<id>", "") or ("", why not).

        <who> is a holder id (player, npc:<name>, street, public) or `anyone`.
        The fact must exist; an about id must resolve (any kind, places too).
        """
        import re

        from world_ids import WorldIds
        usage = ('on_learn matches "<who> learns <fact id>" or "<who> learns about <id>", '
                 'e.g. "npc:Wren learns f42", "street learns about player", '
                 '"anyone learns f17"')
        parts = re.split(r"\s+learns\s+", str(raw).strip(), maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            return "", usage
        who_raw, what = parts[0].strip(), parts[1].strip()
        ids = WorldIds(self.json_ops)
        if who_raw.lower() == 'anyone':
            who = 'anyone'
        else:
            who, error = ids.resolve_holder(who_raw)
            if error:
                return "", f"on_learn: {error}"
        about = re.match(r"about[\s:]+(.+)$", what, flags=re.IGNORECASE)
        if about:
            cid, error = ids.resolve(about.group(1))
            if error:
                return "", f"on_learn: {error}"
            return f"{who} learns about:{cid}", ""
        if not self._find_fact(what):
            return "", f"on_learn: no fact '{what}'. {usage}"
        return f"{who} learns {what}", ""

    def _clock_target(self, raw: str):
        """The canonical on_clock match for `raw`: ("clock:<key>:<segment>", "").

        `raw` is a clock's short name, which means "when it is full", or
        "<name>:<segment>" for a grim portent partway. The clock is looked up by
        the shared resolver (world_ids.py); one that doesn't exist yet counts if a
        waiting consequence starts it when it fires. The segment must be on it.
        Returns ("", error) if not.
        """
        from world_ids import WorldIds, find_clock
        raw = str(raw).strip()
        name, segment = raw, None
        head, sep, tail = raw.rpartition(':')
        if sep and tail.strip().isdigit():
            name, segment = head.strip(), int(tail)
        cid, error = WorldIds(self.json_ops).resolve_as(name, ("clock",))
        if cid:
            key = cid.partition(":")[2]
            mx = int((self.json_ops.load_json("threat-clocks.json") or {})[key].get('max', 1))
        else:
            # Clocks a waiting consequence will start when it fires.
            waiting = {}
            for c in (self.json_ops.load_json(self.consequences_file) or {}).get('active', []):
                for e in c.get('effects') or []:
                    if e.get('type') == 'start_clock':
                        waiting.setdefault(e['name'], {'max': int(e.get('segments', 1)),
                                                       'text': e.get('text')})
            key = find_clock(waiting, name)
            if not key:
                also = f" Waiting to start: {', '.join(waiting)}." if waiting else ""
                return "", (f"on_clock matches a clock's short name, or \"<name>:<segment>\". "
                            f"{error}{also} Create it first (gm-clock.sh add).")
            mx = waiting[key]['max']
        if segment is None:
            segment = mx
        if not 1 <= segment <= mx:
            return "", f"Clock '{key}' has segments 1 to {mx}, not {segment}."
        return f"clock:{key}:{segment}", ""

    @staticmethod
    def structured_triggers(consequence: dict[str, Any]) -> list[dict[str, str]]:
        """The consequence's structured triggers as a list of {"type", "match"}.

        New entries store a `triggers` list. Older entries are read the same way:
        a single `trigger_type` + `match` as a one-item list, and a bare free-text
        `trigger` as an on_fact trigger.
        """
        if isinstance(consequence.get('triggers'), list):
            return [t for t in consequence['triggers']
                    if isinstance(t, dict) and t.get('type') and t.get('match')]
        if consequence.get('trigger_type') and consequence.get('match'):
            return [{'type': consequence['trigger_type'], 'match': consequence['match']}]
        if str(consequence.get('trigger', '')).strip():
            return [{'type': 'on_fact', 'match': str(consequence['trigger']).strip()}]
        return []

    @staticmethod
    def _evaluate_one(ttype: str, raw_match: str, world_state: dict[str, Any]) -> str:
        """The reason a single structured trigger matches now, or '' if it doesn't.

        on_location and on_npc hold ids (location:<key>, npc:<key>), compared
        with the current location and the NPCs present, whose names are keys.
        on_time holds a time-of-day word, compared with the word for the game
        time, so it fires exactly in that word's hours ("noon": 11:00–12:59).
        """
        match = str(raw_match).lower()
        if ttype == 'on_location' and match == f"location:{world_state.get('location', '')}".lower():
            return f"at {raw_match}"
        if ttype == 'on_npc' and match in {f"npc:{n}".lower()
                                          for n in world_state.get('present_npcs') or []}:
            return f"{raw_match} is here"
        if ttype == 'on_time':
            from time_manager import hours_of
            word = ConsequenceManager._time_word(world_state)
            if word and match.strip() == word.lower():
                return f"it is {word} ({hours_of(word)})"
        return ''

    @staticmethod
    def _time_word(world_state: dict[str, Any]) -> str:
        """The time-of-day word now: derived from the game time when there is one
        (never from words written elsewhere), else the stored word."""
        from datetime import datetime

        from time_manager import derive_time_of_day
        stored = world_state.get('game_time')
        if stored:
            try:
                return derive_time_of_day(datetime.strptime(str(stored), STORED_FORMAT))
            except ValueError:
                pass
        return str(world_state.get('time', '')).strip()

    def _matches_now(self, consequence: dict[str, Any], world_state: dict[str, Any]) -> str:
        """Why a state trigger of this consequence matches now, or '' if none does.

        Event triggers (on_death, on_fact, on_clock) never match here; they fire where
        the event is recorded.
        """
        for t in self.structured_triggers(consequence):
            reason = self._evaluate_one(t['type'], t['match'], world_state)
            if reason:
                return reason
        return ''

    def tick(self, world_state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Fire every waiting consequence a state trigger of which matches now.

        There is no limit on how many fire at once: one left out would miss its
        effects (a clock it starts) until the next check at the same place, which
        may never come. A consequence fires once: afterwards it is `fired` and
        matches nothing, until the GM resolves it or arms it again (`rearm`).
        Returns {"fired": [...]}, each with `match_reason`.
        """
        data = self.json_ops.load_json(self.consequences_file)
        fired = []
        for c in data.get('active', []):
            reason = '' if c.get('fired') else self._matches_now(c, world_state)
            if reason:
                fired.append(self._stamp_fired(data, c, reason))
        if fired:
            self.json_ops.save_json(self.consequences_file, data)
        self._carry_out(fired)
        return {'fired': fired}

    def _stamp_fired(self, data: dict[str, Any], consequence: dict[str, Any],
                     reason: str, by_fact: str = None) -> dict[str, Any]:
        """Mark `consequence` (a live object in data['active']) as fired and log
        why. The caller saves. Returns a copy with `match_reason`."""
        from game_time import stored_time
        now = self.json_ops.get_timestamp()
        consequence['fired'] = {'reason': reason, 'at': now}
        game_time = stored_time(self.json_ops)
        if game_time:
            consequence['fired']['game_time'] = game_time
        if by_fact:
            consequence['fired']['fact'] = by_fact
        entry = {'id': consequence['id'], 'consequence': consequence['consequence'],
                 'reason': reason, 'fired_at': now}
        if by_fact:
            entry['fact'] = by_fact
        data.setdefault('provenance', []).append(entry)
        return dict(consequence, match_reason=reason)

    def fire_event(self, ttype: str, value, reason: str) -> list[dict[str, Any]]:
        """An event happened (e.g. on_death, 'Wren'): fire every active consequence
        waiting consequence with a trigger of that type whose match equals `value`
        (case-insensitive; one that has fired already doesn't fire again).
        `value` may be a list of descriptions of the same event (on_learn: "npc:Wren
        learns f42", "anyone learns f42", ...); a consequence fires once even if
        several fit. Called by the command that makes the change. Returns the fired
        consequences.
        """
        data = self.json_ops.load_json(self.consequences_file)
        values = [str(v).lower() for v in (value if isinstance(value, (list, tuple)) else [value])]
        hits = []
        for c in data.get('active', []):
            if not c.get('fired') and any(t['type'] == ttype and str(t['match']).lower() in values
                                          for t in self.structured_triggers(c)):
                hits.append(c)
        if not hits:
            return []
        fired = [self._stamp_fired(data, c, reason) for c in hits]
        self.json_ops.save_json(self.consequences_file, data)
        self._carry_out(fired)
        return fired

    def waiting_time_words(self) -> set[str]:
        """The time-of-day words (lower case) that consequences still wait on (on_time)."""
        data = self.json_ops.load_json(self.consequences_file)
        return {t['match'].strip().lower() for c in data.get('active', []) if not c.get('fired')
                for t in self.structured_triggers(c) if t['type'] == 'on_time'}

    def waiting_on_fact(self) -> list[dict[str, Any]]:
        """Active consequences waiting for a recorded fact (an on_fact trigger;
        old entries with only a free-text trigger count as one). Each comes back
        with `awaits`: its trigger, in words."""
        data = self.json_ops.load_json(self.consequences_file)
        out = []
        for c in data.get('active', []):
            events = [t['match'] for t in self.structured_triggers(c) if t['type'] == 'on_fact']
            if events and not c.get('fired'):
                hit = dict(c)
                hit['awaits'] = ' / '.join(events)
                out.append(hit)
        return out

    def _find_fact(self, fact_id: str) -> dict[str, Any]:
        """The fact with this id, or {}."""
        return fact_file.by_id(fact_file.load(self.json_ops), fact_id) or {}

    def _find_active(self, data: dict[str, Any], consequence_id: str):
        """The active consequence whose id is or starts with `consequence_id`.

        Returns (consequence, error). The session brief shows 4-character ids, so a
        unique prefix is enough.
        """
        cid = str(consequence_id).strip()
        matches = [c for c in data.get('active', []) if str(c.get('id', '')).startswith(cid)]
        if not cid or not matches:
            return None, f"No active consequence '{consequence_id}'"
        exact = [c for c in matches if c.get('id') == cid]
        if exact:
            return exact[0], ''
        if len(matches) > 1:
            return None, (f"'{consequence_id}' fits several consequences: "
                          f"{', '.join(c['id'] for c in matches)}")
        return matches[0], ''

    def fire(self, consequence_id: str, reason: str = None,
             by_fact: str = None) -> dict[str, Any]:
        """The GM fires a consequence by hand (its condition happened in the story).

        `by_fact` names the recorded fact that fulfilled it; the consequence and
        the log keep the link. Firing is not resolving: it is to be played out,
        then resolved. One that has fired already is refused.
        Returns the fired consequence, or {} if refused.
        """
        data = self.json_ops.load_json(self.consequences_file)
        c, error = self._find_active(data, consequence_id)
        if not c:
            print(f"[ERROR] {error}", file=sys.stderr)
            return {}
        if c.get('fired'):
            print(f"[ERROR] [{c['id']}] has fired already ({c['fired'].get('reason', '?')}). "
                  f"Play it out and resolve it (gm-consequence.sh resolve {c['id']}); to let "
                  f"it happen again, arm it first: gm-consequence.sh rearm {c['id']}",
                  file=sys.stderr)
            return {}
        fact = {}
        if by_fact:
            fact = self._find_fact(by_fact)
            if not fact:
                print(f"[ERROR] No fact '{by_fact}'", file=sys.stderr)
                return {}
        if not reason:
            reason = f"fact {by_fact}: {fact['fact']}" if fact else "fired by the GM"
        hit = self._stamp_fired(data, c, reason, by_fact)
        self.json_ops.save_json(self.consequences_file, data)
        if by_fact:                                   # the right answer, for tuning
            from recall_notes import log_fired
            log_fired(self.json_ops.world_state_dir, c['id'], by_fact)
        if by_fact and c.get('plots'):
            self._give_plots(by_fact, c['plots'])     # the fact belongs where it led
        self._carry_out([hit])
        return hit

    def _give_plots(self, fact_id: str, plots) -> None:
        """Add plots to a recorded fact (the fact that fired a consequence)."""
        facts = fact_file.load(self.json_ops)
        fact = fact_file.by_id(facts, fact_id)
        if fact is not None:
            fact['plots'] = list(dict.fromkeys(list(fact.get('plots') or []) + list(plots)))
            fact_file.save(self.json_ops, facts)

    def get_provenance(self) -> list[dict[str, Any]]:
        """Return the 'why did this fire' log (newest last)."""
        data = self.json_ops.load_json(self.consequences_file)
        return data.get('provenance', [])

    def rearm(self, consequence_id: str) -> dict[str, Any]:
        """A fired consequence waits again: the moment was wrong (the GM's veto),
        or it is meant to happen once more. What its effects did stays done (a
        clock it started runs on). Returns the consequence; raises ValueError."""
        data = self.json_ops.load_json(self.consequences_file)
        c, error = self._find_active(data, consequence_id)
        if not c:
            raise ValueError(error)
        if not c.get('fired'):
            raise ValueError(f"[{c['id']}] hasn't fired: it is waiting already.")
        del c['fired']
        self.json_ops.save_json(self.consequences_file, data)
        return c

    def tick_from_session(self, on_the_way: bool = False) -> dict[str, list[dict[str, Any]]]:
        """Build world_state from current campaign state, then tick(). `on_the_way`
        (a journey's time, gm-session.sh move --takes): the character is at no place
        and nobody is present, so only the time can fire a consequence."""
        overview = self.json_ops.load_json("campaign-overview.json") or {}
        pos = overview.get("player_position", {})
        location = pos.get("current_location", "") if isinstance(pos, dict) else ""
        npcs = self.json_ops.load_json("npcs.json") or {}
        present = list(npcs_present(npcs, location, overview.get("scene")).keys())
        if on_the_way:                       # no place; only the party travels along
            location = ""
            present = list(npcs_present(npcs, "", overview.get("scene")).keys())
        world_state = {
            "location": location,
            "time": overview.get("time_of_day", ""),
            "game_time": overview.get("game_time", ""),
            "date": overview.get("current_date", ""),
            "present_npcs": present,
            "events": [],
        }
        return self.tick(world_state)

    def resolve(self, consequence_id: str) -> bool:
        """
        Resolve a consequence by ID
        """
        data = self.json_ops.load_json(self.consequences_file)
        target, error = self._find_active(data, consequence_id)
        if not target:
            print(f"[ERROR] {error}")
            return False

        resolved = None
        remaining = []

        for c in data.get('active', []):
            if c is target:
                resolved = c
                resolved['resolved'] = self.json_ops.get_timestamp()
                if 'resolved' not in data:
                    data['resolved'] = []
                data['resolved'].append(resolved)
            else:
                remaining.append(c)

        if resolved:
            data['active'] = remaining
            if self.json_ops.save_json(self.consequences_file, data):
                print(f"[SUCCESS] Resolved: {resolved['consequence']}")
                return True
        else:
            print(f"[ERROR] Consequence '{consequence_id}' not found")

        return False

    def list_resolved(self) -> list[dict[str, Any]]:
        """
        Get all resolved consequences
        """
        data = self.json_ops.load_json(self.consequences_file)
        return data.get('resolved', [])


def describe_effects(effects) -> str:
    """What a consequence's effects will do when it fires, in words, or ''.

    Shown wherever pending consequences are listed, so the GM can see that a
    firing starts a clock or spreads a fact before deciding anything about it.
    """
    parts = []
    for e in effects or []:
        if not isinstance(e, dict):
            continue
        if e.get('type') == 'start_clock':
            n = int(e.get('segments', 1))
            size = f"{n} segment{'s' if n != 1 else ''}"
            if e.get('on') == 'event':
                when = "advanced by hand"
            elif e.get('due_in'):
                when = f"full {e['due_in']} after it fires"
            elif e.get('due'):
                when = f"full at {e['due']}"
            else:  # a time clock without a due time: one day per segment
                when = f"full {n} day{'s' if n != 1 else ''} after it fires"
            text = (f"starts clock '{e.get('name')}'" + (f" ({e['text']})" if e.get('text') else "")
                    + f" ({size}, {when})")
            if e.get('consequence'):
                text += f", and when it is full: {e['consequence']}"
            parts.append(text)
        elif e.get('type') == 'tell':
            parts.append(f"tells {e.get('fact')} to {', '.join(e.get('holders') or [])}")
        elif e.get('type') == 'rule':
            parts.append(_rule_words(e))
    return "; ".join(parts)


def _rule_words(e: dict[str, Any]) -> str:
    """'Standing of faction:police -3', 'Standing of faction:kin: point +1'."""
    whose = f" of {e['of']}" if e.get('of') else ""
    if 'change' in e:
        how = f"set to {e['set']}" if 'set' in e else f"{e['by']:+d}"
        return f"{e['change']}{whose}{' ' + e['axis'] if e.get('axis') else ''} {how}"
    if 'rate_of' in e:
        how = [f"rate {e['by']:+d}" if 'by' in e else "",
               f"point {e['toward']}" if 'toward' in e else "",
               f"point {e['shift']:+d}" if 'shift' in e else ""]
        return f"{e['rate_of']}{whose}: {', '.join(h for h in how if h)}"
    if 'state' in e:
        return f"{e['state']}{whose} to {e['to']}"
    field = 'add' if 'add' in e else 'remove'
    return f"{e['tokens']}{whose}: {field} " + ", ".join(f"{n} {k}" for k, n in e[field].items())


def _rule_effects(raws) -> list[dict[str, Any]]:
    """--rule-effect '<json>'...: each a world rule's effect, as a consequence effect."""
    import json

    from cli_output import emit_error
    out = []
    for raw in raws:
        try:
            given = json.loads(raw)
        except ValueError as error:
            sys.exit(emit_error(f"--rule-effect is JSON, e.g. '{{\"change\": \"Standing\", "
                                f"\"of\": \"faction:police\", \"by\": -3}}': {error}"))
        if not isinstance(given, dict):
            sys.exit(emit_error("--rule-effect is one JSON object"))
        out.append({'type': 'rule', **given})
    return out


AFTER_FIRING = ("it fires once: play it out, then gm-consequence.sh resolve <id>; "
                "wrong moment: gm-consequence.sh rearm <id>")


def print_fired(fired: list[dict[str, Any]]) -> None:
    """Human output for consequences fired by an event or by hand."""
    if not fired:
        return
    print(f"[REACTIVITY] fired these {len(fired)}")
    for c in fired:
        print(f"  [{c['id']}] {c['consequence']}")
        print(f"      ↳ fired because: {c['match_reason']} ({AFTER_FIRING})")
        for line in c.get('effects_done', []):
            print(f"      ↳ {line}")


def _print_tick_report(result: dict[str, list[dict[str, Any]]]) -> None:
    """Human CLI for tick(): what fired."""
    fired = result.get('fired') or []
    if not fired:
        print("[REACTIVITY] (nothing triggered here)")
        return
    print_fired(fired)


def main():
    """CLI interface for consequence management"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Consequence management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    # Add consequence
    add_parser = subparsers.add_parser('add', help='Add new consequence')
    add_parser.add_argument('description', help='Consequence description')
    add_parser.add_argument('trigger', help='Trigger condition (free-text)')
    add_parser.add_argument('--trigger-type', dest='trigger_type', action='append',
                            choices=list(ConsequenceManager.TRIGGER_TYPES),
                            help='Structured trigger type (enables auto-firing). Repeat with '
                                 '--match for several triggers; any one fires it.')
    add_parser.add_argument('--match', action='append',
                            help='Structured trigger match value, one per --trigger-type, in order')
    add_parser.add_argument('--offscreen', action='store_true',
                            help="It happens where the character isn't: when it fires, time "
                                 "doesn't stop for it (it goes into the timeline)")
    add_parser.add_argument('--plot', action='append', dest='plots', default=[],
                            help='The plot it belongs to (repeatable)')
    add_parser.add_argument('--tells', metavar='FACT_ID',
                            help='When it fires, these holders (--to) learn this fact')
    add_parser.add_argument('--to', action='append', default=[], metavar='HOLDER',
                            help='Who learns the --tells fact (repeatable)')
    add_parser.add_argument('--rule-effect', dest='rule_effects', action='append', default=[],
                            metavar='JSON',
                            help='When it fires, a world rule\'s effect (repeatable), e.g. '
                                 '\'{"change": "Standing", "of": "faction:police", "by": -3}\' '
                                 'or \'{"rate_of": "Standing", "of": "faction:kin", "shift": 1}\'')
    add_parser.add_argument('--starts-clock', dest='starts_clock', metavar='NAME',
                            help='When it fires, start this clock (unless it already exists)')
    add_parser.add_argument('--clock-text', dest='clock_text',
                            help='What the started clock is about')
    add_parser.add_argument('--clock-segments', dest='clock_segments', type=int, default=1)
    add_parser.add_argument('--clock-on', dest='clock_on', default='time', choices=['time', 'event'])
    add_parser.add_argument('--clock-due-in', dest='clock_due_in',
                            help='Time clock: due this long after the consequence fires, e.g. 3d')
    add_parser.add_argument('--clock-due', dest='clock_due', help='Time clock: due at "YYYY-MM-DD HH:MM"')
    add_parser.add_argument('--clock-consequence', dest='clock_consequence',
                            help='What happens when the started clock fills')

    # Check pending
    subparsers.add_parser('check', help='Check pending consequences')

    # Tick (reactivity): fire matching consequences for the current scene
    subparsers.add_parser('tick', help='Fire consequences whose triggers match the current scene')

    subparsers.add_parser('log', help='Why each consequence fired')
    rearm_parser = subparsers.add_parser('rearm', help='A fired consequence waits again')
    rearm_parser.add_argument('id', help='Consequence ID (a unique prefix is enough)')

    # Fire by hand
    fire_parser = subparsers.add_parser('fire', help='Fire a consequence by hand (its condition happened)')
    fire_parser.add_argument('id', help='Consequence ID (a unique prefix is enough)')
    fire_parser.add_argument('--reason', help='What happened that fired it')
    fire_parser.add_argument('--by', dest='by_fact', help='Id of the recorded fact that fulfilled it (f17)')

    # Resolve
    resolve_parser = subparsers.add_parser('resolve', help='Resolve a consequence')
    resolve_parser.add_argument('id', help='Consequence ID')

    # List resolved
    subparsers.add_parser('list-resolved', help='List resolved consequences')

    from cli_output import emit_error
    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = ConsequenceManager()

    triggers, effects = [], []
    if args.action == 'add':
        types, matches = args.trigger_type or [], args.match or []
        if len(types) != len(matches):
            sys.exit(emit_error(f"{len(types)} --trigger-type but {len(matches)} --match: "
                                f"give exactly one --match per --trigger-type, in the same order"))
        triggers = [{'type': t, 'match': m} for t, m in zip(types, matches, strict=True)]
        clock_flags = [args.clock_due_in, args.clock_due, args.clock_consequence, args.clock_text]
        if any(clock_flags) and not args.starts_clock:
            sys.exit(emit_error("--clock-... options describe the clock that --starts-clock starts; "
                                "give --starts-clock \"<name>\" too"))
        effects = []
        if bool(args.tells) != bool(args.to):
            sys.exit(emit_error("--tells <fact id> and --to <holder> go together"))
        if args.tells:
            effects.append({'type': 'tell', 'fact': args.tells, 'holders': args.to})
        effects += _rule_effects(args.rule_effects)
        if args.starts_clock:
            effect = {'type': 'start_clock', 'name': args.starts_clock,
                      'segments': args.clock_segments, 'on': args.clock_on}
            for key, value in (('due_in', args.clock_due_in), ('due', args.clock_due),
                               ('consequence', args.clock_consequence), ('text', args.clock_text)):
                if value:
                    effect[key] = value
            effects.append(effect)

    if args.action == 'add':
        if not manager.add_consequence(args.description, args.trigger,
                                       triggers=triggers,
                                       effects=effects, plots=args.plots,
                                       offscreen=args.offscreen):
            sys.exit(1)

    elif args.action == 'check':
        pending = manager.check_pending()
        if not pending:
            print("No pending consequences")
        else:
            print(f"{len(pending)} pending consequences:")
            for c in pending:
                then = describe_effects(c.get('effects'))
                if c.get('fired'):
                    print(f"  [{c['id']}] FIRED, not resolved yet: {c['consequence']} "
                          f"(because: {c['fired'].get('reason', '?')})")
                    continue
                print(f"  [{c['id']}] {c['consequence']} (triggers: {c['trigger']})"
                      + (f"; when it fires, {then}" if then else ""))

    elif args.action == 'tick':
        _print_tick_report(manager.tick_from_session())

    elif args.action == 'log':
        prov = manager.get_provenance()
        if not prov:
            print("No reactive firings logged")
        else:
            print(f"{len(prov)} reactive firing(s):")
            for p in prov:
                print(f"  [{p['id']}] {p['consequence']}")
                print(f"      ↳ {p['reason']} @ {p['fired_at']}")

    elif args.action == 'rearm':
        try:
            c = manager.rearm(args.id)
        except ValueError as error:
            print(f"[ERROR] {error}", file=sys.stderr)
            sys.exit(1)
        print(f"[SUCCESS] [{c['id']}] waits again: {c['consequence']} (triggers: {c['trigger']})")

    elif args.action == 'fire':
        hit = manager.fire(args.id, args.reason, args.by_fact)
        if not hit:
            sys.exit(1)
        print_fired([hit])

    elif args.action == 'resolve':
        if not manager.resolve(args.id):
            sys.exit(1)

    elif args.action == 'list-resolved':
        resolved = manager.list_resolved()
        if resolved:
            print(json.dumps(resolved, indent=2))
        else:
            print("No resolved consequences")


if __name__ == "__main__":
    main()
