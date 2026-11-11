#!/usr/bin/env python3
"""
JSON operations module for GM tools
Provides safe JSON read/write/update operations with proper error handling
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
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

    def append_to_list(self, filename: str, item: Any, path: List[str] = None) -> bool:
        """
        Append item to a list in JSON file
        If path is provided, appends to list at that path
        """
        data = self.load_json(filename)

        if path:
            # Navigate to nested path
            current = data
            for key in path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Ensure target is a list
            if path[-1] not in current:
                current[path[-1]] = []
            if not isinstance(current[path[-1]], list):
                print(f"[ERROR] Target at {'.'.join(path)} is not a list")
                return False

            current[path[-1]].append(item)
        else:
            # Root must be a list
            if not isinstance(data, list):
                print(f"[ERROR] Root of {filename} is not a list")
                return False
            data.append(item)

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

    def get_value(self, filename: str, key: str = None, path: List[str] = None) -> Any:
        """
        Get value from JSON file
        If path is provided, gets value at that nested path
        If key is provided, gets that specific key
        """
        data = self.load_json(filename)

        if path:
            # Navigate to nested path
            current = data
            for p in path:
                if not isinstance(current, dict) or p not in current:
                    return None
                current = current[p]
            data = current

        if key:
            if isinstance(data, dict):
                return data.get(key)
            return None

        return data

    def delete_key(self, filename: str, key: str, path: List[str] = None) -> bool:
        """
        Delete a key from JSON file
        If path is provided, deletes from that nested path
        """
        data = self.load_json(filename)

        if path:
            # Navigate to nested path
            current = data
            for p in path[:-1]:
                if not isinstance(current, dict) or p not in current:
                    return False
                current = current[p]

            if isinstance(current.get(path[-1]), dict) and key in current[path[-1]]:
                del current[path[-1]][key]
            else:
                return False
        else:
            if isinstance(data, dict) and key in data:
                del data[key]
            else:
                return False

        return self.save_json(filename, data)

    def _resolve_path(self, filename: str) -> Path:
        """Resolve file path relative to world state directory"""
        if os.path.isabs(filename):
            return Path(filename)
        return self.world_state_dir / filename

    @staticmethod
    def get_timestamp() -> str:
        """Get ISO format timestamp"""
        return datetime.now(timezone.utc).isoformat()


# Convenience functions for command-line usage
def main():
    """CLI interface for JSON operations"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='JSON file operations')
    parser.add_argument('action', choices=['get', 'set', 'update', 'append', 'exists', 'delete'])
    parser.add_argument('filename', help='JSON file name')
    parser.add_argument('--key', help='Key to operate on')
    parser.add_argument('--value', help='Value to set (JSON string)')
    parser.add_argument('--path', help='Nested path (dot-separated)')
    parser.add_argument('--world-state-dir', default='world-state', help='World state directory')

    args = parser.parse_args()

    ops = JsonOperations(args.world_state_dir)
    path = args.path.split('.') if args.path else None

    if args.action == 'get':
        result = ops.get_value(args.filename, args.key, path)
        print(json.dumps(result, indent=2))

    elif args.action == 'set' or args.action == 'update':
        if not args.value:
            print("[ERROR] --value required for set/update")
            sys.exit(1)
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value  # Treat as string if not valid JSON

        if args.key:
            updates = {args.key: value}
        else:
            updates = value

        if ops.update_json(args.filename, updates, path):
            print("[SUCCESS] Updated")
        else:
            sys.exit(1)

    elif args.action == 'append':
        if not args.value:
            print("[ERROR] --value required for append")
            sys.exit(1)
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value

        if ops.append_to_list(args.filename, value, path):
            print("[SUCCESS] Appended")
        else:
            sys.exit(1)

    elif args.action == 'exists':
        if not args.key:
            print("[ERROR] --key required for exists check")
            sys.exit(1)
        exists = ops.check_exists(args.filename, args.key, path)
        print("true" if exists else "false")
        sys.exit(0 if exists else 1)

    elif args.action == 'delete':
        if not args.key:
            print("[ERROR] --key required for delete")
            sys.exit(1)
        if ops.delete_key(args.filename, args.key, path):
            print("[SUCCESS] Deleted")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()