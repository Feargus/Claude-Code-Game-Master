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

    # ==================== Session Lifecycle ====================

    def start_session(self) -> dict[str, Any]:
        """A short world-state summary for the start of play. Writes nothing: there
        is no session log (since 2026-11-14 plots carry the story)."""
        summary = {
            "facts_count": self._count_items("facts.json"),
            "npcs_count": self._count_items("npcs.json"),
            "locations_count": self._count_items("locations.json"),
            "current_location": self._get_current_location(),
            "active_character": self._get_active_character(),
            "timestamp": self.get_timestamp()
        }

        return summary

    def get_status(self) -> dict[str, Any]:
        """
        Get current campaign status
        """
        return {
            "facts_count": self._count_items("facts.json"),
            "npcs_count": self._count_items("npcs.json"),
            "locations_count": self._count_items("locations.json"),
            "current_location": self._get_current_location(),
            "active_character": self._get_active_character(),
        }

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
        Add a bidirectional connection between the old and the new location if
        one doesn't exist (the new one is recorded already: check_destination).
        """
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

    def move_party(self, location: str) -> dict[str, str]:
        """
        Move party to new location (a recorded place with a description, by its
        name or an alias). Returns dict with previous and current location.
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

        print(f"[SUCCESS] Party moved from {old_location} to {location}")
        return result

    def get_full_context(self) -> str:
        """The session brief (lib/brief.py)."""
        from brief import Brief
        return Brief(self).text()

    def _scene(self):
        """campaign-overview.json's scene list (see gm-scene.sh), or None."""
        return (self.json_ops.load_json(self.campaign_file) or {}).get("scene")

    def _count_items(self, filename: str) -> int:
        """Count items in a JSON file"""
        data = self.json_ops.load_json(filename)
        if isinstance(data, dict):
            return len(data)
        if isinstance(data, list):
            return len(data)
        return 0

    def _get_current_location(self) -> str | None:
        """Get current party location"""
        campaign = self.json_ops.load_json(self.campaign_file)
        return campaign.get('player_position', {}).get('current_location')

    def _get_active_character(self) -> str | None:
        """Get active character name"""
        campaign = self.json_ops.load_json(self.campaign_file)
        return campaign.get('current_character')


def main():
    """CLI interface for session management"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Session management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    # Start session
    subparsers.add_parser('start', help='Start new session')

    # Status
    subparsers.add_parser('status', help='Get campaign status')

    # Move party
    move_parser = subparsers.add_parser('move', help='Move party to location')
    move_parser.add_argument('location', nargs='+', help='Location name')
    move_parser.add_argument('--check', action='store_true',
                             help='Only check that the place can be moved to (before travel time passes)')

    # Full session context
    subparsers.add_parser('context', help='The start brief (one-command startup)')

    choices_parser = subparsers.add_parser('choices', help='Toggle the action-menu play style')
    choices_parser.add_argument('value', nargs='?', default='show',
                                choices=['on', 'off', 'toggle', 'show'],
                                help='on | off | toggle | show (default: show)')

    from cli_output import emit, strip_json_flag, wants_json
    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = SessionManager()

    if json_mode and args.action == 'status':
        emit(manager.get_status(), json_mode=True)
        return
    if json_mode and args.action == 'context':
        emit({"context": manager.get_full_context()}, json_mode=True)
        return
    if args.action == 'move':
        location = ' '.join(args.location)
        try:
            if args.check:
                manager.check_destination(location)
                return
            result = manager.move_party(location)
        except ValueError as error:
            print(f"[ERROR] {error}", file=sys.stderr)
            sys.exit(1)
        if json_mode:
            emit(result, json_mode=True)
        return                               # move_party printed the one line

    if args.action == 'start':
        summary = manager.start_session()
        print(json.dumps(summary, indent=2))

    elif args.action == 'status':
        status = manager.get_status()
        print(json.dumps(status, indent=2))

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
