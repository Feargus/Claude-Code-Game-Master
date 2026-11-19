"""Characterization tests for SessionManager.get_full_context — seam #1.

These snapshot the CURRENT (post-cleanup) behavior so later reimagining tickets
(story-spine-context, untruncate-campaign-rules, ...) can change it deliberately
and see exactly what moved. They also lock in the consequence-display fix.
"""

from pathlib import Path

from lib.session_manager import SessionManager


def _context(dcc_world):
    ctx = SessionManager(dcc_world).get_full_context()
    assert isinstance(ctx, str) and ctx, "get_full_context must return a non-empty string"
    return ctx


def test_context_includes_active_character(dcc_world):
    assert "Tandy" in _context(dcc_world)


def test_a_consequence_in_no_plot_is_listed_there(dcc_world):
    from lib.consequence_manager import ConsequenceManager
    ConsequenceManager(dcc_world).add_consequence("The bouncer remembers", "later")
    ctx = _context(dcc_world)
    assert "--- IN NO PLOT ---" in ctx and "The bouncer remembers (when: later)" in ctx


def test_the_brief_states_only_play_styles_that_differ_from_the_default(dcc_world):
    """Pacing, failure, book inspiration, the action menu and images were five
    lines in every brief, almost always saying the default that CLAUDE.md states
    already (and the menu rule a second time). Only a preference that differs
    from the default is printed."""
    sm = SessionManager(dcc_world)
    assert sm.get_preferences().get("action_menu") is True
    ctx = sm.get_full_context()
    for line in ("action menu", "Pacing:", "Failure:", "Inspiration", "Scene images"):
        assert line not in ctx, line
    sm.set_preference("action_menu", False)
    assert SessionManager(dcc_world).get_preferences().get("action_menu") is False
    assert "action menu OFF" in SessionManager(dcc_world).get_full_context()


def test_the_menu_rule_lives_in_claude_md(dcc_world):
    """In play the options handed the player a GM-only secret to say, promised
    what enemies would do, and invented a decoy. CLAUDE.md carries the rule."""
    claude_md = (Path(__file__).resolve().parent.parent / "CLAUDE.md").read_text(encoding="utf-8")
    assert "exactly THREE numbered options" in claude_md
    assert "never a `[SECRET]` or `[HIDDEN FROM PLAYER]` fact" in claude_md
    assert "adds nothing new" in claude_md
    assert not hasattr(SessionManager, "MENU_RULE")


def test_choices_on_confirmation_says_exactly_three(dcc_world, capsys, monkeypatch):
    """The choices CLI confirmation must match the exactly-three rule."""
    import sys

    import lib.session_manager as sm_mod

    monkeypatch.setattr(sys, "argv", ["session_manager.py", "choices", "on"])
    monkeypatch.setattr(sm_mod, "SessionManager", lambda: SessionManager(dcc_world))
    sm_mod.main()
    out = capsys.readouterr().out
    assert "exactly three numbered" in out


def test_tight_pacing_keeps_opt_in_cap(dcc_world):
    sm = SessionManager(dcc_world)
    sm.set_preference("beat_length", "tight")
    ctx = SessionManager(dcc_world).get_full_context()
    assert "AT MOST ONE new world development" in ctx


def test_pending_consequences_render_real_text_not_unknown(dcc_world):
    """Regression guard for the consequence-display bug.

    The pre-cleanup code iterated the wrong structure and read non-existent
    fields, so every consequence rendered as 'Unknown' (or the section showed
    '(none)'). Real consequence text must appear and the 'Unknown' sentinel
    must not.
    """
    ctx = _context(dcc_world)
    assert any(name in ctx for name in ("Squeeks", "Nightstalker", "Mongo", "Sheol")), (
        "expected at least one real DCC consequence to surface"
    )
    # The bug rendered each consequence as "[id] Unknown -> triggers: ...".
    assert "Unknown -> triggers" not in ctx


def test_pending_consequences_show_their_typed_triggers(dcc_world):
    from lib.consequence_manager import ConsequenceManager
    ConsequenceManager(dcc_world).add_consequence(
        "The bouncer remembers", "when Carl is back at the club",
        triggers=[{"type": "on_location", "match": "Floor 2 Junction"},
                  {"type": "on_npc", "match": "Mordecai"}])
    ctx = _context(dcc_world)
    assert ("(when: when Carl is back at the club; "
            "on_location location:Floor 2 Junction · on_npc npc:Mordecai)") in ctx
