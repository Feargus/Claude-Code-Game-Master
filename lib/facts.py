#!/usr/bin/env python3
"""The facts file: one list of facts, in the order they were recorded.

`facts.json` in a campaign's folder is a plain list; a fact's id ("f12") counts
them up, so the list is in id order. Every script that reads or writes the facts
goes through this module, which imports only json_ops.py, so each can import it
at the top.

Until 2026-11-16 the file held one list per category ("session_events",
"plot_local", ...). Nothing read the categories any more, and every reader had
to merge the lists and sort them again. A file in that form is refused: the
campaigns from before were retired, not converted.

Recording facts and looking them up is note_manager.py (`gm-note.sh`).
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from json_ops import JsonFileError

FILE = "facts.json"


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
        f"{where} holds its facts by category, the form used until 2026-11-16. Campaigns "
        f"from before that were retired and no longer load: start a new one (/gm).")


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


def next_id(facts: list[dict[str, Any]]) -> str:
    """The id the next fact gets."""
    return f"f{max((number(f) for f in facts), default=0) + 1}"
