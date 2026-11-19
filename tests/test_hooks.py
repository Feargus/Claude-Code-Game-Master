"""The Claude Code settings: the status line is configured, and nothing runs on
its own. The Stop hook that autosaved after every turn went with the save system
(2026-11-13); recall reads the facts directly, so nothing needs refreshing."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_settings_keep_the_statusline_and_have_no_hooks():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert s["statusLine"]["command"] == "bash tools/gm-statusline.sh"
    assert "hooks" not in s
    assert not (ROOT / ".claude" / "hooks").exists()
