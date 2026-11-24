#!/usr/bin/env python3
"""
Campaign management module for GM tools
Handles multi-campaign support with CRUD operations
"""

import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

# The default base dir every manager falls back to when the caller names none.
DEFAULT_WORLD_STATE = "world-state"


def resolve_world_state_base(world_state_dir):
    """Where "the default world-state" points.

    Only the default value is redirectable: GM_WORLD_STATE_BASE moves it (tests
    point the whole system at a tmp tree instead of the player's live campaign).
    A caller that named a directory always gets that directory. Unset, this is
    the literal "world-state" every caller used before.
    """
    if str(world_state_dir) == DEFAULT_WORLD_STATE:
        return os.environ.get("GM_WORLD_STATE_BASE") or DEFAULT_WORLD_STATE
    return world_state_dir


class CampaignManager:
    """Manage multiple campaigns"""

    def __init__(self, world_state_dir: str = DEFAULT_WORLD_STATE):
        self.world_state_dir = Path(resolve_world_state_base(world_state_dir))
        self.campaigns_dir = self.world_state_dir / "campaigns"
        self.active_file = self.world_state_dir / "active-campaign.txt"

        # Ensure directories exist
        self.campaigns_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(name: str) -> str:
        """Normalize a campaign name to its folder slug (matches create()).

        The ONE slug rule for the whole system: lowercase, every run of
        non-alphanumerics becomes a single dash, edge dashes trimmed. Shell
        (`campaign_manager.py slugify`) and extraction (`AgentExtractor.
        _sanitize_name`) both route here, so a punctuated name like
        "Baldur's Gate: Book 1" lands in exactly one directory.

        NEVER returns an empty string. A name with no ASCII alphanumerics at all
        ("龍の伝説", "!!!") gets a deterministic hash slug instead: an empty slug
        would resolve to the campaigns root, and a caller joining it into a path
        would point rm -rf at every campaign.
        """
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        if slug:
            return slug
        digest = hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]
        return f'campaign-{digest}'

    @classmethod
    def _resolve_in(cls, campaigns_dir: Path, name: str) -> str:
        """Resolve a user-supplied name (display name OR slug) to the actual
        campaign folder name under `campaigns_dir`. Returns the slug if no
        exact-folder match exists, so callers still produce a sensible
        '<slug> does not exist' error.

        A name is only an exact match if it names a DIRECT child of
        campaigns_dir. "../rag" and absolute paths are directories too, and a
        caller that joins the result back onto campaigns/ (gm-extract.sh clean
        rm -rf's it) would then delete outside the campaign tree entirely.
        _slugify used to make that impossible by stripping slashes and dots;
        resolving real folder names has to refuse it explicitly.

        Matching runs against the real directory listing rather than is_dir():
        on a case-insensitive filesystem (macOS) is_dir() says yes to "Conan"
        when only "conan" exists, and that wrong spelling then leaks into env
        vars and case-sensitive comparisons. Case variants fall through to the
        slug branch, which lowercases, and land on the canonical folder."""
        name = name.rstrip("/")
        listing = sorted(p.name for p in campaigns_dir.iterdir() if p.is_dir()) \
            if campaigns_dir.is_dir() else []
        if name in listing and (campaigns_dir / name).resolve().parent == campaigns_dir.resolve():
            return name
        slug = cls._slugify(name)
        if slug in listing:
            return slug
        # Folders created under the OLD slug rule kept apostrophes, dots and
        # underscores ("baldur's-gate"), so the current rule no longer points at
        # them and a real campaign reads as "does not exist". Match by comparing
        # slugified folder names — resolves legacy dirs without renaming on disk.
        for existing in listing:
            if cls._slugify(existing) == slug:
                return existing
        return slug

    def _resolve_name(self, name: str) -> str:
        return self._resolve_in(self.campaigns_dir, name)

    def list_campaigns(self) -> list[dict[str, Any]]:
        """
        List all campaigns with their metadata
        Returns list of dicts with name, path, character info
        """
        campaigns = []

        for campaign_dir in sorted(self.campaigns_dir.iterdir()):
            if not campaign_dir.is_dir():
                continue

            campaign_info = {
                "name": campaign_dir.name,
                "path": str(campaign_dir),
            }

            # Try to read campaign overview for more info
            overview_file = campaign_dir / "campaign-overview.json"
            if overview_file.exists():
                try:
                    with open(overview_file, encoding='utf-8') as f:
                        overview = json.load(f)
                    campaign_info["campaign_name"] = overview.get("campaign_name", "Unnamed")
                    campaign_info["current_location"] = overview.get("player_position", {}).get("current_location")
                    bible = campaign_dir / "world-bible.json"
                    if bible.exists():
                        campaign_info["campaign_name"] = (json.loads(bible.read_text(encoding="utf-8"))
                                                          .get("name") or campaign_info["campaign_name"])
                except (OSError, json.JSONDecodeError):
                    campaign_info["campaign_name"] = "Unknown"

            # Try to read character info
            char_file = campaign_dir / "character.json"
            if char_file.exists():
                try:
                    with open(char_file, encoding='utf-8') as f:
                        char = json.load(f)
                    identity = char.get("identity") or {}
                    campaign_info["character"] = {
                        "name": identity.get("name", "Unknown"),
                        "race": identity.get("race", ""),
                        "role": identity.get("role", ""),
                        "level": (char.get("progress") or {}).get("level", 0)
                    }
                except (OSError, json.JSONDecodeError) as e:
                    print(f"[ERROR] Can't read character.json of {campaign_dir.name}: {e}", file=sys.stderr)

            campaigns.append(campaign_info)

        return campaigns

    def _session_file(self) -> Path | None:
        """Where this Claude Code session keeps the campaign it switched to.

        Two sessions playing different campaigns would otherwise switch the one
        shared active campaign under each other. Claude Code gives each session an id
        (CLAUDE_CODE_SESSION_ID); `switch` records the campaign under it, and
        this session reads its own. Without an id, or before a switch, the
        shared active-campaign.txt counts."""
        sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", sid):
            return None
        return self.world_state_dir / "sessions" / sid

    def get_active(self) -> str | None:
        """
        Get the currently active campaign name: this session's own if it
        switched to one (_session_file), else the shared one.
        Returns None if no active campaign is set
        """
        own = self._session_file()
        for path in ([own] if own and own.exists() else []) + [self.active_file]:
            if path.exists():
                return self._existing(path)
        return None

    def _existing(self, path: Path) -> str | None:
        """The campaign named in `path`, if it exists."""
        try:
            campaign_name = path.read_text().strip()
            # Verify the campaign actually exists
            campaign_path = self.campaigns_dir / campaign_name
            if campaign_path.is_dir():
                return campaign_name
            return None
        except OSError:
            return None

    def set_active(self, name: str) -> bool:
        """
        Set the active campaign by name
        Returns True on success, False if campaign doesn't exist
        """
        name = self._resolve_name(name)
        campaign_path = self.campaigns_dir / name
        if not campaign_path.is_dir():
            print(f"[ERROR] Campaign '{name}' does not exist", file=sys.stderr)
            return False

        try:
            self.active_file.write_text(name)
            own = self._session_file()
            if own:
                own.parent.mkdir(exist_ok=True)
                own.write_text(name)
                self._forget_old_sessions(own.parent)
            print(f"[SUCCESS] Active campaign set to: {name}")
            return True
        except OSError as e:
            print(f"[ERROR] Failed to set active campaign: {e}", file=sys.stderr)
            return False

    @staticmethod
    def _forget_old_sessions(folder: Path, days: int = 30) -> None:
        """Sessions' records untouched for `days` are long over: delete them."""
        import time
        cutoff = time.time() - days * 86400
        for record in folder.iterdir():
            with contextlib.suppress(OSError):
                if record.is_file() and record.stat().st_mtime < cutoff:
                    record.unlink()

    def create(self, name: str, campaign_name: str = None) -> Path | None:
        """
        Create a new campaign with empty state files
        name: folder name (typically character name, lowercase with hyphens)
        campaign_name: display name for the campaign
        Returns the campaign path on success, None on failure
        """
        # Normalize name for folder
        safe_name = self._slugify(name)
        campaign_path = self.campaigns_dir / safe_name

        if campaign_path.exists():
            print(f"[ERROR] Campaign '{safe_name}' already exists", file=sys.stderr)
            return None

        try:
            # Create campaign directory structure
            campaign_path.mkdir(parents=True)
            (campaign_path / "extracted").mkdir()

            # Initialize empty state files
            self._init_empty_files(campaign_path, campaign_name or name)

            print(f"[SUCCESS] Created campaign: {safe_name}")
            return campaign_path
        except OSError as e:
            print(f"[ERROR] Failed to create campaign: {e}", file=sys.stderr)
            # Clean up on failure
            if campaign_path.exists():
                shutil.rmtree(campaign_path)
            return None

    def delete(self, name: str, confirm: bool = False) -> bool:
        """
        Delete a campaign and all its data
        Requires confirm=True to actually delete
        Returns True on success
        """
        name = self._resolve_name(name)
        campaign_path = self.campaigns_dir / name

        if not campaign_path.is_dir():
            print(f"[ERROR] Campaign '{name}' does not exist", file=sys.stderr)
            return False

        if not confirm:
            print(f"[ERROR] Deleting {name} ({campaign_path}) can't be undone: add --confirm. "
                  f"Nothing was deleted.", file=sys.stderr)
            return False

        try:
            # If this is the active campaign, clear active file
            if self.get_active() == name:
                self.active_file.unlink(missing_ok=True)

            shutil.rmtree(campaign_path)
            print(f"[SUCCESS] Deleted campaign: {name}")
            return True
        except OSError as e:
            print(f"[ERROR] Failed to delete campaign: {e}", file=sys.stderr)
            return False

    def get_campaign_path(self, name: str = None) -> Path | None:
        """
        Get the path to a campaign folder
        If name is None, returns path to active campaign
        Returns None if campaign doesn't exist
        """
        if name is None:
            name = self.get_active()
            if name is None:
                return None
        else:
            name = self._resolve_name(name)

        campaign_path = self.campaigns_dir / name
        if campaign_path.is_dir():
            return campaign_path
        return None

    def get_active_campaign_dir(self) -> Path | None:
        """
        Get the directory for the active campaign.
        Returns None if no active campaign is set.
        """
        active = self.get_active()
        if active:
            return self.campaigns_dir / active
        return None

    def get_info(self, name: str = None) -> dict[str, Any] | None:
        """
        Get detailed info about a campaign
        If name is None, uses active campaign
        """
        if name is None:
            name = self.get_active()
            if name is None:
                print("[ERROR] No active campaign set", file=sys.stderr)
                return None
        else:
            name = self._resolve_name(name)

        campaign_path = self.campaigns_dir / name
        if not campaign_path.is_dir():
            print(f"[ERROR] Campaign '{name}' does not exist", file=sys.stderr)
            return None

        info = {
            "name": name,
            "path": str(campaign_path),
            "is_active": self.get_active() == name
        }

        # Read campaign overview
        overview_file = campaign_path / "campaign-overview.json"
        if overview_file.exists():
            try:
                with open(overview_file, encoding='utf-8') as f:
                    info["overview"] = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"[ERROR] Can't read campaign-overview.json of {name}: {e}", file=sys.stderr)

        # Read character
        char_file = campaign_path / "character.json"
        if char_file.exists():
            try:
                with open(char_file, encoding='utf-8') as f:
                    info["character"] = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"[ERROR] Can't read character.json of {name}: {e}", file=sys.stderr)

        # Count NPCs, locations, etc.
        for filename in ["npcs.json", "locations.json", "facts.json"]:
            filepath = campaign_path / filename
            if filepath.exists():
                try:
                    with open(filepath, encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, (dict, list)):
                        info[filename.replace('.json', '_count')] = len(data)
                except (OSError, json.JSONDecodeError) as e:
                    print(f"[ERROR] Can't read {filename} of {name}: {e}", file=sys.stderr)

        return info

    def init_campaign_files(self, campaign_path: Path, campaign_name: str, preserve_existing: bool = False):
        """
        Initialize campaign files in an existing directory.
        Public wrapper for _init_empty_files for use by other modules.

        Args:
            campaign_path: Path to the campaign directory
            campaign_name: Display name for the campaign
            preserve_existing: If True, don't overwrite files that already exist
        """
        self._init_empty_files(campaign_path, campaign_name, preserve_existing)

    def _init_empty_files(self, campaign_path: Path, campaign_name: str, preserve_existing: bool = False):
        """Initialize empty state files for a new campaign

        Args:
            campaign_path: Path to the campaign directory
            campaign_name: Display name for the campaign
            preserve_existing: If True, don't overwrite files that already exist
        """

        # campaign-overview.json
        overview_path = campaign_path / "campaign-overview.json"
        if not preserve_existing or not overview_path.exists():
            overview = {
                "campaign_name": campaign_name,
                "current_date": "",
                "time_of_day": "",
                "player_position": {
                    "current_location": None,
                    "previous_location": None
                },
                "current_character": None
            }
            with open(overview_path, 'w', encoding='utf-8') as f:
                json.dump(overview, f, indent=2)

        # npcs.json
        npcs_path = campaign_path / "npcs.json"
        if not preserve_existing or not npcs_path.exists():
            with open(npcs_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)

        # locations.json
        locations_path = campaign_path / "locations.json"
        if not preserve_existing or not locations_path.exists():
            with open(locations_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)

        # facts.json
        facts_path = campaign_path / "facts.json"
        if not preserve_existing or not facts_path.exists():
            with open(facts_path, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)                # one list of facts (facts.py)

        # consequences.json
        consequences_path = campaign_path / "consequences.json"
        if not preserve_existing or not consequences_path.exists():
            with open(consequences_path, 'w', encoding='utf-8') as f:
                json.dump({"active": [], "resolved": []}, f, indent=2)


def main():
    """CLI interface for campaign management"""
    import argparse

    parser = argparse.ArgumentParser(description='Campaign management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    # List campaigns
    subparsers.add_parser('list', help='List all campaigns')

    # Get active campaign
    subparsers.add_parser('active', help='Show active campaign')

    # Switch campaign
    switch_parser = subparsers.add_parser('switch', help='Switch active campaign')
    switch_parser.add_argument('name', help='Campaign name to switch to')

    # Create campaign
    create_parser = subparsers.add_parser('create', help='Create new campaign')
    create_parser.add_argument('name', help='Campaign folder name (character name)')
    create_parser.add_argument('--campaign-name', help='Display name for the campaign')

    # Delete campaign
    delete_parser = subparsers.add_parser('delete', help='Delete a campaign')
    delete_parser.add_argument('name', help='Campaign name to delete')
    delete_parser.add_argument('--confirm', action='store_true', help='Confirm deletion')

    # Get campaign info
    info_parser = subparsers.add_parser('info', help='Get campaign info')
    info_parser.add_argument('name', nargs='?', help='Campaign name (defaults to active)')

    # Get campaign path
    path_parser = subparsers.add_parser('path', help='Get campaign directory path')
    path_parser.add_argument('name', nargs='?', help='Campaign name (defaults to active)')

    # Slugify a name (shell callers use this instead of their own tr|sed)
    slugify_parser = subparsers.add_parser('slugify', help='Print the folder slug for a campaign name')
    slugify_parser.add_argument('name', help='Campaign display name or slug')

    # Resolve a name to the folder that EXISTS on disk (slugify is for new names)
    resolve_parser = subparsers.add_parser(
        'resolve',
        help='Print the existing campaign folder for a name (exit 3, no output, if none matches)')
    resolve_parser.add_argument('name', help='Campaign display name, slug, or legacy folder name')
    resolve_parser.add_argument('--world-state', default='world-state',
                                help='World state directory (default: world-state)')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    if args.action == 'slugify':
        # Pure string work — answer before constructing a manager, which would
        # create world-state/campaigns relative to the caller's cwd.
        print(CampaignManager._slugify(args.name))
        return

    if args.action == 'resolve':
        # Read-only lookup — answered before constructing a manager, whose
        # __init__ would mkdir world-state/campaigns under the caller's cwd.
        # Exit 3 (not 1) so a shell caller can tell "no such campaign" apart
        # from "the interpreter could not run at all".
        campaigns_dir = Path(resolve_world_state_base(args.world_state)) / "campaigns"
        resolved = CampaignManager._resolve_in(campaigns_dir, args.name)
        if not (campaigns_dir / resolved).is_dir():
            sys.exit(3)
        print(resolved)
        return

    manager = CampaignManager()

    if args.action == 'list':
        campaigns = manager.list_campaigns()
        if not campaigns:
            print("No campaigns found")
            print("Create one with: gm-campaign.sh create <name>")
        else:
            active = manager.get_active()
            print(f"{'':2}{'NAME':24}CHARACTER")
            print("-" * 60)
            for c in campaigns:
                marker = "*" if c["name"] == active else " "
                char_info = ""
                if "character" in c:
                    char = c["character"]
                    who = " ".join(x for x in (char['race'], char['role']) if x)
                    char_info = f"{char['name']}" + (f" ({who})" if who else "") + f" L{char['level']}"
                where = f", at {c['current_location']}" if c.get("current_location") else ""
                print(f"{marker} {c['name']:24}{char_info}{where}")
            print()
            if active:
                print(f"* = active campaign ({active})")

    elif args.action == 'active':
        active = manager.get_active()
        if active:
            print(active)
        else:
            print("No active campaign set")
            sys.exit(1)

    elif args.action == 'switch':
        if not manager.set_active(args.name):
            sys.exit(1)

    elif args.action == 'create':
        campaign_name = args.campaign_name or args.name
        path = manager.create(args.name, campaign_name)
        if not path:
            sys.exit(1)
        print(f"Campaign created at: {path}")

    elif args.action == 'delete':
        if not manager.delete(args.name, confirm=args.confirm):
            sys.exit(1)

    elif args.action == 'info':
        info = manager.get_info(args.name)
        if not info:
            sys.exit(1)
        print(json.dumps(info, indent=2))

    elif args.action == 'path':
        path = manager.get_campaign_path(args.name)
        if path:
            print(path)
        else:
            print("Campaign not found", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
