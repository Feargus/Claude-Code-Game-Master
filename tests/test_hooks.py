"""The Claude Code settings: the status line is configured, and the one hook is the
check before a shell command that the tools' output is read whole
(test_read_output_whole.py). Nothing runs after a turn: recall reads the facts
directly, so nothing needs refreshing."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_settings_keep_the_statusline_and_one_hook():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert s["statusLine"]["command"] == "bash tools/gm-statusline.sh"
    assert list(s["hooks"]) == ["PreToolUse"]
    [entry] = s["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Bash"
    [hook] = entry["hooks"]
    assert hook["command"] == 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/read-output-whole.py"'
    assert sorted(p.name for p in (ROOT / ".claude" / "hooks").glob("*.py")) == ["read-output-whole.py"]
