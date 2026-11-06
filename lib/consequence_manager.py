#!/usr/bin/env python3
"""
Consequence management module for GM tools
Handles tracking future events and consequences
"""

import sys
import uuid
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager, npcs_present


class ConsequenceManager(EntityManager):
    """Manage consequence/event tracking. Inherits from EntityManager for common functionality."""

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
    TRIGGER_TYPES = ('on_location', 'on_npc', 'on_time', 'on_event', 'on_death')
    # Event triggers fire once, inside the command that makes the change
    # (fire_event), never on the scene check that moves and time steps run.
    # on_event is the GM's: each recorded fact lists the consequences waiting
    # on one (waiting_on_event), and the GM fires a fitting one by hand.
    EVENT_TRIGGER_TYPES = ('on_death', 'on_event')
    # A trigger either matches (1.0) or not (0.0). There is no word matching:
    # free-text conditions are on_event triggers, judged by the GM.
    FIRE_SCORE = 0.5

    def add_consequence(self, description: str, trigger: str,
                        trigger_type: str = None, match: str = None,
                        expiry: str = None, triggers: List[Dict[str, str]] = None) -> str:
        """
        Add a new consequence.

        Free-text `trigger` is always kept (human-readable). Without structured
        triggers it becomes the consequence's on_event trigger: the event it waits
        for, judged by the GM when facts are recorded. STRUCTURED triggers, any one
        of which fires it:
          triggers:     list of {"type": one of TRIGGER_TYPES, "match": value compared
                        against world state (location/npc/time/event keyword)}
          trigger_type, match: shorthand for a single trigger (added to `triggers`)
          expiry:       optional date or condition after which the consequence ages out
        Structured fields are additive; legacy consequences omit them.

        Returns the consequence ID, or "" if refused.
        """
        triggers = [dict(t) for t in (triggers or [])]
        if trigger_type:
            triggers.append({'type': trigger_type, 'match': match})
        if not triggers and str(trigger or '').strip():
            triggers = [{'type': 'on_event', 'match': str(trigger).strip()}]
        for t in triggers:
            if t.get('type') not in self.TRIGGER_TYPES:
                print(f"[ERROR] Unknown trigger type '{t.get('type')}'. Use one of: "
                      f"{', '.join(self.TRIGGER_TYPES)}", file=sys.stderr)
                return ""
            if not t.get('match'):
                print(f"[ERROR] Trigger {t['type']} needs a --match value.", file=sys.stderr)
                return ""
            if t['type'] == 'on_death':
                who = self._death_target(t['match'])
                if not who:
                    print(f"[ERROR] on_death matches an NPC's name or 'player'; no NPC "
                          f"'{t['match']}' exists. Create the NPC first (gm-npc.sh create).",
                          file=sys.stderr)
                    return ""
                t['match'] = who
            if t['type'] == 'on_time':
                ok, _ = self.validators.validate_time_of_day(t['match'])
                if not ok:
                    print(f"[ERROR] on_time matches the time-of-day word (small hours, dawn, morning, "
                          f"noon, afternoon, evening, dusk, night, midnight), not '{t['match']}'. For a "
                          f"deadline at a date and time, use a clock: gm-clock.sh add \"<name>\" 1 "
                          f"--due \"YYYY-MM-DD HH:MM\" --consequence \"<what happens>\"", file=sys.stderr)
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
        if expiry is not None:
            consequence['expiry'] = expiry

        if 'active' not in data:
            data['active'] = []
        data['active'].append(consequence)

        if self.json_ops.save_json(self.consequences_file, data):
            print(f"[SUCCESS] Added consequence [{consequence_id}]: {description} (triggers: {trigger})")
            return consequence_id
        return ""

    def check_pending(self, world_state: Dict[str, Any] = None,
                      limit: int = 2) -> List[Dict[str, Any]]:
        """
        Pending consequences.

        - No world_state  -> the raw active list (legacy accessor).
        - With world_state -> every consequence that MATCHES now (score >= FIRE_SCORE),
          each annotated with `match_reason`, sorted by confidence. The top `limit`
          are the fire slice; the rest are disclosed (`matched_not_fired`) rather
          than dropped. Structured triggers match exactly; legacy free-text
          triggers are scored fuzzily. Expired consequences (past their `expiry`)
          are auto-archived to resolved.

        world_state keys (all optional): location (str), present_npcs (list[str]),
        time (str), events (list[str]), date (str).

        Firing does NOT remove a consequence — the GM vetoes for timing or resolves
        it explicitly; the tick layer stamps last_fired_key so a beat doesn't stutter.
        """
        data = self.json_ops.load_json(self.consequences_file)
        active = data.get('active', [])

        if world_state is None:
            return active

        matched = []
        survivors = []
        expired = []
        for c in active:
            if self._is_expired(c, world_state):
                aged = dict(c)
                aged['expired'] = self.json_ops.get_timestamp()
                expired.append(aged)
                continue
            survivors.append(c)
            score, reason = self._evaluate_trigger(c, world_state)
            if score >= self.FIRE_SCORE:
                hit = dict(c)
                hit['match_reason'] = reason
                matched.append((score, hit))

        if expired:
            data['active'] = survivors
            data.setdefault('resolved', []).extend(expired)
            self.json_ops.save_json(self.consequences_file, data)

        matched.sort(key=lambda t: t[0], reverse=True)
        out = []
        for i, (_, hit) in enumerate(matched):
            if i >= limit:
                hit['matched_not_fired'] = True
            out.append(hit)
        return out

    @staticmethod
    def _world_text(world_state: Dict[str, Any]) -> str:
        parts = [
            str(world_state.get('location', '')),
            str(world_state.get('time', '')),
            str(world_state.get('date', '')),
            ' '.join(str(x) for x in world_state.get('present_npcs', []) or []),
            ' '.join(str(x) for x in world_state.get('events', []) or []),
        ]
        return ' '.join(parts).lower()

    def _is_expired(self, consequence: Dict[str, Any], world_state: Dict[str, Any]) -> bool:
        expiry = consequence.get('expiry')
        if not expiry:
            return False
        # Whole-word match, not substring: --expiry "dawn" must not self-archive
        # the moment the party stands anywhere named "Dawnhollow".
        import re
        pattern = r'\b' + re.escape(str(expiry).lower()) + r'\b'
        return re.search(pattern, self._world_text(world_state)) is not None

    def _death_target(self, name: str) -> str:
        """The canonical on_death match for `name`: 'player', an NPC key, or '' if unknown."""
        from entity_aliases import resolve_entity_name
        if str(name).strip().lower() == 'player':
            return 'player'
        character = self.json_ops.load_json("character.json") or {}
        if character.get('name') and str(name).strip().lower() == str(character['name']).lower():
            return 'player'
        npcs = self.json_ops.load_json("npcs.json") or {}
        return resolve_entity_name(name, npcs) or ''

    @staticmethod
    def structured_triggers(consequence: Dict[str, Any]) -> List[Dict[str, str]]:
        """The consequence's structured triggers as a list of {"type", "match"}.

        New entries store a `triggers` list. Older entries are read the same way:
        a single `trigger_type` + `match` as a one-item list, and a bare free-text
        `trigger` as an on_event trigger.
        """
        if isinstance(consequence.get('triggers'), list):
            return [t for t in consequence['triggers']
                    if isinstance(t, dict) and t.get('type') and t.get('match')]
        if consequence.get('trigger_type') and consequence.get('match'):
            return [{'type': consequence['trigger_type'], 'match': consequence['match']}]
        if str(consequence.get('trigger', '')).strip():
            return [{'type': 'on_event', 'match': str(consequence['trigger']).strip()}]
        return []

    @staticmethod
    def _evaluate_one(ttype: str, raw_match: str, world_state: Dict[str, Any]) -> str:
        """The reason a single structured trigger matches now, or '' if it doesn't."""
        match = str(raw_match).lower()
        if ttype == 'on_location' and match in str(world_state.get('location', '')).lower():
            return f"at location matching '{raw_match}'"
        if ttype == 'on_npc':
            npcs = ' '.join(str(x) for x in world_state.get('present_npcs', []) or []).lower()
            if match in npcs:
                return f"NPC matching '{raw_match}' present"
        if ttype == 'on_time' and match in str(world_state.get('time', '')).lower():
            return f"time matching '{raw_match}'"
        return ''

    def _evaluate_trigger(self, consequence: Dict[str, Any], world_state: Dict[str, Any]):
        """Return (score, reason): (1.0, why) if any state trigger matches now, else (0.0, '').

        Event triggers (on_death, on_event) never match here; they fire where
        the event is recorded.
        """
        for t in self.structured_triggers(consequence):
            reason = self._evaluate_one(t['type'], t['match'], world_state)
            if reason:
                return 1.0, reason
        return 0.0, ''

    def tick(self, world_state: Dict[str, Any], limit: int = 2) -> Dict[str, List[Dict[str, Any]]]:
        """Evaluate all active consequences; fire the top `limit` that are new here.

        Same scene (location|time|date) will not re-stamp a consequence that already
        fired on this ctx_key — it is disclosed as already-fired, not suppressed.
        Remaining matches are disclosed, not dropped.
        Expired consequences are archived. Newly fired items get last_fired_key +
        provenance; the GM may still veto narratively — they stay active either way.
        """
        data = self.json_ops.load_json(self.consequences_file)
        active = data.get('active', [])
        # Pre-fire snapshot for one-beat rollback (shallow copies; fields are scalar).
        pre_active = [dict(c) for c in active]
        pre_resolved = [dict(c) for c in data.get('resolved', [])]
        ctx_key = "|".join([
            str(world_state.get('location', '')),
            str(world_state.get('time', '')),
            str(world_state.get('date', '')),
        ]).lower()

        survivors, expired = [], []
        matches = []
        for c in active:
            if self._is_expired(c, world_state):
                aged = dict(c)
                aged['expired'] = self.json_ops.get_timestamp()
                expired.append(aged)
                continue
            survivors.append(c)
            score, reason = self._evaluate_trigger(c, world_state)
            if score >= self.FIRE_SCORE:
                matches.append((score, c, reason))

        matches.sort(key=lambda t: t[0], reverse=True)

        already_fired, new_matches = [], []
        for score, c, reason in matches:
            hit = dict(c)
            hit['match_reason'] = reason
            if c.get('last_fired_key') == ctx_key:
                hit['already_fired'] = True
                already_fired.append(hit)
            else:
                new_matches.append((c, reason, hit))

        fired, disclosed = [], []
        for i, (c, reason, hit) in enumerate(new_matches):
            if i < limit:
                c['last_fired_key'] = ctx_key  # stamp the live object (in survivors)
                stamped = dict(c)
                stamped['match_reason'] = reason
                fired.append(stamped)
            else:
                disclosed.append(hit)

        if expired or fired:
            data['active'] = survivors
            if expired:
                data.setdefault('resolved', []).extend(expired)
            # Provenance ("why did this fire") + one-beat rollback snapshot.
            data['_snapshot'] = {'active': pre_active, 'resolved': pre_resolved}
            now = self.json_ops.get_timestamp()
            prov = data.setdefault('provenance', [])
            for hit in fired:
                prov.append({
                    'id': hit['id'],
                    'consequence': hit['consequence'],
                    'reason': hit['match_reason'],
                    'ctx_key': ctx_key,
                    'fired_at': now,
                })
            self.json_ops.save_json(self.consequences_file, data)
        return {
            'fired': fired,
            'disclosed': disclosed,
            'already_fired': already_fired,
        }

    def _stamp_fired(self, data: Dict[str, Any], consequence: Dict[str, Any],
                     reason: str, ctx_key: str) -> Dict[str, Any]:
        """Mark `consequence` (a live object in data['active']) as fired and log why.

        Shared by event triggers and manual firing. The caller snapshots and saves.
        """
        consequence['last_fired_key'] = ctx_key
        prov = data.setdefault('provenance', [])
        prov.append({
            'id': consequence['id'],
            'consequence': consequence['consequence'],
            'reason': reason,
            'ctx_key': ctx_key,
            'fired_at': self.json_ops.get_timestamp(),
        })
        hit = dict(consequence)
        hit['match_reason'] = reason
        return hit

    @staticmethod
    def _snapshot(data: Dict[str, Any]) -> None:
        """Keep the pre-fire state for a one-beat rollback."""
        data['_snapshot'] = {'active': [dict(c) for c in data.get('active', [])],
                             'resolved': [dict(c) for c in data.get('resolved', [])]}

    def fire_event(self, ttype: str, value: str, reason: str) -> List[Dict[str, Any]]:
        """An event happened (e.g. on_death, 'Wren'): fire every active consequence
        with a trigger of that type whose match equals `value`. Called by the command
        that makes the change. Returns the fired consequences.
        """
        data = self.json_ops.load_json(self.consequences_file)
        value_l = str(value).lower()
        hits = [c for c in data.get('active', [])
                if any(t['type'] == ttype and str(t['match']).lower() == value_l
                       for t in self.structured_triggers(c))]
        if not hits:
            return []
        self._snapshot(data)
        ctx_key = f"event|{ttype}|{value_l}"
        fired = [self._stamp_fired(data, c, reason, ctx_key) for c in hits]
        self.json_ops.save_json(self.consequences_file, data)
        return fired

    def waiting_on_event(self) -> List[Dict[str, Any]]:
        """Active consequences the GM must match to events by judgment.

        Those with an on_event trigger (old entries with only a free-text trigger
        count as one). Each comes back with `awaits`: the event it waits for, in words.
        """
        data = self.json_ops.load_json(self.consequences_file)
        out = []
        for c in data.get('active', []):
            events = [t['match'] for t in self.structured_triggers(c) if t['type'] == 'on_event']
            if events:
                hit = dict(c)
                hit['awaits'] = ' / '.join(events)
                out.append(hit)
        return out

    def _find_fact(self, fact_id: str) -> Dict[str, Any]:
        """The fact with this id, or {}."""
        facts = self.json_ops.load_json("facts.json") or {}
        for items in facts.values():
            for f in items if isinstance(items, list) else []:
                if isinstance(f, dict) and f.get('id') == fact_id:
                    return f
        return {}

    def _find_active(self, data: Dict[str, Any], consequence_id: str):
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
             by_fact: str = None) -> Dict[str, Any]:
        """The GM fires a consequence by hand (its condition happened in the story).

        `by_fact` names the recorded fact that fulfilled it; the provenance log
        keeps the link. Firing is not resolving: it stays active until `resolve`.
        Returns the fired consequence, or {} if refused.
        """
        data = self.json_ops.load_json(self.consequences_file)
        c, error = self._find_active(data, consequence_id)
        if not c:
            print(f"[ERROR] {error}", file=sys.stderr)
            return {}
        fact = {}
        if by_fact:
            fact = self._find_fact(by_fact)
            if not fact:
                print(f"[ERROR] No fact '{by_fact}'", file=sys.stderr)
                return {}
        if not reason:
            reason = f"fact {by_fact}: {fact['fact']}" if fact else "fired by the GM"
        self._snapshot(data)
        hit = self._stamp_fired(data, c, reason, f"manual|{c['id']}")
        if by_fact:
            data['provenance'][-1]['fact'] = by_fact
        self.json_ops.save_json(self.consequences_file, data)
        return hit

    def get_provenance(self) -> List[Dict[str, Any]]:
        """Return the 'why did this fire' log (newest last)."""
        data = self.json_ops.load_json(self.consequences_file)
        return data.get('provenance', [])

    def rollback_last(self) -> bool:
        """Undo the most recent reactive beat (restore active/resolved to pre-fire)."""
        data = self.json_ops.load_json(self.consequences_file)
        snap = data.get('_snapshot')
        if not snap:
            print("[ERROR] No reactive beat to roll back")
            return False
        data['active'] = snap.get('active', data.get('active', []))
        data['resolved'] = snap.get('resolved', data.get('resolved', []))
        data['_snapshot'] = None
        if self.json_ops.save_json(self.consequences_file, data):
            print("[SUCCESS] Rolled back the last reactive beat")
            return True
        return False

    def tick_from_session(self, limit: int = 2) -> Dict[str, List[Dict[str, Any]]]:
        """Build world_state from current campaign state, then tick()."""
        overview = self.json_ops.load_json("campaign-overview.json") or {}
        pos = overview.get("player_position", {})
        location = pos.get("current_location", "") if isinstance(pos, dict) else ""
        npcs = self.json_ops.load_json("npcs.json") or {}
        present = list(npcs_present(npcs, location).keys())
        world_state = {
            "location": location,
            "time": overview.get("time_of_day", ""),
            "date": overview.get("current_date", ""),
            "present_npcs": present,
            "events": [],
        }
        return self.tick(world_state, limit=limit)

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

    def list_resolved(self) -> List[Dict[str, Any]]:
        """
        Get all resolved consequences
        """
        data = self.json_ops.load_json(self.consequences_file)
        return data.get('resolved', [])


def print_fired(fired: List[Dict[str, Any]]) -> None:
    """Human output for consequences fired by an event or by hand."""
    if not fired:
        return
    print(f"[REACTIVITY] fired these {len(fired)}")
    for c in fired:
        print(f"  [{c['id']}] {c['consequence']}")
        print(f"      ↳ fired because: {c['match_reason']} (resolve it once it has played out)")


def print_waiting(fact_id: str, waiting: List[Dict[str, Any]]) -> None:
    """After a fact is recorded: the consequences the GM must check it against."""
    if not waiting:
        return
    print(f"Waiting on an event — does {fact_id} fulfil one? (your judgment; usually none)")
    for c in waiting:
        print(f"  [{c['id']}] awaits \"{c['awaits']}\" → {c['consequence']}")
    by = fact_id if ',' not in fact_id else "<the fact's id>"
    print(f"  If one does: bash tools/gm-consequence.sh fire <id> --by {by}")


def _print_tick_report(result: Dict[str, List[Dict[str, Any]]]) -> None:
    """Human CLI for tick(): fire slice plus disclosed remainder."""
    fired = result.get('fired') or []
    disclosed = result.get('disclosed') or []
    already = result.get('already_fired') or []
    if not (fired or disclosed or already):
        print("[REACTIVITY] (nothing triggered here)")
        return
    extra = ""
    if disclosed:
        names = [c.get('consequence', c.get('id', '?')) for c in disclosed]
        extra = f", {len(disclosed)} more matched: [{', '.join(names)}]"
    print(f"[REACTIVITY] fired these {len(fired)}{extra}")
    for c in fired:
        print(f"  [{c['id']}] {c['consequence']}")
        print(f"      ↳ fired because: {c['match_reason']} (veto if the timing's wrong)")
    if disclosed:
        print("  matched-not-fired:")
        for c in disclosed:
            print(f"  [{c['id']}] {c['consequence']}")
            print(f"      ↳ {c.get('match_reason', '')}")
    if already:
        print("  already fired here:")
        for c in already:
            print(f"  [{c['id']}] {c['consequence']}")
            print(f"      ↳ {c.get('match_reason', '')} (already fired here)")


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
    add_parser.add_argument('--expiry', help='Optional expiry (date or condition)')

    # Check pending
    subparsers.add_parser('check', help='Check pending consequences')

    # Tick (reactivity): fire matching consequences for the current scene
    subparsers.add_parser('tick', help='Fire consequences whose triggers match the current scene')

    # Provenance + rollback
    subparsers.add_parser('log', help='Show the reactive firing provenance log')
    subparsers.add_parser('rollback', help='Undo the most recent reactive beat')

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

    from cli_output import wants_json, strip_json_flag, emit, emit_error
    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = ConsequenceManager()

    triggers = []
    if args.action == 'add':
        types, matches = args.trigger_type or [], args.match or []
        if len(types) != len(matches):
            sys.exit(emit_error(f"{len(types)} --trigger-type but {len(matches)} --match: "
                                f"give exactly one --match per --trigger-type, in the same order",
                                json_mode=json_mode))
        triggers = [{'type': t, 'match': m} for t, m in zip(types, matches)]

    if json_mode and args.action == 'add':
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):  # keep stdout JSON-only
            cid = manager.add_consequence(args.description, args.trigger,
                                          triggers=triggers, expiry=args.expiry)
        if cid:
            emit({"id": cid}, json_mode=True)
        else:
            sys.exit(emit_error("failed to add consequence", json_mode=True))
        return
    if json_mode and args.action == 'check':
        emit({"pending": manager.check_pending()}, json_mode=True)
        return
    if json_mode and args.action == 'tick':
        emit(manager.tick_from_session(), json_mode=True)
        return

    if args.action == 'add':
        if not manager.add_consequence(args.description, args.trigger,
                                       triggers=triggers, expiry=args.expiry):
            sys.exit(1)

    elif args.action == 'check':
        pending = manager.check_pending()
        if not pending:
            print("No pending consequences")
        else:
            print(f"{len(pending)} pending consequences:")
            for c in pending:
                print(f"  [{c['id']}] {c['consequence']} (triggers: {c['trigger']})")

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

    elif args.action == 'rollback':
        if not manager.rollback_last():
            sys.exit(1)

    elif args.action == 'fire':
        hit = manager.fire(args.id, args.reason, args.by_fact)
        if not hit:
            sys.exit(1)
        if json_mode:
            emit({"fired": [hit]}, json_mode=True)
        else:
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
