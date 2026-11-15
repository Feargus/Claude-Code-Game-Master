"""Tests for key-facts-reads-choices.

gm-note.sh advertises player_choices and npc_relations; KEY FACTS read only the
three plot_* categories, so the two categories holding what the player DID were
write-only. These assert every advertised category now has a reader.
"""

import re
from pathlib import Path

from lib.note_manager import NoteManager
from lib.session_manager import SessionManager

WRAPPER = Path(__file__).parent.parent / "tools" / "gm-note.sh"


def test_player_choices_reach_the_scene(dcc_world):
    NoteManager(dcc_world).add_fact("player_choices", "Carl spared the goblin scribe")
    ctx = SessionManager(dcc_world).get_full_context()
    assert "spared the goblin scribe" in ctx


def test_npc_relations_reach_the_scene(dcc_world):
    NoteManager(dcc_world).add_fact("npc_relations", "Mordecai now owes Carl a favor")
    ctx = SessionManager(dcc_world).get_full_context()
    assert "owes Carl a favor" in ctx


def test_plot_facts_still_reach_the_scene(dcc_world):
    NoteManager(dcc_world).add_fact("plot_local", "The stairwell is braced open")
    ctx = SessionManager(dcc_world).get_full_context()
    assert "stairwell is braced open" in ctx


def test_every_advertised_category_has_a_reader(dcc_world):
    """No category may be a write-only hole: recall reads every one."""
    help_text = WRAPPER.read_text(encoding="utf-8")
    advertised = set()
    for line in help_text.splitlines():
        if "Categories:" in line or (advertised and line.strip().startswith('"')):
            advertised.update(re.findall(r"\b[a-z]+_[a-z]+\b", line))
        elif advertised:
            advertised.update(re.findall(r"\b[a-z]+_[a-z]+\b", line))
            break
    assert advertised, "could not parse advertised categories from gm-note.sh"

    read_by_key_facts = set()          # the brief reads by plot now, not by category
    for cat in advertised - read_by_key_facts:
        # Reachable through campaign memory, which gathers every facts category.
        NoteManager(dcc_world).add_fact(cat, f"a distinctive {cat} fact about zzyzx")
    from lib.campaign_memory import CampaignMemory
    entries = CampaignMemory(dcc_world).gather()
    sources = {e.get("source", "") for e in entries}
    for cat in advertised - read_by_key_facts:
        assert f"facts:{cat}" in sources, f"{cat} is advertised but nothing reads it"


def test_an_npcs_attitude_is_filed_where_key_facts_reads_it(dcc_world):
    """`gm-npc.sh create` and CLAUDE.md filed how an NPC feels about the player
    under `relations`, a category KEY FACTS didn't read and gm-note.sh didn't
    list; the listed one is `npc_relations`."""
    from lib.npc_manager import NPCManager
    assert NPCManager(dcc_world).create_npc("Vesper", "a fence", "wary, greedy", nowhere=True)
    facts = NoteManager(dcc_world).json_ops.load_json("facts.json")
    assert "relations" not in facts
    assert any(f.get("attitude") and f["fact"] == "wary, greedy" for f in facts["npc_relations"])
    brief = SessionManager(dcc_world).get_full_context()
    assert "regards the player" not in brief       # attitudes are on the cards, by name
    key_facts = brief.split("--- KEY FACTS ---")[-1].split("\n---")[0]
    assert "wary, greedy" not in key_facts
    root = WRAPPER.parent.parent
    for doc in ("CLAUDE.md", ".claude/skills/gm-social/SKILL.md", ".claude/skills/gm-craft/SKILL.md"):
        assert "gm-note.sh relations" not in (root / doc).read_text(encoding="utf-8"), doc


def test_gm_md_says_the_brief_is_the_truth_and_no_session_log_exists():
    """/gm once told the GM to move the character to where the log's last session
    ended. Since 2026-11-14 there is no session log: the plots and facts are the
    record, and /gm end rewrites the plots that moved."""
    text = (WRAPPER.parent.parent / ".claude" / "commands" / "gm.md").read_text(encoding="utf-8")
    assert "Session log is truth" not in text and "gm-session.sh end" not in text
    assert "session-log" not in text and "gm-recall.sh arc" not in text
    assert "gm-plot.sh stands" in text
