"""Tests for world-kit-schema: per-campaign ruleset.json driving the generic core."""

from lib.world_kit import WorldKit


def test_loads_dcc_ruleset(dcc_world):
    k = WorldKit(dcc_world)
    assert k.name() == "Dungeon Crawler Carl"
    assert "npc-builder" in k.active_agents()




def test_campaign_rules_preserved_and_consumed(dcc_world):
    rules = WorldKit(dcc_world).campaign_rules()
    assert "loot_box_system" in rules and "audience_system" in rules


def test_rules_doc_loads_on_demand(dcc_world):
    p = WorldKit(dcc_world).rules_doc_path()
    assert p is not None and p.name == "rules.md"
    assert "resource-axis" in p.read_text(encoding="utf-8")
