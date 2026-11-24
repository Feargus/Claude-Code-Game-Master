"""Location tags are a hint for search, not presence. ("background" is a plot kind,
sorted last.)"""

import json

from lib.search import WorldSearcher


def _world_with_plots(tmp_path, plots):
    world = tmp_path / "world-state"
    (world / "campaigns" / "camp").mkdir(parents=True)
    (world / "active-campaign.txt").write_text("camp")
    (world / "campaigns" / "camp" / "plots.json").write_text(json.dumps(plots))
    return world



def test_tag_gate_decides_presence_not_the_tier(tmp_path):
    """A background NPC is present iff tagged here — the same bar an active one clears."""
    world = tmp_path / "world-state"
    (world / "campaigns" / "camp").mkdir(parents=True)
    (world / "active-campaign.txt").write_text("camp")
    (world / "campaigns" / "camp" / "npcs.json").write_text(json.dumps({
        "Tagged Walkon": {"places": {"usual": ["The Hub"]}},
        "Untagged Walkon": {"places": {"usual": []}},
        "Tagged Lead": {"places": {"usual": ["The Hub"]}},
        "Elsewhere Lead": {"places": {"usual": ["Far Shore"]}},
    }))
    present = WorldSearcher(str(world)).search_npcs_by_tag("locations", "The Hub")

    assert set(present) == {"Tagged Walkon", "Tagged Lead"}
    assert "Untagged Walkon" not in present    # tiering leaks nothing into the scene
    assert "Elsewhere Lead" not in present
