"""The KIT block in the brief, and what the World Kit reads (the world's own rules
are world_rules.py: tests/test_world_rules_in_play.py)."""

import json

from lib.session_manager import SessionManager
from lib.world_kit import WorldKit


def _world(tmp_path, slug, ruleset, overview=None):
    world = tmp_path / "world-state"
    campaign = world / "campaigns" / slug
    campaign.mkdir(parents=True)
    (world / "active-campaign.txt").write_text(slug, encoding="utf-8")
    (campaign / "ruleset.json").write_text(json.dumps(ruleset), encoding="utf-8")
    (campaign / "campaign-overview.json").write_text(
        json.dumps(overview or {"name": slug}), encoding="utf-8"
    )
    return str(world)


def _kit_section(ctx: str) -> str:
    assert "--- KIT ---" in ctx
    rest = ctx.split("--- KIT ---", 1)[1]
    nxt = rest.find("\n--- ")
    return rest if nxt < 0 else rest[:nxt]


# --- scene context -----------------------------------------------------------

def test_dcc_context_kit_block(dcc_world):
    ctx = SessionManager(dcc_world).get_full_context()
    kit = _kit_section(ctx)
    assert "kit:" not in kit
    assert "progression" not in kit      # growth is the same for every campaign
    assert "vitals" not in kit       # gone: the world's own rules are world_rules.py


def test_kit_block_skipped_when_worldkit_fails(dcc_world, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("no campaign")

    # The managers import each other by bare name (lib/ on sys.path), so the brief
    # runs as the module "brief", not "lib.brief".
    import importlib
    monkeypatch.setattr(importlib.import_module("brief"), "WorldKit", boom)
    ctx = SessionManager(dcc_world).get_full_context()
    assert "--- KIT ---" not in ctx
    assert "SESSION CONTEXT" in ctx


# --- WorldKit accessors ------------------------------------------------------

def test_worldkit_accepts_dcc_world_dir(dcc_world):
    kit = WorldKit(dcc_world)
    assert kit.skills() == []


def test_skills_from_list_or_empty(tmp_path):
    world = _world(tmp_path, "skilled", {
        "name": "Skilled",
        "skills": ["might", "guile"],
    })
    assert WorldKit(world).skills() == ["might", "guile"]


def test_a_campaign_without_a_ruleset_plays_the_standard_rules(tmp_path):
    """A one-shot has no ruleset.json: it gets no rules of its own and the canon skills."""
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "solo"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("solo")
    (camp / "campaign-overview.json").write_text('{"campaign_name": "Solo"}')
    from lib.world_kit import WorldKit
    kit = WorldKit(str(ws))
    assert kit.name() == "Standard rules"
    brief = SessionManager(str(ws)).get_full_context()
    assert "YOUR WORLD'S RULES" not in brief
    block = _kit_section(brief)
    assert "skills: the standard list (gm-skills)" in block


def test_new_campaigns_have_no_fantasy_default_and_no_session_log(isolated_world_state):
    import json

    from lib.campaign_manager import CampaignManager
    cm = CampaignManager()
    cdir = cm.create("Solo", "Solo")
    overview = json.loads((cdir / "campaign-overview.json").read_text())
    assert "genre" not in overview and "tone" not in overview and overview["current_date"] == ""
    assert not (cdir / "session-log.md").exists()      # plots carry the story (2026-11-14)
    assert "session_count" not in overview
