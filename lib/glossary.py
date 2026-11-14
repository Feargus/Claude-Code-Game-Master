#!/usr/bin/env python3
"""The glossary: the world's own words, each with a short description.

Lantern papers, the Test, a ghost-dub: the terms a world invents for its things,
institutions and slang. The term is the entry's id; its description says what it
means here, in a line. `plots` will link an entry to the plots it belongs to, as
facts, consequences and clocks will be (empty until plots have ids).

Kept in world-bible.json under "glossary":

    {"glossary": {"Lantern papers": {"description": "The certificate of a ghost; ...",
                                     "plots": []}}}

The brief lists the terms; `gm-glossary.sh show "<term>"` gives the meaning.

    gm-glossary.sh list
    gm-glossary.sh show "<term>"
    gm-glossary.sh add "<term>" "<description>"
    gm-glossary.sh describe "<term>" "<new description>"
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

BIBLE = "world-bible.json"
MAX_TERM_CHARS = 40


class GlossaryError(ValueError):
    """A glossary change that can't be made. The message says how to fix it."""


def glossary(json_ops) -> dict[str, dict[str, Any]]:
    """{term: entry}, in the order they were added; {} if there is none."""
    value = (json_ops.load_json(BIBLE) or {}).get("glossary") or {}
    return value if isinstance(value, dict) else {}


def terms(json_ops) -> list[str]:
    """The terms, for the brief. A campaign from before the glossary has only the
    voice's word list ("in-world terms to favor"); its words count as terms."""
    found = list(glossary(json_ops))
    if found:
        return found
    voice = (json_ops.load_json(BIBLE) or {}).get("voice") or {}
    return [str(v).strip() for v in voice.get("vocab") or [] if str(v).strip()]


def find(json_ops, raw: str) -> str:
    """The stored term `raw` names (case and spacing ignored), or ''."""
    wanted = " ".join(str(raw or "").split()).lower()
    return next((t for t in glossary(json_ops) if t.lower() == wanted), "")


def check_entries(value: Any) -> list[str]:
    """Problems with a glossary as stored (for world_bible.validate_bible)."""
    if not isinstance(value, dict):
        return ['glossary must be an object {"<term>": {"description": "...", "plots": []}}']
    errors = []
    for term, entry in value.items():
        if not isinstance(entry, dict) or not str(entry.get("description") or "").strip():
            errors.append(f"glossary '{term}' needs a description")
        elif not isinstance(entry.get("plots", []), list):
            errors.append(f"glossary '{term}': plots must be a list")
    return errors


def _term(raw: str) -> str:
    term = " ".join(str(raw or "").split())
    if not term:
        raise GlossaryError("A glossary entry needs a term.")
    if len(term) > MAX_TERM_CHARS or ":" in term:
        raise GlossaryError(f"A term is a word or a short name, at most {MAX_TERM_CHARS} "
                            f"characters and without a colon; what it means goes into the "
                            f"description. Got '{term}'.")
    return term


def _description(raw: str) -> str:
    text = " ".join(str(raw or "").split())
    if not text:
        raise GlossaryError("Say what the term means here, in a line.")
    return text


def _save(json_ops, entries: dict[str, dict[str, Any]]) -> None:
    bible = json_ops.load_json(BIBLE) or {}
    bible["glossary"] = entries
    json_ops.save_json(BIBLE, bible)


def add(json_ops, raw_term: str, description: str) -> str:
    """Add a term. Returns it as stored; raises GlossaryError."""
    term = _term(raw_term)
    taken = find(json_ops, term)
    if taken:
        raise GlossaryError(f"'{taken}' is in the glossary already: "
                            f"gm-glossary.sh describe \"{taken}\" \"...\" to reword it.")
    entries = glossary(json_ops)
    entries[term] = {"description": _description(description), "plots": []}
    _save(json_ops, entries)
    return term


def describe(json_ops, raw_term: str, description: str) -> tuple[str, str]:
    """Reword a term's description. Returns (term, the old description)."""
    term = find(json_ops, raw_term)
    if not term:
        raise GlossaryError(_missing(json_ops, raw_term))
    entries = glossary(json_ops)
    old = entries[term].get("description", "")
    entries[term] = {**entries[term], "description": _description(description)}
    _save(json_ops, entries)
    return term, old


def _missing(json_ops, raw: str) -> str:
    import difflib
    known = list(glossary(json_ops))
    close = difflib.get_close_matches(str(raw).lower(), [t.lower() for t in known], n=3, cutoff=0.6)
    hint = f"; did you mean: {', '.join(t for t in known if t.lower() in close)}?" if close else "."
    return f"No term '{raw}' in the glossary{hint}"


def main() -> int:
    import argparse

    from campaign_manager import CampaignManager
    from json_ops import JsonOperations

    parser = argparse.ArgumentParser(description="The world's own terms")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    sub.add_parser("show").add_argument("term")
    for action in ("add", "describe"):
        p = sub.add_parser(action)
        p.add_argument("term")
        p.add_argument("description")
    args = parser.parse_args()

    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        print("[ERROR] No active campaign.", file=sys.stderr)
        return 1
    ops = JsonOperations(str(campaign))
    try:
        if args.action == "list":
            for term, entry in glossary(ops).items():
                print(f"{term}: {entry.get('description', '')}")
            if not glossary(ops):
                print("The glossary is empty.")
        elif args.action == "show":
            term = find(ops, args.term)
            if not term:
                raise GlossaryError(_missing(ops, args.term))
            print(f"{term}: {glossary(ops)[term].get('description', '')}")
        elif args.action == "add":
            term = add(ops, args.term, args.description)
            print(f"[SUCCESS] Added to the glossary: {term}")
        else:
            term, old = describe(ops, args.term, args.description)
            print(f"[SUCCESS] {term} reworded (was: {old})")
    except GlossaryError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
