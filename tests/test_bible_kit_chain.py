"""The import chain: source text -> world-bible (the world's own rules go into
ruleset.json with gm-rule.sh define).

Each step reads what the one before wrote. Every fixture is a throwaway tmp
campaign, never a live one.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib import book_bible
from lib.book_bible import ConfirmedBibleError
from lib.world_bible import validate_bible

REPO = Path(__file__).resolve().parent.parent

VERBATIM = "The Iron Tangle ate the station whole, and the trains kept running."

SOURCE = (
    "Chapter One\n"
    "Carl stood barefoot on the platform, counting the exits.\n"
    f"{VERBATIM}\n\n"
    "Chapter Two\n"
    "The loot box hissed open and the crowd, somewhere far above, screamed for more.\n"
)


@pytest.fixture
def campaign(tmp_path):
    """A bare campaign directory holding only the prepared source text."""
    cdir = tmp_path / "campaigns" / "iron-tangle"
    (cdir / "source").mkdir(parents=True)
    (cdir / "source" / "current-document.txt").write_text(SOURCE, encoding="utf-8")
    return cdir


def test_draft_bible_writes_an_unconfirmed_grounded_draft(campaign):
    bible = book_bible.draft_bible(
        campaign,
        name="The Iron Tangle",
        voice={
            "style": "clipped, wry, disaster-comic",
            "sample_passages": [VERBATIM, "A wise wizard cast fireball at the goblins."],
            "vocab": ["loot box"],
        },
    )

    on_disk = json.loads((campaign / "world-bible.json").read_text(encoding="utf-8"))
    assert on_disk == bible
    assert bible["confirmed"] is False
    assert bible["name"] == "The Iron Tangle"
    # Verbatim filter: the real excerpt survives, the invented one does not.
    assert bible["voice"]["sample_passages"] == [VERBATIM]
    # Chapters are not persisted to the bible; segment_into_chapters feeds the RAG
    # coarse index only. The book's names become sketch records, not a bible index.
    assert "chapters" not in bible and "index" not in bible
    # Skeleton keys are present, so the bible validates before the model fills them.
    assert validate_bible(bible) == (True, [])


def test_draft_bible_is_idempotent_and_keeps_authored_fields(campaign):
    book_bible.draft_bible(campaign, name="The Iron Tangle")
    book_bible.draft_bible(campaign, fields={
        "tone": "comedy-horror",
        "signature_systems": ["loot boxes", "viewer counts"],
    })
    bible = book_bible.draft_bible(campaign)  # a third pass must not wipe the above

    assert bible["name"] == "The Iron Tangle"
    assert bible["tone"] == "comedy-horror"
    assert bible["signature_systems"] == ["loot boxes", "viewer counts"]
    assert bible["confirmed"] is False


def test_draft_bible_refuses_a_confirmed_bible(campaign):
    book_bible.draft_bible(campaign, name="The Iron Tangle")
    path = campaign / "world-bible.json"
    approved = json.loads(path.read_text(encoding="utf-8"))
    approved["confirmed"] = True
    path.write_text(json.dumps(approved), encoding="utf-8")

    with pytest.raises(ConfirmedBibleError):
        book_bible.draft_bible(campaign, name="Something Else")
    assert json.loads(path.read_text(encoding="utf-8"))["name"] == "The Iron Tangle"


def test_draft_bible_without_source_text_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        book_bible.draft_bible(tmp_path)


def test_review_survives_string_faction_nodes(dcc_world):
    # The review screen is what the player approves the draft from, and faction
    # nodes are model-authored: conan's live bible lists them as bare strings.
    from lib.world_bible import WorldBible

    path = Path(dcc_world) / "campaigns" / "dungeon-crawler-carl" / "world-bible.json"
    bible = json.loads(path.read_text(encoding="utf-8"))
    bible["factions"] = {"nodes": ["The System", "The Borant Corporation"], "edges": []}
    path.write_text(json.dumps(bible), encoding="utf-8")

    assert WorldBible(dcc_world).review_summary()["factions"] == [
        "The System", "The Borant Corporation"]


def test_cli_drives_the_whole_chain(campaign):
    def run(*args):
        return subprocess.run([sys.executable, str(REPO / "lib" / "book_bible.py"), *args],
                              capture_output=True, text=True)

    assert run("draft-bible", str(campaign), "--name", "The Iron Tangle",
               "--voice-json", json.dumps({"style": "clipped", "sample_passages": [VERBATIM]}),
               "--fields-json", json.dumps({"tone": "clipped dread"})).returncode == 0
    for gone in ("campaign-rules", "write-systems", "draft-ruleset"):   # no such commands
        assert run(gone, str(campaign)).returncode == 2
    assert not (campaign / "ruleset.json").exists()   # gm-rule.sh define makes it
