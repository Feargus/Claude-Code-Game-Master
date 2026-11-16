"""The skill list (lib/skills.py): the canon skills of gm-skills, read from its index."""

import re

from lib import skills


def test_the_index_gives_every_canon_skill_with_its_anchor():
    canon = skills.canon()
    assert len(canon) == 31
    assert canon["long guns"] == {"name": "Long guns", "category": "Combat", "anchor": "DFT",
                                  "common": False, "status": "canon",
                                  "short": "Guns braced on the shoulder."}
    assert canon["guard"]["common"] and canon["guard"]["anchor"] == "ITU"
    assert all(s["anchor"] in skills.ATTRIBUTES for s in canon.values())


def test_the_index_and_the_skill_files_name_the_same_anchors():
    """The roll script reads the anchor from the index; the GM reads it in the
    skill's own file. A skill whose two anchors differ would be refused for the
    roll its file describes."""
    canon = skills.canon()
    seen = set()
    for path in skills.SKILLS_DIR.glob("*.md"):
        if path == skills.SKILLS_FILE:
            continue
        for section in path.read_text(encoding="utf-8").split("\n## ")[1:]:
            name, _, body = section.partition("\n")
            anchor = re.search(r"Anchor: (\w+)", body)
            assert name.strip().lower() in canon, f"{path.name}: {name} is not in the index"
            assert anchor and anchor.group(1) == canon[name.strip().lower()]["anchor"], name
            seen.add(name.strip().lower())
    assert seen == set(canon)


def test_a_wrong_name_gets_the_skills_it_may_have_meant():
    table = skills.table()
    def names(wrong):
        return [s["name"] for s in skills.suggestions(wrong, table)]
    assert names("Lockpicking")[0] == "Larceny"           # "locks", "picking a lock"
    assert names("Hand guns")[0] == "Handguns"            # spelling
    assert names("Dodge") == ["Evasion"]                  # "dodging"
    assert names("Perception")[:3] == ["Investigation", "Awareness", "Insight"]   # a category
    assert names("Xyzzy") == []
