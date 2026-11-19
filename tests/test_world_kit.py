"""Tests for world-kit-schema: per-campaign ruleset.json driving the generic core."""

from lib.world_kit import WorldKit


def test_loads_dcc_ruleset(dcc_world):
    k = WorldKit(dcc_world)
    assert k.name() == "Dungeon Crawler Carl"
    assert "npc-builder" in k.active_agents()
