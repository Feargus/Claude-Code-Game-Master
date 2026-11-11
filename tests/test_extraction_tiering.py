"""Background plots: a plot marked `background: true` is real but not what the scene
is about; and location tags are a hint for search, not presence. (The import's
census, which set the tiers, is gone since 2026-11-11; the tier stays readable.)"""

import json

from lib.plot_manager import PlotManager
from lib.search import WorldSearcher
from lib.session_manager import SessionManager


def _world_with_plots(tmp_path, plots):
    world = tmp_path / "world-state"
    (world / "campaigns" / "camp").mkdir(parents=True)
    (world / "active-campaign.txt").write_text("camp")
    (world / "campaigns" / "camp" / "plots.json").write_text(json.dumps(plots))
    return world


TIERED_PLOTS = {
    "The Spine": {"type": "main", "status": "active"},
    "The Siege": {"type": "threat", "status": "active"},
    "The Errand": {"type": "side", "status": "active"},
    "Tavern Gossip": {"type": "side", "status": "active", "background": True},
    "A Rumour": {"type": "side", "status": "active", "background": True},
    "Old Debt": {"type": "personal", "status": "active", "background": True},
}


def test_scene_context_story_threads_skip_background_plots(tmp_path):
    """Background plots are real, but they are not what the scene is about."""
    world = _world_with_plots(tmp_path, TIERED_PLOTS)
    threads = SessionManager(str(world))._active_plot_threads(limit=None)

    assert len(threads) == 3
    named = " ".join(threads)
    for live in ("The Spine", "The Siege", "The Errand"):
        assert live in named
    for held in ("Tavern Gossip", "A Rumour", "Old Debt"):
        assert held not in named


def test_plot_threads_output_discloses_the_background_count(tmp_path):
    """The GM has to know they exist, or tiering reads as data loss."""
    world = _world_with_plots(tmp_path, TIERED_PLOTS)
    pm = PlotManager(str(world))
    out = pm.format_threads(pm.get_active_threads())

    assert "+3 background plots" in out
    assert "The Spine" in out
    assert "Tavern Gossip" not in out


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
