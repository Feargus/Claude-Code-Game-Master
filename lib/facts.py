#!/usr/bin/env python3
"""The facts file: one list of facts, in the order they were recorded.

`facts.json` in a campaign's folder is a plain list; a fact's id ("f12") counts
them up, so the list is in id order. Every script that reads or writes the facts
goes through this module, which imports only json_ops.py, so each can import it
at the top. A file that holds its facts by category is refused.

`removed-facts.json` holds the facts the GM removed (`gm-note.sh remove`), each
with when it was removed. Nothing reads them in play; they keep their ids, so an
id is never given twice.

Recording facts and looking them up is note_manager.py (`gm-note.sh`).
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from json_ops import JsonFileError

FILE = "facts.json"
REMOVED = "removed-facts.json"


class FactsError(JsonFileError):
    """A facts file that can't be used. The message says why. Like any file that
    can't be read, it stops the command with one plain message (json_ops.py)."""


def as_list(data: Any, where: str = FILE) -> list[dict[str, Any]]:
    """The content of a facts file as its list of facts. An empty file's content
    ({} or nothing) is no facts; the old form, by category, raises FactsError."""
    if not data:
        return []
    if isinstance(data, list):
        return data
    raise FactsError(
        f"{where} holds its facts by category, a form that no longer loads: start a new "
        f"campaign (/gm).")


def load(json_ops) -> list[dict[str, Any]]:
    """Every fact, oldest first. `json_ops` is a JsonOperations on the campaign's folder."""
    return as_list(json_ops.load_json(FILE, default=[]), str(json_ops.world_state_dir / FILE))


def save(json_ops, facts: list[dict[str, Any]]) -> None:
    json_ops.save_json(FILE, facts)


def number(fact: dict[str, Any]) -> int:
    """The number in a fact's id: 12 for "f12"; 0 for a fact without a usable id."""
    digits = str(fact.get("id", ""))[1:]
    return int(digits) if digits.isdigit() else 0


def newest_first(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(facts, key=number, reverse=True)


def by_id(facts: list[dict[str, Any]], fact_id: str) -> dict[str, Any] | None:
    """The fact with this id, or None."""
    return next((f for f in facts if f.get("id") == fact_id), None)


def load_removed(json_ops) -> list[dict[str, Any]]:
    """The facts the GM removed, oldest removal first."""
    value = json_ops.load_json(REMOVED, default=[])
    return value if isinstance(value, list) else []


def save_removed(json_ops, removed: list[dict[str, Any]]) -> None:
    json_ops.save_json(REMOVED, removed)


def next_id(facts: list[dict[str, Any]], removed=()) -> str:
    """The id the next fact gets: one past every fact recorded, removed ones too."""
    return f"f{max((number(f) for f in list(facts) + list(removed)), default=0) + 1}"
