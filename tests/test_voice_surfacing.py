"""The world's authorial voice reaches the GM's scene context every beat.

`get_full_context` must surface a `NARRATIVE VOICE` block (style + sample passages)
from `world-bible.json` so the GM narrates in the author's voice — and must NOT
emit a stray block when no voice exists.
"""

import json
import sys
from pathlib import Path

LIB = str(Path(__file__).resolve().parent.parent / "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from session_manager import SessionManager  # noqa: E402 (after lib/ is put on the path)


def _campaign(tmp_path, voice=None):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    (camp / "campaign-overview.json").write_text(json.dumps(
        {"campaign_name": "C", "player_position": {"current_location": "X"}}))
    if voice is not None:
        (camp / "world-bible.json").write_text(json.dumps({
            "name": "C", "voice": voice, "tone": "t", "themes": [],
            "factions": {"nodes": [], "edges": []}, "geography": {"nodes": [], "edges": []},
            "signature_systems": []}))
    return str(ws)


def test_voice_block_surfaces_style_and_passages(tmp_path):
    ws = _campaign(tmp_path, {
        "style": "terse, blood-dark Howard cadence",
        "vocab": ["toll-sworn"],
        "sample_passages": ["The sea gave back its dead, and the dead remembered."]})
    out = SessionManager(world_state_dir=ws).get_full_context()
    assert "--- NARRATIVE VOICE" in out
    assert "Howard cadence" in out
    assert "gave back its dead" in out          # passage is an imitation target
    assert "toll-sworn" in out                  # in-world vocab favored
    assert "NOT lore" in out                    # framed as prose target, not facts


def test_no_block_without_bible(tmp_path):
    out = SessionManager(world_state_dir=_campaign(tmp_path, None)).get_full_context()
    assert "NARRATIVE VOICE" not in out


def test_no_block_for_empty_voice(tmp_path):
    out = SessionManager(world_state_dir=_campaign(tmp_path, {"style": "", "sample_passages": []})).get_full_context()
    assert "NARRATIVE VOICE" not in out
