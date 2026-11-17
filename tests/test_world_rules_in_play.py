"""The world's own rules in play (2026-11-17, step 2): the brief shows them in full,
the cards show a person's or a place's values, the HUD and `gm-player.sh show` the
character's. The old surfaces (campaign_rules, signature_systems, the kit's systems,
vitals) are gone."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import world_rules as wr
from lib.json_ops import JsonOperations
from lib.session_manager import SessionManager

ROOT = Path(__file__).resolve().parent.parent
LONG = ("Lost time: under stress or asleep, something else drives the body for minutes; "
        "narrate only what the character finds when they come back, " * 4).strip()
RULES = [
    {"name": "Bleed", "block": "counter", "held_by": "player", "range": [0, 6],
     "summary": "How much of other people's work has leaked into your head.",
     "when": "After every Lease roll.", "notes": "A dry night lowers it by 1.",
     "results": [{"from": 2, "text": "Intrusions."}, {"from": 4, "text": LONG}]},
    {"name": "Patience", "block": "counter", "held_by": "faction", "known": False,
     "range": [0, 5], "start": 5, "summary": "What a faction will still put up with.",
     "when": "-1 for each slight.", "results": [{"from": 0, "to": 1, "text": "Warnings."}]},
    {"name": "Heat", "block": "counter", "held_by": ["location", "npc"], "range": [0, 10],
     "summary": "Attention from the law.", "when": "+2 for a fight there.",
     "results": [{"from": 3, "text": "Patrols pass by more often."}]},
    {"name": "Sea level", "block": "counter", "held_by": "world", "range": [0, 10],
     "start": 2, "summary": "How far the sea has risen.", "when": "Storms.", "results": []},
]


@pytest.fixture
def ops(dcc_world):
    ops = JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))
    wr.define(ops, RULES)
    wr.set_plain(ops, ["Credits are gold pieces."])
    return ops


def _brief(dcc_world) -> str:
    return SessionManager(dcc_world).get_full_context()


def _rules_section(brief: str) -> str:
    rest = brief.split("--- YOUR WORLD'S RULES (follow exactly) ---", 1)[1]
    return rest.split("\n--- ", 1)[0]


def test_the_brief_shows_the_rules_in_full_once(dcc_world, ops):
    wr.change(ops, "Bleed", by=4)
    wr.change(ops, "Patience", "faction:crawlers", by=-4)
    wr.change(ops, "Heat", "Carl", by=3)
    brief = _brief(dcc_world)
    assert brief.count("YOUR WORLD'S RULES") == 1 and "SIGNATURE SYSTEMS" not in brief
    section = _rules_section(brief)
    assert section.startswith("\n- Credits are gold pieces.\nBleed (counter 0–6, held by the player)")
    assert LONG in section                                            # never cut
    assert "Notes: A dry night lowers it by 1." in section
    assert 'Command: gm-rule.sh change "Bleed" +N|-N' in section
    assert "Now, Tandy: 4 (from 2, from 4)" in section
    assert "Now, The Crawlers: 1 (from 0 to 1) " + wr.HIDDEN in section
    assert "Now, the world: 2 (no result)" in section
    assert "Carl" not in section                                       # people: on their cards
    assert 'values of people and places are on their cards (all: gm-rule.sh show "Heat")' in section


def test_old_rule_surfaces_are_not_shown(dcc_world):
    """The fixture is an old campaign: campaign_rules, signature_systems and rules.md
    are still in its files, and nothing reads them."""
    brief = _brief(dcc_world)
    assert "loot_box_system" not in brief and "YOUR WORLD'S RULES" not in brief
    assert "vitals" not in brief


def test_the_cards_show_a_holders_values(dcc_world, ops):
    from lib.cards import Cards
    wr.change(ops, "Heat", "Carl", by=4)
    wr.change(ops, "Heat", "Bone Garden", by=1)
    cards = Cards(ops)
    person = "\n".join(cards.npc_card("Carl"))
    assert "  rule: Heat 4 (counter 0–10): from 3: Patrols pass by more often." in person
    place = "\n".join(cards.location_card("Bone Garden"))
    assert "Rule here: Heat 1 (counter 0–10): no result" in place
    assert "rule:" not in "\n".join(cards.npc_card("Mordecai"))       # no value, no line


def test_the_player_summary_and_the_hud(dcc_world, ops):
    wr.change(ops, "Bleed", by=3)
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)
    shown = subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh"), "show"],
                           capture_output=True, text=True, env=env)
    assert "| Bleed 3/6" in shown.stdout, shown.stdout + shown.stderr
    assert "vital" not in subprocess.run(["bash", str(ROOT / "tools" / "gm-player.sh")],
                                         capture_output=True, text=True, env=env).stdout


def test_the_hud_shows_known_values_only(tmp_path):
    """gm-statusline.sh reads world-state under the repo root, so it runs on a copy."""
    import shutil
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "gm-statusline.sh", root / "tools")
    camp = root / "world-state" / "campaigns" / "c"
    camp.mkdir(parents=True)
    (root / "world-state" / "active-campaign.txt").write_text("c")
    (camp / "character.json").write_text(json.dumps({"identity": {"name": "Mara"}}))
    (camp / "ruleset.json").write_text(json.dumps({"rules": [
        {**RULES[0]}, {**RULES[0], "name": "Cascade", "known": False}]}))

    def hud():
        out = subprocess.run(["bash", str(root / "tools" / "gm-statusline.sh")], input="{}",
                             capture_output=True, text=True).stdout
        import re
        return re.sub(r"\x1b\[[0-9;]*m", "", out)
    assert "Bleed 0/6" in hud() and "Cascade" not in hud()             # its start; hidden
    (camp / "rule-state.json").write_text(json.dumps(
        {"player": {"Bleed": {"value": 5}, "Cascade": {"value": 2, "known": True}}}))
    assert "Bleed 5/6  Cascade 2/6" in hud()
