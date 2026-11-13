"""Tests for the Stop autosave hook: the config is valid (statusLine preserved)
and the script parses."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_settings_keeps_statusline_and_adds_hooks():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "statusLine" in s, "must not clobber the existing statusLine"
    assert "Stop" in s["hooks"]


def test_hook_scripts_exist_and_parse():
    for name in ("session-autosave.sh",):
        p = ROOT / ".claude" / "hooks" / name
        assert p.exists(), f"missing hook {name}"
        assert subprocess.run(["bash", "-n", str(p)]).returncode == 0
