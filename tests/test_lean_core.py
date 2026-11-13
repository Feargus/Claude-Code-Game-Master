"""Tests for claudemd-lean-core-router: lean CLAUDE.md + mechanics/craft/framework Skills.

CLAUDE.md was swapped to the lean core (the 1227-line original is in git history).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALL_SKILLS = ["gm-combat", "gm-conditions", "gm-death", "gm-growth",
              "gm-sites", "gm-images", "gm-craft", "gm-skills", "gm-social"]


def _claude_md():
    return (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_claude_md_is_lean():
    text = _claude_md()
    assert len(text.splitlines()) < 320, "CLAUDE.md should be the lean core now"
    assert "LEAN CORE" in text


def test_lean_core_keeps_always_on_essentials():
    text = _claude_md()
    assert "## The Core Loop" in text
    assert "Persist" in text
    assert "Action Router" in text
    assert "Golden Rules" in text


def test_lean_core_routes_to_all_skills_not_inline_tables():
    text = _claude_md()
    for skill in ALL_SKILLS:
        assert skill in text, f"CLAUDE.md must route to {skill}"
    assert "25,000" not in text  # no inline XP-by-CR table


def test_lean_core_drops_beat_mandates():
    text = _claude_md()
    assert "exactly 3 numbered" not in text
    assert "AT MOST ONE new world development" not in text
    assert "Test before sending" not in text


def test_the_death_protocol_is_a_skill_stated_once():
    """It was written out in CLAUDE.md (every turn) and again in gm.md (loaded at
    session start, long before anyone dies). It is the gm-death skill; CLAUDE.md
    keeps the one step that can't be repaired afterwards: persist the death, with
    its cause, before anything else."""
    claude, gm = _claude_md(), (ROOT / ".claude" / "commands" / "gm.md").read_text(encoding="utf-8")
    skill = (ROOT / ".claude" / "skills" / "gm-death" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Death Protocol" not in claude and "CHARACTER DEATH" not in gm
    assert "--replace" not in claude and "fallen/" not in claude      # the swap rules moved
    for part in ("gm-player.sh kill --cause", "hand-off", "--canon", "--replace", "fallen/",
                 "gm-note.sh witness"):
        assert part in skill, part
    for line in claude.splitlines():
        if "gm-death" in line:
            assert "gm-player.sh kill --cause" in line, line
            assert line.index("gm-player.sh kill --cause") < line.index("gm-death"), line
    assert sum("gm-death" in line for line in claude.splitlines()) == 3
    assert "Stakes & Death" in claude                                   # the rules before a death stay


def test_lean_core_keeps_load_bearing_sections():
    # The audit's must-restore-inline items.
    text = _claude_md()
    assert "Movement" in text
    assert "Output Format" in text
    assert "Auto Memory Policy" in text
    assert "uv run python" in text
    assert "Search Guide" in text


def test_all_skills_exist_with_frontmatter():
    for name in ALL_SKILLS:
        p = ROOT / ".claude" / "skills" / name / "SKILL.md"
        assert p.exists(), f"missing skill {name}"
        assert f"name: {name}" in p.read_text(encoding="utf-8")


def test_craft_skill_preserves_the_soul():
    text = (ROOT / ".claude" / "skills" / "gm-craft" / "SKILL.md").read_text(encoding="utf-8")
    assert "Yes, and" in text and "Persist before narrating" in text


def test_no_skill_instructs_world_kit_info():
    for name in ALL_SKILLS:
        text = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "world_kit.py info" not in text, (
            f"{name} must not instruct world_kit.py info for what context now carries"
        )


def test_world_kit_info_runs():
    import json
    import subprocess
    import sys as _sys
    r = subprocess.run([_sys.executable, str(ROOT / "lib" / "world_kit.py"), "info", "--json"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)["data"]
    assert "kit" not in data and "progression_model" not in data


def test_gm_md_holds_no_rules_for_the_middle_of_play():
    """/gm is put into the conversation once, when it is typed. Its action-menu
    and gameplay-loop sections repeated CLAUDE.md and the brief, a second copy
    to keep in step."""
    gm = (ROOT / ".claude" / "commands" / "gm.md").read_text(encoding="utf-8")
    assert "## ACTION MENU" not in gm and "## GAMEPLAY LOOP" not in gm
    assert "gm-session.sh choices" in gm          # /gm choices is still routed
    claude = _claude_md()
    assert "choices on|off|toggle" in claude and "CONTEXT → DECIDE → EXECUTE → PERSIST → NARRATE" in claude
