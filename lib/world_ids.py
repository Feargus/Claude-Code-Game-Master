#!/usr/bin/env python3
"""Ids for what a fact can be about or held by.

    player                  the player character
    npc:<key>               an NPC, by its key in npcs.json
    location:<key>          a location, by its key in locations.json
    street, public          rungs of the knowledge ladder

Faction and item ids come with those systems. The stored id uses the exact
existing key ("npc:Auntie Ro"), so there is no separate table to keep in sync.
Input is forgiving: "npc:auntie-ro", "Auntie Ro" or an alias resolve to the same
id, and the player's name resolves to `player`. Anything unknown is refused
with close matches, so a typo never becomes a new, empty id.
"""

import difflib
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from entity_aliases import normalize_entity_name, resolve_entity_name

RUNGS = ("street", "public")
KINDS = ("npc", "location")
LATER = {"faction": "factions", "item": "items with ids"}


class WorldIds:
    """Resolve ids against one campaign's files (a JsonOperations on its folder)."""

    def __init__(self, json_ops):
        self.json_ops = json_ops
        self._tables = None

    def _load(self) -> Dict[str, dict]:
        if self._tables is None:
            self._tables = {
                "npc": self.json_ops.load_json("npcs.json") or {},
                "location": self.json_ops.load_json("locations.json") or {},
            }
        return self._tables

    def player_name(self) -> str:
        return str((self.json_ops.load_json("character.json") or {}).get("name") or "")

    def all_ids(self) -> List[str]:
        """Every id that exists now, in a fixed order."""
        tables = self._load()
        return (["player"] + [f"{kind}:{key}" for kind in KINDS for key in tables[kind]]
                + list(RUNGS))

    def _is_player(self, text: str) -> bool:
        name = self.player_name()
        low = text.strip().lower()
        return low == "player" or bool(name) and (
            low == name.lower() or normalize_entity_name(text) == normalize_entity_name(name))

    def _suggest(self, text: str, kinds=KINDS) -> str:
        """', did you mean: …?' with up to three close ids, or ''."""
        tables = self._load()
        choices = {}
        for kind in kinds:
            for key in tables[kind]:
                choices[normalize_entity_name(key) or key.lower()] = f"{kind}:{key}"
        query = normalize_entity_name(text) or text.lower()
        close = difflib.get_close_matches(query, list(choices), n=3, cutoff=0.75)
        # A first name or part of a key ("Ilse" for "Doc Ilse Varga") counts too.
        close += [n for n in choices if query and query in n.split() and n not in close]
        return f"; did you mean: {', '.join(choices[n] for n in close[:3])}?" if close else ""

    def resolve(self, raw: str) -> Tuple[str, str]:
        """(canonical id, '') or ('', why it was refused)."""
        text = str(raw or "").strip()
        if not text:
            return "", "An empty id."
        kind, sep, rest = text.partition(":")
        kind = kind.strip().lower()
        if not sep:
            return self._resolve_bare(text)
        rest = rest.strip()
        if kind in LATER:
            return "", f"'{text}': {kind} ids come once there are {LATER[kind]}."
        if kind not in KINDS:
            return "", (f"'{text}': unknown kind '{kind}'. Use player, "
                        f"{', '.join(k + ':<name>' for k in KINDS)}, street or public.")
        key = resolve_entity_name(rest, self._load()[kind])
        if key is None:
            return "", f"No {kind} '{rest}'{self._suggest(rest, kinds=(kind,))}"
        return f"{kind}:{key}", ""

    def _resolve_bare(self, text: str) -> Tuple[str, str]:
        low = text.lower()
        if low in RUNGS:
            return low, ""
        if self._is_player(text):
            return "player", ""
        hits = [f"{kind}:{key}" for kind in KINDS
                if (key := resolve_entity_name(text, self._load()[kind])) is not None]
        if len(hits) == 1:
            return hits[0], ""
        if hits:
            return "", f"'{text}' fits several: {', '.join(hits)}. Give the kind."
        return "", f"Nothing called '{text}'{self._suggest(text)}"

    def _names(self):
        """(id, name) for every name the text can mention: keys, aliases, the player's name."""
        out = []
        player = self.player_name()
        if player:
            out.append(("player", player))
        for kind in KINDS:
            for key, data in self._load()[kind].items():
                out.append((f"{kind}:{key}", key))
                if isinstance(data, dict):
                    out += [(f"{kind}:{key}", a) for a in data.get("aliases") or [] if a]
        return out

    def mentioned(self, text: str) -> List[str]:
        """Ids whose name appears in `text`, in the order found.

        A name counts only as a whole: case and punctuation may differ, but the
        first letter must be a capital, so "Tally" counts and "keep a tally"
        doesn't. Leading titles and parentheticals are ignored ("the Stalled
        Car" finds "The Stalled Car (Mags Teller)"). A name inside a longer one
        that is also found ("Lantern" in "the Lantern noodle stall") is skipped.
        """
        import re
        found = []  # (start, end, id)
        for cid, name in self._names():
            words = (normalize_entity_name(name) or name).split()
            if not words:
                continue
            pattern = r"(?<!\w)" + r"[\W_]+".join(re.escape(w) for w in words) + r"(?!\w)"
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                if m.group(0)[0].isupper():
                    found.append((m.start(), m.end(), cid))
        found.sort(key=lambda f: (f[0], -(f[1] - f[0])))
        ids, covered = [], []
        for start, end, cid in found:
            if any(s <= start and end <= e for s, e in covered):
                continue
            covered.append((start, end))
            if cid not in ids:
                ids.append(cid)
        return ids

    def resolve_holder(self, raw: str) -> Tuple[str, str]:
        """Like resolve, for who can know a fact: a place can't."""
        cid, error = self.resolve(raw)
        if cid.startswith("location:"):
            return "", (f"'{raw}' is a place, and a place can't know a fact. Use street, "
                        f"public, or the NPCs there.")
        return cid, error

    def present(self) -> List[str]:
        """Default holders in a scene: the player plus the NPCs present (party
        members, and NPCs tagged with the current location; never the dead)."""
        from entity_manager import npcs_present
        overview = self.json_ops.load_json("campaign-overview.json") or {}
        pos = overview.get("player_position") or {}
        here = pos.get("current_location", "") if isinstance(pos, dict) else ""
        return ["player"] + [f"npc:{name}" for name in npcs_present(self._load()["npc"], here)]

    def resolve_all(self, raws, holders: bool = False) -> Tuple[List[str], List[str]]:
        """(ids, errors) for several; duplicates collapse, order is kept.
        `holders` refuses places (see resolve_holder)."""
        ids, errors = [], []
        for raw in raws or []:
            cid, error = self.resolve_holder(raw) if holders else self.resolve(raw)
            if error:
                errors.append(error)
            elif cid not in ids:
                ids.append(cid)
        return ids, errors


def main():
    """`world_ids.py check <id>…` or `world_ids.py list`: for the GM and for testing."""
    from campaign_manager import CampaignManager
    from json_ops import JsonOperations
    args = sys.argv[1:]
    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        print("No active campaign.", file=sys.stderr)
        return 1
    ids = WorldIds(JsonOperations(str(campaign)))
    if args[:1] == ["list"]:
        print("\n".join(ids.all_ids()))
        return 0
    if args[:1] == ["check"] and args[1:]:
        bad = 0
        for raw in args[1:]:
            cid, error = ids.resolve(raw)
            print(f"{raw} → {cid}" if cid else f"{raw}: {error}")
            bad += bool(error)
        return 1 if bad else 0
    print("Usage: world_ids.py list | check <id>…", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
