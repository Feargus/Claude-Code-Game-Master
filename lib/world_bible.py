#!/usr/bin/env python3
"""
The Book Bible — the structured fidelity spine of a world.

world-bible.json is what makes "playing Dune" feel unmistakably like Dune rather
than d20-fantasy-in-a-desert. It captures VOICE, TONE, THEMES, the links between FACTIONS
(the factions themselves are in factions.json), GEOGRAPHY (as a place graph), and TIMELINE, and is the canonical spine loaded at session start. The import pipeline
(import-longcontext-read) auto-drafts it; here we define + validate the shape and
ship a hand-authored DCC bible to prove it.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import world_rules
from campaign_manager import CampaignManager
from json_ops import JsonOperations

_REQUIRED = ('name', 'voice', 'tone', 'themes', 'factions', 'geography')


def _is_graph(g: Any) -> bool:
    return isinstance(g, dict) and isinstance(g.get('nodes'), list) and isinstance(g.get('edges'), list)


def _is_links(g: Any) -> bool:
    """The bible's factions: the links between them (`edges`); the factions
    themselves are in factions.json. Older bibles list them as `nodes` too."""
    return isinstance(g, dict) and isinstance(g.get('edges'), list) \
        and isinstance(g.get('nodes', []), list)


def validate_bible(bible: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(bible, dict):
        return False, ['world-bible must be an object']
    for key in _REQUIRED:
        if key not in bible:
            errors.append(f'missing required key: {key}')
    if not isinstance(bible.get('themes', []), list):
        errors.append('themes must be a list')
    if 'geography' in bible and not _is_graph(bible['geography']):
        errors.append('geography must be a graph {nodes:[], edges:[]}')
    if 'factions' in bible and not _is_links(bible['factions']):
        errors.append('factions must be {edges:[]}: the links between factions (the factions '
                      'themselves are in factions.json)')
    voice = bible.get('voice')
    if voice is not None and not isinstance(voice, dict):
        errors.append('voice must be an object (style/sample_passages)')
    if 'glossary' in bible:
        from glossary import check_entries
        errors.extend(check_entries(bible['glossary']))
    return (len(errors) == 0), errors


class WorldBible:
    """Loads + exposes a campaign's world-bible.json."""

    def __init__(self, world_state_dir: str = None):
        base = world_state_dir or "world-state"
        cm = CampaignManager(base)
        self.campaign_dir = cm.get_active_campaign_dir()
        self.json_ops = JsonOperations(str(self.campaign_dir))
        self.bible = self.json_ops.load_json("world-bible.json") or {}

    def exists(self) -> bool:
        return bool(self.bible)

    def validate(self) -> tuple[bool, list[str]]:
        return validate_bible(self.bible)

    def voice(self) -> dict[str, Any]:
        return self.bible.get('voice', {})

    def factions(self) -> dict[str, Any]:
        """The links between factions (an older bible's faction nodes too)."""
        return self.bible.get('factions', {'edges': []})

    def geography(self) -> dict[str, Any]:
        return self.bible.get('geography', {'nodes': [], 'edges': []})

    # --- draft-then-confirm gate ---
    def is_confirmed(self) -> bool:
        """A newly-drafted bible is `confirmed: false` until a human approves it.

        Legacy campaigns / hand-authored bibles (no flag) count as confirmed so the
        gate only blocks freshly auto-drafted worlds.
        """
        return bool(self.bible.get('confirmed', True))

    def is_playable(self) -> bool:
        """A world is playable unless it has an unconfirmed auto-drafted bible."""
        if not self.bible:
            return True  # no bible (e.g. /new-game) -> nothing to confirm
        return self.is_confirmed()

    def confirm(self) -> bool:
        """Mark the drafted world approved + persist."""
        self.bible['confirmed'] = True
        return self.json_ops.save_json("world-bible.json", self.bible)

    def _faction_names(self) -> list[str]:
        """factions.json's, or an older bible's nodes (conan's live bible lists them as
        bare strings, not {name: ...}: a review screen shows what is there)."""
        import factions
        if factions.has_file(self.json_ops):
            return [f.get('name', fid) for fid, f in factions.load(self.json_ops).items()]
        return [n.get('name') if isinstance(n, dict) else n
                for n in self.factions().get('nodes', [])]

    def review_summary(self) -> dict[str, Any]:
        """The human-facing draft to review before play (voice, factions, the world's
        own rules: those are the ruleset's, world_rules.py)."""
        return {
            'name': self.bible.get('name'),
            'tone': self.bible.get('tone'),
            'voice_style': self.voice().get('style'),
            'themes': self.bible.get('themes', []),
            'factions': self._faction_names(),
            'rules': [r['name'] for r in world_rules.rules(self.json_ops)],
            'confirmed': self.is_confirmed(),
        }


def main():
    import argparse
    import json

    from cli_output import emit, emit_error, strip_json_flag, wants_json

    parser = argparse.ArgumentParser(description="World Bible")
    parser.add_argument('action', nargs='?', default='validate',
                        choices=['validate', 'show', 'review', 'confirm'])
    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))

    wb = WorldBible()
    if args.action == 'validate':
        ok, errs = wb.validate()
        result = {'valid': ok, 'errors': errs, 'name': wb.bible.get('name')}
        if json_mode:
            emit(result, json_mode=True)
        else:
            print(json.dumps(result, indent=2))
        sys.exit(0 if ok else 1)
    elif args.action == 'review':
        # The human-facing draft. A drafted world is `confirmed: false` until the
        # PLAYER approves what this prints — never confirm on their behalf.
        summary = wb.review_summary()
        if json_mode:
            emit(summary, json_mode=True)
        else:
            print(json.dumps(summary, indent=2))
    elif args.action == 'confirm':
        if not wb.exists():
            sys.exit(emit_error('no world-bible.json to confirm', json_mode))
        wb.confirm()
        emit({'confirmed': True, 'name': wb.bible.get('name')},
             message=f"World bible confirmed: {wb.bible.get('name')}", json_mode=json_mode)
    else:
        if json_mode:
            emit(wb.bible, json_mode=True)
        else:
            print(json.dumps(wb.bible, indent=2))


if __name__ == "__main__":
    main()
