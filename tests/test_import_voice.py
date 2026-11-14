"""Imported books capture the author's voice — grounded in the real source text.

`draft_voice` keeps only sample passages that appear verbatim in the source, so an
imported world's `voice` is the author's actual prose, and the resulting bible
stays valid for the runtime voice-surfacing path.
"""

import sys
from pathlib import Path

LIB = str(Path(__file__).resolve().parent.parent / "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from book_bible import draft_voice  # noqa: E402 (after lib/ is put on the path)
from world_bible import validate_bible  # noqa: E402 (after lib/ is put on the path)

SOURCE = (
    "The sea gave back its dead, and the dead remembered the names of the living. "
    "Conan laughed, a short hard sound, and set his back to the cold stone."
)


def test_keeps_only_verbatim_passages():
    voice = draft_voice(
        style="terse, blood-dark; muscular cadence; sensory violence",
        sample_passages=[
            "The sea gave back its dead, and the dead remembered the names of the living.",  # verbatim
            "A wise wizard cast a fireball at the goblins.",  # NOT in source -> dropped
        ],
        source_text=SOURCE,
        vocab=["the Drowned"],
    )
    assert voice["style"]
    assert len(voice["sample_passages"]) == 1
    assert voice["sample_passages"][0] in SOURCE
    assert "wizard" not in " ".join(voice["sample_passages"])
    assert voice["vocab"] == ["the Drowned"]


def test_voice_block_makes_a_valid_bible():
    voice = draft_voice("terse and grim", ["Conan laughed, a short hard sound, and set his back to the cold stone."], SOURCE)
    bible = {
        "name": "Hyboria", "voice": voice, "tone": "sword-and-sorcery", "themes": ["doom"],
        "factions": {"nodes": [], "edges": []}, "geography": {"nodes": [], "edges": []},
        "signature_systems": [{"name": "Sorcery is feared"}],
    }
    ok, errs = validate_bible(bible)
    assert ok, errs
    assert bible["voice"]["sample_passages"], "a verbatim passage must survive"


def test_no_invented_passages_when_none_match():
    voice = draft_voice("epic", ["totally invented line not in the book"], SOURCE)
    assert voice["sample_passages"] == []
