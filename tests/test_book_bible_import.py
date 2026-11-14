"""Tests for import-longcontext-read: retention + segmentation + bible auto-draft.

The world-bible subagent read is orchestrated by /import (model call, not
hermetic); these cover the deterministic core that the AC can verify.
"""

import json
from pathlib import Path

from lib import book_bible

SAMPLE = (
    "Chapter One\nThe spice must flow. Paul looked across the dunes.\n\n"
    "Chapter Two\nThe Fremen watched from the rocks, patient as stone.\n\n"
    "Chapter Three\nArrakis taught the lesson of the knife: cutting away the incomplete.\n"
)


def test_segmentation_keeps_large_spans_not_tiny_chunks():
    chapters = book_bible.segment_into_chapters(SAMPLE)
    assert len(chapters) == 3  # one per chapter marker
    assert all("text" in c and "index" in c for c in chapters)
    assert "spice must flow" in chapters[0]["text"]


def test_segmentation_falls_back_to_size_windows():
    big = "no markers here. " * 4000  # ~68k chars, no chapter marks
    chapters = book_bible.segment_into_chapters(big, max_chars=20000)
    assert len(chapters) >= 3 and all(len(c["text"]) <= 20000 for c in chapters)


def test_draft_ruleset_from_bible_is_valid_kit():
    bible = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "world-state" / "campaigns"
         / "dungeon-crawler-carl" / "world-bible.json").read_text(encoding="utf-8")
    )
    ruleset = book_bible.draft_ruleset_from_bible(bible)
    assert ruleset["name"] == "Dungeon Crawler Carl"
    assert "resolution" not in ruleset and "progression" not in ruleset


def test_bible_to_campaign_rules_carries_signature_systems():
    bible = {"name": "DCC", "tone": "comedy-horror",
             "signature_systems": ["loot boxes", "viewer counts"]}
    rules = book_bible.bible_to_campaign_rules(bible)
    assert rules["signature_systems"] == ["loot boxes", "viewer counts"]
    assert "follow them exactly" in rules["description"]


def test_token_estimate_is_observable_not_a_cap():
    n = book_bible.log_token_estimate("abcd" * 100, label="test")
    assert n == 100  # 400 chars // 4; never truncates


def test_extractor_no_longer_deletes_source_text():
    src = Path(__file__).resolve().parent.parent / "lib" / "agent_extractor.py"
    text = src.read_text(encoding="utf-8")
    # current-document.txt must NOT be in the active cleanup list (retained now).
    assert "'current-document.txt',  # Source text" not in text
