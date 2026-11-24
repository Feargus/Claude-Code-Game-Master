"""What is recorded reaches the GM's brief, and the prompts name nothing that
doesn't exist."""

from pathlib import Path

from lib.note_manager import NoteManager
from lib.session_manager import SessionManager

ROOT = Path(__file__).parent.parent


def test_a_new_fact_reaches_the_brief(dcc_world):
    NoteManager(dcc_world).add_fact("Carl spared the goblin scribe")
    assert "spared the goblin scribe" in SessionManager(dcc_world).get_full_context()


def test_an_npcs_attitude_is_a_flagged_fact_shown_by_name(dcc_world):
    from lib.npc_manager import NPCManager
    assert NPCManager(dcc_world).create_npc("Vesper", "a fence", "wary, greedy", nowhere=True)
    facts = NoteManager(dcc_world).json_ops.load_json("facts.json")
    assert any(f.get("attitude") and f["fact"] == "wary, greedy" for f in facts)
    brief = SessionManager(dcc_world).get_full_context()
    assert "regards the player" not in brief       # attitudes are on the cards, by name


def test_the_prompts_record_facts_without_a_category():
    """`gm-note.sh <category> "<fact>"` is refused now, so no prompt may teach it."""
    import re
    verbs = "tell|about|plot|truth|show|find|recent|beat|witness|add"
    old_form = re.compile(r"gm-note\.sh (add )?(?!(?:" + verbs + r")\b)[a-z_]+ \"")
    assert old_form.search('gm-note.sh session_events "x"') and not old_form.search('gm-note.sh tell "f1"')
    for doc in ["CLAUDE.md", *sorted(str(p.relative_to(ROOT)) for p in (ROOT / ".claude").rglob("*.md"))]:
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert not old_form.search(text), f"{doc} still records a fact with a category"
        assert "find --category" not in text and "gm-note.sh categories" not in text, doc


def test_gm_md_says_the_brief_is_the_truth_and_no_session_log_exists():
    """There is no session log: the plots and facts are the record, and /gm end
    rewrites the plots that moved; /gm never sends the GM to a log."""
    text = (ROOT / ".claude" / "commands" / "gm.md").read_text(encoding="utf-8")
    assert "Session log is truth" not in text and "gm-session.sh end" not in text
    assert "session-log" not in text and "gm-recall.sh arc" not in text
