#!/usr/bin/env python3
"""The one sheet format, for the player, NPCs and mobs.

A sheet is a dict of sections, one level deep. Every kind of sheet uses the same
sections; some only make sense for one kind, and most fields are optional, filled
in when play needs them. Scripts read and write sheets through this module, so
they can rely on the structure.

    identity     name, aliases, race, role, background, affiliation
    look         physique, style, presence
    personality  big_five, demeanor, voice, tells, want, need, values, fears
    stats        attributes, skills, traits, perks, luck (the player only), counters
                 (the campaign's own, e.g. Drift: its ruleset's vitals)
    body         the player: zones, armor, cyberware
                 NPCs and mobs: wounds, armor, cyberware
    items        gear (holstered, in pockets, slung within reach: visible unless an
                 item is marked concealed), inventory (bags and packs: hidden)
    possessions  the player: credits, vehicles, lodging, stashes
    places       NPCs: usual (where they are usually found)
    progress     the player: level, xp, practice
    source       NPCs from a book: passages (what the book says about them, for their
                 voice), document, enhanced_at (gm-enhance.sh apply)
    status       state (alive or dead), cause, died_at, died_game_time, conditions,
                 goal (what they're after right now), party_member,
                 former_player_character

What a person knows, feels, has done and hides is not on the sheet: those are
facts (`gm-note.sh`).

`big_five` is the Big Five personality model in OCEAN order, each a signed whole
number from -3 to +3, 0 being the average person: "O1 C-2 E3 A-1 N2" (openness,
conscientiousness, extraversion, agreeableness, neuroticism; N+ is anxious and
volatile, N- calm under pressure).

The places a sheet lives: the player in character.json, NPCs in npcs.json and
mobs in mobs.json (both keyed by name; identity.name is the same name).
"""

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

KINDS = ("player", "npc", "mob")
# The nine attributes, in the order rolls are written. Defined here only: every
# script that names an attribute imports this list.
ATTRIBUTES = ("STR", "AGI", "DFT", "VIG", "LOG", "ITU", "NRV", "PRS", "EMP")

TEXT, LIST, DICT, INT, BOOL = "text", "list", "dict", "int", "bool"

# section -> field -> type. A section lists every field it can hold.
SECTIONS: dict[str, dict[str, str]] = {
    "identity": {"name": TEXT, "aliases": LIST, "race": TEXT, "role": TEXT,
                 "background": TEXT, "affiliation": TEXT},
    "look": {"physique": TEXT, "style": TEXT, "presence": TEXT},
    "personality": {"big_five": TEXT, "demeanor": TEXT, "voice": TEXT, "tells": TEXT,
                    "want": TEXT, "need": TEXT, "values": TEXT, "fears": TEXT},
    "stats": {"attributes": DICT, "skills": DICT, "traits": DICT, "perks": DICT,
              "luck": DICT, "counters": DICT},
    "body": {"zones": DICT, "wounds": INT, "armor": LIST, "cyberware": LIST},
    "items": {"gear": LIST, "inventory": LIST},
    "possessions": {"credits": INT, "vehicles": LIST, "lodging": LIST, "stashes": LIST},
    "places": {"usual": LIST},
    "source": {"passages": LIST, "document": TEXT, "enhanced_at": TEXT},
    "progress": {"level": INT, "xp": INT, "practice": DICT},
    "status": {"state": TEXT, "cause": TEXT, "died_at": TEXT, "died_game_time": TEXT,
               "conditions": LIST, "goal": TEXT, "party_member": BOOL,
               "former_player_character": BOOL},
}

# Sections a kind may have, and the fields it must have.
ALLOWED = {
    "player": ("identity", "look", "personality", "stats", "body", "items", "possessions",
               "progress", "status"),
    "npc": ("identity", "look", "personality", "stats", "body", "items", "possessions",
            "places", "progress", "status", "source"),
    "mob": ("identity", "look", "stats", "body", "items"),
}
REQUIRED = {
    "player": (("identity", "name"), ("stats", "attributes"), ("body", "zones")),
    "npc": (("identity", "name"),),
    "mob": (("identity", "name"),),   # stats and wounds come before the first roll or fight
}

BIG_FIVE = "OCEAN"
BIG_FIVE_RANGE = (-3, 3)
STATES = ("alive", "dead")


class SheetError(ValueError):
    """A sheet that doesn't fit the format. The message says what to fix."""


def blank(kind: str, name: str) -> dict[str, Any]:
    """The smallest valid start of a sheet of `kind`; the rest is filled in later."""
    if kind not in KINDS:
        raise SheetError(f"A sheet is one of {', '.join(KINDS)}, not {kind!r}.")
    sheet: dict[str, Any] = {"identity": {"name": name}}  # a mob's note: identity.background
    if kind == "player":
        sheet["stats"] = {"attributes": {}}
        sheet["body"] = {"zones": {}}
    return sheet


def is_die(size: Any) -> bool:
    """An attribute is a die size: a whole number of at least 2."""
    return isinstance(size, int) and not isinstance(size, bool) and size >= 2


def check_die(attribute: str, size: Any) -> int:
    """`size` if it is a die size, else SheetError naming the attribute."""
    if not is_die(size):
        raise SheetError(f"{attribute}: a die size is a whole number of at least 2, not {size!r}.")
    return size


def check_big_five(text: str) -> str:
    """'O1 C-2 E3 A-1 N2' (spacing and case forgiven), or SheetError."""
    pairs = re.findall(r"([OCEAN])\s*([+-]?\d+)", str(text).upper())
    low, high = BIG_FIVE_RANGE
    if [letter for letter, _ in pairs] != list(BIG_FIVE) or \
            not all(low <= int(v) <= high for _, v in pairs) or \
            re.sub(r"[OCEAN]\s*[+-]?\d+|[\s,]", "", str(text).upper()):
        raise SheetError(f"big_five is the Big Five in OCEAN order, each from {low} to "
                         f"+{high}, 0 the average person: e.g. \"O1 C-2 E3 A-1 N2\"; "
                         f"got {text!r}.")
    return " ".join(f"{letter}{int(v)}" for letter, v in pairs)


def _type_ok(value: Any, kind: str) -> bool:
    if kind == TEXT:
        return isinstance(value, str)
    if kind == LIST:
        return isinstance(value, list)
    if kind == DICT:
        return isinstance(value, dict)
    if kind == INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == BOOL:
        return isinstance(value, bool)
    return True


def check(sheet: dict[str, Any], kind: str) -> dict[str, Any]:
    """Check a sheet of `kind` against the format; returns it with big_five tidied.
    Raises SheetError naming the first problem."""
    if kind not in KINDS:
        raise SheetError(f"A sheet is one of {', '.join(KINDS)}, not {kind!r}.")
    if not isinstance(sheet, dict):
        raise SheetError("A sheet is an object of sections.")
    for section, content in sheet.items():
        if section not in SECTIONS:
            raise SheetError(f"Unknown section '{section}'. Sections: "
                             f"{', '.join(s for s in SECTIONS if s in ALLOWED[kind])}.")
        if section not in ALLOWED[kind]:
            raise SheetError(f"A {kind} sheet has no '{section}' section.")
        if not isinstance(content, dict):
            raise SheetError(f"'{section}' is a section: an object of fields.")
        for field, value in content.items():
            expected = SECTIONS[section].get(field)
            if expected is None:
                raise SheetError(f"'{section}' has no field '{field}'. Its fields: "
                                 f"{', '.join(SECTIONS[section])}.")
            if not _type_ok(value, expected):
                raise SheetError(f"{section}.{field} is a {expected}, not {value!r}.")
    for section, field in REQUIRED[kind]:
        if field not in (sheet.get(section) or {}):
            raise SheetError(f"A {kind} sheet needs {section}.{field}.")
    personality = sheet.get("personality") or {}
    if personality.get("big_five"):
        personality["big_five"] = check_big_five(personality["big_five"])
    state = (sheet.get("status") or {}).get("state")
    if state is not None and state not in STATES:
        raise SheetError(f"status.state is alive or dead, not {state!r}.")
    attributes = (sheet.get("stats") or {}).get("attributes") or {}
    for key, size in attributes.items():
        if key != "default" and key not in ATTRIBUTES:
            raise SheetError(f"Unknown attribute '{key}'. Use: {', '.join(ATTRIBUTES)}.")
        check_die(key, size)
    for name, value in ((sheet.get("stats") or {}).get("skills") or {}).items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise SheetError(f"{name}: a skill value is a whole number, not {value!r}.")
    return sheet


# ---------- reading a sheet ----------

def name(sheet: dict[str, Any]) -> str:
    return str((sheet.get("identity") or {}).get("name") or "")


def section(sheet: dict[str, Any], key: str) -> dict[str, Any]:
    """A section, created empty if missing (for writing into it)."""
    return sheet.setdefault(key, {})


def get(sheet: dict[str, Any], key: str, field: str, default: Any = None) -> Any:
    return (sheet.get(key) or {}).get(field, default)


def attributes(sheet: dict[str, Any]) -> dict[str, int]:
    return get(sheet, "stats", "attributes") or {}


def skills(sheet: dict[str, Any]) -> dict[str, int]:
    return get(sheet, "stats", "skills") or {}


def aliases(sheet: dict[str, Any]) -> list[str]:
    return [a for a in get(sheet, "identity", "aliases") or [] if a]


def is_dead(sheet: dict[str, Any]) -> bool:
    return get(sheet, "status", "state") == "dead"


def conditions(sheet: dict[str, Any]) -> list[str]:
    return list(get(sheet, "status", "conditions") or [])


def look_line(sheet: dict[str, Any]) -> str:
    """The look in one line, for narration and image prompts."""
    look = sheet.get("look") or {}
    return "; ".join(look[f] for f in ("physique", "style", "presence") if look.get(f))


# ---------- items ----------

ITEM_PLACES = ("gear", "inventory")


def item(value: Any) -> dict[str, Any]:
    """An item as stored: {"name", "concealed"?, "note"?}. A plain string is a name."""
    if isinstance(value, str):
        return {"name": value}
    if isinstance(value, dict) and isinstance(value.get("name"), str) and value["name"]:
        unknown = set(value) - {"name", "concealed", "note"}
        if unknown:
            raise SheetError(f"An item has a name, and may be concealed or have a note; "
                             f"not {', '.join(sorted(unknown))}.")
        return dict(value)
    raise SheetError(f"An item is a name or {{\"name\": ...}}, not {value!r}.")


def items(sheet: dict[str, Any], place: str) -> list[dict[str, Any]]:
    return [item(i) for i in get(sheet, "items", place) or []]


def visible_items(sheet: dict[str, Any]) -> list[str]:
    """What others see at a glance: gear that isn't concealed. The inventory is hidden."""
    return [i["name"] for i in items(sheet, "gear") if not i.get("concealed")]


# ---------- moving between kinds ----------

def merge(base: dict[str, Any], given: dict[str, Any]) -> dict[str, Any]:
    """`base` with `given` laid over it, section by section (given wins per field)."""
    out = {key: dict(value) if isinstance(value, dict) else value for key, value in base.items()}
    for key, value in given.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def as_npc(player: dict[str, Any], wounds: int = 3) -> dict[str, Any]:
    """An outgoing player character as an NPC sheet: the same sheet, with an NPC's
    wound count next to the zones, no luck, and marked as a former player character."""
    npc = merge(player, {})
    npc.get("stats", {}).pop("luck", None)
    section(npc, "body").setdefault("wounds", wounds)
    section(npc, "status")["former_player_character"] = True
    section(npc, "status").pop("party_member", None)
    return npc


def from_npc(npc: dict[str, Any]) -> dict[str, Any]:
    """A canon NPC's sheet as the base of a player sheet: what carries over (identity,
    look, personality, stats, items, possessions); body and status start fresh."""
    keep = ("identity", "look", "personality", "stats", "items", "possessions")
    base = {key: merge(npc, {})[key] for key in keep if key in npc}
    base.get("stats", {}).pop("counters", None)
    return base


# ---------- editing: the text fields every `set` command takes ----------

# command-line flag -> (section, field). Used by gm-player.sh set and gm-npc.sh
# create/set, so both take the same flags.
TEXT_FIELDS = {
    "race": ("identity", "race"), "role": ("identity", "role"),
    "background": ("identity", "background"), "affiliation": ("identity", "affiliation"),
    "physique": ("look", "physique"), "style": ("look", "style"),
    "presence": ("look", "presence"),
    "big-five": ("personality", "big_five"), "demeanor": ("personality", "demeanor"),
    "voice": ("personality", "voice"), "tells": ("personality", "tells"),
    "want": ("personality", "want"), "need": ("personality", "need"),
    "values": ("personality", "values"), "fears": ("personality", "fears"),
    "goal": ("status", "goal"),
}


def add_field_flags(parser) -> None:
    """--race, --physique, --big-five ... on an argparse parser."""
    for flag, (sec, field) in TEXT_FIELDS.items():
        parser.add_argument(f"--{flag}", dest=f"field_{field}", metavar="TEXT",
                            help=f"{sec}.{field}" + (' (Big Five, OCEAN: "O1 C-2 E3 A-1 N2")'
                                                    if field == "big_five" else ""))


def fields_from_args(args) -> dict[str, str]:
    """{flag: value} for the field flags given (an empty string clears a field)."""
    out = {}
    for flag, (_, field) in TEXT_FIELDS.items():
        value = getattr(args, f"field_{field}", None)
        if value is not None:
            out[flag] = value
    return out


def set_fields(sheet: dict[str, Any], values: dict[str, str]) -> list[str]:
    """Set text fields by flag name; an empty value clears the field. Returns what
    changed, as "section.field" names. Raises SheetError for an unknown flag or a
    bad big_five."""
    changed = []
    for flag, value in values.items():
        if flag not in TEXT_FIELDS:
            raise SheetError(f"No field '{flag}'. Fields: {', '.join(TEXT_FIELDS)}.")
        sec, field = TEXT_FIELDS[flag]
        value = str(value).strip()
        if field == "big_five" and value:
            value = check_big_five(value)
        target = section(sheet, sec)
        if value:
            target[field] = value
        else:
            target.pop(field, None)
            if not target:
                del sheet[sec]
        changed.append(f"{sec}.{field}")
    return changed


# ---------- items ----------

def add_item(sheet: dict[str, Any], place: str, name: str, concealed: bool = False,
             note: str = "") -> dict[str, Any]:
    if place not in ITEM_PLACES:
        raise SheetError(f"An item goes into gear or inventory, not {place!r}.")
    if not str(name).strip():
        raise SheetError("An item needs a name.")
    entry = {"name": str(name).strip()}
    if concealed:
        entry["concealed"] = True
    if note:
        entry["note"] = note
    section(sheet, "items").setdefault(place, []).append(entry)
    return entry


def remove_item(sheet: dict[str, Any], name: str) -> dict[str, Any]:
    """Remove the first item whose name matches (exactly, then as part of the name),
    gear before inventory. Returns it with its place; SheetError if none."""
    wanted = str(name).strip().lower()
    for exact in (True, False):
        for place in ITEM_PLACES:
            stored = get(sheet, "items", place) or []
            for index, value in enumerate(stored):
                entry = item(value)
                low = entry["name"].lower()
                if (low == wanted) if exact else (wanted in low):
                    del stored[index]
                    return dict(entry, place=place)
    held = [i["name"] for p in ITEM_PLACES for i in items(sheet, p)]
    raise SheetError(f"No item '{name}'. Carried: {', '.join(held) or 'nothing'}.")


# ---------- showing ----------

def _item_text(entry: dict[str, Any]) -> str:
    extra = [x for x in ("concealed" if entry.get("concealed") else "", entry.get("note", "")) if x]
    return entry["name"] + (f" ({', '.join(extra)})" if extra else "")


def describe(sheet: dict[str, Any]) -> list[str]:
    """The sheet as readable lines, section by section; empty fields left out."""
    lines = []
    for sec in ("identity", "look", "personality", "status", "places", "possessions", "progress"):
        content = sheet.get(sec) or {}
        for field, value in content.items():
            if value in ("", [], {}, None) or (sec, field) == ("identity", "name"):
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                value = ", ".join(f"{k} {v}" for k, v in value.items())
            lines.append(f"{field.replace('_', ' ')}: {value}")
    stats = sheet.get("stats") or {}
    attrs = stats.get("attributes") or {}
    if attrs:
        order = [a for a in ATTRIBUTES if a in attrs] + (["default"] if "default" in attrs else [])
        lines.append("attributes: " + ", ".join(f"{a} d{attrs[a]}" for a in order))
    if stats.get("skills"):
        lines.append("skills: " + ", ".join(f"{k} {v}" for k, v in stats["skills"].items()))
    for kind in ("traits", "perks"):
        for key, effect in (stats.get(kind) or {}).items():
            lines.append(f"{kind[:-1]}: {key}" + (f": {effect}" if effect else ""))
    if stats.get("luck"):
        lines.append(f"luck: {stats['luck'].get('current')}/{stats['luck'].get('max')}")
    for key, value in (stats.get("counters") or {}).items():
        shown = f"{value.get('current')}/{value.get('max')}" if isinstance(value, dict) else value
        lines.append(f"{key}: {shown}")
    if "wounds" in (sheet.get("body") or {}):
        lines.append(f"wounds: {sheet['body']['wounds']}")
    for place in ITEM_PLACES:
        listed = items(sheet, place)
        if listed:
            lines.append(f"{place}: " + "; ".join(_item_text(i) for i in listed))
    return lines
