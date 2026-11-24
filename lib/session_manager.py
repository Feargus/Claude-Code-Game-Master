#!/usr/bin/env python3
"""
Session management module for GM tools
Handles the start of play, party movement and the session brief
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager


class SessionManager(EntityManager):
    """Manage session operations. Inherits from EntityManager for common functionality."""

    # Per-campaign play-style defaults. `action_menu` controls whether the GM ends
    # each beat with exactly three numbered choices (on) or an open prompt (off). Stored
    # under overview.preferences; surfaced in get_full_context so the GM honors it.
    # `beat_length` picks the pacing line. Same storage + surfacing.
    # `rag_inspiration` makes the GM pull source passages every beat or so for
    # grounded narration detail rather than improvising from memory. Currently
    # disabled by default (2026-11-08: the campaigns have no book text, so each
    # search was wasted); re-enable with "rag_inspiration": true here or in a
    # campaign's overview.preferences.
    DEFAULT_PREFERENCES = {"action_menu": True,
                           "beat_length": "adaptive", "rag_inspiration": False}

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)

        # Additional paths specific to session management
        self._wsd = world_state_dir  # passed through to sibling managers
        self.world_state_dir = self.campaign_dir  # Alias for compatibility

        # Core files
        self.campaign_file = "campaign-overview.json"

        # Character file (single character per campaign)
        self.character_file = self.campaign_dir / "character.json"

    def get_timestamp(self) -> str:
        """Get formatted timestamp"""
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # ==================== Play-Style Preferences ====================

    def get_preferences(self) -> dict[str, Any]:
        """Return play-style preferences, defaults merged with any saved overrides."""
        campaign = self.json_ops.load_json(self.campaign_file) or {}
        prefs = dict(self.DEFAULT_PREFERENCES)
        saved = campaign.get("preferences")
        if isinstance(saved, dict):
            prefs.update(saved)
        return prefs

    def set_preference(self, key: str, value: Any) -> dict[str, Any]:
        """Persist a single play-style preference; returns the full merged prefs."""
        campaign = self.json_ops.load_json(self.campaign_file) or {}
        prefs = campaign.get("preferences")
        if not isinstance(prefs, dict):
            prefs = {}
        prefs[key] = value
        campaign["preferences"] = prefs
        self.json_ops.save_json(self.campaign_file, campaign)
        return self.get_preferences()

    # ==================== Party Movement ====================

    @staticmethod
    def _normalize_connection_list(connections):
        """Coerce a connections list to {to, ...} dicts; tolerate malformed data.

        Extraction can leave bare-string connection entries. Everything here
        indexes c.get("to"), so coerce strings to {"to": name} and drop junk
        rather than crashing a move. Returns (list, changed_bool).
        """
        if not isinstance(connections, list):
            return [], True
        fixed = []
        changed = False
        for c in connections:
            if isinstance(c, dict):
                fixed.append(c)
            elif isinstance(c, str) and c.strip():
                fixed.append({"to": c.strip()})
                changed = True
            else:
                changed = True  # drop None/other junk
        return fixed, changed

    def check_destination(self, location: str) -> str:
        """The key of a place the party may move to. Raises ValueError for a place
        that isn't recorded, or has no description: a place is written to disk
        before it is narrated (gm-location.sh add / describe)."""
        from world_ids import WorldIds
        name = str(location or "").strip()
        cid, error = WorldIds(self.json_ops).resolve_as(name, ("location",))
        if error:
            raise ValueError(
                f"{error.rstrip('.')}. A new place is added before the party goes there: "
                f"bash tools/gm-location.sh add \"{name}\" \"<where it is>\" "
                f"\"<what it is like, a sentence or two>\", then move.")
        key = cid.partition(":")[2]
        place = (self.json_ops.load_json("locations.json") or {}).get(key) or {}
        if not str(place.get("description") or "").strip():
            raise ValueError(
                f"{key} has no description yet. Write what it is like before narrating it: "
                f"bash tools/gm-location.sh describe \"{key}\" \"<a sentence or two>\", then move.")
        return key

    def _ensure_location_and_connection(self, old_location: str, new_location: str) -> None:
        """
        Add a bidirectional connection between the old and the new place's sites
        if one doesn't exist (the new one is recorded already: check_destination).
        Within one site every location is reached from every other: no connection
        (sites.py).
        """
        import sites
        if sites.same_site(old_location, new_location):
            return
        old_location, new_location = sites.site_of(old_location), sites.site_of(new_location)
        locations = self.json_ops.load_json("locations.json") or {}
        changed = False

        # Add bidirectional connection if old location is valid and known
        if old_location and old_location != "Unknown" and old_location in locations:
            # Coerce malformed entries (bare-string connections from extraction)
            # so a bad data file never hard-crashes a move on c.get("to").
            old_connections, old_fixed = self._normalize_connection_list(
                locations[old_location].get("connections", []))
            new_connections, new_fixed = self._normalize_connection_list(
                locations[new_location].get("connections", []))
            if old_fixed:
                locations[old_location]["connections"] = old_connections
                changed = True
            if new_fixed:
                locations[new_location]["connections"] = new_connections
                changed = True

            # Check if connection from old -> new exists
            if not any(c.get("to") == new_location for c in old_connections):
                old_connections.append({"to": new_location, "path": "traveled"})
                locations[old_location]["connections"] = old_connections
                changed = True

            # Check if connection from new -> old exists
            if not any(c.get("to") == old_location for c in new_connections):
                new_connections.append({"to": old_location, "path": "traveled"})
                locations[new_location]["connections"] = new_connections
                changed = True

        if changed:
            self.json_ops.save_json("locations.json", locations)

    def move_party(self, location: str, with_time: bool = False) -> dict[str, str]:
        """
        Move party to new location (a recorded place with a description, by its
        name or an alias). Returns dict with previous and current location.
        `with_time`: the journey took time, and the line says the time of arrival.
        Raises ValueError (check_destination).
        """
        location = self.check_destination(location)
        campaign = self.json_ops.load_json(self.campaign_file)

        if 'player_position' not in campaign:
            campaign['player_position'] = {}

        old_location = campaign['player_position'].get('current_location', 'Unknown')

        # Connect the two places if they weren't yet
        self._ensure_location_and_connection(old_location, location)

        campaign['player_position']['previous_location'] = old_location
        campaign['player_position']['current_location'] = location
        campaign['player_position']['arrival_time'] = self.get_timestamp()
        # A new scene starts with only the party (gm-scene.sh enter adds others).
        if str(location).lower() != str(old_location).lower():
            campaign['scene'] = {'location': location, 'present': []}

        self.json_ops.save_json(self.campaign_file, campaign)


        result = {
            "previous_location": old_location,
            "current_location": location
        }

        arrival = ""
        if with_time:
            from game_time import current_time
            from time_manager import describe
            moment = current_time(self.json_ops)
            arrival = f", {describe(moment)}" if moment else ""
        print(f"[SUCCESS] Moved to {location}{arrival}")
        return result

    def get_full_context(self) -> str:
        """The session brief (lib/brief.py)."""
        from brief import Brief
        return Brief(self).text()

    def _scene(self):
        """campaign-overview.json's scene list (see gm-scene.sh), or None."""
        return (self.json_ops.load_json(self.campaign_file) or {}).get("scene")


def main():
    """CLI interface for session management"""
    import argparse

    parser = argparse.ArgumentParser(description='Session management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    subparsers.add_parser('location', help='the current location, alone on a line')

    # Move party
    move_parser = subparsers.add_parser('move', help='Move party to location')
    move_parser.add_argument('location', nargs='+', help='Location name')
    move_parser.add_argument('--with-time', action='store_true',
                             help='The journey took time: the line gives the time of arrival')
    move_parser.add_argument('--check', action='store_true',
                             help='Only check that the place can be moved to (before travel time passes)')

    # Full session context
    subparsers.add_parser('context', help='The start brief (one-command startup)')

    header_parser = subparsers.add_parser('header', help='The header line, from the records')
    header_parser.add_argument('--full', action='store_true',
                               help='with the date and credits (the start of a session)')

    choices_parser = subparsers.add_parser('choices', help='Toggle the action-menu play style')
    choices_parser.add_argument('value', nargs='?', default='show',
                                choices=['on', 'off', 'toggle', 'show'],
                                help='on | off | toggle | show (default: show)')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = SessionManager()

    if args.action == 'header':
        import header
        print(header.line(manager.json_ops, full=args.full))
        return
    if args.action == 'move':
        location = ' '.join(args.location)
        try:
            if args.check:
                manager.check_destination(location)
                return
            manager.move_party(location, with_time=args.with_time)
        except ValueError as error:
            print(f"[ERROR] {error}", file=sys.stderr)
            sys.exit(1)
        return                               # move_party printed the one line

    if args.action == 'location':
        pos = (manager.json_ops.load_json(manager.campaign_file) or {}).get('player_position') or {}
        print(pos.get('current_location') or '' if isinstance(pos, dict) else '')

    elif args.action == 'context':
        print(manager.get_full_context())

    elif args.action == 'choices':
        val = getattr(args, 'value', 'show')
        current = manager.get_preferences().get('action_menu', True)
        if val != 'show':
            new = (not current) if val == 'toggle' else (val == 'on')
            manager.set_preference('action_menu', new)
            current = new
        state = 'on' if current else 'off'
        if val == 'show':
            print(f"Action menu is {state}.")
        else:
            print(f"Action menu turned {state}. "
                  f"{'Beats will end with exactly three numbered choices.' if current else 'Beats will end with an open prompt.'}")


if __name__ == "__main__":
    main()
