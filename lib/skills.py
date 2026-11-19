#!/usr/bin/env python3
"""The skill list: the canon skills of gm-skills, and a campaign's improvised ones.

Every roll names a skill, and so do the sheets. This module is the one place
that knows which skills exist, so a name that isn't one is refused where it is
typed: the dice script used to roll "Lockpicking" (the skill is Larceny) as an
untrained skill without a word, and then teach it to the character.

    canon        the index table at the end of .claude/skills/gm-skills/SKILL.md:
                 name, category, anchor, whether it is common, a line on what it is
    improvised   the campaign's improvised-skills.md, written by the GM in play, in
                 the form the canon skill files use:

                     ## Ratcatching

                     *Anchor: AGI · Status: improvised*

                     Catching small fast things alive.

                 `Status: banned` marks one the player disliked: never used again.

A canon skill can't be redefined by a campaign: the canon entry counts.
"""

import difflib
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from sheet import ATTRIBUTES

SKILLS_DIR = Path(__file__).parent.parent / ".claude" / "skills" / "gm-skills"
SKILLS_FILE = SKILLS_DIR / "SKILL.md"
IMPROVISED_FILE = "improvised-skills.md"
STATUSES = ("canon", "improvised", "banned")
# Words of five letters or more that say nothing about a skill (suggestions).
COMMON_WORDS = {"about", "after", "against", "always", "another", "before", "between", "every",
                "other", "their", "there", "under", "where", "which", "while", "without",
                "anything", "something"}


class SkillError(ValueError):
    """A skill name that can't be used. The message says how to fix it."""


def _key(name: str) -> str:
    return " ".join(str(name).split()).lower()


def canon() -> dict[str, dict[str, Any]]:
    """The canon skills, in the order of the index: {lowercase name: skill}. A
    skill is {"name", "category", "anchor", "common", "short", "status"}."""
    index = SKILLS_FILE.read_text(encoding="utf-8").split("## Index", 1)[-1]
    out = {}
    for line in index.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("", "Skill") or set(cells[0]) <= {"-", " ", ":"}:
            continue
        category = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cells[1])
        out[_key(cells[0])] = {"name": cells[0], "category": category, "anchor": cells[2].upper(),
                               "common": cells[3].lower() == "yes", "short": cells[4],
                               "status": "canon"}
    return out


def improvised(campaign_dir) -> dict[str, dict[str, Any]]:
    """The campaign's own skills: every heading of improvised-skills.md that has
    an anchor or a status under it. Other headings are just headings."""
    path = Path(campaign_dir) / IMPROVISED_FILE if campaign_dir else None
    if path is None or not path.exists():
        return {}
    out, current = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"#{2,4}\s+(.+?)\s*#*\s*$", line)
        if heading:
            current = {"name": " ".join(heading.group(1).split()), "category": "", "anchor": "",
                       "common": False, "short": "", "status": ""}
            continue
        if current is None:
            continue
        anchor = re.search(r"anchor\W+([A-Za-z]{3})\b", line, flags=re.IGNORECASE)
        status = re.search(r"status\W+([A-Za-z]+)", line, flags=re.IGNORECASE)
        anchor = anchor.group(1).upper() if anchor and anchor.group(1).upper() in ATTRIBUTES else ""
        status = status.group(1).lower() if status and status.group(1).lower() in STATUSES else ""
        if anchor or status:
            current["anchor"] = anchor or current["anchor"]
            current["status"] = status or current["status"] or "improvised"
            out[_key(current["name"])] = current
        elif line.strip() and not current["short"] and _key(current["name"]) in out:
            current["short"] = line.strip()
    return out


def table(campaign_dir=None) -> dict[str, dict[str, Any]]:
    """Every skill the campaign has: its improvised ones, then the canon ones,
    which win over an improvised skill of the same name."""
    return {**improvised(campaign_dir), **canon()}


def _mentions() -> dict[str, str]:
    """{lowercase canon name: everything gm-skills says about the skill}: its line
    in the index, and its section in its category file."""
    out = {key: f"{s['name']} {s['category']} {s['short']}" for key, s in canon().items()}
    for path in SKILLS_DIR.glob("*.md"):
        if path == SKILLS_FILE:
            continue
        for section in path.read_text(encoding="utf-8").split("\n## ")[1:]:
            name, _, body = section.partition("\n")
            if _key(name) in out:
                out[_key(name)] += " " + body
    return out


def _alike(a: str, b: str) -> bool:
    """Two words that start the same: "lockpicking" and "locks", "dodge" and "dodging"."""
    shared = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        shared += 1
    return shared >= 4


def suggestions(name: str, skills: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Up to four skills a wrong name may have meant, the likeliest first: those
    of a category of that name ("Perception"), those spelled nearly the same,
    then those whose text in gm-skills uses words like it, most such words first
    ("Lockpicking": Larceny, for "locks" and "picking a lock"). A hint, not a
    ruling: the GM picks from the index."""
    usable = {k: s for k, s in skills.items() if s["status"] != "banned"}
    wanted = _key(name)
    found = [k for k, s in usable.items() if s["category"].lower() == wanted]
    found += [k for k in difflib.get_close_matches(wanted, list(usable), n=3, cutoff=0.75)
              if k not in found]
    words = [w for w in re.findall(r"[a-z]+", wanted) if len(w) >= 4]
    counted = []
    for key, text in _mentions().items():
        said = {s for s in re.findall(r"[a-z]+", text.lower())
                if len(s) >= 5 and s not in COMMON_WORDS}
        hits = sum(1 for s in said if any(_alike(w, s) or (len(s) >= 6 and s in w) for w in words))
        if hits and key in usable and key not in found:
            counted.append((-hits, key))
    found += [key for _, key in sorted(counted, key=lambda pair: pair[0])]
    return [usable[k] for k in found[:4]]


def find(campaign_dir, name: str) -> dict[str, Any]:
    """The skill `name` means, spelled as its entry spells it. Raises SkillError
    for one that doesn't exist (with the skills it may have meant, and how to
    improvise a new one) or is banned."""
    if _key(name) == "default":
        raise SkillError("'default' is not a skill: on an NPC's or a mob's sheet it is the "
                         "value of the skills the sheet doesn't list.")
    skills = table(campaign_dir)
    skill = skills.get(_key(name))
    if skill is None:
        shown = " ".join(str(name).split())
        close = suggestions(shown, skills)
        hint = (" Did you mean: " + "; ".join(f"{s['name']} ({s['short'].rstrip('.')})" if s["short"]
                                              else s["name"] for s in close) + "?") if close else ""
        raise SkillError(
            f"No skill '{shown}'.{hint} The skills are in the gm-skills index. Only if none "
            f"fits (a rare action): improvise it first, by adding to the campaign's "
            f"{IMPROVISED_FILE}\n"
            f"  ## {shown}\n\n"
            f"  *Anchor: <{'|'.join(ATTRIBUTES)}> · Status: improvised*\n\n"
            f"  <one line on what it is>\n"
            f"and use it then.")
    if skill["status"] == "banned":
        raise SkillError(f"'{skill['name']}' is banned in this campaign ({IMPROVISED_FILE}): "
                         f"never use it, or anything like it. Use a canon skill.")
    return skill


def check_anchor(skill: dict[str, Any], attributes: list[str]) -> None:
    """The anchor is always one of the three dice (gm-skills, Building a roll).
    Raises SkillError when it isn't, or when an improvised skill has none."""
    anchor = skill.get("anchor")
    if not anchor:
        raise SkillError(
            f"{skill['name']} has no anchor yet. Give it one in the campaign's {IMPROVISED_FILE}, "
            f"under its heading: *Anchor: <{'|'.join(ATTRIBUTES)}> · Status: improvised*")
    if anchor not in attributes:
        raise SkillError(
            f"{skill['name']} is anchored on {anchor}: one of the three dice must be {anchor} "
            f"(gm-skills, Building a roll). {', '.join(attributes)} is another skill's roll.")
