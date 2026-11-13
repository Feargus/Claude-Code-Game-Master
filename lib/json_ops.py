#!/usr/bin/env python3
"""
JSON operations module for GM tools
Provides safe JSON read/write/update operations with proper error handling.
Import-only: the tools reach campaign files through the managers.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone


class JsonFileError(RuntimeError):
    """A file that exists but can't be read, or one that can't be written. Reading
    a damaged file as empty would let the next save write over everything in it,
    and carrying on after a failed write would report success for something that
    isn't on disk, so the command stops instead."""


def _plain_error(kind, error, traceback):
    """Show an unhandled JsonFileError as one plain message, not a traceback."""
    if issubclass(kind, JsonFileError):
        print(f"[ERROR] {error}", file=sys.stderr)
        sys.exit(1)
    _previous_hook(kind, error, traceback)


_previous_hook = sys.excepthook
sys.excepthook = _plain_error


class JsonOperations:
    """Safe JSON file operations for world state management"""

    def __init__(self, world_state_dir: str = "world-state"):
        self.world_state_dir = Path(world_state_dir)
        # Guard the str(None) trap: a manager constructed with no active
        # campaign passes "None", and the eager mkdir would create ./None/.
        # Reads then return defaults (path doesn't exist); writes fail loudly.
        if str(world_state_dir) != "None":
            self.world_state_dir.mkdir(parents=True, exist_ok=True)

    def load_json(self, filename: str, default: Any = None) -> Any:
        """The file's content, or `default` ({} if not given) if it doesn't exist.

        A file that exists but isn't valid JSON (a hand edit gone wrong, a file
        cut short) raises JsonFileError: returning the default would let the
        caller save over the whole file.
        """
        filepath = self._resolve_path(filename)

        if not filepath.exists():
            if default is None:
                default = {}
            return default

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise JsonFileError(
                f"{filepath} is not valid JSON ({e.msg} at line {e.lineno}, column {e.colno}). "
                f"Nothing was changed. Repair the file, or get the last committed version "
                f"back from git, then run the command again.") from e
        except (OSError, UnicodeDecodeError) as e:
            raise JsonFileError(f"Can't read {filepath}: {e}. Nothing was changed.") from e

    def save_json(self, filename: str, data: Any, indent: int = 2) -> bool:
        """
        Save data to a JSON file, written to a temp file and moved into place, so
        the file is either the old one or the new one, never half of each.

        Returns True. A write that fails (no space, no permission, data that
        isn't JSON) raises JsonFileError and leaves the file as it was: it used
        to print an error and return False, which most callers never looked at,
        so a command could go on and report success.
        """
        filepath = self._resolve_path(filename)
        temp_path = filepath.with_suffix('.tmp')

        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            temp_path.replace(filepath)
        except (OSError, TypeError, ValueError) as e:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise JsonFileError(
                f"Can't write {filepath}: {e}. That file is as it was before; anything the "
                f"command saved before this point is kept, so check the result before "
                f"running it again.") from e
        return True

    def update_json(self, filename: str, updates: Dict, path: List[str] = None) -> bool:
        """
        Update JSON file with partial data
        If path is provided, updates nested structure at that path
        """
        data = self.load_json(filename)

        if path:
            # Navigate to nested path
            current = data
            for key in path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Update at the target path
            if isinstance(updates, dict) and isinstance(current.get(path[-1]), dict):
                current[path[-1]].update(updates)
            else:
                current[path[-1]] = updates
        else:
            # Update root level
            if isinstance(data, dict) and isinstance(updates, dict):
                data.update(updates)
            else:
                data = updates

        return self.save_json(filename, data)

    def check_exists(self, filename: str, key: str, path: List[str] = None) -> bool:
        """
        Check if a key exists in JSON file
        If path is provided, checks at that nested path
        """
        data = self.load_json(filename)

        if path:
            # Navigate to nested path
            current = data
            for p in path:
                if not isinstance(current, dict) or p not in current:
                    return False
                current = current[p]

            return isinstance(current, dict) and key in current
        else:
            return isinstance(data, dict) and key in data

    def _resolve_path(self, filename: str) -> Path:
        """Resolve file path relative to world state directory"""
        if os.path.isabs(filename):
            return Path(filename)
        return self.world_state_dir / filename

    @staticmethod
    def get_timestamp() -> str:
        """Get ISO format timestamp"""
        return datetime.now(timezone.utc).isoformat()
