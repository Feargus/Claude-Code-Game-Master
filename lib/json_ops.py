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
    """A file that exists but can't be read. Reading it as empty would let the
    next save write over everything in it, so the command stops instead."""


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
        Save data to JSON file with atomic write
        Returns True on success, False on failure
        """
        filepath = self._resolve_path(filename)

        try:
            # Write to temp file first for atomic operation
            temp_path = filepath.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)

            # Atomic rename
            temp_path.replace(filepath)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save {filename}: {e}")
            # Clean up temp file if it exists
            temp_path = filepath.with_suffix('.tmp')
            if temp_path.exists():
                temp_path.unlink()
            return False

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
